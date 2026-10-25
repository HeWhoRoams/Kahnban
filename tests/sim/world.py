"""A throwaway repository, a plan for the scripted agents, and a driver that checks as it goes."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import core, gitops, runner
from kahnban.cli import main as kahnban_main
from conftest import git, init_repo, scaffold_board, write_ticket

from .invariants import Checker

PY = sys.executable
AGENT = Path(__file__).resolve().parent / "agent.py"
SRC = str(Path(__file__).resolve().parents[2] / "src")
ROLES = ("coder", "qa_reviewer", "spec_analyst", "curator")


@dataclass
class Outcome:
    config: core.Config
    result: runner.RunResult
    checker: Checker
    seconds: float
    commits: int
    agent_log: list[dict[str, Any]] = field(default_factory=list)


class World:
    def __init__(
        self,
        root: Path,
        *,
        tickets: int,
        seed: int = 0,
        extra_files: dict[str, str] | None = None,
        **config: object,
    ) -> None:
        self.root = root
        self.extra_files = extra_files or {}
        self.human: Callable[[core.Config, runner.RunResult], bool] | None = None
        self.seed = seed
        self.repo = init_repo(root / "repo")
        self.sim_dir = root / "sim"
        self.sim_dir.mkdir()
        self.policies = {role: "honest" for role in ROLES}
        self.plan: dict[str, Any] = {"tickets": {}}
        self.count = tickets
        self.config_overrides = config
        self.max_steps = 40
        for n in range(1, tickets + 1):
            (self.repo / "src").mkdir(exist_ok=True)
            (self.repo / "src" / f"m{n}.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        for relative, text in self.extra_files.items():
            (self.repo / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / relative).write_text(text, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "modules return 1")

    # --- building the board ------------------------------------------------

    def ticket_id(self, n: int) -> str:
        return f"TST-{n:03d}"

    def add_ticket(
        self,
        n: int,
        *,
        column: str = "2-ready",
        depends_on: tuple[int, ...] = (),
        extra_radius: tuple[str, ...] = (),
    ) -> str:
        """Ticket ``n`` makes ``src/m{n}.py`` return 2; its own check proves it."""
        ident = self.ticket_id(n)
        module, check = f"src/m{n}.py", f"tests/check_m{n}.py"
        command = f"{PY} {check}"
        criterion = f"f() returns 2 (test: `{command}`)"
        radius = (module, check, *extra_radius)
        self.plan["tickets"][ident] = {
            "files": {
                module: "def f():\n    return 2\n",
                check: f"import sys\nsys.path.insert(0, 'src')\nfrom m{n} import f\nassert f() == 2, f()\n",
            },
            "validation": command,
            "spec": {
                "criteria": f"- [ ] {criterion}",
                "radius": "\n".join(f"- `{item}`" for item in radius),
                "validation": command,
            },
        }
        self._columns = getattr(self, "_columns", {})
        self._columns[ident] = column
        self._pending = getattr(self, "_pending", [])
        self._pending.append((n, ident, column, depends_on, radius, command, criterion))
        return ident

    def build(self) -> core.Config:
        overrides = {
            "require_proof": True,
            "require_review": True,
            "require_integration": True,
            "workers": {role: f"{PY} {AGENT} {self.policies[role]}" for role in ROLES}
            | {"default": f"{PY} {AGENT} honest"},
            "worker_timeout_sec": 120,
            **self.config_overrides,
        }
        scaffold_board(self.repo, overrides)
        config = core.load_config(self.repo)
        backlog = [p for p in self._pending if p[2] == "0-backlog"]
        for n, ident, column, depends_on, radius, command, criterion in self._pending:
            if column == "0-backlog":
                continue
            write_ticket(
                config.board_path,
                "1-refining",
                ident,
                f"m{n}",
                title=f"Make m{n}.f return 2",
                acceptance=(f"- [ ] {criterion}",),
                blast_radius=radius,
                validation=command,
                depends_on="[" + ", ".join(self.ticket_id(d) for d in depends_on) + "]",
            )
        git(self.repo, "add", "-A")
        if gitops.status_porcelain(self.repo):
            git(self.repo, "commit", "-m", "refine tickets")
        for _n, ident, column, *_rest in self._pending:
            if column == "2-ready":
                core.ready(config, ident)
        for n, ident, *_rest in sorted(backlog):
            code = kahnban_main(
                ["--project-root", str(self.repo), "new", f"Make m{n}.f return 2", "--problem", f"m{n}.f returns 1"]
            )
            assert code == 0, f"could not create backlog ticket {ident}"
        return config

    # --- running -------------------------------------------------------------

    def run(self) -> Outcome:
        config = self.build()
        plan_path = self.sim_dir / "plan.json"
        plan_path.write_text(json.dumps(self.plan, indent=2), encoding="utf-8")
        environment = {
            "KAHNBAN_SIM_PLAN": str(plan_path),
            "KAHNBAN_SIM_DIR": str(self.sim_dir),
            "KAHNBAN_KEY_DIR": str(self.root / "keys"),
            "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        saved = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        try:
            checker = Checker(config, self.plan)
            before = checker.head
            started = time.monotonic()
            result = runner.run(config, max_steps=self.max_steps, echo=checker.after_step)
            while self.human is not None and self.human(config, result):
                more = runner.run(config, max_steps=self.max_steps, echo=checker.after_step)
                result.steps.extend(more.steps)
                result.stopped, result.parked = more.stopped, more.parked
            seconds = time.monotonic() - started
            checker.finalize(runner)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        commits = len(checker.commits_since(before))
        log_file = self.sim_dir / "agent-log.jsonl"
        entries = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()] if log_file.exists() else []
        checker.audit({".gitignore", "README.md", *self.extra_files}, entries)
        guard_files = (config.board_path / core.ARTIFACT_DIR).glob("*.guard")
        result.guard_refusals = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in guard_files)
        return Outcome(config, result, checker, seconds, commits, entries)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
