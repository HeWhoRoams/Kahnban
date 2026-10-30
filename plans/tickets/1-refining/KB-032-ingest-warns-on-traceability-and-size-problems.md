---
id: KB-032
title: Ingest warns on traceability and size problems
status: refining
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-031]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/ingest-warns-on-traceability-and-size-pr
source_hash: 7026247784be
validation_class: headless-verified
covers: [R19]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] warns on a covers id the spec does not define (test: `python -m pytest tests/test_ingest_traceability.py -q -k unknown_covers`)
- [ ] warns on a spec requirement no draft covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k uncovered_requirement`)
- [ ] warns on an unapproved spec (test: `python -m pytest tests/test_ingest_traceability.py -q -k unapproved_spec`)
- [ ] warns on a draft blast radius that is empty or over max_blast_radius_files (test: `python -m pytest tests/test_ingest_traceability.py -q -k radius_size`)
- [ ] warns when a non-spec document's ## Requirements section produced no covers, and not when it has none (test: `python -m pytest tests/test_ingest_traceability.py -q -k skipped_requirements`)
- [ ] ingest still exits 0 when it only warns (test: `python -m pytest tests/test_ingest_traceability.py -q -k warnings_exit_zero`)

## Blast radius
- `src/kahnban/ingest.py`
- `tests/test_ingest_traceability.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_ingest_traceability.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ingest-warns-on-traceability-and-size-pr
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-29 23:24 - unblocked: dependencies are in 5-done (supervisor)