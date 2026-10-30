---
id: KB-019
title: Ship the kahnban-comment-sicko helper agent
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-018]
blocked_on: "human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done."
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/ship-the-kahnban-comment-sicko-helper-ag
source_hash: 4d50f9669582
validation_class: headless-verified
covers: [R6]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] kahnban skills install for the claude harness writes .claude/agents/kahnban-comment-sicko.md from pstack's comment-sicko (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k agent_installed`)
- [ ] kb-no-comments spawns subagent_type kahnban-comment-sicko (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k skill_spawns_agent`)
- [ ] the agent's provenance names cursor/plugins at c742dd6 (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k agent_provenance`)

## Blast radius
- `src/kahnban/harnesses.py`
- `src/kahnban/templates/agents/comment-sicko.md`
- `.claude/agents/kahnban-comment-sicko.md`
- `src/kahnban/templates/skills/kb-no-comments/skill.md`
- `.agents/skills/kb-no-comments/skill.md`
- `.claude/skills/kb-no-comments/skill.md`
- `adapters/skills/kb-no-comments/skill.md`
- `src/kahnban/templates/provenance.json`
- `.agents/skills.lock.json`
- `tests/test_comment_sicko_agent.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_comment_sicko_agent.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ship-the-kahnban-comment-sicko-helper-ag
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.