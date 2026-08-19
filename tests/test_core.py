from __future__ import annotations

import json
from pathlib import Path

import pytest

from kahnban import core, frontmatter, gitops
from conftest import git, scaffold_board, write_ticket


def commit_board(repo: Path, message: str = "board fixture") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def load(repo: Path) -> core.Config:
    return core.load_config(repo)


# --- configuration ----------------------------------------------------------


def test_load_config_reads_the_documented_fields(board: Path) -> None:
    config = load(board)

    assert config.id_prefix == "TST"
    assert config.project_root == board.resolve()
    assert config.board_path == board.resolve() / "plans" / "tickets"
    assert config.done_column == "5-done"
    assert config.status_for("3-in-progress") == "in-progress"
    assert config.in_progress_column == "3-in-progress"


def test_load_config_refuses_an_older_engine(board: Path) -> None:
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["engine_min_version"] = "99.0.0"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(core.ConfigError, match="pip install --upgrade"):
        load(board)


def test_load_config_without_a_board_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(core.ConfigError, match="kahnban init"):
        core.load_config(tmp_path)


def test_load_config_from_a_worktree_resolves_the_main_worktree(board: Path) -> None:
    gitops.branch(board, "ticket/TST-900", "main")
    linked = board / ".worktrees" / "TST-900"
    gitops.worktree_add(board, linked, "ticket/TST-900")

    config = core.load_config(linked)

    assert config.project_root == board.resolve()


# --- lookup and identity ----------------------------------------------------


def test_find_ticket_matches_ids_exactly_not_by_substring(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-1", "small")
    write_ticket(config.board_path, "0-backlog", "TST-10", "larger")
    commit_board(board)

    assert core.find_ticket(config, "TST-1").path.name == "TST-1-small.md"
    assert core.find_ticket(config, "TST-10").path.name == "TST-10-larger.md"
    assert core.find_ticket(config, "tst-10").path.name == "TST-10-larger.md"


def test_find_ticket_raises_for_unknown_ids(board: Path) -> None:
    with pytest.raises(core.TicketNotFoundError):
        core.find_ticket(load(board), "TST-404")


def test_next_id_scans_columns_and_archive(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "5-done", "TST-004", "done-work")
    write_ticket(config.board_path, "archive", "TST-009", "retired")
    commit_board(board)

    assert core.next_id(config) == "TST-010"


def test_next_id_rolls_past_three_digits(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-999", "last-of-three")
    commit_board(board)

    assert core.next_id(config) == "TST-1000"


def test_next_id_on_an_empty_board(board: Path) -> None:
    assert core.next_id(load(board)) == "TST-001"


# --- body helpers -----------------------------------------------------------


def test_blast_radius_parsing_and_overlap() -> None:
    body = "## Blast radius\n- `src/ui/panel.py`\n- game/combat/\n\n## Log\n- x\n"

    radius = core.parse_blast_radius(body)

    assert radius == ["src/ui/panel.py", "game/combat"]
    assert core.paths_overlap("src/ui/panel.py", "src/ui")
    assert core.paths_overlap("game/combat", "game/combat/targeting.gd")
    assert not core.paths_overlap("src/ui/panel.py", "src/ui_helpers.py")
    assert core.path_within("game/combat/targeting.gd", radius)
    assert not core.path_within("game/ai/brain.gd", radius)


def test_checkbox_counting_is_section_scoped() -> None:
    body = (
        "## Acceptance criteria\n- [x] done\n- [ ] pending\n\n"
        "## Implementation notes\n- [ ] not a criterion\n"
    )

    assert core.checkboxes(body) == (1, 1)


def test_validation_command_prefers_the_ticket_fence(board: Path) -> None:
    config = load(board)
    body = "## Validation\n```\npytest -q\n```\n\n## Log\n- x\n"

    assert core.validation_command(config, body) == "pytest -q"


def test_validation_command_falls_back_to_config(board: Path) -> None:
    scaffolded = core.load_config(board)
    config = core.Config(
        project_root=scaffolded.project_root,
        path=scaffolded.path,
        validation_command="ctest",
    )

    assert core.validation_command(config, "## Validation\n\n## Log\n- x\n") == "ctest"


def test_validation_command_missing_is_a_gate_error(board: Path) -> None:
    with pytest.raises(core.GateError, match="no validation command"):
        core.validation_command(load(board), "## Log\n- x\n")


def test_extension_problems_covers_enum_required_and_log_match(board: Path) -> None:
    scaffolded = core.load_config(board)
    config = core.Config(
        project_root=scaffolded.project_root,
        path=scaffolded.path,
        extensions={
            "validation_class": {
                "enum": ["headless-verified", "visual-deferred"],
                "required_from": "2-ready",
            },
            "balance_risk": {
                "enum": ["yes", "no"],
                "required_from": "2-ready",
                "when": {
                    "equals": "yes",
                    "from_column": "4-verifying",
                    "require_log_match": "(?i)prediction",
                },
            },
        },
    )
    body = "## Log\n- 2026-08-18 10:00 - claimed\n"

    assert core.extension_problems(config, {"validation_class": "headless-verified"}, body, "0-backlog") == []

    missing = core.extension_problems(config, {}, body, "2-ready")
    assert any("validation_class" in problem for problem in missing)

    bad_enum = core.extension_problems(
        config, {"validation_class": "guessed", "balance_risk": "no"}, body, "2-ready"
    )
    assert any("is not one of" in problem for problem in bad_enum)

    conditional = core.extension_problems(
        config,
        {"validation_class": "headless-verified", "balance_risk": "yes"},
        body,
        "4-verifying",
    )
    assert any("require" in problem and "Log" in problem for problem in conditional)

    satisfied = core.extension_problems(
        config,
        {"validation_class": "headless-verified", "balance_risk": "yes"},
        "## Log\n- 2026-08-18 10:00 - prediction recorded\n",
        "4-verifying",
    )
    assert satisfied == []


def test_extension_log_match_ignores_the_rest_of_the_body(board: Path) -> None:
    scaffolded = core.load_config(board)
    config = core.Config(
        project_root=scaffolded.project_root,
        path=scaffolded.path,
        extensions={
            "balance_risk": {
                "when": {
                    "equals": "yes",
                    "from_column": "4-verifying",
                    "require_log_match": "(?i)prediction",
                }
            }
        },
    )
    body = "## Problem\nThe prediction lives here, not in the Log.\n\n## Log\n- moved\n"

    problems = core.extension_problems(config, {"balance_risk": "yes"}, body, "4-verifying")

    assert problems


# --- locking ----------------------------------------------------------------


def test_board_lock_is_exclusive_and_released(board: Path) -> None:
    config = load(board)

    with core.board_lock(config):
        assert (config.board_path / core.LOCK_NAME).exists()
        with pytest.raises(core.LockError, match="locked by another"):
            with core.board_lock(config):
                pass

    assert not (config.board_path / core.LOCK_NAME).exists()


def test_board_lock_breaks_a_stale_lock_with_a_warning(board: Path) -> None:
    config = load(board)
    lock_path = config.board_path / core.LOCK_NAME
    lock_path.write_text("pid=1 at=old\n", encoding="utf-8")

    with core.board_lock(config, stale_seconds=0) as warnings:
        assert any("stale" in warning for warning in warnings)


# --- transitions ------------------------------------------------------------


def test_create_ticket_allocates_ids_and_commits(board: Path) -> None:
    config = load(board)

    first = core.create_ticket(config, "Add targeting UI", problem="No UI today.")
    second = core.create_ticket(config, "Second ticket")

    assert first.ticket_id == "TST-001"
    assert first.path.name == "TST-001-add-targeting-ui.md"
    assert second.ticket_id == "TST-002"
    fields, body = frontmatter.parse(core.read_text(first.path))
    assert fields["id"] == "TST-001"
    assert fields["title"] == "Add targeting UI"
    assert fields["status"] == "backlog"
    assert "No UI today." in core.section(body, "Problem")
    assert "created -> 0-backlog" in core.section(body, "Log")
    assert gitops.status_porcelain(board) == []
    assert (board / "plans" / "STATUS.md").exists()
    assert (board / "plans" / "status.json").exists()


def test_transition_commits_on_the_default_branch_and_regenerates_projections(
    board: Path,
) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    result = core.transition(config, "TST-001", "1-refining", log_entry="moved by test")

    assert result.from_column == "0-backlog"
    assert result.to_column == "1-refining"
    assert result.path == config.board_path / "1-refining" / "TST-001-example.md"
    assert not (config.board_path / "0-backlog" / "TST-001-example.md").exists()
    fields, body = frontmatter.parse(core.read_text(result.path))
    assert fields["status"] == "refining"
    assert "moved by test" in core.section(body, "Log")

    subject = git(board, "log", "-1", "--pretty=%s").stdout.strip()
    assert subject == "kanban(TST-001): 0-backlog -> 1-refining"
    changed = git(board, "show", "--name-only", "--pretty=format:", "HEAD").stdout
    assert "plans/STATUS.md" in changed
    assert "plans/status.json" in changed
    assert gitops.current_branch(board) == "main"
    assert gitops.status_porcelain(board) == []


def test_transition_refuses_when_a_ticket_branch_is_checked_out(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)
    gitops.branch(board, "ticket/TST-001", "main")
    git(board, "checkout", "ticket/TST-001")

    with pytest.raises(core.GateError, match="default branch"):
        core.transition(config, "TST-001", "1-refining", log_entry="nope")


def test_transition_rejects_unknown_columns(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="unknown target column"):
        core.transition(config, "TST-001", "9-nowhere", log_entry="nope")


def test_transition_never_rewrites_body_prose(board: Path) -> None:
    config = load(board)
    path = write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    text = core.read_text(path)
    text = text.replace(
        "## Problem\nSomething needs doing.",
        "## Problem\nDocumented example: status: backlog owner: unassigned",
    )
    core.write_text(path, text)
    commit_board(board)

    result = core.transition(config, "TST-001", "1-refining", log_entry="moved")

    _, body = frontmatter.parse(core.read_text(result.path))
    assert "status: backlog owner: unassigned" in core.section(body, "Problem")


# --- ready gate -------------------------------------------------------------


def test_ready_gate_passes_a_refined_ticket(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    commit_board(board)

    result = core.ready(config, "TST-001")

    assert result.to_column == "2-ready"


def test_ready_gate_refuses_missing_criteria_and_radius(board: Path) -> None:
    config = load(board)
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-001",
        "example",
        acceptance=("- nothing checkable",),
        blast_radius=(),
    )
    commit_board(board)

    with pytest.raises(core.GateError) as error_info:
        core.ready(config, "TST-001")

    message = str(error_info.value)
    assert "Acceptance criteria" in message
    assert "Blast radius" in message


def test_ready_gate_refuses_blocked_and_unfinished_dependencies(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "dependency")
    write_ticket(
        config.board_path,
        "1-refining",
        "TST-002",
        "example",
        depends_on="[TST-001, TST-404]",
        blocked_on="waiting on design",
    )
    commit_board(board)

    with pytest.raises(core.GateError) as error_info:
        core.ready(config, "TST-002")

    message = str(error_info.value)
    assert "blocked_on" in message
    assert "TST-001" in message and "0-backlog" in message
    assert "TST-404" in message and "does not exist" in message


def test_ready_gate_accepts_dependencies_in_the_done_column(board: Path) -> None:
    config = load(board)
    write_ticket(config.board_path, "5-done", "TST-001", "dependency")
    write_ticket(
        config.board_path, "1-refining", "TST-002", "example", depends_on="[TST-001]"
    )
    commit_board(board)

    assert core.ready(config, "TST-002").to_column == "2-ready"


def test_ready_gate_enforces_extension_required_from(board: Path) -> None:
    scaffold_overrides = {
        "extensions": {
            "validation_class": {
                "enum": ["headless-verified", "visual-deferred"],
                "required_from": "2-ready",
            }
        }
    }
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload.update(scaffold_overrides)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    config = load(board)
    write_ticket(config.board_path, "1-refining", "TST-001", "example")
    commit_board(board)

    with pytest.raises(core.GateError, match="validation_class"):
        core.ready(config, "TST-001")
