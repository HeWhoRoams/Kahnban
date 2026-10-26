---
id: KB-010
title: "The default worker command cannot finish a ticket headlessly: claude -p with acceptEdits is asked to approve git and kahnban commands. Allow the commands each role needs (allowedTools or project permission rules written by skills install) and prove it with the live test"
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
contract_hash: 45e5c3958f8b8cb6
confirmed: ""
---

## Problem
A headless `claude -p --permission-mode acceptEdits` worker is asked to approve `git add`, `git commit` and
`kahnban approve`, and a headless worker cannot answer. Two live runs with Haiku (2026-10-25) show it: the first
coder finished its work and could not commit it; with git allowed by name the second got through refine, implement
and verify, and the reviewer then never ran `kahnban approve` or `kahnban reject`. The worker command `kahnban run`
documents therefore cannot finish a ticket. `kahnban skills install --harness claude` already owns `.claude/settings.json`
(the guard hooks), so it should also write the permission rules the roles need; the guard still refuses push,
`--no-verify` and every command outside a role.

## Acceptance criteria
- [ ] installing for claude writes permissions.allow with the kahnban command and the git verbs a worker needs (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_written`)
- [ ] re-installing keeps every other setting and every rule already there, and adds nothing twice (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_keep`)
- [ ] the board's validation and regression commands are allowed too, when a board exists (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_include_the_board`)

## Blast radius
- `src/kahnban/harnesses.py`
- `src/kahnban/skills.py`
- `tests/test_harness_files.py`

## Implementation notes
- `harnesses.merge_permissions(path, tools, messages)` adds missing entries to `permissions.allow`; `allowed_tools(root)` is the fixed list plus `Bash(<command>:*)` for the board's validation and regression commands.
- Called from `skills._configure_agent_harness` for the claude harness only.
- Specific git verbs (add, commit, status, diff, log, rm, mv), never `git:*`; `Bash(kahnban:*)` is safe because the guard checks the role.
- Proof beyond the unit tests: `KAHNBAN_LIVE=1 python -m pytest tests/live` should get a toy ticket past review.

## Validation
```
python -m pytest tests/test_harness_files.py -q
```

## Log
- 2026-10-25 18:50 - created -> 0-backlog | captured
- 2026-10-26 14:42 - ready gate passed -> 2-ready | contract 45e5c3958f8b8cb6