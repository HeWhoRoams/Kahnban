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
One `###` item per ticket. Wide tickets (the skill set) run under a temporarily raised
`max_blast_radius_files`; see the Log of the commit that raised it.

### Localize every shipped skill under the kb- prefix
- Files: `src/kahnban/templates/skills/change-impact/SKILL.md`, `src/kahnban/templates/skills/code-review/SKILL.md`, `src/kahnban/templates/skills/coder-agent/SKILL.md`, `src/kahnban/templates/skills/create-verification-skill/SKILL.md`, `src/kahnban/templates/skills/factory-mode/SKILL.md`, `src/kahnban/templates/skills/grill-with-docs/SKILL.md`, `src/kahnban/templates/skills/harvest-learnings/SKILL.md`, `src/kahnban/templates/skills/how/SKILL.md`, `src/kahnban/templates/skills/no-comments/SKILL.md`, `src/kahnban/templates/skills/principle-boundary-discipline/SKILL.md`, `src/kahnban/templates/skills/principle-encode-lessons-in-structure/SKILL.md`, `src/kahnban/templates/skills/principle-fix-root-causes/SKILL.md`, `src/kahnban/templates/skills/principle-guard-the-context-window/SKILL.md`, `src/kahnban/templates/skills/principle-laziness-protocol/SKILL.md`, `src/kahnban/templates/skills/principle-model-the-domain/SKILL.md`, `src/kahnban/templates/skills/principle-never-block-on-the-human/SKILL.md`, `src/kahnban/templates/skills/principle-prove-it-works/SKILL.md`, `src/kahnban/templates/skills/principle-sequence-verifiable-units/SKILL.md`, `src/kahnban/templates/skills/principle-subtract-before-you-add/SKILL.md`, `src/kahnban/templates/skills/qa-reviewer-agent/SKILL.md`, `src/kahnban/templates/skills/reflect/SKILL.md`, `src/kahnban/templates/skills/setup-kahnban-skills/SKILL.md`, `src/kahnban/templates/skills/tdd/SKILL.md`, `src/kahnban/templates/skills/to-spec/SKILL.md`, `src/kahnban/templates/skills/to-tickets/SKILL.md`, `src/kahnban/templates/skills/unslop/SKILL.md`, `src/kahnban/templates/skills/why/SKILL.md`, `.agents/skills/change-impact/SKILL.md`, `.agents/skills/code-review/SKILL.md`, `.agents/skills/coder-agent/SKILL.md`, `.agents/skills/create-verification-skill/SKILL.md`, `.agents/skills/factory-mode/SKILL.md`, `.agents/skills/grill-with-docs/SKILL.md`, `.agents/skills/harvest-learnings/SKILL.md`, `.agents/skills/how/SKILL.md`, `.agents/skills/no-comments/SKILL.md`, `.agents/skills/principle-boundary-discipline/SKILL.md`, `.agents/skills/principle-encode-lessons-in-structure/SKILL.md`, `.agents/skills/principle-fix-root-causes/SKILL.md`, `.agents/skills/principle-guard-the-context-window/SKILL.md`, `.agents/skills/principle-laziness-protocol/SKILL.md`, `.agents/skills/principle-model-the-domain/SKILL.md`, `.agents/skills/principle-never-block-on-the-human/SKILL.md`, `.agents/skills/principle-prove-it-works/SKILL.md`, `.agents/skills/principle-sequence-verifiable-units/SKILL.md`, `.agents/skills/principle-subtract-before-you-add/SKILL.md`, `.agents/skills/qa-reviewer-agent/SKILL.md`, `.agents/skills/reflect/SKILL.md`, `.agents/skills/setup-kahnban-skills/SKILL.md`, `.agents/skills/tdd/SKILL.md`, `.agents/skills/to-spec/SKILL.md`, `.agents/skills/to-tickets/SKILL.md`, `.agents/skills/unslop/SKILL.md`, `.agents/skills/why/SKILL.md`, `.claude/skills/change-impact/SKILL.md`, `.claude/skills/code-review/SKILL.md`, `.claude/skills/coder-agent/SKILL.md`, `.claude/skills/create-verification-skill/SKILL.md`, `.claude/skills/factory-mode/SKILL.md`, `.claude/skills/grill-with-docs/SKILL.md`, `.claude/skills/harvest-learnings/SKILL.md`, `.claude/skills/how/SKILL.md`, `.claude/skills/no-comments/SKILL.md`, `.claude/skills/principle-boundary-discipline/SKILL.md`, `.claude/skills/principle-encode-lessons-in-structure/SKILL.md`, `.claude/skills/principle-fix-root-causes/SKILL.md`, `.claude/skills/principle-guard-the-context-window/SKILL.md`, `.claude/skills/principle-laziness-protocol/SKILL.md`, `.claude/skills/principle-model-the-domain/SKILL.md`, `.claude/skills/principle-never-block-on-the-human/SKILL.md`, `.claude/skills/principle-prove-it-works/SKILL.md`, `.claude/skills/principle-sequence-verifiable-units/SKILL.md`, `.claude/skills/principle-subtract-before-you-add/SKILL.md`, `.claude/skills/qa-reviewer-agent/SKILL.md`, `.claude/skills/reflect/SKILL.md`, `.claude/skills/setup-kahnban-skills/SKILL.md`, `.claude/skills/tdd/SKILL.md`, `.claude/skills/to-spec/SKILL.md`, `.claude/skills/to-tickets/SKILL.md`, `.claude/skills/unslop/SKILL.md`, `.claude/skills/why/SKILL.md`, `adapters/skills/change-impact/SKILL.md`, `adapters/skills/code-review/SKILL.md`, `adapters/skills/coder-agent/SKILL.md`, `adapters/skills/create-verification-skill/SKILL.md`, `adapters/skills/factory-mode/SKILL.md`, `adapters/skills/grill-with-docs/SKILL.md`, `adapters/skills/harvest-learnings/SKILL.md`, `adapters/skills/how/SKILL.md`, `adapters/skills/no-comments/SKILL.md`, `adapters/skills/principle-boundary-discipline/SKILL.md`, `adapters/skills/principle-encode-lessons-in-structure/SKILL.md`, `adapters/skills/principle-fix-root-causes/SKILL.md`, `adapters/skills/principle-guard-the-context-window/SKILL.md`, `adapters/skills/principle-laziness-protocol/SKILL.md`, `adapters/skills/principle-model-the-domain/SKILL.md`, `adapters/skills/principle-never-block-on-the-human/SKILL.md`, `adapters/skills/principle-prove-it-works/SKILL.md`, `adapters/skills/principle-sequence-verifiable-units/SKILL.md`, `adapters/skills/principle-subtract-before-you-add/SKILL.md`, `adapters/skills/qa-reviewer-agent/SKILL.md`, `adapters/skills/reflect/SKILL.md`, `adapters/skills/setup-kahnban-skills/SKILL.md`, `adapters/skills/tdd/SKILL.md`, `adapters/skills/to-spec/SKILL.md`, `adapters/skills/to-tickets/SKILL.md`, `adapters/skills/unslop/SKILL.md`, `adapters/skills/why/SKILL.md`, `src/kahnban/templates/skills/kb-change-impact/SKILL.md`, `.agents/skills/kb-change-impact/SKILL.md`, `.claude/skills/kb-change-impact/SKILL.md`, `adapters/skills/kb-change-impact/SKILL.md`, `src/kahnban/templates/skills/kb-code-review/SKILL.md`, `.agents/skills/kb-code-review/SKILL.md`, `.claude/skills/kb-code-review/SKILL.md`, `adapters/skills/kb-code-review/SKILL.md`, `src/kahnban/templates/skills/kb-coder-agent/SKILL.md`, `.agents/skills/kb-coder-agent/SKILL.md`, `.claude/skills/kb-coder-agent/SKILL.md`, `adapters/skills/kb-coder-agent/SKILL.md`, `src/kahnban/templates/skills/kb-create-verification-skill/SKILL.md`, `.agents/skills/kb-create-verification-skill/SKILL.md`, `.claude/skills/kb-create-verification-skill/SKILL.md`, `adapters/skills/kb-create-verification-skill/SKILL.md`, `src/kahnban/templates/skills/kb-factory-mode/SKILL.md`, `.agents/skills/kb-factory-mode/SKILL.md`, `.claude/skills/kb-factory-mode/SKILL.md`, `adapters/skills/kb-factory-mode/SKILL.md`, `src/kahnban/templates/skills/kb-grill-with-docs/SKILL.md`, `.agents/skills/kb-grill-with-docs/SKILL.md`, `.claude/skills/kb-grill-with-docs/SKILL.md`, `adapters/skills/kb-grill-with-docs/SKILL.md`, `src/kahnban/templates/skills/kb-harvest-learnings/SKILL.md`, `.agents/skills/kb-harvest-learnings/SKILL.md`, `.claude/skills/kb-harvest-learnings/SKILL.md`, `adapters/skills/kb-harvest-learnings/SKILL.md`, `src/kahnban/templates/skills/kb-how/SKILL.md`, `.agents/skills/kb-how/SKILL.md`, `.claude/skills/kb-how/SKILL.md`, `adapters/skills/kb-how/SKILL.md`, `src/kahnban/templates/skills/kb-no-comments/SKILL.md`, `.agents/skills/kb-no-comments/SKILL.md`, `.claude/skills/kb-no-comments/SKILL.md`, `adapters/skills/kb-no-comments/SKILL.md`, `src/kahnban/templates/skills/kb-principle-boundary-discipline/SKILL.md`, `.agents/skills/kb-principle-boundary-discipline/SKILL.md`, `.claude/skills/kb-principle-boundary-discipline/SKILL.md`, `adapters/skills/kb-principle-boundary-discipline/SKILL.md`, `src/kahnban/templates/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `.agents/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `.claude/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `adapters/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `src/kahnban/templates/skills/kb-principle-fix-root-causes/SKILL.md`, `.agents/skills/kb-principle-fix-root-causes/SKILL.md`, `.claude/skills/kb-principle-fix-root-causes/SKILL.md`, `adapters/skills/kb-principle-fix-root-causes/SKILL.md`, `src/kahnban/templates/skills/kb-principle-guard-the-context-window/SKILL.md`, `.agents/skills/kb-principle-guard-the-context-window/SKILL.md`, `.claude/skills/kb-principle-guard-the-context-window/SKILL.md`, `adapters/skills/kb-principle-guard-the-context-window/SKILL.md`, `src/kahnban/templates/skills/kb-principle-laziness-protocol/SKILL.md`, `.agents/skills/kb-principle-laziness-protocol/SKILL.md`, `.claude/skills/kb-principle-laziness-protocol/SKILL.md`, `adapters/skills/kb-principle-laziness-protocol/SKILL.md`, `src/kahnban/templates/skills/kb-principle-model-the-domain/SKILL.md`, `.agents/skills/kb-principle-model-the-domain/SKILL.md`, `.claude/skills/kb-principle-model-the-domain/SKILL.md`, `adapters/skills/kb-principle-model-the-domain/SKILL.md`, `src/kahnban/templates/skills/kb-principle-never-block-on-the-human/SKILL.md`, `.agents/skills/kb-principle-never-block-on-the-human/SKILL.md`, `.claude/skills/kb-principle-never-block-on-the-human/SKILL.md`, `adapters/skills/kb-principle-never-block-on-the-human/SKILL.md`, `src/kahnban/templates/skills/kb-principle-prove-it-works/SKILL.md`, `.agents/skills/kb-principle-prove-it-works/SKILL.md`, `.claude/skills/kb-principle-prove-it-works/SKILL.md`, `adapters/skills/kb-principle-prove-it-works/SKILL.md`, `src/kahnban/templates/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `.agents/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `.claude/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `adapters/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `src/kahnban/templates/skills/kb-principle-subtract-before-you-add/SKILL.md`, `.agents/skills/kb-principle-subtract-before-you-add/SKILL.md`, `.claude/skills/kb-principle-subtract-before-you-add/SKILL.md`, `adapters/skills/kb-principle-subtract-before-you-add/SKILL.md`, `src/kahnban/templates/skills/kb-qa-reviewer-agent/SKILL.md`, `.agents/skills/kb-qa-reviewer-agent/SKILL.md`, `.claude/skills/kb-qa-reviewer-agent/SKILL.md`, `adapters/skills/kb-qa-reviewer-agent/SKILL.md`, `src/kahnban/templates/skills/kb-reflect/SKILL.md`, `.agents/skills/kb-reflect/SKILL.md`, `.claude/skills/kb-reflect/SKILL.md`, `adapters/skills/kb-reflect/SKILL.md`, `src/kahnban/templates/skills/kb-setup-kahnban-skills/SKILL.md`, `.agents/skills/kb-setup-kahnban-skills/SKILL.md`, `.claude/skills/kb-setup-kahnban-skills/SKILL.md`, `adapters/skills/kb-setup-kahnban-skills/SKILL.md`, `src/kahnban/templates/skills/kb-tdd/SKILL.md`, `.agents/skills/kb-tdd/SKILL.md`, `.claude/skills/kb-tdd/SKILL.md`, `adapters/skills/kb-tdd/SKILL.md`, `src/kahnban/templates/skills/kb-to-spec/SKILL.md`, `.agents/skills/kb-to-spec/SKILL.md`, `.claude/skills/kb-to-spec/SKILL.md`, `adapters/skills/kb-to-spec/SKILL.md`, `src/kahnban/templates/skills/kb-to-tickets/SKILL.md`, `.agents/skills/kb-to-tickets/SKILL.md`, `.claude/skills/kb-to-tickets/SKILL.md`, `adapters/skills/kb-to-tickets/SKILL.md`, `src/kahnban/templates/skills/kb-unslop/SKILL.md`, `.agents/skills/kb-unslop/SKILL.md`, `.claude/skills/kb-unslop/SKILL.md`, `adapters/skills/kb-unslop/SKILL.md`, `src/kahnban/templates/skills/kb-why/SKILL.md`, `.agents/skills/kb-why/SKILL.md`, `.claude/skills/kb-why/SKILL.md`, `adapters/skills/kb-why/SKILL.md`, `src/kahnban/templates/roles.json`, `src/kahnban/harnesses.py`, `src/kahnban/dispatcher.py`, `src/kahnban/runner.py`, `src/kahnban/learnings.py`, `src/kahnban/templates/agents.md`, `src/kahnban/templates/adr.md`, `src/kahnban/templates/glossary.md`, `.agents/AGENTS.md`, `.agents/templates/adr-template.md`, `.agents/templates/glossary-template.md`, `adapters/AGENTS.md`, `adapters/README.md`, `adapters/templates/adr-template.md`, `adapters/templates/glossary-template.md`, `README.md`, `docs/how-it-works.md`, `.claude/agents/kahnban-coder.md`, `.claude/agents/kahnban-curator.md`, `.claude/agents/kahnban-qa-reviewer.md`, `.claude/agents/kahnban-spec-analyst.md`, `tests/golden/agents/claude/kahnban-coder.md`, `tests/golden/agents/claude/kahnban-curator.md`, `tests/golden/agents/claude/kahnban-qa-reviewer.md`, `tests/golden/agents/claude/kahnban-spec-analyst.md`, `tests/golden/agents/cursor/kahnban-coder.md`, `tests/golden/agents/cursor/kahnban-curator.md`, `tests/golden/agents/cursor/kahnban-qa-reviewer.md`, `tests/golden/agents/cursor/kahnban-spec-analyst.md`, `tests/golden/agents/gemini/kahnban-coder.md`, `tests/golden/agents/gemini/kahnban-curator.md`, `tests/golden/agents/gemini/kahnban-qa-reviewer.md`, `tests/golden/agents/gemini/kahnban-spec-analyst.md`, `tests/sim/agent.py`, `tests/test_audit_fixes.py`, `tests/test_init_agentic.py`, `tests/test_roles.py`, `tests/test_runner_edges.py`, `tests/test_skills.py`, `tests/test_skills_sources.py`, `tests/test_contracts.py`, `.agents/skills.lock.json`, `tests/test_skill_localization.py`
- Covers: R1, R2, R11
- Depends on: none
- Acceptance:
  - [ ] every skill folder and frontmatter name under src/kahnban/templates/skills starts with kb- (test: `python -m pytest tests/test_skill_localization.py -q -k prefixed`)
  - [ ] no shipped skill, roles.json, agent template, AGENTS.md template, README.md or docs/how-it-works.md names an unprefixed shipped skill (test: `python -m pytest tests/test_skill_localization.py -q -k no_unprefixed_refs`)
  - [ ] no shipped file mentions the Lauren Tan Clustering Invariant, /implement-spec or /retro (test: `python -m pytest tests/test_skill_localization.py -q -k no_stale_attributions`)
  - [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)
- Validation: `python -m pytest tests/test_skill_localization.py -q`, `python tests/run_parallel.py -j 8`

### Record skill provenance in the lock
- Files: `src/kahnban/trust.py`, `src/kahnban/templates/provenance.json`, `.agents/skills.lock.json`, `tests/test_skill_provenance.py`
- Covers: R7
- Depends on: Localize every shipped skill under the kb- prefix
- Acceptance:
  - [ ] every shipped skill and agent has a provenance entry with source repository, upstream path and commit, or source kahnban for native ones (test: `python -m pytest tests/test_skill_provenance.py -q -k every_skill_has_provenance`)
  - [ ] writing the lock copies each provenance entry into .agents/skills.lock.json (test: `python -m pytest tests/test_skill_provenance.py -q -k lock_records_provenance`)
  - [ ] lock_problems reports a shipped skill with no provenance entry (test: `python -m pytest tests/test_skill_provenance.py -q -k missing_provenance_reported`)
- Validation: `python -m pytest tests/test_skill_provenance.py -q`, `python tests/run_parallel.py -j 8`

### Re-base the Pocock-derived skills on mattpocock/skills v1.3.2
- Files: `src/kahnban/templates/skills/kb-grill-with-docs/SKILL.md`, `.agents/skills/kb-grill-with-docs/SKILL.md`, `.claude/skills/kb-grill-with-docs/SKILL.md`, `adapters/skills/kb-grill-with-docs/SKILL.md`, `src/kahnban/templates/skills/kb-grilling/SKILL.md`, `.agents/skills/kb-grilling/SKILL.md`, `.claude/skills/kb-grilling/SKILL.md`, `adapters/skills/kb-grilling/SKILL.md`, `src/kahnban/templates/skills/kb-to-spec/SKILL.md`, `.agents/skills/kb-to-spec/SKILL.md`, `.claude/skills/kb-to-spec/SKILL.md`, `adapters/skills/kb-to-spec/SKILL.md`, `src/kahnban/templates/skills/kb-to-tickets/SKILL.md`, `.agents/skills/kb-to-tickets/SKILL.md`, `.claude/skills/kb-to-tickets/SKILL.md`, `adapters/skills/kb-to-tickets/SKILL.md`, `src/kahnban/templates/skills/kb-code-review/SKILL.md`, `.agents/skills/kb-code-review/SKILL.md`, `.claude/skills/kb-code-review/SKILL.md`, `adapters/skills/kb-code-review/SKILL.md`, `src/kahnban/templates/skills/kb-tdd/SKILL.md`, `src/kahnban/templates/skills/kb-tdd/mocking.md`, `src/kahnban/templates/skills/kb-tdd/tests.md`, `.agents/skills/kb-tdd/SKILL.md`, `.agents/skills/kb-tdd/mocking.md`, `.agents/skills/kb-tdd/tests.md`, `.claude/skills/kb-tdd/SKILL.md`, `.claude/skills/kb-tdd/mocking.md`, `.claude/skills/kb-tdd/tests.md`, `adapters/skills/kb-tdd/SKILL.md`, `adapters/skills/kb-tdd/mocking.md`, `adapters/skills/kb-tdd/tests.md`, `src/kahnban/templates/skills/kb-domain-modeling/SKILL.md`, `src/kahnban/templates/skills/kb-domain-modeling/ADR-FORMAT.md`, `src/kahnban/templates/skills/kb-domain-modeling/GLOSSARY-FORMAT.md`, `.agents/skills/kb-domain-modeling/SKILL.md`, `.agents/skills/kb-domain-modeling/ADR-FORMAT.md`, `.agents/skills/kb-domain-modeling/GLOSSARY-FORMAT.md`, `.claude/skills/kb-domain-modeling/SKILL.md`, `.claude/skills/kb-domain-modeling/ADR-FORMAT.md`, `.claude/skills/kb-domain-modeling/GLOSSARY-FORMAT.md`, `adapters/skills/kb-domain-modeling/SKILL.md`, `adapters/skills/kb-domain-modeling/ADR-FORMAT.md`, `adapters/skills/kb-domain-modeling/GLOSSARY-FORMAT.md`, `src/kahnban/templates/provenance.json`, `.agents/skills.lock.json`, `tests/test_skill_upstream_pocock.py`
- Covers: R4
- Depends on: Record skill provenance in the lock
- Acceptance:
  - [ ] kb-grilling and kb-domain-modeling (with ADR-FORMAT.md and GLOSSARY-FORMAT.md) are shipped and installed (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k new_skills_shipped`)
  - [ ] provenance for the seven skills names mattpocock/skills at v1.3.2 and each upstream path (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k provenance_pinned`)
  - [ ] each of the seven ends with a '## Kahnban adaptations' section listing every deviation from upstream, and nothing else differs (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k adaptations_declared`)
  - [ ] kb-to-tickets still requires exact file paths, the file cap, Covers R-ids and kahnban ingest (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k gate_rules_kept`)
  - [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)
- Validation: `python -m pytest tests/test_skill_upstream_pocock.py -q`, `python tests/run_parallel.py -j 8`

### Re-base the pstack-derived skills on cursor/plugins c742dd6
- Files: `src/kahnban/templates/skills/kb-principle-boundary-discipline/SKILL.md`, `.agents/skills/kb-principle-boundary-discipline/SKILL.md`, `.claude/skills/kb-principle-boundary-discipline/SKILL.md`, `adapters/skills/kb-principle-boundary-discipline/SKILL.md`, `src/kahnban/templates/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `.agents/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `.claude/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `adapters/skills/kb-principle-encode-lessons-in-structure/SKILL.md`, `src/kahnban/templates/skills/kb-principle-fix-root-causes/SKILL.md`, `.agents/skills/kb-principle-fix-root-causes/SKILL.md`, `.claude/skills/kb-principle-fix-root-causes/SKILL.md`, `adapters/skills/kb-principle-fix-root-causes/SKILL.md`, `src/kahnban/templates/skills/kb-principle-guard-the-context-window/SKILL.md`, `.agents/skills/kb-principle-guard-the-context-window/SKILL.md`, `.claude/skills/kb-principle-guard-the-context-window/SKILL.md`, `adapters/skills/kb-principle-guard-the-context-window/SKILL.md`, `src/kahnban/templates/skills/kb-principle-laziness-protocol/SKILL.md`, `.agents/skills/kb-principle-laziness-protocol/SKILL.md`, `.claude/skills/kb-principle-laziness-protocol/SKILL.md`, `adapters/skills/kb-principle-laziness-protocol/SKILL.md`, `src/kahnban/templates/skills/kb-principle-model-the-domain/SKILL.md`, `.agents/skills/kb-principle-model-the-domain/SKILL.md`, `.claude/skills/kb-principle-model-the-domain/SKILL.md`, `adapters/skills/kb-principle-model-the-domain/SKILL.md`, `src/kahnban/templates/skills/kb-principle-never-block-on-the-human/SKILL.md`, `.agents/skills/kb-principle-never-block-on-the-human/SKILL.md`, `.claude/skills/kb-principle-never-block-on-the-human/SKILL.md`, `adapters/skills/kb-principle-never-block-on-the-human/SKILL.md`, `src/kahnban/templates/skills/kb-principle-prove-it-works/SKILL.md`, `.agents/skills/kb-principle-prove-it-works/SKILL.md`, `.claude/skills/kb-principle-prove-it-works/SKILL.md`, `adapters/skills/kb-principle-prove-it-works/SKILL.md`, `src/kahnban/templates/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `.agents/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `.claude/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `adapters/skills/kb-principle-sequence-verifiable-units/SKILL.md`, `src/kahnban/templates/skills/kb-principle-subtract-before-you-add/SKILL.md`, `.agents/skills/kb-principle-subtract-before-you-add/SKILL.md`, `.claude/skills/kb-principle-subtract-before-you-add/SKILL.md`, `adapters/skills/kb-principle-subtract-before-you-add/SKILL.md`, `src/kahnban/templates/skills/kb-principle-build-the-lever/SKILL.md`, `.agents/skills/kb-principle-build-the-lever/SKILL.md`, `.claude/skills/kb-principle-build-the-lever/SKILL.md`, `adapters/skills/kb-principle-build-the-lever/SKILL.md`, `src/kahnban/templates/skills/kb-principle-redesign-from-first-principles/SKILL.md`, `.agents/skills/kb-principle-redesign-from-first-principles/SKILL.md`, `.claude/skills/kb-principle-redesign-from-first-principles/SKILL.md`, `adapters/skills/kb-principle-redesign-from-first-principles/SKILL.md`, `src/kahnban/templates/skills/kb-how/SKILL.md`, `src/kahnban/templates/skills/kb-how/references/explainer-prompt.md`, `src/kahnban/templates/skills/kb-how/references/explorer-prompt.md`, `.agents/skills/kb-how/SKILL.md`, `.agents/skills/kb-how/references/explainer-prompt.md`, `.agents/skills/kb-how/references/explorer-prompt.md`, `.claude/skills/kb-how/SKILL.md`, `.claude/skills/kb-how/references/explainer-prompt.md`, `.claude/skills/kb-how/references/explorer-prompt.md`, `adapters/skills/kb-how/SKILL.md`, `adapters/skills/kb-how/references/explainer-prompt.md`, `adapters/skills/kb-how/references/explorer-prompt.md`, `src/kahnban/templates/skills/kb-why/SKILL.md`, `src/kahnban/templates/skills/kb-why/references/epistemics.md`, `src/kahnban/templates/skills/kb-why/references/investigator-prompt.md`, `src/kahnban/templates/skills/kb-why/references/source-playbook.md`, `src/kahnban/templates/skills/kb-why/references/synthesizer-prompt.md`, `src/kahnban/templates/skills/kb-why/references/sources/code-archaeology.md`, `src/kahnban/templates/skills/kb-why/references/sources/databricks.md`, `src/kahnban/templates/skills/kb-why/references/sources/datadog.md`, `src/kahnban/templates/skills/kb-why/references/sources/incident-postmortem.md`, `src/kahnban/templates/skills/kb-why/references/sources/linear.md`, `src/kahnban/templates/skills/kb-why/references/sources/notion.md`, `src/kahnban/templates/skills/kb-why/references/sources/sentry.md`, `src/kahnban/templates/skills/kb-why/references/sources/slack.md`, `.agents/skills/kb-why/SKILL.md`, `.agents/skills/kb-why/references/epistemics.md`, `.agents/skills/kb-why/references/investigator-prompt.md`, `.agents/skills/kb-why/references/source-playbook.md`, `.agents/skills/kb-why/references/synthesizer-prompt.md`, `.agents/skills/kb-why/references/sources/code-archaeology.md`, `.agents/skills/kb-why/references/sources/databricks.md`, `.agents/skills/kb-why/references/sources/datadog.md`, `.agents/skills/kb-why/references/sources/incident-postmortem.md`, `.agents/skills/kb-why/references/sources/linear.md`, `.agents/skills/kb-why/references/sources/notion.md`, `.agents/skills/kb-why/references/sources/sentry.md`, `.agents/skills/kb-why/references/sources/slack.md`, `.claude/skills/kb-why/SKILL.md`, `.claude/skills/kb-why/references/epistemics.md`, `.claude/skills/kb-why/references/investigator-prompt.md`, `.claude/skills/kb-why/references/source-playbook.md`, `.claude/skills/kb-why/references/synthesizer-prompt.md`, `.claude/skills/kb-why/references/sources/code-archaeology.md`, `.claude/skills/kb-why/references/sources/databricks.md`, `.claude/skills/kb-why/references/sources/datadog.md`, `.claude/skills/kb-why/references/sources/incident-postmortem.md`, `.claude/skills/kb-why/references/sources/linear.md`, `.claude/skills/kb-why/references/sources/notion.md`, `.claude/skills/kb-why/references/sources/sentry.md`, `.claude/skills/kb-why/references/sources/slack.md`, `adapters/skills/kb-why/SKILL.md`, `adapters/skills/kb-why/references/epistemics.md`, `adapters/skills/kb-why/references/investigator-prompt.md`, `adapters/skills/kb-why/references/source-playbook.md`, `adapters/skills/kb-why/references/synthesizer-prompt.md`, `adapters/skills/kb-why/references/sources/code-archaeology.md`, `adapters/skills/kb-why/references/sources/databricks.md`, `adapters/skills/kb-why/references/sources/datadog.md`, `adapters/skills/kb-why/references/sources/incident-postmortem.md`, `adapters/skills/kb-why/references/sources/linear.md`, `adapters/skills/kb-why/references/sources/notion.md`, `adapters/skills/kb-why/references/sources/sentry.md`, `adapters/skills/kb-why/references/sources/slack.md`, `src/kahnban/templates/skills/kb-no-comments/SKILL.md`, `.agents/skills/kb-no-comments/SKILL.md`, `.claude/skills/kb-no-comments/SKILL.md`, `adapters/skills/kb-no-comments/SKILL.md`, `src/kahnban/templates/skills/kb-unslop/SKILL.md`, `.agents/skills/kb-unslop/SKILL.md`, `.claude/skills/kb-unslop/SKILL.md`, `adapters/skills/kb-unslop/SKILL.md`, `src/kahnban/templates/skills/kb-change-impact/SKILL.md`, `.agents/skills/kb-change-impact/SKILL.md`, `.claude/skills/kb-change-impact/SKILL.md`, `adapters/skills/kb-change-impact/SKILL.md`, `src/kahnban/templates/skills/kb-create-verification-skill/SKILL.md`, `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/README.md`, `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`, `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/search.md`, `.agents/skills/kb-create-verification-skill/SKILL.md`, `.agents/skills/kb-create-verification-skill/references/feature-map-example/README.md`, `.agents/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`, `.agents/skills/kb-create-verification-skill/references/feature-map-example/search.md`, `.claude/skills/kb-create-verification-skill/SKILL.md`, `.claude/skills/kb-create-verification-skill/references/feature-map-example/README.md`, `.claude/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`, `.claude/skills/kb-create-verification-skill/references/feature-map-example/search.md`, `adapters/skills/kb-create-verification-skill/SKILL.md`, `adapters/skills/kb-create-verification-skill/references/feature-map-example/README.md`, `adapters/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`, `adapters/skills/kb-create-verification-skill/references/feature-map-example/search.md`, `src/kahnban/templates/skills/kb-show-me-your-work/SKILL.md`, `src/kahnban/templates/skills/kb-show-me-your-work/references/decision-log-template.tsv`, `src/kahnban/templates/skills/kb-show-me-your-work/scripts/log.sh`, `.agents/skills/kb-show-me-your-work/SKILL.md`, `.agents/skills/kb-show-me-your-work/references/decision-log-template.tsv`, `.agents/skills/kb-show-me-your-work/scripts/log.sh`, `.claude/skills/kb-show-me-your-work/SKILL.md`, `.claude/skills/kb-show-me-your-work/references/decision-log-template.tsv`, `.claude/skills/kb-show-me-your-work/scripts/log.sh`, `adapters/skills/kb-show-me-your-work/SKILL.md`, `adapters/skills/kb-show-me-your-work/references/decision-log-template.tsv`, `adapters/skills/kb-show-me-your-work/scripts/log.sh`, `src/kahnban/skills.py`, `src/kahnban/templates/provenance.json`, `.agents/skills.lock.json`, `tests/test_skill_upstream_pstack.py`
- Covers: R5
- Depends on: Re-base the Pocock-derived skills on mattpocock/skills v1.3.2
- Acceptance:
  - [ ] kb-principle-build-the-lever, kb-principle-redesign-from-first-principles and kb-show-me-your-work are shipped (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k missing_skills_imported`)
  - [ ] provenance for every pstack-derived skill names cursor/plugins at c742dd6 and its upstream path (blast-radius for kb-change-impact) (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k provenance_pinned`)
  - [ ] supporting files in nested folders (references/, scripts/) are installed with their skill (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k nested_files_installed`)
  - [ ] no shipped skill mentions poteto-mode (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k no_poteto_mode`)
  - [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)
- Validation: `python -m pytest tests/test_skill_upstream_pstack.py -q`, `python tests/run_parallel.py -j 8`

### Ship the kahnban-comment-sicko helper agent
- Files: `src/kahnban/harnesses.py`, `src/kahnban/templates/agents/comment-sicko.md`, `.claude/agents/kahnban-comment-sicko.md`, `src/kahnban/templates/skills/kb-no-comments/SKILL.md`, `.agents/skills/kb-no-comments/SKILL.md`, `.claude/skills/kb-no-comments/SKILL.md`, `adapters/skills/kb-no-comments/SKILL.md`, `src/kahnban/templates/provenance.json`, `.agents/skills.lock.json`, `tests/test_comment_sicko_agent.py`
- Covers: R6
- Depends on: Re-base the pstack-derived skills on cursor/plugins c742dd6
- Acceptance:
  - [ ] kahnban skills install for the claude harness writes .claude/agents/kahnban-comment-sicko.md from pstack's comment-sicko (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k agent_installed`)
  - [ ] kb-no-comments spawns subagent_type kahnban-comment-sicko (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k skill_spawns_agent`)
  - [ ] the agent's provenance names cursor/plugins at c742dd6 (test: `python -m pytest tests/test_comment_sicko_agent.py -q -k agent_provenance`)
- Validation: `python -m pytest tests/test_comment_sicko_agent.py -q`, `python tests/run_parallel.py -j 8`

### skills check catches bold and subagent references
- Files: `src/kahnban/skills_check.py`, `tests/test_skills_check_refs.py`
- Covers: R3
- Depends on: Ship the kahnban-comment-sicko helper agent
- Acceptance:
  - [ ] a '**name** skill' reference to an unshipped skill is reported (test: `python -m pytest tests/test_skills_check_refs.py -q -k bold_skill_ref`)
  - [ ] a '**name** principle skill' reference is resolved to kb-principle-name and reported when missing (test: `python -m pytest tests/test_skills_check_refs.py -q -k bold_principle_ref`)
  - [ ] a subagent_type: "name" reference to an unshipped agent is reported (test: `python -m pytest tests/test_skills_check_refs.py -q -k subagent_ref`)
  - [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)
- Validation: `python -m pytest tests/test_skills_check_refs.py -q`, `python tests/run_parallel.py -j 8`

### skills install prunes skills it no longer ships
- Files: `src/kahnban/skills.py`, `tests/test_skills_prune.py`
- Covers: R8
- Depends on: Re-base the pstack-derived skills on cursor/plugins c742dd6
- Acceptance:
  - [ ] a skill or agent the previous install wrote (per the lock) and no longer shipped is removed from each harness dir (test: `python -m pytest tests/test_skills_prune.py -q -k stale_removed`)
  - [ ] a skill the install never wrote is left untouched (test: `python -m pytest tests/test_skills_prune.py -q -k user_skill_kept`)
- Validation: `python -m pytest tests/test_skills_prune.py -q`, `python tests/run_parallel.py -j 8`

### Upstream installs never overwrite kb- skills
- Files: `src/kahnban/skills.py`, `tests/test_skills_sources.py`
- Covers: R9
- Depends on: skills install prunes skills it no longer ships
- Acceptance:
  - [ ] installing with --source mattpocock (npx stubbed) leaves every kb- skill byte-identical (test: `python -m pytest tests/test_skills_sources.py -q -k kb_skills_untouched`)
- Validation: `python -m pytest tests/test_skills_sources.py -q`, `python tests/run_parallel.py -j 8`

### Add the MIT licence with third-party notices
- Files: `LICENSE`, `THIRD_PARTY_NOTICES.md`, `tests/test_license.py`
- Covers: R10
- Depends on: none
- Acceptance:
  - [ ] LICENSE is the MIT licence naming Tim Niles (test: `python -m pytest tests/test_license.py -q -k mit_license`)
  - [ ] THIRD_PARTY_NOTICES.md reproduces the MIT notices of cursor/plugins (pstack) and mattpocock/skills (test: `python -m pytest tests/test_license.py -q -k third_party_notices`)
- Validation: `python -m pytest tests/test_license.py -q`, `python tests/run_parallel.py -j 8`

### Declare the licence in pyproject.toml
- Files: `pyproject.toml`, `tests/test_license.py`
- Covers: R10
- Depends on: Add the MIT licence with third-party notices
- Acceptance:
  - [ ] pyproject.toml declares the MIT licence and its license file (test: `python -m pytest tests/test_license.py -q -k pyproject_declares_license`)
- Validation: `python -m pytest tests/test_license.py -q`, `python tests/run_parallel.py -j 8`

### lint help names the real rule range
- Files: `src/kahnban/cli.py`, `tests/test_lint_help.py`
- Covers: R12
- Depends on: none
- Acceptance:
  - [ ] kahnban lint --help names the first and last rule ids of the linter's rule table (test: `python -m pytest tests/test_lint_help.py -q -k help_range_from_table`)
- Validation: `python -m pytest tests/test_lint_help.py -q`, `python tests/run_parallel.py -j 8`

### Status docs stop making stale claims
- Files: `IMPLEMENTATION_STATUS.md`, `NEXT_STEPS.md`, `tests/test_status_docs.py`
- Covers: R12
- Depends on: none
- Acceptance:
  - [ ] neither doc states a hard-coded test count (test: `python -m pytest tests/test_status_docs.py -q -k no_test_count`)
  - [ ] neither doc describes kahnban run as sequential or one ticket at a time (test: `python -m pytest tests/test_status_docs.py -q -k no_sequential_claim`)
- Validation: `python -m pytest tests/test_status_docs.py -q`, `python tests/run_parallel.py -j 8`

### Dispatch waits on unfinished dependencies
- Files: `src/kahnban/dispatcher.py`, `src/kahnban/core.py`, `tests/test_dispatch_dependencies.py`
- Covers: R13, R14
- Depends on: none
- Acceptance:
  - [ ] a backlog ticket listed before its unfinished dependency is never offered; the dependency is (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k dependent_waits`)
  - [ ] a ticket with a missing dependency or on a cycle (self-dependency included) is never offered (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k missing_and_cycle_wait`)
  - [ ] when only waiting tickets remain, next reports idle naming each one and its blocker: id, missing id or cycle (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k idle_names_blockers`)
- Validation: `python -m pytest tests/test_dispatch_dependencies.py -q`, `python tests/run_parallel.py -j 8`

### Lint reports dependency cycles
- Files: `src/kahnban/linter.py`, `tests/test_lint_cycles.py`
- Covers: R15
- Depends on: Dispatch waits on unfinished dependencies
- Acceptance:
  - [ ] kahnban lint reports a depends_on cycle under a new rule id, naming the cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k cycle_reported`)
  - [ ] a self-dependency is reported as a cycle (test: `python -m pytest tests/test_lint_cycles.py -q -k self_dependency`)
- Validation: `python -m pytest tests/test_lint_cycles.py -q`, `python tests/run_parallel.py -j 8`

### Lint priority and risk values
- Files: `src/kahnban/linter.py`, `src/kahnban/templates/ticket.md`, `tests/test_lint_priority_risk.py`
- Covers: R16
- Depends on: Lint reports dependency cycles
- Acceptance:
  - [ ] the ticket template documents priority: normal and risk: medium (test: `python -m pytest tests/test_lint_priority_risk.py -q -k template_fields`)
  - [ ] an invalid priority or risk value is a lint warning, not an error (test: `python -m pytest tests/test_lint_priority_risk.py -q -k invalid_value_warns`)
- Validation: `python -m pytest tests/test_lint_priority_risk.py -q`, `python tests/run_parallel.py -j 8`

### Dispatch by priority, risk and unblocking
- Files: `src/kahnban/dispatcher.py`, `tests/test_dispatch_order.py`
- Covers: R16, R17
- Depends on: Dispatch waits on unfinished dependencies
- Acceptance:
  - [ ] intake and claim candidates are ordered by priority, then risk, then transitive dependents (most first), then id (test: `python -m pytest tests/test_dispatch_order.py -q -k sort_order`)
  - [ ] a missing or invalid priority/risk sorts as normal/medium (test: `python -m pytest tests/test_dispatch_order.py -q -k defaults`)
  - [ ] ties fall back to ticket id deterministically (test: `python -m pytest tests/test_dispatch_order.py -q -k id_tiebreak`)
- Validation: `python -m pytest tests/test_dispatch_order.py -q`, `python tests/run_parallel.py -j 8`

### Ingest report shows spec with covers
- Files: `src/kahnban/ingest.py`, `tests/test_ingest_traceability.py`
- Covers: R18
- Depends on: none
- Acceptance:
  - [ ] the dry-run text report shows each draft's spec and covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k text_report`)
  - [ ] the --json report has spec and covers per draft (test: `python -m pytest tests/test_ingest_traceability.py -q -k json_report`)
- Validation: `python -m pytest tests/test_ingest_traceability.py -q`, `python tests/run_parallel.py -j 8`

### Ingest warns on traceability and size problems
- Files: `src/kahnban/ingest.py`, `tests/test_ingest_traceability.py`
- Covers: R19
- Depends on: Ingest report shows spec with covers
- Acceptance:
  - [ ] warns on a covers id the spec does not define (test: `python -m pytest tests/test_ingest_traceability.py -q -k unknown_covers`)
  - [ ] warns on a spec requirement no draft covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k uncovered_requirement`)
  - [ ] warns on an unapproved spec (test: `python -m pytest tests/test_ingest_traceability.py -q -k unapproved_spec`)
  - [ ] warns on a draft blast radius that is empty or over max_blast_radius_files (test: `python -m pytest tests/test_ingest_traceability.py -q -k radius_size`)
  - [ ] warns when a non-spec document's ## Requirements section produced no covers, and not when it has none (test: `python -m pytest tests/test_ingest_traceability.py -q -k skipped_requirements`)
  - [ ] ingest still exits 0 when it only warns (test: `python -m pytest tests/test_ingest_traceability.py -q -k warnings_exit_zero`)
- Validation: `python -m pytest tests/test_ingest_traceability.py -q`, `python tests/run_parallel.py -j 8`

### Reject and escalate capture learnings
- Files: `src/kahnban/core.py`, `tests/test_learning_capture.py`
- Covers: R20, R21
- Depends on: Dispatch waits on unfinished dependencies
- Acceptance:
  - [ ] reject captures a learning naming the ticket and the reason (test: `python -m pytest tests/test_learning_capture.py -q -k reject_captures`)
  - [ ] escalate captures a learning naming the ticket and the reason (test: `python -m pytest tests/test_learning_capture.py -q -k escalate_captures`)
  - [ ] the same cause on two tickets clusters into one learning with two occurrences (test: `python -m pytest tests/test_learning_capture.py -q -k clusters`)
  - [ ] when capture fails, reject and escalate still transition and print a warning (test: `python -m pytest tests/test_learning_capture.py -q -k capture_failure_nonfatal`)
- Validation: `python -m pytest tests/test_learning_capture.py -q`, `python tests/run_parallel.py -j 8`
