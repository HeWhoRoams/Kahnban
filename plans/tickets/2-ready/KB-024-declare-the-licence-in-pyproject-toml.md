---
id: KB-024
title: Declare the licence in pyproject.toml
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-023]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/declare-the-licence-in-pyproject-toml
source_hash: 1e78674ef093
validation_class: headless-verified
covers: [R10]
spec: SPEC-001
contract_hash: df3650d17f2aa8d7
contract_sig: 57be048441e09f8ae49b817c5dc454e17af37cf2808913789b68c93aa45c1f28
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] pyproject.toml declares the MIT licence and its license file (test: `python -m pytest tests/test_license.py -q -k pyproject_declares_license`)

## Blast radius
- `pyproject.toml`
- `tests/test_license.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_license.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/declare-the-licence-in-pyproject-toml
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-29 22:31 - unblocked: dependencies are in 5-done (supervisor)
- 2026-10-29 23:03 - ready gate passed -> 2-ready | contract df3650d17f2aa8d7