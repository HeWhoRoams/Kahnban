"""STATUS.md and status.json are faithful, ordered projections of the folders."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from kahnban import core, status
from conftest import git, write_ticket

WHEN = datetime(2026, 8, 18, 14, 30)


def commit_board(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "board fixture")


def test_projections_match_folder_state(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "0-backlog",
        "TST-002",
        "second-idea",
        title="Second idea",
    )
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "first-idea",
        title="First idea",
        owner="agent-a",
        branch="ticket/TST-001",
        worktree=".worktrees/TST-001",
    )
    write_ticket(config.board_path, "archive", "TST-000", "retired")
    commit_board(board)

    core.sync(config, timestamp=WHEN)

    payload = json.loads((board / "plans" / "status.json").read_text(encoding="utf-8"))
    columns = {entry["name"]: entry for entry in payload["columns"]}
    assert payload["generated"] == "2026-08-18T14:30:00"
    assert columns["0-backlog"]["count"] == 1
    assert columns["3-in-progress"]["count"] == 1
    assert columns["5-done"]["tickets"] == []
    # Archive is not a column projection; the folders remain ground truth.
    assert "archive" not in columns
    in_progress = columns["3-in-progress"]["tickets"][0]
    assert in_progress == {
        "id": "TST-001",
        "title": "First idea",
        "status": "in-progress",
        "owner": "agent-a",
        "branch": "ticket/TST-001",
        "worktree": ".worktrees/TST-001",
        "updated": "2026-08-18",
        "column": "3-in-progress",
    }

    markdown = (board / "plans" / "STATUS.md").read_text(encoding="utf-8")
    assert "Generated: 2026-08-18 14:30" in markdown
    assert "| TST-001 | First idea | agent-a | ticket/TST-001 | 2026-08-18 |" in markdown
    assert "| 0-backlog | 1 |" in markdown
    assert "_empty_" in markdown


def test_titles_come_from_frontmatter_not_the_filename(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "0-backlog",
        "TST-001",
        "w4-2-guidance-v2",
        title="W4 guidance: accuracy curve, phase 2",
    )
    commit_board(board)

    core.sync(config, timestamp=WHEN)

    markdown = (board / "plans" / "STATUS.md").read_text(encoding="utf-8")
    assert "W4 guidance: accuracy curve, phase 2" in markdown
    assert "w4-2-guidance-v2" not in markdown


def test_ordering_is_numeric_and_deterministic(board: Path) -> None:
    config = core.load_config(board)
    for identifier in ("TST-010", "TST-2", "TST-1", "TST-100"):
        write_ticket(config.board_path, "0-backlog", identifier, "example")
    commit_board(board)

    core.sync(config, timestamp=WHEN)
    first = (board / "plans" / "status.json").read_text(encoding="utf-8")
    core.sync(config, timestamp=WHEN)
    second = (board / "plans" / "status.json").read_text(encoding="utf-8")

    assert first == second
    payload = json.loads(first)
    backlog = next(c for c in payload["columns"] if c["name"] == "0-backlog")
    assert [t["id"] for t in backlog["tickets"]] == [
        "TST-1",
        "TST-2",
        "TST-010",
        "TST-100",
    ]


def test_round_trip_folder_state_to_projection_and_back(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "2-ready", "TST-001", "one", title="One")
    write_ticket(config.board_path, "2-ready", "TST-002", "two", title="Two")
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-003",
        "three",
        title="Three",
        owner="agent",
        branch="ticket/TST-003",
    )
    commit_board(board)

    core.sync(config, timestamp=WHEN)
    payload = json.loads((board / "plans" / "status.json").read_text(encoding="utf-8"))

    projected = {
        (ticket["id"], entry["name"])
        for entry in payload["columns"]
        for ticket in entry["tickets"]
    }
    actual = {(t.ticket_id, t.column) for t in core.iter_tickets(config)}
    assert projected == actual


def test_unparseable_tickets_are_visible_in_the_projection(board: Path) -> None:
    config = core.load_config(board)
    broken = config.board_path / "0-backlog" / "TST-001-broken.md"
    broken.write_text("no frontmatter here\n", encoding="utf-8")
    commit_board(board)

    core.sync(config, timestamp=WHEN)

    markdown = (board / "plans" / "STATUS.md").read_text(encoding="utf-8")
    assert "(invalid frontmatter)" in markdown


def test_markdown_escapes_pipes_in_titles(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path, "0-backlog", "TST-001", "piped", title="a | b pipeline"
    )
    commit_board(board)

    core.sync(config, timestamp=WHEN)

    markdown = (board / "plans" / "STATUS.md").read_text(encoding="utf-8")
    assert "a \\| b pipeline" in markdown


def test_projections_are_written_with_lf_endings(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    core.sync(config, timestamp=WHEN)

    for name in ("STATUS.md", "status.json"):
        raw = (board / "plans" / name).read_bytes()
        assert b"\r\n" not in raw


def test_render_helpers_are_pure(tmp_path: Path) -> None:
    records = [
        {
            "id": "TST-002",
            "title": "Second",
            "status": "backlog",
            "owner": "",
            "branch": "",
            "worktree": "",
            "updated": "2026-08-18",
            "column": "0-backlog",
        },
        {
            "id": "TST-001",
            "title": "First",
            "status": "backlog",
            "owner": "",
            "branch": "",
            "worktree": "",
            "updated": "2026-08-18",
            "column": "0-backlog",
        },
    ]

    markdown = status.render_markdown(records, ["0-backlog"], timestamp=WHEN)
    payload = json.loads(status.render_json(records, ["0-backlog"], timestamp=WHEN))

    assert markdown.index("TST-001") < markdown.index("TST-002")
    assert [t["id"] for t in payload["columns"][0]["tickets"]] == ["TST-001", "TST-002"]
    written = status.write(tmp_path, records, ["0-backlog"], timestamp=WHEN)
    assert [path.name for path in written] == ["STATUS.md", "status.json"]
