"""CLI and MCP surfaces for the ingest/capture entry points."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from kahnban import core, frontmatter, mcp_server
from kahnban.cli import main
from conftest import git

PLAN = """# Cache programme

## Warm the cache on boot
**Why:** cold starts take 12 seconds.
**Acceptance:**
- [ ] boot warms the cache
**Files:** `src/cache.py`
**Validation:** `git --version`

## Evict stale entries
**Why:** memory grows without bound.
**Acceptance:**
- [ ] entries older than a day are evicted
**Files:** `src/evict.py`
**Validation:** `git --version`
"""


def run(board: Path, *argv: str) -> int:
    return main(["--project-root", str(board), *argv])


def write_plan(board: Path, text: str = PLAN, name: str = "plans/PLAN.md") -> Path:
    path = board / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    git(board, "add", "-A")
    git(board, "commit", "-m", "add plan")
    return path


def drive(project_root: Path, name: str, arguments: dict) -> dict:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    stdout = io.StringIO()
    mcp_server.Server(
        project_root, stdin=io.StringIO(json.dumps(request) + "\n"), stdout=stdout
    ).serve_forever()
    response = json.loads(stdout.getvalue())
    assert "error" not in response, response
    return response["result"]


def payload(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


# --- CLI --------------------------------------------------------------------


def test_ingest_dry_run_then_write(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    assert run(board, "ingest", str(plan), "--dry-run") == 0
    preview = capsys.readouterr().out
    assert "[DRY-RUN]" in preview
    assert "would create: Warm the cache on boot" in preview
    assert core.iter_tickets(config) == []

    assert run(board, "ingest", str(plan)) == 0
    written = capsys.readouterr().out
    assert "created TST-001" in written
    assert "created TST-002" in written
    assert len(core.iter_tickets(config)) == 2


def test_ingest_reports_drift_with_exit_one(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = write_plan(board)
    assert run(board, "ingest", str(plan)) == 0
    capsys.readouterr()
    plan.write_text(PLAN.replace("12 seconds", "20 seconds"), encoding="utf-8", newline="\n")

    assert run(board, "ingest", str(plan)) == 1
    assert "source changed for TST-001" in capsys.readouterr().out

    assert run(board, "ingest", str(plan), "--update") == 0
    assert "refreshed TST-001" in capsys.readouterr().out


def test_ingest_ready_promotes_through_the_real_gate(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    assert run(board, "ingest", str(plan), "--ready") == 0

    out = capsys.readouterr().out
    assert "passed the ready gate" in out
    assert core.find_ticket(config, "TST-001").column == "2-ready"
    assert run(board, "claim", "TST-001", "--owner", "agent-a", "--no-worktree") == 0


def test_ingest_json_mode(board: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan = write_plan(board)

    assert run(board, "ingest", str(plan), "--dry-run", "--json") == 0

    reports = json.loads(capsys.readouterr().out)
    assert len(reports) == 1
    assert [draft["title"] for draft in reports[0]["drafts"]] == [
        "Warm the cache on boot",
        "Evict stale entries",
    ]


def test_ingest_accepts_globs_and_per_file(
    board: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_plan(board, "# Feature A\n## Problem\nMissing.\n", "specs/a.md")
    write_plan(board, "# Feature B\n## Problem\nMissing.\n", "specs/b.md")
    monkeypatch.chdir(board)

    assert run(board, "ingest", "specs/*.md", "--per-file") == 0

    out = capsys.readouterr().out
    assert "created TST-001" in out and "created TST-002" in out


def test_ingest_missing_document_exits_one(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(board, "ingest", str(board / "plans" / "nope.md")) == 1

    assert "no plan document matched" in capsys.readouterr().err


def test_capture_from_arguments_and_stdin(
    board: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = core.load_config(board)

    assert run(board, "capture", "Try a warm cache", "Rework the loader") == 0
    assert len(core.iter_tickets(config)) == 2
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.stdin", io.StringIO("- Idea from stdin\n- Another idea\n\n")
    )
    assert run(board, "capture", "--from-file", "-") == 0

    assert len(core.iter_tickets(config)) == 4
    titles = {
        frontmatter.parse(ticket.text)[0]["title"] for ticket in core.iter_tickets(config)
    }
    assert "Idea from stdin" in titles
    assert "Another idea" in titles


def test_capture_without_ideas_exits_one(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(board, "capture") == 1

    assert "no ideas given" in capsys.readouterr().err


def test_new_still_works_and_leaves_no_placeholder_readiness(board: Path) -> None:
    config = core.load_config(board)

    assert run(board, "new", "A plain ticket") == 0

    ticket = core.find_ticket(config, "TST-001")
    _, body = frontmatter.parse(ticket.text)
    # No fabricated criteria or blast radius inherited from the template.
    assert core.checkboxes(body) == (0, 0)
    assert core.parse_blast_radius(body) == []
    core.move(config, "TST-001", "1-refining", reason="refining")
    with pytest.raises(core.GateError, match="Blast radius"):
        core.ready(config, "TST-001")


# --- MCP --------------------------------------------------------------------


def test_plan_ingest_tool_dry_run_and_write(board: Path) -> None:
    write_plan(board)
    config = core.load_config(board)

    preview = payload(
        drive(board, "kanban_plan_ingest", {"path": "plans/PLAN.md", "dry_run": True})
    )
    assert preview["ok"] is True
    assert preview["dry_run"] is True
    assert len(preview["drafts"]) == 2
    assert core.iter_tickets(config) == []

    written = payload(drive(board, "kanban_plan_ingest", {"path": "plans/PLAN.md"}))
    assert [entry["ticket_id"] for entry in written["created"]] == ["TST-001", "TST-002"]
    assert "created TST-001" in written["summary"]


def test_plan_ingest_tool_reports_drift_as_not_ok(board: Path) -> None:
    plan = write_plan(board)
    drive(board, "kanban_plan_ingest", {"path": "plans/PLAN.md"})
    plan.write_text(PLAN.replace("12 seconds", "30 seconds"), encoding="utf-8", newline="\n")

    result = payload(drive(board, "kanban_plan_ingest", {"path": "plans/PLAN.md"}))

    assert result["ok"] is False
    assert result["drifted"][0]["ticket_id"] == "TST-001"


def test_plan_ingest_tool_promotes_with_ready(board: Path) -> None:
    write_plan(board)
    config = core.load_config(board)

    result = payload(
        drive(board, "kanban_plan_ingest", {"path": "plans/PLAN.md", "ready": True})
    )

    assert result["promoted"] == ["TST-001", "TST-002"]
    assert core.find_ticket(config, "TST-002").column == "2-ready"


def test_plan_ingest_tool_missing_path_is_a_tool_error(board: Path) -> None:
    result = drive(board, "kanban_plan_ingest", {"path": "plans/nope.md"})

    assert result["isError"] is True
    assert "not found" in payload(result)["error"]


def test_capture_tool_creates_backlog_tickets(board: Path) -> None:
    config = core.load_config(board)

    result = payload(
        drive(board, "kanban_capture", {"ideas": ["Idea one", "Idea two"]})
    )

    assert [entry["ticket_id"] for entry in result["created"]] == ["TST-001", "TST-002"]
    assert len(core.iter_tickets(config)) == 2


def test_capture_tool_requires_ideas(board: Path) -> None:
    stdout = io.StringIO()
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "kanban_capture", "arguments": {"ideas": []}},
    }
    mcp_server.Server(
        board, stdin=io.StringIO(json.dumps(request) + "\n"), stdout=stdout
    ).serve_forever()

    assert json.loads(stdout.getvalue())["error"]["code"] == -32602


def test_ticket_new_tool_accepts_a_full_body(board: Path) -> None:
    config = core.load_config(board)

    result = payload(
        drive(
            board,
            "kanban_ticket_new",
            {
                "title": "Fully specified from the agent",
                "problem": "The loader is slow.",
                "acceptance": ["loads in under a second", "no regressions"],
                "blast_radius": ["src/loader.py"],
                "notes": "Reuse the existing cache helper.",
                "validation": "git --version",
            },
        )
    )

    assert result["ticket_id"] == "TST-001"
    ticket = core.find_ticket(config, "TST-001")
    _, body = frontmatter.parse(ticket.text)
    assert core.checkboxes(body) == (0, 2)
    assert core.parse_blast_radius(body) == ["src/loader.py"]
    assert core.validation_command(config, body) == "git --version"
    # Fully specified by the agent, so the gate lets it through immediately.
    core.move(config, "TST-001", "1-refining", reason="refining")
    assert core.ready(config, "TST-001").to_column == "2-ready"


def test_ticket_new_tool_rejects_a_non_array_field(board: Path) -> None:
    stdout = io.StringIO()
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "kanban_ticket_new",
            "arguments": {"title": "x", "acceptance": 5},
        },
    }
    mcp_server.Server(
        board, stdin=io.StringIO(json.dumps(request) + "\n"), stdout=stdout
    ).serve_forever()

    assert json.loads(stdout.getvalue())["error"]["code"] == -32602
