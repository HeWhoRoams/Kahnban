# Audit 3: Kahnban vs GitHub Spec Kit

Date: 2026-10-29. Kahnban at `a38a0c0` (engine 1.4.0). Spec Kit at `main` (latest release v1.2.5, 2026-10-28, per `api.github.com/repos/github/spec-kit/releases`).
Scope: how well each one goes from idea to spec, clarification, plan, tasks, consistency analysis, implementation and merge, and how close Kahnban is to the north star: "hand it a whole spec and it swarms it to done."
Method: I read primary sources for Spec Kit (raw files on GitHub, listed in §6) and the Kahnban source, and ran `kahnban ingest --dry-run` on three sample documents. The dry runs wrote nothing (`git status` stayed clean).

---

## 1. Spec Kit in brief

Spec Kit is a set of prompt templates plus small scripts that an AI agent runs one stage at a time. A human reviews the output between stages. The README (v1.2.x) names the core commands with hyphens (`/speckit-constitution`, `-specify`, `-plan`, `-tasks`, `-implement`, `-converge`). The README sends clarify, checklist and analyze to the "SDD walkthrough" [README].

| Command | Artifact | Key mechanics (primary source) |
|---|---|---|
| constitution | `.specify/memory/constitution.md` | Principles use MUST/SHOULD and must be "declarative, testable". Amendments get a semver bump and a Sync Impact Report. Other commands read the constitution at runtime [commands/constitution.md]. Nine articles: library-first, CLI, **test-first**, simplicity (≤3 projects), anti-abstraction, integration-first [spec-driven.md]. |
| specify | `specs/NNN-short-name/spec.md` + `checklists/requirements.md` | A `before_specify` git hook creates the branch. The spec has no tech detail. **"Maximum 3 [NEEDS CLARIFICATION] markers"**, and reasonable defaults are recorded in Assumptions. A quality-checklist loop runs at most 3 iterations [commands/specify.md]. Template: prioritised user stories (P1, P2, …) that each have an "Independent Test", Given/When/Then scenarios, `FR-###`, Key Entities, `SC-###` success criteria, Edge Cases, Assumptions [spec-template.md]. |
| clarify | `## Clarifications / ### Session <date>` in spec.md | Scans a 10-category ambiguity taxonomy and rates each category Clear, Partial or Missing. **Hard cap of 5 questions**, asked one at a time. Each question is multiple choice with a **Recommended** option, or a ≤5-word answer with a Suggested one. Each answer is written back into the relevant spec section, replacing any contradictory text [commands/clarify.md]. |
| plan | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | The Constitution Check is a "GATE: Must pass before Phase 0 research. Re-check after Phase 1 design". Violations must be justified in a Complexity Tracking table. Each NEEDS CLARIFICATION item becomes a research task (Decision / Rationale / Alternatives) [commands/plan.md, plan-template.md]. |
| tasks | `tasks.md` | Format: `- [ ] T012 [P] [US1] Create User model in src/models/user.py`. Phases are Setup → Foundational (blocking) → one phase per user story in priority order → Polish. `[P]` means "different files, no dependency on incomplete tasks". Data-model constraints are quoted verbatim into tasks. Tests are written only if the spec asks for them. The output includes a dependency graph, an MVP scope (US1) and the parallel opportunities [commands/tasks.md, tasks-template.md]. |
| analyze | report only | **"STRICTLY READ-ONLY"**. Six detection passes: duplication, ambiguity, underspecification, constitution alignment, coverage gaps (FR/SC → task, and orphan tasks), inconsistency. Severities run from CRITICAL to LOW, and any constitution conflict is CRITICAL. Output: a coverage table and coverage % [commands/analyze.md]. |
| checklist | `checklists/*.md` | "Unit tests for English": items test the quality of the requirements, never the implementation. Format `- [ ] CHK001 … [Completeness] [Spec §X.Y]`. At least 80% of items must carry a traceability reference [commands/checklist.md]. |
| implement | code; tasks ticked `[X]` | Gate: if any checklist item is unchecked, it stops and asks. Runs phase by phase, TDD order, `[P]` tasks together. On a failure it halts, except a failed `[P]` task, which does not stop the other `[P]` tasks. **No commit, branch or merge logic** [commands/implement.md]. |
| converge | appends `## Phase N: Convergence` to tasks.md | Reads spec, plan, tasks and the constitution against the current code. "Completion claims are not evidence." Gap types: missing, partial, contradicts, unrequested. The loop is implement → converge until the verdict is `converged`, at which point it suggests opening a PR [commands/converge.md]. |
| taskstoissues (deprecated) | GitHub issues | One issue per task, deduplicated on `T\d{3,}` [commands/taskstoissues.md]. |
| git extension | branches, auto-commit | Provides `feature`, `validate`, `commit`, `remote` and `initialize`. **No merge, no PR, no worktrees** [extensions/git/README.md]. |

Spec Kit's strength is everything upstream of code: requirement quality, catching ambiguity, constitution gates, and FR→task coverage. Downstream it is weak. Implement trusts the agent, and there is no isolation, no independent review, no merge queue, and no machine proof that the tests mean anything. Converge is still an LLM judging an LLM.

---

## 2. Stage-by-stage scorecard

| Stage | Spec Kit | Kahnban (evidence) | Verdict |
|---|---|---|---|
| **Constitution / principles** | A versioned constitution with MUST/SHOULD principles. Plan gates it twice, analyze treats a conflict as CRITICAL, and Complexity Tracking records justified exceptions. | No constitution artifact. Principles live in 10 `principle-*` skills plus `/unslop` and `/no-comments`, which the conductor loads (`.agents/skills/factory-mode/SKILL.md:13-28`). The coder agent preloads only `tdd, coder-agent, unslop, no-comments, how, why` (`.claude/agents/kahnban-coder.md:5-11`), and no gate checks a principle. Kahnban does turn several principles into machine checks that Spec Kit only states: TDD proof (`require_proof` reverts the source and requires the feature tests to fail, README.md:145), small units (`max_blast_radius_files`, core.py:528-532), and scope (verify refuses diffs outside the blast radius, README.md:143). | **FALLS SHORT** on declared, gateable principles. Its mechanised subset is stronger than Spec Kit's prose. |
| **Specify** | Rich template (stories, priorities, independent tests, FR/SC, entities, assumptions). Tech-agnostic. NEEDS CLARIFICATION capped at 3. Self-validating checklist loop. Branch per feature. | `kahnban spec new` scaffolds `SPEC-NNN` (specs.py:83-104). The template has only Problem, `R1…` requirements, Non-goals, Decisions, Edge-cases table and Tickets (`.agents/templates/spec-template.md`). It has no user stories, priorities, success criteria or assumptions. **The human approval gate is real**: `spec approve` hashes the requirements (specs.py:107-142), the guard blocks every factory role from approving (how-it-works.md:251), and any later edit is detected (specs.py:41-44, linter BL18). | **MEETS**. A thinner template, but the human gate on intent is enforced, which Spec Kit lacks. |
| **Clarify** | 10-category taxonomy, ≤5 questions, a recommended answer for each, answers written back to the spec under a dated Clarifications log. | `/grill-with-docs` interviews in rounds over a decision tree. It gives a recommended answer per question, looks facts up itself instead of asking ("facts are yours, decisions are theirs"), must cover the edges, and stops "when nothing is assumed" (`grill-with-docs/SKILL.md:14-17`). It records terms in GLOSSARY and decisions in ADRs (`:21-22`). It has no taxonomy, question budget or written Q→A log, and no inline uncertainty marker. The repo's own GLOSSARY.md is still the unfilled template and `ADR/` holds only 0001, so this has not been exercised here. | **MEETS**. Interrogation quality is comparable, but it has no budget or audit trail, and it is a skill, not a gate. |
| **Plan (tech / research / data-model / contracts)** | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, gated by the constitution. | `/to-spec` asks for type contracts, invariants and an edge-case matrix inside the spec (`to-spec/SKILL.md:31-42`). It has no research step, no separate data model or contracts, no pre/post-design gate, and nothing checks its output. The engine has no plan concept at all. | **FALLS SHORT** |
| **Tasks (dependency ordering, parallel markers)** | IDs T001…, `[P]` declared per task, story phases, foundational blocking phase, MVP slice, dependency graph. | Tickets carry `depends_on`, resolved by title, anchor or ID (ingest.py:728-776; PLAN-INGESTION.md:140-142). Unresolved dependencies become `blocked_on`, so they are never silently dropped. **Parallelism is derived, not declared**: claim refuses overlapping blast radii (core.py:1549-1557), and the dispatcher only offers ready tickets with a free radius (dispatcher.py:170-179). `run --jobs N` runs coders concurrently (cli.py:776). Each ticket must have ≤3 files and a test file (core.py:528; README.md:178-179). **But**: there are no phases or priorities, and **the dispatcher ignores `depends_on` for intake**. It hands the first backlog ticket to the spec analyst whatever its dependencies (dispatcher.py:199-221), while `ready` refuses until every dependency is in done (core.py:1430-1440). A failed gate counts as an attempt, and after `max_attempts` (3) the runner escalates to a human (runner.py:157-163). No test covers this: `grep depends_on` over runner.py, dispatcher.py and the dispatcher/factory tests returns nothing. | **MEETS**. Derived parallelism beats a self-declared `[P]`, but dependency-blind dispatch is a real defect for large specs. |
| **Analyze (cross-artifact consistency)** | A read-only, six-pass analysis with severities and coverage %. | `kahnban spec coverage` exits 1 until every R-id has a ticket (specs.py:187-210). Lint BL18 checks that a cited spec or requirement exists and that the approved spec hasn't changed, and **warns** on uncovered requirements (linter.py:476-500). The ready gate under `require_spec` checks the same (core.py:1421-1424). It has no ambiguity, duplication, terminology or conflicting-tech checks, and no orphan-ticket check beyond "names a spec". | **FALLS SHORT**. Structural coverage only; nothing checks semantics. |
| **Checklist (requirements quality)** | CHK items, ≥80% traced, gating implement. | None. | **FAILS** |
| **Implement** | The agent runs tasks.md phase by phase and ticks `[X]` itself. Halt on failure. No isolation. | One worktree per ticket on `ticket/<ID>` (how-it-works.md:77). The coder role is guarded to its blast radius, and override flags and `git merge/push/reset --hard` are blocked (README.md:224). **verify** checks, in order: frozen contract hash, scope, clean tip, each criterion's own test, regression tests, and **proof that the feature tests fail on the reverted source** (how-it-works.md:95-106). Boxes are ticked only by passing tests (README.md:127-135). An independent reviewer approves or rejects, and approvals are signed with HMAC (README.md:220). Retries escalate (README.md:219). | **SUCCEEDS** |
| **Merge / integration** | None. Converge suggests opening a PR. | `kahnban merge` merges the ticket onto main in a scratch worktree under the board lock, runs the feature and regression tests on the merged result, and fast-forwards only on green (how-it-works.md:211-213; core.py:2656-2740). `done` refuses unless the merge commit is on the default branch and contains the tip (how-it-works.md:160-166). Attended mode adds a human merge gate (README.md:221). | **SUCCEEDS** |
| **Traceability (req → task → test → commit)** | FR/SC → task by ID or key phrase (analyze/converge only). Task → commit is not tracked. | **R-id → ticket** (`spec:`, `covers:` set by ingest, specs.py:145-150; ingest.py:822-830). **Criterion → test command** (`(test: …)`, executed by verify). **Ticket → commits** (`ticket/<ID>` branch, merge message `merge ticket/<ID>: <title>`, core.py:2700; merge SHA recorded in the Log, core.py:2419-2456). **Ticket → source section** (`source_doc`, `source_anchor`, `source_hash`, with drift detection; PLAN-INGESTION.md:36-48). Gaps: (a) `require_spec` defaults to off, and this repo's own board has `"require_spec": false` (plans/board.config.json) with no `.agents/specs/` directory, so the chain is not dogfooded. (b) Coverage counts a ticket in **any** column, so "covered" means "has a ticket", not "proven done" (specs.py:192-204). (c) The coder and reviewer prompts never load the requirement text, only the ticket (kahnban-coder.md:16-19; kahnban-qa-reviewer.md:34-38). (d) The ingest dry-run neither shows nor validates `covers` (§4). | **SUCCEEDS** on mechanism, with real gaps in default and in use. |

Tally: SUCCEEDS 3 (Implement, Merge, Traceability). MEETS 3 (Specify, Clarify, Tasks). FALLS SHORT 3 (Constitution, Plan, Analyze). FAILS 1 (Checklist).

---

## 3. Narrative

**SUCCEEDS: the downstream half.** Kahnban is what Spec Kit's `implement` and `converge` would like to be. Spec Kit's converge says "completion claims are not evidence" and then asks an LLM to judge the code. Kahnban makes the evidence mechanical. Criteria tick only when their own test exits 0. Under `require_proof` the feature tests must fail with the source reverted, so a test that passes without the change cannot count as proof. The contract is hash-frozen at `ready` and signed. The diff must stay inside the blast radius. A different identity must approve. The merge queue re-runs everything on the merged result. Spec Kit has no merge or PR step at all (git extension README), and its implement step ticks its own boxes. On "superb, fully tested, vetted code", Kahnban is well ahead.

**MEETS: specify, clarify, tasks.** Kahnban's spec is thinner (no stories, priorities, SC-### or assumptions), but its human gate on intent is real. The requirements hash freezes intent, and factory roles cannot approve. `/grill-with-docs` is as good an interviewer as `/speckit-clarify` in spirit: rounds, recommendations, and looking facts up before asking. But it has no question budget, no category checklist, and no written Q→A record, so you cannot audit afterwards what was decided and why. For tasks, Kahnban's derived parallelism (disjoint blast radii, enforced at claim) is more honest than Spec Kit's `[P]`, which the model asserts about itself. But Kahnban has no phases, priorities or MVP slice, and the dispatcher does not use dependencies.

**FALLS SHORT: constitution, plan, analyze.** These are Spec Kit's best ideas, and Kahnban has no counterpart to any of them as an artifact or a gate. There is no project-level, versioned "MUST" list that a gate checks, no research, data-model or contracts step between spec and tickets, and no pass that catches vague, duplicate or conflicting requirements. Kahnban's checks are structural (does R3 have a ticket?), not semantic (is R3 measurable, and do R3 and R5 contradict each other?).

**FAILS: checklist.** Nothing tests the quality of the requirements themselves. Because Kahnban's downstream is so strict, a badly worded requirement is the most likely way bad software gets through: every gate will faithfully prove the wrong thing.

---

## 4. North-star gap: "hand it a whole spec and it dissects it"

### Experiment (dry run only; board untouched)
Samples are in `C:\Users\User\AppData\Local\Temp\claude\C--github-kahnban\2fa59313-657d-40bf-a396-2e34c00913fb\scratchpad\ingest-samples\`.

**A. A PRD-style plan** (`a-prd.md`: FR-001..FR-004 and SC-001 under `## Requirements`, two phases, four work items, one with 5 files, one with prose "files", one fuzzy dependency name, one pre-ticked box):
```
would create: Saved search model        anchor phase-1-storage/saved-search-model   blast radius: 2
would create: Saved search repository   depends_on: KB-015
would create: Saved search HTTP API     blast radius: 5   depends_on: KB-016
would create: Notification worker       blast radius: 0  validation: no
   blocked_on: unresolved dependency: Saved search API, Email gateway
```
- Good: phase-nested anchors, title-based dependency wiring, and an unresolved dependency parked instead of guessed.
- Bad: **the whole `## Requirements` section (FR-001..SC-001) vanished with no warning**. No ticket received `covers`, and the FR references written in each "Why" were ignored. A non-SPEC document carries no traceability at all.
- Bad: the 5-file item and the 0-file item produced **no warning at dry-run**. They fail later, at `ready` (core.py:528-532), and in the factory a failed ready gate goes to the spec analyst, whose role is told to **escalate, not split**, a ticket that is too big (`templates/roles.json:22`). Splitting oversized work is therefore a human job.
- Bad: the fuzzy reference "Saved search API" did not match "Saved search HTTP API". That is correct but brittle. There is no suggestion of the nearest title.

**B. A Spec Kit `tasks.md`** (`b-speckit-tasks.md`: `T001 [P] [US1] … in src/x.py` lines):
```
would create: Setup / Foundational / User Story 1 … / User Story 2 …   (blast radius: 0, validation: no — each)
```
**Kahnban cannot ingest Spec Kit's task format.** The individual tasks were lost: phases became tickets, and the T-ids, `[P]` markers, story labels, inline file paths and "(depends on T003)" were all dropped.

**C. A Kahnban SPEC** (`c-SPEC-901.md`: R1–R3, two tickets, one citing a non-existent `R9`, R3 uncovered, status `draft`):
```
would create: Saved search model; Listing order (depends_on: KB-015)     warnings: []
```
The dedicated spec path works: it reads only `## Tickets` (ingest.py:822-826) and wires dependencies. But **the dry-run shows neither `spec` nor `covers`** (the JSON report has no such fields, ingest.py:190-205), and it gives **no warning** for the unknown `R9`, the uncovered `R3`, or the unapproved spec. Those problems surface only later, in `spec coverage`, BL18, or a `require_spec` ready refusal.

### Assessment
| North-star capability | Status |
|---|---|
| Idea → interrogation → approved spec | **Mostly there**: `/grill-with-docs` plus the human `spec approve` gate. Missing: a written clarifications log and a requirements-quality check. |
| Spec → tickets with dependencies | **Works only if a human or LLM writes `## Tickets` in Kahnban's exact shape** (`/to-tickets`). The engine does not decompose. Ingest is a careful parser with useful guarantees: idempotent, drift-detecting, never fabricates readiness (PLAN-INGESTION.md:19-48). |
| Arbitrary large doc (PRD / Spec Kit tasks) | **Weak.** Requirements are silently dropped, Spec Kit tasks are unparsed, and oversized items are escalated instead of split. |
| Dependency-ordered autonomous swarm | **Partially broken for large specs.** Dispatch ignores `depends_on` at intake (dispatcher.py:199-221). Dependents can burn spec-analyst turns failing `ready` and get escalated after 3 attempts (runner.py:157-163), depending on document order and `--jobs`. This is inferred from the code and not reproduced live. It is the top thing to verify. |
| "Done" at spec level | **Missing.** Nothing says "SPEC-001 is complete": every R-id covered by a ticket in done, and the spec re-checked against the merged code. Spec Kit's converge loop is exactly that missing step. |
| Requirement → code traceability | **Strong mechanism, off by default.** `require_spec` is false on new boards (README.md:177) and on this repo's own board. |

In short: Kahnban is an excellent **execution and vetting engine** with a **thin front end**. The near-term goal ("I want feature X" → swarm) works when one session runs grill → spec → to-tickets → `ingest --ready` → `run --jobs N`. The ultimate goal ("hand it a whole spec") breaks at three points: decomposing documents it didn't write, dependency-aware dispatch, and spec-level convergence.

---

## 5. STEAL LIST (ranked)

| # | What | Why (gap) | Where in Kahnban | Effort |
|---|---|---|---|---|
| 1 | **Dependency-aware dispatch**: skip intake candidates (and ready ones) whose `depends_on` aren't done, and say "waiting on KB-x" instead of dispatching. Add one test: a dependent listed first is never refined before its dependency. | Stops dependents burning attempts and escalating on large specs. Required for a "whole spec" run. | `dispatcher.py:199-221` (filter with `core._dependency_problems`), test in `tests/test_dispatcher.py` | **S** |
| 2 | **Spec-level converge**: `kahnban spec status SPEC-NNN` / `spec converge`. Mark a spec `implemented` only when every R-id has ≥1 ticket in done. Optionally run a **spec-verifier** worker that reads the spec plus the merged code and files fix tickets (`covers: [Rn]`, "gap: missing/partial/contradicts") until it converges. | The "until done" condition is undefined today. Coverage counts tickets in any column (specs.py:192-204). | `specs.py` (`coverage(..., done_only=True)`), new role in `templates/roles.json`, dispatcher priority after the ready work is drained | **M** |
| 3 | **Ingest validates traceability and size at dry-run**: show `spec` and `covers` in the report, warn on unknown R-ids, uncovered R-ids, an unapproved spec, blast radius > `max_blast_radius_files`, and empty or prose blast radii. Warn when a `## Requirements` section was skipped. | Every problem in samples A and C was silent at preview time, when it is cheapest to fix. | `ingest.py` `IngestReport.to_dict` (~190-205), `render_report` (~997-1040), reuse `core.decomposition_problems` and `specs.coverage` | **S** |
| 4 | **Auto-split instead of escalate**: when a ticket exceeds the file budget, let the spec analyst run `kahnban new`/`ingest` to create child tickets (copying `spec` and `covers`, chained with `depends_on`) and archive the parent. Escalate only when it needs a decision. | Large items in a whole spec need splitting. Today oversized work is a human job (roles.json:22). | `templates/roles.json` spec_analyst `steps` and `escalate_when` (it already holds `new` and `ingest`); a `kahnban split <ID>` helper in `core`/`cli` | **M** |
| 5 | **Constitution as a gated artifact**: `.agents/constitution.md` with numbered MUST principles, each mapped to a check: a lint rule, a ready-gate predicate, or a reviewer rubric item. Load it into the reviewer prompt, and have reject reasons cite the principle id. Version it (semver) like the spec. | Principles are scattered across 12 skills and no gate checks them. Spec Kit makes a conflict CRITICAL. | new `constitution.py` or extend `specs.py`; `templates/roles.json` reviewer facts; `linter.py` | **M** |
| 6 | **Requirements-quality gate before approve** (Spec Kit checklist and analyze, mechanised): `kahnban spec check SPEC-NNN` refuses vague terms ("fast", "secure", "robust" with no number), placeholders (TODO, ???, `[NEEDS CLARIFICATION`), duplicate or near-duplicate R lines, and R lines with no edge-case row. Run it inside `spec approve`. Add an LLM `/spec-analyze` skill for the semantic passes, read-only. | The upstream quality hole (the FAILS row). Today the strict downstream gates can prove the wrong thing. | `specs.py:approve_spec` (pre-check), new skill `.agents/skills/spec-analyze/` | **S** (lexical) / **M** (skill) |
| 7 | **Clarifications log + uncertainty markers**: grill writes `## Clarifications / ### Session <date>` with `Q → A` bullets into the spec, and may leave at most 3 `[NEEDS CLARIFICATION: …]` markers that `spec approve` refuses. Add a question budget and Spec Kit's 10-category coverage sweep as the stop condition. | The interrogation leaves no audit trail, and "interrogate only as needed" needs a budget. | `.agents/skills/grill-with-docs/SKILL.md`, `.agents/templates/spec-template.md`, `specs.py` approve check | **S** |
| 8 | **Richer spec template**: user stories with priority and an "Independent test", `SC-###` measurable success criteria, Assumptions. Map stories → epics, so tickets also cite a story and the dispatcher can prefer P1 (an MVP slice first). | Gives the swarm an ordering and an MVP stopping point, and gives success criteria the converge step can check. | `.agents/templates/spec-template.md`, `specs.REQUIREMENT` regex (accept `SC-\d+`/`FR-\d+` as ids), dispatcher priority | **M** |
| 9 | **Ingest Spec Kit `tasks.md` / checklist-line plans**: parse `- [ ] T\d+ [P]? [US\d]? desc … path` lines into tickets, with each path in the blast radius, `[US]` → a story tag, and phase order → `depends_on` on the previous phase's tasks. Read `FR-###` refs anywhere in a section as `covers`. | Lets Kahnban execute plans made by Spec Kit (and similar tools). Today sample B is lost entirely. | `ingest.py` (a new list-item splitter beside `split_sections`, ~359-444), `_extract_refs` for FR/R ids | **M** |
| 10 | **Plan step with research and contracts**: a `/to-plan` skill that writes `research.md` (Decision / Rationale / Alternatives) and `contracts/` next to the spec, with a pre/post constitution check. To-tickets then quotes contract constraints verbatim into criteria (Spec Kit tasks rule). | Closes the FALLS SHORT on Plan. Gives coders fixed interfaces across parallel tickets. | `.agents/skills/to-spec` (split or extend), `design_docs` already carried into the baton (handoff.py:112) | **M** |
| 11 | **Feed requirement text to coder and reviewer**: put the covered `Rn: <text>` lines (and constitution ids) into the handoff baton, and have the reviewer check "does the diff satisfy R2", not only "do the criteria have tests". | Today the requirement → code link exists only as metadata, and neither worker reads the requirement. | `handoff.py` (~100-130 build baton), `templates/roles.json` qa_reviewer steps | **S** |
| 12 | **Turn on and dogfood `require_spec`**: make `init --agentic` write `require_spec: true`, and route this repo's own next feature through SPEC → tickets. | The traceability mechanism is unused, so its rough edges (items 3, 11) went unnoticed. | `scaffold.py` init defaults; `plans/board.config.json` | **S** |

Do not copy: Spec Kit's self-ticked `[X]` implement step, its agent-asserted `[P]`, or LLM-only convergence as the final word. Kahnban's mechanical proof is the stronger design. Steal converge's *loop*, and keep Kahnban's *gates*.

---

## 6. Sources

Spec Kit (primary, `github/spec-kit` main, fetched 2026-10-29):
- https://raw.githubusercontent.com/github/spec-kit/main/README.md
- https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/spec-template.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/plan-template.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/tasks-template.md
- https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/{constitution,specify,clarify,plan,tasks,analyze,checklist,implement,converge,taskstoissues}.md
- https://raw.githubusercontent.com/github/spec-kit/main/extensions/git/README.md
- https://api.github.com/repos/github/spec-kit/releases (v1.2.5, 2026-10-28)

Kahnban: the file:line citations inline above. Dry-run commands: `py -3 -m kahnban ingest <sample> --dry-run [--json]`, run from `C:\github\kahnban`, with `git status` clean afterwards.
