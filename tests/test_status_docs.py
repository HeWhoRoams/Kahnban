"""Status docs must not make claims that go stale on their own.

- no hard-coded test counts (the number drifts every time a test is added)
- no claim that `kahnban run` is sequential / one-ticket-at-a-time (parallel
  workers are an explicit roadmap item, and the loop's concurrency is an
  implementation detail that changes without the docs being updated)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["implementation_status.md", "next_steps.md"]

# A number followed by "tests" is a stale claim ("343 tests"); a path like
# `tests\run_parallel.py` after a flag such as `-3` is not, so exclude a
# trailing path separator.
TEST_COUNT_RE = re.compile(r"\b\d+\s+tests\b(?![\\/])", re.IGNORECASE)
SEQUENTIAL_RE = re.compile(
    r"\bone ticket at a time\b|\bsequential(ly)?\b|\bone[- ]ticket\b", re.IGNORECASE
)


def _text(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_no_test_count():
    for name in DOCS:
        text = _text(name)
        match = TEST_COUNT_RE.search(text)
        assert not match, f"{name} states a hard-coded test count: {match.group(0)!r}"


def test_no_sequential_claim():
    for name in DOCS:
        text = _text(name)
        match = SEQUENTIAL_RE.search(text)
        assert not match, (
            f"{name} describes `kahnban run` as sequential/one-ticket-at-a-time: "
            f"{match.group(0)!r}"
        )
