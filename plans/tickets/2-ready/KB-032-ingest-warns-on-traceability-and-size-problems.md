---
id: KB-032
title: Ingest warns on traceability and size problems
status: ready
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
contract_hash: 823581484d9e2649
contract_sig: a859c77d4ac46231a39fde48168cab554180aabd8d50b3daeddc0b90a5ee885b
confirmed: ""
---

## Problem
`kahnban ingest` (`src/kahnban/ingest.py`) builds each `TicketDraft`'s `spec`/`covers`
(KB-031, R18) but never checks them against the spec, and never checks blast
radius size or an orphaned `## Requirements` section. A draft can cite a
`covers` id the spec does not define, a spec requirement can go uncovered by
every draft, an unapproved spec can be cited, a draft's blast radius can be
empty or exceed `config.max_blast_radius_files`, and a non-spec document's
`## Requirements` section can produce no `covers` at all — and ingest stays
silent on every one of these, exiting 0 either way. `src/kahnban/specs.py`
already has the primitives (`find_spec`, `Spec.approved`,
`Spec.requirements`) `ingest_document` needs to turn each case into an entry
on `report.warnings`, which `render_report` already prints and `--json`
already carries (`as_dict`'s `warnings` key) — so exit code 0 is kept as-is
and nothing escalates to an error.

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
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ingest-warns-on-traceability-and-size-pr
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-29 23:24 - unblocked: dependencies are in 5-done (supervisor)
- 2026-10-29 23:27 - ready gate passed -> 2-ready | contract 823581484d9e2649