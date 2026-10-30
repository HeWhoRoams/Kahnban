---
id: KB-026
title: Status docs stop making stale claims
status: backlog
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
source_anchor: tickets/status-docs-stop-making-stale-claims
source_hash: 01ba13816e3a
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
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