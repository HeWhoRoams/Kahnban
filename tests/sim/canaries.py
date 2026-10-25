"""Deliberate engine breakages. A simulation that cannot go red proves nothing.

Each canary patches a copy of ``src`` and runs the scenarios that should notice. It is caught when a
scenario stops holding its rules, or when the scorecard is worse than the committed baseline.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .compare import compare, normalize

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
LAUNCHER = HERE.parent / "run_sim.py"
BASELINE = HERE / "baseline" / "scorecard.json"


@dataclass(frozen=True)
class Canary:
    name: str
    file: str
    old: str
    new: str
    scenarios: tuple[str, ...]
    env: tuple[tuple[str, str], ...] = ()  # extra environment, for example one crash point to replay


CANARIES = [
    Canary(
        "approve skips the owner check",
        "core.py",
        "        if reviewer.lower() == owner.lower():\n            raise GateError(",
        "        if False:\n            raise GateError(",
        ("S4f",),
    ),
    Canary(
        "verify skips the blast-radius check",
        "core.py",
        "        messages.extend(notes)\n        if offenders:",
        "        messages.extend(notes)\n        if False:",
        ("S4a",),
    ),
    Canary(
        "require_proof stops asking for source changes",
        "core.py",
        '    if not source:\n        raise GateError(\n            f"require_proof:',
        '    if False:\n        raise GateError(\n            f"require_proof:',
        ("S4b",),
    ),
    Canary(
        "merge skips the combined regression run",
        "core.py",
        'stages.append(("INTEGRATION: FEATURE TESTS", output))\n            if exit_code == 0 and reg_cmd and reg_cmd != feat_cmd:',
        'stages.append(("INTEGRATION: FEATURE TESTS", output))\n            if False:',
        ("S5",),
    ),
    Canary(
        "the guard allows everything",
        "guard.py",
        '    """The reason to block this tool call, or None to allow it."""\n',
        '    """The reason to block this tool call, or None to allow it."""\n    return None\n',
        ("S4d", "S4e"),
    ),
    Canary(
        "every validation command reports success",
        "core.py",
        "    if len(commands) == 1:\n        return run_command(config, commands[0], cwd)",
        "    if len(commands) == 1:\n        return 0, run_command(config, commands[0], cwd)[1]",
        ("S3",),
    ),
    Canary(
        "a lock held by a dead process is never taken over",
        "fsutil.py",
        "    pid = re.search(",
        "    return False\n    pid = re.search(",
        ("S8",),
        env=(("KAHNBAN_SIM_FAULT", "before:1"),),
    ),
    Canary(
        "a done ticket's leftovers are never offered for cleanup",
        "dispatcher.py",
        "            leftovers = core.cleanup_leftovers(config, done)",
        "            leftovers = []",
        ("S8",),
        env=(("KAHNBAN_SIM_FAULT", "after:4"),),
    ),
]


def run_canary(canary: Canary) -> tuple[bool, str]:
    scratch = Path(tempfile.mkdtemp(prefix="sim-canary-"))
    try:
        patched = scratch / "src"
        shutil.copytree(SRC, patched, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        target = patched / "kahnban" / canary.file
        text = target.read_text(encoding="utf-8")
        if text.count(canary.old) != 1:
            return False, f"the patch point is not in {canary.file} exactly once; update the canary"
        target.write_text(text.replace(canary.old, canary.new), encoding="utf-8")
        out = scratch / "scorecard.json"
        env = {**os.environ, "KAHNBAN_SIM_SRC": str(patched), **dict(canary.env)}
        subprocess.run(
            [sys.executable, str(LAUNCHER), "run", *canary.scenarios, "--out", str(out)],
            env=env,
            capture_output=True,
            text=True,
        )
        if not out.exists():
            return True, "the simulation itself failed to complete"
        card = json.loads(out.read_text(encoding="utf-8"))
        failing = [ident for ident, item in card["scenarios"].items() if not item["ok"]]
        if failing:
            return True, f"{', '.join(failing)} no longer hold every rule"
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        baseline["scenarios"] = {k: v for k, v in baseline["scenarios"].items() if k in canary.scenarios}
        result = compare(normalize(baseline), normalize(card))
        if not result.clean:
            return True, "; ".join([*result.broken, *result.worse])[:200]
        return False, "every scenario still passes and the scorecard did not move"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(names: list[str]) -> int:
    chosen = [c for c in CANARIES if not names or any(n.lower() in c.name.lower() for n in names)]
    missed = 0
    for canary in chosen:
        caught, why = run_canary(canary)
        missed += not caught
        print(f"[{'CAUGHT' if caught else 'MISSED'}] {canary.name} -> {why}")
    print(f"{len(chosen) - missed}/{len(chosen)} canaries caught")
    return 1 if missed else 0
