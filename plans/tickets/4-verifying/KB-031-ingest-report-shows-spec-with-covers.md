---
id: KB-031
title: Ingest report shows spec with covers
status: verifying
owner: coder-agent
branch: ticket/KB-031
worktree: .worktrees/KB-031
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/ingest-report-shows-spec-with-covers
source_hash: 378992ff89cc
validation_class: headless-verified
covers: [R18]
spec: SPEC-001
contract_hash: 1aa72e92e2f5f414
contract_sig: a347955db20c35a75e72d0bcfac58641eefda46a634eb118fc6ea66e8fbeedc5
confirmed: ""
verified_sha: e1d0eeeaa119fe303e07f2cd26776ca8dcacf094
reviewer: qa-reviewer
approved_sha: e1d0eeeaa119fe303e07f2cd26776ca8dcacf094
approval_sig: 51ce08429ebb5819aac1cc053abcf09de4fbf837db6b0fe73456cc95c75279a9
reviewer_sig: ""
integrated_sha: dc0509efeb5e6ee824231f5ffbb92db339b79912
---

## Problem

## Acceptance criteria
- [x] the dry-run text report shows each draft's spec and covers (test: `python -m pytest tests/test_ingest_traceability.py -q -k text_report`)
- [x] the --json report has spec and covers per draft (test: `python -m pytest tests/test_ingest_traceability.py -q -k json_report`)

## Blast radius
- `src/kahnban/ingest.py`
- `tests/test_ingest_traceability.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_ingest_traceability.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/ingest-report-shows-spec-with-covers
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 1aa72e92e2f5f414
- 2026-10-29 23:02 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 23:16 - verify exit=0 in 215.6s (cwd=KB-031) -> 4-verifying
    verifying ticket/KB-031 at e1d0eeeaa119; Running Tier 1 (Feature Tests): python -m pytest tests/test_ingest_traceability.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_ingest_traceability.py -q] && [2/2 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 0bd651367418]
    === TIER 1: FEATURE TESTS ===
    ..                                                                       [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k text_report
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_ingest_traceability.py -q -k json_report
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    743 tests, 8 workers, 190s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF                                                                       [100%]
    ================================== FAILURES ===================================
    ___________________ test_text_report_shows_spec_and_covers ____________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1017/test_text_report_shows_spec_an0/scratch')

        def test_text_report_shows_spec_and_covers(board: Path) -> None:
            spec = write_spec(board)
            config = core.load_config(board)

            [report] = ingest.ingest(config, [spec], dry_run=True)
            rendered = ingest.render_report([report])

    >       assert "spec: SPEC-005" in rendered
    E       AssertionError: assert 'spec: SPEC-005' in '[DRY-RUN] Source: specs/example.md\n  - would create: Add the thing\n      anchor: tickets/add-the-thing\n      acceptance: 1 | blast radius: 1 | validation: no\n  1 would be created, 0 created, 0 refreshed, 0 unchanged, 0 drifted\n'

    tests\test_ingest_traceability.py:50: AssertionError
    ____________________ test_json_report_has_spec_and_covers _____________________

    board = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-1017/test_json_report_has_spec_and_0/scratch')

        def test_json_report_has_spec_and_covers(board: Path) -> None:
            spec = write_spec(board)
            config = core.load_config(board)

            [report] = ingest.ingest(config, [spec], dry_run=True)
            payload = json.loads(json.dumps(report.as_dict()))

            draft = payload["drafts"][0]
    >       assert draft["spec"] == "SPEC-005"
                   ^^^^^^^^^^^^^
    E       KeyError: 'spec'

    tests\test_ingest_traceability.py:62: KeyError
    =========================== short test summary info ===========================
    FAILED tests/test_ingest_traceability.py::test_text_report_shows_spec_and_covers
    FAILED tests/test_ingest_traceability.py::test_json_report_has_spec_and_covers

    full output: plans/tickets/.artifacts/KB-031-20261029-231643.log
- 2026-10-29 23:20 - approved by qa-reviewer at e1d0eeeaa119
- 2026-10-29 23:20 - approval by qa-reviewer countersigned by the runner at e1d0eeeaa119
- 2026-10-29 23:20 - integrated into main | merge-commit: dc0509efeb5e6ee824231f5ffbb92db339b79912
    $ merge ticket/KB-031 onto main 4e28f58b4eb1
    === INTEGRATION: FEATURE TESTS ===
    ..                                                                       [100%]


    === INTEGRATION: REGRESSION TESTS ===
    743 tests, 8 workers, 186s, all passed

    full output: plans/tickets/.artifacts/KB-031-20261029-232057.log