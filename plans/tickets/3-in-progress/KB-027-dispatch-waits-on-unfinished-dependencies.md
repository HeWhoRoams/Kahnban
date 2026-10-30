---
id: KB-027
title: Dispatch waits on unfinished dependencies
status: in-progress
owner: coder-agent
branch: ticket/KB-027
worktree: .worktrees/KB-027
created: 2026-10-29
updated: 2026-10-30
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/dispatch-waits-on-unfinished-dependencie
source_hash: bcc76f9923f4
validation_class: headless-verified
covers: [R13, R14]
spec: SPEC-001
contract_hash: 599e575b6942657e
contract_sig: c43d62703cb93f6bae2f1df3cd6b0831fbf1874888cdb9563dd7753317b55b9b
confirmed: ""
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
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - re-ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/dispatch-waits-on-unfinished-dependencie (source_hash bcc76f9923f4)
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 599e575b6942657e
- 2026-10-30 00:25 - claimed by coder-agent -> 3-in-progress