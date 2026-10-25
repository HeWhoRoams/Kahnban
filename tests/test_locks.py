"""A lock left by a process that is gone is broken at once; a live one is respected."""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from kahnban import core, fsutil


def dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def stamp(pid: int, host: str | None = None) -> str:
    return f"pid={pid} host={host or socket.gethostname()} at=2026-01-01T00:00:00\n"


def test_process_alive_tells_a_running_process_from_a_finished_one() -> None:
    import os

    assert fsutil.process_alive(os.getpid())
    assert not fsutil.process_alive(dead_pid())
    assert not fsutil.process_alive(0)


def test_holder_is_dead_only_for_this_host_and_a_named_pid() -> None:
    gone = dead_pid()

    assert fsutil.holder_is_dead(stamp(gone))
    assert not fsutil.holder_is_dead(stamp(gone, host="another-machine"))
    assert not fsutil.holder_is_dead("holder=someone at=test")
    assert not fsutil.holder_is_dead("")


def test_board_lock_is_taken_over_at_once_from_a_dead_process(board: Path) -> None:
    config = core.load_config(board)
    lock_path = config.board_path / core.LOCK_NAME
    lock_path.write_text(stamp(dead_pid()), encoding="utf-8")

    with core.board_lock(config, max_retries=2) as warnings:
        assert any("gone" in warning for warning in warnings)
        assert f"pid={__import__('os').getpid()}" in lock_path.read_text(encoding="utf-8")
    assert not lock_path.exists()


def test_board_lock_waits_for_a_live_holder(board: Path) -> None:
    import os

    config = core.load_config(board)
    lock_path = config.board_path / core.LOCK_NAME
    lock_path.write_text(stamp(os.getpid()), encoding="utf-8")

    with pytest.raises(core.LockError, match="locked by another"):
        with core.board_lock(config, max_retries=2, retry_interval=0.01):
            pass
    assert lock_path.exists()


def test_board_lock_does_not_judge_a_lock_from_another_host(board: Path) -> None:
    config = core.load_config(board)
    lock_path = config.board_path / core.LOCK_NAME
    lock_path.write_text(stamp(dead_pid(), host="another-machine"), encoding="utf-8")

    with pytest.raises(core.LockError):
        with core.board_lock(config, max_retries=2, retry_interval=0.01):
            pass


def test_exclusive_breaks_a_dead_holders_lock_and_respects_a_live_one(tmp_path: Path) -> None:
    import os

    lock = tmp_path / "x.lock"
    lock.write_text(stamp(dead_pid()), encoding="utf-8")
    with fsutil.exclusive(lock, wait=1):
        assert f"pid={os.getpid()}" in lock.read_text(encoding="utf-8")

    lock.write_text(stamp(os.getpid()), encoding="utf-8")
    with pytest.raises(TimeoutError):
        with fsutil.exclusive(lock, wait=0.2):
            pass


def test_only_one_of_many_waiters_breaks_the_same_stale_lock(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    text = stamp(dead_pid())
    lock.write_text(text, encoding="utf-8")
    winners: list[bool] = []
    gate = threading.Barrier(8)

    def waiter() -> None:
        gate.wait()
        winners.append(fsutil.break_lock(lock, text))

    threads = [threading.Thread(target=waiter) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert winners.count(True) == 1
    assert not lock.exists()
    assert not list(tmp_path.glob("x.lock.breaking"))


def test_a_lock_made_after_it_was_judged_stale_is_put_back(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    lock.write_text(stamp(1234), encoding="utf-8")  # a different holder than the one that was judged

    assert not fsutil.break_lock(lock, stamp(dead_pid()))
    assert lock.read_text(encoding="utf-8") == stamp(1234)
