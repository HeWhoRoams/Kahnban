---
id: KB-007
title: Reviewer identity that is not self-asserted
status: done
owner: claude-coder
branch: ticket/KB-007
worktree: .worktrees/KB-007
created: 2026-10-25
updated: 2026-10-28
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 0bf3ef8b8e5113a1
contract_sig: e08fe92d909316fd4721bc9c79bfda7fade1c08c8194b208b780f5bd3f9f06cd
confirmed: ""
verified_sha: c4e3f23abddacb4b0f65d0a2502d1c6d084fb95e
reviewer: Tim Niles
approved_sha: c4e3f23abddacb4b0f65d0a2502d1c6d084fb95e
approval_sig: 13039a917b833bb72cad32c143c8bd9308bbaad73392499ccfbc382efc083655
integrated_sha: 022152efe72b8cfbf96f3e57885e138492bf1ae4
---

## Problem
`kahnban approve --reviewer <name>` records whatever name is typed. The owner check compares two strings, so a typo, a worker or a
second hat can approve under any other name. Decided with the user (2026-10-26): registered reviewer keys.

`kahnban reviewers add <name>` creates a key for that reviewer in the user's key directory (next to the project signing key, never in
the repository). Once a project has at least one registered reviewer, `approve` must be made by a registered one and also records
`reviewer_sig`, an HMAC with that reviewer's key over the ticket, tip and reviewer; `merge` and `done` refuse an approval whose
`reviewer_sig` is missing or wrong. A project with no registered reviewer behaves as before. Limits for the README: a process running
as the same OS user can read every key, and an agent-reviewer flow (a worker approving, the runner countersigning) has no personal key,
so a project that registers reviewers expects human approvals.

## Acceptance criteria
- [x] `kahnban reviewers add NAME` registers a reviewer once, `kahnban reviewers list` shows the names, and adding the same name again is refused (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add`)
- [x] once any reviewer is registered, `approve` by an unregistered name is refused, and by a registered one stores `reviewer_sig` (test: `python -m pytest tests/test_reviewer_keys.py -q -k registered_reviewer`)
- [x] `merge` and `done` refuse an approval whose `reviewer_sig` was removed or edited, and a project with no registered reviewer behaves as before (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewer_sig`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/core.py`
- `src/kahnban/cli.py`
- `tests/test_reviewer_keys.py`

## Implementation notes
- trust.py: `reviewers_dir`, `register_reviewer`, `registered_reviewers`, `sign_reviewer`, `reviewer_problem`; one JSON file per reviewer, named by a hash of the lower-cased name, holding the name and a random key; `key_dir()` is overridable, so tests are isolated.
- core.py: `approve` refuses an unregistered name when any is registered and stores `reviewer_sig`; `_signature_problem` (the one hook merge and done share) also checks it; `reject` stays open.
- cli.py: a `reviewers` parser with `add` and `list`; tests call `main(["reviewers", "add", ...])`.
- Needs 4 files, so `max_blast_radius_files` is raised to 4 for this ticket and restored when it is done.

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 23:32 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 23:32 - ready gate passed -> 2-ready | contract 0bf3ef8b8e5113a1
- 2026-10-26 23:32 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 23:33 - verify exit=0 in 247.8s (cwd=KB-007) -> 4-verifying
    verifying ticket/KB-007 at c4e3f23abdda; Running Tier 1 (Feature Tests): python -m pytest tests/test_reviewer_keys.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_reviewer_keys.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 519e559c9fde]
    === TIER 1: FEATURE TESTS ===
    .....                                                                    [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k registered_reviewer
    ..                                                                       [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k reviewer_sig
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    723 tests, 8 workers, 183s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF.FF                                                                    [100%]
    ================================== FAILURES ===================================
    _________ test_reviewers_add_registers_once_and_list_shows_the_names __________

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    args = ['reviewers', 'list', '--project-root', 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-538\\test_reviewers_add_registers_o0\\scratch']
    namespace = Namespace(project_root=None, config=None, command=None)
    intermixed = False

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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    action = _SubParsersAction(option_strings=[], dest='command', nargs='A...', const=None, default=None, type=None, choices={'new'....HelpFormatter'>, conflict_handler='error', add_help=True)}, required=False, help=None, metavar=None, deprecated=False)
    value = 'reviewers'

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
    E               argparse.ArgumentError: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2578: ArgumentError

    During handling of the above exception, another exception occurred:

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-538/test_reviewers_add_registers_o0/scratch')
    capsys = <_pytest.capture.CaptureFixture object at 0x00000147411EBCB0>

        def test_reviewers_add_registers_once_and_list_shows_the_names(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
            factory_board(repo)
            root = ["--project-root", str(repo)]

    >       assert cli.main(["reviewers", "list", *root]) == 0
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_reviewer_keys.py:27: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\cli.py:1077: in main
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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = "kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, ...uard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)\n"

        def exit(self, status=0, message=None):
            if message:
                self._print_message(message, _sys.stderr)
    >       _sys.exit(status)
    E       SystemExit: 2

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2645: SystemExit
    ---------------------------- Captured stderr call -----------------------------
    usage: kahnban [-h] [--version] [--project-root PROJECT_ROOT]
                   [--config CONFIG]
                   {new,ready,claim,verify,done,approve,reject,merge,run,lease,escalate,unblock,confirm,spec,guard,move,cleanup,ingest,capture,lint,sync,status,init,session,handoff,learnings,next,feedback,skills} ...
    kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)
    _ test_an_unregistered_name_cannot_approve_once_a_registered_reviewer_exists __

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    args = ['reviewers', 'add', 'alice', '--project-root', 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-538\\test_an_unregistered_name_cann0\\scratch']
    namespace = Namespace(project_root=None, config=None, command=None)
    intermixed = False

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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    action = _SubParsersAction(option_strings=[], dest='command', nargs='A...', const=None, default=None, type=None, choices={'new'....HelpFormatter'>, conflict_handler='error', add_help=True)}, required=False, help=None, metavar=None, deprecated=False)
    value = 'reviewers'

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
    E               argparse.ArgumentError: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2578: ArgumentError

    During handling of the above exception, another exception occurred:

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-538/test_an_unregistered_name_cann0/scratch')

        def test_an_unregistered_name_cannot_approve_once_a_registered_reviewer_exists(repo: Path) -> None:
            config = factory_board(repo)
            verified(config)
    >       cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])

    tests\test_reviewer_keys.py:39: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\cli.py:1077: in main
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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = "kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, ...uard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)\n"

        def exit(self, status=0, message=None):
            if message:
                self._print_message(message, _sys.stderr)
    >       _sys.exit(status)
    E       SystemExit: 2

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2645: SystemExit
    ---------------------------- Captured stderr call -----------------------------
    usage: kahnban [-h] [--version] [--project-root PROJECT_ROOT]
                   [--config CONFIG]
                   {new,ready,claim,verify,done,approve,reject,merge,run,lease,escalate,unblock,confirm,spec,guard,move,cleanup,ingest,capture,lint,sync,status,init,session,handoff,learnings,next,feedback,skills} ...
    kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)
    _________ test_an_edited_or_removed_reviewer_sig_is_refused_at_merge __________

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    args = ['reviewers', 'add', 'alice', '--project-root', 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-538\\test_an_edited_or_removed_revi0\\scratch']
    namespace = Namespace(project_root=None, config=None, command=None)
    intermixed = False

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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    action = _SubParsersAction(option_strings=[], dest='command', nargs='A...', const=None, default=None, type=None, choices={'new'....HelpFormatter'>, conflict_handler='error', add_help=True)}, required=False, help=None, metavar=None, deprecated=False)
    value = 'reviewers'

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
    E               argparse.ArgumentError: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2578: ArgumentError

    During handling of the above exception, another exception occurred:

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-538/test_an_edited_or_removed_revi0/scratch')

        def test_an_edited_or_removed_reviewer_sig_is_refused_at_merge(repo: Path) -> None:
            config = factory_board(repo)
            verified(config)
    >       cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])

    tests\test_reviewer_keys.py:61: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\cli.py:1077: in main
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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = "kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, ...uard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)\n"

        def exit(self, status=0, message=None):
            if message:
                self._print_message(message, _sys.stderr)
    >       _sys.exit(status)
    E       SystemExit: 2

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2645: SystemExit
    ---------------------------- Captured stderr call -----------------------------
    usage: kahnban [-h] [--version] [--project-root PROJECT_ROOT]
                   [--config CONFIG]
                   {new,ready,claim,verify,done,approve,reject,merge,run,lease,escalate,unblock,confirm,spec,guard,move,cleanup,ingest,capture,lint,sync,status,init,session,handoff,learnings,next,feedback,skills} ...
    kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)
    __________________ test_a_worker_cannot_register_a_reviewer ___________________

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    args = ['reviewers', 'add', 'mallory', '--project-root', 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-538\\test_a_worker_cannot_register_0\\scratch']
    namespace = Namespace(project_root=None, config=None, command=None)
    intermixed = False

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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    action = _SubParsersAction(option_strings=[], dest='command', nargs='A...', const=None, default=None, type=None, choices={'new'....HelpFormatter'>, conflict_handler='error', add_help=True)}, required=False, help=None, metavar=None, deprecated=False)
    value = 'reviewers'

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
    E               argparse.ArgumentError: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2578: ArgumentError

    During handling of the above exception, another exception occurred:

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-538/test_a_worker_cannot_register_0/scratch')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000147424F1F20>

        def test_a_worker_cannot_register_a_reviewer(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
            factory_board(repo)
            monkeypatch.setenv("KAHNBAN_ROLE", "coder")

    >       assert cli.main(["reviewers", "add", "mallory", "--project-root", str(repo)]) != 0
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_reviewer_keys.py:84: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\cli.py:1077: in main
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

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = "kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, ...uard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)\n"

        def exit(self, status=0, message=None):
            if message:
                self._print_message(message, _sys.stderr)
    >       _sys.exit(status)
    E       SystemExit: 2

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2645: SystemExit
    ---------------------------- Captured stderr call -----------------------------
    usage: kahnban [-h] [--version] [--project-root PROJECT_ROOT]
                   [--config CONFIG]
                   {new,ready,claim,verify,done,approve,reject,merge,run,lease,escalate,unblock,confirm,spec,guard,move,cleanup,ingest,capture,lint,sync,status,init,session,handoff,learnings,next,feedback,skills} ...
    kahnban: error: argument command: invalid choice: 'reviewers' (choose from new, ready, claim, verify, done, approve, reject, merge, run, lease, escalate, unblock, confirm, spec, guard, move, cleanup, ingest, capture, lint, sync, status, init, session, handoff, learnings, next, feedback, skills)
    =========================== short test summary info ===========================
    FAILED tests/test_reviewer_keys.py::test_reviewers_add_registers_once_and_list_shows_the_names
    FAILED tests/test_reviewer_keys.py::test_an_unregistered_name_cannot_approve_once_a_registered_reviewer_exists
    FAILED tests/test_reviewer_keys.py::test_an_edited_or_removed_reviewer_sig_is_refused_at_merge
    FAILED tests/test_reviewer_keys.py::test_a_worker_cannot_register_a_reviewer

    full output: plans/tickets/.artifacts/KB-007-20261026-233355.log
- 2026-10-28 22:24 - approved by Tim Niles at c4e3f23abdda
- 2026-10-28 22:24 - integrated into main | merge-commit: 022152efe72b8cfbf96f3e57885e138492bf1ae4
    $ merge ticket/KB-007 onto main 382b5d6dbb77
    === INTEGRATION: FEATURE TESTS ===
    .....                                                                    [100%]


    === INTEGRATION: REGRESSION TESTS ===
    723 tests, 8 workers, 202s, all passed

    full output: plans/tickets/.artifacts/KB-007-20261028-222428.log
- 2026-10-28 22:28 - done gate passed -> 5-done | merge-commit: 022152efe72b8cfbf96f3e57885e138492bf1ae4