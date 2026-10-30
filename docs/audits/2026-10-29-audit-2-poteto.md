# Audit 2: kahnban measured against poteto (Lauren Tan) / pstack

Date: 2026-10-29. Repo: `C:\github\kahnban` at `a38a0c0`, read-only. Evidence is given as `file:line` or a URL. Claims are labelled **measured** (I ran or read it), **inferred** (from the code, not run), or **sourced** (from a third-party write-up, not the primary).

## 0. "Software kitchen": not found

I found no "software kitchen" source by poteto. Searches covered her GitHub, the pstack README and poteto-mode SKILL.md, the AI Engineer speaker page, Flavio Copes' two pstack write-ups, The Neuron explainer, and mirrors of her X guide (Parts 1 and 2). None of them uses a kitchen or chef metaphor. Two of them say so outright: The Neuron explainer, and Flavio's deep dive, which uses "software factory" and "small engineering organization" instead. Her own metaphors are **gardener / maintainer** (X guide Part 1, via mirror) and the **lever** ("Build the Lever"). The audit below is against **pstack**, which is what she actually publishes. If the user has a specific kitchen talk or post in mind, it should be supplied. I did not invent one.

Sources:
- pstack (canonical, MIT, author Lauren Tan): https://github.com/cursor/plugins/tree/main/pstack
- poteto-mode router: https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/poteto-mode/SKILL.md
- Principle leaves, e.g. https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/principle-laziness-protocol/SKILL.md (the same pattern holds for the others)
- Guide Part 1, "verification is all you need": https://x.com/poteto/status/2094457600259842065 (read via the mirror https://youmind.com/landing/x-viral-articles/pstack-guide-ai-verification-skills)
- Guide Part 2, "what to build": https://x.com/poteto/status/2097732320606507506 (mirror https://youmind.com/vi-VN/landing/x-viral-articles/pstack-guide-part-two)
- Secondary: https://flaviocopes.com/pstack/, https://flaviocopes.com/poteto-mode.md, https://www.theneuron.ai/explainer-articles/pstack-explained-lauren-tans-system-for-trustworthy-ai-agents/
- Searches with no kitchen hit: https://ai.engineer/speakers/lauren-tan and her GitHub profile https://github.com/poteto

## 1. Reference summary (pstack)

**Shape.** Thirty-four skills, 24 `principle-*` leaves, 23 playbooks under `poteto-mode`, and two subagents: `poteto-agent` and `comment-sicko` (the pstack tree). The README tagline is "if you want to go fast, go deep first". The stated aim is less code at higher quality, with parallelism earned once a single agent can be trusted (the Part 1 mirror and the README).

**Loop (`poteto-mode`).**
1. State the goal, the problem and the smallest expected change. Do not wait for confirmation.
2. Match a playbook and copy its steps verbatim into the todo list. A skipped step stays listed with `skip: <reason>`.
3. Route by trigger: `how` for non-trivial changes, `interrogate` for contested designs, `architect` for code that crosses a function boundary, `swarm` or `arena` for fan-out.
4. Name the data shape before writing code.
5. Delegate to `poteto-agent` with an explicit model per role. The lead owns every subagent's output and writes its own summary.
6. Verify on the real surface.
7. Open a PR.
8. The final reply names each principle that shaped a decision and labels each claim as measured, inferred or guessed.

(All from poteto-mode SKILL.md.)

**Principles (24).**
- Core: laziness-protocol, foundational-thinking, redesign-from-first-principles, attack-the-premise, subtract-before-you-add, minimize-reader-load, outcome-oriented-execution, experience-first, exhaust-the-design-space, build-the-lever.
- Architecture: model-the-domain, boundary-discipline, type-system-discipline, make-operations-idempotent, migrate-callers-then-delete-legacy-apis, separate-before-serializing-shared-state.
- Verification: prove-it-works, fix-root-causes, sequence-verifiable-units, test-behavior-not-implementation, explain-the-number.
- Delegation: guard-the-context-window, never-block-on-the-human.
- Meta: encode-lessons-in-structure.

Upstream leaves set `disable-model-invocation`. They are read through the poteto-mode index, not auto-triggered (WebFetch of the never-block and laziness leaves).

**Verification philosophy.** "Verification is all you need" (Part 1). Each project gets a `verify-<app>` skill plus a feature map ("materialized memory"), kept current with `maintain-verification-skill`. Bugs are reproduced on the same surface first. Inconclusive is not a pass. Numbers go through a benchmark checklist (`explain-the-number`). Before review, `/deslop` and `/no-comments` run (poteto-mode SKILL.md).

**Planning philosophy.** "Prototyping is planning, but with code" (Part 2). The pieces are restating the problem in your own words (`in-your-own-words`), competing architectures across model families (`architect` and `arena`), multi-model review triage (`interrogate`), and multi-phase plans whose tasks are each verified by running code and checked by a validation script (Part 2 mirror).

**Human policy.** Do not ask about facts you can observe. Ask only about product or preference calls. Pause for irreversible actions such as force-pushes to shared branches, deploys, data deletion and customer messages. Under full autonomy, apply a default and report it (poteto-mode SKILL.md, "When to ask").

**Autonomy at scale.** `autopilot-full` runs a queue of independent PRs through verification and merge. `orchestrate` covers multi-day programs with a standing coordinator. `autonomous run` drives toward a checkable finish condition (flaviocopes.com/pstack). Self-reported throughput is about 2,000 PRs a month, with 2,462 in August (sourced; not independently verified).

## 2. Provenance of kahnban's borrowed skills (measured)

- These kahnban skills match pstack upstream text: the 11 principle leaves, `how`, `why`, `no-comments`, `unslop`, `create-verification-skill`, and `change-impact`. `change-impact` is pstack's `blast-radius` renamed, and `NEXT_STEPS.md:20-21` says "rename the pstack `blast-radius` skill". The principle bodies match upstream content. I compared laziness-protocol, guard-the-context-window, never-block-on-the-human and encode-lessons-in-structure directly; upstream is just as terse.
- **No attribution or licence.** The repo has no LICENSE or NOTICE file, and `.agents/skills.lock.json` records only SHA-256 hashes, with no source URL or upstream version. pstack is MIT, which requires the copyright notice to travel with the copies. The skills are also duplicated four times, in `.agents/skills`, `.claude/skills`, `adapters/skills` and `src/kahnban/templates/skills`, so updating from upstream is manual and error-prone.
- **Frontmatter deliberately changed.** Kahnban strips `disable-model-invocation`, and `skills_check.py:60-68,112-115` turns any skill that keeps it into an error. That is a defensible choice, because it lets roles preload skills. The cost is that the principles are no longer reached through a curated index. They depend on description-matching, which a headless worker may never trigger.
- **Misattribution.** `.agents/skills/reflect/SKILL.md:10` ("The Lauren Tan Clustering Invariant") and `src/kahnban/learnings.py:4` credit occurrence-clustering to Lauren Tan. pstack's `reflect` is something else: a multi-reviewer transcript review with an accepted / rejected / backlog synthesizer and no change without approval (flaviocopes.com/pstack). Clustering is closer to the task-observer "check for a restatement" pattern. The name should be removed or corrected.

## 3. SUCCEEDS: where kahnban goes beyond pstack

1. **prove-it-works is enforced by code, not by discipline.**
   - The `require_proof` red check re-runs the feature tests against the merge-base source and refuses the ticket if they still pass (`core.py:2017-2077`; README:145).
   - Every criterion must name a test (`core.py:512-519`).
   - The blast radius must include a test file (`core.py:539`).
   - pstack relies on the agent following poteto-mode and the verification skill. Kahnban makes an unproven change unmergeable.
2. **sequence-verifiable-units and laziness are structural at the ticket level.**
   - `max_blast_radius_files` (`init` writes 3) refuses an oversized ticket with "split the ticket" (`core.py:528-532`).
   - Verify refuses a diff outside the declared radius (README:143).
   - The merge queue tests main plus the branch, one merge at a time, under the board lock (README:153-155).
   - pstack's "small self-contained PRs" (Part 2) is advice; here it is a gate.
3. **Frozen contracts and anti-tamper.**
   - `contract_hash` and `contract_sig` refuse post-ready edits to the criteria, radius or validation (README:141, 220).
   - Approvals are HMAC-signed, the reviewer must differ from the owner, and approval is bound to the verified tip (README:151, 220).
   - pstack has nothing comparable: it trusts the lead agent's review.
4. **Role guard.** A PreToolUse hook plus CLI/MCP-side enforcement blocks out-of-remit edits, `git push`/`merge`/`reset --hard`, override flags, and `kahnban` commands outside the role (README:224; `src/kahnban/guard.py`). The README is honest that this is a tripwire, not a sandbox.
5. **never-block-on-the-human, with a bounded escape.**
   - `max_attempts` leads to automatic escalation with `blocked_on: human:` (README:219).
   - The Stop-hook nudge keeps workers from quitting early (README:224).
   - `attended` versus `unattended` with `human_gates` (README:221) gives a structural version of pstack's "pause for irreversible, default otherwise".
6. **Machine-checkable traceability from intent to ticket.**
   - `spec approve` freezes requirements (`requirements_hash`).
   - Tickets carry `covers: [R1]`; `spec coverage` exits 1 until every requirement is covered; lint BL18 enforces it (README:161-182).
   - pstack's multi-phase plan has a validation script, but no requirement-to-ticket coverage gate.
7. **encode-lessons-in-structure is a pipeline, not a sentence.**
   - The `./learnings/` queue clusters occurrences (`learnings.py:224-229`).
   - The dispatcher puts `harvest_learnings` ahead of new work when a learning recurs or is critical (`dispatcher.py:147-158`).
   - The curator turns each such learning into a gated fix ticket.
   - `promote` requires an artifact that exists (IMPLEMENTATION_STATUS.md, "Learn" row).
   - pstack's `encode-lessons-in-structure` leaf is three sentences with no machinery behind it.

## 4. MEETS: parity

- **Autopilot-full ≈ `kahnban run --jobs N`.** A queue of independent work goes through verification and merge unattended (`runner.py:74-95,186-211`; README:186-197).
- **Per-role model choice ≈ pstack's explicit model per role.** `workers.get(role) or workers.get("default")` (`runner.py:440`).
- **Cheap, file-path-based handoffs ≈ "pass file paths rather than inlined context".** The relay baton is `.agents/HANDOFF.json` (README:281).
- **Interrogation of the human ≈ the "When to ask" policy.** `grill-with-docs` asks questions in rounds with a recommended answer for each, and "Facts are yours, decisions are theirs" (`.agents/skills/grill-with-docs/SKILL.md:13-16`). This mirrors pstack's "don't ask about facts you can observe".
- **TDD.** The `tdd` skill plus the red check match pstack's `tdd` and the failing-test-first story order in sequence-verifiable-units.

## 5. FALLS SHORT: partial or weaker

1. **Most principles are text only, and the factory's workers never load them.**
   - No role preloads any `principle-*` skill. The preload lists are: spec_analyst `[to-tickets]`, coder `[tdd, coder-agent, unslop, no-comments, how, why]`, qa_reviewer `[qa-reviewer-agent]`, curator `[harvest-learnings]` (`src/kahnban/templates/roles.json`). `coder-agent`, `tdd` and `qa-reviewer-agent` never mention a principle (grep, measured).
   - The principles are cited only in `factory-mode` (`src/kahnban/templates/skills/factory-mode/SKILL.md:16-47`), which is an interactive-session skill. `kahnban run` workers never load it.
   - Structural enforcement by principle:

   | Principle | Enforcement in kahnban |
   | :--- | :--- |
   | prove-it-works | Code gate. |
   | sequence-verifiable-units | Code gate. |
   | laziness | Partial code gate: a file-count cap. There is no LOC or diff-size budget, and no "consolidate decisions" check. |
   | never-block | Code: escalation, attempts and autonomy settings. |
   | encode-lessons | Code pipeline, but capture is voluntary (see 5.2). |
   | guard-the-context-window | None. `worker_timeout_sec` is the only budget; there are no turn or token caps per role. |
   | boundary-discipline | Text only. |
   | model-the-domain | Text only. |
   | subtract-before-you-add | Text only. |
   | fix-root-causes | Text only. |

   - The QA reviewer's checklist (`roles.json`, qa_reviewer steps) covers test fidelity and scope only. It never asks whether the change was the smallest, whether the root cause was fixed, or whether the diff subtracted first.
2. **Learning capture depends on the agent remembering.**
   - `done` only prints an advisory to run `/reflect` (`cli.py:145`; `harnesses.py:191`).
   - The runner never records a rejection, an escalation, a refused gate or a repeated verify failure as a learning, although every one of those is already a logged, structured event (`grep learning runner.py core.py`: no capture call, measured).
   - The live board shows the result: one pending learning, with "No problem description recorded" (`learnings/LRN-0001-...md`).
   - pstack's `reflect` is heavier: it runs multiple reviewers and a synthesizer.
3. **Verification is limited to command exit codes.**
   - Kahnban proves that tests depend on the change. It does not prove that the product behaves, which is pstack's centre of gravity (`verify-<app>` plus the feature map).
   - `create-verification-skill` is installed but unwired. It writes to `.cursor/skills/verify-<app>/` (`create-verification-skill/SKILL.md:24,35`) and links `references/feature-map-example/`, which does not exist (`ls` of the skill directory, measured).
   - No role, gate or validation default calls a verify skill, and `maintain-verification-skill` is not imported.
   - The README itself admits that the red check "proves the tests depend on the change, not that they fail for the right reason" (IMPLEMENTATION_STATUS.md, Known limits).
4. **Review is single-model and single-reviewer.** pstack uses `interrogate`, where several models review one diff and the findings are triaged into act on, consider, noted and dismissed. Kahnban runs one `qa-reviewer` worker. Per-role worker commands would allow a different model, but there is no fan-out or triage.
5. **Docs disagree with the code.**
   - `NEXT_STEPS.md` ("Parallel workers in `kahnban run` … the loop is sequential") and `IMPLEMENTATION_STATUS.md` ("`kahnban run` works one ticket at a time") are contradicted by `--jobs` (`cli.py:776`; `runner.py:81`).
   - IMPLEMENTATION_STATUS also says "343 tests", while the tests directory now holds about 60 files.

## 6. FAILS: absent or broken

1. **`no-comments` is preloaded into every coder and cannot work.**
   - It spawns `subagent_type: "comment-sicko"` and defers to "the Subagents section of the **poteto-mode** skill" (`.agents/skills/no-comments/SKILL.md:18`). It also cites `principle-redesign-from-first-principles` (`:21`).
   - None of the three exists in the repo (`.claude/agents/` holds only the four kahnban agents; grep, measured).
   - **`kahnban skills check` still reports `[OK]`** (run, measured). Its reference regex matches only `/slash` mentions (`skills_check.py:28`), so `**bold**` and quoted subagent references pass.
   - Inferred consequence: a headless coder either fails the step or silently skips it.
2. **Other dangling cross-references.**
   - `principle-prove-it-works/SKILL.md:21` cites `show-me-your-work`.
   - `principle-sequence-verifiable-units/SKILL.md:16` cites `build-the-lever`.
   - Neither is installed, and the same blind spot in `skills check` misses both.
3. **No router or playbook layer.** pstack's core value is `poteto-mode`: it matches the task to a playbook, copies the steps verbatim into the todo list, keeps skipped steps with a reason, names the principles that shaped decisions, and labels claims measured, inferred or guessed. Kahnban has a fixed column pipeline. Bug-fix (reproduce first), perf (benchmark checklist), refactor, migration and investigation tickets all go through the same coder prompt (`roles.json`, coder steps). There is no `figure-it-out` for work that does not fit.
4. **No premise attack or restatement step.** pstack's opener is "state goal, problem and the smallest change; if evidence rules out the requested change, show that and stop", together with `in-your-own-words` and `attack-the-premise`. The spec analyst's steps go straight to filling in criteria, radius and validation (`roles.json`, spec_analyst). Its escalation conditions cover size and spec changes, not a wrong premise.
5. **No design exploration before the contract is frozen.** There is no `architect`, `arena` or `prototype` equivalent. Kahnban freezes a contract at `ready` before any code exists, which runs against "Prototyping is planning, but with code" (Part 2). A wrong design is found only after verify, review or merge, and each discovery costs a full rejection loop.
6. **Thirteen of the 24 principles are missing.** The most relevant to a factory are:
   - `build-the-lever`, which is referenced but missing;
   - `test-behavior-not-implementation`, the natural reviewer rubric;
   - `explain-the-number`, needed for metrics and first-pass yield claims;
   - `make-operations-idempotent`;
   - `attack-the-premise`;
   - `type-system-discipline`.

## 7. North-star gap (idea → interrogation → spec → tickets → swarm → vetted merge)

| Step | kahnban today | pstack lens verdict |
| :--- | :--- | :--- |
| Idea → interrogation | `/grill-with-docs` asks in rounds and records GLOSSARY and ADR entries (`grill-with-docs/SKILL.md`). It is interactive only and the runner never invokes it. | Good questioning discipline. No prototyping is allowed to answer questions ("let the agent answer open questions with experiments", Part 2). |
| Spec | `spec new` / `spec approve`, with the approval reserved to a human by the guard (README:167-182). | Correct. This matches "product direction comes from the human". |
| Spec → tickets | `/to-tickets` writes `## Tickets`, then `ingest --ready` and `spec coverage` (README:170). | **Gap:** the dispatcher has no "approved spec without tickets" action. Its action list is cleanup / merge / review / resume / claim / refine / harvest / idle (`dispatcher.py:18`). The decomposition step is a human-session skill, not a factory step. |
| Tickets → swarm | `run --jobs N` with leases and radius-overlap refusal (`runner.py:186-211`; `dispatcher.py:170-178`). | **Hazard (inferred, not reproduced):** `ready` refuses a ticket whose `depends_on` is not done (`core.py:1426-1440`), but the dispatcher's `_is_open` filters only on `blocked_on` (`dispatcher.py:34-39`). It picks `intake_candidates[0]` (`dispatcher.py:199-203`), which can be a dependency-blocked ticket. The spec analyst would then fail `ready` repeatedly until `max_attempts` escalates it to a human. No dispatcher test covers `depends_on` (grep, measured). With a large spec of many three-file tickets, this would turn the dependency chain into an escalation storm. |
| Vetted merge | Red check, single review, merge queue, signed approvals. | Stronger than pstack on test-dependence and tamper evidence. Weaker on real-surface verification and multi-model review. |
| Learn | Curator pipeline. Capture is voluntary. | Half a loop. |

**What blocks "hand it a whole spec and walk away":**
1. There is no factory step that turns an approved spec into tickets.
2. The dispatcher is not dependency-aware.
3. There is no design or prototype phase before contracts freeze, so a big spec's architectural mistakes surface as serial rejections.
4. Verification proves tests, not product behaviour.
5. Failures do not automatically feed learnings.
6. The coder's preloaded `no-comments` is broken.
7. The evidence base is thin: "Live agents have only run on toy tickets (one-line changes)" (IMPLEMENTATION_STATUS.md, Known limits). pstack's lesson is to earn trust in one agent on real work before parallelising (Part 1). Kahnban has parallelism but no measured first-pass yield on a real multi-ticket spec.

## 8. STEAL LIST (ranked)

| # | What | Why (pstack evidence) | Touches | Effort |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Fix `no-comments`: either import `comment-sicko` as a fifth agent and drop the poteto-mode reference, or remove `no-comments` from the coder preload. Also extend `SKILL_REF` to catch `**skill**` and `subagent_type: "x"`. | It is broken today and `skills check` says OK. pstack ships `agents/comment-sicko.md`. | `roles.json` (coder.skills), `.claude/agents/`, `skills_check.py:28`, `tests/test_skills.py` | S |
| 2 | Make the dispatcher dependency-aware: skip backlog and ready tickets whose `depends_on` is not done, reusing `core._dependency_problems`, and add a dispatcher test. | Without it, autonomous decomposition of a whole spec cannot work. | `dispatcher.py:34-39,170-203`, `tests/test_dispatcher.py` | S |
| 3 | Auto-capture learnings from structured failures: each reject, escalation and verify failure past N attempts calls `learnings.capture_learning`, with the ticket, gate and refusal text. | encode-lessons-in-structure: "the instruction is the symptom". The current loop depends on an agent remembering `/reflect`. | `runner.py` (after each gate refusal), `core.reject`, `learnings.py:337` | S-M |
| 4 | Add a `decompose_spec` dispatcher action and runner step: an approved spec with no `## Tickets`, or with `spec coverage` below 100%, goes to the spec analyst running `/to-tickets` and then `ingest --ready`. | This closes the north-star step from spec to swarm. It mirrors pstack's multi-phase plan with a validation script (Part 2). | `dispatcher.py`, `runner.py`, `roles.json` (spec_analyst commands: `ingest`, `spec coverage`) | M |
| 5 | Preload a curated principle set per role, and give the QA reviewer a principle rubric: smallest diff, root cause not symptom, `test-behavior-not-implementation`, subtract first. Require the decision record to name the principle that drove each rejection. | poteto-mode: "Name each principle that shaped a decision". Today no worker sees any principle. | `roles.json` (skills, qa_reviewer steps), import `principle-test-behavior-not-implementation` | S |
| 6 | Add a "premise" step to the spec analyst: restate the ticket in its own words and state the smallest change. If the evidence rules the change out, write that in the ticket and `escalate`. | pstack opener plus `in-your-own-words` and `attack-the-premise`. It is cheaper than a rejection loop. | `roles.json` (spec_analyst steps, escalate_when), import two principle leaves | S |
| 7 | Wire real-surface verification: fix `create-verification-skill`'s paths (`.agents/skills/verify-<app>` rather than `.cursor`) and its missing `references/`. Add an optional `verify_skill` board key whose journey command `verify` runs as a third validation tier. | Part 1, "verification is all you need". Today tests prove dependence, not behaviour. | `create-verification-skill/SKILL.md:24,35`, `core.verify` (~`core.py:2077`), `config.py` | M |
| 8 | Multi-reviewer interrogation: let `qa_reviewer` fan out to K worker commands (different models) and approve only on agreement; a dissent becomes a structured reject. | pstack `interrogate` and `arena`, with cross-model judges. | `runner.py:440` (worker lookup), `roles.json`, `core.approve` | M |
| 9 | Typed ticket playbooks: a `kind:` frontmatter field (bug, perf, refactor, feature) selects extra coder steps and ready-gate rules. For example, a bug ticket must carry a reproduction criterion that fails on main, and a perf ticket must carry a benchmark command. | pstack playbooks: reproduce first for bugs, a benchmark checklist for numbers. A small slice of poteto-mode without a router. | `roles.json`, `core.ready_problems` (`core.py:1395`), `templates/ticket.md` | M |
| 10 | Add a diff-size budget alongside the file cap (`max_diff_lines`, refused at verify) and a context budget per worker (`--max-turns` in the worker template). | Turns laziness and guard-the-context-window from text into gates. | `config.py:131`, `core.verify`, the runner's default worker command (`runner.py:31`) | S |
| 11 | Provenance hygiene: add `LICENSE` and `THIRD_PARTY_NOTICES` naming pstack (MIT, Lauren Tan), record `source` and `upstream_rev` per skill in `skills.lock.json`, rename the "Lauren Tan Clustering Invariant", and collapse the four skill copies to one source plus generated copies. | MIT notice obligation, plus accurate attribution. | repo root, `.agents/skills.lock.json`, `trust.py`, `reflect/SKILL.md:10`, `learnings.py:4` | S |
| 12 | A design spike before freezing: an optional `spike` ticket kind with no `require_proof`, whose output is an ADR plus a throwaway branch. Dependent tickets `depends_on` it. | "Prototyping is planning, but with code"; `architect`. | `core.ready_problems`, `templates/adr.md`, `to-tickets` skill | M |
| 13 | Correct the stale docs on parallelism and test counts. | Minimize reader load. | `NEXT_STEPS.md`, `IMPLEMENTATION_STATUS.md` | S |

**Bottom line.** Kahnban takes pstack's verification and sequencing principles further than pstack does by turning them into gates, and its signed-contract and guard layer has no pstack counterpart. It falls short on pstack's other half: judgment before code (premise, restatement, prototyping, competing designs), verification on the real product surface, multi-model review, and the router or playbook layer that makes principles show up in decisions. The principle skills it imports are mostly decoration in the factory, because no worker role loads them, and one preloaded skill (`no-comments`) is broken while `skills check` passes it.
