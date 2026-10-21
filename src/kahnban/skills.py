"""Skills management and multi-harness distribution for Kahnban.

Allows installing and synchronizing Matt Pocock's engineering skills across
various AI harnesses (Claude Code, Gemini/Antigravity, Cursor, Codex).
By default, installs the bundled 5-stage pipeline skills into ``.agents/skills/``
and auto-configures detected harnesses, with the option to pull the extended suite
directly from ``mattpocock/skills``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kahnban import frontmatter

TEMPLATES_SKILLS_DIR = Path(__file__).parent / "templates" / "skills"


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: str
    source: str


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
                            path=str(entry / "SKILL.md"),
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
                        path=str(entry / "SKILL.md"),
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
When working on features or bugfixes, strictly follow the 5-stage Matt Pocock skill pipeline:
1. Backlog Intake: `.agents/skills/grill-with-docs/SKILL.md` (Domain alignment in GLOSSARY.md & ADR/)
2. Specification: `.agents/specs/` and `.agents/skills/to-spec/SKILL.md`
3. Granular Breakdown: `.agents/skills/to-tickets/SKILL.md` (1-3 files touched)
4. TDD in Worktrees: Work inside `.worktrees/<ID>` and follow `.agents/skills/tdd/SKILL.md`
5. Defensive Verification: Run `.agents/skills/code-review/SKILL.md` before `kahnban verify <ID>`
"""


def install_skills(
    project_root: Path,
    *,
    harness: str = "auto",
    source: str = "bundled",
    dry_run: bool = False,
) -> dict[str, Any]:
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
        configured_harnesses.append("claude (.claude/skills/)")

    if should_configure_gemini:
        gemini_skills = root / ".gemini" / "skills"
        if not dry_run:
            gemini_skills.mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(agents_skills_dir, gemini_skills)
        configured_harnesses.append("gemini (.gemini/skills/)")

    if should_configure_cursor:
        cursor_rules = root / ".cursor" / "rules"
        rule_file = cursor_rules / "kanban.mdc"
        if not dry_run:
            cursor_rules.mkdir(parents=True, exist_ok=True)
            if not rule_file.exists():
                rule_file.write_text(CURSOR_MDC_CONTENT, encoding="utf-8", newline="\n")
        configured_harnesses.append("cursor (.cursor/rules/kanban.mdc)")

    return {
        "ok": True,
        "source": source,
        "harness": harness,
        "installed_skills": sorted(set(installed_skills)),
        "configured_harnesses": configured_harnesses,
        "messages": messages,
    }


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
