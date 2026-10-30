---
id: KB-025
title: lint help names the real rule range
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-help-names-the-real-rule-range
source_hash: bb144b599d40
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] kahnban lint --help names the first and last rule ids of the linter's rule table (test: `python -m pytest tests/test_lint_help.py -q -k help_range_from_table`)

## Blast radius
- `src/kahnban/cli.py`
- `tests/test_lint_help.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_help.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-help-names-the-real-rule-range
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement