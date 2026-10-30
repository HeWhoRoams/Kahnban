---
id: KB-026
title: Status docs stop making stale claims
status: in-progress
owner: coder-agent
branch: ticket/KB-026
worktree: .worktrees/KB-026
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/status-docs-stop-making-stale-claims
source_hash: 01ba13816e3a
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
contract_hash: 92f5edd88d033004
contract_sig: 6f9e08b42a98bd62d77e120053e695f134b9fc7a7392107aa37feda229bd17d0
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] neither doc states a hard-coded test count (test: `python -m pytest tests/test_status_docs.py -q -k no_test_count`)
- [ ] neither doc describes kahnban run as sequential or one ticket at a time (test: `python -m pytest tests/test_status_docs.py -q -k no_sequential_claim`)

## Blast radius
- `implementation_status.md`
- `next_steps.md`
- `tests/test_status_docs.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_status_docs.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/status-docs-stop-making-stale-claims
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 92f5edd88d033004
- 2026-10-29 22:43 - claimed by coder-agent -> 3-in-progress