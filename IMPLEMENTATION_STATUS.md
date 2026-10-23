# Kahnban Implementation Status

**Date:** 2026-10-23
**Engine:** `1.4.0` (`src/kahnban/__init__.py` is the only version string)
**CI:** `.github/workflows/ci.yml`, Windows and Linux × Python 3.10–3.13

The README is the user-facing reference for every gate; this file records what is
built, what has been proven, and the limits that are known.

---

## What a ticket goes through

| Stage | Command | Enforced by the engine |
| :--- | :--- | :--- |
| Intent | `kahnban spec new` / `spec approve` | numbered requirements, frozen by a human approval (`requirements_hash`) |
| Decomposition | `kahnban ingest <spec> --ready` | tickets get `spec:`/`covers:`; `spec coverage` and BL18 check traceability |
| Ready | `kahnban ready` | criteria, tests per criterion (`require_proof`), ≤ `max_blast_radius_files` named files incl. a test, approved spec (`require_spec`), `allowed_commands`; freezes `contract_hash` |
| Claim | `kahnban claim` / `lease` | blast-radius overlap, WIP, lease with expiry and logged takeover |
| Verify | `kahnban verify` | contract unchanged, clean committed tip, scope incl. tests/CI, every validation line, each criterion's test, red check in a scratch worktree |
| Review | `kahnban approve` / `reject` | reviewer ≠ owner, approval bound to the verified commit; reject routes back with reasons |
| Land | `kahnban merge` / `done` | merge onto current main in a scratch worktree, tests on the result, fast-forward only if green |
| Run it | `kahnban run` | the loop runs every gate itself; workers only refine, implement, review, and (once per run, when a learning recurs) curate |
| Learn | `kahnban learnings` | recurring or critical learnings are curated before new claims; promotion needs an artifact that exists |
| Observe | `status.json`, `kahnban lint` | per-ticket verify attempts, rejections, escalations, cycle time and first-pass yield; BL19 flags claims idle past `stale_after_days` |

## Proven

- 343 tests on the latest local run (3.13 and 3.11), including one regression test per
  audit probe (A–K) in `tests/test_factory_gates.py`, `tests/test_factory_run.py` and
  `tests/test_spec_gates.py`.
- Live smoke test (2026-10-22): headless `claude -p --model haiku` workers took a ticket
  from `2-ready` to `5-done` unattended; the guard hook blocked a reviewer's file write
  inside a real Claude Code session.
- The first CI run found a real bug local runs had missed (stale bytecode fooling the red
  check); fixed in `52c8a85`.

## Known limits

- The contract, approval and integration records live in the ticket file, which an
  agent can edit; the guard blocks edits outside a worker's remit, but it matches
  commands by text and is a tripwire, not a sandbox. The CLI and MCP server refuse
  commands outside a worker's role on their own (`KAHNBAN_ROLE`), so that part does
  not depend on the harness having hooks; a worker that unsets the variable is not
  caught by it.
- Reviewer identity is the name passed to `--reviewer`.
- Leases are local files: they arbitrate workers on one machine.
- `kahnban run` works one ticket at a time, and its retry counts reset per run.
- The red check proves the tests depend on the change, not that they fail for the right
  reason; a test-only ticket cannot pass strict proof.
- Live agents have been run on one trivial ticket only: not yet the spec-analyst path,
  a reviewer rejection, or a refused merge.

## History

- Phase 1 (engine) and the entry-point layer: 2026-08-18/19, `v1.0.0`–`v1.1.2`.
- Phase 2/3 (`heirs_ancients` adoption and backlog migration): done 2026-08-19.
- Audit and P0–P2 hardening: 2026-10-22/23, see `git log` from `aa34d6d`.

See [plan.md](plan.md) §0 for the original decision log (D1–D13).
