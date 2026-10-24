"""Tests for lifecycle hooks (.kahnban/hooks/) and state transition triggers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kahnban import core, hooks, scaffold


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", str(r)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "HookTest"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "hook@test.com"], check=True)
    scaffold.init_board(r, prefix="HOOK")
    return r


def test_hook_execution_python(repo: Path) -> None:
    hooks_dir = repo / ".kahnban" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Python hook
    hook_script = hooks_dir / "post-ready.py"
    hook_script.write_text(
        "import os, pathlib\n"
        "p = pathlib.Path('hook_ran.txt')\n"
        "p.write_text(f\"{os.environ.get('KAHNBAN_EVENT')}:{os.environ.get('KAHNBAN_TICKET')}\", encoding='utf-8')\n",
        encoding="utf-8"
    )

    res = hooks.run_hook(repo, "post-ready", "HOOK-001", column="2-ready")
    assert res.executed is True
    assert res.exit_code == 0
    assert (repo / "hook_ran.txt").exists()
    assert (repo / "hook_ran.txt").read_text(encoding="utf-8") == "post-ready:HOOK-001"


def test_hook_missing_is_non_blocking(repo: Path) -> None:
    res = hooks.run_hook(repo, "post-nonexistent", "HOOK-002")
    assert res.executed is False
    assert "no hook found" in res.messages[0]


def test_hook_failure_is_captured(repo: Path) -> None:
    hooks_dir = repo / ".kahnban" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_script = hooks_dir / "post-verify.py"
    hook_script.write_text("import sys; sys.stderr.write('Fatal hook error\\n'); sys.exit(2)", encoding="utf-8")

    res = hooks.run_hook(repo, "post-verify", "HOOK-003")
    assert res.executed is True
    assert res.exit_code == 2
    assert "Fatal hook error" in res.stderr
