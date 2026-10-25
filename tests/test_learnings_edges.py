"""Learnings: unreadable records, clustering by path and category, id allocation, and what counts as a defence."""

from __future__ import annotations

from pathlib import Path

import pytest

from kahnban import learnings


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "learnings" / "archive").mkdir(parents=True)
    return tmp_path


def capture(project: Path, title: str, **kwargs: object) -> learnings.LearningRecord:
    record, _ = learnings.capture_learning(
        project,
        title=title,
        problem="it broke",
        ticket_id="T-1",
        location="x.py:1",
        trigger="a trigger",
        today="2026-10-25",
        **kwargs,  # type: ignore[arg-type]
    )
    return record


def test_an_unreadable_learning_is_reported_on_stderr_and_skipped(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capture(project, "A real learning")
    (project / "learnings" / "LRN-9999-broken.md").write_bytes(b"\xff\xfe not a learning")
    (project / "learnings" / "archive" / "LRN-9998-also-broken.md").write_bytes(b"\xff\xfe")

    found = learnings.list_learnings(project, include_archive=True)

    assert [r.title for r in found] == ["A real learning"]
    assert "failed to parse learning" in capsys.readouterr().err


def test_ids_continue_after_the_highest_in_the_queue_or_the_archive(project: Path) -> None:
    (project / "learnings" / "archive" / "LRN-0007-old.md").write_text("x", encoding="utf-8")
    (project / "learnings" / "LRN-0003-live.md").write_text("x", encoding="utf-8")
    (project / "learnings" / "LRN-notanumber.md").write_text("x", encoding="utf-8")

    assert learnings._next_learning_id(project / "learnings") == "LRN-0008"
    assert learnings._next_learning_id(project / "nowhere") == "LRN-0001"


def test_slugs_match_on_equality_or_a_hyphen_boundary_and_never_when_empty() -> None:
    assert learnings._slugify("!!!") == "learning"
    assert learnings._slugify("A Very Long Title " * 10, max_len=20).endswith("-") is False
    assert learnings._slug_matches("cache-race", "cache-race")
    assert learnings._slug_matches("cache-race-in-status", "cache-race")
    assert not learnings._slug_matches("cache", "cachet")
    assert not learnings._slug_matches("", "cache")


def test_a_similar_title_in_the_same_category_and_path_joins_the_existing_learning(project: Path) -> None:
    first = capture(project, "Stale cache entries survive eviction", category="architecture", target_paths=["src/Cache.py"])
    records = learnings.list_learnings(project)

    joined = learnings.find_matching_learning(
        records, title="Cache entries survive after eviction runs", target_paths=["SRC/cache.py"], category="architecture"
    )
    different_category = learnings.find_matching_learning(
        records, title="Cache entries survive after eviction runs", target_paths=["src/cache.py"], category="testing"
    )
    unrelated = learnings.find_matching_learning(
        records, title="Completely different wording here", target_paths=["src/cache.py"], category="architecture"
    )

    assert joined is not None and joined.id == first.id
    assert different_category is None
    assert unrelated is None


def test_a_promotion_needs_a_real_defence(project: Path) -> None:
    capture(project, "Needs a guard")

    for artifact, message in [
        ("", "--artifact is required"),
        ("BL99", "lint rule BL99 does not exist"),
        ("no/such/path.py", "does not exist"),
    ]:
        with pytest.raises(ValueError, match=message):
            learnings.promote_learning(project, "LRN-0001", level="1", artifact=artifact)

    (project / "guard.py").write_text("# the guard\n", encoding="utf-8")
    promoted = learnings.promote_learning(project, "LRN-0001", level="2", artifact="guard.py", today="2026-10-25")

    assert promoted.status == "promoted"
    with pytest.raises(ValueError, match="not found in active"):
        learnings.promote_learning(project, "LRN-0001", level="2", artifact="guard.py")
