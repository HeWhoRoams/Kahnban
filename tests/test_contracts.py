"""Structural checks: a command, tool or shipped file nobody tests turns this red."""

from __future__ import annotations

import argparse
import filecmp
import re
from pathlib import Path

import pytest

from kahnban import cli, mcp_server
from test_mcp_server import call, tool_payload

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent


def _subcommands(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    found: list[tuple[str, ...]] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found.append((*prefix, name))
                found.extend(_subcommands(sub, (*prefix, name)))
    return found


def _test_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in TESTS.glob("test_*.py")
        if path.name != Path(__file__).name
    )


def _argv_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\s*,\s*".join(f"[\"']{re.escape(word)}[\"']" for word in words))


# Gaps the contract tests found on 2026-10-25. Each is a test to write (self-test plan,
# step 3); delete the entry when it is written. An entry that gets tested fails below.
CLI_GAPS = {"reject", "lease", "spec new", "spec approve", "spec list", "handoff"}
MCP_GAPS = {
    "kanban_ticket_ready",
    "kanban_session_status",
    "kanban_session_update",
    "kanban_next",
    "kanban_ticket_approve",
    "kanban_ticket_reject",
    "kanban_ticket_lease",
    "kanban_ticket_escalate",
    "kanban_feedback",
}


def test_every_cli_command_appears_in_a_test() -> None:
    source = _test_source()
    untested = {
        " ".join(words)
        for words in _subcommands(cli.build_parser())
        if not _argv_pattern(words).search(source)
    }
    assert untested == CLI_GAPS, f"new gaps: {untested - CLI_GAPS}; now tested: {CLI_GAPS - untested}"


def test_mcp_registry_tables_agree() -> None:
    schemas = {schema["name"] for schema in mcp_server.TOOL_SCHEMAS}
    assert schemas == set(mcp_server.TOOLS) == set(mcp_server.TOOL_COMMANDS)


def test_every_mcp_tool_appears_in_a_test() -> None:
    source = _test_source()
    untested = {name for name in mcp_server.TOOLS if name not in source}
    assert untested == MCP_GAPS, f"new gaps: {untested - MCP_GAPS}; now tested: {MCP_GAPS - untested}"


@pytest.mark.parametrize("name", sorted(mcp_server.TOOLS))
def test_every_mcp_tool_answers_empty_arguments_without_crashing(board: Path, name: str) -> None:
    response = call(board, name, {})

    if "error" in response:
        assert response["error"]["code"] == mcp_server.INVALID_PARAMS, response
    else:
        assert isinstance(tool_payload(response), dict)


def test_adapter_skills_match_the_shipped_templates() -> None:
    adapters = ROOT / "adapters" / "skills"
    shipped = ROOT / "src" / "kahnban" / "templates" / "skills"

    def differences(cmp: filecmp.dircmp[str]) -> list[str]:
        found = [*cmp.left_only, *cmp.right_only, *cmp.diff_files, *cmp.funny_files]
        for name, sub in cmp.subdirs.items():
            found += [f"{name}/{item}" for item in differences(sub)]
        return found

    assert not differences(filecmp.dircmp(adapters, shipped))
