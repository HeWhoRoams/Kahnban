---
id: KB-009
title: The citadel portability smoke test (plan.md phase 4)
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-25
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: "human: smoke test done by hand (see Log); no engine change to prove"
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
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-29 - smoke run on a throwaway clone of C:\github\citadel (engine unchanged): init --prefix CIT, new, ready, claim --worktree, implement, verify -> 4-verifying all worked. Findings: (1) claim runs a git push to the clone origin, so a clone of a real repo must have its remote removed first (the push was rejected, nothing reached citadel); (2) ready refuses a blast radius with no file matching test_patterns (tools/ did not count, tests/ did). Not taken through the board: no engine change to prove. Clone left in the temp dir tmp.YajixPf3Wn.
- 2026-10-29 19:29 - escalated to a human: smoke test done by hand (see Log); no engine change to prove
