---
id: KB-010
title: "The default worker command cannot finish a ticket headlessly: claude -p with acceptEdits is asked to approve git and kahnban commands. Allow the commands each role needs (allowedTools or project permission rules written by skills install) and prove it with the live test"
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-25
updated: 2026-10-25
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
---

## Problem

## Acceptance criteria

## Blast radius

## Implementation notes

## Validation
```
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-25 18:50 - created -> 0-backlog | captured