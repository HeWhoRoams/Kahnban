---
id: KB-014
title: "Core clean-up: one list of approval fields to clear, rename _signature_problem"
status: ready
owner: unassigned
branch: ""
worktree: ""
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
contract_hash: 1e0d5fe012da54e4
contract_sig: b229f9ee9849180e08393686e6e639b10c309589fbff3ac86c82687b441c5c74
confirmed: ""
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
- [ ] `verify` and `reject` clear the same approval fields (`reviewer`, `approved_sha`, `approval_sig`, `reviewer_sig`, `integrated_sha`, `confirmed`) via one module-level `_APPROVAL_FIELDS` mapping in `core.py`, not two duplicated dict literals (test: `python -m pytest tests/test_reviewer_keys.py -q -k approval_fields_mapping_is_shared`)
- [ ] `core._signature_problem` is renamed to `core._approval_problem` (no remaining reference to the old name anywhere in `src/`) and its docstring says it checks both the engine HMAC and the reviewer seal (test: `python -m pytest tests/test_reviewer_keys.py -q -k approval_problem_checks_hmac_and_seal`)
- [ ] no behaviour change: the existing reviewer-key suite and the full regression suite still pass (test: `python tests/run_parallel.py -j 8`)

## Blast radius
- `src/kahnban/core.py`
- `tests/test_reviewer_keys.py`

## Implementation notes
- The two fields dicts to dedupe are in `verify` (sets `verified_sha` to the new tip, the rest blank) and `reject` (blanks `verified_sha` too). Keep `verified_sha` out of `_APPROVAL_FIELDS` since the two callers disagree on its value; each call site still sets it itself and merges in `_APPROVAL_FIELDS` for the rest.
- `_signature_problem` is called from two sites (`_release_problems`, used by `done`, and `merge`) — rename both call sites along with the definition.

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:41 - ready gate passed -> 2-ready | contract 1e0d5fe012da54e4