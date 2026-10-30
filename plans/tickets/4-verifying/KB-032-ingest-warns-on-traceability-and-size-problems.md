---
id: KB-032
title: Ingest warns on traceability and size problems
status: verifying
owner: coder-agent
branch: ticket/KB-032
worktree: .worktrees/KB-032
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-031]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/ingest-warns-on-traceability-and-size-pr
source_hash: 7026247784be
validation_class: headless-verified
covers: [R19]
spec: SPEC-001
contract_hash: 823581484d9e2649
contract_sig: a859c77d4ac46231a39fde48168cab554180aabd8d50b3daeddc0b90a5ee885b
confirmed: ""
verified_sha: 9a9dc21e1f1a0848703b7b9120f4eddd9cee1179
reviewer: qa-reviewer
approved_sha: 9a9dc21e1f1a0848703b7b9120f4eddd9cee1179
approval_sig: ""
reviewer_sig: ""
integrated_sha: ""
---

## Problem
`kahnban ingest` (`src/kahnban/ingest.py`) builds each `TicketDraft`'s `spec`/`covers`
(KB-031, R18) but never checks them against the spec, and never checks blast
radius size or an orphaned `## Requirements` section. A draft can cite a
`covers` id the spec does not define, a spec requirement can go uncovered by
every draft, an unapproved spec can be cited, a draft's blast radius can be
empty or exceed `config.max_blast_radius_files`, and a non-spec document's
`## Requirements` section can produce no `covers` at all — and ingest stays
silent on every one of these, exiting 0 either way. `src/kahnban/specs.py`
already has the primitives (`find_spec`, `Spec.approved`,
`Spec.requirements`) `ingest_document` needs to turn each case into an entry
on `report.warnings`, which `render_report` already prints and `--json`
already carries (`as_dict`'s `warnings` key) — so exit code 0 is kept as-is
and nothing escalates to an error.

## Acceptance criteria
- [x] warns on a covers id the spec does not define (test: `python -m pytest tests/test_ingest_traceability.py -q -k unknown_covers`)
- [x] warns on a spec requirement no draft covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k uncovered_requirement`)
- [x] warns on an unapproved spec (test: `python -m pytest tests/test_ingest_traceability.py -q -k unapproved_spec`)
- [x] warns on a draft blast radius that is empty or over max_blast_radius_files (test: `python -m pytest tests/test_ingest_traceability.py -q -k radius_size`)
- [x] warns when a non-spec document's ## Requirements section produced no covers, and not when it has none (test: `python -m pytest tests/test_ingest_traceability.py -q -k skipped_requirements`)
- [x] ingest still exits 0 when it only warns (test: `python -m pytest tests/test_ingest_traceability.py -q -k warnings_exit_zero`)

## Blast radius
- `src/kahnban/ingest.py`
- `tests/test_ingest_traceability.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_ingest_traceability.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ingest-warns-on-traceability-and-size-pr
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-29 23:24 - unblocked: dependencies are in 5-done (supervisor)
- 2026-10-29 23:27 - ready gate passed -> 2-ready | contract 823581484d9e2649
- 2026-10-29 23:28 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 23:41 - verify exit=0 in 404.9s (cwd=KB-032) -> 4-verifying
    verifying ticket/KB-032 at 9a9dc21e1f1a; Running Tier 1 (Feature Tests): python -m pytest tests/test_ingest_traceability.py -q
python tests/run_parallel.py -j 8; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_ingest_traceability.py -q
python tests/run_parallel.py -j 8] && [6/6 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs e4b344ddd56c]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_ingest_traceability.py -q
    .........                                                                [100%]

    $ python tests/run_parallel.py -j 8
    750 tests, 8 workers, 171s, all passed


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k unknown_covers
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k uncovered_requirement
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k unapproved_spec
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k radius_size
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k skipped_requirements
    ..                                                                       [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k warnings_exit_zero
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    750 tests, 8 workers, 182s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_ingest_traceability.py -q
    ..FFFFF.F                                                                [100%]
    ================================== FAILURES ===================================
    ________________________ test_warns_on_unknown_covers _________________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_warns_on_unknown_covers0/scratch')

        def test_warns_on_unknown_covers(board: Path) -> None:
            path = write_real_spec(
                board,
                requirements=("R1: first requirement",),
                tickets_body=ONE_TICKET.format(covers="R1, R99"),
            )
            config = core.load_config(board)
            specs.approve_spec(config, "SPEC-001", "tim")

            [report] = ingest.ingest(config, [path], dry_run=True)

    >       assert any(
                "R99" in warning and "does not define" in warning for warning in report.warnings
            ), report.warnings
    E       AssertionError: []
    E       assert False
    E        +  where False = any(<generator object test_warns_on_unknown_covers.<locals>.<genexpr> at 0x00000180ADF1F440>)

    tests\test_ingest_traceability.py:148: AssertionError
    _____________________ test_warns_on_uncovered_requirement _____________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_warns_on_uncovered_requir0/scratch')

        def test_warns_on_uncovered_requirement(board: Path) -> None:
            path = write_real_spec(
                board,
                requirements=("R1: first requirement", "R2: second requirement"),
                tickets_body=ONE_TICKET.format(covers="R1"),
            )
            config = core.load_config(board)
            specs.approve_spec(config, "SPEC-001", "tim")

            [report] = ingest.ingest(config, [path], dry_run=True)

    >       assert any(
                "R2" in warning and "no draft covers" in warning for warning in report.warnings
            ), report.warnings
    E       AssertionError: []
    E       assert False
    E        +  where False = any(<generator object test_warns_on_uncovered_requirement.<locals>.<genexpr> at 0x00000180ADF1F2A0>)

    tests\test_ingest_traceability.py:164: AssertionError
    ________________________ test_warns_on_unapproved_spec ________________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_warns_on_unapproved_spec0/scratch')

        def test_warns_on_unapproved_spec(board: Path) -> None:
            path = write_real_spec(
                board,
                requirements=("R1: first requirement",),
                tickets_body=ONE_TICKET.format(covers="R1"),
            )
            config = core.load_config(board)
            # left unapproved: no specs.approve_spec call

            [report] = ingest.ingest(config, [path], dry_run=True)

    >       assert any("not approved" in warning for warning in report.warnings), report.warnings
    E       AssertionError: []
    E       assert False
    E        +  where False = any(<generator object test_warns_on_unapproved_spec.<locals>.<genexpr> at 0x00000180ADF1FAC0>)

    tests\test_ingest_traceability.py:180: AssertionError
    __________________________ test_warns_on_radius_size __________________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_warns_on_radius_size0/scratch')

        def test_warns_on_radius_size(board: Path) -> None:
            set_board_config(board, max_blast_radius_files=2)
            plan = write_plan(board, RADIUS_PLAN, "radius.md")
            config = core.load_config(board)

            [report] = ingest.ingest(config, [plan], dry_run=True)

    >       assert any("blast radius is empty" in warning for warning in report.warnings), report.warnings
    E       AssertionError: []
    E       assert False
    E        +  where False = any(<generator object test_warns_on_radius_size.<locals>.<genexpr> at 0x00000180ADF1FE00>)

    tests\test_ingest_traceability.py:215: AssertionError
    ________ test_skipped_requirements_section_warns_when_no_draft_covers _________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_skipped_requirements_sect0/scratch')

        def test_skipped_requirements_section_warns_when_no_draft_covers(board: Path) -> None:
            plan = write_plan(board, REQUIREMENTS_ORPHANED_PLAN, "orphaned.md")
            config = core.load_config(board)

            [report] = ingest.ingest(config, [plan], dry_run=True)

    >       assert any(
                "Requirements" in warning and "no draft covers" in warning
                for warning in report.warnings
            ), report.warnings
    E       AssertionError: []
    E       assert False
    E        +  where False = any(<generator object test_skipped_requirements_section_warns_when_no_draft_covers.<locals>.<genexpr> at 0x00000180ADF1DD80>)

    tests\test_ingest_traceability.py:254: AssertionError
    _______________ test_warnings_exit_zero_when_ingest_only_warns ________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1072/test_warnings_exit_zero_when_i0/scratch')
    capsys = <_pytest.capture.CaptureFixture object at 0x00000180ADFABB60>

        def test_warnings_exit_zero_when_ingest_only_warns(board: Path, capsys) -> None:
            plan = write_plan(board, RADIUS_PLAN, "exit-zero.md")

            exit_code = main(["--project-root", str(board), "ingest", str(plan)])
            output = capsys.readouterr().out

            assert exit_code == 0
    >       assert "[WARN]" in output
    E       AssertionError: assert '[WARN]' in 'Source: exit-zero.md\n  - drafted: Empty radius ticket\n      anchor: empty-radius-ticket\n      acceptance: 1 | blas...ket.md\n  [OK] created TST-002: TST-002-oversized-radius-ticket.md\n  2 created, 0 refreshed, 0 unchanged, 0 drifted\n'

    tests\test_ingest_traceability.py:278: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_ingest_traceability.py::test_warns_on_unknown_covers - Asse...
    FAILED tests/test_ingest_traceability.py::test_warns_on_uncovered_requirement
    FAILED tests/test_ingest_traceability.py::test_warns_on_unapproved_spec - Ass...
    FAILED tests/test_ingest_traceability.py::test_warns_on_radius_size - Asserti...
    FAILED tests/test_ingest_traceability.py::test_skipped_requirements_section_warns_when_no_draft_covers
    FAILED tests/test_ingest_traceability.py::test_warnings_exit_zero_when_ingest_only_warns

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-032-20261029-234102.log
- 2026-10-29 23:49 - approved by qa-reviewer at 9a9dc21e1f1a