---
id: KB-003
title: Repeat the fast simulation five times on an unchanged tree and gate only the metrics that never move
status: verifying
owner: claude-coder
branch: ticket/KB-003
worktree: .worktrees/KB-003
created: 2026-10-25
updated: 2026-10-26
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 73553383573b7909
confirmed: ""
verified_sha: f0de2811bd32b853c566d71d95c2b500dc34dabc
reviewer: Tim Niles
approved_sha: f0de2811bd32b853c566d71d95c2b500dc34dabc
approval_sig: c2a4d875ad3ed4121ce086dd62a1ac5526c109211ca96492da760f290f3fe465
integrated_sha: ""
---

## Problem
The simulation baseline was made in one run and compared in one later run (docs/gap-fix-plan.md, G6). Two matching runs do not show that a
metric never moves, and the tolerances in `tests/sim/compare.py` are guesses. A metric that moves on an unchanged tree would block
every pull request. `python tests/run_sim.py stability` should run the chosen scenarios N times (default 5) on the same tree, report
which metrics moved, and let `compare` skip those, so only metrics that never move are gated.

## Acceptance criteria
- [x] `stability_report(cards)` takes the scorecards of several runs and returns the `scenario metric` names whose value differs between runs (wall_seconds ignored) (test: `python -m pytest tests/test_sim_compare.py -q -k stability_report`)
- [x] a baseline with an `unstable` list makes `compare` ignore those metrics, still gating every other metric and every invariant (test: `python -m pytest tests/test_sim_compare.py -q -k unstable_metrics`)
- [x] `run_sim.py stability --runs N` runs the chosen scenarios N times, prints the unstable metrics, and with `--accept` writes them as `unstable` into the baseline (test: `python -m pytest tests/test_sim_compare.py -q -k stability_command`)

## Blast radius
- `tests/sim/compare.py`
- `tests/sim/__main__.py`
- `tests/test_sim_compare.py`

## Implementation notes
- `stability_report` goes in compare.py; `normalize` must carry the baseline's `unstable` list through, and `compare` skips `f"{ident} {name}"` found in it.
- The command reuses `run_scenarios` in a loop; the test calls `main` with a tiny scenario and `--runs 2`.
- After merge, outside the ticket: run `stability --runs 5 --accept` once and commit the baseline.

## Validation
```
python -m pytest tests/test_sim_compare.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 19:19 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 19:19 - ready gate passed -> 2-ready | contract 73553383573b7909
- 2026-10-26 19:19 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 19:21 - verify exit=0 in 239.8s (cwd=KB-003) -> 4-verifying
    verifying ticket/KB-003 at f0de2811bd32; Running Tier 1 (Feature Tests): python -m pytest tests/test_sim_compare.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_sim_compare.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 9d90d0e14c11]
    === TIER 1: FEATURE TESTS ===
    ...........                                                              [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k stability_report
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k unstable_metrics
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_sim_compare.py -q -k stability_command
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    710 tests, 8 workers, 179s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    ........FFF                                                              [100%]
    ================================== FAILURES ===================================
    ___________ test_stability_report_names_only_the_metrics_that_moved ___________

        def test_stability_report_names_only_the_metrics_that_moved() -> None:
    >       from sim.compare import stability_report
    E       ImportError: cannot import name 'stability_report' from 'sim.compare' (C:\github\kahnban\.worktrees\.red-KB-003\tests\sim\compare.py)

    tests\test_sim_compare.py:91: ImportError
    _____________ test_unstable_metrics_in_the_baseline_are_not_gated _____________

        def test_unstable_metrics_in_the_baseline_are_not_gated() -> None:
            base = normalize(CARD)
            base["unstable"] = ["S1 steps_to_done"]

            result = compare(base, normalize(changed(steps_to_done=9, first_pass_yield=0.5)))

    >       assert result.worse == ["S1 first_pass_yield: 1.0 -> 0.5"]
    E       AssertionError: assert ['S1 first_pa...done: 4 -> 9'] == ['S1 first_pa...: 1.0 -> 0.5']
    E         
    E         Left contains one more item: 'S1 steps_to_done: 4 -> 9'
    E         Use -v to get more diff

    tests\test_sim_compare.py:105: AssertionError
    ________________ test_the_stability_command_records_what_moved ________________

    self = ArgumentParser(prog='python tests/run_sim.py', usage=None, description=None, formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    args = ['stability', 'S1', '--runs', '2', '--accept']
    namespace = Namespace(command=None), intermixed = False

        def _parse_known_args2(self, args, namespace, intermixed):
            if args is None:
                # args default to the system args
                args = _sys.argv[1:]
            else:
                # make sure that args are mutable
                args = list(args)

            # default Namespace built from parser defaults
            if namespace is None:
                namespace = Namespace()

            # add any action defaults that aren't present
            for action in self._actions:
                if action.dest is not SUPPRESS:
                    if not hasattr(namespace, action.dest):
                        if action.default is not SUPPRESS:
                            setattr(namespace, action.dest, action.default)

            # add any parser defaults that aren't present
            for dest in self._defaults:
                if not hasattr(namespace, dest):
                    setattr(namespace, dest, self._defaults[dest])

            # parse the arguments and exit if there are any errors
            if self.exit_on_error:
                try:
    >               namespace, args = self._parse_known_args(args, namespace, intermixed)
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1937: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2169: in _parse_known_args
        positionals_end_index = consume_positionals(start_index)
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2144: in consume_positionals
        take_action(action, args)
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1998: in take_action
        argument_values = self._get_values(action, argument_strings)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2528: in _get_values
        self._check_value(action, value[0])
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = ArgumentParser(prog='python tests/run_sim.py', usage=None, description=None, formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    action = _SubParsersAction(option_strings=[], dest='command', nargs='A...', const=None, default=None, type=None, choices={'run'...e.HelpFormatter'>, conflict_handler='error', add_help=True)}, required=True, help=None, metavar=None, deprecated=False)
    value = 'stability'

        def _check_value(self, action, value):
            # converted value must be one of the choices (if specified)
            choices = action.choices
            if choices is not None:
                if isinstance(choices, str):
                    choices = iter(choices)
                if value not in choices:
                    args = {'value': str(value),
                            'choices': ', '.join(map(str, action.choices))}
                    msg = _('invalid choice: %(value)r (choose from %(choices)s)')
    >               raise ArgumentError(action, msg % args)
    E               argparse.ArgumentError: argument command: invalid choice: 'stability' (choose from run, compare, list, canaries)

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2578: ArgumentError

    During handling of the above exception, another exception occurred:

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-447/test_the_stability_command_rec0')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000018094976350>
    capsys = <_pytest.capture.CaptureFixture object at 0x0000018094A4A510>

        def test_the_stability_command_records_what_moved(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
            import json

            from sim import __main__ as sim_main

            baseline = tmp_path / "scorecard.json"
            baseline.write_text(json.dumps({"engine": "x", "scenarios": {}}), encoding="utf-8")
            monkeypatch.setattr(sim_main, "BASELINE", baseline)

    >       assert sim_main.main(["stability", "S1", "--runs", "2", "--accept"]) == 0
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_sim_compare.py:118: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    tests\sim\__main__.py:96: in main
        args = parser.parse_args(argv)
               ^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1898: in parse_args
        args, argv = self.parse_known_args(args, namespace)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1908: in parse_known_args
        return self._parse_known_args2(args, namespace, intermixed=False)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1939: in _parse_known_args2
        self.error(str(err))
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2658: in error
        self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = ArgumentParser(prog='python tests/run_sim.py', usage=None, description=None, formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = "python tests/run_sim.py: error: argument command: invalid choice: 'stability' (choose from run, compare, list, canaries)\n"

        def exit(self, status=0, message=None):
            if message:
                self._print_message(message, _sys.stderr)
    >       _sys.exit(status)
    E       SystemExit: 2

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2645: SystemExit
    ---------------------------- Captured stderr call -----------------------------
    usage: python tests/run_sim.py [-h] {run,compare,list,canaries} ...
    python tests/run_sim.py: error: argument command: invalid choice: 'stability' (choose from run, compare, list, canaries)
    =========================== short test summary info ===========================
    FAILED tests/test_sim_compare.py::test_stability_report_names_only_the_metrics_that_moved
    FAILED tests/test_sim_compare.py::test_unstable_metrics_in_the_baseline_are_not_gated
    FAILED tests/test_sim_compare.py::test_the_stability_command_records_what_moved

    full output: plans/tickets/.artifacts/KB-003-20261026-192130.log
- 2026-10-26 20:00 - approved by Tim Niles at f0de2811bd32