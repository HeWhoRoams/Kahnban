---
id: KB-012
title: "Reviewer registry: committed reviewer names so a missing key dir refuses, and a corrupt reviewer file gives a clear error"
status: in-progress
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
- [ ] `kahnban reviewers add NAME` writes `NAME` (never the key), case-insensitively de-duplicated, into a committed `plans/reviewers.json`, in addition to the existing per-machine key it already creates (test: `python -m pytest tests/test_reviewer_keys.py -q -k reviewers_add_writes_the_committed_registry`)
- [ ] once `plans/reviewers.json` names a reviewer, that name being required carries over to a checkout with an empty local key directory: `core.approve`/`core.merge` for that reviewer refuse with `"reviewer 'NAME' has no key on this machine; run 'kahnban reviewers add NAME' here"` instead of silently treating no reviewers as registered (test: `python -m pytest tests/test_reviewer_keys.py -q -k committed_registry_without_a_local_key_refuses`)
- [ ] a corrupt (unreadable/invalid-JSON) `plans/reviewers.json` makes `core.merge` refuse with a one-line `GateError` naming the path, not a traceback (test: `python -m pytest tests/test_reviewer_keys.py -q -k corrupt_reviewers_file_refuses_cleanly`)
- [ ] the five existing reviewer-key tests keep passing unchanged (test: `python -m pytest tests/test_reviewer_keys.py -q`)

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