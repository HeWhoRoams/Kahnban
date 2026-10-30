---
id: KB-027
title: Dispatch waits on unfinished dependencies
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-015]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/dispatch-waits-on-unfinished-dependencie
source_hash: 9313b916e454
validation_class: headless-verified
covers: [R13, R14]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] a backlog ticket listed before its unfinished dependency is never offered; the dependency is (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k dependent_waits`)
- [ ] a ticket with a missing dependency or on a cycle (self-dependency included) is never offered (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k missing_and_cycle_wait`)
- [ ] when only waiting tickets remain, next reports idle naming each one and its blocker: id, missing id or cycle (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k idle_names_blockers`)

## Blast radius
- `src/kahnban/dispatcher.py`
- `src/kahnban/core.py`
- `tests/test_dispatch_dependencies.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_dispatch_dependencies.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/dispatch-waits-on-unfinished-dependencie