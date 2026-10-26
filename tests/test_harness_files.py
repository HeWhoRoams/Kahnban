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


def test_the_guard_sees_every_tool_call(tmp_path: Path) -> None:
    skills.install_skills(tmp_path, harness="all")

    claude = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "matcher" not in claude["hooks"]["PreToolUse"][0]
    gemini = json.loads((tmp_path / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    assert gemini["hooks"]["BeforeTool"][0]["matcher"] == ".*"


def test_installing_over_an_old_matcher_updates_it_and_keeps_the_users_hooks(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    old = {
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
                    "hooks": [
                        {"type": "command", "command": "kahnban guard"},
                        {"type": "command", "command": "echo mine"},
                    ],
                },
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "lint-shell"}]},
            ]
        },
    }
    settings.write_text(json.dumps(old), encoding="utf-8")
    skills.install_skills(tmp_path, harness="claude")
    (tmp_path / ".agents" / "skills.lock.json").unlink(missing_ok=True)

    assert "out-of-date matcher" not in "\n".join(skills_check.audit(tmp_path))
    data = json.loads(settings.read_text(encoding="utf-8"))
    first = data["hooks"]["PreToolUse"][0]
    assert "matcher" not in first and [h["command"] for h in first["hooks"]] == ["kahnban guard", "echo mine"]
    assert data["hooks"]["PreToolUse"][1]["hooks"][0]["command"] == "lint-shell" and data["theme"] == "dark"


def test_check_reports_an_installed_guard_that_still_filters_tools(tmp_path: Path) -> None:
    skills.install_skills(tmp_path, harness="all")
    settings = tmp_path / ".gemini" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["BeforeTool"][0]["matcher"] = "run_shell_command"
    settings.write_text(json.dumps(data), encoding="utf-8")

    assert any("out-of-date matcher" in problem for problem in skills_check.audit(tmp_path))


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "read_file", "grep_search", "list_directory", "read_many_files"])
def test_reads_of_the_signing_key_are_refused_under_every_harness_tool_name(tool: str, repo: Path) -> None:
    from kahnban import trust

    trust.sign(repo, trust.Approval("TST-001", "abc", "qa"))
    key = str(next(trust.key_dir().glob("*.key")))
    payload = {"tool_name": tool, "tool_input": {"file_path": key, "pattern": "x"}}

    assert "signing key" in (guard.decide(payload, {"KAHNBAN_ROLE": "coder"}) or "")


def test_check_notices_a_cursor_rule_that_is_not_kahnbans_and_hooks_left_without_agents(tmp_path: Path) -> None:
    import shutil

    skills.install_skills(tmp_path, harness="all")
    (tmp_path / ".cursor" / "rules" / "kanban.mdc").write_text("be nice\n", encoding="utf-8")
    shutil.rmtree(tmp_path / ".claude" / "agents")

    report = "\n".join(skills_check.audit(tmp_path))
    assert ".cursor/rules/kanban.mdc is not Kahnban's rule" in report
    assert ".claude/settings.json still runs the guard but .claude/agents/ is missing" in report


def test_cursors_follow_up_cap_follows_max_stop_nudges(repo: Path) -> None:
    from conftest import set_board_config, scaffold_board

    scaffold_board(repo)
    set_board_config(repo, max_stop_nudges=4)
    cursor = repo / ".cursor" / "hooks.json"

    skills.install_skills(repo, harness="cursor")
    assert json.loads(cursor.read_text(encoding="utf-8"))["hooks"]["stop"][0]["loop_limit"] == 4
    assert not any("out-of-date" in problem for problem in skills_check.audit(repo))

    set_board_config(repo, max_stop_nudges=3)
    assert any("out-of-date" in problem for problem in skills_check.audit(repo))  # the file still says 4
    skills.install_skills(repo, harness="cursor")
    assert json.loads(cursor.read_text(encoding="utf-8"))["hooks"]["stop"][0]["loop_limit"] == 3


# --- the worker command a headless Claude worker needs (opt-in) -----------------------------------


def workers_of(repo: Path) -> dict:
    return json.loads((repo / "plans" / "board.config.json").read_text(encoding="utf-8")).get("workers", {})


def test_worker_commands_are_left_alone_unless_asked(repo: Path) -> None:
    from conftest import scaffold_board

    scaffold_board(repo, {})
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    before = (repo / "plans" / "board.config.json").read_text(encoding="utf-8")

    skills.install_skills(repo, harness="claude")

    assert json.loads(settings.read_text(encoding="utf-8"))["permissions"] == {"allow": ["Bash(ls)"]}
    assert (repo / "plans" / "board.config.json").read_text(encoding="utf-8") == before


def test_worker_commands_are_written_for_kahnban_the_git_verbs_and_the_boards_test_commands(repo: Path) -> None:
    from conftest import scaffold_board
    from kahnban.cli import main

    scaffold_board(repo, {"validation_command": "python -m pytest -q", "regression_command": "python tests/all.py"})

    assert main(["--project-root", str(repo), "skills", "install", "--harness", "claude", "--allow-worker-commands"]) == 0

    command = workers_of(repo)["default"]
    assert command.startswith("claude -p --agent kahnban-{role} --permission-mode acceptEdits --allowedTools ")
    for rule in ("Bash(kahnban:*)", "Bash(git add:*)", "Bash(git commit:*)", "Bash(python -m pytest -q:*)", "Bash(python tests/all.py:*)"):
        assert f'"{rule}"' in command
    assert "git push" not in command and "Bash(git:*)" not in command


def test_worker_commands_keep_a_workers_entry_that_is_already_there(repo: Path) -> None:
    from conftest import scaffold_board

    scaffold_board(repo, {"workers": {"default": "my-own-agent --role {role}"}})

    result = skills.install_skills(repo, harness="claude", allow_worker_commands=True)

    assert workers_of(repo) == {"default": "my-own-agent --role {role}"}
    assert any("already has workers" in m for m in result["messages"])


def test_worker_commands_without_a_board_write_nothing_and_print_the_command(tmp_path: Path) -> None:
    result = skills.install_skills(tmp_path, harness="claude", allow_worker_commands=True)

    assert not (tmp_path / "plans").exists()
    assert any("No board here yet" in m and "--allowedTools" in m for m in result["messages"])
    assert "permissions" not in json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))


def test_a_board_test_command_with_a_quote_is_left_out_of_the_command(repo: Path) -> None:
    from conftest import scaffold_board

    scaffold_board(repo, {"validation_command": 'python -c "print(1)"'})

    assert not [t for t in skills.allowed_tools(repo) if "print" in t]
