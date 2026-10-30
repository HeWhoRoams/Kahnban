---
id: KB-022
title: Upstream installs never overwrite kb- skills
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-021]
blocked_on: "human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done."
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/upstream-installs-never-overwrite-kb-ski
source_hash: 84caad18feec
validation_class: headless-verified
covers: [R9]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] installing with --source mattpocock (npx stubbed) leaves every kb- skill byte-identical (test: `python -m pytest tests/test_skills_sources.py -q -k kb_skills_untouched`)

## Blast radius
- `src/kahnban/skills.py`
- `tests/test_skills_sources.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skills_sources.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/upstream-installs-never-overwrite-kb-ski
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.