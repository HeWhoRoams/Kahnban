---
id: KB-006
title: "Tamper resistance for the frozen records: keep contract and approval records out of the workers' write access"
status: verifying
owner: claude-coder
branch: ticket/KB-006
worktree: .worktrees/KB-006
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
contract_hash: f8680312d43d6fe4
confirmed: ""
verified_sha: 5957e8e4c77098d5a266b65fc03d7ce8229a6927
reviewer: ""
approved_sha: ""
approval_sig: ""
integrated_sha: ""
---

## Problem
Approvals are signed with a key kept outside the repository, but the frozen contract is not: `contract_hash` is plain frontmatter, so a
worker that edits the acceptance criteria, blast radius or validation can write the matching hash too, and `verify_contract` passes.
Sign the hash at the same moments it is written (`ready`, and the freeze at `claim`) with the existing key, store it as `contract_sig`,
and check it wherever `verify_contract` runs. With `require_signed_approvals`, a hash without a signature is refused with the way out
(`move` back to refining, then `ready`). Limit, to be stated in the README: a worker running as the same OS user can still read the key
file, so this is a tripwire. Real isolation is a container or a separate OS user for workers, which is a deployment choice, not engine code.

## Acceptance criteria
- [x] `ready` stores `contract_sig`, an HMAC of the ticket id and contract hash made with the approval key (test: `python -m pytest tests/test_contract_signature.py -q -k ready_signs`)
- [x] a contract edited together with its `contract_hash` is refused at verify when the signature no longer matches (test: `python -m pytest tests/test_contract_signature.py -q -k forged_hash`)
- [x] with `require_signed_approvals`, a frozen contract with no signature is refused and the message names `ready`; without the setting it still passes (test: `python -m pytest tests/test_contract_signature.py -q -k unsigned_contract`)

## Blast radius
- `src/kahnban/trust.py`
- `src/kahnban/core.py`
- `tests/test_contract_signature.py`

## Implementation notes
- `trust.sign_contract(root, ticket_id, digest)` and `trust.contract_problem(root, ticket_id, digest, signature)`, built on `_key`.
- `core.ready` and the claim-time freeze add `contract_sig` next to `contract_hash`; `verify_contract` checks it (all five callers share it).
- Tests use `test_factory_gates` helpers (`factory_board`, `claimed`).
- After merge, outside the ticket: a README line on the limit and on isolating workers.

## Validation
```
python -m pytest tests/test_contract_signature.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 22:44 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 22:44 - ready gate passed -> 2-ready | contract f8680312d43d6fe4
- 2026-10-26 22:44 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 22:44 - verify exit=0 in 239.0s (cwd=KB-006) -> 4-verifying
    verifying ticket/KB-006 at 5957e8e4c770; Running Tier 1 (Feature Tests): python -m pytest tests/test_contract_signature.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_contract_signature.py -q] && [3/3 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 260f146c0b36]
    === TIER 1: FEATURE TESTS ===
    ...                                                                      [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_contract_signature.py -q -k ready_signs
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_contract_signature.py -q -k forged_hash
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_contract_signature.py -q -k unsigned_contract
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    718 tests, 8 workers, 194s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FFF                                                                      [100%]
    ================================== FAILURES ===================================
    ________________________ test_ready_signs_the_contract ________________________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-515/test_ready_signs_the_contract0/scratch')

        def test_ready_signs_the_contract(repo: Path) -> None:
            config = strict_board(repo)
            claimed(config)

            fields = fields_of(config)

    >       assert fields["contract_sig"]
                   ^^^^^^^^^^^^^^^^^^^^^^
    E       KeyError: 'contract_sig'

    tests\test_contract_signature.py:24: KeyError
    _______ test_a_forged_hash_beside_edited_criteria_is_refused_at_verify ________

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-515/test_a_forged_hash_beside_edit0/scratch')

        def test_a_forged_hash_beside_edited_criteria_is_refused_at_verify(repo: Path) -> None:
            config = strict_board(repo)
            tree = claimed(config)
            commit_work(tree, FIX)
            text = core.find_ticket(config, "TST-001").text
            edited = text.replace("## Validation", "## Validation\n# sneaked in", 1)
            forged = re.sub(r"contract_hash: .*", f"contract_hash: {core.contract_hash(frontmatter.parse(edited)[1])}", edited)
            edit_ticket(config, text, forged)

    >       with pytest.raises(core.GateError, match="signature"):
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    E       Failed: DID NOT RAISE <class 'kahnban.config.GateError'>

    tests\test_contract_signature.py:37: Failed
    ___ test_an_unsigned_contract_is_refused_only_when_signatures_are_required ____

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-515/test_an_unsigned_contract_is_r0/scratch')

        def test_an_unsigned_contract_is_refused_only_when_signatures_are_required(repo: Path) -> None:
            config = strict_board(repo, require_signed_approvals=True)
            tree = claimed(config)
            commit_work(tree, FIX)
            text = core.find_ticket(config, "TST-001").text
    >       edit_ticket(config, text, re.sub(r"contract_sig: .*\n", "", text))

    tests\test_contract_signature.py:46: 
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    tests\test_factory_gates.py:92: in edit_ticket
        git(config.project_root, "commit", "-m", "edit TST-001")
    tests\conftest.py:47: in git
        return gitops.run(repo, args)
               ^^^^^^^^^^^^^^^^^^^^^^
    _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    repo = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-515/test_an_unsigned_contract_is_r0/scratch')
    args = ('commit', '-m', 'edit TST-001')

        def run(
            repo: Path,
            args: Sequence[str],
            *,
            check: bool = True,
        ) -> subprocess.CompletedProcess[str]:
            """Run ``git <args>`` inside ``repo``.

            Raises :class:`GitError` on a non-zero exit unless ``check`` is false.
            """
            cmd = ["git", "-C", str(repo), *args]
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if check and completed.returncode != 0:
    >           raise GitError(cmd, completed.returncode, completed.stderr)
    E           kahnban.gitops.GitError: git command failed (exit 1): git -C C:\Users\User\AppData\Local\Temp\pytest-of-User\pytest-515\test_an_unsigned_contract_is_r0\scratch commit -m edit TST-001

    src\kahnban\gitops.py:50: GitError
    =========================== short test summary info ===========================
    FAILED tests/test_contract_signature.py::test_ready_signs_the_contract - KeyE...
    FAILED tests/test_contract_signature.py::test_a_forged_hash_beside_edited_criteria_is_refused_at_verify
    FAILED tests/test_contract_signature.py::test_an_unsigned_contract_is_refused_only_when_signatures_are_required

    full output: plans/tickets/.artifacts/KB-006-20261026-224458.log