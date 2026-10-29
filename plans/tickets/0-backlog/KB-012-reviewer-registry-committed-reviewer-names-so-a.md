---
id: KB-012
title: "Reviewer registry: committed reviewer names so a missing key dir refuses, and a corrupt reviewer file gives a clear error"
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
## R2: Reviewer registry robustness (findings 5, 6)

Files: `src/kahnban/trust.py`, `src/kahnban/cli.py`, `tests/test_reviewer_keys.py`.

Decision needed (finding 5): the registry lives in the user key directory, so a checkout on another
machine sees no reviewers and the check silently turns off.

- Recommended: `reviewers add` also writes the reviewer's name (never the key) to a committed
  `plans/reviewers.json`. `reviewer_problem` treats a non-empty file as "reviewers required" and refuses
  with "reviewer 'X' has no key on this machine; run 'kahnban reviewers add X' here" when the key is missing.
  The name list is not secret, and a worker editing it can only make the gate stricter or remove it, which
  is the same tripwire limit as the rest of the trust model (document it).
- Alternative: a board setting `require_registered_reviewers`. Simpler, but one more flag to forget.

Corrupt reviewer file: `registered_reviewers` skips and reports an unreadable file as a `GateError` naming the
path, instead of a traceback.

Tests: a repo with `plans/reviewers.json` and an empty key dir refuses merge with the new message; a corrupt
json file gives a one-line refusal; the existing five tests keep passing.


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