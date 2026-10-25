"""The crash-injection hook the simulation uses: inert unless KAHNBAN_FAULT is set."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")
SCRIPT = (
    "import sys; from pathlib import Path; from kahnban import gitops\n"
    "root = Path(sys.argv[1])\n"
    "for n in (1, 2, 3):\n"
    "    (root / f'f{n}.txt').write_text(str(n))\n"
    "    gitops.add(root, [f'f{n}.txt'])\n"
    "    gitops.commit(root, f'commit {n}')\n"
)


def run(repo: Path, fault: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": REPO_SRC}
    if fault:
        env["KAHNBAN_FAULT"] = fault
    return subprocess.run([sys.executable, "-c", SCRIPT, str(repo)], env=env, capture_output=True, text=True)


def commits(repo: Path) -> int:
    return int(git(repo, "rev-list", "--count", "HEAD").stdout.strip())


def test_without_the_variable_every_commit_lands(repo: Path) -> None:
    before = commits(repo)

    assert run(repo, "").returncode == 0
    assert commits(repo) == before + 3


@pytest.mark.parametrize(
    ("fault", "landed"),
    [("after:2", 2), ("before:2", 1), ("after:1", 1), ("before:3", 2)],
)
def test_the_process_dies_at_the_named_commit(repo: Path, fault: str, landed: int) -> None:
    before = commits(repo)

    result = run(repo, fault)

    assert result.returncode == 137
    assert commits(repo) == before + landed


def test_a_crash_before_the_commit_leaves_the_work_staged(repo: Path) -> None:
    run(repo, "before:2")

    assert git(repo, "diff", "--cached", "--name-only").stdout.split() == ["f2.txt"]
