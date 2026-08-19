"""MCP protocol conformance and tool round-trips (plan §4.6)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kahnban import core, mcp_server
from conftest import git, write_ticket

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")


def commit_board(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "board fixture")


def drive(project_root: Path, messages: list[dict]) -> list[dict]:
    """Feed newline-delimited frames through a Server and collect responses."""
    payload = "".join(json.dumps(message) + "\n" for message in messages)
    stdout = io.StringIO()
    server = mcp_server.Server(
        project_root, stdin=io.StringIO(payload), stdout=stdout
    )
    server.serve_forever()
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def call(project_root: Path, name: str, arguments: dict, *, identifier: int = 1) -> dict:
    responses = drive(
        project_root,
        [
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        ],
    )
    assert len(responses) == 1
    return responses[0]


def tool_payload(response: dict) -> dict:
    return json.loads(response["result"]["content"][0]["text"])


# --- protocol ---------------------------------------------------------------


def test_initialize_reports_the_protocol_version(board: Path) -> None:
    [response] = drive(
        board, [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}]
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert response["result"]["serverInfo"]["name"] == "kahnban"
    assert response["result"]["capabilities"]["tools"] == {"listChanged": False}


@pytest.mark.parametrize(
    "notification",
    [
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}},
        {"jsonrpc": "2.0", "method": "notifications/unheard-of"},
        {"jsonrpc": "2.0"},
    ],
)
def test_notifications_never_receive_a_response(board: Path, notification: dict) -> None:
    assert drive(board, [notification]) == []


def test_unknown_requests_get_method_not_found(board: Path) -> None:
    [response] = drive(board, [{"jsonrpc": "2.0", "id": 7, "method": "resources/list"}])

    assert response["id"] == 7
    assert response["error"]["code"] == -32601


def test_ping_is_answered_with_an_empty_result(board: Path) -> None:
    [response] = drive(board, [{"jsonrpc": "2.0", "id": 2, "method": "ping"}])

    assert response["result"] == {}


def test_parse_errors_answer_with_a_null_id(board: Path) -> None:
    stdout = io.StringIO()
    server = mcp_server.Server(board, stdin=io.StringIO("{not json}\n"), stdout=stdout)
    server.serve_forever()

    response = json.loads(stdout.getvalue())
    assert response["id"] is None
    assert response["error"]["code"] == -32700


def test_non_object_messages_are_invalid_requests(board: Path) -> None:
    stdout = io.StringIO()
    mcp_server.Server(board, stdin=io.StringIO("42\n"), stdout=stdout).serve_forever()

    assert json.loads(stdout.getvalue())["error"]["code"] == -32600


def test_blank_lines_are_ignored(board: Path) -> None:
    stdout = io.StringIO()
    mcp_server.Server(
        board, stdin=io.StringIO("\n\n  \n"), stdout=stdout
    ).serve_forever()

    assert stdout.getvalue() == ""


def test_tools_list_advertises_every_tool(board: Path) -> None:
    [response] = drive(board, [{"jsonrpc": "2.0", "id": 3, "method": "tools/list"}])

    tools = response["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == set(mcp_server.TOOLS)
    for tool in tools:
        assert tool["description"]
        assert tool["inputSchema"]["type"] == "object"


def test_unknown_tools_and_bad_arguments_are_invalid_params(board: Path) -> None:
    unknown = call(board, "kanban_not_a_tool", {})
    assert unknown["error"]["code"] == -32602

    missing = call(board, "kanban_ticket_get", {})
    assert missing["error"]["code"] == -32602


def test_project_root_resolution_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv_root = tmp_path / "from-argv"
    env_root = tmp_path / "from-env"
    cwd_root = tmp_path / "from-cwd"
    for path in (argv_root, env_root, cwd_root):
        path.mkdir()

    monkeypatch.setenv("KAHNBAN_PROJECT_ROOT", str(env_root))
    monkeypatch.chdir(cwd_root)

    assert mcp_server.resolve_project_root(["--project-root", str(argv_root)]) == (
        argv_root.resolve()
    )
    assert mcp_server.resolve_project_root([]) == env_root.resolve()

    monkeypatch.delenv("KAHNBAN_PROJECT_ROOT")
    assert mcp_server.resolve_project_root([]) == cwd_root.resolve()


# --- tools ------------------------------------------------------------------


def test_board_status_tool_reports_counts_and_lint(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    payload = tool_payload(call(board, "kanban_board_status", {}))

    assert payload["ok"] is True
    assert payload["column_counts"]["0-backlog"] == 1
    assert payload["violations"] == []


def test_ticket_get_tool_returns_frontmatter_and_body(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "0-backlog",
        "TST-001",
        "example",
        title="Readable title",
        blast_radius=("src/one.py", "src/two.py"),
    )
    commit_board(board)

    payload = tool_payload(call(board, "kanban_ticket_get", {"ticket_id": "TST-001"}))

    assert payload["column"] == "0-backlog"
    assert payload["frontmatter"]["title"] == "Readable title"
    assert payload["blast_radius"] == ["src/one.py", "src/two.py"]
    assert "## Problem" in payload["body"]


def test_ticket_new_and_move_tools(board: Path) -> None:
    created = tool_payload(
        call(board, "kanban_ticket_new", {"title": "From MCP", "problem": "Because."})
    )
    assert created["ticket_id"] == "TST-001"
    assert created["to_column"] == "0-backlog"

    moved = tool_payload(
        call(
            board,
            "kanban_ticket_move",
            {"ticket_id": "TST-001", "column": "1-refining", "reason": "refining"},
        )
    )
    assert moved["to_column"] == "1-refining"


def test_claim_verify_done_and_cleanup_tools(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "example",
        blast_radius=("src/feature.py",),
    )
    commit_board(board)

    claimed = tool_payload(
        call(board, "kanban_ticket_claim", {"ticket_id": "TST-001", "owner": "agent-a"})
    )
    assert claimed["to_column"] == "3-in-progress"
    assert claimed["worktree"].endswith(".worktrees/TST-001")

    tree = board / ".worktrees" / "TST-001"
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "feature.py").write_text("ok = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "ticket work")

    verified = tool_payload(call(board, "kanban_ticket_verify", {"ticket_id": "TST-001"}))
    assert verified["passed"] is True
    assert verified["exit_code"] == 0
    assert "git version" in verified["output"]
    assert verified["transition"]["to_column"] == "4-verifying"

    ticket = core.find_ticket(config, "TST-001")
    core.write_text(ticket.path, core.read_text(ticket.path).replace("- [ ]", "- [x]"))
    git(board, "add", "-A")
    git(board, "commit", "-m", "check the boxes")
    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")

    finished = tool_payload(call(board, "kanban_ticket_done", {"ticket_id": "TST-001"}))
    assert finished["to_column"] == "5-done"

    cleaned = tool_payload(call(board, "kanban_cleanup", {"ticket_id": "TST-001"}))
    assert cleaned["ok"] is True
    assert not (board / ".worktrees" / "TST-001").exists()


def test_verify_tool_reports_failure_without_moving_the_ticket(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "example",
        validation="git rev-parse --verify no-such-ref",
    )
    commit_board(board)
    call(board, "kanban_ticket_claim", {"ticket_id": "TST-001", "create_worktree": False, "owner": "a"})

    payload = tool_payload(call(board, "kanban_ticket_verify", {"ticket_id": "TST-001"}))

    assert payload["passed"] is False
    assert payload["exit_code"] != 0
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"


def test_gate_refusals_are_tool_errors_not_protocol_errors(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    commit_board(board)

    response = call(
        board, "kanban_ticket_claim", {"ticket_id": "TST-001", "owner": "agent"}
    )

    assert "error" not in response
    assert response["result"]["isError"] is True
    payload = tool_payload(response)
    assert payload["ok"] is False
    assert "only 2-ready" in payload["error"]


def test_missing_tickets_are_reported_as_tool_errors(board: Path) -> None:
    response = call(board, "kanban_ticket_get", {"ticket_id": "TST-404"})

    assert response["result"]["isError"] is True
    assert "not found" in tool_payload(response)["error"]


def test_sync_tool_writes_projections(board: Path) -> None:
    payload = tool_payload(call(board, "kanban_sync", {}))

    assert payload["ok"] is True
    assert any(path.endswith("STATUS.md") for path in payload["written"])


def test_batched_requests_each_get_a_response(board: Path) -> None:
    responses = drive(
        board,
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ],
    )

    assert [response["id"] for response in responses] == [1, 2, 3]


# --- real stdio -------------------------------------------------------------


def test_server_over_real_stdio_pipes_keeps_stdout_clean(board: Path) -> None:
    frames = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "kanban_board_status", "arguments": {}},
        },
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "kahnban.mcp_server",
            "--project-root",
            str(board),
        ],
        input="".join(json.dumps(frame) + "\n" for frame in frames),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": REPO_SRC},
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    responses = [
        json.loads(line) for line in completed.stdout.splitlines() if line.strip()
    ]
    assert [response["id"] for response in responses] == [1, 2, 3]
    # Every stdout line is a protocol frame; diagnostics went to stderr.
    assert all("jsonrpc" in response for response in responses)
    assert "[kahnban-mcp]" in completed.stderr


def test_server_reads_the_project_root_from_the_environment(board: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "kahnban.mcp_server"],
        input=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "kanban_board_status", "arguments": {}},
            }
        )
        + "\n",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": REPO_SRC,
            "KAHNBAN_PROJECT_ROOT": str(board),
        },
        cwd=str(Path(__file__).resolve().parents[1]),
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        json.loads(completed.stdout.splitlines()[0])["result"]["content"][0]["text"]
    )
    assert payload["ok"] is True
