---
id: KB-028
title: Lint reports dependency cycles
status: in-progress
owner: coder-agent
branch: ticket/KB-028
worktree: .worktrees/KB-028
created: 2026-10-29
updated: 2026-10-30
legacy_id: ""
design_docs: []
depends_on: [KB-027]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-reports-dependency-cycles
source_hash: b067ce6bece5
validation_class: headless-verified
covers: [R15]
spec: SPEC-001
contract_hash: 218a65fc86818449
contract_sig: a42b8bce78196ba051023cf2682bb74701f75151d77f9ec33b984dfc1e345ffb
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] kahnban lint reports a depends_on cycle under a new rule id, naming the cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k cycle_reported`)
- [ ] a self-dependency is reported as a cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k self_dependency`)

## Blast radius
- `src/kahnban/linter.py`
- `tests/test_lint_cycles.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_cycles.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-reports-dependency-cycles
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-30 00:45 - unblocked: dependencies are in 5-done (supervisor)
- 2026-10-30 00:47 - ready gate passed -> 2-ready | contract 218a65fc86818449
- 2026-10-30 00:47 - claimed by coder-agent -> 3-in-progress