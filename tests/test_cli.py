from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from kahnban import __version__, core, gitops
from kahnban.cli import main
from conftest import git, refine_ticket, write_ticket


def run(argv: list[str], board: Path | None = None) -> int:
    if board is not None:
        argv = ["--project-root", str(board), *argv]
    return main(argv)


def commit_board(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "board fixture")


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"kahnban {__version__}\n"


def test_bare_invocation_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    assert "usage: kahnban" in capsys.readouterr().out


def test_missing_board_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["lint"], tmp_path) == 2

    assert "kahnban init" in capsys.readouterr().err


def test_lint_exit_codes(board: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "clean")
    commit_board(board)

    assert run(["lint"], board) == 0
    assert "[OK]" in capsys.readouterr().out

    write_ticket(config.board_path, "0-backlog", "TST-002", "drifted", status="ready")
    commit_board(board)

    assert run(["lint"], board) == 1
    captured = capsys.readouterr().out
    assert "[FAIL] BL04" in captured
    assert captured.isascii()


def test_lint_json_mode(board: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "drifted", status="done")
    commit_board(board)

    assert run(["lint", "--json"], board) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["violations"][0]["rule"] == "BL04"


def test_lint_accepts_an_explicit_config_path(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(board / "plans" / "board.config.json"), "lint"]) == 0
    assert "[OK]" in capsys.readouterr().out


def test_new_ready_and_sync_round_trip(board: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["new", "Add a targeting panel", "--problem", "No panel today."], board) == 0
    out = capsys.readouterr().out
    assert "TST-001" in out

    config = core.load_config(board)
    refine_ticket(config, "TST-001", blast_radius=("src/panel.py",))

    assert run(["move", "TST-001", "1-refining", "--reason", "refining now"], board) == 0
    assert run(["ready", "TST-001"], board) == 0
    assert core.find_ticket(config, "TST-001").column == "2-ready"

    assert run(["sync"], board) == 0
    assert "STATUS.md" in capsys.readouterr().out


def test_new_reads_the_problem_from_a_file(board: Path, tmp_path: Path) -> None:
    problem = tmp_path / "problem.txt"
    problem.write_text("Long problem statement.\nSecond line.\n", encoding="utf-8")

    assert run(["new", "From a file", "--problem-file", str(problem)], board) == 0

    config = core.load_config(board)
    _, body = core.frontmatter.parse(core.read_text(core.find_ticket(config, "TST-001").path))
    assert "Second line." in core.section(body, "Problem")


def test_move_requires_a_reason(board: Path) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    with pytest.raises(SystemExit):
        run(["move", "TST-001", "1-refining"], board)


def test_claim_verify_and_done_via_cli(board: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "example",
        blast_radius=("src/feature.py",),
    )
    commit_board(board)

    assert run(["claim", "TST-001", "--owner", "agent-a", "--worktree"], board) == 0
    assert "3-in-progress" in capsys.readouterr().out

    tree = board / ".worktrees" / "TST-001"
    (tree / "src").mkdir(parents=True, exist_ok=True)
    (tree / "src" / "feature.py").write_text("ok = 1\n", encoding="utf-8")
    git(tree, "add", "-A")
    git(tree, "commit", "-m", "ticket work")

    assert run(["verify", "TST-001"], board) == 0
    out = capsys.readouterr().out
    assert "git version" in out
    assert "4-verifying" in out

    ticket = core.find_ticket(config, "TST-001")
    core.write_text(ticket.path, core.read_text(ticket.path).replace("- [ ]", "- [x]"))
    git(board, "add", "-A")
    git(board, "commit", "-m", "check the boxes")

    assert run(["done", "TST-001"], board) == 1  # branch not merged yet
    assert "not merged" in capsys.readouterr().err

    git(board, "merge", "--no-ff", "-m", "merge ticket", "ticket/TST-001")
    assert run(["done", "TST-001"], board) == 0
    assert run(["cleanup", "TST-001"], board) == 0
    assert not gitops.branch_exists(board, "ticket/TST-001")


def test_verify_failure_exits_one_and_reports_output(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-001",
        "example",
        validation="git rev-parse --verify no-such-ref",
    )
    commit_board(board)
    assert run(["claim", "TST-001", "--owner", "agent", "--no-worktree"], board) == 0
    capsys.readouterr()

    assert run(["verify", "TST-001"], board) == 1

    captured = capsys.readouterr()
    assert "validation exited" in captured.err
    assert core.find_ticket(config, "TST-001").column == "3-in-progress"


def test_claim_overlap_refusal_exits_one(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = core.load_config(board)
    write_ticket(
        config.board_path,
        "3-in-progress",
        "TST-001",
        "busy",
        owner="agent-a",
        branch="ticket/TST-001",
        blast_radius=("src/ui/",),
    )
    write_ticket(
        config.board_path,
        "2-ready",
        "TST-002",
        "wants-ui",
        blast_radius=("src/ui/panel.py",),
    )
    commit_board(board)

    assert run(["claim", "TST-002", "--owner", "agent-b", "--no-worktree"], board) == 1

    assert "overlaps" in capsys.readouterr().err


def test_status_command_summarizes_the_board(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = core.load_config(board)
    write_ticket(config.board_path, "0-backlog", "TST-001", "example")
    commit_board(board)

    assert run(["status"], board) == 0

    out = capsys.readouterr().out
    assert "0-backlog=1" in out
    assert "0 violation(s)" in out


def test_init_scaffolds_a_board_in_a_fresh_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from conftest import init_repo

    repo = init_repo(tmp_path / "adopter")

    assert main(["--project-root", str(repo), "init", "--prefix", "hoa"]) == 0

    out = capsys.readouterr().out
    assert "prefix HOA" in out
    config = core.load_config(repo)
    assert config.id_prefix == "HOA"
    assert (config.board_path / "template.md").is_file()
    for column in config.columns:
        assert (config.board_path / column / ".gitkeep").is_file()
    assert ".worktrees/" in (repo / ".gitignore").read_text(encoding="utf-8")
    assert (repo / "plans" / "STATUS.md").is_file()
    assert gitops.status_porcelain(repo) == []

    assert main(["--project-root", str(repo), "init", "--prefix", "HOA"]) == 2
    assert "already initialized" in capsys.readouterr().err


def test_init_refuses_a_directory_that_is_not_a_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--project-root", str(tmp_path), "init", "--prefix", "XYZ"]) == 2

    assert "not a git repository" in capsys.readouterr().err


def test_engine_version_gate_reports_the_upgrade_command(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = board / "plans" / "board.config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["engine_min_version"] = "99.0.0"
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    assert run(["lint"], board) == 2

    assert "pip install --upgrade kahnban" in capsys.readouterr().err


def test_module_entry_point_runs(board: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "kahnban", "--project-root", str(board), "lint"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert "[OK]" in completed.stdout


def test_board_flags_work_before_and_after_the_subcommand(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """plan.md §6.2 calls `kahnban lint --config <path>` — after the subcommand."""
    config_path = str(board / "plans" / "board.config.json")

    assert main(["--config", config_path, "lint"]) == 0
    assert "[OK]" in capsys.readouterr().out

    assert main(["lint", "--config", config_path]) == 0
    assert "[OK]" in capsys.readouterr().out

    assert main(["status", "--project-root", str(board)]) == 0
    assert "Columns:" in capsys.readouterr().out


def test_subcommand_flags_do_not_clobber_the_global_ones(
    board: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unspecified subcommand flag must not erase a value given globally."""
    assert main(["--project-root", str(board), "lint", "--strict"]) == 0

    assert "[OK]" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["new", "A ticket"],
        ["capture", "An idea"],
        ["sync"],
        ["status"],
    ],
)
def test_every_board_subcommand_accepts_project_root_in_place(
    board: Path, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*argv, "--project-root", str(board)]) == 0

    capsys.readouterr()
