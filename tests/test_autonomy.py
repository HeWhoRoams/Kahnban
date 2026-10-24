"""Attended vs unattended runs: a human gate parks the ticket, and retry counts outlive a run."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import core, guard, runner
from kahnban.cli import main
from conftest import git, write_ticket
from test_factory_gates import CHECK, CHECK_APP, CRITERION, PY, factory_board
from test_factory_run import WORKER, fields_of, ready_ticket


def worker_command(tmp_path: Path) -> str:
    script = tmp_path / "worker.py"
    script.write_text(WORKER.format(check_app=CHECK_APP), encoding="utf-8")
    return f"{PY} {script}"


def test_an_attended_run_stops_at_the_merge_gate_until_a_human_confirms(repo: Path, tmp_path: Path) -> None:
    config = factory_board(repo, workers={"default": worker_command(tmp_path)}, autonomy="attended")
    ready_ticket(config)

    first = runner.run(config, max_steps=10, echo=lambda line: None)

    assert [step.action for step in first.steps] == ["claim_and_implement", "review_and_gate", "merge_and_close"]
    assert "paused for a human before merge" in first.steps[-1].outcome
    assert core.find_ticket(config, "TST-001").column == "4-verifying"
    assert str(fields_of(config)["blocked_on"]).startswith("human: attended run")
    assert first.parked and first.parked[0].startswith("TST-001")

    assert main(["--project-root", str(repo), "confirm", "TST-001"]) == 0
    assert fields_of(config)["confirmed"].startswith("merge:")

    second = runner.run(config, max_steps=10, echo=lambda line: None)

    assert [step.action for step in second.steps] == ["merge_and_close"]
    assert core.find_ticket(config, "TST-001").column == "5-done"


def test_an_attended_run_holds_the_ready_gate_against_workers(repo: Path, monkeypatch) -> None:
    config = factory_board(repo, autonomy="attended", human_gates=["ready"])
    write_ticket(config.board_path, "1-refining", "TST-001", "fix", acceptance=(CRITERION,),
                 blast_radius=("src/app.py", "tests/check_app.py"), validation=CHECK)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine TST-001")
    monkeypatch.setenv("KAHNBAN_ROLE", "spec_analyst")

    with pytest.raises(core.GateError, match="waits for a human"):
        core.ready(config, "TST-001")
    monkeypatch.delenv("KAHNBAN_ROLE")  # the CLI refuses 'confirm' to any worker, as it should
    assert main(["--project-root", str(repo), "confirm", "TST-001"]) == 0
    monkeypatch.setenv("KAHNBAN_ROLE", "spec_analyst")
    core.ready(config, "TST-001")  # confirmed, so the gate now judges it on its merits
    assert core.find_ticket(config, "TST-001").column == "2-ready"


def test_confirm_needs_a_branch_and_a_waiting_gate(repo: Path) -> None:
    config = factory_board(repo, autonomy="attended")
    write_ticket(config.board_path, "4-verifying", "TST-001", "fix")
    with pytest.raises(core.GateError, match="no branch"):
        core.confirm(config, "TST-001")
    write_ticket(config.board_path, "3-in-progress", "TST-002", "fix")
    with pytest.raises(core.GateError, match="anything to confirm"):
        core.confirm(config, "TST-002")


def test_a_worker_may_not_confirm_its_own_gate() -> None:
    assert "not a coder's" in guard.command_problem("coder", "confirm")
    assert "not a qa_reviewer's" in guard.command_problem("qa_reviewer", "confirm")


def test_retry_counts_survive_between_runs(repo: Path) -> None:
    idle_worker = f'{PY} -c "import sys; sys.stdin.read()"'
    config = factory_board(repo, workers={"default": idle_worker}, max_attempts=2)
    ready_ticket(config)

    runner.run(config, max_steps=1, echo=lambda line: None)
    assert core.load_attempts(config)["claim_and_implement|TST-001"]["count"] == 1

    # A second run (a new cron tick) picks up the count and escalates on the next try.
    again = runner.run(config, max_steps=5, echo=lambda line: None)
    assert any(step.outcome.startswith("escalated") for step in again.steps)
    assert core.load_attempts(config) == {}  # escalating hands the ticket to a human: counts reset


def test_invalid_autonomy_is_refused(repo: Path) -> None:
    with pytest.raises(core.KahnbanError, match="autonomy must be"):
        factory_board(repo, autonomy="sometimes")
