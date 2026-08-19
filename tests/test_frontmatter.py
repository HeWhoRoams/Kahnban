from __future__ import annotations

import pytest

from kahnban.frontmatter import FrontmatterError, append_log, mutate, parse, serialize


TICKET = """---
id: HOA-007
title: "Targeting: accuracy curve"
owner: unassigned
branch: ""
design_docs:
  - plans/GUIDANCE.md
depends_on: [HOA-001, "HOA-002"]
---

## Problem
Body status: backlog must remain unchanged.
"""


def test_parse_normalizes_crlf_and_supports_documented_values() -> None:
    frontmatter, body = parse(TICKET.replace("\n", "\r\n"))

    assert frontmatter == {
        "id": "HOA-007",
        "title": "Targeting: accuracy curve",
        "owner": "unassigned",
        "branch": "",
        "design_docs": ["plans/GUIDANCE.md"],
        "depends_on": ["HOA-001", "HOA-002"],
    }
    assert "\r" not in body


def test_canonical_serialization_is_semantically_stable() -> None:
    frontmatter, body = parse(TICKET)
    rendered = serialize(frontmatter, body)

    assert parse(rendered) == (frontmatter, body)
    reparsed_frontmatter, reparsed_body = parse(rendered)
    assert serialize(reparsed_frontmatter, reparsed_body) == rendered


def test_quoted_commas_and_escapes_round_trip() -> None:
    text = '---\nvalues: ["a,b", "say \\"hello\\""]\n---\nbody\n'

    frontmatter, body = parse(text)
    rendered = serialize(frontmatter, body)

    assert frontmatter["values"] == ["a,b", 'say "hello"']
    assert parse(rendered) == (frontmatter, body)


def test_empty_frontmatter_is_supported() -> None:
    assert parse("---\n---\nbody\n") == ({}, "body\n")


def test_mutate_only_changes_frontmatter() -> None:
    updated = mutate(TICKET, {"owner": "copilot"})

    frontmatter, body = parse(updated)
    assert frontmatter["owner"] == "copilot"
    assert "Body status: backlog must remain unchanged." in body


def test_append_log_places_entry_before_next_section() -> None:
    ticket = TICKET + "\n## Log\n- created\n\n## Notes\nKeep me.\n"

    updated = append_log(ticket, "- claimed")

    assert "## Log\n- created\n- claimed\n\n## Notes" in updated


@pytest.mark.parametrize(
    "text, message",
    [
        ("id: HOA-007\n", "must begin"),
        ("---\nid: HOA-007\n", "closing delimiter"),
        ("---\n  nested: value\n---\n", "nested mappings"),
        ("---\nid: one\nid: two\n---\n", "duplicate key"),
    ],
)
def test_invalid_frontmatter_is_rejected(text: str, message: str) -> None:
    with pytest.raises(FrontmatterError, match=message):
        parse(text)