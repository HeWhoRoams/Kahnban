"""Unit and CLI tests for cross-harness session continuity (session.py)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from kahnban import cli, core, mcp_server, session
from conftest import git, write_ticket

WHEN = datetime(2026, 10, 20, 16, 45)


def commit_board(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "board fixture")


def test_session_read_write(tmp_path: Path) -> None:
    session_file = session.write_session(
        tmp_path,
        active_ticket="HOA-001",
        active_worktree=".worktrees/HOA-001",
        branch="ticket/HOA-001",
        agent_harness="claude-code",
        status_text="in_progress",
        context="Working on galaxy seam generator.",
        subagents=[
            {
                "id": "HOA-001",
                "owner": "agent-a",
                "worktree": ".worktrees/HOA-001",
                "branch": "ticket/HOA-001",
            }
        ],
        modified_files=["src/galaxy.gd", "tests/test_galaxy.gd"],
        blockers="None today.",
        next_commands=["pytest tests/test_galaxy.gd"],
        timestamp=WHEN,
    )

    assert session_file.exists()
    assert session_file == tmp_path / ".agents" / "state" / "ACTIVE_SESSION.md"

    state = session.read_session(tmp_path)
    assert state is not None
    assert state.active_ticket == "HOA-001"
    assert state.active_worktree == ".worktrees/HOA-001"
    assert state.branch == "ticket/HOA-001"
    assert state.agent_harness == "claude-code"
    assert state.status == "in_progress"
    assert "galaxy seam generator" in state.context
    assert state.modified_files == ["src/galaxy.gd", "tests/test_galaxy.gd"]
    assert state.next_commands == ["pytest tests/test_galaxy.gd"]


def test_session_inspect_live(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "first-task",
        owner="worker-1",
        branch="ticket/TST-001",
        worktree=".worktrees/TST-001",
    )
    commit_board(board)

    # Create a dirty file in repo
    (board / "dirty.txt").write_text("unstaged", encoding="utf-8")

    inspected = session.inspect_session(config)
    assert inspected["active_ticket"] == "TST-001"
    assert inspected["active_worktree"] == ".worktrees/TST-001"
    assert inspected["branch"] == "ticket/TST-001"
    assert len(inspected["in_progress_tickets"]) == 1
    assert "dirty.txt" in inspected["modified_files"]
    assert not any(f.startswith("??") for f in inspected["modified_files"])


def test_cli_session_command(board: Path, capsys) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "active-task",
        owner="worker-1",
        branch="ticket/TST-001",
        worktree=".worktrees/TST-001",
    )
    commit_board(board)

    # 1. Flush session
    code = cli.main(
        [
            "--project-root",
            str(board),
            "session",
            "--flush",
            "--note",
            "TDD refactor loop",
            "--next-cmd",
            "pytest tests/",
        ]
    )
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "[OK] updated session state" in out

    # 2. Inspect session
    code = cli.main(["--project-root", str(board), "session"])
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "Active Session: TST-001 [in_progress]" in out
    assert "Context:  TDD refactor loop" in out
    assert "$ pytest tests/" in out


def test_mcp_session_tools(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-002",
        "mcp-task",
        owner="agent-x",
        branch="ticket/TST-002",
        worktree=".worktrees/TST-002",
    )
    commit_board(board)

    # Update via MCP
    result = mcp_server.tool_session_update(
        board,
        {
            "active_ticket": "TST-002",
            "context": "Updating via MCP tool",
            "status": "review",
            "next_commands": ["kahnban verify TST-002"],
        },
    )
    assert result["ok"] is True
    assert result["active_ticket"] == "TST-002"
    assert result["status"] == "review"

    # Status via MCP
    status_result = mcp_server.tool_session_status(board, {})
    assert status_result["ok"] is True
    assert status_result["has_active_session_file"] is True
    assert status_result["current"]["active_ticket"] == "TST-002"
    assert status_result["current"]["status"] == "review"
    assert status_result["current"]["next_commands"] == ["kahnban verify TST-002"]

def test_mcp_canonical_spec_contract(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-003",
        "spec-task",
        owner="agent-y",
        branch="ticket/TST-003",
        worktree=".worktrees/TST-003",
    )
    commit_board(board)

    # 1. Update using canonical spec parameters (CR-REM-005)
    update_result = mcp_server.tool_session_update(
        board,
        {
            "ticket_id": "TST-003",
            "summary": "Building map generator",
            "modified_files": ["src/map.gd"],
            "next_command": "pytest tests/test_map.py",
            "blockers": "Need seed data",
        },
    )
    assert update_result["ok"] is True
    assert update_result["active_ticket"] == "TST-003"

    # 2. Get using canonical tool alias kanban_session_get (CR-REM-005)
    get_tool = mcp_server.TOOLS["kanban_session_get"]
    get_result = get_tool(board, {})
    assert get_result["ok"] is True
    assert get_result["current"]["active_ticket"] == "TST-003"
    assert get_result["current"]["context"] == "Building map generator"
    assert get_result["current"]["modified_files"] == ["src/map.gd"]
    assert get_result["current"]["next_commands"] == ["pytest tests/test_map.py"]
    assert get_result["current"]["blockers"] == "Need seed data"

    # 3. Verify ISO-8601 timestamp with 'T' (CR-REM-004)
    state = session.read_session(board)
    assert state is not None
    assert "T" in state.last_updated


def test_write_session_dataclass_input(tmp_path: Path) -> None:
    # Test CR-REM-009: passing SessionState directly
    state = session.SessionState(
        last_updated="2026-10-20T20:00:00",
        active_ticket="TST-099",
        active_worktree=".worktrees/TST-099",
        branch="ticket/TST-099",
        agent_harness="antigravity",
        status="in_progress",
        context="Testing dataclass writer",
        modified_files=["file1.py"],
        blockers="",
        next_commands=["make test"],
    )
    session_file = session.write_session(tmp_path, state=state)
    assert session_file.exists()

    read_back = session.read_session(tmp_path)
    assert read_back is not None
    assert read_back.active_ticket == "TST-099"
    assert read_back.last_updated == "2026-10-20T20:00:00"
    assert read_back.agent_harness == "antigravity"



def test_read_session_subagents_table_roundtrip(tmp_path: Path) -> None:
    subagents = [
        {
            "id": "HOA-002",
            "owner": "subagent-alpha",
            "worktree": ".worktrees/HOA-002",
            "branch": "ticket/HOA-002",
            "title": "Sector generator seam",
        },
        {
            "id": "HOA-003",
            "owner": "subagent-beta",
            "worktree": ".worktrees/HOA-003",
            "branch": "ticket/HOA-003",
            "title": "Starbase UI component",
        },
    ]
    session_file = session.write_session(
        tmp_path,
        active_ticket="HOA-001",
        subagents=subagents,
    )
    assert session_file.exists()

    state = session.read_session(tmp_path)
    assert state is not None
    assert len(state.subagents) == 2
    assert state.subagents[0]["id"] == "HOA-002"
    assert state.subagents[0]["owner"] == "subagent-alpha"
    assert state.subagents[0]["worktree"] == ".worktrees/HOA-002"
    assert state.subagents[0]["branch"] == "ticket/HOA-002"
    assert state.subagents[0]["title"] == "Sector generator seam"
    assert state.subagents[1]["id"] == "HOA-003"


def test_session_update_apply_value_object(board: Path) -> None:
    config = core.load_config(board)
    update = session.SessionUpdate(
        ticket_id="HOA-777",
        context="Applied via value object",
        status="review",
        next_commands=["pytest -q"],
    )
    state, path = session.sync_session(config, update=update)
    assert path.exists()
    assert state.active_ticket == "HOA-777"
    assert state.status == "review"
    assert state.context == "Applied via value object"
    assert state.next_commands == ["pytest -q"]
