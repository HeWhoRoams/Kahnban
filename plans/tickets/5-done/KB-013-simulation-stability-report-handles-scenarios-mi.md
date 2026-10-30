---
id: KB-013
title: "Simulation stability_report handles scenarios missing from a run, and --accept without a baseline says what to do"
status: done
owner: coder-agent
branch: ""
worktree: ""
created: 2026-10-29
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
contract_hash: d2e146a4bf5fea9f
contract_sig: 8828727a23b708c82b2dd47a4d2dbc799bf294f0639a93d9bf071fe9785cb2d6
confirmed: ""
verified_sha: ba4b77ec1eb0891e552982de5fa0dc86dec4e9dc
reviewer: qa-reviewer
approved_sha: ba4b77ec1eb0891e552982de5fa0dc86dec4e9dc
approval_sig: 1ca9ecfeadfbcdc5c7abc053d4160ead4009d2d9175902c7cf2def0cb4180ae8
reviewer_sig: ""
integrated_sha: ffd401a09349af508f1a2b10e7e23c5c80d16e77
---

## Problem
## R3: Simulation stability hardening (finding 7)

Files: `tests/sim/compare.py`, `tests/sim/__main__.py`, `tests/test_sim_compare.py`.

- `stability_report` takes the union of scenario ids and metric names across all cards; a scenario or
  metric missing from some run counts as unstable.
- `stability --accept` with no baseline file writes a baseline containing only `unstable`, or says "run
  `compare --accept` first" (pick the second: one clear message).
- Tests: a card missing a scenario is reported, not a `KeyError`; `--accept` without a baseline gives the message.


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria
- [x] `stability_report` takes the union of scenario ids and metric names across all cards, instead of only `cards[0]`'s (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report_covers_the_union`)
- [x] a scenario or metric present in some runs but missing from another is reported as moved/unstable, not a `KeyError` (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report_handles_a_missing_scenario`)
- [x] `stability --accept` with no baseline file prints "run `compare --accept` first" and exits non-zero instead of raising `FileNotFoundError` (test: `python -m pytest tests/test_sim_compare.py -q -k stability_accept_without_baseline`)

## Blast radius
- `tests/sim/compare.py`
- `tests/sim/__main__.py`
- `tests/test_sim_compare.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_sim_compare.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:37 - ready gate passed -> 2-ready | contract d2e146a4bf5fea9f
- 2026-10-29 19:37 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 20:01 - verify exit=0 in 446.1s (cwd=KB-013) -> 4-verifying
    verifying ticket/KB-013 at ba4b77ec1eb0; Running Tier 1 (Feature Tests): python -m pytest tests/test_sim_compare.py -q
python tests/run_parallel.py -j 8; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_sim_compare.py -q
python tests/run_parallel.py -j 8] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 853b7d44a61c]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_sim_compare.py -q
    ..............                                                           [100%]

    $ python tests/run_parallel.py -j 8
    728 tests, 8 workers, 188s, all passed


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k stability_report_covers_the_union
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k stability_report_handles_a_missing_scenario
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k stability_accept_without_baseline
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    728 tests, 8 workers, 184s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_sim_compare.py -q
    ..........FFF.                                                           [100%]
    ================================== FAILURES ===================================
    ___________________ test_stability_report_covers_the_union ____________________

        def test_stability_report_covers_the_union() -> None:
            from sim.compare import stability_report

            first = copy.deepcopy(CARD)
            del first["scenarios"]["S1"]["metrics"]["steps_to_done"]  # cards[0] is missing a metric the others have
            second = changed(steps_to_done=9)

    >       assert stability_report([first, second]) == ["S1 steps_to_done"]
    E       AssertionError: assert [] == ['S1 steps_to_done']
    E         
    E         Right contains one more item: 'S1 steps_to_done'
    E         Use -v to get more diff

    tests\test_sim_compare.py:116: AssertionError
    ______________ test_stability_report_handles_a_missing_scenario _______________

        def test_stability_report_handles_a_missing_scenario() -> None:
            from sim.compare import stability_report

            first = copy.deepcopy(CARD)
            second = copy.deepcopy(CARD)
            del second["scenarios"]["S1"]  # a run where the scenario didn't happen at all

    >       result = stability_report([first, second])
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_sim_compare.py:126: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    cards = [{'engine': '1.4.0', 'scenarios': {'S1': {'expectations': {'done': {'pass': True}}, 'invariants': {'I1': {'pass': True..._refusals': 0, 'steps_to_done': 4, 'wall_seconds': 5.0, ...}, 'ok': True, ...}}}, {'engine': '1.4.0', 'scenarios': {}}]

        def stability_report(cards: list[dict[str, Any]]) -> list[str]:
            """'S3 steps_to_done' for every metric whose value differs between runs of one unchanged tree."""
            moved = set()
            for ident in cards[0]["scenarios"]:
                for name in cards[0]["scenarios"][ident]["metrics"]:
                    if name in IGNORED:
                        continue
    >               if len({repr(card["scenarios"][ident]["metrics"].get(name)) for card in cards}) > 1:
                                 ^^^^^^^^^^^^^^^^^^^^^^^^
    E               KeyError: 'S1'

    tests\sim\compare.py:64: KeyError
    ___________________ test_stability_accept_without_baseline ____________________

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-685/test_stability_accept_without_0')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001C8A05AAE10>
    capsys = <_pytest.capture.CaptureFixture object at 0x000001C8A082A660>

        def test_stability_accept_without_baseline(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
            import pytest

            from sim import __main__ as sim_main

            baseline = tmp_path / "scorecard.json"  # does not exist
            monkeypatch.setattr(sim_main, "BASELINE", baseline)

            with pytest.raises(SystemExit) as exc:
    >           sim_main.main(["stability", "S1", "--runs", "1", "--accept"])

    tests\test_sim_compare.py:141: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    tests\sim\__main__.py:119: in main
        kept = json.loads(BASELINE.read_text(encoding="utf-8"))
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:546: in read_text
        return PathBase.read_text(self, encoding, errors, newline)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_abc.py:632: in read_text
        with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-685/test_stability_accept_without_0/scorecard.json')
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
    E       FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-685\\test_stability_accept_without_0\\scorecard.json'

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:537: FileNotFoundError
    ---------------------------- Captured stdout call -----------------------------
    [OK] TST-001: (new) -> 0-backlog (commit b5ad27e9)
         C:\Users\User\AppData\Local\Temp\sim-S1-2andzai9\repo\plans\tickets\0-backlog\TST-001-make-m1-f-return-2.md
    [PASS] S1 One idea from the backlog to done, honest agents | steps 4, first-pass 1.0, prompts 1277B, 8.4s
    0 metric(s) moved over 1 runs: none
    =========================== short test summary info ===========================
    FAILED tests/test_sim_compare.py::test_stability_report_covers_the_union - As...
    FAILED tests/test_sim_compare.py::test_stability_report_handles_a_missing_scenario
    FAILED tests/test_sim_compare.py::test_stability_accept_without_baseline - Fi...

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-013-20261029-200105.log
- 2026-10-29 20:17 - approved by qa-reviewer at ba4b77ec1eb0
- 2026-10-29 20:17 - approval by qa-reviewer countersigned by the runner at ba4b77ec1eb0
- 2026-10-29 20:17 - integrated into main | merge-commit: ffd401a09349af508f1a2b10e7e23c5c80d16e77
    $ merge ticket/KB-013 onto main ef14cb25fade
    === INTEGRATION: FEATURE TESTS ===
    $ python -m pytest tests/test_sim_compare.py -q
    ..............                                                           [100%]

    $ python tests/run_parallel.py -j 8
    733 tests, 8 workers, 186s, all passed


    === INTEGRATION: REGRESSION TESTS ===
    733 tests, 8 workers, 183s, all passed

    full output: plans/tickets/.artifacts/KB-013-20261029-201740.log
- 2026-10-29 20:24 - done gate passed -> 5-done | merge-commit: ffd401a09349af508f1a2b10e7e23c5c80d16e77
- 2026-10-29 20:24 - cleanup: removed worktree: KB-013; deleted branch: ticket/KB-013