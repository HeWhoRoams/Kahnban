---
id: KB-004
title: "Break down status.json metrics per role: which worker caused the rejections"
status: verifying
owner: claude-coder
branch: ticket/KB-004
worktree: .worktrees/KB-004
created: 2026-10-25
updated: 2026-10-26
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 74031f925bb25faf
confirmed: ""
verified_sha: da33841596827a5a33f246655f5c1bf57caa3f42
reviewer: Tim Niles
approved_sha: da33841596827a5a33f246655f5c1bf57caa3f42
approval_sig: 25b48a0c6b3863d52e726178e6b4ca00b52163bdf6a8ec7cae789b74bdfb6d24
integrated_sha: dccfdc7f85b7ae48766820f821f48096161d432b
---

## Problem
`status.json` metrics count verify attempts and rejections per ticket and give a board-level first-pass yield, but not who caused them.
With several workers, or after changing one worker's prompt, nobody can tell which owner's work fails verify or gets rejected, or which
reviewer rejects. The ticket Log already has what is needed: `claimed by <owner>` (and `taken over by <owner>`), `verify exit=N`,
and `rejected by <reviewer>:`.

## Acceptance criteria
- [x] `log_metrics` adds `by_owner` ({owner: {failed_verifies, rejections}}, a failed verify or rejection counting against the owner of the most recent claim or take-over) and `rejected_by` ({reviewer: count}), and still returns the existing four keys (test: `python -m pytest tests/test_factory_run.py -q -k log_metrics`)
- [x] a failed verify or rejection before any claim is counted under `unknown` and never raises (test: `python -m pytest tests/test_factory_run.py -q -k log_metrics_unknown_owner`)
- [x] `status.json` metrics gain board-level `by_owner` and `by_reviewer`, the sums over every ticket's counts (test: `python -m pytest tests/test_factory_run.py -q -k board_metrics_by_role`)

## Blast radius
- `src/kahnban/core.py`
- `src/kahnban/status.py`
- `tests/test_factory_run.py`

## Implementation notes
- In `core.log_metrics`, walk the entries in order keeping `owner` from `claimed by X ->` and `taken over by X from`; `rejected by R:` takes R up to the first colon.
- Update the exact-equality assertion in `test_log_metrics_count_attempts_rejections_and_cycle_time` for the new keys.
- `status._metrics` sums per-ticket `by_owner` and `rejected_by` into `by_owner` and `by_reviewer`.

## Validation
```
python -m pytest tests/test_factory_run.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 20:04 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 20:04 - ready gate passed -> 2-ready | contract 74031f925bb25faf
- 2026-10-26 20:04 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 20:05 - verify exit=0 in 251.9s (cwd=KB-004) -> 4-verifying
    verifying ticket/KB-004 at da3384159682; Running Tier 1 (Feature Tests): python -m pytest tests/test_factory_run.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_factory_run.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs cbd226b94404]
    === TIER 1: FEATURE TESTS ===
    ....................                                                     [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_factory_run.py -q -k log_metrics
    ...                                                                      [100%]

    [PASS] $ python -m pytest tests/test_factory_run.py -q -k log_metrics_unknown_owner
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_factory_run.py -q -k board_metrics_by_role
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    713 tests, 8 workers, 166s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    ..............FFFF..                                                     [100%]
    ================================== FAILURES ===================================
    __________ test_log_metrics_count_attempts_rejections_and_cycle_time __________

        def test_log_metrics_count_attempts_rejections_and_cycle_time() -> None:
            log = "\n".join([
                "- 2026-10-01 09:00 - created -> 0-backlog",
                "- 2026-10-01 10:00 - verify exit=1 in 2.0s (cwd=TST-001) (no transition)",
                "    $ pytest",
                "- 2026-10-01 11:00 - verify exit=0 in 2.0s (cwd=TST-001) -> 4-verifying",
                "- 2026-10-01 12:00 - rejected by qa:",
                "    cover the overflow case",
                "- 2026-10-02 11:00 - done gate passed -> 5-done | merge-commit: abc",
            ])

            metrics = core.log_metrics(log)

    >       assert metrics == {
                "by_owner": {"unknown": {"failed_verifies": 1, "rejections": 1}},
                "rejected_by": {"qa": 1},
                "verify_attempts": 2,
                "rejections": 1,
                "escalations": 0,
                "cycle_hours": 26.0,
            }
    E       AssertionError: assert {'cycle_hours..._attempts': 2} == {'by_owner': ...'qa': 1}, ...}
    E         
    E         Omitting 4 identical items, use -vv to show
    E         Right contains 2 more items:
    E         {'by_owner': {'unknown': {'failed_verifies': 1, 'rejections': 1}},
    E          'rejected_by': {'qa': 1}}
    E         Use -v to get more diff

    tests\test_factory_run.py:352: AssertionError
    ____________ test_log_metrics_blame_the_owner_of_the_latest_claim _____________

        def test_log_metrics_blame_the_owner_of_the_latest_claim() -> None:
            log = "\n".join([
                "- 2026-10-01 09:00 - claimed by alice -> 3-in-progress",
                "- 2026-10-01 10:00 - verify exit=1 in 2.0s (cwd=T) (no transition)",
                "- 2026-10-01 11:00 - rejected by qa:",
                "    fix it",
                "- 2026-10-01 12:00 - taken over by bob from alice (no live lease)",
                "- 2026-10-01 13:00 - rejected by lead:",
                "    again",
            ])

            metrics = core.log_metrics(log)

    >       assert metrics["by_owner"] == {
                   ^^^^^^^^^^^^^^^^^^^
                "alice": {"failed_verifies": 1, "rejections": 1},
                "bob": {"failed_verifies": 0, "rejections": 1},
            }
    E       KeyError: 'by_owner'

    tests\test_factory_run.py:375: KeyError
    ___________ test_log_metrics_unknown_owner_when_nothing_was_claimed ___________

        def test_log_metrics_unknown_owner_when_nothing_was_claimed() -> None:
    >       assert core.log_metrics("- 2026-10-01 09:00 - verify exit=2 in 1s (cwd=T) (no transition)")["by_owner"] == {
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                "unknown": {"failed_verifies": 1, "rejections": 0}
            }
    E       KeyError: 'by_owner'

    tests\test_factory_run.py:383: KeyError
    _________________ test_board_metrics_by_role_sum_every_ticket _________________

        def test_board_metrics_by_role_sum_every_ticket() -> None:
            from kahnban import status

            def record(ident: str, log: str) -> dict:
                return {"id": ident, "metrics": core.log_metrics(log)}

            rejected = "- 2026-10-01 09:00 - claimed by alice -> 3-in-progress\n- 2026-10-01 10:00 - rejected by qa:\n    no"
            metrics = status._metrics([record("A-1", rejected), record("A-2", rejected)])

    >       assert metrics["by_owner"] == {"alice": {"failed_verifies": 0, "rejections": 2}}
                   ^^^^^^^^^^^^^^^^^^^
    E       KeyError: 'by_owner'

    tests\test_factory_run.py:397: KeyError
    =========================== short test summary info ===========================
    FAILED tests/test_factory_run.py::test_log_metrics_count_attempts_rejections_and_cycle_time
    FAILED tests/test_factory_run.py::test_log_metrics_blame_the_owner_of_the_latest_claim
    FAILED tests/test_factory_run.py::test_log_metrics_unknown_owner_when_nothing_was_claimed
    FAILED tests/test_factory_run.py::test_board_metrics_by_role_sum_every_ticket

    full output: plans/tickets/.artifacts/KB-004-20261026-200546.log
- 2026-10-26 22:19 - approved by Tim Niles at da3384159682
- 2026-10-26 22:19 - integrated into main | merge-commit: dccfdc7f85b7ae48766820f821f48096161d432b
    $ merge ticket/KB-004 onto main f1ca9907d54e
    === INTEGRATION: FEATURE TESTS ===
    ....................                                                     [100%]


    === INTEGRATION: REGRESSION TESTS ===
    713 tests, 8 workers, 180s, all passed

    full output: plans/tickets/.artifacts/KB-004-20261026-221942.log