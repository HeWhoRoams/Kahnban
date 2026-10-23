---
id: SPEC-000
title: Replace with the feature's name
status: draft
approved_by: ""
approved: ""
requirements_hash: ""
created: 1970-01-01
---

# SPEC-000: Replace with the feature's name

## Problem
What is wrong or missing today, for whom, and why it matters now.

## Requirements
One observable outcome per line, each with a stable id that tickets cite in
`covers:`. Approving the spec freezes this list; changing it later means
approving it again.
- R1: Replace with the first observable outcome
- R2: Replace with the second observable outcome

## Non-goals
- What this spec deliberately does not change.

## Decisions
- Terms used here are defined in `GLOSSARY.md`; choices between real options are
  recorded in `ADR/NNNN-<slug>.md`. Link them here.

## Edge cases
| Scenario | Expected behaviour | Test that proves it |
| :--- | :--- | :--- |
| Empty or malformed input | Refused with a clear error | Unit test |

## Tickets
One `###` item per ticket: 1-3 files, the requirements it covers, and a test
for every criterion. `kahnban ingest <this file> --ready` turns them into tickets
and `kahnban spec coverage SPEC-000` checks every requirement is covered.

### Replace with the first ticket's title
- Files: `path/to/source.ext`, `path/to/test_source.ext`
- Covers: R1
- Acceptance:
  - [ ] The observable condition (test: `command that proves it`)
- Validation: `command that runs the feature tests`
