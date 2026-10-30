"""KB-031: the dry-run ingest report surfaces each draft's spec and covers.

KB-032: ingest warns (without failing) on traceability and size problems a
dry-run report used to stay silent on.
"""

from __future__ import annotations

import json
from pathlib import Path

from kahnban import core, ingest, specs
from kahnban.cli import main

from conftest import git, set_board_config

SPEC = """---
id: SPEC-005
title: Example spec
---

# Example spec

## Tickets

### Add the thing
Problem: there is no thing.

Acceptance criteria:
- [ ] the thing exists

Files:
- `src/thing.py`

Covers: R18, R19
"""


def write_spec(repo: Path) -> Path:
    path = repo / "specs" / "example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SPEC, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "add spec document")
    return path


def test_text_report_shows_spec_and_covers(board: Path) -> None:
    spec = write_spec(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [spec], dry_run=True)
    rendered = ingest.render_report([report])

    assert "spec: SPEC-005" in rendered
    assert "covers: R18, R19" in rendered


def test_json_report_has_spec_and_covers(board: Path) -> None:
    spec = write_spec(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [spec], dry_run=True)
    payload = json.loads(json.dumps(report.as_dict()))

    draft = payload["drafts"][0]
    assert draft["spec"] == "SPEC-005"
    assert draft["covers"] == ["R18", "R19"]


# --- KB-032: warnings on traceability and size problems ---------------------


def write_real_spec(
    repo: Path,
    *,
    spec_id: str = "SPEC-001",
    requirements: tuple[str, ...] = ("R1: first requirement", "R2: second requirement"),
    tickets_body: str,
) -> Path:
    """A spec document under ``.agents/specs/`` -- what ``specs.find_spec`` sees.

    Left unapproved by default; a test calls ``specs.approve_spec`` when it
    needs an approved one.
    """
    path = repo / ".agents" / "specs" / f"{spec_id}-bounds.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    requirements_block = "\n".join(f"- {item}" for item in requirements)
    path.write_text(
        f"""---
id: {spec_id}
title: Bounds
status: draft
approved_by: ""
approved: ""
requirements_hash: ""
---

# {spec_id}: Bounds

## Requirements
{requirements_block}

## Tickets

{tickets_body}
""",
        encoding="utf-8",
        newline="\n",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", f"draft {spec_id}")
    return path


def write_plan(repo: Path, text: str, name: str) -> Path:
    path = repo / name
    path.write_text(text, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", f"add {name}")
    return path


ONE_TICKET = """### Add the thing
Problem: there is no thing.

Acceptance criteria:
- [ ] the thing exists

Files:
- `src/thing.py`

Covers: {covers}
"""


def test_warns_on_unknown_covers(board: Path) -> None:
    path = write_real_spec(
        board,
        requirements=("R1: first requirement",),
        tickets_body=ONE_TICKET.format(covers="R1, R99"),
    )
    config = core.load_config(board)
    specs.approve_spec(config, "SPEC-001", "tim")

    [report] = ingest.ingest(config, [path], dry_run=True)

    assert any(
        "R99" in warning and "does not define" in warning for warning in report.warnings
    ), report.warnings


def test_warns_on_uncovered_requirement(board: Path) -> None:
    path = write_real_spec(
        board,
        requirements=("R1: first requirement", "R2: second requirement"),
        tickets_body=ONE_TICKET.format(covers="R1"),
    )
    config = core.load_config(board)
    specs.approve_spec(config, "SPEC-001", "tim")

    [report] = ingest.ingest(config, [path], dry_run=True)

    assert any(
        "R2" in warning and "no draft covers" in warning for warning in report.warnings
    ), report.warnings


def test_warns_on_unapproved_spec(board: Path) -> None:
    path = write_real_spec(
        board,
        requirements=("R1: first requirement",),
        tickets_body=ONE_TICKET.format(covers="R1"),
    )
    config = core.load_config(board)
    # left unapproved: no specs.approve_spec call

    [report] = ingest.ingest(config, [path], dry_run=True)

    assert any("not approved" in warning for warning in report.warnings), report.warnings


RADIUS_PLAN = """# Plan

### Empty radius ticket
Problem: nothing to touch yet.

Acceptance criteria:
- [ ] works

Validation: `git --version`

### Oversized radius ticket
Problem: touches too much.

Acceptance criteria:
- [ ] works

Files:
- `a.py`
- `b.py`
- `c.py`

Validation: `git --version`
"""


def test_warns_on_radius_size(board: Path) -> None:
    set_board_config(board, max_blast_radius_files=2)
    plan = write_plan(board, RADIUS_PLAN, "radius.md")
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], dry_run=True)

    assert any("blast radius is empty" in warning for warning in report.warnings), report.warnings
    assert any(
        "lists 3 path(s); the limit is 2" in warning for warning in report.warnings
    ), report.warnings


REQUIREMENTS_ORPHANED_PLAN = """# Plan

## Requirements
Some context about scope; not structured per ticket.

### Build a widget
Problem: there is no widget.

Acceptance criteria:
- [ ] works

Validation: `git --version`

### Ship a gadget
Problem: there is no gadget.

Acceptance criteria:
- [ ] works too

Validation: `git --version`
"""

REQUIREMENTS_FREE_PLAN = REQUIREMENTS_ORPHANED_PLAN.replace(
    "## Requirements\nSome context about scope; not structured per ticket.\n\n", ""
)


def test_skipped_requirements_section_warns_when_no_draft_covers(board: Path) -> None:
    plan = write_plan(board, REQUIREMENTS_ORPHANED_PLAN, "orphaned.md")
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], dry_run=True)

    assert any(
        "Requirements" in warning and "no draft covers" in warning
        for warning in report.warnings
    ), report.warnings


def test_skipped_requirements_warning_is_silent_without_a_requirements_section(
    board: Path,
) -> None:
    plan = write_plan(board, REQUIREMENTS_FREE_PLAN, "no-requirements.md")
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], dry_run=True)

    assert not any("Requirements" in warning for warning in report.warnings), report.warnings


def test_warnings_exit_zero_when_ingest_only_warns(board: Path, capsys) -> None:
    plan = write_plan(board, RADIUS_PLAN, "exit-zero.md")

    exit_code = main(["--project-root", str(board), "ingest", str(plan)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "[WARN]" in output
