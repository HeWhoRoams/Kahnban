"""The runner's refusals and fallbacks: the paths a scripted worker run does not reach."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from kahnban import core, dispatcher, frontmatter, roles, runner
from conftest import git, write_ticket
from test_factory_gates import PY, claimed, factory_board, strict_board, verified


def quiet(line: str) -> None:
    return None


def rec(action: str, ticket: str | None = "TST-001") -> dispatcher.DispatchRecommendation:
    return dispatcher.DispatchRecommendation(action=action, assigned_role="none", ticket_id=ticket)


def test_parked_lists_blocked_tickets_and_skips_done_and_unreadable_ones(repo: Path) -> None:
    config = strict_board(repo)
    write_ticket(config.board_path, "2-ready", "TST-001", "blocked", blocked_on="human: which currency?")
    write_ticket(config.board_path, "5-done", "TST-002", "done", blocked_on="stale")
    broken = config.board_path / "2-ready" / "TST-003-broken.md"
    broken.write_text("not frontmatter at all\n", encoding="utf-8")

    assert runner._parked(config) == ["TST-001 (human: which currency?)"]


def test_progress_of_a_ticket_that_does_not_exist_is_empty(repo: Path) -> None:
    assert runner._progress(strict_board(repo), "TST-404") == ""


def test_an_action_the_runner_has_no_handler_for_stops_the_run(repo: Path) -> None:
    config = strict_board(repo)

    with pytest.raises(runner.RunStop, match="no handler for action 'teleport'"):
        runner._step(config, rec("teleport"), repo / "log.txt")


def test_a_role_with_no_worker_command_stops_the_run(repo: Path) -> None:
    config = strict_board(repo)

    with pytest.raises(runner.RunStop, match="no worker command for role 'coder'"):
        runner._work(config, roles.CODER, rec("claim_and_implement", None), repo, repo / "log.txt")


def test_the_curator_gets_one_turn_and_a_refusal_there_is_reported_not_fatal(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = strict_board(repo, workers={"default": f'{PY} -c "pass"'})
    plan = iter([rec("harvest_learnings", None), rec("idle", None)])
    monkeypatch.setattr(dispatcher, "resolve_next_action", lambda *a, **k: next(plan))
    monkeypatch.setattr(runner, "_work", lambda *a, **k: (0, ""))

    result = runner.run(config, max_steps=5, echo=quiet)

    assert [s.action for s in result.steps] == ["harvest_learnings"]
    assert result.steps[0].outcome == "curator turn finished (exit 0)"

    plan = iter([rec("harvest_learnings", None), rec("idle", None)])

    def refuse(*args: object, **kwargs: object) -> None:
        raise core.GateError("curator may not")

    monkeypatch.setattr(runner, "_work", refuse)
    result = runner.run(config, max_steps=5, echo=quiet)
    assert result.steps[0].outcome == "refused: curator may not"


def test_a_coder_turn_needs_a_worktree(repo: Path) -> None:
    config = strict_board(repo)
    write_ticket(config.board_path, "3-in-progress", "TST-001", "busy", owner="coder-agent")

    with pytest.raises(core.GateError, match="has no worktree"):
        runner._implement(config, rec("resume_worktree"), repo / "log.txt")


def test_a_reviewer_that_neither_approves_nor_rejects_is_noted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = factory_board(repo)
    verified(config)
    monkeypatch.setattr(runner, "_work", lambda *a, **k: (3, ""))

    outcome = runner._step(config, rec("review_and_gate"), repo / "log.txt")

    assert outcome == "reviewer exited 3 without approving or rejecting"


def test_a_reviewer_who_rejects_is_reported_as_a_rejection(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = factory_board(repo)
    verified(config)
    def reviewer_rejects(*args: object, **kwargs: object) -> tuple[int, str]:
        core.reject(config, "TST-001", "qa", "no")
        return 0, ""

    monkeypatch.setattr(runner, "_work", reviewer_rejects)

    assert runner._step(config, rec("review_and_gate"), repo / "log.txt") == "rejected by the reviewer"


def test_a_signed_approval_is_countersigned_by_the_runner(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = factory_board(repo, require_signed_approvals=True)
    verified(config)
    signed: list[str] = []
    def reviewer_approves(*args: object, **kwargs: object) -> tuple[int, str]:
        core.approve(config, "TST-001", "qa")
        return 0, ""

    monkeypatch.setattr(runner, "_work", reviewer_approves)
    monkeypatch.setattr(core, "countersign", lambda cfg, ticket: signed.append(ticket))

    assert runner._step(config, rec("review_and_gate"), repo / "log.txt") == "approved by qa"
    assert signed == ["TST-001"]


def test_a_refused_merge_goes_back_to_the_coder_and_is_counted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = factory_board(repo)
    verified(config)
    core.approve(config, "TST-001", "qa")

    def refuse(*args: object, **kwargs: object) -> None:
        raise core.GateError("merge conflict in src/app.py")

    monkeypatch.setattr(core, "merge", refuse)

    outcome = runner._merge_and_close(config, "TST-001")

    assert outcome.startswith("merge refused and sent back: merge conflict")
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"
    assert core.integration_refusals(config, "TST-001") == 1


def test_an_attended_run_whose_ready_gate_is_confirmed_takes_the_gate_itself(repo: Path) -> None:
    config = strict_board(repo, autonomy="attended", human_gates=["ready"], workers={"default": f'{PY} -c "pass"'})
    write_ticket(
        config.board_path, "1-refining", "TST-001", "fix", blast_radius=("src/app.py", "tests/check_app.py"), acceptance=("- [ ] f() returns 2 (test: `git --version`)",)
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")
    core.confirm(config, "TST-001")

    outcome = runner._step(config, rec("spec_and_refine"), repo / "log.txt")

    assert outcome == "confirmed by a human; passed the ready gate"
    assert core.find_ticket(config, "TST-001").column == "2-ready"


def test_a_worker_that_overruns_is_killed_with_everything_it_started() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, text=True
    )

    runner._kill_tree(process)

    assert process.wait(timeout=15) != 0
    runner._kill_tree(process)  # killing what is already gone is not an error
