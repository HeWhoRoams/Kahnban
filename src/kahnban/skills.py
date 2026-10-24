"""Skills management and multi-harness distribution for Kahnban.

Allows installing and synchronizing Matt Pocock's engineering skills across
various AI harnesses (Claude Code, Gemini/Antigravity, Cursor, Codex).
By default, installs the bundled 5-stage pipeline skills into ``.agents/skills/``
and auto-configures detected harnesses, with the option to pull the extended suite
directly from ``mattpocock/skills``.
"""

from __future__ import annotations

import json

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import frontmatter, roles, trust

TEMPLATES_SKILLS_DIR = Path(__file__).parent / "templates" / "skills"
GUARD_COMMAND = "kahnban guard"
# VS Code's mcp.json schema: a stdio server is "type": "stdio" plus command/args.
VSCODE_MCP_SERVER = {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "kahnban.mcp_server", "--project-root", "${workspaceFolder}"],
}
GUARD_HOOK = {
    "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
    "hooks": [{"type": "command", "command": GUARD_COMMAND}],
}
STOP_COMMAND = "kahnban guard --stop"
STOP_HOOK = {"hooks": [{"type": "command", "command": STOP_COMMAND}]}
CLAUDE_HOOKS = (("PreToolUse", GUARD_HOOK, GUARD_COMMAND), ("Stop", STOP_HOOK, STOP_COMMAND))
# Gemini CLI's settings.json uses the same shape under its own event and tool names.
GEMINI_HOOKS = (
    (
        "BeforeTool",
        {
            "matcher": "write_file|replace|run_shell_command",
            "hooks": [{"type": "command", "command": GUARD_COMMAND}],
        },
        GUARD_COMMAND,
    ),
    ("AfterAgent", STOP_HOOK, STOP_COMMAND),
)
# Cursor's hooks.json: one flat list of commands per event. Its stop hook re-prompts the
# agent instead of blocking, so it is capped at two follow-ups.
CURSOR_HOOKS = (
    ("beforeShellExecution", {"command": GUARD_COMMAND}),
    ("preToolUse", {"command": GUARD_COMMAND}),
    ("stop", {"command": STOP_COMMAND, "loop_limit": 2}),
)


def _install_cursor_hooks(hooks_path: Path, messages: list[str]) -> None:
    """Add the role guard to .cursor/hooks.json, keeping every existing hook."""
    data: dict[str, Any] = {"version": 1}
    if hooks_path.is_file():
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            messages.append(f"{hooks_path} is not valid JSON; add the '{GUARD_COMMAND}' hooks by hand.")
            return
    added = False
    for event, hook in CURSOR_HOOKS:
        entries = data.setdefault("hooks", {}).setdefault(event, [])
        if not any(entry.get("command") == hook["command"] for entry in entries):
            entries.append(hook)
            added = True
    if added:
        from kahnban.core import write_text_atomic

        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(hooks_path, json.dumps(data, indent=2) + "\n")


def _install_guard_hook(
    settings_path: Path, messages: list[str], hooks: tuple[tuple[str, dict[str, Any], str], ...] = CLAUDE_HOOKS
) -> None:
    """Add the role guard as pre-tool and stop hooks, keeping every existing setting."""
    data: dict[str, Any] = {}
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            messages.append(
                f"{settings_path} is not valid JSON; add the '{GUARD_COMMAND}' "
                "PreToolUse hook by hand."
            )
            return
    added = False
    for event, hook, command in hooks:
        entries = data.setdefault("hooks", {}).setdefault(event, [])
        if not any(h.get("command") == command for entry in entries for h in entry.get("hooks", [])):
            entries.append(hook)
            added = True
    if not added:
        return
    from kahnban.core import write_text_atomic

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(settings_path, json.dumps(data, indent=2) + "\n")


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: str
    source: str


@dataclass(frozen=True)
class SkillsResult:
    ok: bool
    source: str
    harness: str
    installed_skills: list[str]
    configured_harnesses: list[str]
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source": self.source,
            "harness": self.harness,
            "installed_skills": self.installed_skills,
            "configured_harnesses": self.configured_harnesses,
            "messages": self.messages,
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


def _read_skill_description(skill_md: Path) -> str:
    if not skill_md.is_file():
        return ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        fields, body = frontmatter.parse(text)
        desc = fields.get("description")
        if desc:
            return str(desc).strip()
        for line in body.splitlines():
            line_s = line.strip()
            if line_s.startswith("# "):
                return line_s[2:].strip()
            if line_s and not line_s.startswith("#") and not line_s.startswith("---"):
                return line_s
    except Exception:
        pass
    return ""


def list_skills(project_root: Path | None = None) -> list[SkillInfo]:
    """List available skills, checking the project's .agents/skills/ first, then bundled."""
    skills: list[SkillInfo] = []
    seen: set[str] = set()

    if project_root is not None:
        proj_dir = Path(project_root).resolve() / ".agents" / "skills"
        if proj_dir.is_dir():
            for entry in sorted(proj_dir.iterdir()):
                if entry.is_dir() and (entry / "SKILL.md").is_file():
                    desc = _read_skill_description(entry / "SKILL.md")
                    skills.append(
                        SkillInfo(
                            name=entry.name,
                            description=desc,
                            path=(entry / "SKILL.md").resolve().as_posix(),
                            source="project (.agents/skills)",
                        )
                    )
                    seen.add(entry.name)

    if TEMPLATES_SKILLS_DIR.is_dir():
        for entry in sorted(TEMPLATES_SKILLS_DIR.iterdir()):
            if entry.is_dir() and entry.name not in seen and (entry / "SKILL.md").is_file():
                desc = _read_skill_description(entry / "SKILL.md")
                skills.append(
                    SkillInfo(
                        name=entry.name,
                        description=desc,
                        path=(entry / "SKILL.md").resolve().as_posix(),
                        source="bundled",
                    )
                )
                seen.add(entry.name)

    return skills


CURSOR_MDC_CONTENT = """---
description: Kahnban Software Factory Rules & Matt Pocock Skills
globs: *
alwaysApply: true
---
# Kahnban Engineering Protocols

Always check `.agents/state/ACTIVE_SESSION.md` before starting work and synchronize it before handing off.
For full end-to-end autonomous lifecycle execution, use `/factory-mode` (`.agents/skills/factory-mode/SKILL.md`).
When working on features or bugfixes, strictly follow the 5-stage engineering pipeline:
1. Backlog Intake: `.agents/skills/grill-with-docs/SKILL.md` (Domain alignment in GLOSSARY.md & ADR/)
2. Specification: `.agents/specs/` and `.agents/skills/to-spec/SKILL.md`
3. Granular Breakdown: `.agents/skills/to-tickets/SKILL.md` (1-3 files touched)
4. TDD in Worktrees: Work inside `.worktrees/<ID>` and follow `.agents/skills/tdd/SKILL.md`
5. Defensive Verification: Run `.agents/skills/code-review/SKILL.md` before `kahnban verify <ID>`
6. Learning & Feedback: Run `/reflect` upon completing tickets and log patterns to `./learnings/`
"""


def install_skills(
    project_root: Path,
    *,
    harness: str = "auto",
    source: str = "bundled",
    dry_run: bool = False,
    relock: bool = False,
) -> SkillsResult:
    """Install and configure skills in the adopter project and chosen harnesses.

    Parameters
    ----------
    project_root:
        Target project repository root.
    harness:
        One of 'auto', 'agents', 'claude', 'gemini', 'cursor', 'all'.
        Default is 'auto', which populates .agents/skills/ and configures any
        detected harness directories present in the project.
    source:
        'bundled' (default) copies Kahnban's built-in Matt Pocock pipeline skills.
        'mattpocock' or 'upstream' pulls the full suite from github.com/mattpocock/skills.
    dry_run:
        If True, only simulate actions without writing files.
    """
    root = Path(project_root).resolve()
    installed_skills: list[str] = []
    configured_harnesses: list[str] = []
    messages: list[str] = []

    agents_skills_dir = root / ".agents" / "skills"

    # Step 1: Install source into .agents/skills/
    if source in ("mattpocock", "upstream"):
        messages.append("Installing extended skills from upstream mattpocock/skills...")
        if not dry_run:
            agents_skills_dir.mkdir(parents=True, exist_ok=True)
            npx_bin = shutil.which("npx")
            if npx_bin:
                try:
                    cmd = [npx_bin, "skills@latest", "add", "mattpocock/skills", "--yes"]
                    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
                    if res.returncode == 0:
                        messages.append("Successfully added mattpocock/skills via npx skills.")
                    else:
                        messages.append(f"npx skills returned code {res.returncode}; falling back to bundled.")
                        _copy_bundled_skills(agents_skills_dir, installed_skills)
                except Exception as ex:
                    messages.append(f"npx execution failed ({ex}); falling back to bundled.")
                    _copy_bundled_skills(agents_skills_dir, installed_skills)
            else:
                messages.append("npx not found in PATH; falling back to bundled skills.")
                _copy_bundled_skills(agents_skills_dir, installed_skills)
    elif source == "pstack" or source.startswith("pstack:"):
        messages.append(f"Installing skills from {source}...")
        if not dry_run:
            agents_skills_dir.mkdir(parents=True, exist_ok=True)
            _fetch_pstack_upstream(agents_skills_dir, source, installed_skills, messages)
        else:
            if TEMPLATES_SKILLS_DIR.is_dir():
                installed_skills.extend(d.name for d in TEMPLATES_SKILLS_DIR.iterdir() if d.is_dir())
    else:
        # Default: bundled
        if not dry_run:
            _copy_bundled_skills(agents_skills_dir, installed_skills)
        else:
            if TEMPLATES_SKILLS_DIR.is_dir():
                installed_skills.extend(d.name for d in TEMPLATES_SKILLS_DIR.iterdir() if d.is_dir())

    configured_harnesses.append("agents (.agents/skills/)")

    # Step 2: Configure target harness(es)
    harness_norm = harness.strip().lower()
    should_configure_claude = harness_norm in ("claude", "all") or (
        harness_norm == "auto" and (root / ".claude").is_dir()
    )
    should_configure_gemini = harness_norm in ("gemini", "all") or (
        harness_norm == "auto" and (root / ".gemini").is_dir()
    )
    should_configure_cursor = harness_norm in ("cursor", "all") or (
        harness_norm == "auto" and (root / ".cursor").is_dir()
    )

    if should_configure_claude:
        claude_skills = root / ".claude" / "skills"
        if not dry_run:
            claude_skills.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(agents_skills_dir, claude_skills)
            _write_agents(root / ".claude" / "agents")
            _install_guard_hook(root / ".claude" / "settings.json", messages)
            messages.append(
                "Commit .claude/ so ticket worktrees inherit the agents and the guard hook."
            )
        configured_harnesses.append("claude (.claude/skills/, .claude/agents/, guard hook)")

    if should_configure_gemini:
        gemini_skills = root / ".gemini" / "skills"
        if not dry_run:
            gemini_skills.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(agents_skills_dir, gemini_skills)
            _write_agents(root / ".gemini" / "agents", "gemini")
            _install_guard_hook(root / ".gemini" / "settings.json", messages, GEMINI_HOOKS)
            messages.append("Commit .gemini/ so ticket worktrees inherit the agents and the guard hook.")
        configured_harnesses.append("gemini (.gemini/skills/, .gemini/agents/, guard hook)")

    if should_configure_cursor:
        cursor_rules = root / ".cursor" / "rules"
        rule_file = cursor_rules / "kanban.mdc"
        if not dry_run:
            cursor_rules.mkdir(parents=True, exist_ok=True)
            if not rule_file.exists():
                from kahnban.core import write_text_atomic
                write_text_atomic(rule_file, CURSOR_MDC_CONTENT)
            _write_agents(root / ".cursor" / "agents", "cursor")
            _install_cursor_hooks(root / ".cursor" / "hooks.json", messages)
            messages.append("Commit .cursor/ so ticket worktrees inherit the agents and the guard hook.")
        configured_harnesses.append("cursor (.cursor/rules/kanban.mdc, .cursor/agents/, guard hook)")

    should_configure_vscode = harness_norm in ("vscode", "all") or (
        harness_norm == "auto" and (root / ".vscode").is_dir()
    )
    if should_configure_vscode:
        vscode_dir = root / ".vscode"
        mcp_config = vscode_dir / "mcp.json"
        if not dry_run:
            vscode_dir.mkdir(parents=True, exist_ok=True)
            if not mcp_config.exists():
                from kahnban.core import write_text_atomic
                mcp_data = {"servers": {"kahnban": VSCODE_MCP_SERVER}}
                write_text_atomic(mcp_config, json.dumps(mcp_data, indent=2))
        configured_harnesses.append("vscode (.vscode/mcp.json)")

    should_configure_hermes = harness_norm in ("hermes", "all") or (
        harness_norm == "auto" and (root / ".hermes").is_dir()
    )
    if should_configure_hermes:
        hermes_skills = root / ".hermes" / "skills"
        if not dry_run:
            hermes_skills.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(agents_skills_dir, hermes_skills)
        configured_harnesses.append("hermes (.hermes/skills/)")

    if not dry_run:
        if relock or not (root / trust.LOCK).is_file():
            pinned = trust.write_lock(root)
            if pinned:
                messages.append(f"Pinned {pinned} skill and hook files in {trust.LOCK.as_posix()}; commit it.")
        else:
            # An existing pin is a decision a person made: report what changed, never move it.
            messages.extend(f"[WARN] {problem}" for problem in trust.lock_problems(root))

    return SkillsResult(
        ok=True,
        source=source,
        harness=harness,
        installed_skills=sorted(set(installed_skills)),
        configured_harnesses=configured_harnesses,
        messages=messages,
    )


def _fetch_pstack_upstream(
    dest_dir: Path,
    source: str,
    installed: list[str],
    messages: list[str],
) -> None:
    """Fetch skills from cursor/plugins/pstack via GitHub API."""
    import json
    import urllib.request
    from kahnban.core import write_text_atomic

    # First copy bundled core so project has the foundations
    _copy_bundled_skills(dest_dir, installed)

    target = source.split(":", 1)[1].strip() if ":" in source else ""
    if not target or target in ("core", "curated"):
        messages.append("Installed curated pstack core skills from bundle.")
        return

    headers = {"User-Agent": "kahnban-skills"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api_url = "https://api.github.com/repos/cursor/plugins/contents/pstack/skills"

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        available = {item["name"]: item for item in data if item.get("type") == "dir"}

        targets_to_fetch = list(available.keys()) if target == "all" else [target]
        for t in targets_to_fetch:
            if t not in available:
                messages.append(f"Skill '{t}' not found in cursor/plugins/pstack.")
                continue
            try:
                skill_raw_url = f"https://raw.githubusercontent.com/cursor/plugins/main/pstack/skills/{t}/SKILL.md"
                req_skill = urllib.request.Request(skill_raw_url, headers=headers)
                with urllib.request.urlopen(req_skill, timeout=15) as sresp:
                    skill_content = sresp.read().decode("utf-8")

                s_dir = dest_dir / t
                s_dir.mkdir(parents=True, exist_ok=True)
                write_text_atomic(s_dir / "SKILL.md", skill_content)
                if t not in installed:
                    installed.append(t)
                messages.append(f"Successfully fetched '{t}' from upstream pstack.")
            except Exception as item_err:
                messages.append(f"Failed to fetch '{t}' from pstack ({item_err}); retained bundled version.")
    except Exception as ex:
        messages.append(f"Remote fetch from pstack failed ({ex}); retained bundled skills.")


# A skill invoked by name: "/tdd", "`/tdd`", "(/tdd)"; never a path segment like "plans/tickets".
SKILL_REF = re.compile(r"(?:^|[\s`(])/([a-z][a-z0-9-]*)")
KAHNBAN_COMMAND = re.compile(r"\bkahnban ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?")
HARNESS_SKILL_DIRS = (".claude/skills", ".gemini/skills", ".hermes/skills")
AGENT_HARNESSES = ("claude", "gemini", "cursor")


def check(project_root: Path | None = None) -> list[str]:
    """Everything that would break a skill-to-skill or role-to-skill handoff; empty when sound.

    Checks the bundled skills, or a project's ``.agents/skills`` when it has one,
    against the role manifest and the CLI: every ``/skill`` a skill or role names
    exists and may be invoked by an agent, every role's preloaded skills only call
    skills it also preloads, every ``kahnban`` command named anywhere exists, and a
    role's own instructions name only commands the guard lets it run (or its gate).
    A preloaded skill may name a gate such as ``claim`` or ``verify``, because an
    interactive conductor runs those, but never a runner-only command. For a
    project it also compares the harness copies and generated agent files.
    """
    root = Path(project_root).resolve() if project_root else None
    source = root / ".agents" / "skills" if root and (root / ".agents" / "skills").is_dir() else None
    problems: list[str] = []
    found = _read_skills(source or TEMPLATES_SKILLS_DIR, problems)
    cli_commands = _cli_commands()

    def blocked(name: str) -> bool:
        return str(found[name][0].get("disable-model-invocation", "")).lower() == "true"

    def check_refs(where: str, text: str) -> None:
        for ref in sorted(set(SKILL_REF.findall(text))):
            if ref not in found:
                problems.append(f"{where}: /{ref} is not an installed skill")
            elif blocked(ref):
                problems.append(f"{where}: /{ref} sets disable-model-invocation, so no agent can call it")

    def check_commands(where: str, text: str, allowed: set[str] | None) -> None:
        for command in sorted(_named_commands(text)):
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
                for command in sorted(_named_commands(body) & runner_only):
                    problems.append(
                        f"{where}: preloads {skill}, which tells it to run 'kahnban {command}' (runner only)"
                    )

    if root:
        problems += _project_drift(root, source)
        problems += trust.lock_problems(root)
    return problems


def _named_commands(text: str) -> set[str]:
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


def _cli_commands() -> set[str]:
    import argparse

    from kahnban import cli

    return {
        name
        for action in cli.build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
        for name in action.choices
    }


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
            continue
        for name in roles.workers():
            path = agents_dir / f"{roles.agent_name(name)}.md"
            if not path.is_file() or _text(path) != roles.agent_markdown(name, harness):
                problems.append(
                    f".{harness}/agents/{path.name} is missing or stale; re-run 'kahnban skills install'"
                )
    return problems


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _write_agents(agents_dir: Path, harness: str = "claude") -> None:
    """Render one native agent file per worker role from the role manifest."""
    from kahnban.core import write_text_atomic

    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in roles.workers():
        write_text_atomic(agents_dir / f"{roles.agent_name(name)}.md", roles.agent_markdown(name, harness))


def _copy_bundled_skills(target_dir: Path, recorded_names: list[str]) -> None:
    if not TEMPLATES_SKILLS_DIR.is_dir():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for skill_dir in sorted(TEMPLATES_SKILLS_DIR.iterdir()):
        if skill_dir.is_dir():
            dest = target_dir / skill_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            for file in sorted(skill_dir.iterdir()):
                if file.is_file():
                    shutil.copyfile(file, dest / file.name)
            recorded_names.append(skill_dir.name)


def _copy_tree_contents(source_dir: Path, target_dir: Path) -> None:
    if not source_dir.is_dir():
        return
    for item in source_dir.iterdir():
        dest = target_dir / item.name
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(item, dest)
        elif item.is_file():
            shutil.copyfile(item, dest)
