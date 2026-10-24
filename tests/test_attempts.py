"""Retry counts: safe under concurrent runners, restarted by progress, and never silently lost."""

from __future__ import annotations

import threading
from pathlib import Path

from kahnban import attempts, core
from conftest import scaffold_board


def board_config(repo: Path) -> core.Config:
    scaffold_board(repo, {})
    return core.load_config(repo)


def test_concurrent_runners_do_not_lose_counts(repo: Path) -> None:
    config = board_config(repo)

    def bump_thirty_times() -> None:
        for _ in range(30):
            attempts.bump(config, "claim_and_implement", "TST-001", "2-ready||")

    threads = [threading.Thread(target=bump_thirty_times) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert attempts.load(config)["claim_and_implement|TST-001"].count == 90


def test_progress_restarts_the_count_and_a_stuck_ticket_keeps_it(repo: Path) -> None:
    config = board_config(repo)

    for _ in range(3):
        stuck = attempts.bump(config, "revise_implementation", "TST-001", "3-in-progress|aaa|bbb")
    assert stuck.count == 3

    moved = attempts.bump(config, "revise_implementation", "TST-001", "3-in-progress|ccc|bbb")
    assert moved.count == 1  # new commits: this is a rework cycle, not a stuck ticket


def test_a_corrupt_counts_file_is_kept_not_overwritten(repo: Path, capsys) -> None:
    config = board_config(repo)
    attempts.bump(config, "claim_and_implement", "TST-001", "x")
    path = config.board_path / attempts.ARTIFACT_DIR / "attempts.json"
    path.write_text("{not json", encoding="utf-8")

    assert attempts.load(config) == {}
    assert (path.parent / "attempts.json.corrupt").read_text(encoding="utf-8") == "{not json"
    assert "unreadable" in capsys.readouterr().err


def test_clear_forgets_one_ticket_only(repo: Path) -> None:
    config = board_config(repo)
    attempts.bump(config, "claim_and_implement", "TST-001", "x")
    attempts.bump(config, "claim_and_implement", "TST-002", "x")

    attempts.clear(config, "TST-001")

    assert list(attempts.load(config)) == ["claim_and_implement|TST-002"]


def test_a_lock_left_by_a_dead_process_is_broken_but_a_fresh_one_is_not(tmp_path: Path) -> None:
    import os
    import time

    import pytest

    from kahnban.fsutil import exclusive

    lock = tmp_path / "x.lock"
    lock.write_text("", encoding="utf-8")
    with pytest.raises(TimeoutError):
        with exclusive(lock, wait=0.2, stale=30):  # a fresh lock is respected
            pass

    old = time.time() - 120
    os.utime(lock, (old, old))
    with exclusive(lock, wait=1, stale=30):  # an old one is taken over
        assert lock.exists()
    assert not lock.exists()


def test_windows_style_permission_errors_while_a_lock_is_deleted_just_mean_retry(tmp_path: Path, monkeypatch) -> None:
    import os

    from kahnban.fsutil import exclusive

    real_open = os.open
    failures = iter([PermissionError(13, "pending delete"), PermissionError(13, "pending delete")])

    def flaky_open(path, flags, *args):  # type: ignore[no-untyped-def]
        error = next(failures, None)
        if error:
            raise error
        return real_open(path, flags, *args)

    monkeypatch.setattr(os, "open", flaky_open)
    with exclusive(tmp_path / "x.lock", wait=2):
        pass


def test_stop_nudges_are_not_lost_to_concurrent_workers(repo: Path) -> None:
    from kahnban import exit_checks

    board_config(repo)
    env = {"KAHNBAN_PROJECT_ROOT": str(repo), "KAHNBAN_TICKET": "TST-001"}
    spent: list[bool] = []

    def spend() -> None:
        for _ in range(5):
            spent.append(exit_checks.spend_nudge("coder", env))

    threads = [threading.Thread(target=spend) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert spent.count(True) == 2  # max_stop_nudges, however the workers interleave
    assert len(spent) == 20
