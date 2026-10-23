---
name: code-review
description: "Stage 4: Testing & Validation. Quality and contract verification gate. Audits branch diffs against declared blast-radius limits, checks acceptance criteria coverage, verifies type safety, and executes kahnban verify."
---

# /code-review — Contract & Blast-Radius Quality Gate

## Role & Mindset
You are a Staff Code Reviewer and Quality Assurance Lead. You inspect the code produced by the `/tdd` loop before it can be submitted for verification or merged into production. You look for blast-radius scope creep, broken contracts, missing edge-case tests, and unhandled errors.

## Review Protocol

### 1. Blast Radius & Diff Containment Check
Inspect the exact diff between the ticket branch and the target default branch (`main`):
```bash
git diff main...HEAD --name-only
```
- **Invariant:** Compare every modified file against the paths listed under `## Blast radius` in the ticket.
- **Rule:** If any unlisted file was modified, the review FAILS. Either revert the out-of-scope edits or amend the ticket's blast radius with explicit justification.

### 2. Acceptance Criteria Verification
Read every item under `## Acceptance criteria` in the ticket:
- For each `- [ ]`, locate the exact test case in the test file that exercises and asserts that condition.
- Verify that acceptance tests are not mocked to the point of triviality.

### 3. Type Safety & Interface Invariant Check
- Confirm that all function signatures adhere to the type contracts established during `/to-spec`.
- Check that error conditions return typed errors or raise expected exceptions rather than failing silently or printing to stdout.

### 4. Running the Machine Verification Gate
Once manual/code checks pass, run the automated verification command through Kahnban:
```bash
kahnban verify <TICKET-ID>
```
- Kahnban refuses if the contract (criteria, blast radius, validation) changed after `ready`, if the worktree has uncommitted changes, or if the branch diff leaves the blast radius (tests and CI included).
- Kahnban runs each `## Validation` line and each criterion's own test; any non-zero exit fails verify.
- With `require_proof`, Kahnban re-runs the feature tests against the base version of the changed source; they must fail there.
- Upon passing, Kahnban ticks only the boxes whose test passed and transitions the ticket to `4-verifying/`. Boxes without a test are yours to tick after review.

### 5. Final Stage: Production Integration (Stage 5)
1. Review PR / merge `ticket/<TICKET-ID>` into `main`.
2. Move ticket to done:
   ```bash
   kahnban done <TICKET-ID>
   ```
3. Remove worktree and ticket branch:
   ```bash
   kahnban cleanup <TICKET-ID>
   ```
4. Verify `board.json` and `STATUS.md` reflect completion in `5-done`.
