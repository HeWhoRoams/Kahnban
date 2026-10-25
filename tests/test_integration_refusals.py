"""The merge queue's refusals are counted for the life of a ticket, so confirming cannot loop for ever."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import core, frontmatter, runner
from kahnban.cli import main
from conftest import git
from test_factory_gates import PY, factory_board, verified


def attended_board(repo: Path) -> core.Config:
    config = factory_board(repo, autonomy="attended", workers={"default": f'{PY} -c "pass"'})
    verified(config)
    core.approve(config, "TST-001", "qa")
    return config


def set_field(config: core.Config, name: str, value: str) -> None:
    ticket = core.find_ticket(config, "TST-001")
    fields, body = frontmatter.parse(ticket.text)
    fields[name] = value
    core.write_text(ticket.path, frontmatter.serialize(fields, body))
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", f"set {name}")


def fields_of(config: core.Config) -> dict:
    return frontmatter.parse(core.find_ticket(config, "TST-001").text)[0]


def test_a_merge_queue_rejection_is_counted_and_a_reviewers_is_not(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    core.reject(config, "TST-001", "qa", "no")
    assert core.integration_refusals(config, "TST-001") == 0

    core.verify(config, "TST-001")
    core.reject(config, "TST-001", "integrator", "does not land", integration_refusal=True)
    core.verify(config, "TST-001")
    core.reject(config, "TST-001", "integrator", "still does not land", integration_refusal=True)

    assert core.integration_refusals(config, "TST-001") == 2


def test_confirm_below_the_limit_needs_no_reason_and_keeps_the_count(repo: Path) -> None:
    config = attended_board(repo)
    set_field(config, "integration_refusals", "2")

    core.confirm(config, "TST-001")

    assert core.integration_refusals(config, "TST-001") == 2


def test_confirm_at_the_limit_refuses_without_a_reason(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = attended_board(repo)
    set_field(config, "integration_refusals", str(config.max_attempts))

    with pytest.raises(core.GateError, match="lands nothing new"):
        core.confirm(config, "TST-001")
    assert main(["--project-root", str(repo), "confirm", "TST-001"]) == 1
    assert "--reason" in capsys.readouterr().err


def test_confirm_with_a_reason_allows_exactly_one_more_try(repo: Path) -> None:
    config = attended_board(repo)
    set_field(config, "integration_refusals", str(config.max_attempts))

    assert main(["--project-root", str(repo), "confirm", "TST-001", "--reason", "pinned the dependency"]) == 0

    assert core.integration_refusals(config, "TST-001") == config.max_attempts - 1
    log = core.section(frontmatter.parse(core.find_ticket(config, "TST-001").text)[1], "Log")
    assert "pinned the dependency" in log
    assert fields_of(config)["confirmed"].startswith("merge:")


def test_the_run_escalates_instead_of_pausing_once_the_limit_is_reached(repo: Path) -> None:
    config = attended_board(repo)
    set_field(config, "integration_refusals", str(config.max_attempts))

    outcome = runner._await_human(config, "TST-001")

    assert outcome.startswith("escalated:") and "confirming it again lands nothing new" in outcome
    assert "attended run" not in str(fields_of(config)["blocked_on"])
