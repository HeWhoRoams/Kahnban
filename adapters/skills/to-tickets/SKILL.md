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

## Execution Methods

### Method A: Using `kahnban ingest` (Recommended for Batch Breakdown)
Format the breakdown section in your spec according to `adapters/PLAN-INGESTION.md`:
```markdown
### HOA-001: Implement Galaxy Seam Bounds
- Files: `src/engine/galaxy/map_generator.py`, `tests/test_map_generator.py`
- Depends on: none
- Acceptance:
  - [ ] Validates galaxy coordinates within [0, 1000] (test: `pytest tests/test_map_generator.py::test_bounds`)
  - [ ] Raises OutOfBoundsError when coordinates exceed threshold (test: `pytest tests/test_map_generator.py::test_overflow`)
- Validation: `pytest tests/test_map_generator.py`
```
Then run:
```bash
kahnban ingest .agents/specs/SPEC-001.md --ready
```

### Method B: Single Ticket Generation
Use `kahnban new`:
```bash
kahnban new "Implement Galaxy Seam Bounds" --problem-file problem.txt
```
Then fill the generated card in `plans/tickets/0-backlog/` or `1-refining/`.

## Exit Gate: Moving to Ready
Execute:
```bash
kahnban ready <TICKET-ID>
```
The machine gate validates headings, non-empty blast radius, unchecked criteria, dependencies, and moves the ticket to `plans/tickets/2-ready/`.
Verify that `board.json` shows the ticket in `2-ready`.
