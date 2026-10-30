# Feature: Saved Searches

## Overview
Users want to save a search query and get notified when new results appear.

## Requirements
- FR-001: Users MUST be able to save a search with a name.
- FR-002: Saved searches MUST be listed per user, newest first.
- FR-003: The system MUST notify the user by email when a saved search has new results.
- FR-004: A user MUST be able to delete a saved search.
- SC-001: Listing 100 saved searches returns in under 200 ms.

## Phase 1: Storage

### Saved search model
**Why:** need persistent storage for saved searches (FR-001, FR-002).
**Files:** `src/search/models.py`, `tests/test_models.py`
**Acceptance:**
- [ ] a saved search round-trips (test: `pytest tests/test_models.py::test_roundtrip`)
**Validation:** `pytest tests/test_models.py`

### Saved search repository
**Why:** CRUD over saved searches.
**Files:** `src/search/repo.py`, `tests/test_repo.py`
**Depends on:** Saved search model
**Acceptance:**
- [ ] list returns newest first (test: `pytest tests/test_repo.py::test_order`)
- [x] delete removes the row
**Validation:** `pytest tests/test_repo.py`

## Phase 2: API and notifications

### Saved search HTTP API
**Why:** expose save/list/delete over HTTP.
**Files:** `src/api/routes.py`, `src/api/schemas.py`, `src/search/service.py`, `tests/test_api.py`, `docs/api.md`
**Depends on:** Saved search repository
**Acceptance:**
- [ ] POST /saved-searches creates one
**Validation:** `pytest tests/test_api.py`

### Notification worker
**Why:** email users when new results appear.
**Files:** the whole notification subsystem
**Depends on:** Saved search API, Email gateway
**Acceptance:**
- [ ] user is notified
