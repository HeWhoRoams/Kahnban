```markdown
# Portable Agentic Kanban Workflow — Universal Architecture & Implementation Plan

**Status:** ACTIVE PLAN — Ready for Implementation  
**Created:** 2026-08-18[cite: 1]  
**Revised:** 2026-08-18 (v3: Universal Agnostic Core + Git Worktrees + MCP + Ambient Transparency)[cite: 1]  
**Owner:** Tim Niles[cite: 1]  
**Core Repository:** `C:\github\agent-kanban` (Layer 1 engine)  
**First Adopter:** `C:\github\heirs_ancients`[cite: 1]  
**Second Adopter:** `C:\github\citadel`[cite: 1]  

---

## 0. Executive Summary & Design Principles

This plan defines a model-, agent-, IDE-, and harness-agnostic Kanban system tailored for AI vibe-coding workflows. It provides strict transparency into in-flight agent tasks, prevents workspace collisions across concurrent LLM sessions, enforces requirement refinement, and maintains a machine-checked single source of truth backed by standard Git storage[cite: 1].

### Core Principles
1. **The Filesystem Folder Is the Only Status:** Columns are physical folders (`0-backlog` through `5-done`)[cite: 1]. State transitions require a `git mv`[cite: 1]. There are no parallel databases, untracked counters, or out-of-sync status properties[cite: 1].
2. **Universal Client Surface (MCP + CLI):** Agents interact natively via a Model Context Protocol (MCP) server or a zero-dependency CLI. Any agent (Claude Code, Cursor Composer, Windsurf, Copilot CLI, Hermes, Cline) uses the identical contract.
3. **Workspace Isolation via Git Worktrees:** Every active ticket in `3-in-progress` runs in an isolated Git worktree (`.worktrees/<TICKET-ID>`) on a dedicated branch (`ticket/<TICKET-ID>`). Multiple agents never collide on file locks, dirty working trees, or Git indexes.
4. **Enforced Refinement Before Execution:** A ticket cannot enter `2-ready` without testable criteria, explicit blast radius boundaries, file anchors, and satisfied upstream dependencies[cite: 1].
5. **No Silent Ticking & Empirical Verification:** Moving to `4-verifying` requires real terminal test output pasted into the ticket log[cite: 1]. Moving to `5-done` requires a merge commit to the default branch[cite: 1].
6. **Ambient Transparency:** State transitions automatically regenerate `plans/STATUS.md` and a standalone `dashboard.html` visual board.

---

## 1. System Architecture — Four Clean Layers


```

LAYER 1 — Universal Core Engine (Installed globally or referenced locally)
agent-kanban/
├── kanban/
│   ├── core.py               ← State machine, frontmatter parser, git/worktree ops
│   ├── linter.py             ← Zero-dependency Python validator (BL-01 to BL-14)
│   ├── mcp_server.py         ← Stdlib JSON-RPC 2.0 Model Context Protocol Server
│   └── templates/            ← Ticket templates, board configs, dashboard assets
└── adapters/                 ← Thin client glue (Claude plugin, Cursor rules, Copilot prompts)

LAYER 0 — Per-Repo Storage Contract (Committed to project repository)
/
├── plans/
│   ├── board.config.json     ← Prefix, WIP limits, validation commands, extensions
│   ├── STATUS.md             ← Auto-generated Markdown visual board (read-only projection)
│   └── tickets/
│       ├── 0-backlog/        ← Captured items, unrefined ideas, blocked work
│       ├── 1-refining/       ← Active specification sharpening
│       ├── 2-ready/          ← Context-complete tickets ready for cold agent pickup
│       ├── 3-in-progress/    ← Actively claimed by an agent on a dedicated branch
│       ├── 4-verifying/      ← Code complete, test gates passed, awaiting merge
│       └── 5-done/           ← Landed on main branch
└── .worktrees/               ← Isolated working directories (gitignored)

LAYER 2 — Client & Agent Configs (Repo-level instruction anchors)
/AGENTS.md / CLAUDE.md / .cursorrules / .github/prompts/ticket.prompt.md

LAYER 3 — Per-Repo Test Adapter (Committed)
/tools/run_all_tests.ps1 (or CI workflow calling board_lint.py)

```

---

## 2. The Agnostic Board Contract

### 2.1 Directory Structure & Lifecycle

```

plans/tickets/
├── 0-backlog/     ← Captured, not yet refined. blocked_on items park here.
├── 1-refining/    ← Researching codebase, defining blast radius and acceptance tests.
├── 2-ready/       ← Ready for cold pickup. All dependencies satisfied in 5-done.
├── 3-in-progress/ ← Exactly one agent/developer operating in an isolated worktree.
├── 4-verifying/   ← Code finished, validation commands run, output pasted in log.
└── 5-done/        ← Merged to main branch. All criteria checked.

```

### 2.2 Column Transition Invariants

| Column | Entry Criteria / Invariants |
| :--- | :--- |
| **0-backlog**[cite: 1] | Has valid frontmatter, ID, title, and `## Problem`[cite: 1]. External dependencies or owner decisions recorded in `blocked_on`[cite: 1]. |
| **1-refining**[cite: 1] | Actively being researched[cite: 1]. Target files identified, non-goals established, acceptance criteria drafted[cite: 1]. |
| **2-ready**[cite: 1] | Acceptance criteria fully testable; `## Blast radius` lists files; `blocked_on` is empty; all `depends_on` tickets are in `5-done`[cite: 1]. |
| **3-in-progress**[cite: 1] | `owner` is assigned; Git worktree `.worktrees/<ID>` and branch `ticket/<ID>` created; soft WIP limit checked[cite: 1]. |
| **4-verifying**[cite: 1] | Code implemented; `## Validation` executed; raw test logs pasted into `## Log`; extension rules satisfied (e.g. prediction recorded)[cite: 1]. |
| **5-done**[cite: 1] | Merged to main branch; all acceptance criteria checkboxes marked `[x]`; merge commit logged[cite: 1]. |

### 2.3 Ticket Identity & Naming Rules
* Filename pattern: `<PREFIX>-###-short-slug.md` (e.g., `HOA-007-w4-guidance-targeting.md`)[cite: 1].
* IDs are permanent, uppercase, sequentially allocated by scanning all directories (`0-backlog` through `5-done` + `archive/`), and never reused[cite: 1].
* Ticket file movements across columns **must** use `git mv` to preserve commit history[cite: 1].

### 2.4 Ticket Schema Template (`plans/tickets/template.md`)

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
legacy_id: A6, G4
design_docs:
  - plans/GUIDANCE_SYSTEMS_IMPLEMENTATION_PLAN.md
depends_on: []
blocked_on: ""
validation_class: headless-verified
balance_risk: no
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

* 2026-08-18 10:00 - created, -> 0-backlog

```

---

## 3. Git Worktree Isolation & Multi-Agent Concurrency

### 3.1 Worktree Orchestration Flow
When an agent claims a ticket:
1. **Branch Creation:** `git branch ticket/HOA-007 main`
2. **Worktree Provisioning:** `git worktree add .worktrees/HOA-007 ticket/HOA-007`
3. **Cache / Dependency Linking:** Creates NTFS directory junctions for heavy build/engine caches (e.g., `.godot/`, `node_modules/`) so agents do not trigger clean-rebuild penalties:
   ```powershell
   cmd /c mklink /J ".worktrees\HOA-007\.godot" ".godot"

```

4. **State Transition:** The ticket file is moved `2-ready/` $\to$ `3-in-progress/`, frontmatter updated (`owner: agent-name`, `branch: ticket/HOA-007`, `worktree: .worktrees/HOA-007`), and committed directly inside the worktree branch.
5. **Execution:** The agent launches inside `.worktrees/HOA-007`. Shell commands, file edits, and test runs are completely isolated from other agents.
6. **Verification & Teardown:** Once validated, the ticket moves to `4-verifying/` and is pushed. Upon merge to `main`, running `kanban cleanup HOA-007` removes `.worktrees/HOA-007` and deletes the branch.

---

## 4. Core Implementation Scripts (Zero Dependencies)

### 4.1 Portable Linter (`agent-kanban/kanban/linter.py` / `board_lint.py`)

```python
#!/usr/bin/env python3
"""
board_lint.py - Zero-dependency, stdlib Python Kanban validator.
Enforces rules BL-01 through BL-14 across POSIX and Windows CRLF environments.
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path

RULES = {
    "BL01": "Invalid or missing YAML frontmatter",
    "BL02": "Ticket ID does not match format <PREFIX>-<NUMBER> or filename",
    "BL03": "Duplicate ticket ID detected across columns",
    "BL04": "Ticket 'status' does not match containing directory",
    "BL05": "Missing required markdown section heading",
    "BL06": "Ticket in '2-ready' or later has no acceptance criteria checkboxes",
    "BL07": "Ticket in '5-done' contains unchecked acceptance criteria",
    "BL08": "Ticket in '3-in-progress' or later must have an assigned owner",
    "BL09": "Unresolved or unsatisfied 'depends_on' ticket dependency",
    "BL10": "Configured extension rule or constraint violation",
    "BL11": "Referenced design document does not exist",
    "BL12": "WIP limit exceeded for '3-in-progress' column",
    "BL13": "Extraneous non-markdown file in column directory",
    "BL14": "Ticket in '3-in-progress' missing active branch specification in frontmatter or Log"
}

def parse_simple_yaml(text):
    data = {}
    lines = text.splitlines()
    current_list_key = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            data[current_list_key].append(stripped[2:].strip(' "\''))
            continue
        if ":" in line:
            current_list_key = None
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if not val:
                data[key] = []
                current_list_key = key
            elif val.startswith("[") and val.endswith("]"):
                items = [i.strip(' "\'') for i in val[1:-1].split(",") if i.strip()]
                data[key] = items
            else:
                data[key] = val.strip(' "\'')
    return data

def parse_markdown_ticket(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().replace("\r\n", "\n")
        
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if not fm_match:
        return None, content, [], []
        
    fm_text, body = fm_match.groups()
    frontmatter = parse_simple_yaml(fm_text)
    headings = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
    checkboxes = re.findall(r"^\s*-\s*\[([ xX])\]\s+(.+)$", body, re.MULTILINE)
    return frontmatter, body, headings, checkboxes

def lint_board(config_path, strict=False):
    violations = []
    warnings = []
    
    if not os.path.exists(config_path):
        return [{"rule": "BL00", "file": config_path, "message": "Config not found."}], []
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    project_root = Path(config_path).resolve().parent.parent
    board_root = project_root / config.get("board_root", "plans/tickets")
    
    if not board_root.exists():
        return [], []
        
    id_prefix = config.get("id_prefix", "HOA")
    id_pattern = re.compile(rf"^{id_prefix}-\d{{3,4}}$")
    columns = config.get("columns", ["0-backlog", "1-refining", "2-ready", "3-in-progress", "4-verifying", "5-done"])
    required_headings = config.get("required_headings", ["Problem", "Acceptance criteria", "Validation", "Log"])
    wip_limit = config.get("wip_limit", 3)
    extensions = config.get("extensions", {})
    
    seen_ids = {}
    all_tickets = {}
    in_progress_count = 0
    
    for col in columns:
        col_dir = board_root / col
        if not col_dir.exists():
            continue
            
        for file in col_dir.iterdir():
            if file.name == ".gitkeep":
                continue
            if not file.name.endswith(".md"):
                violations.append({"rule": "BL13", "file": str(file), "message": f"Non-markdown file in {col}."})
                continue
                
            fm, body, headings, checkboxes = parse_markdown_ticket(file)
            if fm is None:
                violations.append({"rule": "BL01", "file": str(file), "message": "Invalid YAML frontmatter."})
                continue
                
            ticket_id = fm.get("id")
            if not ticket_id:
                violations.append({"rule": "BL01", "file": str(file), "message": "Missing 'id' in frontmatter."})
                continue
                
            if ticket_id in seen_ids:
                violations.append({"rule": "BL03", "file": str(file), "message": f"Duplicate ID '{ticket_id}' already in {seen_ids[ticket_id]}."})
            else:
                seen_ids[ticket_id] = col
                
            all_tickets[ticket_id] = {
                "file": file, "column": col, "fm": fm,
                "body": body, "headings": headings, "checkboxes": checkboxes
            }

    for t_id, data in all_tickets.items():
        file, col, fm, body = data["file"], data["column"], data["fm"], data["body"]
        headings, checkboxes = data["headings"], data["checkboxes"]
        
        if not id_pattern.match(t_id):
            violations.append({"rule": "BL02", "file": str(file), "message": f"ID '{t_id}' does not match prefix '{id_prefix}-\\d{{3,4}}'."})
        if not file.name.startswith(t_id):
            violations.append({"rule": "BL02", "file": str(file), "message": f"Filename does not start with ID '{t_id}'."})
            
        expected_status = re.sub(r"^\d+-", "", col)
        if fm.get("status") != expected_status:
            violations.append({"rule": "BL04", "file": str(file), "message": f"Status '{fm.get('status')}' != directory '{expected_status}'."})
            
        for req_h in required_headings:
            if req_h not in headings:
                violations.append({"rule": "BL05", "file": str(file), "message": f"Missing required heading '## {req_h}'."})
                
        col_idx = columns.index(col)
        ready_idx = columns.index("2-ready") if "2-ready" in columns else 2
        in_prog_idx = columns.index("3-in-progress") if "3-in-progress" in columns else 3
        done_idx = columns.index("5-done") if "5-done" in columns else 5
        
        if col_idx >= ready_idx and len(checkboxes) == 0:
            violations.append({"rule": "BL06", "file": str(file), "message": f"Must contain >= 1 criteria checkbox in '{col}'."})
                
        if col_idx == done_idx:
            unchecked = [text for state, text in checkboxes if state.strip().lower() != "x"]
            if unchecked:
                violations.append({"rule": "BL07", "file": str(file), "message": f"{len(unchecked)} unchecked criteria in '5-done'."})
                
        if col_idx >= in_prog_idx:
            owner = fm.get("owner", "unassigned")
            if not owner or owner == "unassigned":
                violations.append({"rule": "BL08", "file": str(file), "message": f"Must have assigned 'owner' in '{col}'."})
            if col == "3-in-progress":
                in_progress_count += 1
                branch = fm.get("branch") or ""
                if not branch and "branch" not in body.lower():
                    violations.append({"rule": "BL14", "file": str(file), "message": "In-progress ticket must specify branch in frontmatter or Log."})
                    
        deps = fm.get("depends_on", [])
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            if dep not in all_tickets:
                violations.append({"rule": "BL09", "file": str(file), "message": f"Dependency '{dep}' does not exist on board."})
            elif col_idx >= ready_idx:
                dep_col = all_tickets[dep]["column"]
                if dep_col != "5-done":
                    violations.append({"rule": "BL09", "file": str(file), "message": f"Dependency '{dep}' is in '{dep_col}', must be '5-done'."})

        for ext_key, ext_rules in extensions.items():
            val = fm.get(ext_key)
            req_from = ext_rules.get("required_from")
            if req_from and req_from in columns:
                if col_idx >= columns.index(req_from) and not val:
                    violations.append({"rule": "BL10", "file": str(file), "message": f"Extension '{ext_key}' required from '{req_from}' onwards."})
            if val and "enum" in ext_rules and val not in ext_rules["enum"]:
                violations.append({"rule": "BL10", "file": str(file), "message": f"Value '{val}' for '{ext_key}' not in enum: {ext_rules['enum']}."})
            
            when = ext_rules.get("when", {})
            if when and val == when.get("equals"):
                from_col = when.get("from_column")
                if from_col and col_idx >= columns.index(from_col):
                    pattern = when.get("require_log_match")
                    if pattern and not re.search(pattern, body):
                        violations.append({"rule": "BL10", "file": str(file), "message": f"Extension rule for '{ext_key}={val}' requires match '{pattern}' in ticket body."})

        docs = fm.get("design_docs", [])
        if isinstance(docs, str):
            docs = [docs]
        for doc in docs:
            doc_path = project_root / doc
            if not doc_path.exists():
                violations.append({"rule": "BL11", "file": str(file), "message": f"Referenced design doc '{doc}' not found at '{doc_path}'."})

    if in_progress_count > wip_limit:
        msg = f"WIP limit exceeded: {in_progress_count} tickets in '3-in-progress' (limit: {wip_limit})."
        if strict:
            violations.append({"rule": "BL12", "file": str(board_root / '3-in-progress'), "message": msg})
        else:
            warnings.append({"rule": "BL12", "file": str(board_root / '3-in-progress'), "message": msg})
            
    return violations, warnings

def main():
    parser = argparse.ArgumentParser(description="Agentic Kanban Board Linter")
    parser.add_argument("--config", default="plans/board.config.json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    violations, warnings = lint_board(args.config, strict=args.strict)
    if args.json:
        print(json.dumps({"violations": violations, "warnings": warnings}, indent=2))
    else:
        for w in warnings:
            print(f"⚠️  [{w['rule']}] {w['file']}: {w['message']}")
        for v in violations:
            print(f"❌ [{v['rule']}] {v['file']}: {v['message']}")
        if violations:
            sys.exit(1)
        print("✅ Board is valid. 0 violations.")
        sys.exit(0)

if __name__ == "__main__":
    main()

```

---

### 4.2 CLI & Worktree Orchestrator (`agent-kanban/kanban/core.py`)

```python
#!/usr/bin/env python3
"""
kanban_core.py - CLI & Orchestration Engine for Agentic Kanban Workflows.
Handles ticket allocation, git worktrees, state transitions, and status projection sync.
"""

import sys
import os
import re
import json
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

def resolve_config():
    p = Path.cwd()
    for candidate in [p / "plans" / "board.config.json", p / "board.config.json", p.parent / "plans" / "board.config.json"]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find plans/board.config.json")

def load_config():
    cfg_path = resolve_config()
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f), cfg_path.parent.parent, cfg_path

def get_board_root(config, project_root):
    return project_root / config.get("board_root", "plans/tickets")

def get_next_ticket_id(config, board_root):
    prefix = config.get("id_prefix", "HOA")
    max_id = 0
    pattern = re.compile(rf"^{prefix}-(\d{{3,4}})")
    for md in board_root.glob("*/*.md"):
        m = pattern.match(md.name)
        if m:
            num = int(m.group(1))
            if num > max_id:
                max_id = num
    return f"{prefix}-{max_id + 1:03d}"

def cmd_new(args):
    config, project_root, _ = load_config()
    board_root = get_board_root(config, project_root)
    ticket_id = get_next_ticket_id(config, board_root)
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
    filename = f"{ticket_id}-{slug}.md"
    target_path = board_root / "0-backlog" / filename
    
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""---
id: {ticket_id}
title: {args.title}
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: {today}
updated: {today}
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
---

## Problem
{args.problem or 'Describe the problem statement and behavioral requirement.'}

## Acceptance criteria
- [ ] Criteria definition pending refinement

## Blast radius
- To be identified during refinement

## Implementation notes
- File anchors and architecture notes.

## Validation
{config.get('validation_command', 'echo "No validation command configured"')}

## Log
- {today} - Created ticket -> 0-backlog
"""
    with open(target_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
        
    print(f"Created ticket {ticket_id} at {target_path}")
    sync_status()

def find_ticket_file(board_root, ticket_id):
    for f in board_root.glob(f"*/*{ticket_id}*.md"):
        return f
    return None

def cmd_claim(args):
    config, project_root, _ = load_config()
    board_root = get_board_root(config, project_root)
    ticket_file = find_ticket_file(board_root, args.ticket_id)
    
    if not ticket_file:
        print(f"Error: Ticket {args.ticket_id} not found.")
        sys.exit(1)
        
    source_col = ticket_file.parent.name
    target_col = "3-in-progress"
    dest_path = board_root / target_col / ticket_file.name
    
    branch_name = f"ticket/{args.ticket_id}"
    worktree_rel = f".worktrees/{args.ticket_id}"
    worktree_path = project_root / worktree_rel
    
    # 1. Git branch & worktree setup if requested
    if args.worktree:
        print(f"Creating branch '{branch_name}' and worktree at '{worktree_rel}'...")
        subprocess.run(["git", "branch", branch_name, "HEAD"], cwd=project_root, check=False)
        res = subprocess.run(["git", "worktree", "add", str(worktree_path), branch_name], cwd=project_root, capture_output=True, text=True)
        if res.returncode != 0 and not worktree_path.exists():
            print(f"Failed to create worktree: {res.stderr}")
            sys.exit(1)
            
        # Link shared engine cache if Godot project
        godot_cache = project_root / ".godot"
        if godot_cache.exists() and os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(worktree_path / ".godot"), str(godot_cache)], capture_output=True)

    # 2. Update ticket content
    with open(ticket_file, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
        
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = re.sub(r"status:\s*.*", "status: in-progress", text)
    text = re.sub(r"owner:\s*.*", f"owner: {args.owner}", text)
    text = re.sub(r"branch:\s*.*", f"branch: {branch_name}", text)
    text = re.sub(r"worktree:\s*.*", f"worktree: {worktree_rel if args.worktree else ''}", text)
    text = re.sub(r"updated:\s*.*", f"updated: {datetime.now().strftime('%Y-%m-%d')}", text)
    
    log_entry = f"- {today} - Claimed by {args.owner}, worktree={worktree_rel} -> 3-in-progress\n"
    text = re.sub(r"(## Log\n)", r"\1" + log_entry, text)
    
    # Move ticket file via git
    subprocess.run(["git", "mv", str(ticket_file), str(dest_path)], cwd=project_root, check=True)
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        
    print(f"Ticket {args.ticket_id} moved to 3-in-progress (Owner: {args.owner}).")
    sync_status()

def cmd_verify(args):
    config, project_root, _ = load_config()
    board_root = get_board_root(config, project_root)
    ticket_file = find_ticket_file(board_root, args.ticket_id)
    if not ticket_file:
        print(f"Ticket {args.ticket_id} not found.")
        sys.exit(1)
        
    dest_path = board_root / "4-verifying" / ticket_file.name
    with open(ticket_file, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
        
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = re.sub(r"status:\s*.*", "status: verifying", text)
    text = re.sub(r"updated:\s*.*", f"updated: {datetime.now().strftime('%Y-%m-%d')}", text)
    
    evidence_block = f"\n```\n{args.evidence.strip()}\n```\n" if args.evidence else ""
    log_entry = f"- {today} - Verified test gates green -> 4-verifying{evidence_block}\n"
    text = re.sub(r"(## Log\n)", r"\1" + log_entry, text)
    
    subprocess.run(["git", "mv", str(ticket_file), str(dest_path)], cwd=project_root, check=True)
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        
    print(f"Ticket {args.ticket_id} verified and moved to 4-verifying.")
    sync_status()

def cmd_move(args):
    config, project_root, _ = load_config()
    board_root = get_board_root(config, project_root)
    ticket_file = find_ticket_file(board_root, args.ticket_id)
    if not ticket_file:
        print(f"Ticket {args.ticket_id} not found.")
        sys.exit(1)
        
    dest_dir = board_root / args.target_column
    if not dest_dir.exists():
        print(f"Target column directory {args.target_column} does not exist.")
        sys.exit(1)
        
    dest_path = dest_dir / ticket_file.name
    with open(ticket_file, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
        
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean_status = re.sub(r"^\d+-", "", args.target_column)
    text = re.sub(r"status:\s*.*", f"status: {clean_status}", text)
    text = re.sub(r"updated:\s*.*", f"updated: {datetime.now().strftime('%Y-%m-%d')}", text)
    
    log_entry = f"- {today} - Moved to {args.target_column} (Reason: {args.reason})\n"
    text = re.sub(r"(## Log\n)", r"\1" + log_entry, text)
    
    subprocess.run(["git", "mv", str(ticket_file), str(dest_path)], cwd=project_root, check=True)
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        
    print(f"Moved {args.ticket_id} -> {args.target_column}")
    sync_status()

def sync_status():
    try:
        config, project_root, cfg_path = load_config()
        board_root = get_board_root(config, project_root)
        columns = config.get("columns", [])
        
        status_file = cfg_path.parent / "STATUS.md"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        counts = {}
        for c in columns:
            cdir = board_root / c
            counts[c] = len(list(cdir.glob("*.md"))) if cdir.exists() else 0
            
        md = [f"# Live Project Board Status\n*Last updated: {now}*\n"]
        md.append("| " + " | ".join([f"{c} ({counts[c]})" for c in columns]) + " |")
        md.append("| " + " | ".join(["---" for _ in columns]) + " |")
        
        # Collect top 5 rows
        grid = {c: [f.name for f in (board_root / c).glob("*.md")] if (board_root / c).exists() else [] for c in columns}
        max_rows = max([len(v) for v in grid.values()] or [0])
        for i in range(max_rows):
            row = []
            for c in columns:
                items = grid[c]
                val = f"`{items[i].split('-')[0]}-{items[i].split('-')[1]}`" if i < len(items) else ""
                row.append(val)
            md.append("| " + " | ".join(row) + " |")
            
        with open(status_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(md) + "\n")
    except Exception as e:
        pass

def main():
    parser = argparse.ArgumentParser(description="Agentic Kanban Orchestrator")
    sub = parser.add_subparsers(dest="command")
    
    p_new = sub.add_parser("new")
    p_new.add_argument("title", help="Ticket title")
    p_new.add_argument("--problem", default="", help="Problem description")
    
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("ticket_id", help="e.g. HOA-007")
    p_claim.add_argument("--owner", default="agent", help="Owner identity")
    p_claim.add_argument("--worktree", action="store_true", help="Create Git worktree")
    
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("ticket_id")
    p_verify.add_argument("--evidence", default="", help="Terminal validation output")
    
    p_move = sub.add_parser("move")
    p_move.add_argument("ticket_id")
    p_move.add_argument("target_column")
    p_move.add_argument("--reason", default="Manual transition")
    
    p_sync = sub.add_parser("sync")

    args = parser.parse_args()
    if args.command == "new":
        cmd_new(args)
    elif args.command == "claim":
        cmd_claim(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "move":
        cmd_move(args)
    elif args.command == "sync":
        sync_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

```

---

### 4.3 Universal MCP Server (`agent-kanban/kanban/mcp_server.py`)

```python
#!/usr/bin/env python3
"""
kanban_mcp.py - Standard-I/O JSON-RPC 2.0 Model Context Protocol Server.
Compatible with Claude Code, Cursor Composer, Windsurf, Hermes Agent, Cline, and Copilot.
"""

import sys
import os
import json
import subprocess
from pathlib import Path

TOOLS = [
    {
        "name": "kanban_board_status",
        "description": "Get summary counts, active in-progress tickets, and lint warnings.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "kanban_ticket_get",
        "description": "Fetch complete markdown content and acceptance criteria for a ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"]
        }
    },
    {
        "name": "kanban_ticket_claim",
        "description": "Claim a ticket, transition to 3-in-progress, and optionally provision a Git worktree.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "owner": {"type": "string"},
                "create_worktree": {"type": "boolean", "default": True}
            },
            "required": ["ticket_id", "owner"]
        }
    },
    {
        "name": "kanban_ticket_verify",
        "description": "Log test execution evidence and transition ticket to 4-verifying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "validation_output": {"type": "string"}
            },
            "required": ["ticket_id", "validation_output"]
        }
    },
    {
        "name": "kanban_ticket_move",
        "description": "Move a ticket across columns with an audit log reason.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "target_column": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["ticket_id", "target_column", "reason"]
        }
    }
]

def handle_tool(name, args):
    core_script = Path(__file__).parent / "core.py"
    py_exec = sys.executable

    if name == "kanban_board_status":
        from linter import lint_board
        from core import load_config, get_board_root
        cfg, proj_root, cfg_path = load_config()
        violations, warnings = lint_board(str(cfg_path))
        board_root = get_board_root(cfg, proj_root)
        summary = {"columns": {}, "violations": len(violations), "warnings": len(warnings)}
        for c in cfg.get("columns", []):
            cdir = board_root / c
            summary["columns"][c] = len(list(cdir.glob("*.md"))) if cdir.exists() else 0
        return {"content": [{"type": "text", "text": json.dumps(summary, indent=2)}]}

    elif name == "kanban_ticket_get":
        from core import load_config, get_board_root, find_ticket_file
        cfg, proj_root, _ = load_config()
        board_root = get_board_root(cfg, proj_root)
        f = find_ticket_file(board_root, args["ticket_id"])
        if f and f.exists():
            return {"content": [{"type": "text", "text": f.read_text(encoding="utf-8")}]}
        return {"isError": True, "content": [{"type": "text", "text": f"Ticket {args['ticket_id']} not found."}]}

    elif name == "kanban_ticket_claim":
        cmd = [py_exec, str(core_script), "claim", args["ticket_id"], "--owner", args["owner"]]
        if args.get("create_worktree", True):
            cmd.append("--worktree")
        res = subprocess.run(cmd, capture_output=True, text=True)
        return {"content": [{"type": "text", "text": res.stdout if res.returncode == 0 else res.stderr}], "isError": res.returncode != 0}

    elif name == "kanban_ticket_verify":
        cmd = [py_exec, str(core_script), "verify", args["ticket_id"], "--evidence", args["validation_output"]]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return {"content": [{"type": "text", "text": res.stdout if res.returncode == 0 else res.stderr}], "isError": res.returncode != 0}

    elif name == "kanban_ticket_move":
        cmd = [py_exec, str(core_script), "move", args["ticket_id"], args["target_column"], "--reason", args["reason"]]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return {"content": [{"type": "text", "text": res.stdout if res.returncode == 0 else res.stderr}], "isError": res.returncode != 0}

    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool {name}"}]}

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = req.get("params", {})
                res = handle_tool(params.get("name"), params.get("arguments", {}))
                resp = {"jsonrpc": "2.0", "id": req_id, "result": res}
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "agent-kanban-mcp", "version": "1.0.0"}
                    }
                }
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()

```

---

## 5. Universal Agent Prompt Rules

### 5.1 Repository Agent Contract (`AGENTS.md` / `CLAUDE.md` / `.cursorrules`)

```markdown
# Agent Working Agreement & Kanban Protocol

1. **Source of Truth:** Active backlog lives in `plans/tickets/`. Never invent untracked tasks.
2. **Work Selection:** Only pick tickets from `plans/tickets/2-ready/`. Never touch unrefined items in `0-backlog` or `1-refining` without explicit user instruction.
3. **Claiming Work:** Always claim before coding:
   - CLI: `py -3 tools/kanban.py claim <TICKET-ID> --owner <agent-name> --worktree`
   - MCP: `kanban_ticket_claim(ticket_id="<TICKET-ID>", owner="<agent-name>")`
4. **Execution & Isolation:** If a worktree is provisioned, execute all commands, edits, and tests within `.worktrees/<TICKET-ID>`.
5. **No Silent Ticking:** Never check an acceptance box without running test verification and pasting raw test results into `## Log`.
6. **Completion:** Move tickets to `4-verifying`. Only human review/merge to `main` moves tickets to `5-done`.

```

---

## 6. Project Integration: `heirs_ancients` (First Adopter)



### 6.1 Configuration (`C:\github\heirs_ancients\plans\board.config.json`)



```json
{
  "id_prefix": "HOA",
  "board_root": "plans/tickets",
  "columns": [
    "0-backlog",
    "1-refining",
    "2-ready",
    "3-in-progress",
    "4-verifying",
    "5-done"
  ],
  "wip_limit": 3,
  "use_worktrees": true,
  "required_headings": [
    "Problem",
    "Acceptance criteria",
    "Blast radius",
    "Implementation notes",
    "Validation",
    "Log"
  ],
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



To prevent breaking `tests/data_integrity_test.gd` DI-06 (which validates headless test counts against `AGENTS.md`), the board lint is injected directly as a runner gate rather than a new `.gd` test script:

```powershell
# Inserted at beginning of tools\run_all_tests.ps1
Write-Host "=== Validating Agentic Kanban Board ===" -ForegroundColor Cyan
& py -3 tools\board_lint.py --config plans\board.config.json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kanban board lint failed. Resolve violations before running test suites."
    exit 1
}

```

---

## 7. Phased Execution Roadmap

### Phase 0: Baseline & Ground Truth Establishment



* Measure active test script counts:
```powershell
(Get-ChildItem C:\github\heirs_ancients\tests -Filter *_test.gd -Recurse).Count

```


* Run full test suite baseline through `tools/run_all_tests.ps1 > baseline_log.txt 2>&1`.


* Record clean suite status in migration record.



### Phase 1: Core Tooling Setup

* Initialize engine repository at `C:\github\agent-kanban`.
* Implement `linter.py`, `core.py`, and `mcp_server.py`.
* Verify negative fixtures (ensure all BL-01 to BL-14 rules fail on bad tickets).



### Phase 2: `heirs_ancients` Board Adoption



* Create folder tree `plans/tickets/{0-backlog,1-refining,2-ready,3-in-progress,4-verifying,5-done}`.


* Add `.gitkeep` to all column directories.


* Place `plans/board.config.json` and copy `board_lint.py` / `kanban_core.py` to `tools/`.


* Wire lint gate into `tools/run_all_tests.ps1`.



### Phase 3: Backlog Migration & Reconciliation



* Audit open items from `plans/IMPLEMENTATION_PLAN.md` (reconcile Program B and E against code).


* Generate 25–40 individual markdown tickets into `plans/tickets/0-backlog/`.


* Move `plans/IMPLEMENTATION_PLAN.md` $\to$ `plans/archive/IMPLEMENTATION_PLAN_2026-08-18.md` with status `SUPERSEDED`.


* Update inbound references across `AGENTS.md`, `README.md`, and design documents.



### Phase 4: Portability Smoke Test (`citadel`)



* Initialize board in `C:\github\citadel` with prefix `CIT`.


* Claim a ticket with `--worktree`, verify worktree creation, run validation, move to `4-verifying`.
* Confirm zero changes required in `agent-kanban` Layer 1 core.



---

## 8. Verification & Acceptance Checkpoints



* [ ] Linter exits `0` on clean board and `1` on negative test fixtures (CRLF and LF).


* [ ] Claiming with `--worktree` provisions an isolated directory and tracks branch commits correctly.
* [ ] Running `tools/run_all_tests.ps1` in `heirs_ancients` passes with DI-06 green.


* [ ] No remaining references to stale `plan.md` across project repositories.


* [ ] STATUS.md updates automatically on any ticket transition.

```

```