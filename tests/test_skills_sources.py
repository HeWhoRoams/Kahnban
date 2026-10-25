"""Where skills come from: the project, the bundle, npx and pstack, and what happens when a source fails."""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

from kahnban import skills


def write_skill(root: Path, name: str, text: str) -> Path:
    path = root / ".agents" / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- descriptions and listing ----------------------------------------------


def test_a_description_comes_from_the_frontmatter_then_the_first_heading_then_the_first_line(tmp_path: Path) -> None:
    front = write_skill(tmp_path, "a", "---\nname: a\ndescription: Does the thing.\n---\n# A\n")
    heading = write_skill(tmp_path, "b", "---\nname: b\n---\n# Title of b\ntext\n")
    plain = write_skill(tmp_path, "c", "---\nname: c\n---\njust a line\n")
    bare = write_skill(tmp_path, "d", "no frontmatter at all\n")

    assert skills._read_skill_description(front) == "Does the thing."
    assert skills._read_skill_description(heading) == "Title of b"
    assert skills._read_skill_description(plain) == "just a line"
    assert skills._read_skill_description(bare) == ""  # without frontmatter a skill lists with no description
    assert skills._read_skill_description(tmp_path / "missing.md") == ""


def test_a_project_skill_shadows_the_bundled_one_of_the_same_name(tmp_path: Path) -> None:
    write_skill(tmp_path, "tdd", "---\nname: tdd\n---\n# My own tdd\n")
    write_skill(tmp_path, "extra", "---\nname: extra\n---\n# Extra\n")

    listed = {s.name: s for s in skills.list_skills(tmp_path)}

    assert listed["tdd"].source.startswith("project")
    assert listed["tdd"].description == "My own tdd"
    assert listed["extra"].source.startswith("project")
    assert listed["to-spec"].source == "bundled"


# --- npx ----------------------------------------------------------------------


def install(tmp_path: Path, source: str, *, dry_run: bool = False) -> tuple[list[str], list[str]]:
    installed: list[str] = []
    messages: list[str] = []
    skills._install_source(tmp_path, tmp_path / ".agents" / "skills", source, dry_run, installed, messages)
    return installed, messages


def test_npx_missing_falls_back_to_the_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: None)

    installed, messages = install(tmp_path, "mattpocock")

    assert "tdd" in installed
    assert any("npx not found" in m for m in messages)


def test_npx_that_succeeds_installs_nothing_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: "npx")
    ran: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(skills.subprocess, "run", fake_run)

    installed, messages = install(tmp_path, "upstream")

    assert ran and ran[0][1:3] == ["skills@latest", "add"]
    assert installed == []
    assert any("Successfully added" in m for m in messages)


@pytest.mark.parametrize("failure", ["exit", "raise"])
def test_npx_that_fails_falls_back_to_the_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    monkeypatch.setattr(skills.shutil, "which", lambda name: "npx")

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if failure == "raise":
            raise subprocess.TimeoutExpired(cmd, 120)
        return subprocess.CompletedProcess(cmd, 1, "", "boom")

    monkeypatch.setattr(skills.subprocess, "run", fake_run)

    installed, messages = install(tmp_path, "mattpocock")

    assert "tdd" in installed
    assert any("falling back to bundled" in m for m in messages)


def test_a_dry_run_touches_nothing(tmp_path: Path) -> None:
    for source in ("bundled", "mattpocock", "pstack"):
        install(tmp_path, source, dry_run=True)

    assert not (tmp_path / ".agents").exists()


def test_a_dry_run_of_pstack_lists_what_the_bundle_would_give(tmp_path: Path) -> None:
    installed, _ = install(tmp_path, "pstack", dry_run=True)

    assert "tdd" in installed


# --- pstack over the network, faked ---------------------------------------------


class Response:
    def __init__(self, body: str) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body.encode("utf-8")

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def fake_github(monkeypatch: pytest.MonkeyPatch, *, listing: list[dict], files: dict[str, str]) -> None:
    def urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        url = request.full_url
        if url.endswith("/pstack/skills"):
            return Response(json.dumps(listing))
        for name, text in files.items():
            if f"/{name}/SKILL.md" in url:
                return Response(text)
        raise OSError(f"no such url {url}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def fetch(tmp_path: Path, source: str) -> tuple[list[str], list[str]]:
    installed: list[str] = []
    messages: list[str] = []
    skills._fetch_pstack_upstream(tmp_path / "skills", source, installed, messages)
    return installed, messages


def test_pstack_core_needs_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("no request expected"))

    installed, messages = fetch(tmp_path, "pstack:core")

    assert "tdd" in installed
    assert any("curated pstack core" in m for m in messages)


def test_a_named_pstack_skill_is_fetched_and_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_github(monkeypatch, listing=[{"name": "fresh", "type": "dir"}], files={"fresh": "# Fresh skill\n"})
    monkeypatch.setenv("GITHUB_TOKEN", "token-for-the-test")

    installed, messages = fetch(tmp_path, "pstack:fresh")

    assert "fresh" in installed
    assert (tmp_path / "skills" / "fresh" / "SKILL.md").read_text(encoding="utf-8") == "# Fresh skill\n"
    assert any("Successfully fetched 'fresh'" in m for m in messages)


def test_asking_for_a_skill_pstack_does_not_have_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_github(monkeypatch, listing=[{"name": "fresh", "type": "dir"}], files={})

    _, messages = fetch(tmp_path, "pstack:missing")

    assert any("'missing' not found" in m for m in messages)


def test_one_skill_failing_to_download_keeps_the_bundled_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_github(monkeypatch, listing=[{"name": "fresh", "type": "dir"}, {"name": "broken", "type": "dir"}], files={"fresh": "# ok\n"})

    installed, messages = fetch(tmp_path, "pstack:all")

    assert "fresh" in installed and "broken" not in installed
    assert any("Failed to fetch 'broken'" in m for m in messages)


def test_the_whole_listing_failing_keeps_the_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", down)

    installed, messages = fetch(tmp_path, "pstack:fresh")

    assert "tdd" in installed
    assert any("Remote fetch from pstack failed" in m for m in messages)
