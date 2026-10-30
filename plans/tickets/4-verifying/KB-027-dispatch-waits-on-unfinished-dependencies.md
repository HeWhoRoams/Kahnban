---
id: KB-027
title: Dispatch waits on unfinished dependencies
status: verifying
owner: coder-agent
branch: ticket/KB-027
worktree: .worktrees/KB-027
created: 2026-10-29
updated: 2026-10-30
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/dispatch-waits-on-unfinished-dependencie
source_hash: bcc76f9923f4
validation_class: headless-verified
covers: [R13, R14]
spec: SPEC-001
contract_hash: 599e575b6942657e
contract_sig: c43d62703cb93f6bae2f1df3cd6b0831fbf1874888cdb9563dd7753317b55b9b
confirmed: ""
verified_sha: 3b13cf56cb6954eb7aca24483474913f96b7d4e2
reviewer: qa-reviewer
approved_sha: 3b13cf56cb6954eb7aca24483474913f96b7d4e2
approval_sig: 59617a5ccaaa496b07818e315bd95915b74f29461a42150d072b2bc0f23771e0
reviewer_sig: ""
integrated_sha: ""
---

## Problem

## Acceptance criteria
- [x] a backlog ticket listed before its unfinished dependency is never offered; the dependency is (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k dependent_waits`)
- [x] a ticket with a missing dependency or on a cycle (self-dependency included) is never offered (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k missing_and_cycle_wait`)
- [x] when only waiting tickets remain, next reports idle naming each one and its blocker: id, missing id or cycle (test: `python -m pytest tests/test_dispatch_dependencies.py -q -k idle_names_blockers`)

## Blast radius
- `src/kahnban/dispatcher.py`
- `src/kahnban/core.py`
- `tests/test_dispatch_dependencies.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_dispatch_dependencies.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/dispatch-waits-on-unfinished-dependencie
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - re-ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/dispatch-waits-on-unfinished-dependencie (source_hash bcc76f9923f4)
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 599e575b6942657e
- 2026-10-30 00:25 - claimed by coder-agent -> 3-in-progress
- 2026-10-30 00:36 - verify exit=0 in 209.5s (cwd=KB-027) -> 4-verifying
    verifying ticket/KB-027 at 3b13cf56cb69; Running Tier 1 (Feature Tests): python -m pytest tests/test_dispatch_dependencies.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_dispatch_dependencies.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 1989079c6f50]
    === TIER 1: FEATURE TESTS ===
    ...                                                                      [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_dispatch_dependencies.py -q -k dependent_waits
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_dispatch_dependencies.py -q -k missing_and_cycle_wait
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_dispatch_dependencies.py -q -k idle_names_blockers
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    757 tests, 8 workers, 182s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FFF                                                                      [100%]
    ================================== FAILURES ===================================
    ____________________________ test_dependent_waits _____________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1147/test_dependent_waits0/repo')

        def test_dependent_waits(repo: Path) -> None:
            config = core.load_config(repo)
            # DEP-001 is listed before its dependency DEP-002 (alphabetically first),
            # but DEP-002 is not done. DEP-001 must never be offered; DEP-002 (the
            # unfinished dependency, otherwise unblocked) is offered instead.
            _write_ticket(repo, "0-backlog", "DEP-001-depends-on-002.md", _ticket("DEP-001", "Depends on 002", "DEP-002"))
            _write_ticket(repo, "0-backlog", "DEP-002-the-dependency.md", _ticket("DEP-002", "The dependency"))

            rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
            assert rec.action == "spec_and_refine"
    >       assert rec.ticket_id == "DEP-002"
    E       AssertionError: assert 'DEP-001' == 'DEP-002'
    E         
    E         - DEP-002
    E         ?       ^
    E         + DEP-001
    E         ?       ^

    tests\test_dispatch_dependencies.py:76: AssertionError
    _________________________ test_missing_and_cycle_wait _________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1147/test_missing_and_cycle_wait0/repo')

        def test_missing_and_cycle_wait(repo: Path) -> None:
            config = core.load_config(repo)
            # DEP-001 depends on a dependency that does not exist anywhere on the board.
            _write_ticket(repo, "0-backlog", "DEP-001-missing-dep.md", _ticket("DEP-001", "Missing dep", "DEP-999"))
            # DEP-002 depends on itself (a cycle of length one).
            _write_ticket(repo, "0-backlog", "DEP-002-self-cycle.md", _ticket("DEP-002", "Self cycle", "DEP-002"))

            rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
    >       assert rec.action != "spec_and_refine"
    E       AssertionError: assert 'spec_and_refine' != 'spec_and_refine'
    E        +  where 'spec_and_refine' = DispatchRecommendation(action='spec_and_refine', assigned_role='spec_analyst', ticket_id='DEP-001', ticket_title='Miss... started you, it runs that after you stop, so leave it alone; in an interactive session, run it yourself.', baton=None).action

    tests\test_dispatch_dependencies.py:87: AssertionError
    __________________________ test_idle_names_blockers ___________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1147/test_idle_names_blockers0/repo')

        def test_idle_names_blockers(repo: Path) -> None:
            config = core.load_config(repo)
            _write_ticket(repo, "0-backlog", "DEP-001-missing-dep.md", _ticket("DEP-001", "Missing dep", "DEP-999"))
            _write_ticket(repo, "0-backlog", "DEP-002-self-cycle.md", _ticket("DEP-002", "Self cycle", "DEP-002"))

            rec = dispatcher.resolve_next_action(config, preferred_role=roles.SPEC_ANALYST)
    >       assert rec.action == "idle"
    E       AssertionError: assert 'spec_and_refine' == 'idle'
    E         
    E         - idle
    E         + spec_and_refine

    tests\test_dispatch_dependencies.py:97: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_dispatch_dependencies.py::test_dependent_waits - AssertionE...
    FAILED tests/test_dispatch_dependencies.py::test_missing_and_cycle_wait - Ass...
    FAILED tests/test_dispatch_dependencies.py::test_idle_names_blockers - Assert...

    full output: plans/tickets/.artifacts/KB-027-20261030-003654.log
- 2026-10-30 00:41 - approved by qa-reviewer at 3b13cf56cb69
- 2026-10-30 00:42 - approval by qa-reviewer countersigned by the runner at 3b13cf56cb69