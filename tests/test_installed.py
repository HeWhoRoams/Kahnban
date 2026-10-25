"""The built wheel, installed into a clean environment, carries everything and runs.

Skipped unless KAHNBAN_INSTALLED=1: it builds a wheel and a virtual environment, which takes a
minute and, with build isolation, needs network access to fetch setuptools. CI sets it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("KAHNBAN_INSTALLED"), reason="set KAHNBAN_INSTALLED=1 to build and install the wheel")

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEMPLATES = ROOT / "src" / "kahnban" / "templates"


def run(*argv: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "COVERAGE_PROCESS_START")}
    done = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True)
    assert done.returncode == 0, f"{argv}\n{done.stdout}\n{done.stderr}"
    return done


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The python of a fresh virtual environment with the wheel installed (not editable, not from src)."""
    work = tmp_path_factory.mktemp("wheel")
    wheels = work / "wheels"
    # Build from a copy: no stale build/ directory to hide a missing file, and nothing written into the repository.
    project = work / "project"
    shutil.copytree(ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    shutil.copy(ROOT / "pyproject.toml", project / "pyproject.toml")
    isolation = [] if os.environ.get("KAHNBAN_NO_ISOLATION") != "1" else ["--no-build-isolation"]  # offline: use the installed setuptools
    run(sys.executable, "-m", "pip", "wheel", project, "--no-deps", *isolation, "-w", wheels)
    wheel = next(wheels.glob("kahnban-*.whl"))
    env = work / "venv"
    venv.create(env, with_pip=True)
    python = env / ("Scripts" if os.name == "nt" else "bin") / "python"
    run(python, "-m", "pip", "install", "--no-index", "--no-deps", wheel)
    return python


def test_every_template_in_the_source_tree_is_in_the_wheel(installed: Path) -> None:
    listing = run(
        installed,
        "-c",
        "import importlib.resources as r; root = r.files('kahnban') / 'templates'\n"
        "print('\\n'.join(sorted(str(p.relative_to(root)).replace(chr(92), '/') for p in root.rglob('*') if p.is_file())))",
        cwd=ROOT.parent,
    ).stdout.split()
    expected = sorted(p.relative_to(SOURCE_TEMPLATES).as_posix() for p in SOURCE_TEMPLATES.rglob("*") if p.is_file())

    assert listing == expected


def test_the_installed_command_scaffolds_and_lints_a_board(installed: Path, tmp_path: Path) -> None:
    repo = tmp_path / "adopter"
    repo.mkdir()
    run("git", "init", "--initial-branch", "main", repo)
    run("git", "-C", repo, "config", "user.name", "Installed Test")
    run("git", "-C", repo, "config", "user.email", "installed@example.invalid")
    (repo / "README.md").write_text("adopter\n", encoding="utf-8")
    run("git", "-C", repo, "add", "-A")
    run("git", "-C", repo, "commit", "-m", "initial")

    assert "kahnban" in run(installed, "-m", "kahnban", "--version", cwd=repo).stdout
    run(installed, "-m", "kahnban", "init", "--prefix", "AD", "--agentic", cwd=repo)
    run(installed, "-m", "kahnban", "skills", "install", cwd=repo)
    run(installed, "-m", "kahnban", "skills", "check", cwd=repo)
    run(installed, "-m", "kahnban", "new", "First idea", "--problem", "It needs doing", cwd=repo)
    run(installed, "-m", "kahnban", "lint", cwd=repo)
    status = run(installed, "-m", "kahnban", "status", cwd=repo).stdout

    assert "0-backlog=1" in status
    assert (repo / ".agents").is_dir()
    assert (repo / "plans" / "board.config.json").is_file()
