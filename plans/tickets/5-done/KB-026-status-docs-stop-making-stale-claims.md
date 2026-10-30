---
id: KB-026
title: Status docs stop making stale claims
status: done
owner: coder-agent
branch: ticket/KB-026
worktree: .worktrees/KB-026
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/status-docs-stop-making-stale-claims
source_hash: 01ba13816e3a
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
contract_hash: 92f5edd88d033004
contract_sig: 6f9e08b42a98bd62d77e120053e695f134b9fc7a7392107aa37feda229bd17d0
confirmed: ""
verified_sha: 180dcf74b3d0c00f6fc8aa868dccb3c1335cafb3
reviewer: qa-reviewer
approved_sha: 180dcf74b3d0c00f6fc8aa868dccb3c1335cafb3
approval_sig: ebfe432ddcb6327cded226d8681ae4b06b6aa5eba1568fa68408572c351b6240
reviewer_sig: ""
integrated_sha: da3c237525c68fb2ba3b32f3efd14581fe68a188
---

## Problem

## Acceptance criteria
- [x] neither doc states a hard-coded test count (test: `python -m pytest tests/test_status_docs.py -q -k no_test_count`)
- [x] neither doc describes kahnban run as sequential or one ticket at a time (test: `python -m pytest tests/test_status_docs.py -q -k no_sequential_claim`)

## Blast radius
- `implementation_status.md`
- `next_steps.md`
- `tests/test_status_docs.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_status_docs.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/status-docs-stop-making-stale-claims
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 92f5edd88d033004
- 2026-10-29 22:43 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 22:55 - verify exit=0 in 191.2s (cwd=KB-026) -> 4-verifying
    verifying ticket/KB-026 at 180dcf74b3d0; Running Tier 1 (Feature Tests): python -m pytest tests/test_status_docs.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_status_docs.py -q] && [2/2 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs fd23fded2885]
    === TIER 1: FEATURE TESTS ===
    ..                                                                       [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_status_docs.py -q -k no_test_count
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_status_docs.py -q -k no_sequential_claim
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    741 tests, 8 workers, 170s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF                                                                       [100%]
    ================================== FAILURES ===================================
    _____________________________ test_no_test_count ______________________________

        def test_no_test_count():
            for name in DOCS:
                text = _text(name)
                match = TEST_COUNT_RE.search(text)
    >           assert not match, f"{name} states a hard-coded test count: {match.group(0)!r}"
    E           AssertionError: implementation_status.md states a hard-coded test count: '343 tests'
    E           assert not <re.Match object; span=(1936, 1945), match='343 tests'>

    tests\test_status_docs.py:31: AssertionError
    __________________________ test_no_sequential_claim ___________________________

        def test_no_sequential_claim():
            for name in DOCS:
                text = _text(name)
                match = SEQUENTIAL_RE.search(text)
    >           assert not match, (
                    f"{name} describes `kahnban run` as sequential/one-ticket-at-a-time: "
                    f"{match.group(0)!r}"
                )
    E           AssertionError: implementation_status.md describes `kahnban run` as sequential/one-ticket-at-a-time: 'one ticket at a time'
    E           assert not <re.Match object; span=(3777, 3797), match='one ticket at a time'>

    tests\test_status_docs.py:38: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_status_docs.py::test_no_test_count - AssertionError: implem...
    FAILED tests/test_status_docs.py::test_no_sequential_claim - AssertionError: ...

    full output: plans/tickets/.artifacts/KB-026-20261029-225532.log
- 2026-10-29 22:59 - approved by qa-reviewer at 180dcf74b3d0
- 2026-10-29 22:59 - approval by qa-reviewer countersigned by the runner at 180dcf74b3d0
- 2026-10-29 22:59 - integrated into main | merge-commit: da3c237525c68fb2ba3b32f3efd14581fe68a188
    $ merge ticket/KB-026 onto main 155133470794
    === INTEGRATION: FEATURE TESTS ===
    ..                                                                       [100%]


    === INTEGRATION: REGRESSION TESTS ===
    741 tests, 8 workers, 178s, all passed

    full output: plans/tickets/.artifacts/KB-026-20261029-225933.log
- 2026-10-29 23:02 - done gate passed -> 5-done | merge-commit: da3c237525c68fb2ba3b32f3efd14581fe68a188