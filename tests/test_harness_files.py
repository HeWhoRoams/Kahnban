"""What each harness is handed: golden agent files, installed hooks, and one answer from every payload shape."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kahnban import guard, roles, skills, skills_check

GOLDEN = Path(__file__).parent / "golden" / "agents"
HARNESSES = ("claude", "gemini", "cursor")


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("role", roles.workers())
def test_agent_files_match_the_golden_copy(harness: str, role: str) -> None:
    """A change to roles.json shows up here as a reviewable diff of what each harness will read.

    Refresh with KAHNBAN_UPDATE_GOLDEN=1 after meaning to change the wording.
    """
    golden = GOLDEN / harness / f"{roles.agent_name(role)}.md"
    text = roles.agent_markdown(role, harness)
    if os.environ.get("KAHNBAN_UPDATE_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(text, encoding="utf-8", newline="\n")
    assert golden.is_file(), f"{golden} is missing; run with KAHNBAN_UPDATE_GOLDEN=1"
    assert text == golden.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_installed_agent_files_equal_the_golden_copy(tmp_path: Path) -> None:
    skills.install_skills(tmp_path, harness="all")

    for harness in HARNESSES:
        for role in roles.workers():
            written = tmp_path / f".{harness}" / "agents" / f"{roles.agent_name(role)}.md"
            golden = GOLDEN / harness / written.name
            assert written.read_text(encoding="utf-8").replace("\r\n", "\n") == golden.read_text(
                encoding="utf-8"
            ).replace("\r\n", "\n")


def test_check_notices_a_harness_whose_guard_hooks_are_gone(tmp_path: Path) -> None:
    skills.install_skills(tmp_path, harness="all")
    assert skills_check.audit(tmp_path) == []

    claude = tmp_path / ".claude" / "settings.json"
    data = json.loads(claude.read_text(encoding="utf-8"))
    del data["hooks"]["Stop"]
    claude.write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / ".gemini" / "settings.json").unlink()
    cursor = tmp_path / ".cursor" / "hooks.json"
    data = json.loads(cursor.read_text(encoding="utf-8"))
    data["hooks"]["beforeShellExecution"] = []
    cursor.write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / ".cursor" / "rules" / "kanban.mdc").unlink()

    report = "\n".join(skills_check.audit(tmp_path))
    assert ".claude/settings.json has no Stop hook running 'kahnban guard --stop'" in report
    assert ".gemini/settings.json is missing or not valid JSON" in report
    assert ".cursor/hooks.json has no beforeShellExecution hook running 'kahnban guard'" in report
    assert ".cursor/rules/kanban.mdc is missing" in report


FORBIDDEN_CLAIM = "kahnban claim TST-001"
PAYLOADS = {
    "claude": {"tool_name": "Bash", "tool_input": {"command": FORBIDDEN_CLAIM}},
    "gemini": {"tool_name": "run_shell_command", "tool_input": {"command": FORBIDDEN_CLAIM}, "hook_event_name": "BeforeTool"},
    "cursor preToolUse": {"tool_name": "Shell", "tool_input": {"command": FORBIDDEN_CLAIM}, "hook_event_name": "preToolUse"},
    "cursor beforeShellExecution": {"command": FORBIDDEN_CLAIM, "cwd": ".", "hook_event_name": "beforeShellExecution"},
}


@pytest.mark.parametrize("name", PAYLOADS)
def test_every_harness_payload_gets_the_same_decision(name: str) -> None:
    decisions = {
        guard.decide(PAYLOADS[name], {"KAHNBAN_ROLE": "qa_reviewer"}),
        guard.decide(PAYLOADS["claude"], {"KAHNBAN_ROLE": "qa_reviewer"}),
    }
    assert len(decisions) == 1 and "not a qa_reviewer's" in decisions.pop()
