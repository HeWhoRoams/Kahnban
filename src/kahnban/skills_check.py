"""``kahnban skills check``: do the skills, the role manifest and the generated files agree?

Every ``/skill`` a skill or role names must exist and be callable by an agent, every role's
preloaded skills may only call skills it also preloads, every ``kahnban`` command named in
a skill or role must exist and be one that role may run, and a project's agent files,
harness skill copies, guard hooks and pinned lock must match what the engine would write.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kahnban import cli, exit_checks, frontmatter, roles, trust
from kahnban.harnesses import (
    AGENT_HARNESSES,
    CURSOR_RULE_HEADING,
    HOOK_FILES,
    entry_for,
    hooks_for,
    is_current,
    stop_nudges,
)
from kahnban.skills import TEMPLATES_SKILLS_DIR

SKILL_REF = re.compile(r"(?:^|[\s`(])/([a-z][a-z0-9-]*)")
KAHNBAN_COMMAND = re.compile(r"\bkahnban ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?")
HARNESS_SKILL_DIRS = (".claude/skills", ".gemini/skills", ".hermes/skills")


def audit(project_root: Path | None = None) -> list[str]:
    """Everything that would break a skill or role handoff, or the project's generated files; empty when sound."""
    root = Path(project_root).resolve() if project_root else None
    source = root / ".agents" / "skills" if root and (root / ".agents" / "skills").is_dir() else None
    problems: list[str] = []
    found = _read_skills(source or TEMPLATES_SKILLS_DIR, problems)
    cli_commands = cli.command_names()

    def blocked(name: str) -> bool:
        return str(found[name][0].get("disable-model-invocation", "")).lower() == "true"

    def check_refs(where: str, text: str) -> None:
        for ref in sorted(set(SKILL_REF.findall(text))):
            if ref not in found:
                problems.append(f"{where}: /{ref} is not an installed skill")
            elif blocked(ref):
                problems.append(f"{where}: /{ref} sets disable-model-invocation, so no agent can call it")

    def check_commands(where: str, text: str, allowed: set[str] | None) -> None:
        for command in sorted(named_commands(text)):
            if command.split()[0] not in cli_commands:
                problems.append(f"{where}: 'kahnban {command}' is not a kahnban command")
            elif allowed is not None and command not in allowed:
                problems.append(f"{where}: tells the agent to run 'kahnban {command}', which the guard refuses it")

    runner_only = roles.runner_only()

    for name, (fields, body) in found.items():
        if fields.get("name") != name:
            problems.append(f"skill {name}: frontmatter name '{fields.get('name')}' must match its folder")
        check_refs(f"skill {name}", body)
        check_commands(f"skill {name}", body, None)

    manifest = roles.manifest()
    listed = [*manifest["read_only"], *manifest["runner_only"]]
    listed += [c for spec in manifest["roles"].values() for c in spec.get("commands", [])]
    for command in sorted({c.split()[0] for c in listed} - cli_commands):
        problems.append(f"roles.json: '{command}' is not a kahnban command")

    for name, spec in manifest["roles"].items():
        where = f"role {name}"
        worker = name in roles.workers()
        gate = (spec.get("gate") or "").split()
        allowed = roles.commands(name) | ({gate[1]} if len(gate) > 1 else set()) if worker else None
        text = "\n".join([spec["intro"], *roles.instructions(name)])
        check_refs(where, text)
        check_commands(where, text, allowed)
        if worker and spec.get("exit") not in exit_checks.CHECKS:
            problems.append(f"{where}: exit '{spec.get('exit')}' is not one of {', '.join(sorted(exit_checks.CHECKS))}")
        for fact in sorted(set(spec.get("facts", [])) - roles.FACTS):
            problems.append(f"{where}: fact '{fact}' is not one of {', '.join(sorted(roles.FACTS))}")
        preloaded = set(spec.get("skills", []))
        for skill in spec.get("skills", []):
            if skill not in found:
                problems.append(f"{where}: preloads {skill}, which is not an installed skill")
                continue
            if blocked(skill):
                problems.append(f"{where}: preloads {skill}, which sets disable-model-invocation and so cannot be preloaded")
            body = found[skill][1]
            for ref in sorted(set(SKILL_REF.findall(body)) - preloaded):
                problems.append(f"{where}: preloads {skill}, which calls /{ref}; preload /{ref} too")
            if worker:
                for command in sorted(named_commands(body) & runner_only):
                    problems.append(
                        f"{where}: preloads {skill}, which tells it to run 'kahnban {command}' (runner only)"
                    )

    if root:
        problems += _project_drift(root, source)
        problems += trust.lock_problems(root)
    return problems


def named_commands(text: str) -> set[str]:
    """``kahnban`` subcommands named in prose; ``spec`` keeps its action, as the guard does."""
    return {
        f"{first} {second}" if first == "spec" and second else first
        for first, second in KAHNBAN_COMMAND.findall(text)
    }


def _read_skills(directory: Path, problems: list[str]) -> dict[str, tuple[dict[str, Any], str]]:
    found: dict[str, tuple[dict[str, Any], str]] = {}
    for skill_md in sorted(directory.glob("*/SKILL.md")):
        try:
            found[skill_md.parent.name] = frontmatter.parse(skill_md.read_text(encoding="utf-8"))
        except frontmatter.FrontmatterError as error:
            problems.append(f"skill {skill_md.parent.name}: unreadable frontmatter ({error})")
    return found


def _project_drift(root: Path, source: Path | None) -> list[str]:
    """Harness copies that disagree with .agents/skills, and stale generated agent files."""
    problems: list[str] = []
    if source:
        for relative in HARNESS_SKILL_DIRS:
            for skill_md in sorted((root / relative).glob("*/SKILL.md")):
                original = source / skill_md.parent.name / "SKILL.md"
                if original.is_file() and _text(original) != _text(skill_md):
                    problems.append(
                        f"{relative}/{skill_md.parent.name} differs from .agents/skills; "
                        "re-run 'kahnban skills install'"
                    )
    for harness in AGENT_HARNESSES:
        agents_dir = root / f".{harness}" / "agents"
        if not agents_dir.is_dir():
            problems += _hooks_without_agents(root, harness)
            continue
        for name in roles.workers():
            path = agents_dir / f"{roles.agent_name(name)}.md"
            if not path.is_file() or _text(path) != roles.agent_markdown(name, harness):
                problems.append(
                    f".{harness}/agents/{path.name} is missing or stale; re-run 'kahnban skills install'"
                )
        problems += _hook_problems(root, harness)
    return problems


def _hook_problems(root: Path, harness: str) -> list[str]:
    """A harness with generated agents must also run the guard: without it the role is only advice."""
    fix = f"re-run 'kahnban skills install --harness {harness}'"
    problems = _cursor_rule_problems(root, fix) if harness == "cursor" else []
    path = root / HOOK_FILES[harness]
    label = path.relative_to(root).as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"{label} is missing or not valid JSON, so the guard hooks are not installed; {fix}", *problems]
    for hook in hooks_for(harness, stop_nudges(root)):
        entry = entry_for(harness, data, hook)
        if entry is None:
            problems.append(f"{label} has no {hook.event} hook running '{hook.command}'; {fix}")
        elif not is_current(harness, entry, hook):
            problems.append(f"{label} runs '{hook.command}' for {hook.event} with an out-of-date matcher; {fix}")
    return problems


def _cursor_rule_problems(root: Path, fix: str) -> list[str]:
    rule = root / ".cursor" / "rules" / "kanban.mdc"
    if not rule.is_file():
        return [f".cursor/rules/kanban.mdc is missing; {fix}"]
    if CURSOR_RULE_HEADING not in rule.read_text(encoding="utf-8"):
        return [f".cursor/rules/kanban.mdc is not Kahnban's rule (no '{CURSOR_RULE_HEADING}' heading); {fix}"]
    return []


def _hooks_without_agents(root: Path, harness: str) -> list[str]:
    """The guard is wired into a harness whose agent files are gone: it would hold nobody to a role."""
    try:
        data = json.loads((root / HOOK_FILES[harness]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if any(entry_for(harness, data, hook) for hook in hooks_for(harness)):
        return [
            f"{HOOK_FILES[harness].as_posix()} still runs the guard but .{harness}/agents/ is missing; "
            f"re-run 'kahnban skills install --harness {harness}'"
        ]
    return []


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")
