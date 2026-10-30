---
id: KB-012
title: "Reviewer registry: committed reviewer names so a missing key dir refuses, and a corrupt reviewer file gives a clear error"
status: in-progress
owner: coder-agent
branch: ticket/KB-012
worktree: .worktrees/KB-012
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: [docs/remediation-plan-3.md]
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 2097b578f5077dac
contract_sig: 18b488248360049bef828dbbfa5059b61965d9e09ad517c7c24c40c820fcfe64
confirmed: ""
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
- [ ] `kahnban reviewers add NAME` writes `NAME` (never the key), case-insensitively de-duplicated, into a committed `plans/reviewers.json`, in addition to the existing per-machine key it already creates (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add_writes_the_committed_registry`)
- [ ] once `plans/reviewers.json` names a reviewer, that name being required carries over to a checkout with an empty local key directory: `core.approve`/`core.merge` for that reviewer refuse with `"reviewer 'NAME' has no key on this machine; run 'kahnban reviewers add NAME' here"` instead of silently treating no reviewers as registered (test: `python -m pytest tests/test_reviewer_keys.py -q -k committed_registry_without_a_local_key_refuses`)
- [ ] a corrupt (unreadable/invalid-JSON) `plans/reviewers.json` makes `core.merge` refuse with a one-line `GateError` naming the path, not a traceback (test: `python -m pytest tests/test_reviewer_keys.py -q -k corrupt_reviewers_file_refuses_cleanly`)
- [ ] the five existing reviewer-key tests keep passing unchanged (test: `python -m pytest tests/test_reviewer_keys.py -q`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/cli.py`
- `tests/test_reviewer_keys.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:36 - ready gate passed -> 2-ready | contract 2097b578f5077dac
- 2026-10-29 20:24 - claimed by coder-agent -> 3-in-progress