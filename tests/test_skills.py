"""Tests for skill management, listing, and multi-harness distribution (skills.py)."""

from __future__ import annotations

from pathlib import Path

from kahnban import cli, skills


def test_list_skills_bundled() -> None:
    available = skills.list_skills()
    assert len(available) >= 5
    names = {s.name for s in available}
    assert "grill-with-docs" in names
    assert "to-spec" in names
    assert "to-tickets" in names
    assert "tdd" in names
    assert "code-review" in names
    assert "setup-kahnban-skills" in names


def test_install_skills_default_bundled(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    result = skills.install_skills(repo, harness="agents", source="bundled")
    assert result["ok"] is True
    assert "grill-with-docs" in result["installed_skills"]
    assert "tdd" in result["installed_skills"]

    # Verify physical file layout
    skills_dir = repo / ".agents" / "skills"
    assert (skills_dir / "grill-with-docs" / "SKILL.md").exists()
    assert (skills_dir / "to-spec" / "SKILL.md").exists()
    assert (skills_dir / "to-tickets" / "SKILL.md").exists()
    assert (skills_dir / "tdd" / "SKILL.md").exists()
    assert (skills_dir / "code-review" / "SKILL.md").exists()


def test_install_skills_multi_harness(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create mock harness directories
    (repo / ".claude").mkdir()
    (repo / ".gemini").mkdir()
    (repo / ".cursor").mkdir()

    result = skills.install_skills(repo, harness="auto", source="bundled")
    assert result["ok"] is True
    targets = result["configured_harnesses"]
    assert any("claude" in t for t in targets)
    assert any("gemini" in t for t in targets)
    assert any("cursor" in t for t in targets)

    # Verify files in each harness
    assert (repo / ".claude" / "skills" / "tdd" / "SKILL.md").exists()
    assert (repo / ".gemini" / "skills" / "tdd" / "SKILL.md").exists()
    assert (repo / ".cursor" / "rules" / "kanban.mdc").exists()


def test_cli_skills_list_and_install(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "cli_repo"
    repo.mkdir()

    # 1. Test skills list
    code = cli.main(["--project-root", str(repo), "skills", "list"])
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "Available Agent Skills:" in out
    assert "/grill-with-docs" in out
    assert "/tdd" in out

    # 2. Test skills install --dry-run
    code = cli.main(["--project-root", str(repo), "skills", "install", "--dry-run"])
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "[OK] installed" in out
    assert "/code-review" in out
    assert not (repo / ".agents" / "skills").exists()

    # 3. Test real skills install
    code = cli.main(["--project-root", str(repo), "skills", "install"])
    assert code == cli.EXIT_OK
    out, _ = capsys.readouterr()
    assert "[OK] installed" in out
    assert (repo / ".agents" / "skills" / "tdd" / "SKILL.md").exists()


def test_install_skills_pstack_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Source 'pstack' installs curated bundle
    result = skills.install_skills(repo, harness="agents", source="pstack")
    assert result["ok"] is True
    assert "principle-subtract-before-you-add" in result["installed_skills"]
    assert "reflect" in result["installed_skills"]
    assert "harvest-learnings" in result["installed_skills"]
    assert "factory-mode" in result["installed_skills"]

    skills_dir = repo / ".agents" / "skills"
    assert (skills_dir / "principle-subtract-before-you-add" / "SKILL.md").exists()
    assert (skills_dir / "reflect" / "SKILL.md").exists()
    assert (skills_dir / "harvest-learnings" / "SKILL.md").exists()
    assert (skills_dir / "factory-mode" / "SKILL.md").exists()


def test_template_and_adapters_skills_parity() -> None:
    adapters_dir = Path("adapters/skills")
    templates_dir = skills.TEMPLATES_SKILLS_DIR

    assert adapters_dir.is_dir()
    assert templates_dir.is_dir()

    adapter_skills = sorted([d.name for d in adapters_dir.iterdir() if d.is_dir()])
    template_skills = sorted([d.name for d in templates_dir.iterdir() if d.is_dir()])

    assert adapter_skills == template_skills, f"Mismatch: {set(adapter_skills) ^ set(template_skills)}"

    for s_name in adapter_skills:
        a_file = adapters_dir / s_name / "SKILL.md"
        t_file = templates_dir / s_name / "SKILL.md"
        assert a_file.is_file(), f"Missing {a_file}"
        assert t_file.is_file(), f"Missing {t_file}"
        assert a_file.read_text(encoding="utf-8") == t_file.read_text(encoding="utf-8"), (
            f"Content mismatch for skill {s_name}"
        )
