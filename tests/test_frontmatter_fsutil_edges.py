"""Malformed frontmatter is refused with a line number; file helpers survive the failures they meet."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from kahnban import frontmatter, fsutil


def doc(*lines: str) -> str:
    return "\n".join(["---", *lines, "---", "body", ""])


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (['title: "bad \\q escape"'], "invalid quoted value"),
        (["title: \"123\"", "tags: [a,,b]"], "empty list item"),
        (["tags: [a, b"], "unterminated inline list"),
        (["tags: ['a, b]"], "unterminated"),
        (["tags: [a, b,]"], "empty list item"),
        (["  - orphan"], "no parent key"),
        (["title: x", "- stray"], "no parent key|follows a scalar"),
        (["just text"], "expected 'key: value'"),
        ([": value"], "key cannot be empty"),
        (["a: 1", "a: 2"], "duplicate key"),
        (["parent:", "  child: nested"], "nested mappings"),
    ],
)
def test_malformed_frontmatter_is_refused_with_a_reason(lines: list[str], message: str) -> None:
    with pytest.raises(frontmatter.FrontmatterError, match=message):
        frontmatter.parse(doc(*lines))


def test_single_quoted_values_unescape_doubled_quotes() -> None:
    fields, _ = frontmatter.parse(doc("title: 'it''s fine'"))

    assert fields["title"] == "it's fine"


def test_a_value_that_is_not_text_cannot_be_written() -> None:
    with pytest.raises(TypeError, match="unsupported value for 'n'"):
        frontmatter.serialize({"n": 3}, "body")  # type: ignore[dict-item]


def test_mutate_refuses_a_key_the_ticket_does_not_have() -> None:
    with pytest.raises(frontmatter.FrontmatterError, match="cannot update missing keys: ghost"):
        frontmatter.mutate(doc("id: T-1"), {"ghost": "x"})


def test_a_log_entry_needs_a_log_heading() -> None:
    with pytest.raises(frontmatter.FrontmatterError, match="missing the '## Log' heading"):
        frontmatter.append_log(doc("id: T-1"), "something happened")


# --- file helpers ---------------------------------------------------------------------


def test_an_atomic_write_that_fails_leaves_neither_a_temp_file_nor_a_half_written_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "ticket.md"
    target.write_text("original\n", encoding="utf-8")

    def fail(self: Path, destination: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail)

    with pytest.raises(OSError, match="disk full"):
        fsutil.write_text_atomic(target, "new\n")

    assert target.read_text(encoding="utf-8") == "original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["ticket.md"]


def test_unlink_retry_waits_out_a_reader_and_gives_up_quietly_on_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "x.lock"
    lock.write_text("held", encoding="utf-8")
    real = Path.unlink
    refusals = iter([PermissionError(13, "in use"), PermissionError(13, "in use")])

    def flaky(self: Path, missing_ok: bool = False) -> None:
        error = next(refusals, None)
        if error and self == lock:
            raise error
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky)
    monkeypatch.setattr(fsutil.time, "sleep", lambda seconds: None)

    fsutil.unlink_retry(lock)
    fsutil.unlink_retry(lock)  # already gone

    assert not lock.exists()


def test_unlink_retry_finally_raises_when_the_file_never_frees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def always(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "in use")

    monkeypatch.setattr(Path, "unlink", always)
    monkeypatch.setattr(fsutil.time, "sleep", lambda seconds: None)

    with pytest.raises(PermissionError):
        fsutil.unlink_retry(tmp_path / "x.lock", tries=3)


def test_a_break_guard_left_by_a_dead_breaker_is_cleared_after_ten_seconds(tmp_path: Path) -> None:
    import os

    lock = tmp_path / "x.lock"
    lock.write_text("pid=1 host=h at=t\n", encoding="utf-8")
    guard = tmp_path / "x.lock.breaking"
    guard.write_text("", encoding="utf-8")

    assert not fsutil.break_lock(lock, "pid=1 host=h at=t\n")  # a live breaker holds the guard
    assert guard.exists()

    old = time.time() - 60
    os.utime(guard, (old, old))
    assert not fsutil.break_lock(lock, "pid=1 host=h at=t\n")  # this call only clears the dead guard
    assert not guard.exists()
    assert fsutil.break_lock(lock, "pid=1 host=h at=t\n")
    assert not lock.exists()


def test_breaking_a_lock_that_is_already_gone_reports_no_win(tmp_path: Path) -> None:
    assert not fsutil.break_lock(tmp_path / "x.lock", "anything")
