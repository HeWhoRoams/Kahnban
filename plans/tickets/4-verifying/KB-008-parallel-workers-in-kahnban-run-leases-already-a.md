---
id: KB-008
title: Parallel workers in kahnban run (leases already allow it)
status: verifying
owner: claude-coder
branch: ticket/KB-008
worktree: .worktrees/KB-008
created: 2026-10-25
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 02f0410cc4b0e1d3
contract_sig: 4c9e69822adfd608b5f87796cbc766339e5ff483aa06e7fc9f20bd5e437cc8d1
confirmed: ""
verified_sha: 1c502470170084c1d4879a101a99bc437bb37232
reviewer: Tim Niles
approved_sha: 1c502470170084c1d4879a101a99bc437bb37232
approval_sig: f748cc9117e844e121f3173fd215cd2bb568debbfd73613cbdf77923142e5fc0
reviewer_sig: ""
integrated_sha: 1a3fd9dbb8f41f0ff545e548fde5b7c38d94ed9c
---

## Problem
`kahnban run` drives one ticket at a time, so a board with several ready tickets waits on each coder in turn. Leases and the
dispatcher's free-blast-radius rule already stop two coders from holding overlapping tickets. Decided with the user (2026-10-29):
parallel implement only. `kahnban run --jobs N` runs up to N coder workers at once, each in its own worktree. Only the worker
subprocess runs off the main thread; claim, verify, review, merge and done stay one at a time, so the merge queue, the board's
commits and signing are unchanged. The default is 1, which behaves exactly as before. Limit: tickets with disjoint declared radii
can still conflict at merge; the merge queue refuses those as it does today.

## Acceptance criteria
- [x] with `--jobs 2`, two ready tickets with disjoint blast radii have their coders running at the same time and both reach 4-verifying (test: `python -m pytest tests/test_runner_parallel.py -q -k two_coders`)
- [x] with `--jobs 1` (the default) the run stays sequential (test: `python -m pytest tests/test_runner_parallel.py -q -k one_job`)

## Blast radius
- `src/kahnban/runner.py`
- `src/kahnban/cli.py`
- `tests/test_runner_parallel.py`

## Implementation notes
- runner.py: `run(..., jobs=1)`; a `_Flight` holds the in-flight workers in a ThreadPoolExecutor. A coding action (`claim_and_implement`, `resume_worktree`, `revise_implementation`) claims or leases on the main thread, then submits only `_code` (the worker). Finished workers are harvested on the main thread: the lease is dropped, then `verify` runs. The loop waits for a worker when the board is idle or the pool is full, and drains the pool before it returns. A `RunStop` from a worker ends the run after the others finish.
- `_implement` is split into `_code` and `_verified`; the sequential path is unchanged.
- cli.py: `--jobs` on `run`.
- The test's coders each wait for the other's marker file, so they can only finish if they overlap.

## Validation
```
python -m pytest tests/test_runner_parallel.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-29 08:47 - ready gate passed -> 2-ready | contract 02f0410cc4b0e1d3
- 2026-10-29 08:47 - claimed by claude-coder -> 3-in-progress
- 2026-10-29 08:47 - verify exit=0 in 224.8s (cwd=KB-008) -> 4-verifying
    verifying ticket/KB-008 at 1c5024701700; Running Tier 1 (Feature Tests): python -m pytest tests/test_runner_parallel.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_runner_parallel.py -q] && [2/2 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs e5fe1f127176]
    === TIER 1: FEATURE TESTS ===
    ..                                                                       [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k two_coders
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k one_job
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    725 tests, 8 workers, 188s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF                                                                       [100%]
    ================================== FAILURES ===================================
    __________ test_two_coders_run_at_once_and_both_tickets_are_verified __________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-562/test_two_coders_run_at_once_an0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-562/test_two_coders_run_at_once_an0')

        def test_two_coders_run_at_once_and_both_tickets_are_verified(repo: Path, tmp_path: Path) -> None:
            config = two_ready_tickets(repo, tmp_path, wait=20)

    >       result = runner.run(config, max_steps=6, jobs=2, echo=lambda line: None)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       TypeError: run() got an unexpected keyword argument 'jobs'

    tests\test_runner_parallel.py:54: TypeError
    ________________________ test_one_job_stays_sequential ________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-562/test_one_job_stays_sequential0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-562/test_one_job_stays_sequential0')

        def test_one_job_stays_sequential(repo: Path, tmp_path: Path) -> None:
            config = two_ready_tickets(repo, tmp_path, wait=1)  # the first coder times out waiting for a peer that never starts

            try:
    >           runner.run(config, max_steps=2, jobs=1, echo=lambda line: None)
    E           TypeError: run() got an unexpected keyword argument 'jobs'

    tests\test_runner_parallel.py:67: TypeError
    =========================== short test summary info ===========================
    FAILED tests/test_runner_parallel.py::test_two_coders_run_at_once_and_both_tickets_are_verified
    FAILED tests/test_runner_parallel.py::test_one_job_stays_sequential - TypeErr...

    full output: plans/tickets/.artifacts/KB-008-20261029-084724.log
- 2026-10-29 09:36 - approved by Tim Niles at 1c5024701700
- 2026-10-29 09:36 - integrated into main | merge-commit: 1a3fd9dbb8f41f0ff545e548fde5b7c38d94ed9c
    $ merge ticket/KB-008 onto main e5e9418feaf5
    === INTEGRATION: FEATURE TESTS ===
    ..                                                                       [100%]


    === INTEGRATION: REGRESSION TESTS ===
    725 tests, 8 workers, 189s, all passed

    full output: plans/tickets/.artifacts/KB-008-20261029-093641.log