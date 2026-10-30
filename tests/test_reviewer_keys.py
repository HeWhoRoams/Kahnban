"""Registered reviewers: once any exists, only they can approve, and their seal is checked at merge and done."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from kahnban import cli, core, frontmatter, trust
from conftest import git
from test_factory_gates import factory_board, verified


@pytest.fixture(autouse=True)
def isolated_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAHNBAN_KEY_DIR", str(tmp_path / "keys"))
    # a reviewer registers and approves as a human, not whatever role happens to run this suite
    monkeypatch.delenv("KAHNBAN_ROLE", raising=False)


def fields_of(config: core.Config) -> dict:
    return frontmatter.parse(core.find_ticket(config, "TST-001").text)[0]


def test_reviewers_add_registers_once_and_list_shows_the_names(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    factory_board(repo)
    root = ["--project-root", str(repo)]

    assert cli.main(["reviewers", "list", *root]) == 0
    assert "No reviewers registered" in capsys.readouterr().out
    assert cli.main(["reviewers", "add", "Tim Niles", *root]) == 0
    assert cli.main(["reviewers", "add", "tim niles", *root]) != 0  # the same person, any case
    assert cli.main(["reviewers", "list", *root]) == 0

    assert "Tim Niles" in capsys.readouterr().out


def test_an_unregistered_name_cannot_approve_once_a_registered_reviewer_exists(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])

    with pytest.raises(core.GateError, match="not registered"):
        core.approve(config, "TST-001", "mallory")

    core.approve(config, "TST-001", "alice")
    assert len(str(fields_of(config)["reviewer_sig"])) == 64


def test_a_project_with_no_registered_reviewer_behaves_as_before(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)

    core.approve(config, "TST-001", "anyone")

    assert not fields_of(config).get("reviewer_sig")
    assert core.merge(config, "TST-001").passed


def test_an_edited_or_removed_reviewer_sig_is_refused_at_merge(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
    core.approve(config, "TST-001", "alice")
    ticket = core.find_ticket(config, "TST-001")
    honest = ticket.text
    sig = str(fields_of(config)["reviewer_sig"])

    for tampered in (honest.replace(sig, "0" * 64), honest.replace(f"reviewer_sig: {sig}\n", "")):
        ticket.path.write_text(tampered, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "tamper")
        with pytest.raises(core.GateError, match="reviewer signature|no reviewer signature"):
            core.merge(config, "TST-001")
        ticket.path.write_text(honest, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "restore")

    assert core.merge(config, "TST-001").passed


def test_a_worker_cannot_register_a_reviewer(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    factory_board(repo)
    monkeypatch.setenv("KAHNBAN_ROLE", "coder")

    assert cli.main(["reviewers", "add", "mallory", "--project-root", str(repo)]) != 0
    monkeypatch.delenv("KAHNBAN_ROLE")
    assert cli.main(["reviewers", "list", "--project-root", str(repo)]) == 0


def test_reviewers_add_writes_the_committed_registry(repo: Path) -> None:
    factory_board(repo)
    root = ["--project-root", str(repo)]
    registry_path = repo / "plans" / "reviewers.json"

    assert cli.main(["reviewers", "add", "Tim Niles", *root]) == 0
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["names"] == ["Tim Niles"]
    assert "key" not in json.dumps(registry)  # the name, never the key

    assert cli.main(["reviewers", "add", "tim niles", *root]) != 0  # the same person, any case
    assert json.loads(registry_path.read_text(encoding="utf-8"))["names"] == ["Tim Niles"]  # not duplicated

    assert cli.main(["reviewers", "add", "Bob", *root]) == 0
    assert sorted(json.loads(registry_path.read_text(encoding="utf-8"))["names"]) == ["Bob", "Tim Niles"]


def test_committed_registry_without_a_local_key_refuses(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
    core.approve(config, "TST-001", "alice")

    # a fresh checkout: the committed registry still names alice, but there is no local key for her
    # (only her key is gone; the engine's own signing key, which signed the frozen contract, stays put)
    trust._reviewer_file(config.project_root, "alice").unlink()
    message = "reviewer 'alice' has no key on this machine; run 'kahnban reviewers add alice' here"

    with pytest.raises(core.GateError, match=message):
        core.approve(config, "TST-001", "alice")
    with pytest.raises(core.GateError, match=message):
        core.merge(config, "TST-001")


def test_corrupt_reviewers_file_refuses_cleanly(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    core.approve(config, "TST-001", "alice")  # no registered reviewers yet, so this needs no signature

    (repo / "plans" / "reviewers.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(core.GateError, match=r"plans/reviewers\.json is unreadable"):
        core.merge(config, "TST-001")


APPROVAL_FIELD_NAMES = {"reviewer", "approved_sha", "approval_sig", "reviewer_sig", "integrated_sha", "confirmed"}


def test_approval_fields_mapping_is_shared() -> None:
    # One module-level mapping, not two duplicated dict literals in verify() and reject().
    assert core._APPROVAL_FIELDS == {name: "" for name in APPROVAL_FIELD_NAMES}
    # verified_sha is deliberately excluded: verify and reject disagree on its value.
    assert "verified_sha" not in core._APPROVAL_FIELDS

    verify_source = inspect.getsource(core.verify)
    reject_source = inspect.getsource(core.reject)
    assert "_APPROVAL_FIELDS" in verify_source
    assert "_APPROVAL_FIELDS" in reject_source
    # no duplicated dict literal spelling out every field by hand in either function
    for name in APPROVAL_FIELD_NAMES:
        assert f'"{name}": ""' not in verify_source
        assert f'"{name}": ""' not in reject_source


def test_approval_fields_are_cleared_the_same_way_by_verify_and_reject(repo: Path) -> None:
    config = factory_board(repo)
    verified(config)
    cli.main(["reviewers", "add", "alice", "--project-root", str(repo)])
    core.approve(config, "TST-001", "alice")
    assert core.merge(config, "TST-001").passed
    fields = fields_of(config)
    assert all(fields.get(name) for name in APPROVAL_FIELD_NAMES - {"confirmed"})

    core.reject(config, "TST-001", "bob", "needs more work")
    fields = fields_of(config)
    assert all(not fields.get(name) for name in APPROVAL_FIELD_NAMES)


def test_approval_problem_checks_hmac_and_seal() -> None:
    assert not hasattr(core, "_signature_problem")
    docstring = core._approval_problem.__doc__ or ""
    assert "HMAC" in docstring
    assert "reviewer seal" in docstring
