---
id: KB-012
title: "Reviewer registry: committed reviewer names so a missing key dir refuses, and a corrupt reviewer file gives a clear error"
status: verifying
owner: coder-agent
branch: ticket/KB-012
worktree: .worktrees/KB-012
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: [docs/remediation-plan-3.md]
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 2097b578f5077dac
contract_sig: 18b488248360049bef828dbbfa5059b61965d9e09ad517c7c24c40c820fcfe64
confirmed: ""
verified_sha: 497e92b090cfe5f17f516e59e1ea63741128ad55
reviewer: qa-reviewer
approved_sha: 497e92b090cfe5f17f516e59e1ea63741128ad55
approval_sig: 9f36591623ba86dc195a8d9939b9572311951c095056446f239324f8c953524a
reviewer_sig: ""
integrated_sha: 1091cbfd742ed1cf65bf5b49a9b6d37770c752e9
---

## Problem
## R2: Reviewer registry robustness (findings 5, 6)

Files: `src/kahnban/trust.py`, `src/kahnban/cli.py`, `tests/test_reviewer_keys.py`.

Decision needed (finding 5): the registry lives in the user key directory, so a checkout on another
machine sees no reviewers and the check silently turns off.

- Recommended: `reviewers add` also writes the reviewer's name (never the key) to a committed
  `plans/reviewers.json`. `reviewer_problem` treats a non-empty file as "reviewers required" and refuses
  with "reviewer 'X' has no key on this machine; run 'kahnban reviewers add X' here" when the key is missing.
  The name list is not secret, and a worker editing it can only make the gate stricter or remove it, which
  is the same tripwire limit as the rest of the trust model (document it).
- Alternative: a board setting `require_registered_reviewers`. Simpler, but one more flag to forget.

Corrupt reviewer file: `registered_reviewers` skips and reports an unreadable file as a `GateError` naming the
path, instead of a traceback.

Tests: a repo with `plans/reviewers.json` and an empty key dir refuses merge with the new message; a corrupt
json file gives a one-line refusal; the existing five tests keep passing.


Full context: docs/remediation-plan-3.md (code-review findings, 2026-10-29). Keep the blast radius to the files named above and write the tests first.

## Acceptance criteria
- [x] `kahnban reviewers add NAME` writes `NAME` (never the key), case-insensitively de-duplicated, into a committed `plans/reviewers.json`, in addition to the existing per-machine key it already creates (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add_writes_the_committed_registry`)
- [x] once `plans/reviewers.json` names a reviewer, that name being required carries over to a checkout with an empty local key directory: `core.approve`/`core.merge` for that reviewer refuse with `"reviewer 'NAME' has no key on this machine; run 'kahnban reviewers add NAME' here"` instead of silently treating no reviewers as registered (test: `python -m pytest tests/test_reviewer_keys.py -q -k committed_registry_without_a_local_key_refuses`)
- [x] a corrupt (unreadable/invalid-JSON) `plans/reviewers.json` makes `core.merge` refuse with a one-line `GateError` naming the path, not a traceback (test: `python -m pytest tests/test_reviewer_keys.py -q -k corrupt_reviewers_file_refuses_cleanly`)
- [x] the five existing reviewer-key tests keep passing unchanged (test: `python -m pytest tests/test_reviewer_keys.py -q`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/cli.py`
- `tests/test_reviewer_keys.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
```

## Log
- 2026-10-29 19:29 - created -> 0-backlog
- 2026-10-29 19:36 - ready gate passed -> 2-ready | contract 2097b578f5077dac
- 2026-10-29 20:24 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 20:35 - verify exit=1 in 30.9s (cwd=KB-012) (no transition)
    verifying ticket/KB-012 at 2439ef2d1918; Running Tier 1 (Feature Tests): python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
    $ python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8
    $ python -m pytest tests/test_reviewer_keys.py -q
    ......F.                                                                 [100%]
    ================================== FAILURES ===================================
    _____________ test_committed_registry_without_a_local_key_refuses _____________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-720/test_committed_registry_withou0/scratch')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001FDE8BDFA50>
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-720/test_committed_registry_withou0')

        def test_committed_registry_without_a_local_key_refuses(repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
            config = factory_board(repo)
            verified(config)
            cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
            core.approve(config, "TST-001", "alice")

            # a fresh checkout: the committed registry still names alice, but there is no local key for her
            monkeypatch.setenv("KAHNBAN_KEY_DIR", str(tmp_path / "elsewhere"))
            message = "reviewer 'alice' has no key on this machine; run 'kahnban reviewers add alice' here"

            with pytest.raises(core.GateError, match=message):
    >           core.approve(config, "TST-001", "alice")

    tests\test_reviewer_keys.py:118: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    src\kahnban\core.py:1044: in wrapper
        return gate(config, ticket_id, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    src\kahnban\core.py:2513: in approve
        verify_contract(config, ticket.ticket_id, fields, body)
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    config = Config(project_root=WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-720/test_committed_registry_wi..., max_stop_nudges=2, strict_hooks=False, autonomy='unattended', human_gates=('merge',), require_signed_approvals=False)
    ticket_id = 'TST-001'
    fields = {'approval_sig': '', 'approved_sha': 'd3ea7c69da5c873635caaa9214026bb7e4339819', 'blocked_on': '', 'branch': 'ticket/TST-001', ...}
    body = '\n## Problem\nSomething needs doing.\n\n## Acceptance criteria\n- [x] f() returns 2 (test: `C:\\Users\\User\\AppData\...output: plans/tickets/.artifacts/TST-001-20261029-203530.log\n- 2026-10-29 20:35 - approved by alice at d3ea7c69da5c\n'

        def verify_contract(
            config: Config, ticket_id: str, fields: Mapping[str, object], body: str
        ) -> bool:
            """False when nothing was frozen; raises when the contract changed after ready."""
            frozen = str(fields.get("contract_hash") or "").strip()
            if not frozen:
                return False
            if frozen != contract_hash(body):
                raise GateError(
                    f"{ticket_id}: acceptance criteria, blast radius or validation changed "
                    "after the ready gate froze them. Restore them, or move the ticket back "
                    f"with 'kahnban move {ticket_id} {config.refining_column} --reason <why>' "
                    "and re-run 'kahnban ready'."
                )
            signature = str(fields.get("contract_sig") or "").strip()
            if signature:
                problem = trust.contract_problem(config.project_root, ticket_id, frozen, signature)
            elif config.require_signed_approvals:
                problem = "the frozen contract is unsigned"
            else:
                return True
            if problem:
    >           raise GateError(
                    f"{ticket_id}: {problem}. Move the ticket back with "
                    f"'kahnban move {ticket_id} {config.refining_column} --reason <why>' and re-run 'kahnban ready'."
                )
    E           kahnban.config.GateError: TST-001: contract signature does not match its hash; the hash was edited or forged. Move the ticket back with 'kahnban move TST-001 1-refining --reason <why>' and re-run 'kahnban ready'.

    src\kahnban\core.py:487: GateError

    During handling of the above exception, another exception occurred:

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-720/test_committed_registry_withou0/scratch')
    monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001FDE8BDFA50>
    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-720/test_committed_registry_withou0')

        def test_committed_registry_without_a_local_key_refuses(repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
            config = factory_board(repo)
            verified(config)
            cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
            core.approve(config, "TST-001", "alice")

            # a fresh checkout: the committed registry still names alice, but there is no local key for her
            monkeypatch.setenv("KAHNBAN_KEY_DIR", str(tmp_path / "elsewhere"))
            message = "reviewer 'alice' has no key on this machine; run 'kahnban reviewers add alice' here"

    >       with pytest.raises(core.GateError, match=message):
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       AssertionError: Regex pattern did not match.
    E        Regex: "reviewer 'alice' has no key on this machine; run 'kahnban reviewers add alice' here"
    E        Input: "TST-001: contract signature does not match its hash; the hash was edited or forged. Move the ticket back with 'kahnban move TST-001 1-refining --reason <why>' and re-run 'kahnban ready'."

    tests\test_reviewer_keys.py:117: AssertionError
    ---------------------------- Captured stdout call -----------------------------
    [OK] registered reviewer 'alice'; 'kahnban approve' now needs a registered reviewer
    =========================== short test summary info ===========================
    FAILED tests/test_reviewer_keys.py::test_committed_registry_without_a_local_key_refuses

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-012-20261029-203512.log
- 2026-10-29 20:57 - verify exit=0 in 470.7s (cwd=KB-012) -> 4-verifying
    verifying ticket/KB-012 at 497e92b090cf; Running Tier 1 (Feature Tests): python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_reviewer_keys.py -q
python tests/run_parallel.py -j 8] && [4/4 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 4091e15a9abb]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_reviewer_keys.py -q
    ........                                                                 [100%]

    $ python tests/run_parallel.py -j 8
    736 tests, 8 workers, 179s, all passed


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add_writes_the_committed_registry
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k committed_registry_without_a_local_key_refuses
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q -k corrupt_reviewers_file_refuses_cleanly
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_reviewer_keys.py -q
    ........                                                                 [100%]


    === TIER 2: REGRESSION TESTS ===
    736 tests, 8 workers, 184s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_reviewer_keys.py -q
    .....FFF                                                                 [100%]
    ================================== FAILURES ===================================
    ______________ test_reviewers_add_writes_the_committed_registry _______________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-838/test_reviewers_add_writes_the_0/scratch')

        def test_reviewers_add_writes_the_committed_registry(repo: Path) -> None:
            factory_board(repo)
            root = ["--project-root", str(repo)]
            registry_path = repo / "plans" / "reviewers.json"

            assert cli.main(["reviewers", "add", "Tim Niles", *root]) == 0
    >       registry = json.loads(registry_path.read_text(encoding="utf-8"))
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    tests\test_reviewer_keys.py:98: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:546: in read_text
        return PathBase.read_text(self, encoding, errors, newline)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_abc.py:632: in read_text
        with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    self = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-838/test_reviewers_add_writes_the_0/scratch/plans/reviewers.json')
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
    E       FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\User\\AppData\\Local\\Temp\\pytest-of-User\\pytest-838\\test_reviewers_add_writes_the_0\\scratch\\plans\\reviewers.json'

    C:\Users\User\AppData\Local\Programs\Python\Python313\Lib\pathlib\_local.py:537: FileNotFoundError
    ---------------------------- Captured stdout call -----------------------------
    [OK] registered reviewer 'Tim Niles'; 'kahnban approve' now needs a registered reviewer
    _____________ test_committed_registry_without_a_local_key_refuses _____________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-838/test_committed_registry_withou0/scratch')

        def test_committed_registry_without_a_local_key_refuses(repo: Path) -> None:
            config = factory_board(repo)
            verified(config)
            cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
            core.approve(config, "TST-001", "alice")

            # a fresh checkout: the committed registry still names alice, but there is no local key for her
            # (only her key is gone; the engine's own signing key, which signed the frozen contract, stays put)
            trust._reviewer_file(config.project_root, "alice").unlink()
            message = "reviewer 'alice' has no key on this machine; run 'kahnban reviewers add alice' here"

    >       with pytest.raises(core.GateError, match=message):
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       Failed: DID NOT RAISE <class 'kahnban.config.GateError'>

    tests\test_reviewer_keys.py:120: Failed
    ---------------------------- Captured stdout call -----------------------------
    [OK] registered reviewer 'alice'; 'kahnban approve' now needs a registered reviewer
    _________________ test_corrupt_reviewers_file_refuses_cleanly _________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-838/test_corrupt_reviewers_file_re0/scratch')

        def test_corrupt_reviewers_file_refuses_cleanly(repo: Path) -> None:
            config = factory_board(repo)
            verified(config)
            core.approve(config, "TST-001", "alice")  # no registered reviewers yet, so this needs no signature

            (repo / "plans" / "reviewers.json").write_text("{not json", encoding="utf-8")

    >       with pytest.raises(core.GateError, match=r"plans/reviewers\.json is unreadable"):
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       Failed: DID NOT RAISE <class 'kahnban.config.GateError'>

    tests\test_reviewer_keys.py:133: Failed
    =========================== short test summary info ===========================
    FAILED tests/test_reviewer_keys.py::test_reviewers_add_writes_the_committed_registry
    FAILED tests/test_reviewer_keys.py::test_committed_registry_without_a_local_key_refuses
    FAILED tests/test_reviewer_keys.py::test_corrupt_reviewers_file_refuses_cleanly

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-012-20261029-205713.log
- 2026-10-29 21:06 - approved by qa-reviewer at 497e92b090cf
- 2026-10-29 21:06 - approval by qa-reviewer countersigned by the runner at 497e92b090cf
- 2026-10-29 21:06 - integrated into main | merge-commit: 1091cbfd742ed1cf65bf5b49a9b6d37770c752e9
    $ merge ticket/KB-012 onto main 35dc2c509eb9
    === INTEGRATION: FEATURE TESTS ===
    $ python -m pytest tests/test_reviewer_keys.py -q
    ........                                                                 [100%]

    $ python tests/run_parallel.py -j 8
    736 tests, 8 workers, 190s, all passed


    === INTEGRATION: REGRESSION TESTS ===
    736 tests, 8 workers, 184s, all passed

    full output: plans/tickets/.artifacts/KB-012-20261029-210619.log