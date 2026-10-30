---
id: KB-030
title: "Dispatch by priority, risk and unblocking"
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-027]
blocked_on: "human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done."
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/dispatch-by-priority-risk-and-unblocking
source_hash: d91af5f77b14
validation_class: headless-verified
covers: [R16, R17]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] intake and claim candidates are ordered by priority, then risk, then transitive dependents (most first), then id (test: `python -m pytest tests/test_dispatch_order.py -q -k sort_order`)
- [ ] a missing or invalid priority/risk sorts as normal/medium (test: `python -m pytest tests/test_dispatch_order.py -q -k defaults`)
- [ ] ties fall back to ticket id deterministically (test: `python -m pytest tests/test_dispatch_order.py -q -k id_tiebreak`)

## Blast radius
- `src/kahnban/dispatcher.py`
- `tests/test_dispatch_order.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_dispatch_order.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/dispatch-by-priority-risk-and-unblocking
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.