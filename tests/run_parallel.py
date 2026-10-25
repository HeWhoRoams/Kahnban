"""Run the tests in parallel worker processes: ``python tests/run_parallel.py [-j N] [pytest args]``.

The suite drives real git repositories, about a second per test, so it is slow in one process and
fine in several: every test works in its own temporary directory. No plugin needed. The collected
tests are dealt out to the workers in turn.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def collect(pytest_args: list[str]) -> list[str]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider", *pytest_args, str(HERE)],
        cwd=HERE.parent,
        capture_output=True,
        text=True,
    )
    return [line for line in done.stdout.splitlines() if "::" in line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--jobs", type=int, default=min(8, os.cpu_count() or 2))
    args, pytest_args = parser.parse_known_args()
    started = time.monotonic()
    ids = collect(pytest_args)
    # Interleaved, not chunked: neighbouring tests in a file tend to cost alike, so this spreads the heavy ones.
    groups = [ids[i :: max(1, args.jobs)] for i in range(max(1, args.jobs))]
    groups = [group for group in groups if group]
    scratch = Path(tempfile.mkdtemp(prefix="kahnban-parallel-"))

    def run(index: int) -> tuple[int, str]:
        argsfile = scratch / f"worker{index}.txt"
        argsfile.write_text(chr(10).join(groups[index]), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *pytest_args, f"@{argsfile}"],
            cwd=HERE.parent,
            capture_output=True,
            text=True,
        )
        return done.returncode, done.stdout + done.stderr

    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        results = list(pool.map(run, range(len(groups))))
    worst = 0
    for code, output in results:
        summary = [line for line in output.splitlines() if line.startswith(("FAILED", "ERROR"))]
        if code:
            print(chr(10).join(summary) or output[-2000:])
        worst = max(worst, code)
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"{len(ids)} tests, {len(groups)} workers, {time.monotonic() - started:.0f}s, {'all passed' if not worst else 'FAILURES'}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
