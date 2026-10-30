---
id: KB-011
title: "Runner robustness for --jobs: log worker stops, drop leaked leases, no verify past max_steps"
status: verifying
owner: coder-agent
branch: ticket/KB-011
worktree: .worktrees/KB-011
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: [docs/remediation-plan-3.md]
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 620f208e460cac0b
contract_sig: eea9ba7ecd5de8fe51b1f3f4898df497cbc0dd9a69d36bf6b714b99711242326
confirmed: ""
verified_sha: 60a3483b2f68b665507801fe6d4753a96ec29b12
reviewer: qa-reviewer
approved_sha: 60a3483b2f68b665507801fe6d4753a96ec29b12
approval_sig: ""
reviewer_sig: ""
integrated_sha: ""
---

## Problem
## R1: Runner robustness for `--jobs` (findings 1, 2, 3, 4, 9)

Files: `src/kahnban/runner.py`, `tests/test_runner_parallel.py`.

| Finding | Fix | Test (fails before) |
|---|---|---|
| Worker `RunStop` leaves no Step | In `harvest`, call `_note` with the worker's message before storing `self.stop`. | A coder that exits 1 under `--jobs 2`: the `RunStop` still raises, and the run log has a line for that ticket. |
| Lease leaks if start fails after claim | In `start`, wrap claim/submit so any failure after the claim calls `core.drop_lease`. | Make `pool.submit` raise: the ticket has no live lease afterwards. |
| Other exceptions abort harvest | Catch `Exception` per future in `harvest`, record it as a `refused:` outcome (re-raise only `RunStop`), so every finished future is processed and its lease dropped. | Two finished workers where verify raises `OSError` for the first: both leases are dropped. |
| `drain` verifies past `max_steps` | On the max_steps exit, wait for workers but do not verify them; leave the tickets in-progress with the lease dropped, and say so in `result.stopped` ("N worker(s) finished unverified; run again"). | `max_steps=3, jobs=2`: no verify runs after the budget and the message names the tickets. |
| Duplicated exception tuple and lease-drop | Name `_REFUSALS = (core.KahnbanError, gitops.GitError, worktree.WorktreeError)`; give `_implement` and `harvest` one shared `_finish(config, ticket, code)` that drops the lease and calls `_verified`. | Existing tests still pass (no behaviour change). |

Also in this ticket: reject `--jobs 0` and below with a usage error instead of clamping (cli.py is already
touched by KB-008; this is a one-line `type=` check, so a third file only if the check goes there).


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria
- [x] A worker's `RunStop` still logs a `Step` for its ticket before the run stops (a coder that exits 1 under `--jobs 2`) (test: `python -m pytest tests/test_runner_parallel.py -q -k run_stop_logs_a_step`)
- [x] If `pool.submit` raises after a ticket is claimed/leased, the lease is dropped before `start` returns (test: `python -m pytest tests/test_runner_parallel.py -q -k submit_failure_drops_the_lease`)
- [x] Harvesting two finished workers where `core.verify` raises for the first still drops both leases and records the first as a `refused:` outcome (only `RunStop` is re-raised) (test: `python -m pytest tests/test_runner_parallel.py -q -k harvest_survives_one_worker_error`)
- [x] With `max_steps=3, jobs=2`, a worker that finishes after the budget is not verified: its lease is dropped, its ticket stays in-progress, and `result.stopped` names it (test: `python -m pytest tests/test_runner_parallel.py -q -k max_steps_leaves_workers_unverified`)
- [x] `_implement` and `harvest` share one `_finish(config, ticket, code)` (drop lease, then `_verified`) built on one `_REFUSALS` tuple, with no behaviour change (test: `python -m pytest tests/test_runner_parallel.py -q`)
- [x] `kahnban run --jobs 0` (and any value below 1) fails with a usage error instead of silently clamping to 1 job (test: `python -m pytest tests/test_runner_parallel.py -q -k jobs_rejects_non_positive`)

## Blast radius
- `src/kahnban/runner.py`
- `src/kahnban/cli.py`
- `tests/test_runner_parallel.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_runner_parallel.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:31 - ready gate passed -> 2-ready | contract 620f208e460cac0b
- 2026-10-29 19:32 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 19:52 - verify exit=0 in 507.6s (cwd=KB-011) -> 4-verifying
    verifying ticket/KB-011 at 60a3483b2f68; Running Tier 1 (Feature Tests): python -m pytest tests/test_runner_parallel.py -q
python tests/run_parallel.py -j 8; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_runner_parallel.py -q
python tests/run_parallel.py -j 8] && [6/6 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs c355d454158f]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_runner_parallel.py -q
    .......                                                                  [100%]

    $ python tests/run_parallel.py -j 8
    730 tests, 8 workers, 199s, all passed


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k run_stop_logs_a_step
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k submit_failure_drops_the_lease
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k harvest_survives_one_worker_error
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k max_steps_leaves_workers_unverified
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q
    .......                                                                  [100%]

    [PASS] $ python -m pytest tests/test_runner_parallel.py -q -k jobs_rejects_non_positive
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    730 tests, 8 workers, 179s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_runner_parallel.py -q
    ..FFFFF                                                                  [100%]
    ================================== FAILURES ===================================
    __________________________ test_run_stop_logs_a_step __________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_run_stop_logs_a_step0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_run_stop_logs_a_step0')

        def test_run_stop_logs_a_step(repo: Path, tmp_path: Path) -> None:
            # A coder that exits 1 under --jobs 2: harvest must log a Step for that ticket
            # before the run stops, not just raise.
            config = factory_board(repo)
            flight, result = _flight(config, tmp_path)
            rec = dispatcher.DispatchRecommendation(
                action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
            )
            future: Future[int] = Future()
            future.set_exception(runner.RunStop("coder worker command exited 1"))
            flight.active[future] = rec

            flight.harvest(1)

            assert flight.stop is not None
            steps = [step for step in result.steps if step.ticket_id == "TST-001"]
    >       assert len(steps) == 1, result.steps
    E       AssertionError: []
    E       assert 0 == 1
    E        +  where 0 = len([])

    tests\test_runner_parallel.py:131: AssertionError
    _____________________ test_submit_failure_drops_the_lease _____________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_submit_failure_drops_the_0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_submit_failure_drops_the_0')

        def test_submit_failure_drops_the_lease(repo: Path, tmp_path: Path) -> None:
            config = factory_board(repo)
            n = "001"
            check = f"{PY} tests/check_{n}.py"
            write_ticket(
                config.board_path,
                "1-refining",
                "TST-001",
                "fix",
                acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
                blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"),
                validation=check,
            )
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "refine")
            core.ready(config, "TST-001")

            flight, result = _flight(config, tmp_path)
            assert flight.pool is not None
            flight.pool.submit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pool is broken"))  # type: ignore[method-assign]
            rec = dispatcher.DispatchRecommendation(
                action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
            )

            with pytest.raises(RuntimeError):
                flight.start(1, rec)

    >       assert core.live_lease(config, "TST-001") == ""
    E       AssertionError: assert 'coder-agent' == ''
    E         
    E         + coder-agent

    tests\test_runner_parallel.py:162: AssertionError
    ___________________ test_harvest_survives_one_worker_error ____________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_harvest_survives_one_work0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_harvest_survives_one_work0')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023C181108D0>

        def test_harvest_survives_one_worker_error(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
            config = factory_board(repo)
            tree1 = _claimed_ticket(config, "TST-001")
            _commit_fix(tree1, "TST-001")
            tree2 = _claimed_ticket(config, "TST-002")
            _commit_fix(tree2, "TST-002")

            real_verify = core.verify

            def flaky_verify(cfg: core.Config, ticket_id: str, **kwargs: object) -> object:
                if ticket_id == "TST-001":
                    raise OSError("disk exploded")
                return real_verify(cfg, ticket_id, **kwargs)  # type: ignore[arg-type]

            monkeypatch.setattr(core, "verify", flaky_verify)

            flight, result = _flight(config, tmp_path)
            rec1 = dispatcher.DispatchRecommendation(
                action="claim_and_implement", assigned_role="coder", ticket_id="TST-001", prompt="go"
            )
            rec2 = dispatcher.DispatchRecommendation(
                action="claim_and_implement", assigned_role="coder", ticket_id="TST-002", prompt="go"
            )
            f1: Future[int] = Future()
            f2: Future[int] = Future()
            f1.set_result(0)
            f2.set_result(0)
            flight.active[f1] = rec1
            flight.active[f2] = rec2

    >       flight.harvest(1)

    tests\test_runner_parallel.py:195: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\runner.py:238: in harvest
        outcome = _verified(self.config, ticket, code)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    src\kahnban\runner.py:356: in _verified
        result = core.verify(config, ticket)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    cfg = Config(project_root=WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_harvest_survives_one_..., max_stop_nudges=2, strict_hooks=False, autonomy='unattended', human_gates=('merge',), require_signed_approvals=False)
    ticket_id = 'TST-001', kwargs = {}

        def flaky_verify(cfg: core.Config, ticket_id: str, **kwargs: object) -> object:
            if ticket_id == "TST-001":
    >           raise OSError("disk exploded")
    E           OSError: disk exploded

    tests\test_runner_parallel.py:176: OSError
    __________________ test_max_steps_leaves_workers_unverified ___________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_max_steps_leaves_workers_0/scratch')
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-664/test_max_steps_leaves_workers_0')

        def test_max_steps_leaves_workers_unverified(repo: Path, tmp_path: Path) -> None:
            worker = tmp_path / "worker.py"
            worker.write_text(DELAYED_WORKER.format(check_app=CHECK_APP), encoding="utf-8")
            config = factory_board(repo, workers={"default": f"{PY} {worker}"})
            for ticket in ("TST-001", "TST-002"):
                n = ticket[-3:]
                check = f"{PY} tests/check_{n}.py"
                write_ticket(
                    config.board_path,
                    "1-refining",
                    ticket,
                    "fix",
                    acceptance=(f"- [ ] f() returns 2 (test: `{check}`)",),
                    blast_radius=(f"src/app_{n}.py", f"tests/check_{n}.py"),
                    validation=check,
                )
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "refine")
            for ticket in ("TST-001", "TST-002"):
                core.ready(config, ticket)

            # The 2-step budget is only enough to start both coders; neither can finish in
            # time (each sleeps 0.5s), so the run must stop without verifying either.
            result = runner.run(config, max_steps=2, jobs=2, echo=lambda line: None)

    >       assert "unverified" in result.stopped
    E       AssertionError: assert 'unverified' in 'stopped after 2 steps'
    E        +  where 'stopped after 2 steps' = RunResult(steps=[Step(number=2, action='claim_and_implement', ticket_id='TST-001', outcome='worker exit 0; verified'),...est_max_steps_leaves_workers_0/scratch/plans/tickets/.artifacts/run-20261029-200035.log'), parked=[], guard_refusals=0).stopped

    tests\test_runner_parallel.py:249: AssertionError
    _______________________ test_jobs_rejects_non_positive ________________________

        def test_jobs_rejects_non_positive() -> None:
    >       with pytest.raises(SystemExit) as exit_info:
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
    E       Failed: DID NOT RAISE <class 'SystemExit'>

    tests\test_runner_parallel.py:257: Failed
    ---------------------------- Captured stdout call -----------------------------
    [1] resume_worktree KB-011: refused: board is locked by another kahnban process (pid=94572 host=brainiac at=2026-10-29T19:52:37 until=1793325157); retry once it finishes
    [2] resume_worktree KB-011: refused: board is locked by another kahnban process (pid=94572 host=brainiac at=2026-10-29T19:52:37 until=1793325157); retry once it finishes
    [3] resume_worktree KB-011: refused: board is locked by another kahnban process (pid=94572 host=brainiac at=2026-10-29T19:52:37 until=1793325157); retry once it finishes
    ---------------------------- Captured stderr call -----------------------------
    [FAIL] board is locked by another kahnban process (pid=94572 host=brainiac at=2026-10-29T19:52:37 until=1793325157); retry once it finishes
    =========================== short test summary info ===========================
    FAILED tests/test_runner_parallel.py::test_run_stop_logs_a_step - AssertionEr...
    FAILED tests/test_runner_parallel.py::test_submit_failure_drops_the_lease - A...
    FAILED tests/test_runner_parallel.py::test_harvest_survives_one_worker_error
    FAILED tests/test_runner_parallel.py::test_max_steps_leaves_workers_unverified
    FAILED tests/test_runner_parallel.py::test_jobs_rejects_non_positive - Failed...

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-011-20261029-195237.log
- 2026-10-29 20:10 - approved by qa-reviewer at 60a3483b2f68