---
id: KB-025
title: lint help names the real rule range
status: verifying
owner: coder-agent
branch: ticket/KB-025
worktree: .worktrees/KB-025
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/lint-help-names-the-real-rule-range
source_hash: bb144b599d40
validation_class: headless-verified
covers: [R12]
spec: SPEC-001
contract_hash: 56148b8bf0ac0793
contract_sig: b01efc62360c1a919c5a6d7ad88d717531ce0d22db21ba3204b30fb4add510db
confirmed: ""
verified_sha: b61d3b728973f554f4299494683c22ae740604ac
reviewer: qa-reviewer
approved_sha: b61d3b728973f554f4299494683c22ae740604ac
approval_sig: 37c05ab4bc793a8b8143f31b848df63d59b1c311cebbaa8175c182b722a97c10
reviewer_sig: ""
integrated_sha: ""
---

## Problem

## Acceptance criteria
- [x] kahnban lint --help names the first and last rule ids of the linter's rule table (test: `python -m pytest tests/test_lint_help.py -q -k help_range_from_table`)

## Blast radius
- `src/kahnban/cli.py`
- `tests/test_lint_help.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_lint_help.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/lint-help-names-the-real-rule-range
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 56148b8bf0ac0793
- 2026-10-29 22:30 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 22:36 - verify exit=0 in 208.4s (cwd=KB-025) -> 4-verifying
    verifying ticket/KB-025 at b61d3b728973; Running Tier 1 (Feature Tests): python -m pytest tests/test_lint_help.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_lint_help.py -q] && [1/1 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 729e79b612d8]
    === TIER 1: FEATURE TESTS ===
    .                                                                        [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_lint_help.py -q -k help_range_from_table
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    739 tests, 8 workers, 183s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    F                                                                        [100%]
    ================================== FAILURES ===================================
    _________________________ test_help_range_from_table __________________________

        def test_help_range_from_table() -> None:
            rule_ids = sorted(linter.RULES)
            first, last = rule_ids[0], rule_ids[-1]
            help_text = _lint_help()
            match = re.search(r"\bBL\d+-BL\d+\b", help_text)
            assert match, f"no rule range found in help text: {help_text!r}"
    >       assert match.group(0) == f"{first}-{last}", (
                f"help names {match.group(0)!r} but the rule table spans {first}-{last}"
            )
    E       AssertionError: help names 'BL01-BL16' but the rule table spans BL01-BL20
    E       assert 'BL01-BL16' == 'BL01-BL20'
    E         
    E         - BL01-BL20
    E         ?        ^^
    E         + BL01-BL16
    E         ?        ^^

    tests\test_lint_help.py:22: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_lint_help.py::test_help_range_from_table - AssertionError: ...

    full output: plans/tickets/.artifacts/KB-025-20261029-223643.log
- 2026-10-29 22:40 - approved by qa-reviewer at b61d3b728973
- 2026-10-29 22:40 - approval by qa-reviewer countersigned by the runner at b61d3b728973