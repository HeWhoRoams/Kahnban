"""The role manifest: one definition of every factory role.

``templates/roles.json`` says, for each role, which ``kahnban`` commands it may
run, which files it may edit, which skills it loads and what it is told to do.
The guard, the prompts the runner and ``kahnban next`` hand out, the handoff
baton and the Claude agent files are all rendered from it, so they cannot
disagree.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

MANIFEST = Path(__file__).parent / "templates" / "roles.json"
PLACEHOLDER = "<ID>"
SPEC_ANALYST = "spec_analyst"
CODER = "coder"
QA_REVIEWER = "qa_reviewer"
INTEGRATOR = "integrator"
CURATOR = "curator"
FACTS = {"worktree", "qa_contract", "branch"}  # what handoff.py can say about a ticket
HUMAN = "human"  # who acts next on an escalated ticket
NOBODY = "none"  # who acts next on a finished one


@cache
def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def role(name: str) -> dict[str, Any]:
    return manifest()["roles"][name]


def workers() -> list[str]:
    """Roles that run as agents under ``kahnban run``; the integrator is the runner itself."""
    return [name for name, spec in manifest()["roles"].items() if spec.get("worker", True)]


def agent_name(name: str) -> str:
    return "kahnban-" + name.replace("_", "-")


def runner_only() -> set[str]:
    return set(manifest()["runner_only"])


def commands(name: str) -> set[str]:
    """The ``kahnban`` subcommands a worker in this role may run; none for an unknown role."""
    if name not in workers():
        return set()
    return set(manifest()["read_only"]) | set(role(name).get("commands", []))


def edits(name: str) -> str | list[str]:
    """``"blast_radius"``, or the paths a worker may edit (``{board}`` is the board root)."""
    if name not in workers():
        return []
    return role(name).get("edits", [])


def command(name: str, ticket: str) -> str:
    """The one command this role's turn is about, or '' for a role without one."""
    spec = manifest()["roles"].get(name, {})
    return _fill(spec["command"], ticket) if spec.get("command") else ""


def facts(name: str) -> list[str]:
    """Which ticket facts this role's prompt carries (``worktree``, ``qa_contract``, ``branch``)."""
    return list(manifest()["roles"].get(name, {}).get("facts", []))


def finish(name: str, ticket: str = "") -> str:
    return _fill(role(name)["finish"], ticket or PLACEHOLDER)


def prompt(name: str, *, ticket: str = "", title: str = "", facts: Iterable[str] = ()) -> str:
    """What an agent in this role is told, for one ticket (or none, for the curator)."""
    spec = role(name)
    head = f"You are the Kahnban {spec['title']}"
    head += f" for {ticket}: '{title or ticket}'." if ticket else "."
    lines = [f"{head} {_fill(spec['intro'], ticket or PLACEHOLDER)}"]
    lines += [f"- {fact}" for fact in facts]
    return "\n".join([*lines, "", *instructions(name, ticket)])


def instructions(name: str, ticket: str = "") -> list[str]:
    spec = role(name)
    ref = ticket or PLACEHOLDER
    lines = [f"{number}. {_fill(step, ref)}" for number, step in enumerate(spec["steps"], 1)]
    if spec.get("escalate_when"):
        lines.append(
            f"If {spec['escalate_when']}, do not guess: run "
            f"`kahnban escalate {ref} --reason \"<what has to change and why>\"` and stop."
        )
    lines.append(finish(name, ticket))
    if spec.get("gate"):
        lines.append(
            f"Next comes `{_fill(spec['gate'], ref)}`. If the factory runner started you, it runs "
            "that after you stop, so leave it alone; in an interactive session, run it yourself."
        )
    return lines


# What each harness's agent file can say natively; the rest the guard hook enforces.
AGENT_FORMATS: dict[str, dict[str, Any]] = {
    "claude": {"tools": True, "preloads_skills": True, "extra": []},
    "gemini": {"tools": False, "preloads_skills": False, "extra": ["kind: local"]},
    "cursor": {"tools": False, "preloads_skills": False, "extra": []},
}


def agent_markdown(name: str, harness: str = "claude") -> str:
    """The native agent file for one worker role.

    Claude Code preloads ``skills:`` and restricts ``tools:``. Gemini CLI and Cursor have
    neither, so their files tell the agent which skills to read first; the guard hook
    holds them to the role's commands and files in every harness.
    """
    spec = role(name)
    native = AGENT_FORMATS[harness]
    front = ["---", f"name: {agent_name(name)}", f"description: {spec['description']}"]
    skills = spec.get("skills", [])
    if native["tools"]:
        front.append(f"tools: {spec['tools']}")
    if native["preloads_skills"] and skills:
        front += ["skills:", *(f"  - {skill}" for skill in skills)]
    front += native["extra"]
    intro = f"You are the Kahnban {spec['title']}. {_fill(spec['intro'], PLACEHOLDER)}"
    body = [intro, ""]
    if skills and not native["preloads_skills"]:
        paths = ", ".join(f"`.agents/skills/{skill}/SKILL.md`" for skill in skills)
        body += [f"Before you start, read and follow these skills: {paths}.", ""]
    return "\n".join([*front, "---", "", *body, *instructions(name), ""])


def _fill(text: str, ticket: str) -> str:
    return text.replace("{ticket}", ticket)
