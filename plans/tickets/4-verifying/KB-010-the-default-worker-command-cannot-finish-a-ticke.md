---
id: KB-010
title: "The default worker command cannot finish a ticket headlessly: claude -p with acceptEdits is asked to approve git and kahnban commands. Allow the commands each role needs (allowedTools or project permission rules written by skills install) and prove it with the live test"
status: verifying
owner: claude-coder
branch: ""
worktree: ""
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
contract_hash: 46f79f588a5ad81d
confirmed: ""
verified_sha: 42f7ae1eb79473b80f3f0affffa10929b0715403
reviewer: ""
approved_sha: ""
approval_sig: ""
integrated_sha: ""
---

## Problem
A headless `claude -p --permission-mode acceptEdits` worker is asked to approve `git add`, `git commit` and
`kahnban approve`, and a headless worker cannot answer. Two live runs with Haiku (2026-10-25) show it: the first
coder finished its work and could not commit it; with git allowed by name the second got through refine, implement
and verify, and the reviewer then never ran `kahnban approve` or `kahnban reject`.

`kahnban skills install` has always left a project's permissions alone, and an existing test pins that. So the
rules a worker needs are opt-in: `kahnban skills install --harness claude --allow-worker-commands` writes them
into `.claude/settings.json` (decided with the user, 2026-10-26). The guard still refuses push, `--no-verify`
and every command outside a role.

## Acceptance criteria
- [x] installing for claude without the flag leaves the project's permissions exactly as found (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_left`)
- [x] with --allow-worker-commands it writes permissions.allow with the kahnban command and the git verbs a worker needs, and never git push (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_written`)
- [x] with the flag, other settings and rules are kept and nothing is added twice (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_keep`)
- [x] with the flag, the board's validation and regression commands are allowed too (test: `python -m pytest tests/test_harness_files.py -q -k claude_permissions_include_the_board`)

## Blast radius
- `src/kahnban/skills.py`
- `src/kahnban/cli.py`
- `tests/test_harness_files.py`

## Implementation notes
- Cherry-pick `74a5a99` from `ticket/kb010-saved` (the first version, on by default), then move its three helpers (`CLAUDE_ALLOWED`, `allowed_tools`, `merge_permissions`) from `harnesses.py` into `skills.py`: the blast-radius cap is three files.
- `install_skills(..., allow_worker_commands=False)`; the claude harness calls `merge_permissions` only when it is true. `skills install` gets `--allow-worker-commands`.
- Specific git verbs (add, commit, status, diff, log, rm, mv), never `git:*`.
- Proof beyond the unit tests: `KAHNBAN_LIVE=1 python -m pytest tests/live` with the flag should get a toy ticket past review.

## Validation
```
python -m pytest tests/test_harness_files.py -q
```

## Log
- 2026-10-25 18:50 - created -> 0-backlog | captured
- 2026-10-26 14:42 - ready gate passed -> 2-ready | contract 45e5c3958f8b8cb6
- 2026-10-26 14:42 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 14:43 - verify exit=1 in 201.9s (cwd=KB-010) (no transition)
    verifying ticket/KB-010 at 74a5a9942150; Running Tier 1 (Feature Tests): python -m pytest tests/test_harness_files.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_harness_files.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8]
    === TIER 1: FEATURE TESTS ===
    ..................................                                       [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_written
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_keep
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_include_the_board
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    FAILED tests/test_factory_run.py::test_skills_install_adds_agents_and_one_guard_hook
    706 tests, 8 workers, 189s, FAILURES

    full output: plans/tickets/.artifacts/KB-010-20261026-144351.log
- 2026-10-26 16:01 - abandoned (contract changes: permission rules become opt-in, which moves the work into cli.py and skills.py) | cleanup: worktree removal delayed by file lock; pruned metadata: KB-010; deleted branch: ticket/KB-010
- 2026-10-26 16:01 - manual move 3-in-progress -> 1-refining: contract rewritten: opt-in --allow-worker-commands flag (decided with the user)
- 2026-10-26 16:01 - ready gate passed -> 2-ready | contract 46f79f588a5ad81d
- 2026-10-26 16:01 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 16:03 - verify exit=0 in 204.3s (cwd=KB-010) -> 4-verifying
    verifying ticket/KB-010 at 42f7ae1eb794; Running Tier 1 (Feature Tests): python -m pytest tests/test_harness_files.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_harness_files.py -q] && [4/4 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 86a945720cb7]
    === TIER 1: FEATURE TESTS ===
    ...................................                                      [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_left
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_are_written
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_keep
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_harness_files.py -q -k claude_permissions_include_the_board
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    707 tests, 8 workers, 173s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    ...............................FFFF                                      [100%]
    ================================== FAILURES ===================================
    _ test_claude_permissions_are_written_for_kahnban_and_the_git_verbs_a_worker_needs _

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-407/test_claude_permissions_are_wr0')

        def test_claude_permissions_are_written_for_kahnban_and_the_git_verbs_a_worker_needs(tmp_path: Path) -> None:
            from kahnban.cli import main

    >       assert main(["--project-root", str(tmp_path), "skills", "install", "--harness", "claude", "--allow-worker-commands"]) == 0
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_harness_files.py:197: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\cli.py:1068: in main
        args = parser.parse_args(argv)
               ^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:1902: in parse_args
        self.error(msg)
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\argparse.py:2658: in error
        self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = ArgumentParser(prog='kahnban', usage=None, description='Portable agentic Kanban workflow engine', formatter_class=<class 'argparse.HelpFormatter'>, conflict_handler='error', add_help=True)
    status = 2
    message = 'kahnban: error: unrecognized arguments: --allow-worker-commands\n'

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
    kahnban: error: unrecognized arguments: --allow-worker-commands
    _ test_claude_permissions_keep_other_settings_and_rules_and_add_nothing_twice _

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-407/test_claude_permissions_keep_o0')

        def test_claude_permissions_keep_other_settings_and_rules_and_add_nothing_twice(tmp_path: Path) -> None:
            settings = tmp_path / ".claude" / "settings.json"
            settings.parent.mkdir()
            settings.write_text(
                json.dumps({"model": "haiku", "permissions": {"allow": ["Bash(npm test:*)", "Bash(kahnban:*)"], "deny": ["Bash(rm:*)"]}}),
                encoding="utf-8",
            )

    >       skills.install_skills(tmp_path, harness="claude", allow_worker_commands=True)
    E       TypeError: install_skills() got an unexpected keyword argument 'allow_worker_commands'

    tests\test_harness_files.py:213: TypeError
    ________ test_claude_permissions_include_the_boards_own_test_commands _________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-407/test_claude_permissions_includ0/scratch')

        def test_claude_permissions_include_the_boards_own_test_commands(repo: Path) -> None:
            from conftest import scaffold_board

            scaffold_board(repo, {"validation_command": "python -m pytest -q", "regression_command": "python tests/all.py"})

    >       skills.install_skills(repo, harness="claude", allow_worker_commands=True)
    E       TypeError: install_skills() got an unexpected keyword argument 'allow_worker_commands'

    tests\test_harness_files.py:229: TypeError
    _____ test_a_settings_file_that_is_not_json_is_left_alone_with_a_message ______

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-407/test_a_settings_file_that_is_n0')

        def test_a_settings_file_that_is_not_json_is_left_alone_with_a_message(tmp_path: Path) -> None:
            broken = tmp_path / "settings.json"
            broken.write_text("{nope", encoding="utf-8")
            messages: list[str] = []

    >       skills.merge_permissions(broken, ["Bash(kahnban:*)"], messages)
            ^^^^^^^^^^^^^^^^^^^^^^^^
    E       AttributeError: module 'kahnban.skills' has no attribute 'merge_permissions'

    tests\test_harness_files.py:240: AttributeError
    =========================== short test summary info ===========================
    FAILED tests/test_harness_files.py::test_claude_permissions_are_written_for_kahnban_and_the_git_verbs_a_worker_needs
    FAILED tests/test_harness_files.py::test_claude_permissions_keep_other_settings_and_rules_and_add_nothing_twice
    FAILED tests/test_harness_files.py::test_claude_permissions_include_the_boards_own_test_commands
    FAILED tests/test_harness_files.py::test_a_settings_file_that_is_not_json_is_left_alone_with_a_message

    full output: plans/tickets/.artifacts/KB-010-20261026-160336.log
- 2026-10-26 16:34 - abandoned (the settings.json rules are ignored by a headless worker (probe 2026-10-26); the flag writes the worker command instead) | cleanup: removed worktree: KB-010; deleted branch: ticket/KB-010