"""The role manifest: every surface tells a role the same thing, and `kahnban skills check` proves it."""

from __future__ import annotations

from pathlib import Path

from kahnban import core, dispatcher, guard, learnings, roles, skills
from kahnban.cli import main
from conftest import write_ticket


def test_the_bundled_skills_roles_and_cli_agree() -> None:
    assert skills.check() == []


def test_no_role_is_told_to_run_what_the_guard_refuses_it(board: Path) -> None:
    tickets = board / "plans" / "tickets"
    write_ticket(tickets, "0-backlog", "TST-001", "idea")
    write_ticket(tickets, "2-ready", "TST-002", "ready", blast_radius=("src/b.py",))
    write_ticket(tickets, "4-verifying", "TST-003", "verified", blast_radius=("src/c.py",))
    for _ in range(2):
        learnings.capture_learning(
            board, title="Flaky clock in tests", problem="time.sleep races", ticket_id="TST-003"
        )
    config = core.load_config(board)

    for preferred, role in (
        ("spec_analyst", "spec_analyst"),
        ("claim", "coder"),
        ("qa_reviewer", "qa_reviewer"),
        ("curator", "curator"),
    ):
        rec = dispatcher.resolve_next_action(config, preferred_role=preferred)
        assert rec.assigned_role == role
        gate = (roles.role(role).get("gate") or "").split()[1:2]
        told = skills._named_commands(rec.prompt) - set(gate)
        assert told, f"{role}'s prompt names no command at all"
        assert {c: guard.command_problem(role, c) for c in told} == dict.fromkeys(told)
        assert roles.finish(role, rec.ticket_id or "") in rec.prompt

    # The coder's next gate is the runner's to run, so the guard holds it there.
    assert "not a coder's" in guard.command_problem("coder", "verify")


def test_skills_check_reports_a_broken_handoff(tmp_path: Path, capsys) -> None:
    (tmp_path / ".claude").mkdir()
    skills.install_skills(tmp_path, harness="claude")
    assert main(["--project-root", str(tmp_path), "skills", "check"]) == 0

    agents_skills = tmp_path / ".agents" / "skills"
    coder_agent = agents_skills / "coder-agent" / "SKILL.md"
    coder_agent.write_text(coder_agent.read_text(encoding="utf-8").replace("/unslop", "/polish"), encoding="utf-8")
    tdd = agents_skills / "tdd" / "SKILL.md"
    tdd.write_text(
        tdd.read_text(encoding="utf-8").replace("name: tdd\n", "name: tdd\ndisable-model-invocation: true\n"),
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "agents" / "kahnban-coder.md").write_text("edited by hand\n", encoding="utf-8")

    assert main(["--project-root", str(tmp_path), "skills", "check"]) == 1
    report = capsys.readouterr().err
    assert "skill coder-agent: /polish is not an installed skill" in report
    assert "role coder: preloads tdd, which sets disable-model-invocation" in report
    assert ".claude/skills/coder-agent differs from .agents/skills" in report
    assert ".claude/agents/kahnban-coder.md is missing or stale" in report
