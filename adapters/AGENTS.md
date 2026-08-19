# Agent Working Agreement & Kanban Protocol

Copy this section into the adopter repository's `AGENTS.md`, `CLAUDE.md`, and
`.cursorrules` (plan §5.1).  It is the contract every agent working the board
follows.

1. **Source of Truth:** The active backlog lives in `plans/tickets/`. The folder
   a ticket sits in *is* its status. Never invent untracked tasks and never edit
   `plans/STATUS.md` or `plans/status.json` — both are regenerated projections.
2. **Work Selection:** Only pick tickets from `plans/tickets/2-ready/`. Never
   touch `0-backlog` or `1-refining` items without explicit user instruction.
3. **Claiming Work:** Always claim before coding:
   - CLI: `kahnban claim <TICKET-ID> --owner <agent-name> --worktree`
   - MCP: `kanban_ticket_claim(ticket_id=..., owner=...)`
   The tool will refuse if the ticket is not ready, if a dependency is
   unfinished, or if the ticket's `## Blast radius` overlaps work already in
   progress. Do not work around a refusal — report it.
4. **Execution & Isolation:** All commands, edits, and tests run inside
   `.worktrees/<TICKET-ID>` on branch `ticket/<TICKET-ID>`. Never edit files in
   the main working tree while a ticket is claimed, and never commit anything
   under `plans/tickets/` from a ticket branch — board state belongs to the
   default branch only.
5. **Stay Inside the Blast Radius:** Only change paths declared under
   `## Blast radius`. `kahnban verify` compares the branch diff against that
   declaration and refuses on scope creep. If the work genuinely needs more
   files, say so and get the ticket amended.
6. **No Silent Ticking:** Acceptance boxes are checked only after
   `kahnban verify <TICKET-ID>` passes — the tool runs the validation command
   itself and records the exit code and output in `## Log`. Pasted evidence is
   not accepted for headless-verifiable work.
7. **Completion:** `verify` moves tickets to `4-verifying`. Only human
   review and a merge into the default branch, followed by
   `kahnban done <TICKET-ID>`, moves a ticket to `5-done`. Run
   `kahnban cleanup <TICKET-ID>` afterwards to remove the worktree and branch.

8. **Getting Work Onto the Board:** never hand-write ticket files. Use the
   entry point that matches what you have — `kahnban capture` for rough ideas,
   `kahnban ingest` for a plan document, `kahnban new` for a single ticket. See
   [PLAN-INGESTION.md](PLAN-INGESTION.md). Ingested tickets always start in the
   backlog with unchecked criteria; that is deliberate, not an oversight.

## Command quick reference

```powershell
kahnban lint                                   # board rules BL01-BL17
kahnban status                                 # counts + lint summary
kahnban capture "<idea>" ["<idea>" ...]        # ideation -> backlog, one commit
kahnban ingest <plan.md> [--dry-run] [--ready] # plan -> backlog, idempotent
kahnban new "<title>" --problem-file spec.txt  # long text by file, never argv
kahnban ready <ID>
kahnban claim <ID> --owner <name> --worktree
kahnban verify <ID>
kahnban done <ID> [--merge-commit <sha>]
kahnban cleanup <ID>
kahnban move <ID> <column> --reason "<why>"    # escape hatch; always logged
```
