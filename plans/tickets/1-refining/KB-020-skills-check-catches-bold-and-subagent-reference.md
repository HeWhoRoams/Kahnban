---
id: KB-020
title: skills check catches bold and subagent references
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-019]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/skills-check-catches-bold-and-subagent-r
source_hash: 534cee9a8b72
validation_class: headless-verified
covers: [R3]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] a '**name** skill' reference to an unshipped skill is reported (test: `python -m pytest tests/test_skills_check_refs.py -q -k bold_skill_ref`)
- [ ] a '**name** principle skill' reference is resolved to kb-principle-name and reported when missing (test: `python -m pytest tests/test_skills_check_refs.py -q -k bold_principle_ref`)
- [ ] a subagent_type: "name" reference to an unshipped agent is reported (test: `python -m pytest tests/test_skills_check_refs.py -q -k subagent_ref`)
- [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)

## Blast radius
- `src/kahnban/skills_check.py`
- `tests/test_skills_check_refs.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skills_check_refs.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/skills-check-catches-bold-and-subagent-r
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement