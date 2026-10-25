"""CLI commands and MCP tools that only the core-level tests used to reach."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import core, frontmatter, session
from kahnban.cli import main
from conftest import git, write_ticket
from test_factory_gates import claimed, factory_board, strict_board, verified
from test_mcp_server import call, tool_payload
from test_spec_gates import spec_board


def run(repo: Path, *argv: str) -> int:
    return main(["--project-root", str(repo), *argv])


def ticket_of(config: core.Config, ticket_id: str = "TST-001") -> core.Ticket:
    return core.find_ticket(config, ticket_id)


def log_of(config: core.Config, ticket_id: str = "TST-001") -> str:
    return core.section(frontmatter.parse(ticket_of(config, ticket_id).text)[1], "Log")


# --- CLI: reject, lease ------------------------------------------------------


def test_reject_via_cli_sends_the_ticket_back_with_the_reasons(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    assert run(repo, "reject", "TST-001", "--reviewer", "qa", "-m", "cover the overflow case") == 0

    assert ticket_of(config).column == "3-in-progress"
    assert "cover the overflow case" in log_of(config)


def test_reject_via_cli_without_reasons_refuses(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = factory_board(repo)
    verified(config)

    assert run(repo, "reject", "TST-001", "--reviewer", "qa") == 1

    assert "--message" in capsys.readouterr().err
    assert ticket_of(config).column == "4-verifying"


def test_lease_via_cli_renews_for_the_holder_and_refuses_a_rival(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = strict_board(repo)
    claimed(config)

    assert run(repo, "lease", "TST-001", "--owner", "coder", "--minutes", "5") == 0
    assert "leased by coder" in capsys.readouterr().out
    assert run(repo, "lease", "TST-001", "--owner", "rival") == 1
    assert "leased by" in capsys.readouterr().err


# --- CLI: spec, handoff ------------------------------------------------------


def test_spec_list_new_and_approve_via_cli(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config, _ = spec_board(repo)

    assert run(repo, "spec", "list") == 0
    listing = capsys.readouterr().out
    assert "SPEC-001 [draft]" in listing
    assert "2 requirement(s)" in listing

    assert run(repo, "spec", "approve", "SPEC-001", "--by", "a human") == 0
    assert "approved by a human" in capsys.readouterr().out
    assert run(repo, "spec", "list") == 0
    assert "SPEC-001 [approved]" in capsys.readouterr().out

    assert run(repo, "spec", "new", "Second spec") == 0
    assert "SPEC-002" in capsys.readouterr().out
    assert len(list((config.project_root / ".agents" / "specs").glob("SPEC-*.md"))) == 2


def test_handoff_via_cli_inspects_then_records_a_note(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(board, "handoff") == 0
    assert "no ACTIVE_SESSION.md" in capsys.readouterr().out

    assert run(board, "handoff", "--ticket", "TST-001", "--note", "halfway through the parser") == 0

    assert "halfway through the parser" in session.get_session_path(board).read_text(encoding="utf-8")
    assert run(board, "handoff") == 0
    out = capsys.readouterr().out
    assert "TST-001" in out
    assert "halfway through the parser" in out


# --- MCP: ready, next, session -----------------------------------------------


def test_ticket_ready_tool_moves_a_refined_ticket(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    git(board, "add", "-A")
    git(board, "commit", "-m", "refine")

    payload = tool_payload(call(board, "kanban_ticket_ready", {"ticket_id": "TST-001"}))

    assert payload["from_column"] == "1-refining"
    assert payload["to_column"] == "2-ready"


def test_next_tool_recommends_the_next_step(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "example")
    git(board, "add", "-A")
    git(board, "commit", "-m", "ready")

    payload = tool_payload(call(board, "kanban_next", {}))

    assert payload["ok"] is True
    assert payload["recommendation"]["ticket_id"] == "TST-001"
    assert payload["recommendation"]["assigned_role"] == "coder"


def test_session_status_and_update_tools_round_trip(board: Path) -> None:
    before = tool_payload(call(board, "kanban_session_status", {"inspect_live": False}))
    assert before["has_active_session_file"] is False

    updated = tool_payload(
        call(
            board,
            "kanban_session_update",
            {"ticket_id": "TST-001", "summary": "parser half done", "next_command": "pytest -q"},
        )
    )
    assert updated["active_ticket"] == "TST-001"

    after = tool_payload(call(board, "kanban_session_status", {"inspect_live": False}))
    assert after["has_active_session_file"] is True
    assert after["current"]["active_ticket"] == "TST-001"
    assert after["current"]["context"] == "parser half done"
    assert after["current"]["next_commands"] == ["pytest -q"]


# --- MCP: review gates, lease, escalate --------------------------------------


def test_approve_tool_signs_off_a_verified_ticket(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    payload = tool_payload(
        call(repo, "kanban_ticket_approve", {"ticket_id": "TST-001", "reviewer": "qa", "note": "reads well"})
    )

    assert payload["ok"] is True
    assert "reads well" in log_of(config)
    refused = call(repo, "kanban_ticket_approve", {"ticket_id": "TST-001", "reviewer": "coder"})
    assert refused["result"]["isError"] is True


def test_reject_and_feedback_tools_send_the_ticket_back(repo: Path) -> None:
    config = factory_board(repo)
    tree = verified(config)

    rejected = tool_payload(
        call(repo, "kanban_ticket_reject", {"ticket_id": "TST-001", "reviewer": "qa", "feedback": "cover overflow"})
    )
    assert rejected["to_column"] == "3-in-progress"
    assert "cover overflow" in log_of(config)

    (tree / "src" / "app.py").write_text("def f():\n    return 2  # overflow-safe\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "handle overflow")
    assert core.verify(config, "TST-001").passed

    fed_back = tool_payload(
        call(repo, "kanban_feedback", {"ticket_id": "TST-001", "author": "qa", "feedback": "still wrong"})
    )
    assert fed_back["to_column"] == "3-in-progress"
    assert "still wrong" in log_of(config)


def test_reject_tool_needs_feedback(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    response = call(repo, "kanban_ticket_reject", {"ticket_id": "TST-001"})

    assert response["error"]["code"] == -32602
    assert ticket_of(config).column == "4-verifying"


def test_lease_tool_renews_for_the_holder_and_refuses_a_rival(repo: Path) -> None:
    config = strict_board(repo)
    claimed(config)

    mine = tool_payload(call(repo, "kanban_ticket_lease", {"ticket_id": "TST-001", "owner": "coder", "minutes": 5}))
    assert mine["ok"] is True
    assert mine["leased_by"] == "coder"

    rival = call(repo, "kanban_ticket_lease", {"ticket_id": "TST-001", "owner": "rival"})
    assert rival["result"]["isError"] is True


def test_escalate_tool_parks_the_ticket_for_a_human(repo: Path) -> None:
    config = strict_board(repo)
    claimed(config)

    payload = tool_payload(
        call(repo, "kanban_ticket_escalate", {"ticket_id": "TST-001", "reason": "which rounding rule?"})
    )

    assert payload["ok"] is True
    fields = frontmatter.parse(ticket_of(config).text)[0]
    assert "which rounding rule?" in str(fields["blocked_on"])
