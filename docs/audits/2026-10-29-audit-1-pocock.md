# Audit 1: Kahnban vs. Matt Pocock's AI coding workflow and "software factory"

Date: 2026-10-29. Repo HEAD `a38a0c0` (main). Read-only audit; nothing in the repo was modified.

Abbreviations:
- `PK/` = `C:\Users\User\.claude\plugins\cache\mattpocock\mattpocock-skills\1.2.3\` (Pocock's skills, plugin v1.2.3, read locally as the primary source)
- `SC:` = `github.com/mattpocock/sandcastle` @ main, fetched with `gh api`

Commands actually run:
- `py -3 -m kahnban --help`, `kahnban spec --help` and `kahnban run --help`
- `pytest --collect-only`, which collected **725 tests**
- `pytest tests/test_spec_gates.py`, which passed with 7 dots and no failures

---

## 1. Reference summary: what Pocock's approach is

**Philosophy.** His skills are small, composable and owned by the user. He sets them against frameworks that "own the process" and "take away your control" (GSD, BMAD, Spec-Kit; `PK/README.md`). Three failure modes drive the design:
- **Misalignment.** The fix is grilling.
- **Verbosity.** The fix is a shared language: `CONTEXT.md` plus ADRs.
- **Broken code.** The fix is feedback loops: types, tests, and red-green.

A fourth theme is "ball of mud": "bad codebases make bad agents", so design gets invested in daily through `/improve-codebase-architecture` and `/codebase-design`.

**Artifact chain (user-invoked orchestrators):**
1. **`/grill-with-docs`** = `/grilling` + `/domain-modeling` (`PK/skills/engineering/grill-with-docs/SKILL.md`).
   - The interview is a design tree, worked in rounds. Each round asks the whole current frontier, numbered, with a recommended answer for every question.
   - "Finding facts is your job… dispatch a sub-agent".
   - It ends only when the frontier is empty and the user confirms (`PK/skills/productivity/grilling/SKILL.md:494-510`).
2. **`/to-spec`** synthesizes the conversation without further interview. It agrees **test seams** with the user ("the ideal number is one").
   - It writes a PRD with a long list of user stories, implementation decisions, testing decisions and out-of-scope.
   - It includes **no file paths or code snippets**, since they go stale.
   - It is published to the tracker with the label `ready-for-agent` (`PK/.../to-spec/SKILL.md:14-20,56`).
3. **`/to-tickets`** produces **tracer-bullet vertical slices**: each one cuts through every layer, can be demoed, and fits one fresh context window.
   - Blocking edges are explicit.
   - Wide refactors use **expand–contract**.
   - The user is **quizzed on granularity and edges**.
   - Agents work the **frontier**: tickets whose blockers are all done (`PK/.../to-tickets/SKILL.md:106-142`).
4. **`/implement`** runs `/tdd` at the pre-agreed seams, typechecks often, runs the full suite at the end, then `/code-review`, then commits (`PK/.../implement/SKILL.md`).
5. **`/tdd`** works one vertical slice at a time, red before green.
   - It names anti-patterns: implementation-coupled tests, **tautological** tests, horizontal slicing.
   - **"Refactoring is not part of the loop. It belongs to the review stage"** (`PK/.../tdd/SKILL.md:221-237`).
6. **`/code-review`** reviews on two axes, **Standards** (repo standards plus a Fowler smell baseline) and **Spec** (fidelity to the originating issue), run as **parallel sub-agents** and never reranked against each other (`PK/.../code-review/SKILL.md`).
7. Supporting skills:
   - `/triage`: a state machine of `needs-triage → needs-info / ready-for-agent / ready-for-human / wontfix`, durable **agent briefs**, and an `.out-of-scope/` knowledge base.
   - `/wayfinder`: planning work bigger than one session as a map of *decision* tickets, with a "fog of war" for what can't be specified yet.
   - `/diagnosing-bugs` and `/prototype`.

**Loop shape (Ralph, then Sandcastle, then "factory"):**
- **Ralph** ([aihero tips](https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum)):
  - Start with a human watching each iteration (HITL), then let it run unattended (AFK).
  - Cap iterations.
  - Use a PRD whose items say `passes:false`, plus a `progress.txt`.
  - Typecheck, tests and lint must pass before each commit.
  - Take small steps.
  - **Do the risky work first.**
  - Define quality explicitly.
  - **Run AFK in a Docker sandbox.**
  - Stop on `<promise>COMPLETE</promise>`.
- **Sandcastle** (`SC:src/templates/parallel-planner-with-review/*`):
  - An Opus **planner** builds a dependency graph from open issues, and treats file/module overlap as a blocking edge.
  - It emits the unblocked set with deterministic branch names.
  - For each issue there is a sandboxed **implementer** (RGR, up to 100 iterations) followed by a **reviewer that edits**: it refactors for clarity, checks correctness and tests, and applies `CODING_STANDARDS.md`.
  - A **merger agent** merges the branches, resolves conflicts, re-runs the tests and closes the issues.
  - The outer loop repeats up to 10 rounds.
- **His own factory** (`SC:.factory/implement-task.ts`):
  - A daemon from a private `software-factory` repo spawns an implementer and then a reviewer per task, in a Docker sandbox.
  - Each task's branch is **stacked on a parent** (`FACTORY_BASE="origin/<parent>"`), and commits are "pushed and opened as a PR automatically".
- The human stays at the front (grilling, approving the PRD and tickets) and at the back (PR review). The aihero cohort "Software Factories for Real Engineers" emphasises guardrails. Its page now 404s; the description is secondhand via search results.

---

## 2. SUCCEEDS: where Kahnban goes beyond the reference

**S1. Gates are enforced by the machine, not by prompts.**
- **Reference:** Pocock's discipline lives in prompt text. Ralph's "can't declare success on red" depends on pre-commit hooks.
- **Kahnban:** `ready` freezes a contract hash. `verify` refuses if any of these hold:
  - the contract changed;
  - the tip is dirty;
  - the diff leaves the blast radius;
  - any validation line fails;
  - any criterion test fails;
  - **the feature tests still pass with the source reverted** (`README.md:139-145`, `docs/how-it-works.md:95-106`).
- That proof check mechanically catches the tautological and irrelevant tests that Pocock only warns about (`PK/.../tdd/SKILL.md:230`).

**S2. A real merge queue.**
- **Reference:** Sandcastle's merger is an LLM that "resolve[s] them intelligently" and then runs the tests.
- **Kahnban:** `kahnban merge` tests main+branch in a scratch worktree under the board lock and only fast-forwards when green (`README.md:153-155`, `how-it-works.md:211-230`). It is deterministic and serialized, and a refused merge is auto-rejected under `run` (`how-it-works.md:143`).
- A live run showed it catching two tickets that were each green alone but broke an invariant together (`IMPLEMENTATION_STATUS.md:38-40`).

**S3. Role separation is enforced.**
- `roles.json` is one manifest that renders the agent files, prompts, guard tables and exit checks (`README.md:223`; `src/kahnban/templates/roles.json`).
- The reviewer can never be the owner, and approval is bound to the verified tip.
- Approvals can be HMAC-signed.
- The PreToolUse guard blocks edits outside the role, `git merge/push/reset --hard`, and override flags (`README.md:220,224`).
- The Stop hook nudges a worker that stops early, and the runner applies a per-role exit check.
- Pocock has no equivalent of any of this.

**S4. Traceability from requirements to tickets.**
- **Reference:** Pocock's PRD has user stories but no machine linkage.
- **Kahnban:**
  - Specs number their requirements (`R1…`).
  - `spec approve` hashes them, and every factory role is blocked from approving.
  - Tickets carry `covers:`.
  - `spec coverage` exits 1 on any gap, and lint rule BL18 checks the same (`README.md:161-182`, `src/kahnban/specs.py:187-210`).

**S5. Recovery and limits beyond an iteration cap.**
- Leases with logged takeover.
- `max_attempts`, which escalates to a human and persists across runs.
- `worker_timeout_sec`, which kills the process tree.
- Crash recovery: 12 of 12 crash points recover (`CHANGELOG.md`, "Crash recovery").
- A simulation harness with honest, sloppy and cheating scripted agents, checked against a baseline (`CHANGELOG.md`, "Self-test and simulation").
- Ralph and Sandcastle only have `maxIterations` and an idle timeout.

**S6. A self-improvement loop.**
- `learnings capture` clusters recurrences.
- A curator turns any learning seen at least twice, or marked critical, into a fix ticket that goes through the same gates.
- Promotion requires an artifact, on a four-tier ladder: architecture, then lint, then tests, then docs (`README.md:231-255`, `how-it-works.md:253-267`).
- Pocock's closest equivalent is running `/improve-codebase-architecture` "every few days" by hand.

**S7. Plan ingestion is idempotent and drift-aware.**
- Each ticket records `source_hash`.
- A changed section is reported as drift rather than overwritten.
- `--chain` and "Depends on" become `depends_on` (`adapters/PLAN-INGESTION.md:30-45`; `src/kahnban/ingest.py:88-98,763`).

**S8. Better context between iterations.**
- Kahnban has the ticket `## Log` with verify output and reject reasons, the handoff baton (`.agents/HANDOFF.json`) and `ACTIVE_SESSION.md` (`README.md:281`).
- This is structured and per-ticket, which beats Ralph's ad-hoc `progress.txt` and Sandcastle's "RALPH:" commit messages (`SC:.factory/implement-prompt.md`).

**S9. Metrics.**
- `status.json` records first-pass yield, cycle time, and rejections by owner and by reviewer (`README.md:226`; `CHANGELOG.md`).
- Neither Ralph nor Sandcastle measures yield.

---

## 3. MEETS: parity

**M1. Grilling.**
- The bundled `grill-with-docs` faithfully reproduces the important rules:
  - rounds over the frontier;
  - numbered questions with recommended answers;
  - "facts are yours, decisions are theirs", including dispatching a subagent;
  - stop when nothing is assumed;
  - the user confirms (`.agents/skills/grill-with-docs/SKILL.md:12-17` vs `PK/.../grilling/SKILL.md:494-510`).
- Terms go to `GLOSSARY.md` (Pocock: `CONTEXT.md`) and decisions to `ADR/` (lines 21-22).

**M2. HITL then AFK.**
- `"autonomy": "attended"` parks a ticket before the gates in `human_gates`; `unattended` runs straight through (`README.md:221`). This matches Ralph's "start HITL, go AFK".

**M3. Fresh context per unit of work.**
- Each worker is a new `claude -p --agent kahnban-{role}` process (`plans/board.config.json` → `workers.default`; `README.md:200-203`). This equals Ralph's fresh iteration.

**M4. Frontier and parallelism.**
- `claim` refuses a ticket while any dependency is not done or its blast radius overlaps an in-progress ticket (`how-it-works.md:61-72`).
- `kahnban run --jobs N` runs parallel coders (`kahnban run --help`; `src/kahnban/runner.py:74-95,186-211`).
- This is equivalent to Sandcastle's unblocked set run under `Promise.allSettled`, with the overlap check done deterministically rather than by an LLM planner.

**M5. Completion signal and iteration cap.**
- `--max-steps` plus the "idle" dispatcher state (`src/kahnban/dispatcher.py:224-245`) match `<promise>COMPLETE</promise>` plus `MAX_ITERATIONS`.

**M6. One test per criterion, red before green.**
- The coder's role steps say "Write the failing test first: verify re-runs your feature tests against the old source" (`roles.json:39`).
- The intent matches Pocock's `/tdd`, and kahnban enforces it (see S1).

---

## 4. FALLS SHORT: partly present or weaker

**F1. Code review is one axis, and the reviewer cannot improve the code.**
- **Reference:** Pocock's `/code-review` is two-axis (Standards with a smell baseline, and Spec), run as parallel subagents. Sandcastle's reviewer **edits**: it simplifies, renames and applies `CODING_STANDARDS.md` (`SC:.../review-prompt.md`).
- **Kahnban:**
  - The QA reviewer checks only test fidelity, blast radius and scope (`roles.json:59-63`; `.claude/agents/kahnban-qa-reviewer.md:11-14`).
  - It does not read the spec. Its facts are `qa_contract` and `branch` (`roles.json:51`).
  - It has no coding-standards source and no smell list.
  - It is forbidden to edit (`roles.json:53,63`).
- The bundled `code-review` skill is a blast-radius and verify checklist (`.agents/skills/code-review/SKILL.md:13-38`). Yet `factory-mode` claims "Dual-axis: Standards compliance and Spec alignment" (`.agents/skills/factory-mode/SKILL.md:55`). That claim is false against the skill it names.
- **Result:** Kahnban vets *correctness and containment*, but nothing in the AFK loop vets *design quality*. For "superb code" this is the largest quality gap.

**F2. The refactor step sits in the wrong place.**
- **Reference:** Pocock now puts refactoring in review, not in the red-green loop (`PK/.../tdd/SKILL.md:237`).
- **Kahnban:** `tdd` keeps "Phase 3: REFACTOR" inside the coder loop (`.agents/skills/tdd/SKILL.md:45-49`). The reviewer cannot refactor (F1).
- **Result:** Cleanup depends entirely on a coder that has already been told "minimal implementation".

**F3. Ticket shape is horizontal, coupled to paths, and capped at 1–3 files.**
- **Reference:** Pocock's tickets are vertical tracer bullets "through every layer (schema, API, UI, tests)". They avoid file paths and handle wide refactors with expand–contract (`PK/.../to-tickets/SKILL.md:106-117,182`). Agent briefs: "Don't reference file paths — they go stale" (`PK/.../triage/AGENT-BRIEF.md`).
- **Kahnban:**
  - It requires exact paths, with no more than `max_blast_radius_files: 3`, enforced by the ready gate (`.agents/skills/to-tickets/SKILL.md:12-13`; `README.md:178`; `plans/board.config.json`).
  - Its `to-spec` *requires* code snippets with type signatures (`.agents/skills/to-spec/SKILL.md:31-34`), the opposite of Pocock's rule (`PK/.../to-spec/SKILL.md:56`).
- This is a deliberate trade, since paths are what make the scope gate and overlap detection possible. But a three-file cap makes a real vertical slice through every layer, with a test, often impossible.
- Nothing in the repo says how to run a wide refactor: a grep for "expand", "vertical" and "seam" finds no guidance.
- The stated rule ("decompose into sequential sub-tickets linked by `depends_on`", `to-tickets/SKILL.md:12`) pushes toward **horizontal** layering, which Pocock names as an anti-pattern.

**F4. No step agrees the test seams.**
- **Reference:** Seams are central for Pocock: they are agreed with the user in `/to-spec`, and `/tdd` writes "no test at an unconfirmed seam".
- **Kahnban:** The spec has no testing-decisions or seams section. The spec analyst picks the test commands per ticket, with no human present (`roles.json:16-18`).
- **Result:** Tests get scattered at whatever seam is nearest the three files.

**F5. No human sign-off on the ticket breakdown.**
- **Reference:** Pocock's step 4 of `/to-tickets` quizzes the user on granularity and blocking edges before publishing (`PK/.../to-tickets/SKILL.md:119-133`).
- **Kahnban:**
  - `to-tickets` goes straight to `kahnban ingest --ready` (`.agents/skills/to-tickets/SKILL.md:33-36`).
  - Spec approval is the "one human gate" (`README.md:163`), and it happens *before* `## Tickets` is written (`grill-with-docs/SKILL.md:35`: "Leave `## Tickets` for `/to-tickets`").
- **Result:** The breakdown, which is where most failures of the "swarm a feature" kind start, is never checked by a human, and no engine check catches a bad dependency graph.

**F6. The dispatcher takes the first ready ticket, not the riskiest.**
- **Reference:** Ralph: "Prioritize risky work… architecture, integration points first."
- **Kahnban:** `available[0]` (`src/kahnban/dispatcher.py:180-181`). There is no priority or risk field in the template (`plans/tickets/template.md`).

**F7. Sandboxing is a tripwire, not isolation.**
- **Reference:** Ralph and Sandcastle run AFK work in Docker, Podman or Vercel sandboxes.
- **Kahnban:** Its own docs say the guard "is a tripwire, not a sandbox" and that a worker can unset `KAHNBAN_ROLE` or read the key file as the same OS user (`README.md:220,224`; `IMPLEMENTATION_STATUS.md:49-55`). Workers run with `--permission-mode acceptEdits` on the host.

**F8. The domain model is not dogfooded.**
- Kahnban's own `GLOSSARY.md` is still the unfilled template ("[Entity / Domain Term 1]").
- `ADR/` has only `0001-record-architecture-decisions.md`.
- `.agents/specs/` holds only `.gitkeep`.
- `require_spec` is `false` on its own board (`plans/board.config.json`).
- Pocock calls `CONTEXT.md` "the single coolest technique". Kahnban ships the mechanism but its own factory runs without it, and the coder role does not preload any glossary (`roles.json:33`).

**F9. Escalations reach the human as a bare string.**
- **Reference:** Pocock's `loop-me` vocabulary has "push right" (defer the checkpoint) and a **brief**: "a tight, decision-ready summary… never the raw output" (`PK/skills/in-progress/loop-me/SKILL.md`). `/triage` keeps a `needs-info` template ("established so far / still need") so nobody re-asks a question.
- **Kahnban:** An escalation is `blocked_on: human: <reason>` plus the `on-escalate` hook (`README.md:219`). There is no structured question, no recommended answer, and no capture of the answer back into the ticket beyond `unblock --reason`.

---

## 5. FAILS: absent or broken relative to the reference

**X1. Nothing decomposes a large spec.**
- **Reference:** Sandcastle's planner and Pocock's `/to-tickets` and `/wayfinder` all turn a big input into a dependency graph of right-sized units.
- **Kahnban `run`:**
  - The only intake worker is the spec analyst. It refines **one** ticket at a time (`dispatcher.py:199-221`).
  - It preloads only `to-tickets` (`roles.json:10`).
  - It is told to **escalate** when "the ticket is too big for 1-3 files" (`roles.json:22`), not to split it.
- **`kahnban ingest`** makes "one backlog ticket per work section" by heuristic heading parsing (`adapters/PLAN-INGESTION.md:11,51-53`). A PRD section such as "Authentication" becomes one ticket, which then escalates.
- **Result:** Handing kahnban a whole spec requires a human-driven `/to-tickets` session first.

**X2. No "spec done" check.**
- `spec coverage` counts tickets that *cite* a requirement, in any column (`specs.py:187-210`). It never checks that they reached `5-done`.
- There is no spec-level acceptance check or end-to-end test after the last ticket lands, and no closing step for the parent.
- Pocock and Sandcastle close issues per ticket and leave the PRD to the human. A factory that walks away needs "every requirement of SPEC-N verified on main" as the stop condition, and kahnban has none.

**X3. No way to resolve unknowns before building.**
- **Reference:** Pocock has `/wayfinder` (decision tickets of type research, prototype, grilling or task, plus fog of war), `/prototype`, `/research`, and `/diagnosing-bugs`.
- **Kahnban:**
  - Every ticket is a build ticket.
  - A spec with an open question can only be escalated.
  - None of these skills is bundled or referenced in any role or skill (grep over `.agents/skills`, `.claude/agents`, `roles.json` finds nothing).
- **Result:** "Interrogate only as needed" has no machinery for research the agent can resolve without the human, such as a library choice or an API probe.

**X4. Skill provenance is misleading and the upstream install is unverified.**
- `setup-kahnban-skills` and the README call the bundled set "Matt Pocock 5-stage pipeline skills" (`.agents/skills/setup-kahnban-skills/SKILL.md:17`). They have drifted materially:
  - `to-spec` inverts the paths/snippets rule;
  - `to-tickets` has no quiz;
  - `code-review` is not two-axis;
  - `tdd` puts refactor in the loop.
- `adapters/README.md:79` and `setup-kahnban-skills:18` advertise `/implement-spec` and `/retro`. Neither exists in Pocock's catalog; plugin 1.2.3 has `implement` and no `retro`.
- `kahnban skills install --source mattpocock` runs `npx skills@latest add mattpocock/skills --yes` (`src/kahnban/skills.py:137-156`).
  - It would install upstream skills under the **same names** as the bundled ones (`grill-with-docs`, `to-spec`, `to-tickets`, `tdd`, `code-review`).
  - Their semantics are incompatible: upstream publishes to an issue tracker and avoids paths.
  - The spec analyst preloads `to-tickets` and depends on kahnban's Method A.
  - This is a likely silent break. **Not executed** (it needs network and npx); it is inferred from code, so verify before relying on it.

**X5. No AFK pull from an external tracker and no PR output.**
- **Reference:** Pocock's flows are issue-tracker native (`ready-for-agent` label, GitHub/Linear), and his factory opens a PR per task with stacked branches.
- **Kahnban:** The board is files only and lands straight on main through the merge queue. There is no PR or human review of the final diff, short of `attended` + `confirm`.
- This is a valid design choice, but for a team setting it gives up the PR as the human review surface.

**X6. Status docs are stale.**
- `IMPLEMENTATION_STATUS.md:29` says "343 tests"; `pytest --collect-only` collects **725**.
- `IMPLEMENTATION_STATUS.md:57` ("`kahnban run` works one ticket at a time") and `NEXT_STEPS.md:26` ("the loop is sequential") contradict `--jobs` (KB-008 is done; `runner.py:81`).
- `kahnban lint --help` says "BL01-BL16" while the README cites BL19 and the CHANGELOG cites BL20.
- An agent reading these docs as its world model gets the wrong picture. This is small, but it is exactly what Pocock's "bad codebases make bad agents" means.

---

## 6. North-star gap: idea → interrogation → spec → tickets → swarm → vetted merge

| Stage | Kahnban today | Pocock reference | Verdict |
| :--- | :--- | :--- | :--- |
| Idea → interrogation | `/grill-with-docs`, faithful rounds | `/grilling` + `/domain-modeling` | **Meets**. Interactive only, which is correct. |
| Interrogation "only as needed" | Facts-vs-decisions rule; no research or prototype tickets | `/wayfinder`, research subagents, `/prototype` | **Falls short** (X3) |
| Spec | `spec new/approve`, frozen R-ids, the human gate | `/to-spec` with seams agreed | **Exceeds** on traceability, **falls short** on seams and testing decisions (F4) |
| Tickets | Human runs `/to-tickets`, then `ingest --ready`; no breakdown review; 1–3 files | Vertical slices, blocking edges, user quiz, expand–contract | **Falls short** (F3, F5) |
| Swarm | `kahnban run --jobs N`: deterministic dispatcher, gates, leases, escalation | Sandcastle planner, parallel implementers, merger | **Exceeds** on safety, **meets** on parallelism |
| Vetting | Proof gate, scope gate, independent approve, merge queue | Two-axis review, editing reviewer, typecheck and tests | **Exceeds** on correctness, **falls short** on design quality (F1, F2) |
| Done | Per ticket only | Per issue; PRD is the human's | **Fails** at the spec level (X2) |

### What blocks "hand it a whole spec and walk away"

1. **Decomposition is a human-interactive step** (X1).
   - `kahnban run` cannot turn an approved spec, or a large requirements document, into tickets.
   - It refines tickets that already exist, one at a time, and escalates anything bigger than three files.
   - So "walk away" begins only after someone has sat through `/to-tickets` and every ticket already fits in three files.
2. **No stop condition at the spec level** (X2). The run stops when the board is idle, not when the spec's requirements are verified together on main.
3. **Unknowns become blocked tickets, not research** (X3). Any open question parks the ticket for a human. A long autonomous run over a real spec will accumulate escalations without trying to resolve them itself.
4. **The quality ceiling is "passes its own tests inside three files"** (F1, F2, F3). Nothing in the AFK loop asks whether the code is well designed or matches the spec's intent beyond its criteria. Over many tickets, that builds the "ball of mud" Pocock warns about.
5. **Unmeasured at scale.** Live agents have only run toy, one-line tickets (`IMPLEMENTATION_STATUS.md:60-61`). Pocock's factory runs on his real repos, and Sandcastle has its own `.factory/` dogfooding.

**Bottom line through this lens.** The engine already has the back half of the factory (swarm, vet, merge), and it is stronger than Pocock's public tooling there. The gaps are on either side of the swarm:
- **Upstream:** the factory needs an autonomous decomposer and a research/decision step, so that a whole spec can be fed in.
- **Downstream:** it needs a design-quality reviewer and a spec-level done check, so that "fully tested" also means "superb".

---

## 7. STEAL LIST (ranked)

**1. Add a decomposer role to `kahnban run`. Effort: M.**
- **What:**
  - Add a `planner` role in `src/kahnban/templates/roles.json`, plus a dispatcher row in `src/kahnban/dispatcher.py` placed before refine.
  - It triggers when an *approved* spec has no `## Tickets`, or when a ticket is escalated as "too big".
  - The worker writes vertical slices with `Depends on:` edges into the spec's `## Tickets`. The runner then runs `kahnban ingest <spec> --ready` itself.
  - Change the spec analyst's `escalate_when` "too big" (`roles.json:22`) into a hand-off to the planner.
- **Why:** This is Sandcastle's planner and Pocock's `/to-tickets` made autonomous, and it is the main blocker for "hand it a spec and walk away" (X1).
- **Keep the human gate as an option:** add `human_gates: ["breakdown"]` with `kahnban confirm` (F5).

**2. Two-axis review, and let a reviewer refactor. Effort: M.**
- **What:** Rewrite `.agents/skills/code-review/SKILL.md` on the model of `PK/.../code-review` (Standards + Spec as parallel subagents, Fowler smell baseline, repo `CODING_STANDARDS.md`).
- Give `qa_reviewer` the spec in its facts (`roles.json:51`): `spec:`, the requirement text for its `covers:`, and the PRD path.
- Add an optional **refine** pass, as in Sandcastle's reviewer: a worker allowed to edit inside the blast radius and commit "Review –" changes, after which `verify` re-runs (since a new tip invalidates the approval, this already composes).
- Fix the false "Dual-axis" claim in `factory-mode/SKILL.md:55`. Move refactor out of `tdd` (`tdd/SKILL.md:45-49`) to match upstream.
- **Why:** F1 and F2. This is the cheapest lever on "superb code".

**3. A spec-level done check. Effort: S.**
- **What:**
  - Make `kahnban spec coverage` (or a new `spec status`) report requirements whose covering tickets are not all in `5-done` (`src/kahnban/specs.py:187-210`).
  - Add an optional `## Acceptance` / `Validation:` block on the spec, run on main once every ticket is done.
  - `kahnban run` exits with "SPEC-N complete" or "SPEC-N stuck: …".
- **Why:** X2. It gives "walk away" a real `<promise>COMPLETE</promise>`.

**4. Agree seams and testing decisions in the spec. Effort: S.**
- **What:**
  - Add a `## Testing decisions / Seams` section to the `kahnban spec new` template and to `grill-with-docs` / `to-spec`.
  - Have the spec analyst and planner pull criterion tests from those seams.
  - Optionally add a lint check that each ticket's test file lies in a seam the spec declared.
- **Why:** F4. Pocock's highest-leverage test-quality rule.

**5. Research and decision tickets: a lightweight `/wayfinder`. Effort: M.**
- **What:**
  - Add a `ticket_type: research|decision` (template plus `ready` gate exemption: no blast radius; the deliverable is a doc under `docs/research/`).
  - Add a `researcher` role whose output is a cited Markdown file that unblocks dependants.
  - Bundle or require `mattpocock-skills:research`, `prototype` and `diagnosing-bugs`.
- **Why:** X3. It turns "escalate to human" into "resolve without the human where possible", so the human is asked "only as needed".

**6. Vertical slices and expand–contract in `to-tickets`. Effort: S.**
- **What:**
  - Port Pocock's vertical-slice rules and expand–contract section into `.agents/skills/to-tickets/SKILL.md`.
  - Allow `max_blast_radius_files` to be overridden per ticket with a logged reason, or count only source files toward the cap so tests don't use it up (`README.md:178`).
  - Replace "split by `depends_on`" (line 12) with "split by behaviour".
- **Why:** F3.

**7. Structured escalation briefs. Effort: S.**
- **What:** `kahnban escalate` takes `--question` (repeatable) and `--recommend`, and writes a `## Questions` block in the needs-info style ("established so far / need from you"). `unblock --answer` records the answers in the ticket so a worker reads them.
- Touches `core` (escalate/unblock) and the `cli`.
- **Why:** F9. It follows Pocock's push-right/brief idea, so the human reviews a decision-ready summary instead of reading a log.

**8. Prioritise risk in dispatch. Effort: S.**
- **What:** Add `priority:` / `risk:` frontmatter to `plans/tickets/template.md`, and have `dispatcher.py:180` sort `available` by it, then by number of dependents (unblock the most), then by id.
- **Why:** F6, Ralph's risky-first rule.

**9. A container worker mode. Effort: M–L.**
- **What:** Add a documented `workers.default` that runs `claude -p` inside Docker, with the worktree bind-mounted and no host home directory or key file, in the style of Sandcastle's `docker()` provider. Add a `kahnban skills install --harness claude --sandbox docker` path.
- **Why:** F7. It turns the tripwire into isolation, and also closes the signing-key exposure that `IMPLEMENTATION_STATUS.md:49-55` admits.

**10. Fix skill provenance and the upstream install collision. Effort: S.**
- **What:**
  - Rename the bundled forks to `kb-to-spec`, `kb-to-tickets` and so on, or describe them as "adapted from".
  - Drop the nonexistent `/implement-spec` and `/retro` (`adapters/README.md:79`, `setup-kahnban-skills/SKILL.md:18`).
  - Make `--source mattpocock` install upstream *alongside* the bundled set instead of in place of it, and add a test for the collision (`src/kahnban/skills.py:137-156`).
- **Why:** X4.

**11. Dogfood the domain model. Effort: S.**
- **What:**
  - Fill in kahnban's own `GLOSSARY.md` (ticket, gate, contract, blast radius, baton, lease, proof).
  - Add ADRs for D1–D13 from `plan.md` §0.
  - Turn on `require_spec` for engine features.
  - Preload the glossary in every role's facts.
- **Why:** F8. Pocock's "bad codebases make bad agents" applies to kahnban's own factory.

**12. Refresh the stale status docs. Effort: S.**
- **What:** `IMPLEMENTATION_STATUS.md:29,57`, `NEXT_STEPS.md:26` and the `lint --help` BL range in `src/kahnban/cli.py`.
- Consider generating the test count instead of hand-writing it.
- **Why:** X6.

---

### Sources
- Local Pocock skills v1.2.3: `C:\Users\User\.claude\plugins\cache\mattpocock\mattpocock-skills\1.2.3\` (README, grilling, grill-with-docs, to-spec, to-tickets, implement, tdd, code-review, triage and AGENT-BRIEF, wayfinder, loop-me)
- Sandcastle repo: https://github.com/mattpocock/sandcastle (`src/templates/parallel-planner-with-review/{plan,implement,review,merge}-prompt.md`, `main.mts`; `.factory/implement-task.ts`, `.factory/implement-prompt.md`, `.factory/review-prompt.md`; `.out-of-scope/bundled-workflow-templates.md`)
- Ralph tips: https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum
- Software factory cohort listing (secondhand; the page returned 404 when fetched): https://www.aihero.dev/boss/software-factories-for-real-engineers-xdy1m
- AFK agents workshop: https://www.aihero.dev/workshops/afk-agents~h0fsr
