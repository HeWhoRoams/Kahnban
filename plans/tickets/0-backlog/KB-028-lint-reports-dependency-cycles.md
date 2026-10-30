---
id: KB-028
title: Lint reports dependency cycles
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-027]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-reports-dependency-cycles
source_hash: b067ce6bece5
validation_class: headless-verified
covers: [R15]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] kahnban lint reports a depends_on cycle under a new rule id, naming the cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k cycle_reported`)
- [ ] a self-dependency is reported as a cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k self_dependency`)

## Blast radius
- `src/kahnban/linter.py`
- `tests/test_lint_cycles.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_cycles.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-reports-dependency-cycles