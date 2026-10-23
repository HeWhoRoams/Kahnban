"""The factory loop: leases, escalation, `kahnban run`, the role guard, the allowlist."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from kahnban import core, dispatcher, frontmatter, guard, learnings, linter, mcp_server, runner, skills
from kahnban.cli import main
from conftest import git, write_ticket
from test_factory_gates import CHECK, CHECK_APP, CRITERION, PY, claimed, factory_board, strict_board

WORKER = """\
import os, subprocess, sys
role = os.environ["KAHNBAN_ROLE"]
ticket = os.environ["KAHNBAN_TICKET"]
root = os.environ["KAHNBAN_PROJECT_ROOT"]
sys.stdin.read()
if role == "coder":
    with open("src/app.py", "w") as handle:
        handle.write("def f():\\n    return 2\\n")
    os.makedirs("tests", exist_ok=True)
    with open("tests/check_app.py", "w") as handle:
        handle.write({check_app!r})
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "fix f"], check=True)
elif role == "qa_reviewer":
    subprocess.run(
        [sys.executable, "-m", "kahnban", "--project-root", root,
         "approve", ticket, "--reviewer", "qa-bot"],
        check=True,
    )
print(role, "finished")
"""


def ready_ticket(config: core.Config) -> None:
    write_ticket(config.board_path, "1-refining", "TST-001", "fix", acceptance=(CRITERION,),
                 blast_radius=("src/app.py", "tests/check_app.py"), validation=CHECK)
    git(config.project_root, "add", "-A")
    git(config.project_root, "commit", "-m", "refine TST-001")
    core.ready(config, "TST-001")


def fields_of(config: core.Config, ticket_id: str = "TST-001") -> dict:
    return frontmatter.parse(core.find_ticket(config, ticket_id).text)[0]


# --- leases (probe I) ----------------------------------------------------------


def test_a_leased_ticket_is_not_handed_to_a_second_coder(repo: Path) -> None:
    config = strict_board(repo)
    claimed(config)

    assert core.live_lease(config, "TST-001") == "coder"
    assert dispatcher.resolve_next_action(config).action == "idle"
    with pytest.raises(core.GateError, match="leased by 'coder'"):
        core.lease(config, "TST-001", "other")

    core.write_lease(config, "TST-001", "coder", minutes=-1)  # the holder went quiet

    assert dispatcher.resolve_next_action(config).ticket_id == "TST-001"
    core.lease(config, "TST-001", "other")
    assert fields_of(config)["owner"] == "other"
    assert "taken over by other from coder" in core.section(
        frontmatter.parse(core.find_ticket(config, "TST-001").text)[1], "Log"
    )


# --- escalation ------------------------------------------------------------------


def test_an_escalated_ticket_waits_for_a_human(repo: Path) -> None:
    config = strict_board(repo)
    ready_ticket(config)

    core.escalate(config, "TST-001", "which currency?")

    assert fields_of(config)["blocked_on"] == "human: which currency?"
    assert dispatcher.resolve_next_action(config).action == "idle"
    core.unblock(config, "TST-001", "use EUR")
    assert dispatcher.resolve_next_action(config).action == "claim_and_implement"


# --- kahnban run -------------------------------------------------------------------


def test_run_takes_a_ready_ticket_all_the_way_to_done(repo: Path, tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER.format(check_app=CHECK_APP), encoding="utf-8")
    config = factory_board(repo, workers={"default": f"{PY} {worker}"})
    ready_ticket(config)

    result = runner.run(config, max_steps=10, echo=lambda line: None)

    assert [step.action for step in result.steps] == [
        "claim_and_implement",
        "review_and_gate",
        "merge_and_close",
    ], [step.outcome for step in result.steps]
    assert core.find_ticket(config, "TST-001").column == "5-done"
    assert fields_of(config)["reviewer"] == "qa-bot"
    log = core.section(frontmatter.parse(core.find_ticket(config, "TST-001").text)[1], "Log")
    assert f"done gate passed -> 5-done | merge-commit: {fields_of(config)['integrated_sha']}" in log
    assert not (repo / ".worktrees" / "TST-001").exists()
    assert not core.branch_tip(config, "ticket/TST-001")
    assert (repo / "src" / "app.py").read_text(encoding="utf-8").strip().endswith("return 2")
    assert "coder finished" in result.log_path.read_text(encoding="utf-8")
    metrics = json.loads((repo / "plans" / "status.json").read_text(encoding="utf-8"))["metrics"]
    assert metrics["tickets"]["TST-001"]["verify_attempts"] == 1
    assert (metrics["done"], metrics["first_pass_yield"]) == (1, 1.0)


def test_run_escalates_a_ticket_that_makes_no_progress(repo: Path) -> None:
    idle_worker = f'{PY} -c "import sys; sys.stdin.read()"'
    config = strict_board(repo, workers={"default": idle_worker}, max_attempts=2)
    ready_ticket(config)

    result = runner.run(config, max_steps=10, echo=lambda line: None)

    assert result.steps[-1].outcome.startswith("escalated")
    assert str(fields_of(config)["blocked_on"]).startswith("human:")
    assert "wait for a human" in result.stopped
    assert result.parked and result.parked[0].startswith("TST-001")


def test_run_kills_a_worker_that_overruns_its_timeout(repo: Path) -> None:
    config = strict_board(
        repo, workers={"default": f'{PY} -c "import time; time.sleep(60)"'}, worker_timeout_sec=2
    )
    ready_ticket(config)
    started = time.monotonic()

    result = runner.run(config, max_steps=1, echo=lambda line: None)

    assert "timed out" in result.steps[0].outcome
    assert time.monotonic() - started < 30
    assert core.live_lease(config, "TST-001") == ""


def test_a_failing_worker_command_stops_the_run_without_blaming_the_ticket(repo: Path) -> None:
    # What the live smoke test hit: the CLI's login had expired, every worker exited 1.
    broken = f"{PY} -c \"import sys; sys.stdin.read(); print('Failed to authenticate'); sys.exit(1)\""
    config = strict_board(repo, workers={"default": broken})
    ready_ticket(config)

    with pytest.raises(runner.RunStop, match="exited 1") as error:
        runner.run(config, echo=lambda line: None)

    assert "Failed to authenticate" in str(error.value)
    assert not str(fields_of(config).get("blocked_on") or "")
    assert core.live_lease(config, "TST-001") == ""


def test_run_refuses_to_start_without_a_worker(repo: Path) -> None:
    config = strict_board(repo)
    ready_ticket(config)

    with pytest.raises(runner.RunStop, match="no worker command"):
        runner.run(config, echo=lambda line: None)

    assert core.find_ticket(config, "TST-001").column == "2-ready"


# --- kahnban guard -------------------------------------------------------------


def test_guard_keeps_a_coder_inside_its_worktree_and_blast_radius(repo: Path) -> None:
    config = strict_board(repo)
    tree = claimed(config)
    env = {
        "KAHNBAN_ROLE": "coder",
        "KAHNBAN_TICKET": "TST-001",
        "KAHNBAN_PROJECT_ROOT": str(repo),
        "KAHNBAN_WORKTREE": str(tree),
    }

    def edit(path: Path) -> str | None:
        return guard.decide({"tool_name": "Write", "tool_input": {"file_path": str(path)}}, env)

    def bash(command: str, role: str = "coder") -> str | None:
        return guard.decide(
            {"tool_name": "Bash", "tool_input": {"command": command}}, {**env, "KAHNBAN_ROLE": role}
        )

    assert edit(tree / "src" / "app.py") is None
    assert "blast radius" in edit(tree / "README.md")
    assert "board files" in edit(tree / "plans" / "tickets" / "x.md")
    assert "outside your worktree" in edit(repo / "src" / "app.py")
    assert bash(f"{PY} -m pytest -q") is None
    assert "not a coder's" in bash("kahnban --project-root . done TST-001")
    assert "not a coder's" in bash(f"{PY} -m kahnban approve TST-001 --reviewer x")
    assert "runner's job" in bash("git push origin main")
    assert "override" in bash("kahnban verify TST-001 --force-scope --reason x")
    assert bash("kahnban escalate TST-001 --reason 'needs a decision'") is None
    assert bash("kahnban approve TST-001 --reviewer q", "qa_reviewer") is None
    assert "does not commit" in bash("git commit -m x", "qa_reviewer")
    assert "does not edit" in guard.decide(
        {"tool_name": "Edit", "tool_input": {"file_path": str(tree / "src" / "app.py")}},
        {**env, "KAHNBAN_ROLE": "qa_reviewer"},
    )
    assert guard.decide({"tool_name": "Bash", "tool_input": {"command": "git push"}}, {}) is None


def test_the_engine_holds_a_worker_to_its_role_on_every_surface(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The Claude Code hook covers one harness; the engine itself covers the rest.
    config = strict_board(repo)
    claimed(config)
    monkeypatch.setenv("KAHNBAN_ROLE", "coder")

    assert main(["--project-root", str(repo), "done", "TST-001"]) == 1
    assert "not a coder's to run" in capsys.readouterr().err
    assert main(["--project-root", str(repo), "status"]) == 0

    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "kanban_ticket_merge", "arguments": {"ticket_id": "TST-001"}}}
    out = io.StringIO()
    mcp_server.Server(repo, stdin=io.StringIO(json.dumps(request) + "\n"), stdout=out).serve_forever()
    reply = json.loads(out.getvalue().splitlines()[0])["result"]
    assert reply["isError"] and "not a coder's to run" in reply["content"][0]["text"]

    hook = {"tool_name": "Bash", "tool_input": {"command": "kahnban done TST-001"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook)))
    assert main(["guard"]) == 2  # the hook itself still runs with the role set


def test_skills_install_adds_agents_and_one_guard_hook(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")

    skills.install_skills(tmp_path, harness="claude")
    skills.install_skills(tmp_path, harness="claude")

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    commands = [h["command"] for e in data["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert commands == ["kahnban guard"]
    for role in ("coder", "qa-reviewer", "spec-analyst", "curator"):
        assert (tmp_path / ".claude" / "agents" / f"kahnban-{role}.md").is_file()


def test_the_vscode_mcp_config_starts_a_working_server(tmp_path: Path) -> None:
    # Audit probe K: this config used to run 'python -m kahnban mcp', which is no command.
    assert main(["--project-root", str(tmp_path), "skills", "install", "--harness", "vscode"]) == 0
    server = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    entry = server["servers"]["kahnban"]
    args = [arg.replace("${workspaceFolder}", str(tmp_path)) for arg in entry["args"]]
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

    reply = subprocess.run(
        [sys.executable, *args], input=json.dumps(request) + "\n",
        capture_output=True, text=True, timeout=60,
    )

    assert entry["type"] == "stdio"
    assert json.loads(reply.stdout.splitlines()[0])["result"]["serverInfo"]


# --- recurring learnings get a curator before new work ---------------------------


def recur(repo: Path, times: int) -> None:
    for _ in range(times):
        learnings.capture_learning(
            repo, title="Tests read the wall clock", problem="flaky", category="testing"
        )


def test_a_recurring_learning_is_curated_before_new_claims(repo: Path) -> None:
    config = strict_board(repo)
    ready_ticket(config)
    recur(repo, 1)
    assert dispatcher.resolve_next_action(config).action == "claim_and_implement"

    recur(repo, 1)  # it happened again

    assert dispatcher.resolve_next_action(config).action == "harvest_learnings"
    assert dispatcher.resolve_next_action(config, skip_harvest=True).action == "claim_and_implement"


def test_run_gives_the_curator_one_turn_then_moves_on(repo: Path) -> None:
    config = strict_board(repo, workers={"default": f'{PY} -c "import sys; sys.stdin.read()"'})
    recur(repo, 2)

    result = runner.run(config, max_steps=5, echo=lambda line: None)

    assert [step.action for step in result.steps] == ["harvest_learnings"]
    assert result.steps[0].outcome == "curator turn finished (exit 0)"
    assert "idle" in result.stopped.lower()


# --- metrics and stale claims ------------------------------------------------------


def test_log_metrics_count_attempts_rejections_and_cycle_time() -> None:
    log = "\n".join([
        "- 2026-10-01 09:00 - created -> 0-backlog",
        "- 2026-10-01 10:00 - verify exit=1 in 2.0s (cwd=TST-001) (no transition)",
        "    $ pytest",
        "- 2026-10-01 11:00 - verify exit=0 in 2.0s (cwd=TST-001) -> 4-verifying",
        "- 2026-10-01 12:00 - rejected by qa:",
        "    cover the overflow case",
        "- 2026-10-02 11:00 - done gate passed -> 5-done | merge-commit: abc",
    ])

    metrics = core.log_metrics(log)

    assert metrics == {"verify_attempts": 2, "rejections": 1, "escalations": 0, "cycle_hours": 26.0}


def test_a_claim_nobody_moves_is_reported_stale(repo: Path) -> None:
    config = strict_board(repo, stale_after_days=3)
    write_ticket(config.board_path, "3-in-progress", "TST-001", "old", owner="coder",
                 branch="ticket/TST-001")  # write_ticket dates it 2026-08-18
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "an old claim")

    warnings = [f for f in linter.lint(config).warnings if f.rule == "BL19"]

    assert len(warnings) == 1 and "owner coder" in warnings[0].message


# --- allowlist for ticket-supplied commands ------------------------------------


def test_ready_refuses_a_command_outside_the_allowlist(repo: Path) -> None:
    config = strict_board(repo, allowed_commands=[PY])
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-001",
        "fix",
        acceptance=(CRITERION, "- [ ] cleans up (test: `rm -rf build`)"),
        validation=CHECK,
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "refine")

    with pytest.raises(core.GateError, match="outside 'allowed_commands': rm -rf build"):
        core.ready(config, "TST-001")
