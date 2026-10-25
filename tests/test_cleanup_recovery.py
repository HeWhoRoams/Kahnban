"""A run killed between 'done' and 'cleanup' is finished by the next run, and lint says so meanwhile."""

from __future__ import annotations

import json
from pathlib import Path

from kahnban import core, dispatcher, linter, runner
from kahnban.cli import main
from conftest import git
from test_factory_gates import PY, factory_board, verified


def landed_but_not_cleaned(repo: Path) -> core.Config:
    """What a crash after the done commit leaves: the ticket is done, its worktree and branch remain."""
    config = factory_board(repo, workers={"default": f'{PY} -c "pass"'})  # no worker should be needed
    verified(config)
    core.approve(config, "TST-001", "qa")
    assert core.merge(config, "TST-001").passed
    core.done(config, "TST-001")
    return config


def test_a_done_ticket_that_kept_its_worktree_and_branch_is_offered_for_cleanup(repo: Path) -> None:
    config = landed_but_not_cleaned(repo)

    recommendation = dispatcher.resolve_next_action(config)

    assert recommendation.action == "finish_cleanup"
    assert recommendation.ticket_id == "TST-001"
    assert recommendation.command == "kahnban cleanup TST-001"
    assert "worktree" in recommendation.summary and "branch" in recommendation.summary


def test_lint_warns_about_the_leftovers_and_stops_once_they_are_gone(repo: Path) -> None:
    config = landed_but_not_cleaned(repo)

    warned = [f for f in linter.lint(config).warnings if f.rule == "BL20"]
    assert len(warned) == 1 and "kahnban cleanup TST-001" in warned[0].message
    assert not linter.lint(config).violations

    core.cleanup(config, "TST-001")

    assert not [f for f in linter.lint(config).warnings if f.rule == "BL20"]


def test_the_run_finishes_the_cleanup_and_then_goes_idle(repo: Path) -> None:
    config = landed_but_not_cleaned(repo)

    result = runner.run(config, max_steps=5, echo=lambda line: None)

    assert [step.action for step in result.steps] == ["finish_cleanup"]
    assert not (repo / ".worktrees" / "TST-001").exists()
    assert not core.branch_tip(config, "ticket/TST-001")
    assert dispatcher.resolve_next_action(config).action == "idle"


def test_a_done_ticket_whose_branch_never_landed_is_left_alone(repo: Path) -> None:
    config = factory_board(repo)
    tree = verified(config)
    git(repo, "mv", "plans/tickets/4-verifying/TST-001-fix.md", "plans/tickets/5-done/TST-001-fix.md")
    git(repo, "commit", "-m", "moved to done by hand, branch unmerged")

    assert core.cleanup_leftovers(config, core.find_ticket(config, "TST-001")) == []
    assert tree.exists()
    assert dispatcher.resolve_next_action(config).action != "finish_cleanup"


def test_next_names_the_cleanup(repo: Path, capsys) -> None:
    landed_but_not_cleaned(repo)

    assert main(["--project-root", str(repo), "next", "--json"]) == 0

    assert json.loads(capsys.readouterr().out)["action"] == "finish_cleanup"


def test_idle_names_a_live_lease_instead_of_saying_nothing_is_waiting(repo: Path) -> None:
    from test_factory_gates import claimed, strict_board

    config = strict_board(repo)
    claimed(config)

    recommendation = dispatcher.resolve_next_action(config)

    assert recommendation.action == "idle"
    assert "live lease" in recommendation.summary and "TST-001" in recommendation.summary
