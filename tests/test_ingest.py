"""Entry points: ideation capture, plan ingestion, per-file feature specs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kahnban import core, frontmatter, ingest, linter
from conftest import git, write_ticket

PLAN = """# Widget Programme

Some framing prose that belongs to no ticket.

## Phase 1 - foundations

### Add the widget module
**Why:** there is no widget and the panel cannot render without one.
**Acceptance:**
- [ ] widget() returns a Widget
- [ ] the panel renders it
**Files:** `src/widget.py`, `tests/widget_test.py`
**Validation:** `pytest tests/widget_test.py`

### Wire the widget into the panel
Problem: the panel has no slot for the widget.

Depends on: Add the widget module

Acceptance criteria:
- [ ] panel exposes a widget slot

Files:
- `src/panel.py`

Validation:
```
pytest tests/panel_test.py
```

## Phase 2 - polish

### Style the widget
No detail yet.
"""


def commit_board(repo: Path, message: str = "board fixture") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def write_plan(repo: Path, text: str = PLAN, name: str = "plans/PLAN.md") -> Path:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    commit_board(repo, "add plan document")
    return path


def fields_of(path: Path) -> dict:
    return frontmatter.parse(core.read_text(path))[0]


def body_of(path: Path) -> str:
    return frontmatter.parse(core.read_text(path))[1]


# --- parsing ----------------------------------------------------------------


def test_parse_document_finds_one_draft_per_work_section() -> None:
    drafts, warnings = ingest.parse_document(PLAN, source_doc="plans/PLAN.md")

    assert [draft.title for draft in drafts] == [
        "Add the widget module",
        "Wire the widget into the panel",
        "Style the widget",
    ]
    assert warnings == []


def test_inline_labels_are_mapped_to_ticket_fields() -> None:
    drafts, _ = ingest.parse_document(PLAN, source_doc="plans/PLAN.md")
    first = drafts[0]

    assert "no widget" in first.problem
    assert first.acceptance == ["widget() returns a Widget", "the panel renders it"]
    assert first.blast_radius == ["src/widget.py", "tests/widget_test.py"]
    assert first.validation == "pytest tests/widget_test.py"


def test_plain_labels_fenced_validation_and_dependencies_are_parsed() -> None:
    drafts, _ = ingest.parse_document(PLAN, source_doc="plans/PLAN.md")
    second = drafts[1]

    assert "no slot" in second.problem
    assert second.acceptance == ["panel exposes a widget slot"]
    assert second.blast_radius == ["src/panel.py"]
    assert second.validation == "pytest tests/panel_test.py"
    assert second.unresolved_dependencies == ["Add the widget module"]


def test_anchors_carry_the_heading_path_and_a_content_hash() -> None:
    drafts, _ = ingest.parse_document(PLAN, source_doc="plans/PLAN.md")

    assert drafts[0].source_anchor == "phase-1-foundations/add-the-widget-module"
    assert drafts[2].source_anchor == "phase-2-polish/style-the-widget"
    assert len(drafts[0].source_hash) == 12
    assert drafts[0].source_hash != drafts[1].source_hash


def test_heading_level_is_auto_detected_past_alias_subsections() -> None:
    plan = """# Feature
## Build the thing
### Problem
It is missing.
### Acceptance criteria
- [ ] it exists
## Build the other thing
### Problem
Also missing.
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert [draft.title for draft in drafts] == ["Build the thing", "Build the other thing"]
    assert drafts[0].problem == "It is missing."
    assert drafts[0].acceptance == ["it exists"]


def test_explicit_heading_level_overrides_detection() -> None:
    drafts, _ = ingest.parse_document(
        PLAN, source_doc="plan.md", options=ingest.IngestOptions(heading_level=2)
    )

    assert [draft.title for draft in drafts] == ["foundations", "polish"]


def test_section_scoping_ingests_one_subtree() -> None:
    drafts, _ = ingest.parse_document(
        PLAN, source_doc="plan.md", options=ingest.IngestOptions(section="Phase 2")
    )

    assert [draft.title for draft in drafts] == ["Style the widget"]


def test_unknown_section_is_an_ingest_error() -> None:
    with pytest.raises(ingest.IngestError, match="no heading matching"):
        ingest.parse_document(
            PLAN, source_doc="plan.md", options=ingest.IngestOptions(section="Phase 9")
        )


def test_headings_inside_fenced_blocks_are_not_sections() -> None:
    plan = """# Plan
## Real ticket
Validation:
```bash
# this comment is not a heading
## neither is this
pytest -q
```
## Second real ticket
Nothing here.
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert [draft.title for draft in drafts] == ["Real ticket", "Second real ticket"]
    assert drafts[0].validation == "# this comment is not a heading\n## neither is this\npytest -q"


def test_enumerated_headings_lose_their_numbering_in_titles() -> None:
    plan = """# Plan
## 1. Do the first thing
## Phase 2 - do the second thing
## 3.1) Do the third thing
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert [draft.title for draft in drafts] == [
        "Do the first thing",
        "do the second thing",
        "Do the third thing",
    ]


def test_unmapped_subsections_are_preserved_in_notes() -> None:
    plan = """# Plan
## Ticket one
### Risks
The cache may be cold.
### Acceptance criteria
- [ ] warms the cache
## Ticket two
Nothing.
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert "### Risks" in drafts[0].notes
    assert "cache may be cold" in drafts[0].notes
    assert drafts[0].acceptance == ["warms the cache"]


def test_bare_checkboxes_become_acceptance_criteria() -> None:
    plan = """# Plan
## Ticket one
Make the thing work.
- [ ] it works
- [x] someone already claimed this was done
## Ticket two
Nothing.
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert drafts[0].acceptance == [
        "it works",
        "someone already claimed this was done",
    ]
    assert drafts[0].problem == "Make the thing work."


def test_frontmatter_on_the_plan_document_is_ignored() -> None:
    plan = "---\ntitle: My plan\n---\n\n# Plan\n## Ticket one\nx\n## Ticket two\ny\n"

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert [draft.title for draft in drafts] == ["Ticket one", "Ticket two"]


def test_prose_blast_radius_entries_are_reported_not_invented() -> None:
    plan = """# Plan
## Ticket one
Files: the whole UI layer
## Ticket two
Files: `src/real.py`
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert drafts[0].blast_radius == []
    assert "unparsed blast-radius entry: the whole UI layer" in drafts[0].notes
    assert drafts[1].blast_radius == ["src/real.py"]


def test_a_document_with_no_work_sections_becomes_one_ticket() -> None:
    plan = "# Single feature\n## Problem\nIt is missing.\n## Acceptance criteria\n- [ ] exists\n"

    drafts, _ = ingest.parse_document(plan, source_doc="spec.md")

    assert [draft.title for draft in drafts] == ["Single feature"]
    assert drafts[0].problem == "It is missing."


def test_per_file_mode_keeps_a_document_as_one_ticket() -> None:
    drafts, _ = ingest.parse_document(
        PLAN, source_doc="plans/PLAN.md", options=ingest.IngestOptions(per_file=True)
    )

    assert len(drafts) == 1
    assert drafts[0].title == "Widget Programme"
    assert drafts[0].source_anchor == ingest.WHOLE_DOCUMENT_ANCHOR


def test_duplicate_section_titles_get_distinct_anchors() -> None:
    plan = """# Plan
## Phase 1
### Shared name
a
## Phase 1
### Shared name
b
"""

    drafts, warnings = ingest.parse_document(plan, source_doc="plan.md")

    anchors = [draft.source_anchor for draft in drafts]
    assert len(set(anchors)) == len(anchors)
    assert any("duplicate section anchor" in warning for warning in warnings)


# --- writing to the board ---------------------------------------------------


def test_ingest_creates_tickets_in_one_commit(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    before = git(board, "rev-list", "--count", "HEAD").stdout.strip()

    [report] = ingest.ingest(config, [plan])

    assert [result.ticket_id for result in report.created] == [
        "TST-001",
        "TST-002",
        "TST-003",
    ]
    after = git(board, "rev-list", "--count", "HEAD").stdout.strip()
    assert int(after) - int(before) == 1
    subject = git(board, "log", "-1", "--pretty=%s").stdout.strip()
    assert subject == "kanban: ingest 3 ticket(s) from plans/PLAN.md"
    assert core.find_ticket(config, "TST-001").column == "0-backlog"
    assert linter.lint(config).violations == []


def test_ingested_tickets_carry_content_and_provenance(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    ingest.ingest(config, [plan])

    ticket = core.find_ticket(config, "TST-001")
    fields = fields_of(ticket.path)
    body = body_of(ticket.path)
    assert fields["title"] == "Add the widget module"
    assert fields["source_doc"] == "plans/PLAN.md"
    assert fields["source_anchor"] == "phase-1-foundations/add-the-widget-module"
    assert len(str(fields["source_hash"])) == 12
    assert core.checkboxes(body) == (0, 2)
    assert core.parse_blast_radius(body) == ["src/widget.py", "tests/widget_test.py"]
    assert core.validation_command(config, body) == "pytest tests/widget_test.py"
    assert "ingested from plans/PLAN.md#" in core.section(body, "Log")


def test_acceptance_criteria_are_never_ingested_pre_checked(board: Path) -> None:
    plan = write_plan(
        board,
        "# Plan\n## Ticket one\n- [x] the plan claims this is already done\n"
        "## Ticket two\n- [ ] honest\n",
    )
    config = core.load_config(board)

    ingest.ingest(config, [plan])

    body = body_of(core.find_ticket(config, "TST-001").path)
    assert core.checkboxes(body) == (0, 1)
    assert "the plan claims this is already done" in body


def test_dependencies_between_plan_sections_are_wired_to_ids(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    ingest.ingest(config, [plan])

    assert fields_of(core.find_ticket(config, "TST-002").path)["depends_on"] == [
        "TST-001"
    ]
    assert fields_of(core.find_ticket(config, "TST-001").path)["depends_on"] == []


def test_chain_mode_makes_a_sequential_pipeline(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    ingest.ingest(config, [plan], options=ingest.IngestOptions(chain=True))

    assert fields_of(core.find_ticket(config, "TST-002").path)["depends_on"] == ["TST-001"]
    assert fields_of(core.find_ticket(config, "TST-003").path)["depends_on"] == ["TST-002"]


def test_unresolvable_dependencies_land_in_blocked_on(board: Path) -> None:
    plan = write_plan(
        board,
        "# Plan\n## Ticket one\nDepends on: Some ticket that does not exist\n"
        "## Ticket two\nfine\n",
    )
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan])

    fields = fields_of(core.find_ticket(config, "TST-001").path)
    assert "unresolved dependency" in str(fields["blocked_on"])
    assert fields["depends_on"] == []
    assert any("unresolved dependencies" in warning for warning in report.warnings)
    # The refinement gate refuses while the reference is unresolved.
    core.move(config, "TST-001", "1-refining", reason="refining")
    with pytest.raises(core.GateError, match="blocked_on"):
        core.ready(config, "TST-001")


def test_dependencies_can_reference_tickets_already_on_the_board(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path, "5-done", "TST-001", "existing", title="Existing groundwork"
    )
    commit_board(board)
    plan = write_plan(
        board, "# Plan\n## New work\nDepends on: Existing groundwork\n## Other work\nx\n"
    )

    ingest.ingest(core.load_config(board), [plan])

    assert fields_of(core.find_ticket(config, "TST-002").path)["depends_on"] == ["TST-001"]


def test_dry_run_writes_nothing(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    head = git(board, "rev-parse", "HEAD").stdout.strip()

    [report] = ingest.ingest(config, [plan], dry_run=True)

    assert report.dry_run
    assert len(report.drafts) == 3
    assert report.created == []
    assert git(board, "rev-parse", "HEAD").stdout.strip() == head
    assert core.iter_tickets(config) == []
    rendered = ingest.render_report([report])
    assert "[DRY-RUN]" in rendered
    assert "would create: Add the widget module" in rendered
    assert rendered.isascii()


# --- idempotency ------------------------------------------------------------


def test_re_ingesting_an_unchanged_plan_creates_nothing(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    head = git(board, "rev-parse", "HEAD").stdout.strip()

    [report] = ingest.ingest(config, [plan])

    assert report.created == []
    assert len(report.unchanged) == 3
    assert git(board, "rev-parse", "HEAD").stdout.strip() == head
    assert len(core.iter_tickets(config)) == 3


def test_a_plan_that_grew_only_ingests_the_new_sections(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])

    plan.write_text(
        PLAN + "\n### Document the widget\nNew section.\n", encoding="utf-8", newline="\n"
    )
    commit_board(board, "extend the plan")

    [report] = ingest.ingest(config, [plan])

    assert [result.ticket_id for result in report.created] == ["TST-004"]
    assert len(report.unchanged) == 3
    assert fields_of(core.find_ticket(config, "TST-004").path)["title"] == (
        "Document the widget"
    )


def test_a_changed_section_is_reported_as_drift_not_duplicated(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    plan.write_text(
        PLAN.replace("the panel renders it", "the panel renders it twice"),
        encoding="utf-8",
        newline="\n",
    )
    commit_board(board, "amend the plan")

    [report] = ingest.ingest(config, [plan])

    assert report.created == []
    assert report.drifted == [
        ("phase-1-foundations/add-the-widget-module", "TST-001")
    ]
    assert len(core.iter_tickets(config)) == 3
    assert "source changed for TST-001" in ingest.render_report([report])


def test_update_refreshes_an_unstarted_ticket_and_keeps_its_log(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    created = fields_of(core.find_ticket(config, "TST-001").path)["created"]
    plan.write_text(
        PLAN.replace("the panel renders it", "the panel renders it twice"),
        encoding="utf-8",
        newline="\n",
    )
    commit_board(board, "amend the plan")

    [report] = ingest.ingest(config, [plan], options=ingest.IngestOptions(update=True))

    assert [result.ticket_id for result in report.updated] == ["TST-001"]
    assert report.drifted == []
    ticket = core.find_ticket(config, "TST-001")
    body = body_of(ticket.path)
    assert "the panel renders it twice" in body
    log = core.section(body, "Log")
    assert "ingested from plans/PLAN.md#" in log  # original entry survives
    assert "re-ingested from plans/PLAN.md#" in log
    assert fields_of(ticket.path)["created"] == created
    assert core.checkboxes(body) == (0, 2)


def test_update_refuses_to_rewrite_a_claimed_ticket(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    core.move(config, "TST-001", "2-ready", reason="ready for the test")
    core.claim(config, "TST-001", "agent-a", create_worktree=False)
    plan.write_text(
        PLAN.replace("the panel renders it", "the panel renders it twice"),
        encoding="utf-8",
        newline="\n",
    )
    commit_board(board, "amend the plan")

    [report] = ingest.ingest(config, [plan], options=ingest.IngestOptions(update=True))

    assert report.updated == []
    assert report.drifted == [("phase-1-foundations/add-the-widget-module", "TST-001")]
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"


def test_bl17_catches_two_tickets_claiming_one_plan_section(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    original = core.find_ticket(config, "TST-001")
    clone = config.board_path / "0-backlog" / "TST-099-hand-copied.md"
    clone.write_text(
        core.read_text(original.path).replace("id: TST-001", "id: TST-099"),
        encoding="utf-8",
        newline="\n",
    )
    commit_board(board, "hand-copy a ticket")

    result = linter.lint(config)

    provenance = [f for f in result.violations if f.rule == "BL17"]
    assert provenance, [f.render() for f in result.violations]
    assert "TST-001" in provenance[0].message and "TST-099" in provenance[0].message


def test_bl17_warns_when_the_source_document_disappears(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan])
    plan.unlink()
    commit_board(board, "delete the plan")

    result = linter.lint(config)

    warnings = [f for f in result.warnings if f.rule == "BL17"]
    assert warnings
    assert "no longer exists" in warnings[0].message


# --- promotion --------------------------------------------------------------


def test_ready_promotes_only_sections_that_satisfy_the_gate(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], options=ingest.IngestOptions(promote=True))

    # TST-001 is fully specified; TST-002 depends on it; TST-003 has no detail.
    assert report.promoted == ["TST-001"]
    assert core.find_ticket(config, "TST-001").column == "2-ready"
    not_promoted = dict(report.not_promoted)
    assert "TST-002" in not_promoted and "TST-001" in not_promoted["TST-002"]
    assert "TST-003" in not_promoted
    assert "Blast radius" in not_promoted["TST-003"]
    assert core.find_ticket(config, "TST-003").column == "1-refining"
    assert linter.lint(config).violations == []


def test_a_promoted_ticket_can_be_claimed_immediately(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)
    ingest.ingest(config, [plan], options=ingest.IngestOptions(promote=True))

    result = core.claim(config, "TST-001", "agent-a", create_worktree=False)

    assert result.to_column == "3-in-progress"


# --- capture ----------------------------------------------------------------


def test_capture_writes_one_ticket_per_idea_in_one_commit(board: Path) -> None:
    config = core.load_config(board)
    before = int(git(board, "rev-list", "--count", "HEAD").stdout.strip())

    report = ingest.capture(config, ["Try a new cache", "Rework the loader"])

    assert [result.ticket_id for result in report.created] == ["TST-001", "TST-002"]
    after = int(git(board, "rev-list", "--count", "HEAD").stdout.strip())
    assert after - before == 1
    assert fields_of(core.find_ticket(config, "TST-001").path)["title"] == (
        "Try a new cache"
    )
    assert "captured" in core.section(body_of(core.find_ticket(config, "TST-001").path), "Log")
    assert linter.lint(config).violations == []


def test_capture_dry_run_and_empty_input(board: Path) -> None:
    config = core.load_config(board)

    preview = ingest.capture(config, ["An idea"], dry_run=True)
    assert preview.created == [] and len(preview.drafts) == 1
    assert core.iter_tickets(config) == []

    empty = ingest.capture(config, ["  "])
    assert empty.created == []
    assert "no ideas to capture" in empty.warnings


# --- multiple documents -----------------------------------------------------


def test_ingesting_several_specs_per_file_keeps_them_separate(board: Path) -> None:
    first = write_plan(board, "# Cache warmer\n## Problem\nCold starts.\n", "specs/a.md")
    second = write_plan(board, "# Loader rework\n## Problem\nSlow.\n", "specs/b.md")
    config = core.load_config(board)

    reports = ingest.ingest(
        config, [first, second], options=ingest.IngestOptions(per_file=True)
    )

    assert [r.created[0].ticket_id for r in reports] == ["TST-001", "TST-002"]
    titles = {
        fields_of(core.find_ticket(config, ticket_id).path)["title"]
        for ticket_id in ("TST-001", "TST-002")
    }
    assert titles == {"Cache warmer", "Loader rework"}
    documents = {
        fields_of(core.find_ticket(config, ticket_id).path)["source_doc"]
        for ticket_id in ("TST-001", "TST-002")
    }
    assert documents == {"specs/a.md", "specs/b.md"}
    assert linter.lint(config).violations == []


def test_missing_plan_document_is_an_ingest_error(board: Path) -> None:
    with pytest.raises(ingest.IngestError, match="not found"):
        ingest.ingest(core.load_config(board), [board / "plans" / "nope.md"])


def test_report_payload_is_json_serializable(board: Path) -> None:
    plan = write_plan(board)
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], dry_run=True)

    payload = json.loads(json.dumps(report.as_dict()))
    assert payload["dry_run"] is True
    assert payload["drafts"][0]["title"] == "Add the widget module"
    assert payload["drafts"][0]["acceptance"] == 2


# --- robustness on real-world plan documents --------------------------------


def test_section_matching_tolerates_dashes_and_case() -> None:
    plan = "# Doc\n## Phase 1 — Engine Implementation\n### Do the thing\nx\n"

    for query in (
        "Phase 1 - Engine Implementation",
        "phase 1 — engine implementation",
        "Phase 1-Engine Implementation",
    ):
        drafts, _ = ingest.parse_document(
            plan, source_doc="plan.md", options=ingest.IngestOptions(section=query)
        )
        assert [draft.title for draft in drafts] == ["Do the thing"], query


def test_report_rendering_survives_a_plan_containing_emoji(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = write_plan(
        board, "# Doc\n## ✅ Shipped work\nx\n## ⏳ Pending work\ny\n"
    )
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan], dry_run=True)
    rendered = ingest.render_report([report])

    # The console rendering is downgraded to what stdout accepts; the tickets
    # themselves keep the original text.
    rendered.encode(getattr(__import__("sys").stdout, "encoding", None) or "utf-8")
    assert "Shipped work" in rendered
    [written] = ingest.ingest(config, [plan])
    stored = core.read_text(written.created[0].path)
    assert "✅" in stored


# --- blocked_on ---------------------------------------------------------


def test_blocked_on_label_is_recognized_as_a_heading_and_inline_form() -> None:
    plan = """# Plan
## Ticket one
Blocked on: waiting on a tagged release before this is safe
## Ticket two
### Blocked on
External API key has not been provisioned yet.
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")

    assert drafts[0].blocked_on == (
        "waiting on a tagged release before this is safe"
    )
    assert drafts[1].blocked_on == "External API key has not been provisioned yet."


def test_blocked_on_is_distinct_from_blocked_by_dependency_references() -> None:
    """'Blocked by' names a ticket (depends_on); 'Blocked on' is free text."""
    plan = """# Plan
## Ticket one
x
## Ticket two
Blocked by: Ticket one
Blocked on: an unrelated external approval
"""

    drafts, _ = ingest.parse_document(plan, source_doc="plan.md")
    second = drafts[1]

    assert second.unresolved_dependencies == ["Ticket one"]
    assert second.blocked_on == "an unrelated external approval"


def test_blocked_on_survives_ingest_and_gates_readiness(board: Path) -> None:
    plan = write_plan(
        board,
        "# Plan\n## Ticket one\nBlocked on: no tagged release has shipped yet\n"
        "**Acceptance:**\n- [ ] a\n**Files:** `src/a.py`\n**Validation:** `git --version`\n",
    )
    config = core.load_config(board)

    ingest.ingest(config, [plan])

    ticket = core.find_ticket(config, "TST-001")
    assert fields_of(ticket.path)["blocked_on"] == "no tagged release has shipped yet"
    core.move(config, "TST-001", "1-refining", reason="refining")
    with pytest.raises(core.GateError, match="blocked_on is set"):
        core.ready(config, "TST-001")


def test_explicit_blocked_on_combines_with_an_unresolved_dependency_not_lost(
    board: Path,
) -> None:
    """An unresolved depends_on reference must not silently erase an explicit
    blocked_on label parsed from the same section."""
    plan = write_plan(
        board,
        "# Plan\n## Ticket one\n"
        "Blocked on: owner sign-off pending\n"
        "Depends on: Some ticket that does not exist\n",
    )
    config = core.load_config(board)

    [report] = ingest.ingest(config, [plan])

    fields = fields_of(core.find_ticket(config, "TST-001").path)
    assert "owner sign-off pending" in str(fields["blocked_on"])
    assert "unresolved dependency" in str(fields["blocked_on"])
    assert any("unresolved dependencies" in warning for warning in report.warnings)


def test_blocked_on_alias_is_configurable(board: Path) -> None:
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["ingest"] = {"section_aliases": {"blocked_on": ["pending on"]}}
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    plan = write_plan(
        board, "# Plan\n## Ticket one\nPending on: a licensing decision\n"
    )
    config = core.load_config(board)

    ingest.ingest(config, [plan], options=ingest.options_for(config))

    fields = fields_of(core.find_ticket(config, "TST-001").path)
    assert fields["blocked_on"] == "a licensing decision"
