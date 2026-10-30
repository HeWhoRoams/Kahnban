---
id: KB-023
title: Add the MIT licence with third-party notices
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
source_anchor: tickets/add-the-mit-licence-with-third-party-not
source_hash: 073cf3811063
validation_class: headless-verified
covers: [R10]
spec: SPEC-001
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