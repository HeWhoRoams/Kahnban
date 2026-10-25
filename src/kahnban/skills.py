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
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kahnban import frontmatter, trust
from kahnban.fsutil import write_text_atomic
from kahnban.harnesses import (
    AGENT_HARNESSES,
    CURSOR_MDC_CONTENT,
    HOOK_FILES,
    VSCODE_MCP_SERVER,
    merge_hooks,
    stop_nudges,
    write_agents,
)

TEMPLATES_SKILLS_DIR = Path(__file__).parent / "templates" / "skills"
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
        try:
            fields, body = frontmatter.parse(text)
        except frontmatter.FrontmatterError:
            fields, body = {}, text  # no (readable) frontmatter: describe it by its heading or first line
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


def _install_source(
    root: Path,
    skills_dir: Path,
    source: str,
    dry_run: bool,
    installed: list[str],
    messages: list[str],
) -> None:
    """Put the chosen skills into ``.agents/skills/``: bundled, upstream through npx, or pstack."""
    if source in ("mattpocock", "upstream"):
        messages.append("Installing extended skills from upstream mattpocock/skills...")
        if not dry_run:
            skills_dir.mkdir(parents=True, exist_ok=True)
            npx_bin = shutil.which("npx")
            if npx_bin:
                try:
                    cmd = [npx_bin, "skills@latest", "add", "mattpocock/skills", "--yes"]
                    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
                    if res.returncode == 0:
                        messages.append("Successfully added mattpocock/skills via npx skills.")
                    else:
                        messages.append(f"npx skills returned code {res.returncode}; falling back to bundled.")
                        _copy_bundled_skills(skills_dir, installed)
                except Exception as ex:
                    messages.append(f"npx execution failed ({ex}); falling back to bundled.")
                    _copy_bundled_skills(skills_dir, installed)
            else:
                messages.append("npx not found in PATH; falling back to bundled skills.")
                _copy_bundled_skills(skills_dir, installed)
    elif source == "pstack" or source.startswith("pstack:"):
        messages.append(f"Installing skills from {source}...")
        if not dry_run:
            skills_dir.mkdir(parents=True, exist_ok=True)
            _fetch_pstack_upstream(skills_dir, source, installed, messages)
        else:
            if TEMPLATES_SKILLS_DIR.is_dir():
                installed.extend(d.name for d in TEMPLATES_SKILLS_DIR.iterdir() if d.is_dir())
    else:
        # Default: bundled
        if not dry_run:
            _copy_bundled_skills(skills_dir, installed)
        else:
            if TEMPLATES_SKILLS_DIR.is_dir():
                installed.extend(d.name for d in TEMPLATES_SKILLS_DIR.iterdir() if d.is_dir())


def _configure_agent_harness(
    root: Path, name: str, skills_dir: Path, messages: list[str], dry_run: bool
) -> str:
    """Skills, native agent files and the guard hooks for one harness; returns the summary line."""
    folder = root / f".{name}"
    parts = [f".{name}/agents/", "guard hook"]
    if name != "cursor":  # Cursor reads .agents/skills through its rule instead of a copy
        parts.insert(0, f".{name}/skills/")
    if name == "cursor":
        parts.insert(0, ".cursor/rules/kanban.mdc")
    if not dry_run:
        if name != "cursor":
            (folder / "skills").mkdir(parents=True, exist_ok=True)
            _copy_tree_contents(skills_dir, folder / "skills")
        else:
            rule = folder / "rules" / "kanban.mdc"
            rule.parent.mkdir(parents=True, exist_ok=True)
            if not rule.exists():
                write_text_atomic(rule, CURSOR_MDC_CONTENT)
        write_agents(folder / "agents", name)
        merge_hooks(root / HOOK_FILES[name], name, messages, stop_nudges(root))
        messages.append(f"Commit .{name}/ so ticket worktrees inherit the agents and the guard hook.")
    return f"{name} ({', '.join(parts)})"


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
    drift_before = {} if dry_run else trust.drift(root)

    agents_skills_dir = root / ".agents" / "skills"

    _install_source(root, agents_skills_dir, source, dry_run, installed_skills, messages)

    configured_harnesses.append("agents (.agents/skills/)")

    # Step 2: Configure target harness(es)
    harness_norm = harness.strip().lower()
    def wanted(name: str) -> bool:
        return harness_norm in (name, "all") or (harness_norm == "auto" and (root / f".{name}").is_dir())

    for name in AGENT_HARNESSES:
        if wanted(name):
            configured_harnesses.append(
                _configure_agent_harness(root, name, agents_skills_dir, messages, dry_run)
            )

    if wanted("vscode"):
        vscode_dir = root / ".vscode"
        mcp_config = vscode_dir / "mcp.json"
        if not dry_run:
            vscode_dir.mkdir(parents=True, exist_ok=True)
            if not mcp_config.exists():
                mcp_data = {"servers": {"kahnban": VSCODE_MCP_SERVER}}
                write_text_atomic(mcp_config, json.dumps(mcp_data, indent=2))
        configured_harnesses.append("vscode (.vscode/mcp.json)")

    if wanted("hermes"):
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
            after = trust.drift(root)
            for name in sorted(drift_before.keys() - after.keys()):
                messages.append(f"Restored {name} to the bundled version (it had {drift_before[name]}).")
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
