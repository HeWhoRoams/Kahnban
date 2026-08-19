# Entry Points — from ideation, a plan, or a feature spec to an executable board

Kahnban is a conduit: whatever produced the work — a conversation, an
AI-generated plan document, a one-line hunch — it ends up as tickets that carry
machine-checked gates. Every entry point converges on the same ticket draft and
the same refinement gate, so nothing enters the pipeline pre-approved.

| You have | Command | Result |
| :--- | :--- | :--- |
| A hunch, mid-conversation | `kahnban capture "Try a warm cache"` | One backlog ticket per idea, one commit |
| An AI-generated plan | `kahnban ingest plans/PLAN.md` | One backlog ticket per work section, one commit |
| A plan you only partly trust | `kahnban ingest plans/PLAN.md --dry-run` | A preview; nothing is written |
| One feature spec per file | `kahnban ingest --per-file specs/*.md` | One ticket per document |
| Part of a large plan | `kahnban ingest plans/PLAN.md --section "Phase 3"` | Only that subtree |
| A sequential plan | `kahnban ingest plans/PLAN.md --chain` | Each ticket depends on the previous |
| A single well-specified ticket | `kahnban new "<title>" --problem-file spec.txt` | One backlog ticket |
| A fully specified ticket, from an agent | `kanban_ticket_new(title=…, acceptance=[…], blast_radius=[…], validation=…)` | One backlog ticket with a complete body |

## Two invariants that make this safe

**1. Ingestion never fabricates readiness.** Tickets land in `0-backlog` with
every acceptance box *unchecked*, even if the source document ticked them. A
section with no declared files gets an empty `## Blast radius`, and the
refinement gate refuses it — it does not inherit the template's example path.
Add `--ready` to attempt promotion: each ticket runs through the *real*
`kahnban ready` gate, and the ones that fail stay behind with the reason
reported.

```powershell
kahnban ingest plans/PLAN.md --ready
#   [OK] created TST-001: TST-001-warm-the-cache-on-boot.md
#   [OK] TST-001 passed the ready gate
#   [WARN] TST-003 stayed back: TST-003 is not ready:
```

**2. Ingestion is idempotent.** Each ticket records `source_doc`,
`source_anchor` (the heading path), and `source_hash` (a digest of that
section's text). Re-running ingest on the same plan:

- **unchanged section** → skipped, nothing written,
- **new section** → ingested as a new ticket,
- **changed section** → reported as drift, exit code 1, nothing overwritten.
  `--update` rewrites the ticket *only* while it is still in `0-backlog` or
  `1-refining`; a claimed or done ticket is never silently rewritten, and its
  `## Log` is preserved across a refresh.

`kahnban lint` rule **BL17** fails the board if two tickets ever claim the same
`source_doc#source_anchor`, which is what a double-ingest would look like.

Anchors deliberately exclude the document's top-level title, so retitling a plan
does not orphan every ticket it produced.

## The plan shape that ingests cleanly

Ingestion is heuristic — it reads ordinary markdown, and it tells you what it
could not interpret rather than guessing. It is most accurate when each work
item is one heading with labeled fields underneath. Both of these forms work:

```markdown
## Warm the cache on boot
**Why:** cold starts take 12 seconds.
**Acceptance:**
- [ ] boot warms the cache
- [ ] a cold start is under 2 seconds
**Files:** `src/cache.py`, `tests/cache_test.py`
**Validation:** `pytest tests/cache_test.py`
**Depends on:** Add the cache module
```

```markdown
### Wire the widget into the panel

Problem: the panel has no slot for the widget.

Acceptance criteria:
- [ ] panel exposes a widget slot

Files:
- `src/panel.py`

Validation:
```
pytest tests/panel_test.py
```
```

Recognized labels (as a heading *or* an inline `Label:`), case-insensitive:

| Ticket field | Accepted labels |
| :--- | :--- |
| `## Problem` | problem, why, context, background, rationale, goal, objective, summary, description |
| `## Acceptance criteria` | acceptance criteria, acceptance, success criteria, done when, definition of done, exit criteria, deliverables |
| `## Blast radius` | blast radius, files, files touched, files to change, affected files, touches, scope |
| `## Implementation notes` | implementation notes, notes, implementation, approach, design, steps, plan |
| `## Validation` | validation, verification, tests, test plan, how to test, validate, test command |
| `depends_on` | depends on, dependencies, blocked by, prerequisites, requires |
| `design_docs` | design docs, references, see also |
| `blocked_on` | blocked on, blocker, blocking reason, on hold, waiting on |

`depends_on` and `blocked_on` read differently even though both gate the ready
check: **"Blocked by: TICKET-004"** names another ticket and is resolved to its
ID (or, if it can't be resolved, becomes an entry in `blocked_on` automatically
— see below); **"Blocked on: a tagged release hasn't shipped yet"** is a
free-text reason that isn't itself a ticket, and is stored verbatim. Use
whichever label matches what you're actually saying.

An unresolvable dependency reference and an explicit `blocked_on` label combine
rather than overwrite each other — a ticket can be blocked for its own stated
reason *and* on a dependency nobody can find, and both show up in the field,
joined with `|`.

Add your own vocabulary in `plans/board.config.json` — configured names *extend*
the defaults:

```json
{
  "ingest": {
    "heading_level": null,
    "section_aliases": {
      "validation": ["tests to add"],
      "blast_radius": ["touched files"]
    }
  }
}
```

Other parsing behavior worth knowing:

- **Heading level is auto-detected**: the deepest level with two or more
  non-label headings. Override with `--heading-level N`.
- **Headings inside fenced code blocks are ignored**, so `# comment` lines in a
  validation snippet do not split the document.
- **Numbered prefixes are trimmed** from titles: `### 3.1 Add the widget` and
  `## Phase 2 - polish` become `Add the widget` and `polish`.
- **Unmapped subsections are preserved** under `## Implementation notes` with
  their heading demoted, so nothing in the source is lost.
- **Prose in a files list is not treated as a path.** `Files: the whole UI layer`
  produces no blast radius and leaves a note saying the entry was unparsed —
  the gate then refuses the ticket, which is the correct outcome.
- **Dependencies resolve by title, anchor, or ticket ID**, against both this
  batch and the existing board. An unresolvable reference goes into
  `blocked_on`, which blocks the ready gate until a human fixes it.

## Prompt snippet for the plan-writing agent

Paste this into whatever generates the plan, so its output ingests losslessly:

```markdown
Write the plan as markdown. Use one `##` heading per unit of work — a unit is
something one agent can finish and verify on its own. Under each heading, use
exactly these labels:

**Why:** one or two sentences on the behavioral gap.
**Acceptance:** a checkbox list of testable conditions. Leave every box
unchecked; they are ticked only after the test command passes.
**Files:** backtick-quoted paths or directory prefixes this unit may change.
Two units must never list overlapping paths — they will be refused as a
merge-conflict risk.
**Validation:** one command that exits non-zero on failure.
**Depends on:** titles of other units that must finish first (omit if none).

Do not invent file paths you have not confirmed exist, and do not write a
validation command you have not confirmed runs in this repository.
```

The "no overlapping files" instruction matters: overlapping blast radii are
refused at claim time, so a plan that partitions the codebase cleanly is a plan
whose tickets can be worked in parallel.

## Recommended loop

```powershell
kahnban ingest plans/PLAN.md --dry-run     # read what it found
kahnban ingest plans/PLAN.md --ready       # write, then attempt the gate
kahnban lint                               # board invariants, incl. BL17
kahnban status                             # what is where
# ... agents claim from 2-ready, refine the rest by hand ...
kahnban ingest plans/PLAN.md               # after the plan is regenerated
#   -> new sections ingested, unchanged skipped, drift reported
```

Every one of these writes a single commit on the default branch, so any step is
one `git revert` away from undone.
