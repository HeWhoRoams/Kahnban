# Kahnban — Portable Agentic Kanban Workflow — Implementation Plan

**Status:** ACTIVE PLAN — v4 (post-audit revision)
**Created:** 2026-08-18
**Revised:** 2026-08-18 (v4: audit fixes, pip packaging, machine-run verification, main-branch board state)
**Owner:** Tim Niles
**Engine Repository:** `C:\Github\Kahnban` (this repo — Layer 1 engine, package name `kahnban`)
**First Adopter:** `C:\github\heirs_ancients`
**Second Adopter:** `C:\github\citadel`

---

## 0. Executive Summary & Design Principles

Kahnban is a model-, agent-, IDE-, and harness-agnostic Kanban system for AI
vibe-coding workflows. It provides strict transparency into in-flight agent
tasks, prevents workspace collisions across concurrent LLM sessions, enforces
requirement refinement through machine-checked gates, and maintains a single
source of truth backed by standard Git storage.

### Core Principles

1. **The Filesystem Folder Is the Only Status.** Columns are physical folders
   (`0-backlog` through `5-done`). State transitions require a `git mv`
   **committed to the default branch** so every agent and human sees claims
   immediately. There are no parallel databases, untracked counters, or
   out-of-sync status properties.
2. **Universal Client Surface (MCP + CLI).** Agents interact via a Model
   Context Protocol server or the `kahnban` CLI. Both surfaces call the same
   in-process core; there is exactly one implementation of every transition.
3. **Workspace Isolation via Git Worktrees.** Every active ticket runs its
   *code changes* in an isolated worktree (`.worktrees/<TICKET-ID>`) on a
   dedicated branch (`ticket/<TICKET-ID>`). **Board state never lives on
   ticket branches** — the ticket file itself is moved and committed on the
   default branch (see §3.2 for the split).
4. **Gates Are Enforced by Tooling, Not Convention.** A ticket cannot be
   claimed unless it is in `2-ready` with satisfied dependencies. The tool
   refuses; it does not merely document the rule.
5. **Machine-Run Verification — No Silent Ticking.** `kahnban verify` executes
   the ticket's `## Validation` command itself, captures stdout/stderr and the
   exit code, and blocks the transition on non-zero exit. Agent-pasted
   evidence is not trusted for headless-verifiable work.
6. **Ambient Transparency.** Every transition regenerates `plans/STATUS.md`
   (human projection) and `plans/status.json` (machine projection).

### Non-Goals (v1)

- `dashboard.html` visual board — **deferred to v2**. STATUS.md is the sole
  human-facing projection in v1.
- `kahnban watch` background daemon — **deferred to v2**, and only as an
  observe-only process (see §7 v2 candidates). Automated state transitions
  driven by commit monitoring are rejected outright.
- LLM-based acceptance verification — **rejected, not deferred**:
  non-deterministic, unauditable, and gameable by the agents it would audit.
  Verification is the deterministic execution of `## Validation` (D4).
- Granular sub-tasking below the ticket level — a ticket is the atomic unit
  of work by design.
- Web UI, authentication, multi-repo federation, remote board hosting.
- YAML spec compliance — the frontmatter parser supports the documented
  subset only (scalars, inline lists, block lists; no nesting).

### Decision Log (2026-08-18 audit)

| # | Decision | Rationale |
| :- | :--- | :--- |
| D1 | This repo (`Kahnban`) is the Layer 1 engine; `agent-kanban` name retired | Single home for engine code |
| D2 | Board transitions commit directly to the **default branch** | Fixes the visibility gap: v3 committed claims on ticket branches, so `main` never showed a ticket as claimed until merge, enabling double-claims |
| D3 | Distribution via **pip-installable package** (editable/local or git) | Eliminates vendored-copy drift across adopter repos |
| D4 | `verify` **runs the validation command itself** | Eliminates fabricated evidence; agents cannot silently tick |
| D5 | `dashboard.html` deferred to v2 | Keeps v1 lean; STATUS.md suffices |
| D6 | 6-column model retained; 4-macro-state reduction rejected | Transition overhead is borne by agents (single tool calls), not humans — velocity is preserved without collapsing the `1-refining`/`2-ready` enforcement gates |
| D7 | Blast-radius overlap: hard refuse at claim; diff containment at verify | Worktrees isolate filesystems, not merge targets; overlapping in-flight blast radii are the primary merge-conflict source |
| D8 | JSON is never ground truth; `plans/status.json` added as a read-only projection | Principle 1 — a parallel state file would diverge from the folders |
| D9 | Observe-only `kahnban watch` daemon deferred to v2; LLM-as-judge verification **rejected** | Auto-transitions destroy the audit trail; LLM verification is non-deterministic and gameable by the agents it audits (contradicts D4) |

---

## 1. System Architecture — Four Layers

```
LAYER 1 — Engine (this repo, pip-installable)
Kahnban/
├── pyproject.toml            ← zero runtime deps; pytest is dev-only
├── src/kahnban/
│   ├── __init__.py           ← __version__ (single source of version truth)
│   ├── cli.py                ← argparse entry point (console script `kahnban`)
│   ├── frontmatter.py        ← frontmatter parse/serialize + safe mutation
│   ├── core.py               ← state machine, transitions, ID allocation
│   ├── gitops.py             ← all subprocess git calls, error surfacing
│   ├── worktree.py           ← worktree provision/cleanup, cache junctions
│   ├── linter.py             ← rules BL01–BL17
│   ├── ingest.py             ← plan/idea -> ticket drafts (entry points)
│   ├── status.py             ← STATUS.md projection
│   ├── mcp_server.py         ← stdio JSON-RPC 2.0 MCP server
│   └── templates/ticket.md   ← canonical ticket template
├── tests/                    ← pytest suite + fixtures (see §8)
└── adapters/                 ← client glue: AGENTS.md snippet, .cursorrules,
                                 Copilot prompt file, MCP registration examples

LAYER 0 — Per-Repo Storage Contract (committed to each adopter repo)
/
├── plans/
│   ├── board.config.json     ← prefix, WIP limits, validation cmd, extensions
│   ├── STATUS.md             ← auto-generated projection (read-only)
│   ├── status.json           ← auto-generated machine projection (read-only)
│   └── tickets/
│       ├── template.md       ← copied from engine at init (outside columns)
│       ├── 0-backlog/ … 5-done/   (each with .gitkeep)
│       └── archive/          ← retired tickets; still scanned for ID allocation
└── .worktrees/               ← gitignored (init adds the .gitignore entry)

LAYER 2 — Client & Agent Configs (per adopter repo)
/AGENTS.md, /CLAUDE.md, /.cursorrules, /.github/prompts/ticket.prompt.md,
/.vscode/mcp.json

LAYER 3 — Per-Repo Test Adapter (committed)
/tools/run_all_tests.ps1 (or CI workflow) calling `kahnban lint`
```

### 1.1 Packaging & Distribution (D3)

- `pyproject.toml` declares `[project.scripts] kahnban = "kahnban.cli:main"`.
- Runtime dependencies: **none** (stdlib only). Dev dependencies: `pytest`.
- Minimum Python: **3.10** (matches `py -3` availability on target machines).
- Adopters install with either:
  ```powershell
  py -3 -m pip install -e C:\Github\Kahnban          # local dev, editable
  py -3 -m pip install git+https://<remote>/Kahnban  # pinned by tag in CI
  ```
- `board.config.json` carries `"engine_min_version"`; every CLI/MCP entry
  point compares it against `kahnban.__version__` and refuses to run if the
  installed engine is older, printing the upgrade command.
- Adopter repos contain **no copied engine code**. `tools/run_all_tests.ps1`
  invokes `py -3 -m kahnban lint`.

---

## 2. The Board Contract

### 2.1 Directory Structure & Lifecycle

```
plans/tickets/
├── 0-backlog/     ← Captured, not yet refined. blocked_on items park here.
├── 1-refining/    ← Researching codebase, defining blast radius and tests.
├── 2-ready/       ← Ready for cold pickup. All depends_on in 5-done.
├── 3-in-progress/ ← Claimed by exactly one owner in an isolated worktree.
├── 4-verifying/   ← Validation command ran green; output captured in Log.
├── 5-done/        ← Merged to default branch. All criteria checked.
└── archive/       ← Retired/superseded tickets. IDs remain reserved.
```

### 2.2 Transition Gates (enforced by `kahnban`, verified by `kahnban lint`)

| Transition | Command | Gate (tool refuses unless...) |
| :--- | :--- | :--- |
| create → `0-backlog` | `kahnban new` | Title present; ID allocated from global scan incl. `archive/` |
| `0-backlog` → `1-refining` | `kahnban move` | Frontmatter valid |
| `1-refining` → `2-ready` | `kahnban ready` | ≥1 acceptance checkbox; `## Blast radius` non-empty; `blocked_on` empty; all `depends_on` in `5-done`; extension fields required-from-ready present |
| `2-ready` → `3-in-progress` | `kahnban claim` | Source column is `2-ready` (override: `--force` + logged reason); owner given; WIP < limit (hard fail with `--strict-wip`, else warning); blast radius does not overlap any `3-in-progress` ticket (§3.5, override: `--force-overlap` + logged reason); claim lock acquired (§3.3) |
| `3-in-progress` → `4-verifying` | `kahnban verify` | Tool executes the `## Validation` command; exit code 0; full output + exit code appended to `## Log` (D4); ticket-branch diff confined to `## Blast radius` (§3.5, override: `--force-scope` + logged reason). Tickets with `validation_class: visual-deferred` may pass `--manual-evidence <file>` — the override itself is logged |
| `4-verifying` → `5-done` | `kahnban done` | Ticket branch tip is an ancestor of the default branch (`git merge-base --is-ancestor`), or `--merge-commit <sha>` verified to exist on default branch; all checkboxes `[x]` |
| any → any | `kahnban move --reason` | Escape hatch; always logged; lint still applies column invariants afterward |

Every transition, without exception:
1. Rewrites frontmatter (`status`, `updated`, transition-specific fields) via
   `frontmatter.py` mutation — **never** whole-file regex.
2. Appends a timestamped `## Log` entry.
3. `git mv` + `git add` + `git commit` **on the default branch** with message
   `kanban(<ID>): <from-column> -> <to-column>` (D2).
4. Regenerates `plans/STATUS.md` and `plans/status.json` and includes both in
   the same commit.

### 2.3 Ticket Identity & Naming Rules

- Filename pattern: `<PREFIX>-<NNN>-short-slug.md` (e.g.
  `HOA-007-w4-guidance-targeting.md`).
- IDs are permanent, uppercase, and never reused. Allocation scans **all**
  column directories **and** `archive/` for the highest existing number.
- Numbers are zero-padded to 3 digits and roll naturally to 4+ digits
  (`HOA-999` → `HOA-1000`); tooling must not assume fixed width.
- Ticket lookup matches the ID **exactly** against the filename prefix
  (`^<ID>-`), never by substring (v3 defect: `HOA-1` matched `HOA-10`).

### 2.4 Ticket Schema Template (`src/kahnban/templates/ticket.md`)

```markdown
---
id: HOA-007
title: W4 computer guidance - accuracy curve and targeting UI
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-08-18
updated: 2026-08-18
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
validation_class: headless-verified
---

## Problem
Why this exists and what is wrong today. State the behavioral gap clearly.

## Acceptance criteria
- [ ] Explicit testable condition 1
- [ ] Explicit testable condition 2

## Blast radius
- `game/combat/targeting_computer.gd`
- `tests/targeting_computer_test.gd`

## Implementation notes
- Named functions, line anchors, architectural patterns to reuse.
- Invariants and non-goals (what NOT to modify).

## Validation
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_all_tests.ps1 -Suite targeting_computer_test
```

## Log
- 2026-08-18 10:00 - created -> 0-backlog
```

Frontmatter subset supported by the parser (documented, tested):
scalar values, inline lists (`[a, b]`), block lists (`- item`), quoted
strings. Nested mappings are a lint error (BL01). Colons inside values are
preserved (`split(":", 1)` semantics).

### 2.6 Entry Points — Ideation, Plan, or Feature (v1.1)

Kahnban is a conduit from whatever produced the work to an executable pipeline.
Every entry point produces `core.TicketDraft` objects and lands them in the
backlog column through one commit:

| Entry point | Command | MCP tool |
| :--- | :--- | :--- |
| Ideation (rough titles) | `kahnban capture "<idea>" …` | `kanban_capture` |
| A markdown plan document | `kahnban ingest <plan.md>` | `kanban_plan_ingest` |
| One feature spec per file | `kahnban ingest --per-file <glob>` | `kanban_plan_ingest` (`per_file`) |
| A single ticket | `kahnban new <title>` | `kanban_ticket_new` (body fields accepted) |

Two invariants make plan ingestion safe to run repeatedly:

- **No fabricated readiness.** Drafted tickets always enter the backlog column
  with acceptance boxes **unchecked**, whatever the source claimed, and a
  draft-managed section left empty stays empty — a ticket never inherits the
  template's example checkbox or example path. `--ready` attempts promotion by
  running each ticket through the real §2.2 refinement gate; tickets that fail
  stay behind with their refusal reported. The gate decides, not the flag.
- **Idempotent re-ingest.** Each ticket records `source_doc`, `source_anchor`
  (slugged heading path, excluding the document title so retitling is harmless),
  and `source_hash` (digest of the section text). Re-ingesting skips unchanged
  sections, creates only new ones, and reports changed ones as **drift** with a
  non-zero exit instead of duplicating them. `--update` re-renders a drifted
  ticket only while it is still in `0-backlog` or `1-refining`, preserving its
  `## Log`; a claimed or done ticket is never rewritten. BL17 fails the board if
  two tickets ever claim the same section.

Parsing is heuristic over ordinary markdown and reports what it could not
interpret rather than guessing: fenced blocks never contribute headings, prose in
a files list produces no blast radius (and leaves a note), unmapped subsections
are preserved under `## Implementation notes`, dependency references resolve by
title/anchor/ID with unresolvable ones written to `blocked_on`. Field vocabulary
is configurable per adopter via `board.config.json → ingest.section_aliases`,
which extends the built-in aliases. See `adapters/PLAN-INGESTION.md` for the
recognized labels and the prompt snippet that makes an AI plan ingest losslessly.

---

## 3. Git Strategy: Board State, Worktrees, Concurrency

### 3.1 The Two-Plane Split (D2 — fixes the v3 visibility gap)

| Plane | Branch | Contents |
| :--- | :--- | :--- |
| **Board plane** | default branch (`main`) | Ticket files, STATUS.md, board.config.json. Every transition commits here immediately. |
| **Code plane** | `ticket/<ID>` | Source changes only, made inside `.worktrees/<ID>`. Never touches `plans/tickets/`. |

Consequences:
- Any observer of `main` sees the true board at all times.
- Ticket branches merge cleanly — they contain no board-file edits, so board
  commits and code commits cannot conflict.
- `kahnban done` can verify the merge (gate in §2.2) because the ticket
  branch and default branch are independent lines.

### 3.2 Claim Flow (`kahnban claim <ID> --owner <name> [--worktree]`)

1. Acquire the claim lock (§3.3).
2. Gate checks: ticket in `2-ready`, deps satisfied, WIP limit, blast-radius
   overlap against all `3-in-progress` tickets (§3.5).
3. If repo has a remote: `git pull --ff-only` on the default branch; abort
   the claim if the ticket moved out of `2-ready` upstream.
4. Code plane setup (when `--worktree` / config `use_worktrees: true`):
   ```powershell
   git branch ticket/HOA-007 <default-branch>
   git worktree add .worktrees/HOA-007 ticket/HOA-007
   ```
5. Cache linking (Windows): NTFS junctions for heavy caches listed in
   `board.config.json → "shared_caches"` (e.g. `.godot/`, `node_modules/`):
   ```powershell
   cmd /c mklink /J ".worktrees\HOA-007\.godot" ".godot"
   ```
   Each junction is recorded in ticket frontmatter (`junctions:` list) so
   cleanup can remove them deterministically.
6. Board plane transition: frontmatter update
   (`status/owner/branch/worktree/updated`), Log entry, `git mv` to
   `3-in-progress/`, commit on default branch, STATUS.md regen, push if a
   remote exists (push failure ⇒ claim rolled back and retried once after
   `pull --ff-only`).
7. Release the lock. Agent begins work **inside** `.worktrees/HOA-007`.

### 3.3 Concurrency & Claim Arbitration

Two protections, both required:

- **Local lock (same clone, multiple agent processes):** claim/verify/done/
  move acquire `plans/tickets/.claim.lock` created with
  `os.open(..., O_CREAT | O_EXCL)` containing PID + timestamp. Stale locks
  (> 5 minutes) are broken with a logged warning. Lock scope covers gate
  check through commit — the check-then-move window is closed.
- **Distributed arbitration (multiple clones):** the default-branch commit is
  the arbiter. Claim pushes immediately; a rejected push means another clone
  claimed first — the local transition is rolled back (`git reset --hard
  HEAD~1` on the just-created commit only) and the claim fails with a clear
  message.

Acceptance test (§9): two simultaneous claims of the same ticket — exactly
one succeeds, the loser gets a non-zero exit and an explanatory error.

### 3.4 Cleanup (`kahnban cleanup <ID>`) — implemented in v1 (missing in v3)

1. Verify ticket is in `5-done` (or `--abandon` with logged reason).
2. Remove recorded junctions with `rmdir` (junction-safe: removes the link,
   never the target) **before** worktree removal — `git worktree remove`
   fails or misbehaves on foreign junction content otherwise.
3. `git worktree remove .worktrees/<ID>` (`--force` only with `--abandon`).
4. `git branch -d ticket/<ID>` (`-D` only with `--abandon`).
5. Clear `worktree`/`branch` frontmatter fields, log entry, commit.

### 3.5 Domain Isolation & Merge-Conflict Prevention (D7)

Worktrees isolate working directories but **not merge targets**: two agents
whose tickets touch the same files still collide at merge time — the worst
case being shared engine resource files in coupled architectures. Two
machine-checked gates close this:

- **Claim-time overlap gate:** `claim` parses `## Blast radius` of the
  candidate and of every `3-in-progress` ticket. Entries are file paths or
  directory prefixes (normalized separators; case-insensitive on Windows).
  Overlap = identical path or prefix containment. Any overlap ⇒ **hard
  refusal** naming the conflicting ticket and paths. Override:
  `--force-overlap` with a logged reason.
- **Verify-time containment check:** `verify` runs
  `git diff --name-only <merge-base>..ticket/<ID>`; every changed path must
  fall under the declared `## Blast radius`. Scope creep ⇒ refusal listing
  the out-of-scope paths. Override: `--force-scope` with a logged reason —
  the correct fix is amending the blast radius while the ticket is still
  in refinement, not forcing.

Practical effect: concurrent agents are physically partitioned by declared
domain (e.g. one ticket owns `ui/`, another owns `game/combat/`), and the
partition is enforced by tooling rather than convention. Blast radius
declarations double as the isolation contract.

---

## 4. Module Specifications

Full code lives in the engine repo with tests; this plan specifies contracts
and the defect fixes each module must carry. (v3 embedded ~600 lines of
unreviewed code in the plan; that code is superseded by these specs plus the
test suite in §8.)

### 4.1 `frontmatter.py`

- `parse(text) -> (dict, body: str)` — accepts CRLF and LF; normalizes to LF
  internally; returns `None` sentinel handled by callers as BL01.
- `mutate(text, updates: dict) -> str` — rewrites only lines inside the
  frontmatter block (between the first `---` pair), first match per key.
  **Never** applies regex to the body (v3 defect: `re.sub(r"status:\s*.*")`
  rewrote prose and Log entries anywhere in the file).
- `append_log(text, entry: str) -> str` — appends under `## Log` at the end
  of that section (v3 inserted at the top via fragile regex).
- Round-trip property test: `serialize(parse(x)) == normalize(x)` for all
  fixture tickets.

### 4.2 `core.py`

- `find_ticket(board_root, ticket_id)` — exact filename-prefix match
  (`<ID>-…`); searches columns + `archive/`; returns path + column.
- `next_id(config, board_root)` — scans columns **and** `archive/`.
- `transition(ticket_id, target_column, *, gates, log_entry, fm_updates)` —
  the single writer for all moves; performs the four steps of §2.2.
- Evidence and long text arrive via file path or stdin — **never** argv (v3
  defect: `--evidence "<32KB of test output>"` breaks Windows command-line
  limits and quoting).
- No silent exception swallowing anywhere (v3 defect: `sync_status` had
  `except Exception: pass`). Failures raise; the CLI maps them to stderr +
  exit 1.

### 4.3 `gitops.py`

- Thin wrappers: `mv`, `commit`, `branch`, `worktree_add`, `worktree_remove`,
  `pull_ff_only`, `push`, `is_ancestor(sha, branch)`.
- Every call: `subprocess.run([...], capture_output=True, text=True)`;
  non-zero exit raises `GitError(cmd, stderr)` — stderr is always surfaced.
- Never invokes a shell; arguments are always list-form.

### 4.4 `linter.py` — Rules BL01–BL16

| Rule | Check |
| :--- | :--- |
| BL01 | Valid frontmatter (parseable, has `id`, no unsupported nesting) |
| BL02 | ID matches `<PREFIX>-\d+` and filename starts with `<ID>-` |
| BL03 | No duplicate IDs across columns + archive |
| BL04 | `status` matches containing directory (digit prefix stripped) |
| BL05 | All `required_headings` present |
| BL06 | `2-ready` and later: ≥1 acceptance checkbox |
| BL07 | `5-done`: zero unchecked checkboxes |
| BL08 | `3-in-progress` and later: owner assigned |
| BL09 | Every `depends_on` exists; from `2-ready` onward all deps are in the **configured done column** (v3 hardcoded the string `"5-done"`) |
| BL10 | Extension field rules: `enum`, `required_from`, conditional `require_log_match` — matched against the `## Log` section only (v3 matched the whole body) |
| BL11 | Referenced `design_docs` exist on disk |
| BL12 | WIP limit — warning by default, violation with `--strict` |
| BL13 | No extraneous non-markdown files in column directories (`.gitkeep` exempt; subdirectories reported distinctly) |
| BL14 | `3-in-progress`: `branch` set in frontmatter |
| BL15 | `5-done`: ticket branch merged to default branch (`is_ancestor`), or a `merge-commit: <sha>` Log entry whose sha exists on the default branch. Skipped with a warning when the branch was already cleaned up and the Log holds the recorded sha |
| BL16 | No two `3-in-progress` tickets have overlapping `## Blast radius` entries (§3.5) — catches forced or manually-moved states |
| BL17 | Ingest provenance: no two tickets claim the same `source_doc#source_anchor` (a double ingest); a missing `source_doc` or a half-set pair is a warning (§2.6) |

Output requirements:
- ASCII-safe status markers (`[WARN]`, `[FAIL]`, `[OK]`) — v3's emoji output
  crashes on Windows cp1252 consoles; additionally
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup.
- `--json` machine mode: `{"violations": [...], "warnings": [...]}`.
- Exit 0 clean / 1 violations / 2 config or I/O error.
- `template.md` and `archive/` contents are exempt from column invariants
  (archive is scanned only for BL03 ID uniqueness).

### 4.5 `status.py`

- Regenerates `plans/STATUS.md`: header with timestamp, per-column counts,
  table of tickets showing **ID and title read from frontmatter** (v3 split
  filenames on `-` and broke on any slug containing digits or short names).
- Also emits `plans/status.json`: machine-readable projection (columns,
  ticket IDs, titles, owners, branches, updated dates) for programmatic
  consumers. Both files are **projections only** — the folders remain the
  sole ground truth and the projections are regenerated, never edited (D8).
- Deterministic ordering (by ID) so diffs are meaningful.
- Called from `transition()`; also exposed as `kahnban sync`.

### 4.6 `mcp_server.py`

Protocol requirements (v3 violated several):
- Newline-delimited JSON-RPC 2.0 over stdio.
- Responds to `initialize` (protocolVersion `2024-11-05`), `tools/list`,
  `tools/call`, `ping`.
- **Never responds to notifications** (messages without `id`), including
  `notifications/initialized` and `notifications/cancelled` — v3 returned
  error objects for these, which breaks strict clients.
- Unknown *requests* get `-32601`; parse failures get `-32700` with `id:
  null`.
- All logging to **stderr** only; stdout carries protocol frames exclusively.
- Project root resolution order: `--project-root` argv →
  `KAHNBAN_PROJECT_ROOT` env → cwd. (v3 relied on `Path.cwd()`, which is
  undefined for MCP-launched processes.)
- Tools call `core.py` functions **in-process** (v3 shelled out to
  `python core.py`, losing structured errors and doubling startup cost).

Tool surface:

| Tool | Maps to | Notes |
| :--- | :--- | :--- |
| `kanban_board_status` | lint summary + column counts | read-only |
| `kanban_ticket_get` | `find_ticket` + read | read-only |
| `kanban_ticket_new` | `kahnban new` | |
| `kanban_ticket_claim` | `kahnban claim` | `create_worktree` default true |
| `kanban_ticket_verify` | `kahnban verify` | **runs validation server-side**; returns captured output + exit code (D4) |
| `kanban_ticket_move` | `kahnban move` | requires `reason` |
| `kanban_cleanup` | `kahnban cleanup` | |

### 4.7 `cli.py` — Command Surface

```
kahnban new <title> [--problem TEXT]
kahnban ready <ID>                         # 1-refining -> 2-ready, gated
kahnban claim <ID> --owner NAME [--worktree] [--force] [--force-overlap] [--strict-wip]
kahnban verify <ID> [--manual-evidence FILE] [--force-scope]   # runs ## Validation itself
kahnban done <ID> [--merge-commit SHA]
kahnban move <ID> <column> --reason TEXT
kahnban cleanup <ID> [--abandon]
kahnban lint [--json] [--strict] [--config PATH]
kahnban sync                               # regenerate STATUS.md only
kahnban init [--prefix PREFIX]             # scaffold Layer 0 in an adopter repo
```

`kahnban init` creates the column tree + `.gitkeep`s, `board.config.json`
from answers/flags, copies `template.md`, appends `.worktrees/` to
`.gitignore`, and commits.

### 4.8 `verify` Execution Contract (D4)

1. Extract the first fenced code block under `## Validation`.
2. Run it with `subprocess.run` (shell only for the documented PowerShell
   wrapper form), cwd = the ticket's worktree if one exists, else project
   root; timeout from config (`validation_timeout_sec`, default 1800).
3. Append to `## Log`: timestamp, command, exit code, and output (truncated
   to config `log_output_max_bytes`, default 64KB, with head+tail retention
   and a truncation marker; full output written to
   `plans/tickets/.artifacts/<ID>-<timestamp>.log`, gitignored).
4. Exit code 0 ⇒ transition to `4-verifying`. Non-zero ⇒ no transition, log
   entry still appended (failed attempts are part of the audit trail).
5. `validation_class: visual-deferred` tickets may use `--manual-evidence
   FILE`; the Log entry is explicitly marked `MANUAL-EVIDENCE (unverified)`.

---

## 5. Agent Integration

### 5.1 Repository Agent Contract (`AGENTS.md` / `CLAUDE.md` / `.cursorrules`)

```markdown
# Agent Working Agreement & Kanban Protocol

1. **Source of Truth:** Active backlog lives in `plans/tickets/`. Never
   invent untracked tasks.
2. **Work Selection:** Only pick tickets from `plans/tickets/2-ready/`.
   Never touch `0-backlog` or `1-refining` items without explicit user
   instruction.
3. **Claiming Work:** Always claim before coding:
   - CLI: `kahnban claim <TICKET-ID> --owner <agent-name> --worktree`
   - MCP: `kanban_ticket_claim(ticket_id=..., owner=...)`
   The tool will refuse if the ticket is not ready — do not work around a
   refusal; report it.
4. **Execution & Isolation:** All commands, edits, and tests run inside
   `.worktrees/<TICKET-ID>`. Never edit files in the main working tree while
   a ticket is claimed.
5. **No Silent Ticking:** Acceptance boxes are checked only after
   `kahnban verify <TICKET-ID>` passes — the tool runs the tests itself and
   records the output.
6. **Completion:** `verify` moves tickets to `4-verifying`. Only human
   review/merge to the default branch followed by `kahnban done` moves
   tickets to `5-done`.
```

### 5.2 MCP Client Registration (adapters/, copied per adopter)

`.vscode/mcp.json` (VS Code / Copilot):
```json
{
  "servers": {
    "kahnban": {
      "type": "stdio",
      "command": "py",
      "args": ["-3", "-m", "kahnban.mcp_server", "--project-root", "${workspaceFolder}"]
    }
  }
}
```

Claude Code:
```powershell
claude mcp add kahnban -- py -3 -m kahnban.mcp_server --project-root .
```

Cursor / Windsurf / Cline: equivalent stdio entries documented in
`adapters/README.md`.

---

## 6. Project Integration: `heirs_ancients` (First Adopter)

### 6.1 Configuration (`plans\board.config.json`)

```json
{
  "engine_min_version": "1.0.0",
  "id_prefix": "HOA",
  "board_root": "plans/tickets",
  "columns": ["0-backlog", "1-refining", "2-ready", "3-in-progress", "4-verifying", "5-done"],
  "done_column": "5-done",
  "wip_limit": 3,
  "use_worktrees": true,
  "shared_caches": [".godot"],
  "validation_timeout_sec": 1800,
  "log_output_max_bytes": 65536,
  "required_headings": ["Problem", "Acceptance criteria", "Blast radius", "Implementation notes", "Validation", "Log"],
  "validation_command": "powershell -ExecutionPolicy Bypass -File tools\\run_all_tests.ps1",
  "design_doc_roots": ["plans"],
  "extensions": {
    "validation_class": {
      "enum": ["headless-verified", "visual-deferred", "toolchain-blocked"],
      "required_from": "2-ready"
    },
    "balance_risk": {
      "enum": ["yes", "no"],
      "required_from": "2-ready",
      "when": {
        "equals": "yes",
        "from_column": "4-verifying",
        "require_log_match": "(?i)prediction"
      }
    }
  }
}
```

### 6.2 Test Runner Integration (`tools/run_all_tests.ps1`)

The board lint runs as a runner gate — not a new `.gd` test script — to avoid
breaking `tests/data_integrity_test.gd` DI-06 (which validates headless test
counts against `AGENTS.md`):

```powershell
# Inserted at beginning of tools\run_all_tests.ps1
Write-Host "=== Validating Kahnban Board ===" -ForegroundColor Cyan
& py -3 -m kahnban lint --config plans\board.config.json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kanban board lint failed. Resolve violations before running test suites."
    exit 1
}
```

Note: `kahnban verify` for a ticket runs the *ticket's* validation command,
which itself begins with this lint gate — recursion is prevented because the
lint gate never invokes `verify`.

---

## 7. Phased Execution Roadmap

### Phase 0 — Baseline & Ground Truth (heirs_ancients)
- Count active test scripts:
  `(Get-ChildItem C:\github\heirs_ancients\tests -Filter *_test.gd -Recurse).Count`
- Run `tools/run_all_tests.ps1 > baseline_log.txt 2>&1`; record clean status.

### Phase 1 — Engine Implementation (this repo)

#### ✅ COMPLETE (as of 2026-08-18)
1. Scaffold package (`pyproject.toml`, `src/kahnban/`, `tests/`, `.gitignore`)
2. `frontmatter.py` + 7 round-trip tests (CRLF + LF, quoted escapes, empty blocks, mutation, log insertion)
3. `cli.py` full command surface (`new/ready/claim/verify/done/move/cleanup/lint/sync/status/init`) + 17 tests
4. `gitops.py` — git subprocess wrappers with error surfacing (204 lines, 9 tests)
5. `core.py` — config, ID allocation, board lock, `transition()` single writer, all gates (1,526 lines; 28 + 33 tests)
6. `linter.py` — BL01–BL16 + 18 fixture boards (clean LF, clean CRLF, one negative per rule); 32 tests
7. `worktree.py` — junction provision/cleanup, cache linking (13 tests, Windows-guarded junction assertions)
8. `status.py` — STATUS.md (human) and status.json (machine) projections; called from `transition()` (8 tests)
9. `mcp_server.py` + protocol conformance tests (initialize, notification silence, error codes, tool round-trips, real stdio); 24 tests
10. Concurrency tests: same-clone parallel claim race and cross-clone push-rejection rollback (§3.3)
11. `templates/ticket.md` — canonical template for `kahnban new` and adoptions
12. `adapters/` — AGENTS.md contract, MCP registration examples, adoption README

13. `ingest.py` + `capture`/`ingest` commands and MCP tools — ideation, plan,
    and feature-spec entry points (§2.6); BL17 provenance rule (48 + 17 tests)

**Suite:** 241 tests passing (`py -3 -m pytest -q`). Engine version bumped to
`1.0.0`; the `v1.0.0` tag is the only Phase 1 item left and is deliberately left
to the repository owner.

**Dependency order:** gitops → core → linter (uses core.find_ticket) → transitions (gates) → status → mcp_server. Worktree is orthogonal; can be done in parallel.

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed current state and next steps.

### Phase 2 — `heirs_ancients` Adoption
- `py -3 -m pip install -e C:\Github\Kahnban`, then `kahnban init --prefix HOA`.
- Apply §6.1 config; wire lint gate into `tools/run_all_tests.ps1` (§6.2).
- Add `.vscode/mcp.json` and AGENTS.md protocol section (§5).

### Phase 3 — Backlog Migration & Reconciliation
- Audit open items from `plans/IMPLEMENTATION_PLAN.md` (reconcile Programs B
  and E against code).
- Generate 25–40 tickets into `plans/tickets/0-backlog/` via `kahnban new`.
- Move `plans/IMPLEMENTATION_PLAN.md` → `plans/archive/IMPLEMENTATION_PLAN_2026-08-18.md`,
  marked `SUPERSEDED`; update inbound references in `AGENTS.md`, `README.md`,
  and design docs.

### Phase 4 — Portability Smoke Test (`citadel`)
- `kahnban init --prefix CIT`; claim a ticket with `--worktree`; run
  `kahnban verify`; move through `4-verifying`.
- **Acceptance:** zero code changes required in the Kahnban engine.

### v2 Candidates (explicitly out of scope for this plan)
- `dashboard.html` standalone visual board (D5).
- `kahnban watch` — observe-only background daemon: regenerates projections
  on filesystem events, appends `## Log` annotations for conventional
  commits tagged with ticket IDs, flags stale in-progress tickets. It
  **never performs transitions** and holds no state of its own (D9).

---

## 8. Engine Test Plan

- Framework: `pytest` (dev-only dependency). CI: GitHub Actions matrix on
  `windows-latest` + `ubuntu-latest`, Python 3.10 and 3.12.
- Fixture layout:
  ```
  tests/fixtures/
  ├── clean-board/            ← lints with 0 violations (LF)
  ├── clean-board-crlf/       ← identical content, CRLF endings
  └── violations/BL01/ … BL16/  ← one minimal failing board per rule
  ```
- Transition tests run against throwaway `git init` repos created in `tmp_path`.
- Windows-only tests (junctions, `py` launcher) marked
  `@pytest.mark.skipif(os.name != "nt")`.
- MCP tests drive the server as a subprocess over real stdio pipes.

---

## 9. Verification & Acceptance Checkpoints

- [x] `kahnban lint` exits 0 on clean boards and 1 on every BL01–BL16
      negative fixture, on both CRLF and LF, on Windows and Linux.
- [x] Lint output is ASCII-safe on a cp1252 Windows console.
- [x] `kahnban claim --worktree` provisions an isolated worktree + branch;
      the board commit lands on the default branch, not the ticket branch.
- [x] Parallel-claim race: exactly one of two simultaneous claims succeeds.
- [x] Claim refuses when the candidate's blast radius overlaps any
      `3-in-progress` ticket; `--force-overlap` succeeds and logs the reason.
- [x] Verify refuses when the ticket-branch diff touches paths outside the
      declared blast radius, listing the offending paths.
- [x] `plans/status.json` regenerates with STATUS.md in every transition
      commit and matches folder state exactly.
- [x] `kahnban verify` executes the ticket's validation command, blocks on
      non-zero exit, and records exit code + truncated output in `## Log`.
- [x] `kahnban done` refuses when the ticket branch is not merged; accepts
      once `git merge-base --is-ancestor` holds.
- [x] `kahnban cleanup` removes junctions, worktree, and branch without
      touching junction targets.
- [x] `tools/run_all_tests.ps1` in `heirs_ancients` passes with DI-06 green.
- [x] STATUS.md regenerates on every transition and is included in the
      transition commit.
- [x] `engine_min_version` mismatch produces a refusal with upgrade
      instructions.
- [ ] No remaining references to stale `plan.md` / `agent-kanban` paths
      across adopter repositories.
