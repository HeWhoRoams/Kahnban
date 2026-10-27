---
id: KB-006
title: "Tamper resistance for the frozen records: keep contract and approval records out of the workers' write access"
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
contract_hash: f8680312d43d6fe4
confirmed: ""
---

## Problem
Approvals are signed with a key kept outside the repository, but the frozen contract is not: `contract_hash` is plain frontmatter, so a
worker that edits the acceptance criteria, blast radius or validation can write the matching hash too, and `verify_contract` passes.
Sign the hash at the same moments it is written (`ready`, and the freeze at `claim`) with the existing key, store it as `contract_sig`,
and check it wherever `verify_contract` runs. With `require_signed_approvals`, a hash without a signature is refused with the way out
(`move` back to refining, then `ready`). Limit, to be stated in the README: a worker running as the same OS user can still read the key
file, so this is a tripwire. Real isolation is a container or a separate OS user for workers, which is a deployment choice, not engine code.

## Acceptance criteria
- [ ] `ready` stores `contract_sig`, an HMAC of the ticket id and contract hash made with the approval key (test: `python -m pytest tests/test_contract_signature.py -q -k ready_signs`)
- [ ] a contract edited together with its `contract_hash` is refused at verify when the signature no longer matches (test: `python -m pytest tests/test_contract_signature.py -q -k forged_hash`)
- [ ] with `require_signed_approvals`, a frozen contract with no signature is refused and the message names `ready`; without the setting it still passes (test: `python -m pytest tests/test_contract_signature.py -q -k unsigned_contract`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/core.py`
- `tests/test_contract_signature.py`

## Implementation notes
- `trust.sign_contract(root, ticket_id, digest)` and `trust.contract_problem(root, ticket_id, digest, signature)`, built on `_key`.
- `core.ready` and the claim-time freeze add `contract_sig` next to `contract_hash`; `verify_contract` checks it (all five callers share it).
- Tests use `test_factory_gates` helpers (`factory_board`, `claimed`).
- After merge, outside the ticket: a README line on the limit and on isolating workers.

## Validation
```
python -m pytest tests/test_contract_signature.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 22:44 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 22:44 - ready gate passed -> 2-ready | contract f8680312d43d6fe4