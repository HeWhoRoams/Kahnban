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
