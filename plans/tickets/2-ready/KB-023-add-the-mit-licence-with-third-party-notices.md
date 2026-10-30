---
id: KB-023
title: Add the MIT licence with third-party notices
status: ready
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
source_anchor: tickets/add-the-mit-licence-with-third-party-not
source_hash: 073cf3811063
validation_class: headless-verified
covers: [R10]
spec: SPEC-001
contract_hash: 50939535bb7426aa
contract_sig: 3645a1999ae8009dd4115020cff15e0e964463a62aae6c2860a69c0997546e13
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] LICENSE is the MIT licence naming Tim Niles (test: `python -m pytest tests/test_license.py -q -k mit_license`)
- [ ] THIRD_PARTY_NOTICES.md reproduces the MIT notices of cursor/plugins (pstack) and mattpocock/skills (test: `python -m pytest tests/test_license.py -q -k third_party_notices`)

## Blast radius
- `license`
- `third_party_notices.md`
- `tests/test_license.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_license.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/add-the-mit-licence-with-third-party-not
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 50939535bb7426aa