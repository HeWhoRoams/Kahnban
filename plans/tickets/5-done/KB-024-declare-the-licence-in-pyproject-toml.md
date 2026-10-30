---
id: KB-024
title: Declare the licence in pyproject.toml
status: done
owner: coder-agent
branch: ticket/KB-024
worktree: .worktrees/KB-024
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-023]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/declare-the-licence-in-pyproject-toml
source_hash: 1e78674ef093
validation_class: headless-verified
covers: [R10]
spec: SPEC-001
contract_hash: df3650d17f2aa8d7
contract_sig: 57be048441e09f8ae49b817c5dc454e17af37cf2808913789b68c93aa45c1f28
confirmed: ""
verified_sha: 2b799dab99d3ebd539d1d1b68d94911eb24db7d5
reviewer: qa-reviewer
approved_sha: 2b799dab99d3ebd539d1d1b68d94911eb24db7d5
approval_sig: 8da119b03e6ab236a821aa11679990e7b2fe4d51ed175516e347efbee00eaeb6
reviewer_sig: ""
integrated_sha: 43f33780af246b312a3f90acf4ccadf7942277ee
---

## Problem

## Acceptance criteria
- [x] pyproject.toml declares the MIT licence and its license file (test: `python -m pytest tests/test_license.py -q -k pyproject_declares_license`)

## Blast radius
- `pyproject.toml`
- `tests/test_license.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_license.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/declare-the-licence-in-pyproject-toml
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 21:05 - escalated to a human: waiting: depends_on not done; the running dispatcher predates KB-027, so this is parked to stop it refining early. The supervisor unblocks it when every dependency is in 5-done.
- 2026-10-29 22:31 - unblocked: dependencies are in 5-done (supervisor)
- 2026-10-29 23:03 - ready gate passed -> 2-ready | contract df3650d17f2aa8d7
- 2026-10-29 23:24 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 23:29 - verify exit=0 in 232.7s (cwd=KB-024) -> 4-verifying
    verifying ticket/KB-024 at 2b799dab99d3; Running Tier 1 (Feature Tests): python -m pytest tests/test_license.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_license.py -q] && [1/1 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs a3b8fc4cd948]
    === TIER 1: FEATURE TESTS ===
    ...                                                                      [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_license.py -q -k pyproject_declares_license
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    744 tests, 8 workers, 209s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    .F.                                                                      [100%]
    ================================== FAILURES ===================================
    _______________________ test_pyproject_declares_license _______________________

        def test_pyproject_declares_license() -> None:
            text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    >       assert 'license = "MIT"' in text
    E       assert 'license = "MIT"' in '[build-system]\nrequires = ["setuptools>=77"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = "kahnban"...md", "templates/*.json", "templates/skills/**/*.md"]\n[tool.coverage.run]\nsource = ["src/kahnban"]\nparallel = true\n'

    tests\test_license.py:19: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_license.py::test_pyproject_declares_license - assert 'licen...

    full output: plans/tickets/.artifacts/KB-024-20261029-232902.log
- 2026-10-29 23:33 - approved by qa-reviewer at 2b799dab99d3
- 2026-10-29 23:33 - approval by qa-reviewer countersigned by the runner at 2b799dab99d3
- 2026-10-29 23:33 - integrated into main | merge-commit: 43f33780af246b312a3f90acf4ccadf7942277ee
    $ merge ticket/KB-024 onto main 936d18db145e
    === INTEGRATION: FEATURE TESTS ===
    ...                                                                      [100%]


    === INTEGRATION: REGRESSION TESTS ===
    744 tests, 8 workers, 196s, all passed

    full output: plans/tickets/.artifacts/KB-024-20261029-233348.log
- 2026-10-29 23:37 - done gate passed -> 5-done | merge-commit: 43f33780af246b312a3f90acf4ccadf7942277ee