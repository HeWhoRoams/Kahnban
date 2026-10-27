"""The frozen contract is sealed with the engine's key, so editing the hash next to the text no longer passes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kahnban import core, frontmatter
from test_factory_gates import FIX, claimed, commit_work, edit_ticket, strict_board


def fields_of(config: core.Config) -> dict:
    return frontmatter.parse(core.find_ticket(config, "TST-001").text)[0]


def test_ready_signs_the_contract(repo: Path) -> None:
    config = strict_board(repo)
    claimed(config)

    fields = fields_of(config)

    assert fields["contract_sig"]
    assert core.trust.contract_problem(config.project_root, "TST-001", fields["contract_hash"], fields["contract_sig"]) == ""


def test_a_forged_hash_beside_edited_criteria_is_refused_at_verify(repo: Path) -> None:
    config = strict_board(repo)
    tree = claimed(config)
    commit_work(tree, FIX)
    text = core.find_ticket(config, "TST-001").text
    edited = text.replace("## Validation", "## Validation\n# sneaked in", 1)
    forged = re.sub(r"contract_hash: .*", f"contract_hash: {core.contract_hash(frontmatter.parse(edited)[1])}", edited)
    edit_ticket(config, text, forged)

    with pytest.raises(core.GateError, match="signature"):
        core.verify(config, "TST-001")


def test_an_unsigned_contract_is_refused_only_when_signatures_are_required(repo: Path) -> None:
    config = strict_board(repo, require_signed_approvals=True)
    tree = claimed(config)
    commit_work(tree, FIX)
    text = core.find_ticket(config, "TST-001").text
    edit_ticket(config, text, re.sub(r"contract_sig: .*\n", "", text))

    with pytest.raises(core.GateError, match="unsigned"):
        core.verify(config, "TST-001")

    loose = core.load_config(repo)
    object.__setattr__(loose, "require_signed_approvals", False)
    assert core.verify(loose, "TST-001").passed
