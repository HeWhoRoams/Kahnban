"""Deterministic intake: approved specs, requirement coverage, ticket-size rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import core, frontmatter, guard, linter, specs
from kahnban.cli import main
from conftest import git, scaffold_board, write_ticket

SPEC = """---
id: SPEC-001
title: Bounds
status: draft
approved_by: ""
approved: ""
requirements_hash: ""
---

# SPEC-001: Bounds

## Requirements
- R1: Coordinates inside [0, 1000] are accepted
- R2: Coordinates outside [0, 1000] are refused

## Tickets

### Accept coordinates in range
- Files: `src/bounds.py`, `tests/test_bounds.py`
- Covers: R1
- Blocked on: none
- Acceptance:
  - [ ] in-range input is accepted (test: `git --version`)
- Validation: `git --version`

### Refuse coordinates out of range
- Files: `src/bounds.py`, `tests/test_bounds.py`
- Covers: R2
- Acceptance:
  - [ ] out-of-range input is refused (test: `git --version`)
- Validation: `git --version`
"""


def spec_board(repo: Path, **overrides: object) -> tuple[core.Config, Path]:
    scaffold_board(repo, {"require_spec": True, "max_blast_radius_files": 3, **overrides})
    path = repo / ".agents" / "specs" / "SPEC-001-bounds.md"
    path.parent.mkdir(parents=True)
    path.write_text(SPEC, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "draft SPEC-001")
    return core.load_config(repo), path


def ticket_fields(config: core.Config, ticket_id: str) -> dict:
    return frontmatter.parse(core.find_ticket(config, ticket_id).text)[0]


def refining_ticket(config: core.Config, ticket_id: str, extra: str, **kwargs: object) -> None:
    write_ticket(
        config.board_path,
        "1-refining",
        ticket_id,
        "extra",
        blast_radius=("src/bounds.py", "tests/test_bounds.py"),
        extra_frontmatter=extra,
        **kwargs,  # type: ignore[arg-type]
    )
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", f"add {ticket_id}")


def test_an_approved_spec_ingests_into_traceable_ready_tickets(repo: Path) -> None:
    config, path = spec_board(repo)
    specs.approve_spec(config, "SPEC-001", "tim")

    assert main(["--project-root", str(repo), "ingest", str(path), "--ready"]) == 0

    first, second = ticket_fields(config, "TST-001"), ticket_fields(config, "TST-002")
    assert first["title"] == "Accept coordinates in range"
    assert (first["spec"], first["covers"], first["blocked_on"]) == ("SPEC-001", ["R1"], "")
    assert second["covers"] == ["R2"]
    assert core.find_ticket(config, "TST-002").column == "2-ready"
    assert specs.coverage(config, "SPEC-001").complete
    assert main(["--project-root", str(repo), "spec", "coverage", "SPEC-001"]) == 0
    assert not [f for f in linter.lint(config).findings if f.rule == "BL18"]


def test_ready_refuses_work_without_an_approved_spec_behind_it(repo: Path) -> None:
    config, _ = spec_board(repo)
    refining_ticket(config, "TST-001", "spec: SPEC-001\ncovers: [R1]")
    refining_ticket(config, "TST-002", "")

    with pytest.raises(core.GateError, match="SPEC-001 is not approved"):
        core.ready(config, "TST-001")
    with pytest.raises(core.GateError, match="names no spec"):
        core.ready(config, "TST-002")

    specs.approve_spec(config, "SPEC-001", "tim")
    refining_ticket(config, "TST-003", "spec: SPEC-001\ncovers: [R9]")
    with pytest.raises(core.GateError, match="does not have: R9"):
        core.ready(config, "TST-003")
    assert core.ready(config, "TST-001").to_column == "2-ready"


def test_editing_requirements_after_approval_breaks_the_freeze(repo: Path) -> None:
    config, path = spec_board(repo)
    specs.approve_spec(config, "SPEC-001", "tim")
    path.write_text(
        path.read_text(encoding="utf-8").replace("- R2:", "- R3: anything goes\n- R2:"),
        encoding="utf-8",
    )
    git(repo, "commit", "-qam", "sneak in a requirement")
    refining_ticket(config, "TST-001", "spec: SPEC-001\ncovers: [R1]")

    with pytest.raises(core.GateError, match="changed after approval"):
        core.ready(config, "TST-001")
    violations = [f.message for f in linter.lint(config).violations if f.rule == "BL18"]
    assert any("changed after approval" in message for message in violations)


def test_coverage_names_requirements_no_ticket_covers(repo: Path) -> None:
    config, _ = spec_board(repo)
    specs.approve_spec(config, "SPEC-001", "tim")
    refining_ticket(config, "TST-001", "spec: SPEC-001\ncovers: [R1]")

    report = specs.coverage(config, "SPEC-001")

    assert report.uncovered == ["R2"] and not report.complete
    assert main(["--project-root", str(repo), "spec", "coverage", "SPEC-001"]) == 1
    warnings = [f.message for f in linter.lint(config).warnings if f.rule == "BL18"]
    assert warnings == ["SPEC-001 R2 is covered by no ticket"]


def test_spec_new_drafts_the_next_id_and_approval_needs_requirements(repo: Path) -> None:
    scaffold_board(repo)
    config = core.load_config(repo)

    first = specs.new_spec(config, "Bounds checking")
    second = specs.new_spec(config, "Rate limits")

    assert first.name == "SPEC-001-bounds-checking.md" and second.name.startswith("SPEC-002-")
    spec = specs.load_spec(first)
    assert (spec.spec_id, spec.fields["status"], spec.approved) == ("SPEC-001", "draft", False)
    assert "spec(SPEC-002): draft" in git(repo, "log", "-1", "--format=%s").stdout
    first.write_text(
        first.read_text(encoding="utf-8").replace("- R2: Replace with the second", "- R1: Again"),
        encoding="utf-8",
    )
    with pytest.raises(core.GateError, match="repeats requirement ids: R1"):
        specs.approve_spec(config, "SPEC-001", "tim")


def test_ready_enforces_ticket_size_and_a_test_in_the_radius(repo: Path) -> None:
    scaffold_board(repo, {"max_blast_radius_files": 3, "require_proof": True})
    config = core.load_config(repo)
    (repo / "src" / "engine").mkdir(parents=True)
    (repo / "src" / "engine" / "keep.py").write_text("", encoding="utf-8")
    tickets = {
        "TST-001": ("src/a.py", "src/b.py", "src/c.py", "tests/test_abc.py"),
        "TST-002": ("src/engine", "tests/test_engine.py"),
        "TST-003": ("src/a.py",),
    }
    for ticket_id, radius in tickets.items():
        write_ticket(
            config.board_path,
            "1-refining",
            ticket_id,
            "size",
            blast_radius=radius,
            acceptance=("- [ ] works (test: `git --version`)",),
        )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "tickets")

    with pytest.raises(core.GateError, match="lists 4 paths; the limit is 3"):
        core.ready(config, "TST-001")
    with pytest.raises(core.GateError, match="names directories, not files: src/engine"):
        core.ready(config, "TST-002")
    with pytest.raises(core.GateError, match="names no test file"):
        core.ready(config, "TST-003")


def test_only_a_human_approves_a_spec(repo: Path) -> None:
    def bash(command: str, role: str) -> str | None:
        return guard.decide(
            {"tool_name": "Bash", "tool_input": {"command": command}}, {"KAHNBAN_ROLE": role}
        )

    assert "not a spec_analyst's" in bash("kahnban spec approve SPEC-001 --by me", "spec_analyst")
    assert bash('kahnban spec new "Bounds checking"', "spec_analyst") is None
    assert bash("kahnban spec coverage SPEC-001", "coder") is None
    assert "not a coder's" in bash('kahnban spec new "x"', "coder")
