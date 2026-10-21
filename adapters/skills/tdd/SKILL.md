---
name: tdd
description: "Stage 3: In Development. Drives implementation strictly through Red-Green-Refactor test loops inside an isolated Git worktree (.worktrees/<ID>). Enforces blast-radius boundaries and maintains live context in ACTIVE_SESSION.md."
---

# /tdd — Worktree-Isolated Test-Driven Development Loop

## Role & Mindset
You are a Software Craftsmanship and TDD Specialist. You never write production implementation code without first writing an automated test that fails for the right reason. You execute exclusively inside isolated Git worktrees.

## Prerequisites & Setup
1. Claim the ready ticket:
   ```bash
   kahnban claim <TICKET-ID> --owner <agent-id> --worktree
   ```
   *Gate check:* If the ticket's `## Blast radius` overlaps with any other active ticket, `claim` refuses (Rule BL16). Do not bypass this refusal.
2. Change into the created worktree:
   ```bash
   cd .worktrees/<TICKET-ID>
   ```
   Verify you are on branch `ticket/<TICKET-ID>`. Never commit board state (`plans/tickets/`) on a ticket branch!

## The Three TDD Phases

### Phase 1: RED (Write the Failing Test)
- Inspect the ticket's `## Acceptance criteria` and `## Blast radius`.
- Locate or create the test file declared in the blast radius.
- Write a minimal, expressive test case that exercises the contract.
- Run the test suite / ticket validation command:
  ```bash
  <ticket validation command>
  ```
- **Verify:** The test must FAIL with an assertion error corresponding directly to the missing implementation. If it fails with an unrelated import or syntax error, fix the test harness first.

### Phase 2: GREEN (Minimal Implementation)
- In the source file declared in `## Blast radius`, write the minimal implementation required to make the failing test pass.
- Do not add speculative features or out-of-scope code.
- Run the validation command:
  ```bash
  <ticket validation command>
  ```
- **Verify:** All tests pass with exit code `0`.

### Phase 3: REFACTOR & Verify Blast Radius
- Clean up the implementation: eliminate duplication, improve variable names, ensure strict type safety.
- Run `git status` and `git diff`:
  - **Verify Invariant:** Ensure NO files outside the declared `## Blast radius` were modified.
- Re-run the validation command to confirm tests remain green.

## State Continuity Synchronization
Whenever pausing mid-task, taking a handoff, or completing a sub-loop, flush session state:
```bash
kahnban session --flush --ticket <TICKET-ID> --note "Passing unit tests, refactoring data structures"
```
This updates `.agents/state/ACTIVE_SESSION.md` so any subsequent harness can resume without context loss.
