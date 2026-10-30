---
id: SPEC-001
title: "Phase 0-1 elevation: localized skill set, dependency-aware dispatch, truthful ingest"
status: approved
approved_by: claude-opus-5-5 (authorized by Tim Niles in chat)
approved: 2026-10-29
requirements_hash: 88705bf452eabd81
created: 2026-10-29
---

# SPEC-001: Phase 0-1 elevation: localized skill set, dependency-aware dispatch, truthful ingest

## Problem
The 2026-10-29 factory audit (`docs/audits/2026-10-29-factory-audit-and-elevation-plan.md`) found two gaps that block "hand it a whole spec".

**The skill set is borrowed, broken in places, and unattributed.** `no-comments` is preloaded into every coder but needs an agent and a router that aren't shipped. `skills check` misses the problem. The upstream copies have drifted, carry no licence notice, and can clash with upstream installs.

**The factory cannot run a dependency chain.** The dispatcher sends tickets whose dependencies are not done to refinement, where `ready` refuses them until they escalate to a human. Ingest also drops traceability problems without warning, and learnings are captured only when an agent remembers to.

## Requirements
**Skill set (Phase 0)**
- R1: Every skill under `src/kahnban/templates/skills/` has a folder name and frontmatter `name` starting with `kb-`; no unprefixed skill is shipped.
- R2: Every skill reference in shipped skills, `roles.json`, agent templates, `AGENTS.md` templates and docs uses the `kb-` names, and `kahnban skills check` passes on the repo.
- R3: `kahnban skills check` reports a reference to a skill or agent that is not shipped when it is written as `**name** skill`, `**name**` principle skill, or `subagent_type: "name"`, not only `/name`.
- R4: `kb-grill-with-docs`, `kb-grilling`, `kb-domain-modeling`, `kb-to-spec`, `kb-to-tickets`, `kb-tdd` and `kb-code-review` are based on mattpocock/skills v1.3.2. They differ from upstream only where a Kahnban gate requires it: exact ticket paths, the file cap, `R`-numbered requirements, and the `kahnban spec`/`ingest` commands.
- R5: Every pstack-derived skill is based on cursor/plugins@c742dd6. `kb-principle-build-the-lever`, `kb-principle-redesign-from-first-principles` and `kb-show-me-your-work` are shipped, and no shipped skill references `poteto-mode`.
- R6: `kahnban skills install` writes a `kahnban-comment-sicko` agent for the claude harness, and `kb-no-comments` spawns it under that name.
- R7: `.agents/skills.lock.json` records, for every shipped skill and agent, its source repository, its upstream path and its commit, or `kahnban` for native ones.
- R8: `kahnban skills install` removes from each harness directory any skill or agent it previously installed that is no longer shipped, and leaves skills it did not install untouched.
- R9: `kahnban skills install --source mattpocock` leaves every `kb-` skill byte-identical.
- R10: The repo has an MIT `LICENSE`, `pyproject.toml` declares it, and `THIRD_PARTY_NOTICES.md` reproduces the MIT notices of cursor/plugins (pstack) and mattpocock/skills.
- R11: No shipped file mentions "Lauren Tan Clustering Invariant", `/implement-spec` or `/retro`.
- R12: `IMPLEMENTATION_STATUS.md` and `NEXT_STEPS.md` state no hard-coded test count and do not describe `kahnban run` as sequential, and `kahnban lint --help` names the rule range taken from the linter's own rule table.

**Dispatch (Phase 1)**
- R13: `kahnban next` never assigns a backlog or refining ticket to the spec analyst while any of that ticket's `depends_on` entries is not in done, does not exist, or lies on a dependency cycle.
- R14: When the only open intake or claim work is waiting tickets, `kahnban next` reports idle and names each waiting ticket with what it waits on: a ticket id, a missing id, or the cycle.
- R15: `kahnban lint` reports a `depends_on` cycle under a new rule id.
- R16: A ticket may set `priority: critical|high|normal|low` (default `normal`) and `risk: high|medium|low` (default `medium`). `kahnban lint` warns on any other value, and dispatch treats it as the default.
- R17: Among eligible intake candidates, and separately among eligible claim candidates, `kahnban next` picks by priority, then risk (highest first), then the number of open tickets that transitively depend on the candidate (most first), then ticket id.

**Ingest and learnings (Phase 1)**
- R18: The `kahnban ingest --dry-run` report, as text and as `--json`, shows each draft's `spec` and `covers`.
- R19: `kahnban ingest` warns, and still exits 0, on each of these:
  - a `covers` id that the spec does not define;
  - a spec requirement that no draft covers;
  - an unapproved spec;
  - a draft blast radius that is empty or larger than `max_blast_radius_files`;
  - a `## Requirements` section in a non-spec document that produced no `covers`.
- R20: `kahnban reject` and `kahnban escalate` each capture a learning naming the ticket and the reason, and repeated captures for the same cause cluster into one learning.
- R21: If capturing the learning fails, `reject` and `escalate` still complete their transition and print a warning.

## Non-goals
- Phase 2 and later: the planner role, `spec status`/`close`, turning on `require_spec`, two-axis review, and constitution gates.
- Resolving the tension between vertical slices and the file cap, or the rule against code snippets in specs. The localized skills keep the gate needs listed in R4, and Phase 5 revisits them.
- Importing pstack's `poteto-mode` router or its playbooks, or any automatic upstream sync.
- Renaming CLI commands or the four `kahnban-*` role agents, or adding a fifth board role. `kahnban-comment-sicko` is a helper the coder spawns.
- Changing tickets KB-011, KB-012 and KB-014, which are already in flight.
- Making ingest warnings fatal (`--strict`).

## Decisions
- Terms: Localized skill, Provenance, Priority, Risk, Dispatch order, Waiting ticket ([GLOSSARY.md](../../GLOSSARY.md)).
- [ADR-0002](../../ADR/0002-localize-skills-with-kb-prefix.md): localize every shipped skill under `kb-`, base on the latest upstream, record provenance, prune stale installs.
- [ADR-0003](../../ADR/0003-dependency-aware-dispatch-order.md): skip waiting tickets, and order by priority, then risk, then unblocking count, then id.
- Licence: MIT for Kahnban, with third-party MIT notices.
- Learnings are captured in `core.reject` and `core.escalate` (every caller), not in the runner, so this work does not collide with KB-011 in `runner.py`.

## Edge cases
| Scenario | Expected behaviour | Test that proves it |
| :--- | :--- | :--- |
| A dependent ticket is listed before its dependency in backlog | The dependency is refined first; the dependent is never offered while waiting | Dispatcher unit test (R13) |
| `depends_on` names a ticket that does not exist | The ticket waits; idle names "missing KB-99"; lint BL09 already errors | Dispatcher test (R14) |
| A cycle KB-3 → KB-5 → KB-3 | Both wait; idle names the cycle; lint reports it | Dispatcher and lint tests (R14, R15) |
| A ticket depends on itself | Treated as a cycle of length 1 | Lint test (R15) |
| Every open ticket is waiting | `next` reports idle, never empty or crashing | Dispatcher test (R14) |
| `priority: urgent` (invalid) | Lint warns; dispatch sorts it as `normal` | Lint and dispatcher tests (R16) |
| Equal priority, risk and unblocking count | Ticket id decides, deterministically | Dispatcher test (R17) |
| The learnings dir is unwritable during `reject` | The ticket still moves back to in-progress; a warning is printed | Core test (R21) |
| The same rejection reason recurs on two tickets | One learning with 2 occurrences | Learnings test (R20) |
| A harness dir holds a user's own skill named `tdd` | `skills install` leaves it; it only prunes what its lock says it installed | Skills test (R8) |
| An upstream skill renamed or removed after the pinned commit | Not applicable: no auto-sync; the pinned commit is the source | n/a (R7 records it) |
| Ingest of a document with no `## Requirements` | No requirements warning | Ingest test (R19) |

## Tickets
Left for `/kb-to-tickets` after approval.
