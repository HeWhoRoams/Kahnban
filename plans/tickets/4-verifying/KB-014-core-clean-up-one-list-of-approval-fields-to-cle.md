---
id: KB-014
title: "Core clean-up: one list of approval fields to clear, rename _signature_problem"
status: verifying
owner: coder-agent
branch: ticket/KB-014
worktree: .worktrees/KB-014
created: 2026-10-29
updated: 2026-10-30
legacy_id: ""
design_docs: [docs/remediation-plan-3.md]
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 1e0d5fe012da54e4
contract_sig: b229f9ee9849180e08393686e6e639b10c309589fbff3ac86c82687b441c5c74
confirmed: ""
verified_sha: 9bb3beac645019bdfe28da57265c066d094b05ed
reviewer: qa-reviewer
approved_sha: 9bb3beac645019bdfe28da57265c066d094b05ed
approval_sig: a5ed5fda2f02b98590f283c7936ede0268a3872b0aaf6c36bbf18f1a228b79e1
reviewer_sig: ""
integrated_sha: ""
---

## Problem
## R4: Core clean-ups (findings 8, 10)

Files: `src/kahnban/core.py`, `tests/test_reviewer_keys.py` (name use only).

- One module-level `_APPROVAL_FIELDS` mapping of the fields to blank, used by `verify` and `reject`.
- Rename `_signature_problem` to `_approval_problem` and update its docstring to say it checks both the
  engine HMAC and the reviewer seal.
- No behaviour change, so no new test; the full suite is the check.


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria
- [x] `verify` and `reject` clear the same approval fields (`reviewer`, `approved_sha`, `approval_sig`, `reviewer_sig`, `integrated_sha`, `confirmed`) via one module-level `_APPROVAL_FIELDS` mapping in `core.py`, not two duplicated dict literals (test: `python -m pytest tests/test_reviewer_keys.py -q -k approval_fields_mapping_is_shared`)
- [x] `core._signature_problem` is renamed to `core._approval_problem` (no remaining reference to the old name anywhere in `src/`) and its docstring says it checks both the engine HMAC and the reviewer seal (test: `python -m pytest tests/test_reviewer_keys.py -q -k approval_problem_checks_hmac_and_seal`)
- [x] no behaviour change: the existing reviewer-key suite and the full regression suite still pass (test: `python tests/run_parallel.py -j 8`)

## Blast radius
- `src/kahnban/core.py`
- `tests/test_reviewer_keys.py`

## Implementation notes
- The two fields dicts to dedupe are in `verify` (sets `verified_sha` to the new tip, the rest blank) and `reject` (blanks `verified_sha` too). Keep `verified_sha` out of `_APPROVAL_FIELDS` since the two callers disagree on its value; each call site still sets it itself and merges in `_APPROVAL_FIELDS` for the rest.
- `_signature_problem` is called from two sites (`_release_problems`, used by `done`, and `merge`) — rename both call sites along with the definition.

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:41 - ready gate passed -> 2-ready | contract 1e0d5fe012da54e4
- 2026-10-29 21:13 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 21:22 - verify exit=1 in 38.9s (cwd=KB-014) (no transition)
    verifying ticket/KB-014 at ab033b90de3a; Running Tier 1 (Feature Tests): python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
    $ python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
    $ python -m pytest tests/test_reviewer_keys.py -q
    .........F.                                                              [100%]
    ================================== FAILURES ===================================
    _____ test_approval_fields_are_cleared_the_same_way_by_verify_and_reject ______

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-856/test_approval_fields_are_clear0/scratch')

        def test_approval_fields_are_cleared_the_same_way_by_verify_and_reject(repo: Path) -> None:
            config = factory_board(repo)
            verified(config)
            cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
            core.approve(config, "TST-001", "alice")
            assert core.merge(config, "TST-001").passed
            fields = fields_of(config)
    >       assert all(fields.get(name) for name in APPROVAL_FIELD_NAMES - {"confirmed"})
    E       assert False
    E        +  where False = all(<generator object test_approval_fields_are_cleared_the_same_way_by_verify_and_reject.<locals>.<genexpr> at 0x000001F73ECA82E0>)

    tests\test_reviewer_keys.py:164: AssertionError
    ---------------------------- Captured stdout call -----------------------------
    [OK] registered reviewer 'alice'; 'kahnban approve' now needs a registered reviewer
    =========================== short test summary info ===========================
    FAILED tests/test_reviewer_keys.py::test_approval_fields_are_cleared_the_same_way_by_verify_and_reject

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-014-20261029-212229.log
- 2026-10-29 22:16 - escalated to a human: 'resume_worktree' made no progress after 3 attempts; last: coder worker command exited 1; fix the worker setup and re-run (full output in C:\github\kahnban\plans\tickets\.artifacts\run-20261029-212733.log): You've hit your session limit · resets 9:40pm (America/New_York)
- 2026-10-29 23:59 - unblocked: escalated only by the 21:27 usage-limit worker failures, which have cleared; retry the coder
- 2026-10-30 00:07 - verify exit=0 in 631.3s (cwd=KB-014) -> 4-verifying
    verifying ticket/KB-014 at 9bb3beac6450; Running Tier 1 (Feature Tests): python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 742c0c7591ce]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_reviewer_keys.py -q
    ...........                                                              [100%]

    $ python tests/run_parallel.py -j 8
    739 tests, 8 workers, 187s, all passed


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k approval_fields_mapping_is_shared
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k approval_problem_checks_hmac_and_seal
    .                                                                        [100%]

    [PASS] $ python tests/run_parallel.py -j 8
    739 tests, 8 workers, 175s, all passed


    === TIER 2: REGRESSION TESTS ===
    739 tests, 8 workers, 182s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_reviewer_keys.py -q
    ........F.F                                                              [100%]
    ================================== FAILURES ===================================
    ___________________ test_approval_fields_mapping_is_shared ____________________

        def test_approval_fields_mapping_is_shared() -> None:
            # One module-level mapping, not two duplicated dict literals in verify() and reject().
    >       assert core._APPROVAL_FIELDS == {name: "" for name in APPROVAL_FIELD_NAMES}
                   ^^^^^^^^^^^^^^^^^^^^^
    E       AttributeError: module 'kahnban.core' has no attribute '_APPROVAL_FIELDS'

    tests\test_reviewer_keys.py:143: AttributeError
    _________________ test_approval_problem_checks_hmac_and_seal __________________

        def test_approval_problem_checks_hmac_and_seal() -> None:
    >       assert not hasattr(core, "_signature_problem")
    E       AssertionError: assert not True
    E        +  where True = hasattr(core, '_signature_problem')

    tests\test_reviewer_keys.py:172: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_reviewer_keys.py::test_approval_fields_mapping_is_shared - ...
    FAILED tests/test_reviewer_keys.py::test_approval_problem_checks_hmac_and_seal

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-014-20261030-000729.log
- 2026-10-30 00:18 - approved by qa-reviewer at 9bb3beac6450
- 2026-10-30 00:18 - approval by qa-reviewer countersigned by the runner at 9bb3beac6450