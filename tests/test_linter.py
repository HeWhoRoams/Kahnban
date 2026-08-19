"""Every BL01-BL16 rule is proved by its own negative fixture board."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kahnban import core, gitops, linter
from conftest import git, init_repo

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPECTED_STRICT_ONLY = {"BL12"}


def materialize(fixture: Path, destination: Path, *, as_repo: bool = True) -> Path:
    """Copy a fixture board into a scratch location, optionally as a git repo."""
    shutil.copytree(fixture, destination)
    if as_repo:
        init_repo(destination)
        git(destination, "add", "-A")
        git(destination, "commit", "-m", "fixture board")
    return destination


def lint_fixture(
    name: str, tmp_path: Path, *, strict: bool = False, as_repo: bool = True
) -> linter.LintResult:
    root = materialize(FIXTURES / name, tmp_path / "board", as_repo=as_repo)
    return linter.lint(core.load_config(root), strict=strict)


def rules_of(findings) -> set[str]:
    return {finding.rule for finding in findings}


# --- clean boards -----------------------------------------------------------


@pytest.mark.parametrize("name", ["clean-board", "clean-board-crlf"])
def test_clean_boards_lint_without_violations(name: str, tmp_path: Path) -> None:
    root = materialize(FIXTURES / name, tmp_path / "board")
    # The done ticket's branch is merged, so BL15 resolves without a warning.
    gitops.branch(root, "ticket/TST-006", "main")
    config = core.load_config(root)

    result = linter.lint(config)

    assert result.violations == [], [f.render() for f in result.violations]
    assert result.ok
    assert result.tickets_checked == 6
    assert result.column_counts["archive"] == 1
    unexpected = [f.render() for f in result.warnings if f.rule != "BL15"]
    assert unexpected == []


def test_clean_board_text_output_is_ascii_and_marks_ok(tmp_path: Path) -> None:
    result = lint_fixture("clean-board", tmp_path)

    rendered = linter.render_text(result)

    assert "[OK]" in rendered
    assert "[FAIL]" not in rendered
    rendered.encode("cp1252")  # must survive a Windows console
    assert rendered.isascii()


def test_crlf_and_lf_fixtures_agree(tmp_path: Path) -> None:
    lf = lint_fixture("clean-board", tmp_path / "lf")
    crlf = lint_fixture("clean-board-crlf", tmp_path / "crlf")

    assert [f.as_dict() for f in lf.findings] == [f.as_dict() for f in crlf.findings]


# --- one negative board per rule -------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [f"BL{index:02d}" for index in range(1, 17) if f"BL{index:02d}" != "BL15"],
)
def test_each_negative_fixture_fails_its_own_rule(rule: str, tmp_path: Path) -> None:
    strict = rule in EXPECTED_STRICT_ONLY
    result = lint_fixture(f"violations/{rule}", tmp_path, strict=strict)

    assert rule in rules_of(result.violations), linter.render_text(result)
    assert not result.ok


def test_bl15_flags_a_done_ticket_whose_branch_is_not_merged(tmp_path: Path) -> None:
    root = materialize(FIXTURES / "violations/BL15", tmp_path / "board")
    gitops.branch(root, "ticket/TST-001", "main")
    git(root, "checkout", "ticket/TST-001")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "unmerged.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "unmerged ticket work")
    git(root, "checkout", "main")

    result = linter.lint(core.load_config(root))

    assert "BL15" in rules_of(result.violations)

    git(root, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")
    assert "BL15" not in rules_of(linter.lint(core.load_config(root)).violations)


def test_bl15_accepts_a_recorded_merge_commit_after_cleanup(tmp_path: Path) -> None:
    root = materialize(FIXTURES / "violations/BL15", tmp_path / "board")
    gitops.branch(root, "ticket/TST-001", "main")
    git(root, "checkout", "ticket/TST-001")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "work.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "ticket work")
    git(root, "checkout", "main")
    git(root, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")
    merged_sha = git(root, "rev-parse", "HEAD").stdout.strip()
    gitops.delete_branch(root, "ticket/TST-001", force=True)

    ticket_path = root / "plans" / "tickets" / "5-done" / "TST-001-unmerged.md"
    text = core.read_text(ticket_path)
    text = text.replace('branch: "ticket/TST-001"', 'branch: ""')
    text = text.rstrip("\n") + f"\n- 2026-08-18 13:00 - merge-commit: {merged_sha}\n"
    core.write_text(ticket_path, text)

    result = linter.lint(core.load_config(root))

    assert "BL15" not in rules_of(result.violations)
    assert "BL15" not in rules_of(result.warnings)


# --- rule-specific detail ---------------------------------------------------


def test_bl01_stops_further_checks_for_the_broken_ticket(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL01", tmp_path)

    assert rules_of(result.violations) == {"BL01"}


def test_bl02_names_the_filename_mismatch(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL02", tmp_path)

    messages = [f.message for f in result.violations if f.rule == "BL02"]
    assert any("filename" in message for message in messages)


def test_bl03_reports_both_locations(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL03", tmp_path)

    finding = next(f for f in result.violations if f.rule == "BL03")
    assert "0-backlog/TST-003-first-home.md" in finding.message
    assert "1-refining/TST-003-second-home.md" in finding.message


def test_bl09_reports_missing_and_unfinished_dependencies(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL09", tmp_path)

    messages = " ".join(f.message for f in result.violations if f.rule == "BL09")
    assert "TST-900" in messages and "does not exist" in messages
    assert "TST-001" in messages and "0-backlog" in messages


def test_bl12_is_a_warning_by_default_and_a_violation_under_strict(
    tmp_path: Path,
) -> None:
    lenient = lint_fixture("violations/BL12", tmp_path / "lenient")
    assert "BL12" in rules_of(lenient.warnings)
    assert "BL12" not in rules_of(lenient.violations)
    assert lenient.ok

    strict = lint_fixture("violations/BL12", tmp_path / "strict", strict=True)
    assert "BL12" in rules_of(strict.violations)
    assert not strict.ok


def test_bl13_distinguishes_stray_files_from_subdirectories(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL13", tmp_path)

    messages = [f.message for f in result.violations if f.rule == "BL13"]
    assert any("notes.txt" in message and "non-markdown" in message for message in messages)
    assert any("scratch" in message and "subdirectory" in message for message in messages)


def test_bl16_names_the_overlapping_paths(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL16", tmp_path)

    finding = next(f for f in result.violations if f.rule == "BL16")
    assert "TST-002" in finding.message
    assert "src/ui" in finding.message


# --- exemptions -------------------------------------------------------------


def test_template_and_archive_are_exempt_from_column_invariants(
    tmp_path: Path, board: Path
) -> None:
    config = core.load_config(board)
    template = config.board_path / core.TEMPLATE_NAME
    assert template.is_file(), "the board fixture copies the engine template"
    archived = config.board_path / "archive" / "TST-050-retired.md"
    archived.write_text(
        core.read_text(template).replace("id: TICKET-000", "id: TST-050"),
        encoding="utf-8",
        newline="\n",
    )
    git(board, "add", "-A")
    git(board, "commit", "-m", "archive a retired ticket")

    result = linter.lint(config)

    assert result.violations == [], [f.render() for f in result.violations]


def test_archive_still_participates_in_id_uniqueness(board: Path) -> None:
    config = core.load_config(board)
    from conftest import write_ticket

    write_ticket(config.board_path, "0-backlog", "TST-010", "active")
    write_ticket(config.board_path, "archive", "TST-010", "retired")
    git(board, "add", "-A")
    git(board, "commit", "-m", "duplicate id across archive")

    result = linter.lint(config)

    assert "BL03" in rules_of(result.violations)


# --- machine output ---------------------------------------------------------


def test_json_mode_reports_violations_and_warnings(tmp_path: Path) -> None:
    result = lint_fixture("violations/BL12", tmp_path, strict=False)

    payload = json.loads(linter.render_json(result))

    assert payload["violations"] == []
    assert payload["warnings"]
    assert payload["warnings"][0]["rule"] == "BL12"
    assert payload["board_root"] == "plans/tickets"
    assert payload["column_counts"]["3-in-progress"] == 2


def test_every_documented_rule_has_a_description() -> None:
    assert set(linter.RULES) == {f"BL{index:02d}" for index in range(1, 18)}


def test_fixture_line_endings_are_preserved_on_disk() -> None:
    """The CRLF fixture must really be CRLF, on every platform.

    `.gitattributes` marks `tests/fixtures/**` as `-text` for this reason: with
    autocrlf normalization both fixtures end up identical after a clone and the
    CRLF half of the plan §9 acceptance criterion tests nothing.
    """
    lf = (
        FIXTURES
        / "clean-board"
        / "plans"
        / "tickets"
        / "0-backlog"
        / "TST-001-capture-idea.md"
    ).read_bytes()
    crlf = (
        FIXTURES
        / "clean-board-crlf"
        / "plans"
        / "tickets"
        / "0-backlog"
        / "TST-001-capture-idea.md"
    ).read_bytes()

    assert b"\r\n" not in lf
    assert b"\r\n" in crlf
    assert lf.replace(b"\n", b"\r\n") == crlf
