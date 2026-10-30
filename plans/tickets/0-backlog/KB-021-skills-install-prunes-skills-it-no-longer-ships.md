---
id: KB-021
title: skills install prunes skills it no longer ships
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-018]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/skills-install-prunes-skills-it-no-longe
source_hash: 4f3d40ac2061
validation_class: headless-verified
covers: [R8]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] a skill or agent the previous install wrote (per the lock) and no longer shipped is removed from each harness dir (test: `python -m pytest tests/test_skills_prune.py -q -k stale_removed`)
- [ ] a skill the install never wrote is left untouched (test: `python -m pytest tests/test_skills_prune.py -q -k user_skill_kept`)

## Blast radius
- `src/kahnban/skills.py`
- `tests/test_skills_prune.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skills_prune.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/skills-install-prunes-skills-it-no-longe