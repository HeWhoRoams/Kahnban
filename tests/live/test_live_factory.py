"""Real agents through the real gates. Opt in with KAHNBAN_LIVE=1; it spends model usage and takes minutes.

    KAHNBAN_LIVE=1 KAHNBAN_LIVE_RUNS=3 KAHNBAN_LIVE_MODEL=haiku python -m pytest tests/live -q -s

Each run: a toy repository with one bare idea on the board, ``kahnban run`` with the default worker
(``claude -p`` as each role), and a check that the ticket ended done or was escalated with a reason,
never half-moved. The first-pass yield and step count of every run are printed so runs can be compared
by their medians; one run proves little, because the agent is not deterministic.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from kahnban import core, runner

ROOT = Path(__file__).resolve().parents[2]
RUNS = int(os.environ.get("KAHNBAN_LIVE_RUNS", "1"))
MODEL = os.environ.get("KAHNBAN_LIVE_MODEL", "haiku")

pytestmark = pytest.mark.skipif(not os.environ.get("KAHNBAN_LIVE"), reason="set KAHNBAN_LIVE=1 to run real agents")


def sh(*argv: str | Path, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True, check=check)


RESULTS: list[dict[str, object]] = []


@pytest.fixture(scope="module", autouse=True)
def report_medians():  # type: ignore[no-untyped-def]
    yield
    steps = [r["steps"] for r in RESULTS if isinstance(r["steps"], int)]
    done = sum(1 for r in RESULTS if r["done"])
    if steps:
        print(f"\nlive summary: {done}/{len(RESULTS)} done, median steps {statistics.median(steps)}")


@pytest.fixture(scope="module", autouse=True)
def preflight() -> None:
    """Fail once, clearly, when the agent CLI cannot answer: the earlier live run lost every worker to an expired login."""
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("the claude CLI is not on PATH")
    status = subprocess.run([claude, "auth", "status"], capture_output=True, text=True)
    if status.returncode != 0:
        pytest.skip(f"claude auth status failed: {status.stdout.strip() or status.stderr.strip()}")
    hello = subprocess.run([claude, "-p", "--model", MODEL, "Reply with the single word OK."], capture_output=True, text=True, timeout=180)
    if hello.returncode != 0 or "OK" not in hello.stdout:
        pytest.skip(f"one trivial call failed: {hello.stdout.strip()[:200]} {hello.stderr.strip()[:200]}")


def toy_repo(path: Path) -> Path:
    path.mkdir()
    sh("git", "init", "--initial-branch", "main", path, cwd=path.parent)
    sh("git", "config", "user.name", "Live Test", cwd=path)
    sh("git", "config", "user.email", "live@example.invalid", cwd=path)
    (path / "src").mkdir()
    (path / "tests").mkdir()
    (path / "src" / "slug.py").write_text("def slugify(text):\n    raise NotImplementedError\n", encoding="utf-8")
    (path / "README.md").write_text("A toy project.\n", encoding="utf-8")
    sh("git", "add", "-A", cwd=path)
    sh("git", "commit", "-m", "toy project", cwd=path)
    sh(sys.executable, "-m", "kahnban", "init", "--prefix", "LV", "--agentic", "--validation-command", f"{sys.executable} -m pytest -q", cwd=path)
    sh(sys.executable, "-m", "kahnban", "skills", "install", "--harness", "claude", cwd=path)  # the native agents behind --agent kahnban-<role>
    config = json.loads((path / "plans" / "board.config.json").read_text(encoding="utf-8"))
    config["workers"] = {"default": f"claude -p --model {MODEL} --agent kahnban-{{role}} --permission-mode acceptEdits"}
    config["worker_timeout_sec"] = 900
    (path / "plans" / "board.config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    sh("git", "add", "-A", cwd=path)
    sh("git", "commit", "-m", "worker command", cwd=path)
    sh(
        sys.executable, "-m", "kahnban", "new", "Add slugify",
        "--problem", "src/slug.py slugify(text) must lowercase, trim, and join words with single hyphens: 'Hello,  World!' -> 'hello-world'.",
        cwd=path,
    )
    return path


@pytest.mark.parametrize("run", range(RUNS))
def test_a_real_agent_takes_an_idea_to_done_or_escalates_it_with_a_reason(tmp_path: Path, run: int, capsys: pytest.CaptureFixture[str]) -> None:
    repo = toy_repo(tmp_path / f"toy{run}")
    config = core.load_config(repo)

    result = runner.run(config, max_steps=20, echo=lambda line: None)

    ticket = core.find_ticket(config, "LV-001")
    metrics = json.loads((repo / "plans" / "status.json").read_text(encoding="utf-8")).get("metrics", {}) if (repo / "plans" / "status.json").exists() else {}
    with capsys.disabled():
        print(f"\nlive run {run}: {ticket.column}, {len(result.steps)} steps, first-pass {metrics.get('first_pass_yield')}, guard refusals {result.guard_refusals}")
    done = ticket.column == config.done_column
    RESULTS.append({"done": done, "steps": len(result.steps)})
    escalated = bool(result.parked)
    assert done or escalated, f"the ticket is in {ticket.column} and nothing is waiting for a human: {result.stopped}"

