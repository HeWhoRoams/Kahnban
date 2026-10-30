from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mit_license() -> None:
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "MIT License" in text
    assert "Tim Niles" in text
    assert "Permission is hereby granted, free of charge" in text


def test_third_party_notices() -> None:
    text = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert "cursor/plugins" in text
    assert "Lauren Tan" in text
    assert "mattpocock/skills" in text
    assert "Matt Pocock" in text
    assert text.count("Permission is hereby granted, free of charge") == 2
