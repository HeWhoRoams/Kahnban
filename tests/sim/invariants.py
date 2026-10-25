"""The rules the workflow promises, checked after every step and again at the end."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from kahnban import core, frontmatter, gitops, linter

INVARIANTS = {
    "I1": "lint is clean after every step",
    "I2": "every ticket is in exactly one column and its status matches",
    "I3": "a commit moves at most one ticket between columns",
    "I4": "a done ticket's merge is on the default branch",
    "I5": "the approved commit is the verified commit and is in the merge",
    "I6": "validation passes at every commit the run landed",
    "I8": "the reviewer is never the owner",
    "I9": "no two in-progress tickets overlap in blast radius",
    "I10": "a done ticket leaves no worktree, branch or lease behind",
    "I11": "a second run on an idle board changes nothing",
}


class Checker:
    def __init__(self, config: core.Config, plan: dict[str, Any]) -> None:
        self.config = config
        self.repo = config.project_root
        self.plan = plan
        self.branch = gitops.default_branch(self.repo)
        self.head = gitops.rev_parse(self.repo, self.branch)
        self.step = 0
        self.violations: dict[str, list[str]] = {key: [] for key in INVARIANTS}
        self.evaluated: Counter[str] = Counter()

    def fail(self, invariant: str, message: str) -> None:
        self.violations[invariant].append(f"step {self.step}: {message}")

    def _fields(self, ticket: core.Ticket) -> tuple[dict[str, Any], str]:
        fields, body = frontmatter.parse(ticket.text)
        return dict(fields), body

    def commits_since(self, old: str) -> list[str]:
        out = gitops.run(self.repo, ["rev-list", "--reverse", f"{old}..{self.branch}"]).stdout
        return out.split()

    # --- after every step ------------------------------------------------------

    def after_step(self, line: str = "") -> None:
        self.step += 1
        self._lint()
        self._columns()
        self._moves()
        self._reviewers()
        self._overlaps()
        self.head = gitops.rev_parse(self.repo, self.branch)

    def _lint(self) -> None:
        self.evaluated["I1"] += 1
        for finding in linter.lint(self.config).violations:
            self.fail("I1", f"{finding.rule} {finding.ticket}: {finding.message}")

    def _columns(self) -> None:
        self.evaluated["I2"] += 1
        seen: Counter[str] = Counter()
        for ticket in core.iter_tickets(self.config):
            seen[ticket.ticket_id] += 1
            status = str(self._fields(ticket)[0].get("status") or "")
            head, _, tail = ticket.column.partition("-")
            expected = tail if tail and head.isdigit() else ticket.column
            if status != expected:
                self.fail("I2", f"{ticket.ticket_id} is in {ticket.column} but says status: {status}")
        for ident, count in seen.items():
            if count > 1:
                self.fail("I2", f"{ident} exists in {count} columns")

    def _moves(self) -> None:
        self.evaluated["I3"] += 1
        out = gitops.run(
            self.repo,
            ["log", "--name-status", "-M", "--format=@%H", f"{self.head}..{self.branch}"],
        ).stdout
        moved = Counter[str]()
        commit = ""
        for row in out.splitlines():
            if row.startswith("@"):
                commit = row[1:]
            elif row.startswith("R") and self.config.board_root in row:
                moved[commit] += 1
        for sha, count in moved.items():
            if count > 1:
                self.fail("I3", f"commit {sha[:10]} moved {count} tickets")

    def _reviewers(self) -> None:
        self.evaluated["I8"] += 1
        for ticket in core.iter_tickets(self.config):
            fields, _ = self._fields(ticket)
            reviewer, owner = str(fields.get("reviewer") or ""), str(fields.get("owner") or "")
            if reviewer and reviewer.lower() == owner.lower():
                self.fail("I8", f"{ticket.ticket_id} was reviewed by its owner {owner}")

    def _overlaps(self) -> None:
        self.evaluated["I9"] += 1
        radii = {
            ticket.ticket_id: core.parse_blast_radius(self._fields(ticket)[1])
            for ticket in core.iter_tickets(self.config)
            if ticket.column == self.config.in_progress_column
        }
        names = sorted(radii)
        for i, left in enumerate(names):
            for right in names[i + 1 :]:
                if core.radius_overlaps(radii[left], radii[right]):
                    self.fail("I9", f"{left} and {right} are in progress with overlapping blast radii")

    # --- at the end ----------------------------------------------------------------

    def finalize(self, runner: Any) -> None:
        done = [t for t in core.iter_tickets(self.config) if t.column == self.config.done_column]
        landed: list[tuple[str, str]] = []
        for ticket in done:
            fields, _ = self._fields(ticket)
            integrated = str(fields.get("integrated_sha") or "")
            approved, verified = str(fields.get("approved_sha") or ""), str(fields.get("verified_sha") or "")
            self.evaluated["I4"] += 1
            if not integrated or not gitops.is_ancestor(self.repo, integrated, self.branch):
                self.fail("I4", f"{ticket.ticket_id} is done but its merge is not on {self.branch}")
                continue
            landed.append((ticket.ticket_id, integrated))
            self.evaluated["I5"] += 1
            if not approved or approved != verified or not gitops.is_ancestor(self.repo, approved, integrated):
                self.fail("I5", f"{ticket.ticket_id}: approved {approved[:10]} verified {verified[:10]}")
            self.evaluated["I10"] += 1
            leftovers = []
            if (self.repo / ".worktrees" / ticket.ticket_id).exists():
                leftovers.append("worktree")
            if gitops.branch_exists(self.repo, f"ticket/{ticket.ticket_id}"):
                leftovers.append("branch")
            if core.live_lease(self.config, ticket.ticket_id):
                leftovers.append("lease")
            if leftovers:
                self.fail("I10", f"{ticket.ticket_id} left a {', '.join(leftovers)} behind")
        self._replay(landed)
        self._idempotent(runner)

    def _replay(self, landed: list[tuple[str, str]]) -> None:
        """Re-run each landed ticket's validation on the default branch as it stood at each merge."""
        order = gitops.run(self.repo, ["rev-list", "--reverse", self.branch]).stdout.split()
        landed.sort(key=lambda item: order.index(gitops.rev_parse(self.repo, item[1])))
        scratch = Path(tempfile.mkdtemp(prefix="sim-replay-"))
        try:
            for position, (ident, sha) in enumerate(landed):
                tree = scratch / ident
                gitops.run(self.repo, ["worktree", "add", "--detach", str(tree), sha])
                try:
                    for earlier, _ in landed[: position + 1]:
                        self.evaluated["I6"] += 1
                        command = self.plan["tickets"][earlier]["validation"]
                        done = subprocess.run(command, shell=True, cwd=str(tree), capture_output=True, text=True)
                        if done.returncode != 0:
                            self.fail("I6", f"{earlier}'s validation fails at the merge of {ident} ({sha[:10]})")
                finally:
                    gitops.run(self.repo, ["worktree", "remove", "--force", str(tree)], check=False)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def _idempotent(self, runner: Any) -> None:
        self.evaluated["I11"] += 1
        before = gitops.rev_parse(self.repo, self.branch)
        again = runner.run(self.config, max_steps=5, echo=lambda line: None)
        after = gitops.rev_parse(self.repo, self.branch)
        if again.steps or before != after:
            self.fail("I11", f"a second run took {len(again.steps)} step(s) and moved {before[:10]} -> {after[:10]}")

    def summary(self) -> dict[str, dict[str, Any]]:
        return {
            key: {
                "title": INVARIANTS[key],
                "checked": self.evaluated[key],
                "violations": self.violations[key],
                "pass": not self.violations[key],
            }
            for key in INVARIANTS
        }
