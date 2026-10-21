"""Tests for the Kahnban learnings queue and deduplicating pattern aggregator."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kahnban import learnings


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    learnings_dir = tmp_path / "learnings"
    learnings_dir.mkdir(parents=True, exist_ok=True)
    (learnings_dir / "archive").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_capture_new_learning(temp_project: Path):
    rec, is_new = learnings.capture_learning(
        temp_project,
        title="Direct non-atomic file writes bypass safety locks",
        problem="Agent called Path.write_text directly causing race condition.",
        ticket_id="HOA-002",
        location="status.py:45",
        trigger="write_text used directly",
        category="architecture",
        severity="medium",
        target_paths=["src/kahnban/status.py"],
        systemic_diagnosis="Missing linter check.",
        proposed_remediation="Use core.write_text_atomic.",
        today="2026-10-21",
    )

    assert is_new is True
    assert rec.id == "LRN-0001"
    assert rec.occurrences == 1
    assert rec.severity == "medium"
    assert rec.target_paths == ["src/kahnban/status.py"]
    assert rec.file_path is not None
    assert rec.file_path.exists()
    assert rec.file_path.name == "LRN-0001-direct-non-atomic-file-writes-bypass-safety-locks.md"

    # Verify content parsed back
    parsed = learnings.parse_learning(rec.file_path)
    assert parsed.id == "LRN-0001"
    assert parsed.occurrences == 1
    assert len(parsed.occurrences_table) == 1
    assert parsed.occurrences_table[0].location == "status.py:45"


def test_clustering_deduplication_and_augmentation(temp_project: Path):
    # First occurrence
    rec1, is_new1 = learnings.capture_learning(
        temp_project,
        title="Direct non-atomic file writes bypass safety locks",
        problem="Agent called Path.write_text directly.",
        ticket_id="HOA-002",
        location="status.py:45",
        trigger="write_text used",
        category="architecture",
        severity="medium",
        target_paths=["src/kahnban/status.py"],
        today="2026-10-21",
    )
    assert is_new1 is True
    assert rec1.occurrences == 1

    # Second occurrence - same pattern, different ticket, higher severity
    rec2, is_new2 = learnings.capture_learning(
        temp_project,
        title="Direct non-atomic file writes bypass safety locks",
        problem="Another agent called write_text in skills.py.",
        ticket_id="HOA-005",
        location="skills.py:112",
        trigger="Copied nearest example",
        category="architecture",
        severity="high",
        target_paths=["src/kahnban/skills.py"],
        systemic_diagnosis="Legacy method still accessible.",
        today="2026-10-21",
    )

    assert is_new2 is False
    assert rec2.id == rec1.id
    assert rec2.occurrences == 2
    assert rec2.severity == "high"  # Escalated from medium
    assert "src/kahnban/status.py" in rec2.target_paths
    assert "src/kahnban/skills.py" in rec2.target_paths

    # Verify occurrences table augmented to 2 rows
    assert len(rec2.occurrences_table) == 2
    assert rec2.occurrences_table[0].ticket_session == "HOA-002"
    assert rec2.occurrences_table[1].ticket_session == "HOA-005"
    assert rec2.occurrences_table[1].location == "skills.py:112"

    # Verify only ONE file exists in learnings/
    files = list((temp_project / "learnings").glob("*.md"))
    assert len(files) == 1


def test_promote_learning(temp_project: Path):
    rec, _ = learnings.capture_learning(
        temp_project,
        title="Unverified blast radius containment",
        problem="Blast radius was assumed rather than proven.",
        ticket_id="HOA-003",
        location="core.py:90",
        category="testing",
        severity="high",
    )

    promoted = learnings.promote_learning(
        temp_project,
        rec.id,
        level="level-2",
        resolution_notes="Added BL16 lint check enforcing blast-radius disjointness.",
        today="2026-10-21",
    )

    assert promoted.status == "promoted"
    assert promoted.escalation_level == "level-2"
    assert promoted.resolved == "2026-10-21"
    assert "Added BL16 lint check" in promoted.proposed_remediation

    # Verify moved to archive/
    assert not (temp_project / "learnings" / rec.file_path.name).exists()
    assert (temp_project / "learnings" / "archive" / rec.file_path.name).exists()

    # Active list should be empty
    active = learnings.list_learnings(temp_project, include_archive=False)
    assert len(active) == 0

    # Archive list should contain it
    all_recs = learnings.list_learnings(temp_project, include_archive=True)
    assert len(all_recs) == 1
    assert all_recs[0].status == "promoted"


def test_cli_learnings(temp_project: Path, capsys: pytest.CaptureFixture):
    from kahnban import cli

    # Capture via CLI
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "capture",
        "--title", "Unchecked exception in session engine",
        "--problem", "CLI panicked when session table had 4 columns",
        "--ticket", "HOA-007",
        "--location", "session.py:88",
        "--category", "architecture",
        "--severity", "high",
        "--path", "src/kahnban/session.py",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Created new learning LRN-0001" in captured.out

    # List via CLI
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "list",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Active Learnings (1):" in captured.out
    assert "LRN-0001: Unchecked exception in session engine" in captured.out

    # Augment via capture with same title
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "capture",
        "--title", "Unchecked exception in session engine",
        "--ticket", "HOA-009",
        "--location", "session.py:120",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Augmented existing pattern LRN-0001" in captured.out
    assert "occurrences: 2" in captured.out

    # Show via CLI
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "show", "LRN-0001",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "id: LRN-0001" in captured.out
    assert "| #2 | HOA-009 | `session.py:120`" in captured.out

    # Promote via CLI
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "promote", "LRN-0001",
        "--level", "level-2",
        "--notes", "Added adaptive column parser",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Promoted LRN-0001" in captured.out
    assert "Moved to ./learnings/archive/" in captured.out

    # List again: active should be 0
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "list",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "No learnings recorded" in captured.out

    # List --all: should show 1
    ret = cli.main([
        "--project-root", str(temp_project),
        "learnings", "list", "--all",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    assert "All Learnings (Active & Archived) (1):" in captured.out
    assert "[PROMOTED]" in captured.out
