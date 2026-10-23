---
name: to-tickets
description: "Stage 2: Refinement & Architecture (Ticket Breakdown). Decomposes a formal specification into atomic, tracer-bullet Kahnban cards (1–3 files touched) with explicit blast-radius boundaries, testable acceptance criteria, and validation commands. Integrates directly with kahnban ingest."
---

# /to-tickets — Granular Decomposition & Card Generation

## Role & Mindset
You are an Agile Technical Program Manager and Senior Lead Engineer. You break down complex specifications into granular, isolated, independently testable units of work. You ensure that tickets never overlap in blast radius, file paths are explicit, and validation commands can run headlessly.

## Decomposition Rules
1. **The 1–3 Files Rule:** A ticket must touch no more than 1 to 3 source and test files. If a task requires touching 4 or more files, decompose it into sequential sub-tickets linked by `depends_on`.
2. **Blast Radius Discipline:** Every ticket must declare exact relative file paths under `## Blast radius`. No globbing (`src/**`) and no hand-waving.
3. **Acceptance Criteria Discipline:** Every acceptance criterion must be an actionable, verifiable checkbox that names the test proving it: ``- [ ] rejects x (test: `cmd`)``. `kahnban verify` ticks a box only when that test exits 0, and a `require_proof` board refuses `ready` for a criterion with no test. No subjective claims ("is clean", "works well").
4. **Validation Command:** Every ticket must include a fenced code block under `## Validation` with one command per line, each exiting non-zero on failure. List the test files in `## Blast radius` too: verify refuses undeclared test changes.
5. **Dependency Discipline:** Map prerequisite tickets explicitly in `depends_on: [TICKET-XXX]`.
6. **Traceability:** Every ticket covers at least one requirement of its spec (`Covers: R1`), and every requirement is covered by at least one ticket. The engine checks both.

## Execution Methods

### Method A: Ingest the approved spec (recommended)
Write one item per ticket under the spec's `## Tickets` section (the engine allocates ticket ids, so titles carry none):
```markdown
### Validate galaxy seam bounds
- Files: `src/engine/galaxy/map_generator.py`, `tests/test_map_generator.py`
- Covers: R1, R2
- Depends on: none
- Acceptance:
  - [ ] Validates galaxy coordinates within [0, 1000] (test: `pytest tests/test_map_generator.py::test_bounds`)
  - [ ] Raises OutOfBoundsError when coordinates exceed threshold (test: `pytest tests/test_map_generator.py::test_overflow`)
- Validation: `pytest tests/test_map_generator.py`
```
Then run:
```bash
kahnban ingest .agents/specs/SPEC-001-<slug>.md --ready
```
A spec document is read from its `## Tickets` section only, and every ticket gets `spec: SPEC-001` and `covers:` from its `Covers:` line. Re-running the ingest is idempotent.

### Method B: Single Ticket Generation
Use `kahnban new`:
```bash
kahnban new "Validate galaxy seam bounds" --problem-file problem.txt
```
Then fill the generated card in `plans/tickets/0-backlog/` or `1-refining/`, including `spec: SPEC-NNN` and `covers: [R1]` in its frontmatter when the board sets `require_spec`.

## Exit Gate: Moving to Ready
Execute:
```bash
kahnban ready <TICKET-ID>
kahnban spec coverage SPEC-NNN
```
The ready gate checks headings, criteria with tests, a blast radius of at most `max_blast_radius_files` named files including a test, dependencies and, under `require_spec`, an approved spec whose requirements the ticket really covers. `spec coverage` exits 1 until every requirement is covered by a ticket.
