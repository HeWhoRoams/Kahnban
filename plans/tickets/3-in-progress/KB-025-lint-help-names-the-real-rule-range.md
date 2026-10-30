---
id: KB-025
title: lint help names the real rule range
status: in-progress
owner: coder-agent
branch: ticket/KB-025
worktree: .worktrees/KB-025
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-help-names-the-real-rule-range
source_hash: bb144b599d40
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
contract_hash: 56148b8bf0ac0793
contract_sig: b01efc62360c1a919c5a6d7ad88d717531ce0d22db21ba3204b30fb4add510db
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] kahnban lint --help names the first and last rule ids of the linter's rule table (test: `python -m pytest tests/test_lint_help.py -q -k help_range_from_table`)

## Blast radius
- `src/kahnban/cli.py`
- `tests/test_lint_help.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_help.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-help-names-the-real-rule-range
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 56148b8bf0ac0793
- 2026-10-29 22:30 - claimed by coder-agent -> 3-in-progress