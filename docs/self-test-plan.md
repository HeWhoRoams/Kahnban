# Self-test plan: prove every part of kahnban works, on its own

Goal: one command a contributor (or CI) can run that shows every command, gate, entry point and install path of kahnban working, plus a slower tier that has kahnban run its own development.

## Where it stands (measured 2026-10-25)

- 532 tests, all green, on `main` at `02272bf`. Wall time **9m10s** locally (the README says about 5 minutes).
- CI runs `pytest -q` on Windows and Linux, Python 3.10 to 3.13. Nothing else runs in CI.
- No coverage tool is installed, so nobody knows which lines run.
- Rough reach per area, from grepping the tests:
  - **CLI:** every top-level command is named in at least one test. Lightly covered: `lease` (1 file), `sync`, `unblock`, `confirm`, `feedback` (2 each), `reject`, `session`/`handoff` (3), `spec` subcommands, `learnings promote`.
  - **MCP:** 22 tools are registered, and only 2 tests start the server as a real stdio process. `tests/test_mcp_server.py` never names 13 of the tools: `plan_ingest`, `ticket_ready`, `session_status`, `session_get`, `session_update`, `next`, `ticket_approve`, `ticket_reject`, `ticket_merge`, `ticket_lease`, `ticket_escalate`, `feedback`. Some may be tested elsewhere, for example `plan_ingest` in `test_entrypoints.py`, so step 2 settles this.
  - **Packaging:** nothing tests an installed wheel. `package-data` globs (`templates/skills/**/*.md`) are never checked from outside the source tree.
  - **Factory loop:** `kahnban run` is tested with fake Python workers only. Real `claude -p` runs happened by hand (IMPLEMENTATION_STATUS.md) and are not repeatable.
  - **Drift:** `adapters/skills/` and `src/kahnban/templates/skills/` are byte-identical copies today, and no test keeps them that way.
  - **Dogfood:** this repository has no `plans/` board. NEXT_STEPS.md already lists "run this repository's own work on a kahnban board".

## Tiers

| Tier | What it proves | Runs where | Target time |
|---|---|---|---|
| T0 | Unit and integration suite (exists) | every push, CI matrix | under 5 min |
| T1 | Coverage floor and contract tests: every command and MCP tool has a test | every push | adds under 1 min |
| T2 | Installed-wheel smoke: build, install in a clean venv, drive the full lifecycle through the real `kahnban` entry point | CI, one job per OS | about 2 min |
| T3 | Adversarial gate matrix: try to get past each gate with a no-op, tampered or self-signed input | every push (part of T0) | in T0 |
| T4 | Live harness smoke: a real `claude -p` worker drives one toy ticket from ready to done | opt-in, `KAHNBAN_LIVE=1`, never CI | about 10 min |
| T5 | Dogfood: kahnban's own backlog runs on a kahnban board in this repo | ongoing | — |
| T6 | Workflow simulation with scripted agents, a scorecard and a before/after comparison (see [simulation-plan.md](simulation-plan.md)) | fast set on every PR, full set nightly | under 3 min / nightly |

`python -m kahnban selftest` is **not** proposed: the tiers are pytest markers plus one script, so no new command needs maintaining.

## Steps

Write the failing test first, as in the remediation plans. One commit per step on `main`.

### 1. Measure before changing anything
- Add `coverage>=7` to the `dev` extra. Run `python -m coverage run -m pytest` and `coverage report --skip-covered`, and save the per-module table in this doc.
- Run `pytest --durations=30` and record the slowest tests. Each git-heavy test builds its own repo, which is the likely cost.
- **Done when:** this doc has the real coverage per module and the 30 slowest tests. Every later step cites those numbers.

**Measured (2026-10-25, Windows, Python 3.x, `coverage run --source=src/kahnban -m pytest`):** 90% line coverage, 6415 statements, 640 missed, 532 tests pass. In-process only: code that runs in child processes (`__main__.py` at 0%, the MCP server's stdio loop, worker scripts) is not measured, so those numbers are floors. Subprocess coverage needs `COVERAGE_PROCESS_START` plus a `.pth` hook; add it with step 2's MCP round-trip tests.

| Module | Cover | Main gap |
|---|---|---|
| `skills.py` | 69% | install/configure paths, lines 76-106, 135-153, 300-333 |
| `worktree.py` | 79% | junction and removal branches, 137-197 |
| `fsutil.py` | 80% | 21-27 |
| `hooks.py` | 81% | `run_hook` and stale-hook checks, 113-165 |
| `cli.py` | 85% | 155-247 and 524-546 (spec and learnings subcommands) |
| `mcp_server.py` | 85% | 885-921, 984-1005 (the untested tools) |
| `trust.py` | 85% | 110-142 |
| `runner.py` | 86% | 179-254 (worker failure and kill paths) |
| `learnings.py`, `frontmatter.py` | 88% | scattered |
| `core.py` | 92% | 108 lines, spread out; 2375-2389 is the largest block |

Everything else is at or above 90%. Suggested first floor: `--fail-under=88`, raised after step 3.

**Speed:** the 30 slowest tests run 2.7s to 10.1s (about 140s together). That is under a third of the 9 minutes, so the cost is spread across all 532 tests at roughly 1s each: per-test git repo setup, not a few heavy tests. Step 6 should start with the shared template repo, not with trimming individual tests. Slowest: `test_merge_queue_refuses_what_only_breaks_main_in_combination` (10.1s), `test_full_ticket_lifecycle` (7.8s), `test_an_attended_run_stops_at_the_merge_gate_until_a_human_confirms` (7.1s).

### 2. Contract tests: nothing ships untested (T1)
These are structural checks. They fail the moment someone adds a command or tool without a test, so the gap cannot come back quietly.
- `test_every_cli_command_is_exercised`: walk the argparse subparsers from `cli.build_parser()` (or whatever builds them) and assert each one is invoked by at least one test. Do this with a pytest plugin hook that records which subcommands `cli.main` ran during the session, then checks the set in `pytest_sessionfinish`.
- `test_every_mcp_tool_round_trips`: list the tools from the server's own registry. For each one, send a real JSON-RPC `tools/call` over stdio to `python -m kahnban.mcp_server` on a fixture board and assert the response is well-formed: `ok` on the honest path, a tool error on a missing ticket. Write tests for the 13 tools step 1 confirms are untested.
- `test_adapter_skills_match_templates`: `filecmp.dircmp` of `adapters/skills` against `src/kahnban/templates/skills`. If one tree is generated from the other, say which in the failure message.
- Coverage floor: `coverage report --fail-under=<measured − 2>`, raised as gaps close. Set no number until step 1 has measured one.
- **Done when:** removing any one command's test, or registering a new MCP tool without a test, turns the suite red.

### 3. Fill the thin spots found in step 1
Start with the areas listed above (`lease` takeover after expiry, `unblock`/`confirm` on an attended run, `reject` then re-verify at the same tip, `session update` across harnesses, `spec draft/approve/check`, `learnings promote`) and anything else under the coverage floor. Each new test names the behaviour it proves, in the same style as `test_factory_gates.py`.
- **Done when:** every module in `src/kahnban/` is above the floor, or is listed here with a reason it is not (for example, `runner._kill_tree` Windows branch is covered only on the Windows CI leg).

### 4. Installed-wheel smoke (T2)
A new `tests/test_installed.py`, marked `@pytest.mark.installed` and skipped unless `KAHNBAN_INSTALLED=1`:
1. `python -m build --wheel` (add `build` to `dev`) into a temp dir; create a venv with `venv`; `pip install` the wheel, **not** `-e`.
2. In a fresh `git init` repo, with the venv's `kahnban` executable and never `python -m` from `src/`, run: `init --prefix ST --agentic`, `skills install`, `new`, `ready`, `claim --worktree`, commit a passing change in the worktree, `verify`, `approve --reviewer other`, `merge`, `done`, `cleanup`, `lint`, `status`, `sync`, `next --json`.
3. Assert each exit code, the final column of the ticket, a clean `lint`, and that every file `init --agentic` and `skills install` promise exists. This is the check that catches a template left out of `package-data`.
- CI: a separate job, one Python per OS, sets `KAHNBAN_INSTALLED=1`.
- **Done when:** deleting a glob from `[tool.setuptools.package-data]` fails this job and nothing else.

### 5. Adversarial gate matrix (T3)
One table-driven test, `tests/test_gate_matrix.py`. Each row is a gate, an attack and the expected refusal. Rows already covered elsewhere point at that test instead of being duplicated, so the matrix doubles as an index. Minimum rows:

| Gate | Attack |
|---|---|
| `ready` | no acceptance boxes; a box naming a test that does not exist; empty blast radius; run as `KAHNBAN_ROLE=coder` |
| `claim` | blast radius overlaps another in-progress ticket; ticket not in `2-ready` |
| `verify` | test command that exits 0 without running anything (`true`, `pytest --co`); tests edited after the contract froze; diff touches files outside the blast radius |
| `approve` | reviewer equals owner; approving a tip other than the verified one |
| `merge` | main moved and the merged result fails; `confirmed: merge:<tip>` reused after reject |
| `done` | without a merge |
| `guard` | every bypass in remediation-plan-2 C1/C2/X1, re-run as regression rows |
| `move` | no `--reason` |

- **Done when:** every row is either a passing refusal test or a link to one, and a no-op version of each gate (patch the check to `return`) turns at least one row red. Check that by hand once with a throwaway patch; never with `git checkout` on a dirty tree.

### 6. Get T0 back under 5 minutes
Act on the step-1 durations. Ladder, cheapest first:
1. A session-scoped template repo in `conftest.py`, copied with `shutil.copytree` per test instead of `git init` plus commits each time.
2. Set `GIT_CONFIG_NOSYSTEM=1` and skip hooks in fixtures.
3. Only if both fall short: `pytest-xdist -n auto` in `dev`. The tests use `tmp_path` only, which step 1 should confirm before this is turned on.
- **Done when:** local wall time is under 5 minutes and the README number is true again.

### 7. Live harness smoke (T4, opt-in)
`tests/live/test_live_factory.py`, skipped unless `KAHNBAN_LIVE=1`:
1. Preflight in the same process: `claude auth status` and one trivial `claude -p "reply OK"`. Skip with a clear reason if either fails, rather than failing every worker the way the earlier live run did.
2. A toy repo with one spec ("add `slugify()` with three cases"), `kahnban run` with the default worker template and a cheap model, a worker timeout, and `max_attempts=2`.
3. Assert the ticket reached `5-done` or was escalated with a `blocked_on` reason. Record first-pass yield from `status.json` in the test output.
- Never in CI: it costs money and depends on a login.
- **Done when:** one command reproduces the manual live runs in IMPLEMENTATION_STATUS.md.

### 8. Dogfood (T5)
- `kahnban init --prefix KB --agentic` in this repository. Ingest NEXT_STEPS.md and the open items of this plan as tickets.
- From then on, engine work lands through `ready → claim → verify → approve → merge → done`, with `validation_command` set to the T0+T1 suite. `kahnban lint` joins CI.
- Friction found while doing this goes into `kahnban learnings capture`. That queue is the real report on whether kahnban works.
- **Done when:** this plan's own remaining steps are tickets on the board, and the next engine change merged through `kahnban merge`.

## CI after this plan

```yaml
jobs:
  test:       # existing matrix, now: coverage run -m pytest && coverage report --fail-under=N
  installed:  # ubuntu + windows, one Python: KAHNBAN_INSTALLED=1 pytest -m installed
  board:      # kahnban lint on this repo's own board (after step 8)
```

## Out of scope
- Mutation testing tools (mutmut and similar): step 5's one-time no-op check gets most of the value. Add a tool only if a gate regression gets through the matrix.
- Testing harness-specific behaviour inside Cursor, Gemini or VS Code. The golden files in `tests/golden/agents/` cover what kahnban writes for them; what those tools do with the files is theirs.
- Parallel `kahnban run` workers: not built yet (NEXT_STEPS.md, "Harder limits").
