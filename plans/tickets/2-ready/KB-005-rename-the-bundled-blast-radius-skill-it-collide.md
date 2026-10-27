---
id: KB-005
title: "Rename the bundled blast-radius skill: it collides with the ticket field of the same name"
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-25
updated: 2026-10-26
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 1ef52016b0f3a7a1
confirmed: ""
---

## Problem
The bundled skill `blast-radius` shares its name with the ticket field `## Blast radius`, so `/blast-radius` and the field are easy to
confuse (the field is the files a coder may touch; the skill is a method for finding what a change breaks elsewhere). Rename the
skill to `change-impact` (decided with the user, 2026-10-26) everywhere it is shipped: the bundle, `adapters/skills`, `.agents/skills` and the lock.
Mentions of the ticket field stay as they are. The rename needs more files than the usual limit of 3, so `max_blast_radius_files`
is raised for this one ticket and restored when it is done.

## Acceptance criteria
- [ ] the bundled skills include `change-impact` and no longer include `blast-radius` (test: `python -m pytest tests/test_skills_sources.py -q -k change_impact`)
- [ ] `/blast-radius` in the factory-mode skill now reads `/change-impact`, and `kahnban skills check` passes (test: `python -m pytest tests/test_skills_sources.py -q -k change_impact_is_referenced`)

## Blast radius
- `src/kahnban/templates/skills/blast-radius/SKILL.md`
- `src/kahnban/templates/skills/change-impact/SKILL.md`
- `src/kahnban/templates/skills/factory-mode/SKILL.md`
- `adapters/skills/blast-radius/SKILL.md`
- `adapters/skills/change-impact/SKILL.md`
- `adapters/skills/factory-mode/SKILL.md`
- `.agents/skills/blast-radius/SKILL.md`
- `.agents/skills/change-impact/SKILL.md`
- `.agents/skills/factory-mode/SKILL.md`
- `.agents/skills.lock.json`
- `tests/test_skills_sources.py`

## Implementation notes
- Do it in the bundle first (`git mv`, then `name:` and the `# Blast radius` heading in SKILL.md, and the factory-mode line), then copy the same files to `adapters/skills` and `.agents/skills`, then `kahnban skills lock`.
- Leave the other skills' wording about the ticket's blast radius alone.
- Tests: read the bundled skill names from `src/kahnban/templates/skills` and check factory-mode's text.

## Validation
```
python -m pytest tests/test_skills_sources.py -q
python -m kahnban skills check
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 22:25 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 22:25 - ready gate passed -> 2-ready | contract 1ef52016b0f3a7a1