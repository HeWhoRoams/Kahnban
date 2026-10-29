---
id: KB-014
title: "Core clean-up: one list of approval fields to clear, rename _signature_problem"
status: backlog
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
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
---

## Problem
## R4: Core clean-ups (findings 8, 10)

Files: `src/kahnban/core.py`, `tests/test_reviewer_keys.py` (name use only).

- One module-level `_APPROVAL_FIELDS` mapping of the fields to blank, used by `verify` and `reject`.
- Rename `_signature_problem` to `_approval_problem` and update its docstring to say it checks both the
  engine HMAC and the reviewer seal.
- No behaviour change, so no new test; the full suite is the check.


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria

## Blast radius

## Implementation notes

## Validation
```
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog