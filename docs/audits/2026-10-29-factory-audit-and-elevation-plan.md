# Factory audit and elevation plan

Date: 2026-10-29. Kahnban `1.4.0` at `a38a0c0`. This document blends four independent audits:

| # | Reference | Raw report |
|---|---|---|
| 1 | Matt Pocock: skills v1.2.3, Ralph, Sandcastle, `.factory/` | [audit-1-pocock](2026-10-29-audit-1-pocock.md) |
| 2 | poteto (Lauren Tan, Cursor): pstack | [audit-2-poteto](2026-10-29-audit-2-poteto.md) |
| 3 | GitHub Spec Kit v1.2.5 | [audit-3-speckit](2026-10-29-audit-3-speckit.md) |
| 4 | BMAD Method V6.12 | [audit-4-bmad](2026-10-29-audit-4-bmad.md) |

Each raw report has file:line evidence and source URLs. This document cites the reports by number.

> **Note on "software kitchen".** Auditor 2 found no poteto source that uses a kitchen metaphor. Her published work is **pstack** (MIT, `cursor/plugins/pstack`), and her own metaphors are "gardener" and "lever". The audit is against pstack. If you meant a specific talk or post, share the link and that lens can be re-run.

**North star.** An idea goes in. The factory interrogates the human only as needed, writes the spec, breaks it into tickets and tests, and swarms them to merged, fully tested, vetted code. In the ultimate version you hand it a whole spec and walk away until it is delivered.

---

## 1. Verdict in one paragraph

Kahnban has the strongest **back half** of any of the four references, and every auditor agreed on that independently. Its gates are code, not prompts: a frozen contract hash, a blast-radius scope check, a red proof (feature tests must fail on the reverted source), a reviewer who is not the owner with signed approvals, and a merge queue that retests the merged result. Spec Kit has no merge step at all. BMAD's gates are markdown HALT instructions. Sandcastle's merger is an LLM. pstack trusts the lead agent. The weakness is everything **around** that core. Upstream, nothing turns a spec into tickets without a human at the keyboard, and nothing checks whether the requirements are any good. Downstream, nothing says when a *spec* is done, and review checks containment but not design quality or fidelity to the spec. In the middle, the dispatcher ignores dependencies, so a large spec would turn into a storm of escalations. **Kahnban is an excellent execution and vetting engine with a thin front end and no finish line.**

---

## 2. Cross-reference scorecard

`++` succeeds (beats the reference) · `=` meets · `-` falls short · `x` fails · `·` the reference does not cover it

| Capability | Pocock | poteto | Spec Kit | BMAD | Consensus |
|---|:-:|:-:|:-:|:-:|---|
| Interrogation (grill, facts vs. decisions) | = | = | = | ++ | **Solid.** No question budget and no Q→A record (3) |
| Spec as a frozen, human-approved contract | ++ | = | = | = | **Solid.** The human gate is enforced |
| Requirements quality (vague, conflicting, untestable) | · | · | x | · | **Missing** |
| Constitution or principles that a gate enforces | · | - | - | · | **Text only.** No worker preloads any principle (2) |
| Test seams agreed up front | - | · | · | · | **Missing** (1) |
| Plan, research and contracts step | · | - | - | · | **Missing** |
| Unknowns resolved by research or a spike, not escalation | x | x | · | · | **Missing.** Every open question goes to a human |
| **Spec → tickets, autonomously** | x | x | - | x | **The #1 blocker.** Only the human-driven `/to-tickets` does it |
| Oversized work is split, not escalated | x | · | - | · | **Missing.** `roles.json:22` escalates instead |
| Ingest of arbitrary documents | - | · | - | x | Drops a `## Requirements` section with no warning. Cannot parse Spec Kit `tasks.md` (3) |
| **Dependency-aware dispatch** | = | x | - | · | **A bug.** Verified in `dispatcher.py`, see §3 |
| Parallel swarm (leases, radius overlap) | = | = | ++ | ++ | **Strong** |
| Context into each ticket (spec text, code map, sibling tickets) | · | · | - | - | **Thin.** The coder and reviewer never see the requirement text |
| Implementation gates (proof, scope, contract) | ++ | ++ | ++ | ++ | **Best in class** |
| Review: design quality and fidelity to the spec | - | - | · | - | **Single axis**, checking containment only |
| Reject routing (bad code, bad ticket, intent gap) | · | · | · | - | **Missing.** Every reject goes to the coder |
| Verification on the real running product | · | - | · | · | Exit codes only (2) |
| Merge queue | ++ | ++ | ++ | ++ | **Best in class** |
| **Spec-level "done" or convergence** | x | · | x | x | **Missing.** Coverage counts tickets in any column |
| Learning loop | ++ | ++ | · | ++ | **Strong pipeline**, but capture is voluntary (2) |
| Sandbox or isolation | - | · | · | · | A tripwire, not a sandbox (1) |
| Hygiene: docs, provenance, dogfooding | - | x | - | · | Several defects, see §4 |

---

## 3. The verified bug

`src/kahnban/dispatcher.py` (Priority 5, intake) picks `intake_candidates[0]` with no `depends_on` filter. `core._dependency_problems` makes `ready` refuse any ticket whose dependency is not in done. On a spec whose `## Tickets` lists a dependent before its dependency, the spec analyst refines a ticket it cannot promote. The ready gate fails, each failure counts as an attempt, and after `max_attempts` the runner escalates to a human (`runner.py:157-163`). No test covers this. Auditors 2 and 3 found it independently, and I confirmed it by reading the code. It has **not** been reproduced in a live run. That reproduction is the first test to write.

---

## 4. Where we stand

### SUCCEED: keep and protect
- **Mechanical proof beats asserted completion.** The red check catches the tautological tests that Pocock only warns about (1), and it is what Spec Kit's `converge` only aspires to (3).
- **The merge queue** is deterministic and serialized, and a live run has already caught two tickets that broke an invariant together (1).
- **The role guard, signed approvals and reviewer ≠ owner.** No reference has an equivalent.
- **Status as folders plus commits.** It cannot drift, whereas BMAD needs a repair mode for `sprint-status.yaml` (4).
- **The learnings → curator → fix-ticket ladder.** It is a pipeline. pstack's `encode-lessons` is three sentences (2), and BMAD's retro only proposes changes (4).
- **`kahnban run`** already ships what BMAD's Loop module only describes (4).
- **Requirement → ticket → test → merge-commit traceability.** It is mechanical, though off by default (3).

### MEET: parity
Grilling quality · HITL to AFK autonomy · a fresh context per worker · parallelism with radius-overlap refusal · iteration caps and an idle signal · TDD red before green.

### FALL SHORT
1. **Context handoff is thin.** The analyst investigates and then leaves `## Implementation notes` empty. The coder is never pointed at the spec. A ticket knows nothing about earlier tickets from the same spec. (3, 4)
2. **Review covers one axis.** It checks scope and test fidelity, but has no standards axis, no spec axis and no smell baseline. The reviewer cannot refine. `factory-mode/SKILL.md:55` claims a "dual-axis" review that does not exist. (1, 2, 4)
3. **The refactor step is in the wrong place.** It sits in the coder's TDD loop, where Pocock now puts it in review. (1)
4. **The 1–3 file cap fights vertical slices,** and there is no expand–contract guidance for wide refactors. (1)
5. **Principles are decoration in the factory.** No role preloads any `principle-*` skill, and the reviewer's rubric never asks for the smallest diff, the root cause, or subtracting first. (2)
6. **Learning capture is voluntary.** Rejects, escalations and refused gates are structured events, yet none of them auto-captures a learning. (2)
7. **Escalations are a bare string.** There is no question, no recommended answer, and no recorded answer. (1)
8. **No human sign-off on the breakdown,** which is exactly where "swarm a feature" failures start. (1)
9. **First ready ticket, not riskiest first.** (1)

### FAIL
1. **No autonomous decomposition.** `run` refines existing tickets one at a time. `ingest` splits on headings. (all four)
2. **No spec-level finish line.** `spec coverage` passes on citation, not delivery. (1, 3, 4)
3. **No research or spike path.** Unknowns become human escalations. (1, 2)
4. **No requirements-quality gate.** The strict downstream gates will faithfully prove the wrong thing. (3)
5. **Hygiene defects:**
   - `no-comments` is preloaded into every coder but spawns a `comment-sicko` agent that does not exist, and cites `poteto-mode`, which is not installed.
   - `skills check` passes it anyway, because its regex only matches `/slash` references (`skills_check.py:28`).
   - Two principles reference skills that are not installed.
   - The pstack skills ship with **no LICENSE or attribution**, which MIT requires.
   - The "Lauren Tan Clustering Invariant" is a misattribution (`reflect/SKILL.md:10`, `learnings.py:4`).
   - The bundled "Matt Pocock" skills have drifted from upstream, and `/implement-spec` and `/retro` don't exist upstream. `skills install --source mattpocock` would probably overwrite them under the same names (inferred, not run).
   - The status docs are stale: they say the runner is sequential and that there are 343 tests, where there are 725.
   - `GLOSSARY.md` is an unfilled template, and `require_spec` is off on kahnban's own board. (1, 2)

---

## 5. Design tensions to resolve, not copy blindly

| Tension | Resolution |
|---|---|
| Pocock wants path-free, vertical tickets, but Kahnban's scope gate and overlap detection *need* paths. | Keep paths at **ticket** level. Keep the **spec** at behaviour level, with seams but no snippets. Count only non-test files toward `max_blast_radius_files`, and allow a per-ticket override that is logged with a reason. |
| Spec Kit and BMAD carry a heavy document stack (constitution, PRD, plan, research, contracts, checklists). | Take only what a **gate can check**: a constitution of numbered MUSTs mapped to checks, a lexical requirements check, and a seams section. Skip the brief, PRFAQ, sharding and persona theatre (4, DON'T-STEAL). |
| Converge loops in Spec Kit and Sandcastle are an LLM judging an LLM. | Steal the **loop**, keep the **gates**. Spec "delivered" must be computed (every R-id covered by a done ticket, plus spec acceptance commands green on main). An LLM spec verifier may only *file tickets*, never declare done. |
| pstack's playbook router versus Kahnban's fixed pipeline. | Add a `kind:` field (`feature`, `bug`, `refactor`, `research`, `spike`) that changes the ready-gate rules and the coder steps. Skip the router. |
| A reviewer that can edit (Sandcastle) versus a non-editing reviewer (Kahnban). | Keep the non-editing **approver**. Add an optional **refine** worker that edits inside the radius. Its new tip invalidates any approval, so it composes with the existing gates. |

---

## 6. Elevation plan

Phases are ordered by what unblocks "hand it a spec". Each item names its source audits, the files it touches, and its effort (S/M/L). Every phase ends in a verifiable state, and phases 1–3 together make up the minimum for walking away.

### Phase 0: Tell the truth (S, about one day)
Fix what is broken or misleading before building on it.
- [ ] Fix `no-comments`: import the `comment-sicko` agent and drop the `poteto-mode` reference, or remove the skill from the coder preload. Widen `skills_check.SKILL_REF` to catch `**skill**` and `subagent_type: "x"` references, and add a test. (2) `roles.json`, `skills_check.py:28`, `tests/test_skills.py`
- [ ] Remove the dangling `show-me-your-work` and `build-the-lever` references, or import those leaves. (2)
- [ ] Add `LICENSE` and `THIRD_PARTY_NOTICES` (pstack MIT, Pocock's licence), and record `source` and `upstream_rev` in `skills.lock.json`. Rename the "Lauren Tan Clustering Invariant". (2)
- [ ] Describe the bundled Pocock forks as "adapted from" and drop `/implement-spec` and `/retro`. Make `--source mattpocock` install alongside the bundled set, not over it, and add a test for the collision. (1)
- [ ] Fix the false "dual-axis" claim in `factory-mode`, the stale `IMPLEMENTATION_STATUS.md` and `NEXT_STEPS.md`, and the `lint --help` BL range. (1, 2)

**Done when:** `skills check` fails on a planted dangling reference, and the status docs match `pytest --collect-only` and `run --help`.

### Phase 1: Unblock the swarm (S)
- [ ] **Dependency-aware dispatch.** Filter the intake and claim candidates through `core._dependency_problems`. When nothing is eligible, report "waiting on KB-x" rather than idle. Write the regression test first: a dependent listed before its dependency is never refined first. (2, 3) `dispatcher.py`, `tests/test_dispatcher.py`
- [ ] **Risk-first ordering.** Add a `priority`/`risk` frontmatter field, and sort by risk, then by the number of dependents unblocked, then by id. (1) `dispatcher.py:180`, ticket template
- [ ] **Ingest dry-run tells the truth.** Show `spec` and `covers`. Warn on an unknown or uncovered R-id, an unapproved spec, an oversized or empty blast radius, and a `## Requirements` section that was skipped. (3) `ingest.py` report and render
- [ ] **Auto-capture learnings** on reject, escalation, and a gate refused more than N times. (2) `runner.py`, `core.reject`, `learnings.capture_learning`

**Done when:** the three samples in `2026-10-29-ingest-samples/` each produce the warnings audit 3 says were missing, and a dependency-chain fixture runs under `run` with zero escalations.

### Phase 2: Close the loop from spec to delivered (M). This is the north star.
- [ ] **Planner role and a `decompose_spec` dispatcher action.** Trigger when an approved spec has uncovered R-ids or no `## Tickets`. The planner writes vertical-slice tickets (`Covers:`, `Depends on:`) into the spec, then the runner runs `ingest --ready`. Optional `human_gates: ["breakdown"]` plus `kahnban confirm` for review of the breakdown. (1, 2, 4) `templates/roles.json`, `dispatcher.py`, `runner.py`, `guard.py` remit
- [ ] **Split instead of escalate.** The analyst's "too big for 1–3 files" case hands off to the planner, or runs a new `kahnban split <ID>` that creates children inheriting `spec`/`covers`, chains them with `depends_on`, and archives the parent. (1, 3) `roles.json:22`, `core`, `cli`
- [ ] **Spec finish line.** `kahnban spec status|close SPEC-NNN`: delivered only when every R-id is covered by a ticket in **5-done** and the spec's `## Acceptance` commands pass on main. `run` exits with `SPEC-N delivered` or `SPEC-N stuck: <reasons>`. (1, 3, 4) `specs.py` (`coverage(done_only=True)`), `cli.py`, dispatcher priority after merges
- [ ] **Converge pass (optional).** A spec-verifier worker reads the spec plus the merged code and may only *file* gap tickets (`gap: missing|partial|contradicts`). It never declares done. (3)
- [ ] Turn on `require_spec` for `init --agentic` and for kahnban's own board. (3)

**Done when:** a real 6–10-ticket spec goes from `spec approve` to `SPEC-N delivered` under `kahnban run --jobs 3`, with no human action between approval and delivery. Record first-pass yield and the escalation count. This is the "earn trust before parallelising" milestone (2).

### Phase 3: Context engineering (S–M)
- [ ] The analyst drains its investigation into `## Implementation notes` as a **code map**: paths, symbols, reuse points, and things never to touch. The coder's first step is to read it. Optionally, lint that a ready ticket has notes. (4) `roles.json` analyst and coder steps
- [ ] **Requirement text in the baton.** Put the covered `Rn: <text>` lines and constitution ids into `handoff.py`, so the coder and reviewer both see them. (3)
- [ ] **Sibling continuity.** Include the done tickets from the same spec (their radius, notes and last Log lines) in the prompt facts. (4) `handoff.py:_prompt`
- [ ] **Spec digest.** `spec digest` compiles a cached summary of 800–1500 tokens, invalidated by a change to the spec, an ADR or the GLOSSARY. (4)
- [ ] **Structured escalation briefs.** Add `escalate --question … --recommend …` and `unblock --answer`, written to a `## Questions` block that workers read. (1)

### Phase 4: Raise the quality ceiling, from "passes" to "superb" (M)
- [ ] **Two-axis review.** Run Standards (a `CODING_STANDARDS.md` plus a smell baseline) and Spec (the R-text) as parallel sub-reviews. Each reject cites a principle or R-id. (1, 2) `code-review` skill, `roles.json` reviewer facts and steps
- [ ] **Reject routing.** `reject --route patch|bad-ticket|intent-gap`. `bad-ticket` sends the ticket back to refining with its contract unfrozen, and `intent-gap` escalates. (4) `core.reject`, `dispatcher.py`
- [ ] **Verification-gap lens.** For each changed behaviour, the reviewer names the smallest realistic regression at a call site and confirms a test would catch it. (4)
- [ ] **Optional refine worker** that edits inside the radius after review. Move REFACTOR out of `tdd` and into this pass. (1)
- [ ] **Preload principles per role**: laziness, root causes, subtract-first and test-behaviour-not-implementation for the coder and reviewer. (2)
- [ ] **Diff-size budget** (`max_diff_lines`) and a `--max-turns` context budget per worker. (2)

### Phase 5: Upstream rigor, fewer bad specs (S–M)
- [ ] **A constitution as a gated artifact.** `.agents/constitution.md` holds numbered MUSTs, each mapped to a lint rule, a ready predicate or a reviewer rubric item. It is versioned. (3)
- [ ] **`spec check` inside `spec approve`.** Refuse vague terms with no number, placeholders, duplicate R lines, and requirements with no edge case. An optional read-only `/spec-analyze` skill handles the semantic passes. (3)
- [ ] **Clarifications log.** Grill writes `## Clarifications / Session <date>` as Q→A pairs. Allow at most 3 `[NEEDS CLARIFICATION]` markers, which `approve` refuses, plus a question budget. (3)
- [ ] **Seams and testing decisions** in the spec template and in grill and to-spec. The planner draws its criterion tests from those seams. (1)
- [ ] **Richer template.** Prioritised stories (P1 = the MVP slice), `SC-###` success criteria, and assumptions. (3)
- [ ] **Breakdown rules.** Port vertical slices and expand–contract into `to-tickets`. Exclude test files from the file cap, and allow a logged per-ticket override. (1)

### Phase 6: Unknowns, product truth and hardening (M–L)
- [ ] **`kind: research | spike` tickets.** No proof gate. The deliverable is a cited doc or an ADR that dependent tickets wait on. Add a researcher role. (1, 2)
- [ ] **A real-surface verification tier.** Fix `create-verification-skill` (wrong `.cursor` paths, missing `references/`). Add a `verify_skill` board key that runs as a third verify tier. (2)
- [ ] **Multi-model review.** K reviewers on different models, approve only on agreement, and a dissent becomes a structured reject. (2)
- [ ] **A container worker mode.** Bind-mount the worktree and exclude the host home directory and the key file. This turns the tripwire into isolation. (1)
- [ ] **Ingest Spec Kit `tasks.md`** (T-ids, `[P]`, `[US]`, paths) and `FR-###` references. (3)

---

## 7. Shape of the finished factory

```
human: "I want X"  or  hands over SPEC.md
   │
   ▼  /grill-with-docs  (budgeted questions, Q→A log, research before asking)      ◄─ the human interrogation
   ▼  spec check → spec approve (constitution + requirements-quality gate)          ◄─ the ONE required human gate
   ▼  planner: decompose_spec → vertical tickets (+ research/spike tickets)          [opt. human_gates: breakdown]
   ▼  analyst per ticket: premise check, code map, seams → ready (contract frozen)
   ▼  dispatcher: dependency-aware, risk-first, radius-disjoint → coders × N (sandboxed)
   ▼  verify (proof · scope · criteria · regression · real-surface)
   ▼  two-axis review → approve | reject(patch | bad-ticket | intent-gap)
   ▼  merge queue (main + branch retested)
   ▼  spec status: all R-ids done + acceptance green on main → "SPEC-N delivered"
   └─ every refusal / reject / escalation → learnings → curator → fix tickets (self-improvement)
```

## 8. Suggested next move

Dogfood it. Run Phases 0–1 through kahnban itself: `/grill-with-docs` → `SPEC-001` → `/to-tickets` → `kahnban run`. That fixes the bugs and also gives the first real multi-ticket evidence. Do Phase 2 as `SPEC-002`. When it ends in `SPEC-002 delivered` with no human action, that is the "walk away" milestone.
