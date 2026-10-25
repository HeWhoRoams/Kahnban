"""Line coverage of ``src/kahnban`` with child processes counted.

    python tests/run_coverage.py [--fail-under N] [pytest arguments ...]

Runs pytest under coverage, with ``tests/_cov/sitecustomize.py`` on PYTHONPATH so the processes the
tests start report as well, then combines the data files and prints the report.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-under", type=float, default=0)
    args, pytest_args = parser.parse_known_args()
    env = {
        **os.environ,
        "COVERAGE_PROCESS_START": str(ROOT / "pyproject.toml"),
        "COVERAGE_FILE": str(ROOT / ".coverage"),  # absolute: a worker runs in a ticket worktree, which must stay clean
        "PYTHONPATH": str(ROOT / "tests" / "_cov") + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    for stale in ROOT.glob(".coverage*"):
        stale.unlink()
    tests = subprocess.run([sys.executable, "-m", "coverage", "run", "-m", "pytest", "-q", *pytest_args], cwd=ROOT, env=env)
    subprocess.run([sys.executable, "-m", "coverage", "combine", "--quiet"], cwd=ROOT, env=env)
    report = subprocess.run(
        [sys.executable, "-m", "coverage", "report", "--skip-covered", f"--fail-under={args.fail_under}"],
        cwd=ROOT,
        env=env,
    )
    return tests.returncode or report.returncode


if __name__ == "__main__":
    sys.exit(main())
