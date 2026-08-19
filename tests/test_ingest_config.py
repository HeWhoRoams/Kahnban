"""Adopters tune ingestion through board.config.json, not engine code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kahnban import core, frontmatter, ingest
from conftest import git

PLAN = """# Programme

## Warm the cache
Rationale: cold starts are slow.
Tests to add:
```
git --version
```
Touched files: `src/cache.py`

## Evict entries
Rationale: memory grows.
Touched files: `src/evict.py`
"""


def configure(board: Path, **ingest_settings: object) -> core.Config:
    path = board / "plans" / "board.config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ingest"] = ingest_settings
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    git(board, "add", "-A")
    git(board, "commit", "-m", "configure ingest")
    return core.load_config(board)


def write_plan(board: Path, text: str = PLAN) -> Path:
    path = board / "plans" / "PLAN.md"
    path.write_text(text, encoding="utf-8", newline="\n")
    git(board, "add", "-A")
    git(board, "commit", "-m", "add plan")
    return path


def test_configured_aliases_extend_the_defaults(board: Path) -> None:
    config = configure(
        board,
        section_aliases={
            "validation": ["tests to add"],
            "blast_radius": ["touched files"],
        },
    )
    plan = write_plan(board)

    [report] = ingest.ingest(config, [plan], options=ingest.options_for(config))

    ticket = core.find_ticket(config, "TST-001")
    _, body = frontmatter.parse(ticket.text)
    assert core.parse_blast_radius(body) == ["src/cache.py"]
    assert core.validation_command(config, body) == "git --version"
    # A default alias still works alongside the configured ones.
    assert "cold starts are slow" in core.section(body, "Problem")
    assert len(report.created) == 2


def test_unconfigured_vocabulary_is_left_in_the_body(board: Path) -> None:
    config = core.load_config(board)
    plan = write_plan(board)

    ingest.ingest(config, [plan], options=ingest.options_for(config))

    _, body = frontmatter.parse(core.find_ticket(config, "TST-001").text)
    # Nothing is invented: the unknown labels stay as prose, and the gate refuses.
    assert core.parse_blast_radius(body) == []
    assert "Touched files" in body
    core.move(config, "TST-001", "1-refining", reason="refining")
    with pytest.raises(core.GateError, match="Blast radius"):
        core.ready(config, "TST-001")


def test_configured_heading_level_is_the_default(board: Path) -> None:
    config = configure(board, heading_level=1)
    plan = write_plan(board)

    ingest.ingest(config, [plan], options=ingest.options_for(config))

    assert [t.ticket_id for t in core.iter_tickets(config)] == ["TST-001"]
    assert frontmatter.parse(core.find_ticket(config, "TST-001").text)[0]["title"] == (
        "Programme"
    )


def test_explicit_heading_level_overrides_the_configured_one(board: Path) -> None:
    config = configure(board, heading_level=1)
    plan = write_plan(board)

    ingest.ingest(
        config, [plan], options=ingest.options_for(config, heading_level=2)
    )

    assert len(core.iter_tickets(config)) == 2


def test_unknown_alias_field_is_rejected_with_the_valid_names(board: Path) -> None:
    config = configure(board, section_aliases={"not_a_field": ["x"]})

    with pytest.raises(ingest.IngestError, match="unknown ingest alias field"):
        ingest.options_for(config)


def test_malformed_alias_block_is_rejected(board: Path) -> None:
    config = configure(board, section_aliases=["acceptance"])

    with pytest.raises(ingest.IngestError, match="must be an object"):
        ingest.options_for(config)


def test_init_writes_an_ingest_block(tmp_path: Path) -> None:
    from conftest import init_repo

    repo = init_repo(tmp_path / "adopter")
    core.init_board(repo, prefix="ADO")

    payload = json.loads(
        (repo / "plans" / "board.config.json").read_text(encoding="utf-8")
    )
    assert "ingest" in payload
    assert payload["ingest"]["section_aliases"] == {}
    config = core.load_config(repo)
    assert ingest.options_for(config).heading_level is None
