---
id: KB-033
title: Reject and escalate capture learnings
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-027]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/reject-and-escalate-capture-learnings
source_hash: 83df070b369a
validation_class: headless-verified
covers: [R20, R21]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] reject captures a learning naming the ticket and the reason (test: `python -m pytest tests/test_learning_capture.py -q -k reject_captures`)
- [ ] escalate captures a learning naming the ticket and the reason (test: `python -m pytest tests/test_learning_capture.py -q -k escalate_captures`)
- [ ] the same cause on two tickets clusters into one learning with two occurrences (test: `python -m pytest tests/test_learning_capture.py -q -k clusters`)
- [ ] when capture fails, reject and escalate still transition and print a warning (test: `python -m pytest tests/test_learning_capture.py -q -k capture_failure_nonfatal`)

## Blast radius
- `src/kahnban/core.py`
- `tests/test_learning_capture.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_learning_capture.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/reject-and-escalate-capture-learnings