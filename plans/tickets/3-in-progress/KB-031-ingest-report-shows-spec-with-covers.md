---
id: KB-031
title: Ingest report shows spec with covers
status: in-progress
owner: coder-agent
branch: ticket/KB-031
worktree: .worktrees/KB-031
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/ingest-report-shows-spec-with-covers
source_hash: 378992ff89cc
validation_class: headless-verified
covers: [R18]
spec: SPEC-001
contract_hash: 1aa72e92e2f5f414
contract_sig: a347955db20c35a75e72d0bcfac58641eefda46a634eb118fc6ea66e8fbeedc5
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] the dry-run text report shows each draft's spec and covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k text_report`)
- [ ] the --json report has spec and covers per draft (test: `python -m pytest tests/test_ingest_traceability.py -q -k json_report`)

## Blast radius
- `src/kahnban/ingest.py`
- `tests/test_ingest_traceability.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_ingest_traceability.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ingest-report-shows-spec-with-covers
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 1aa72e92e2f5f414
- 2026-10-29 23:02 - claimed by coder-agent -> 3-in-progress