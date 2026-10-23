# Next Steps

**Date:** 2026-10-23 — engine `1.4.0`. What is built and proven is in
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md); this is what is left.

## Prove more of it live

The engine paths below are covered by tests with fake workers but have not run with
real agents yet. Use the scratch-repo smoke setup (one ticket, Haiku workers) and add:

1. A backlog ticket with no criteria, so the spec analyst has to refine it.
2. A ticket the reviewer should reject (a hollow `assert True` test), to see the
   reject → revise → re-verify loop with real agents.
3. Two tickets that conflict on main, to see `merge` refuse and send one back.

Preflight first: `claude auth status` and one trivial `claude -p` call, in the same
shell the run will use.

## P3 — learning and operations

- **Metrics per role:** `status.json` now has per-ticket counts and board-level
  first-pass yield; per-role breakdowns (which worker caused rejections) are next.
- **Housekeeping:** rename the pstack `blast-radius` skill (it collides with the
  ticket field); run this repository's own work on a kahnban board.

## Harder limits (need design, not just code)

- Tamper resistance for the frozen records beyond the guard: run workers in a
  container, or keep contract/approval records outside the agents' write access.
- Reviewer identity that is not self-asserted.
- Parallel workers in `kahnban run` (leases already allow it; the loop is sequential).
- Phase 4 from [plan.md](plan.md): the `citadel` portability smoke test.

## Working on the engine

- Every board write goes through `core.transition()`; every new entry point produces
  `core.TicketDraft`s.
- Each gate change gets a "refuses X" test in `tests/test_factory_gates.py` or
  `tests/test_spec_gates.py`, and the honest path must pass on every CI platform.
- `py -3 -m pytest -q` takes about 5 minutes; run one file while iterating.
