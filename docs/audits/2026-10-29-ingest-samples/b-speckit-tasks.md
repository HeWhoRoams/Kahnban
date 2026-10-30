# Tasks: Saved Searches

## Phase 1: Setup
- [ ] T001 Create project structure per implementation plan
- [ ] T002 [P] Configure linting in pyproject.toml

## Phase 2: Foundational
- [ ] T003 Create SavedSearch model in src/search/models.py

## Phase 3: User Story 1 - Save a search (Priority: P1)
- [ ] T004 [P] [US1] Contract test POST /saved-searches in tests/contract/test_save.py
- [ ] T005 [US1] Implement save endpoint in src/api/routes.py

## Phase 4: User Story 2 - Notifications (Priority: P2)
- [ ] T006 [P] [US2] Integration test for notifier in tests/integration/test_notify.py
- [ ] T007 [US2] Implement notifier in src/notify/worker.py (depends on T003)
