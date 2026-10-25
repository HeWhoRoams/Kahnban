"""A scripted worker, started by ``kahnban run`` exactly like a real agent.

    python agent.py POLICY

Role, ticket and project root come from the KAHNBAN_* environment the runner sets. What the
agent should produce comes from the plan file named by KAHNBAN_SIM_PLAN. Every shell command
goes through ``kahnban guard`` first, as a harness hook would, so a refusal is logged by the
guard itself and the command does not run.

Policies: honest, sloppy (wrong first attempt), idle (does nothing), strict and rubber
(reviewers), and ``cheat-*``: try the cheat on the first turn, then work honestly.
A file named ``policy-<role>`` in KAHNBAN_SIM_DIR overrides the policy (a human changing
the instructions between runs).
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
SIM_DIR = Path(os.environ["KAHNBAN_SIM_DIR"])
_override = SIM_DIR / f"policy-{ROLE}"
PROMPT = sys.stdin.read()
PLAN = json.loads(Path(os.environ["KAHNBAN_SIM_PLAN"]).read_text(encoding="utf-8"))
SPEC = PLAN["tickets"].get(TICKET, {})
POLICY = SPEC.get(f"policy_{ROLE}") or (sys.argv[1] if len(sys.argv) > 1 else "honest")
if _override.exists():
    POLICY = _override.read_text(encoding="utf-8").strip()
PY = sys.executable
KAHNBAN = f'{PY} -m kahnban --project-root "{ROOT}"'


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


def attempt_cheat(kind: str, command: str, cwd: Path | None = None) -> None:
    """Try a forbidden command and record how it ended: guard, gate or passed (a failure of the engine)."""
    done = tool(command, cwd)
    result = "guard" if done is None else ("gate" if done.returncode != 0 else "passed")
    note(event="cheat", kind=kind, result=result)


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
    files = dict(SPEC["files"])
    module, check = list(files)[0], list(files)[1]
    if POLICY == "idle":
        return
    if POLICY == "sloppy" and turn == 1:
        files = {path: text.replace("return 2", "return 3") for path, text in files.items()}
    if turn == 1 and POLICY == "cheat-radius":
        note(event="cheat", kind="radius", result="pending")
        files["src/other.py"] = "smuggled = True\n"
    if turn == 1 and POLICY == "cheat-noop-test":
        note(event="cheat", kind="noop-test", result="pending")
        files = {check: "print('ok')\n"}
    if turn == 1 and POLICY == "cheat-tamper":
        edit = f"import glob; open(glob.glob('plans/tickets/*/{TICKET}-*.md')[0], 'a').write('\\n- [x] nothing needed\\n')"
        note(event="cheat", kind="tamper", result="pending")
        tool(f'{PY} -c "{edit}"')
    if turn == 1 and POLICY == "cheat-role":
        attempt_cheat("role", f"env -u KAHNBAN_ROLE {KAHNBAN} approve {TICKET} --reviewer sneaky", ROOT)
    if turn == 1 and POLICY == "cheat-force":
        attempt_cheat("force", f'{KAHNBAN} move {TICKET} 5-done --reason "ship it"', ROOT)
    if turn > 1 and POLICY == "cheat-radius":
        tool("git rm -q -f src/other.py")
    commit_work(files)


def qa_reviewer() -> None:
    turn = attempt()
    if POLICY == "cheat-self-approve" and turn == 1:
        attempt_cheat("self-approve", f"{KAHNBAN} approve {TICKET} --reviewer coder-agent", ROOT)
        return
    if POLICY == "strict" and turn == 1:
        tool(f'{KAHNBAN} reject {TICKET} --reviewer qa-bot -m "tighten the edge cases"', ROOT)
        return
    if POLICY == "rubber":
        tool(f"{KAHNBAN} approve {TICKET} --reviewer qa-bot", ROOT)
        return
    checked = tool(SPEC["validation"], ROOT / ".worktrees" / TICKET)
    if checked is not None and checked.returncode == 0:
        tool(f"{KAHNBAN} approve {TICKET} --reviewer qa-bot", ROOT)
    else:
        tool(f'{KAHNBAN} reject {TICKET} --reviewer qa-bot -m "the ticket check fails on the branch"', ROOT)


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
    tool(f"{KAHNBAN} ready {TICKET}", ROOT)


ROLES = {"coder": coder, "qa_reviewer": qa_reviewer, "spec_analyst": spec_analyst}


if __name__ == "__main__":
    note(event="turn", prompt_bytes=len(PROMPT.encode("utf-8")))
    ROLES.get(ROLE, lambda: None)()
    print(ROLE, POLICY, "finished")
