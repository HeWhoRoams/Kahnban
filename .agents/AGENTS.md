# Agent Working Agreement & Universal SSOT Protocol

Copy this file into the adopter repository's `AGENTS.md`, `CLAUDE.md`, and `.cursorrules`. It is the binding contract every AI agent and human engineer follows when interacting with this codebase across any model harness (Claude Code, ChatGPT, Antigravity, Cursor).

---

## 1. Startup & Resume Protocol (SSOT)

Before performing ANY action or writing ANY code, you MUST:
1. **Read `board.json`** (or `plans/board.json` / `plans/STATUS.md`): Verify active ticket columns, in-flight work, WIP limits, and dependencies.
2. **Read `.agents/state/ACTIVE_SESSION.md`**: Verify in-flight sub-agent tasks, currently modified files, known blockers, and immediate next commands.
3. **Verify Git & Worktree Status**:
   - Check `git status` and active worktrees (`.worktrees/`).
   - If resuming work on a claimed ticket, ensure you are operating INSIDE that ticket's isolated worktree (`.worktrees/<TICKET-ID>`).

---

## 2. The 5-Stage Gated Kanban Engineering Lifecycle

All work items must move strictly through these sequential stages:

```
[1. Intake]         -->  [2. Architecture]   -->  [3. Development]  -->  [4. Validation]    -->  [5. Production]
0-backlog                1-refining/2-ready       3-in-progress          4-verifying             5-done
/grill-with-docs         /to-spec, /to-tickets    /tdd in worktree       /code-review & verify   PR merge & done
```

### Stage 1: Clarification & Enrichment (Intake)
- **Column:** `0-backlog`
- **Skill:** `/grill-with-docs`
- **Rule:** No raw user prompt or feature request may bypass intake. Interview in rounds until nothing is assumed, record terms in `GLOSSARY.md` and choices in `ADR/`, and draft the spec with `kahnban spec new`. A human approves it (`kahnban spec approve SPEC-NNN --by <name>`): that is the one human gate.

### Stage 2: Refinement & Architecture
- **Columns:** `1-refining` -> `2-ready`
- **Skills:** `/to-spec` -> `/to-tickets`
- **Rule:** Complete the spec in `.agents/specs/` with numbered requirements (`- R1: ...`) and type contracts. Decompose it under `## Tickets` into tickets touching 1-3 files, each with `Covers: R1`, then `kahnban ingest <spec> --ready` and `kahnban spec coverage SPEC-NNN`.
- **Machine Gate:** Run `kahnban ready <ID>` to validate required headings, non-empty blast radius, testable acceptance criteria, and valid dependencies before claiming.

### Stage 3: In Development
- **Column:** `3-in-progress`
- **Skill:** `/tdd`
- **Rule:** Always claim before coding:
  ```bash
  kahnban claim <TICKET-ID> --owner <agent-id> --worktree
  ```
  The tool refuses if `## Blast radius` overlaps with any in-flight ticket (Rule BL16).
- All code changes, edits, and test runs execute inside `.worktrees/<TICKET-ID>` on branch `ticket/<TICKET-ID>`. Never edit the main checkout while a ticket is claimed, and never commit board state on a ticket branch.
- Drive implementation strictly using Red-Green-Refactor test loops.

### Stage 4: Testing & Validation
- **Column:** `4-verifying`
- **Skills:** `/code-review` -> `kahnban verify`
- **Rule:** Perform pre-verification review auditing git diff against declared `## Blast radius` and verifying acceptance criteria.
- Run machine verification:
  ```bash
  kahnban verify <TICKET-ID>
  ```
  Commit everything first: verify refuses uncommitted work and any change outside `## Blast radius` (tests and CI included). It runs each `## Validation` line (the first failure stops it) and each criterion's own ``(test: `cmd`)``, and ticks only the boxes whose test passed. Under `require_proof` it also re-runs the feature tests on the base source, where they must fail. A coder never ticks a box; only a reviewer ticks one that names no test.

### Stage 5: In Production
- **Column:** `5-done`
- **Rule:** A reviewer who is not the owner approves (or rejects) the verified tip, then the merge queue lands it. Never `git merge` a ticket branch by hand.
- Review, land, finalize and prune:
  ```bash
  kahnban approve <TICKET-ID> --reviewer <name>       # or: kahnban reject <TICKET-ID> --reviewer <name> -m "..."
  kahnban merge <TICKET-ID>                           # tests main + branch, fast-forwards only if green
  kahnban done <TICKET-ID>
  kahnban cleanup <TICKET-ID>
  ```

---

## 3. Sub-Agent Orchestration & Isolated Worktrees

When spawning parallel sub-agents for concurrent tasks:
1. **Safety Scan:** Verify `candidate.blast_radius` shares no files or directories with any ticket currently in `3-in-progress`.
2. **Worktree Isolation:** Dispatch each sub-agent into its dedicated worktree (`.worktrees/<TICKET-ID>`).
3. **Synchronization:** Update `ACTIVE_SESSION.md` with active sub-agent assignments so parallel work remains visible.
4. **Integration:** Verify and merge sub-agent branches sequentially into `main`.

---

## 4. Cross-Harness Hand-Off Protocol (Claude <-> ChatGPT <-> Antigravity <-> Cursor)

When switching AI harnesses or running low on context/credits:
1. **Flush State:**
   ```bash
   kahnban session --flush --ticket <TICKET-ID> --note "Summary of current progress" --next-cmd "pytest tests/..."
   ```
2. **Commit Worktree:** Commit in-progress code to branch `ticket/<TICKET-ID>`.
3. **Resume Prompt in New Harness:**
   > *"Read `.agents/state/ACTIVE_SESSION.md` and `board.json`. Acknowledge current state and resume work on <TICKET-ID> inside its worktree."*

---

## 5. Command Quick Reference

```powershell
kahnban lint                                   # board rules BL01-BL19
kahnban status                                 # counts + lint summary
kahnban session                                # inspect cross-harness state
kahnban session --flush --ticket <ID>          # update ACTIVE_SESSION.md
kahnban capture "<idea>" ["<idea>" ...]        # ideation -> backlog, one commit
kahnban ingest <spec.md> [--dry-run] [--ready] # spec -> backlog/ready, idempotent
kahnban new "<title>" --problem-file spec.txt  # single ticket creation
kahnban ready <ID>                             # refinement gate -> 2-ready
kahnban spec new "<title>"                     # draft SPEC-NNN in .agents/specs/
kahnban spec approve <SPEC> --by <name>        # humans only: freeze the requirements
kahnban spec coverage <SPEC>                   # exit 1 until every requirement has a ticket
kahnban claim <ID> --owner <name> --worktree   # claim & spawn isolated worktree
kahnban verify <ID>                            # execute validation command -> 4-verifying
kahnban approve <ID> --reviewer <name>         # sign off the verified tip (never the owner)
kahnban reject <ID> --reviewer <name> -m "..." # back to in-progress with reasons in the Log
kahnban merge <ID>                             # merge queue: test main+branch, land only if green
kahnban done <ID> [--merge-commit <sha>]       # production gate -> 5-done
kahnban cleanup <ID>                           # prune worktree & local branch
kahnban escalate <ID> --reason "<question>"    # park for a human instead of guessing
kahnban run --max-steps 20                     # the factory loop (configure 'workers' first)
kahnban move <ID> <column> --reason "<why>"    # escape hatch; always logged
```
