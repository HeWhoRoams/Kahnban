---
id: SPEC-901
title: Saved searches
status: draft
---
# SPEC-901: Saved searches

## Problem
Users cannot save searches.

## Requirements
- R1: A user can save a named search.
- R2: Saved searches list newest first.
- R3: A user is emailed when a saved search has new results.

## Tickets

### Saved search model
- Files: `src/search/models.py`, `tests/test_models.py`
- Covers: R1
- Depends on: none
- Acceptance:
  - [ ] round-trips (test: `pytest tests/test_models.py::test_roundtrip`)
- Validation: `pytest tests/test_models.py`

### Listing order
- Files: `src/search/repo.py`, `tests/test_repo.py`
- Covers: R2, R9
- Depends on: Saved search model
- Acceptance:
  - [ ] newest first (test: `pytest tests/test_repo.py::test_order`)
- Validation: `pytest tests/test_repo.py`
