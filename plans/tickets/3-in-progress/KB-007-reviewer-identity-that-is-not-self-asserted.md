---
id: KB-007
title: Reviewer identity that is not self-asserted
status: in-progress
owner: claude-coder
branch: ticket/KB-007
worktree: .worktrees/KB-007
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
contract_hash: 0bf3ef8b8e5113a1
contract_sig: e08fe92d909316fd4721bc9c79bfda7fade1c08c8194b208b780f5bd3f9f06cd
confirmed: ""
---

## Problem
`kahnban approve --reviewer <name>` records whatever name is typed. The owner check compares two strings, so a typo, a worker or a
second hat can approve under any other name. Decided with the user (2026-10-26): registered reviewer keys.

`kahnban reviewers add <name>` creates a key for that reviewer in the user's key directory (next to the project signing key, never in
the repository). Once a project has at least one registered reviewer, `approve` must be made by a registered one and also records
`reviewer_sig`, an HMAC with that reviewer's key over the ticket, tip and reviewer; `merge` and `done` refuse an approval whose
`reviewer_sig` is missing or wrong. A project with no registered reviewer behaves as before. Limits for the README: a process running
as the same OS user can read every key, and an agent-reviewer flow (a worker approving, the runner countersigning) has no personal key,
so a project that registers reviewers expects human approvals.

## Acceptance criteria
- [ ] `kahnban reviewers add NAME` registers a reviewer once, `kahnban reviewers list` shows the names, and adding the same name again is refused (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add`)
- [ ] once any reviewer is registered, `approve` by an unregistered name is refused, and by a registered one stores `reviewer_sig` (test: `python -m pytest tests/test_reviewer_keys.py -q -k registered_reviewer`)
- [ ] `merge` and `done` refuse an approval whose `reviewer_sig` was removed or edited, and a project with no registered reviewer behaves as before (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewer_sig`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/core.py`
- `src/kahnban/cli.py`
- `tests/test_reviewer_keys.py`

## Implementation notes
- trust.py: `reviewers_dir`, `register_reviewer`, `registered_reviewers`, `sign_reviewer`, `reviewer_problem`; one JSON file per reviewer, named by a hash of the lower-cased name, holding the name and a random key; `key_dir()` is overridable, so tests are isolated.
- core.py: `approve` refuses an unregistered name when any is registered and stores `reviewer_sig`; `_signature_problem` (the one hook merge and done share) also checks it; `reject` stays open.
- cli.py: a `reviewers` parser with `add` and `list`; tests call `main(["reviewers", "add", ...])`.
- Needs 4 files, so `max_blast_radius_files` is raised to 4 for this ticket and restored when it is done.

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 23:32 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 23:32 - ready gate passed -> 2-ready | contract 0bf3ef8b8e5113a1
- 2026-10-26 23:32 - claimed by claude-coder -> 3-in-progress