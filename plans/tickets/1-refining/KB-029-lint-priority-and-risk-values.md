---
id: KB-029
title: Lint priority and risk values
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-028]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-priority-and-risk-values
source_hash: 9e29761fffb6
validation_class: headless-verified
covers: [R16]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] the ticket template documents priority: normal and risk: medium (test: `python -m pytest tests/test_lint_priority_risk.py -q -k template_fields`)
- [ ] an invalid priority or risk value is a lint warning, not an error (test: `python -m pytest tests/test_lint_priority_risk.py -q -k invalid_value_warns`)

## Blast radius
- `src/kahnban/linter.py`
- `src/kahnban/templates/ticket.md`
- `tests/test_lint_priority_risk.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_priority_risk.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-priority-and-risk-values
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement