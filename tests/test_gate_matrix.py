"""Every gate, one dishonest input each, in one table. A gate that lets its row through turns the suite red.

The simulation's cheat scenarios (S4a-S4f) and the factory-gate tests cover deeper cases; this is the
index: if a gate has no row here, nobody has written down what it is supposed to refuse.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kahnban import core
from conftest import git, write_ticket
from test_factory_gates import CHECK, CRITERION, commit_work, claimed, factory_board, strict_board, verified


def refining(config: core.Config, **overrides: object) -> None:
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-001",
        "fix",
        **{"acceptance": (CRITERION,), "blast_radius": ("src/app.py", "tests/check_app.py"), "validation": CHECK, **overrides},  # type: ignore[arg-type]
    )
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", "refine")


# gate name -> a setup that returns a callable making the dishonest request
def ready_without_a_checkbox(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config, acceptance=())
    return lambda: core.ready(config, "TST-001")


def ready_with_no_blast_radius(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config, blast_radius=())
    return lambda: core.ready(config, "TST-001")


def ready_with_a_dependency_not_done(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config, depends_on="[TST-009]")
    write_ticket(config.board_path, "2-ready", "TST-009", "other")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "dependency")
    return lambda: core.ready(config, "TST-001")


def claim_a_ticket_that_is_not_ready(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config)
    return lambda: core.claim(config, "TST-001", "coder", create_worktree=False)


def claim_an_overlapping_blast_radius(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    claimed(config)
    write_ticket(config.board_path, "2-ready", "TST-002", "twin", blast_radius=("src/app.py", "tests/check_app.py"))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "twin")
    return lambda: core.claim(config, "TST-002", "other", create_worktree=False)


def claim_forced_without_a_reason(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config)
    return lambda: core.claim(config, "TST-001", "coder", create_worktree=False, force=True)


def claim_an_overlap_forced_without_a_reason(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    claimed(config)
    write_ticket(config.board_path, "2-ready", "TST-002", "twin", blast_radius=("src/app.py", "tests/check_app.py"))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "twin")
    return lambda: core.claim(config, "TST-002", "other", create_worktree=False, force_overlap=True)


def verify_with_uncommitted_work(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    tree = claimed(config)
    (tree / "src" / "app.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    return lambda: core.verify(config, "TST-001")


def verify_a_ticket_that_changes_no_source(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    tree = claimed(config)
    commit_work(tree, {"tests/check_app.py": "print('ok')\n"})
    return lambda: core.verify(config, "TST-001")


def approve_as_the_owner(repo: Path) -> Callable[[], object]:
    config = factory_board(repo)
    verified(config)
    return lambda: core.approve(config, "TST-001", "coder")


def approve_a_ticket_that_is_not_verified(repo: Path) -> Callable[[], object]:
    config = factory_board(repo)
    claimed(config)
    return lambda: core.approve(config, "TST-001", "qa")


def merge_without_an_approval(repo: Path) -> Callable[[], object]:
    config = factory_board(repo)
    verified(config)
    return lambda: core.merge(config, "TST-001")


def done_without_a_merge(repo: Path) -> Callable[[], object]:
    config = factory_board(repo)
    verified(config)
    core.approve(config, "TST-001", "qa")
    return lambda: core.done(config, "TST-001")


def reject_without_saying_why(repo: Path) -> Callable[[], object]:
    config = factory_board(repo)
    verified(config)
    return lambda: core.reject(config, "TST-001", "qa", "   ")


def move_without_a_reason(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config)
    return lambda: core.move(config, "TST-001", "2-ready", reason="")


def cleanup_of_unfinished_work(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    claimed(config)
    return lambda: core.cleanup(config, "TST-001")


def confirm_when_nothing_waits(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    claimed(config)
    return lambda: core.confirm(config, "TST-001")


def escalate_without_a_question(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config)
    return lambda: core.escalate(config, "TST-001", "")


def unblock_without_an_answer(repo: Path) -> Callable[[], object]:
    config = strict_board(repo)
    refining(config)
    return lambda: core.unblock(config, "TST-001", "")


ROWS = [
    ready_without_a_checkbox,
    ready_with_no_blast_radius,
    ready_with_a_dependency_not_done,
    claim_a_ticket_that_is_not_ready,
    claim_an_overlapping_blast_radius,
    claim_forced_without_a_reason,
    claim_an_overlap_forced_without_a_reason,
    verify_with_uncommitted_work,
    verify_a_ticket_that_changes_no_source,
    approve_as_the_owner,
    approve_a_ticket_that_is_not_verified,
    merge_without_an_approval,
    done_without_a_merge,
    reject_without_saying_why,
    move_without_a_reason,
    cleanup_of_unfinished_work,
    confirm_when_nothing_waits,
    escalate_without_a_question,
    unblock_without_an_answer,
]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.__name__)
def test_the_gate_refuses(repo: Path, row: Callable[[Path], Callable[[], object]]) -> None:
    attempt = row(repo)

    with pytest.raises(core.KahnbanError):
        attempt()


def test_the_table_names_every_gate() -> None:
    gates = {row.__name__.split("_")[0] for row in ROWS}

    assert gates >= {"ready", "claim", "verify", "approve", "merge", "done", "reject", "move", "cleanup", "confirm", "escalate", "unblock"}
