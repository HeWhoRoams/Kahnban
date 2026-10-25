"""A scripted worker, started by ``kahnban run`` exactly like a real agent.

    python agent.py POLICY

Role, ticket and project root come from the KAHNBAN_* environment the runner sets. What the
agent should produce comes from the plan file named by KAHNBAN_SIM_PLAN. Every shell command
goes through ``kahnban guard`` first, as a harness hook would, so a refusal is logged by the
guard itself and the command does not run.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROLE = os.environ["KAHNBAN_ROLE"]
TICKET = os.environ.get("KAHNBAN_TICKET", "")
ROOT = Path(os.environ["KAHNBAN_PROJECT_ROOT"])
POLICY = sys.argv[1] if len(sys.argv) > 1 else "honest"
PROMPT = sys.stdin.read()
PLAN = json.loads(Path(os.environ["KAHNBAN_SIM_PLAN"]).read_text(encoding="utf-8"))
SPEC = PLAN["tickets"].get(TICKET, {})
SIM_DIR = Path(os.environ["KAHNBAN_SIM_DIR"])
PY = sys.executable


def note(**entry: object) -> None:
    with (SIM_DIR / "agent-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"role": ROLE, "ticket": TICKET, "policy": POLICY, **entry}) + "\n")


def attempt() -> int:
    """1 on this worker's first turn for this ticket, 2 on its second, and so on."""
    counter = SIM_DIR / f"turns-{ROLE}-{TICKET or 'none'}"
    turn = (int(counter.read_text()) if counter.exists() else 0) + 1
    counter.write_text(str(turn))
    return turn


def tool(command: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    """Run a shell command the way a harness would: the guard sees it first. None if refused."""
    where = cwd or Path.cwd()
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(where)})
    verdict = subprocess.run(
        [PY, "-m", "kahnban", "guard"], input=payload, capture_output=True, text=True, cwd=str(where)
    )
    if verdict.returncode == 2:
        note(event="refused", command=command, reason=verdict.stderr.strip()[:200])
        return None
    return subprocess.run(command, shell=True, cwd=str(where), capture_output=True, text=True)


def kahnban(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    quoted = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
    return tool(f'{PY} -m kahnban --project-root "{ROOT}" {quoted}', cwd or ROOT)


def write_files(files: dict[str, str]) -> None:
    for relative, text in files.items():
        target = Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def commit_work(files: dict[str, str]) -> None:
    write_files(files)
    tool("git add -A")
    tool('git commit -qm "work"')


def coder() -> None:
    turn = attempt()
    files = SPEC["files"]
    if POLICY == "sloppy" and turn == 1:
        files = {path: text.replace("return 2", "return 3") for path, text in files.items()}
    commit_work(files)


def qa_reviewer() -> None:
    tree = ROOT / ".worktrees" / TICKET
    checked = tool(SPEC["validation"], tree)
    if checked is not None and checked.returncode == 0:
        kahnban("approve", TICKET, "--reviewer", "qa-bot")
    else:
        kahnban("reject", TICKET, "--reviewer", "qa-bot", "-m", "the ticket's own check fails on the branch")


def spec_analyst() -> None:
    kahnban_core = __import__("kahnban.core", fromlist=["core"])
    frontmatter = __import__("kahnban.frontmatter", fromlist=["frontmatter"])
    path = glob.glob(str(ROOT / "plans" / "tickets" / "*" / f"{TICKET}-*.md"))[0]
    fields, body = frontmatter.parse(Path(path).read_text(encoding="utf-8"))
    spec = SPEC["spec"]
    body = kahnban_core.replace_section(body, "Acceptance criteria", spec["criteria"])
    body = kahnban_core.replace_section(body, "Blast radius", spec["radius"])
    body = kahnban_core.replace_section(body, "Validation", f"```\n{spec['validation']}\n```")
    Path(path).write_text(frontmatter.serialize(fields, body), encoding="utf-8")
    kahnban("ready", TICKET)


ROLES = {"coder": coder, "qa_reviewer": qa_reviewer, "spec_analyst": spec_analyst}


if __name__ == "__main__":
    note(event="turn", prompt_bytes=len(PROMPT.encode("utf-8")))
    ROLES.get(ROLE, lambda: None)()
    print(ROLE, POLICY, "finished")
