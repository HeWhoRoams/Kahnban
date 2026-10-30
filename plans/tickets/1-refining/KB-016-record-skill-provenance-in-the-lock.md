---
id: KB-016
title: Record skill provenance in the lock
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-015]
blocked_on: "human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done."
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/record-skill-provenance-in-the-lock
source_hash: a0486282ca91
validation_class: headless-verified
covers: [R7]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] every shipped skill and agent has a provenance entry with source repository, upstream path and commit, or source kahnban for native ones (test: `python -m pytest tests/test_skill_provenance.py -q -k every_skill_has_provenance`)
- [ ] writing the lock copies each provenance entry into .agents/skills.lock.json (test: `python -m pytest tests/test_skill_provenance.py -q -k lock_records_provenance`)
- [ ] lock_problems reports a shipped skill with no provenance entry (test: `python -m pytest tests/test_skill_provenance.py -q -k missing_provenance_reported`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/templates/provenance.json`
- `.agents/skills.lock.json`
- `tests/test_skill_provenance.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skill_provenance.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/record-skill-provenance-in-the-lock
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.