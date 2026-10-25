"""Hook dispatch by file type, hook failures, the pinned-file lock and approval signing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kahnban import hooks, trust


def hook_file(root: Path, name: str, text: str = "") -> Path:
    path = root / ".kahnban" / "hooks" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- hooks ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected_start", "shell"),
    [
        ("post-ready.ps1", ["powershell", "-NoProfile"], False),
        ("post-ready.sh", ["sh"], False),
        ("post-ready.bat", None, True),
        ("post-ready.cmd", None, True),
        ("post-ready", None, False),
    ],
)
def test_each_hook_file_type_is_started_the_way_its_shell_expects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, expected_start: list[str] | None, shell: bool
) -> None:
    script = hook_file(tmp_path, name)
    seen: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        seen.update(cmd=cmd, shell=kwargs["shell"], input=kwargs["input"])
        return subprocess.CompletedProcess(cmd, 0, "out", "")

    monkeypatch.setattr(hooks.subprocess, "run", fake_run)

    result = hooks.run_hook(tmp_path, "post-ready", "T-1", column="2-ready", payload={"gate": "x"})

    assert result.executed and result.exit_code == 0 and result.stdout == "out"
    assert seen["shell"] is shell
    assert seen["cmd"][-1] == str(script)
    if expected_start:
        assert seen["cmd"][: len(expected_start)] == expected_start
    event = json.loads(str(seen["input"]))
    assert (event["event"], event["ticket"], event["column"], event["gate"]) == ("post-ready", "T-1", "2-ready", "x")


def test_a_hook_that_overruns_its_timeout_is_reported_not_raised(tmp_path: Path) -> None:
    import sys

    hook_file(tmp_path, "post-ready.py", "import time\ntime.sleep(30)\n")

    result = hooks.run_hook(tmp_path, "post-ready", "T-1", timeout=0.5)

    assert result.executed and result.exit_code == 124
    assert "timed out after 0.5s" in result.stderr
    assert sys.executable  # the hook ran under this interpreter


def test_a_hook_that_cannot_be_started_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook_file(tmp_path, "post-ready.sh")

    def broken(cmd, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("no such shell")

    monkeypatch.setattr(hooks.subprocess, "run", broken)

    result = hooks.run_hook(tmp_path, "post-ready", "T-1")

    assert result.exit_code == 1
    assert "failed to execute: no such shell" in result.messages[0]


def test_a_board_that_cannot_be_read_is_not_strict(tmp_path: Path) -> None:
    assert hooks._strict(tmp_path) is False


# --- the pinned-file lock --------------------------------------------------------------


def installed_skill(root: Path) -> Path:
    skill = root / ".agents" / "skills" / "tdd" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# tdd\n", encoding="utf-8")
    return skill


def test_nothing_to_pin_writes_no_lock(tmp_path: Path) -> None:
    assert trust.write_lock(tmp_path) == 0
    assert not (tmp_path / trust.LOCK).exists()
    assert trust.drift(tmp_path) == {}


def test_drift_names_changed_unpinned_and_gone_files(tmp_path: Path) -> None:
    skill = installed_skill(tmp_path)
    other = skill.parent.parent / "extra" / "SKILL.md"
    other.parent.mkdir()
    other.write_text("# extra\n", encoding="utf-8")
    assert trust.write_lock(tmp_path) == 2

    skill.write_text("# tdd, edited\n", encoding="utf-8")
    other.unlink()
    (skill.parent.parent / "new").mkdir()
    (skill.parent.parent / "new" / "SKILL.md").write_text("# new\n", encoding="utf-8")

    drift = trust.drift(tmp_path)

    assert drift == {
        ".agents/skills/extra/SKILL.md": "gone",
        ".agents/skills/new/SKILL.md": "unpinned",
        ".agents/skills/tdd/SKILL.md": "changed",
    }
    problems = " | ".join(trust.lock_problems(tmp_path))
    assert "changed since it was pinned" in problems and "is not pinned" in problems and "is gone" in problems


def test_an_unreadable_lock_is_reported_and_blocks_nothing_else(tmp_path: Path) -> None:
    installed_skill(tmp_path)
    (tmp_path / trust.LOCK).write_text("{not json", encoding="utf-8")

    assert trust.drift(tmp_path) == {trust.LOCK.as_posix(): "unreadable"}
    assert "unreadable; re-run 'kahnban skills lock'" in trust.lock_problems(tmp_path)[0]
    assert trust.verify_file(tmp_path, tmp_path / ".agents" / "skills" / "tdd" / "SKILL.md") == ""


def test_verify_file_judges_only_locked_directories(tmp_path: Path) -> None:
    skill = installed_skill(tmp_path)
    trust.write_lock(tmp_path)
    outside = tmp_path / "notes.md"
    outside.write_text("x", encoding="utf-8")
    unpinned = skill.parent.parent / "later" / "SKILL.md"
    unpinned.parent.mkdir()
    unpinned.write_text("later", encoding="utf-8")

    assert trust.verify_file(tmp_path, skill) == ""
    assert trust.verify_file(tmp_path, outside) == ""
    assert trust.verify_file(tmp_path.parent, skill) == ""  # not under that root
    assert "is not pinned" in trust.verify_file(tmp_path, unpinned)
    skill.write_text("changed", encoding="utf-8")
    assert "changed since it was pinned" in trust.verify_file(tmp_path, skill)


# --- signing ------------------------------------------------------------------------------


def test_key_dir_follows_the_override_then_the_platform_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(trust.KEY_DIR_ENV, str(tmp_path / "keys"))
    assert trust.key_dir() == tmp_path / "keys"

    monkeypatch.delenv(trust.KEY_DIR_ENV)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    # Each platform reads its own variable; CI covers the other one.
    base = tmp_path / ("roaming" if trust.os.name == "nt" else "state")
    assert trust.key_dir() == base / "kahnban" / "keys"


def test_a_signing_key_from_the_environment_beats_the_key_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    approval = trust.Approval("T-1", "abc123", "Reviewer")
    from_file = trust.sign(tmp_path, approval)

    monkeypatch.setenv(trust.KEY_ENV, "a-key-from-the-environment")

    assert trust.sign(tmp_path, approval) != from_file
    assert trust.sign(tmp_path, approval) == trust.sign(tmp_path, trust.Approval("T-1", "abc123", "  reviewer "))


def test_an_approval_is_unsigned_forged_or_good(tmp_path: Path) -> None:
    good = trust.Approval("T-1", "abc123", "qa")
    signed = trust.Approval("T-1", "abc123", "qa", trust.sign(tmp_path, good))

    assert "unsigned" in trust.signature_problem(tmp_path, good)
    assert trust.signature_problem(tmp_path, signed) == ""
    forged = trust.Approval("T-1", "def456", "qa", signed.signature)
    assert "forged" in trust.signature_problem(tmp_path, forged)
