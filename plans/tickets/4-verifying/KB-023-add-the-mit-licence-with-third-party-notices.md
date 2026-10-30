---
id: KB-023
title: Add the MIT licence with third-party notices
status: verifying
owner: coder-agent
branch: ticket/KB-023
worktree: .worktrees/KB-023
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/add-the-mit-licence-with-third-party-not
source_hash: 073cf3811063
validation_class: headless-verified
covers: [R10]
spec: SPEC-001
contract_hash: 50939535bb7426aa
contract_sig: 3645a1999ae8009dd4115020cff15e0e964463a62aae6c2860a69c0997546e13
confirmed: ""
verified_sha: 11044b912ed9a298f3bdcd481a65529e2a90928a
reviewer: qa-reviewer
approved_sha: 11044b912ed9a298f3bdcd481a65529e2a90928a
approval_sig: ""
reviewer_sig: ""
integrated_sha: ""
---

## Problem

## Acceptance criteria
- [x] LICENSE is the MIT licence naming Tim Niles (test: `python -m pytest tests/test_license.py -q -k mit_license`)
- [x] THIRD_PARTY_NOTICES.md reproduces the MIT notices of cursor/plugins (pstack) and mattpocock/skills (test: `python -m pytest tests/test_license.py -q -k third_party_notices`)

## Blast radius
- `license`
- `third_party_notices.md`
- `tests/test_license.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_license.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/add-the-mit-licence-with-third-party-not
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract 50939535bb7426aa
- 2026-10-29 22:16 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 22:23 - verify exit=0 in 206.4s (cwd=KB-023) -> 4-verifying
    verifying ticket/KB-023 at 11044b912ed9; Running Tier 1 (Feature Tests): python -m pytest tests/test_license.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_license.py -q] && [2/2 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs d4f8dddf87a2]
    === TIER 1: FEATURE TESTS ===
    ..                                                                       [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_license.py -q -k mit_license
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_license.py -q -k third_party_notices
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    738 tests, 8 workers, 177s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF                                                                       [100%]
    ================================== FAILURES ===================================
    ______________________________ test_mit_license _______________________________

        def test_mit_license() -> None:
    >       text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_license.py:9: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:546: in read_text
        return PathBase.read_text(self, encoding, errors, newline)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_abc.py:632: in read_text
        with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = WindowsPath('C:/github/kahnban/.worktrees/.red-KB-023/LICENSE')
    mode = 'r', buffering = -1, encoding = 'utf-8', errors = None, newline = None

        def open(self, mode='r', buffering=-1, encoding=None,
                 errors=None, newline=None):
            """
            Open the file pointed to by this path and return a file object, as
            the built-in open() function does.
            """
            if "b" not in mode:
                encoding = io.text_encoding(encoding)
    >       return io.open(self, mode, buffering, encoding, errors, newline)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       FileNotFoundError: [Errno 2] No such file or directory: 'C:\\github\\kahnban\\.worktrees\\.red-KB-023\\LICENSE'

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:537: FileNotFoundError
    __________________________ test_third_party_notices ___________________________

        def test_third_party_notices() -> None:
    >       text = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_license.py:17: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:546: in read_text
        return PathBase.read_text(self, encoding, errors, newline)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_abc.py:632: in read_text
        with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = WindowsPath('C:/github/kahnban/.worktrees/.red-KB-023/THIRD_PARTY_NOTICES.md')
    mode = 'r', buffering = -1, encoding = 'utf-8', errors = None, newline = None

        def open(self, mode='r', buffering=-1, encoding=None,
                 errors=None, newline=None):
            """
            Open the file pointed to by this path and return a file object, as
            the built-in open() function does.
            """
            if "b" not in mode:
                encoding = io.text_encoding(encoding)
    >       return io.open(self, mode, buffering, encoding, errors, newline)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       FileNotFoundError: [Errno 2] No such file or directory: 'C:\\github\\kahnban\\.worktrees\\.red-KB-023\\THIRD_PARTY_NOTICES.md'

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:537: FileNotFoundError
    =========================== short test summary info ===========================
    FAILED tests/test_license.py::test_mit_license - FileNotFoundError: [Errno 2]...
    FAILED tests/test_license.py::test_third_party_notices - FileNotFoundError: [...

    full output: plans/tickets/.artifacts/KB-023-20261029-222302.log
- 2026-10-29 22:27 - approved by qa-reviewer at 11044b912ed9