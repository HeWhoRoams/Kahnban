---
id: KB-001
title: A SKILL.md without frontmatter lists with an empty description
status: in-progress
owner: claude-coder
branch: ticket/KB-001
worktree: .worktrees/KB-001
created: 2026-10-25
updated: 2026-10-25
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 169b13c85d65e848
confirmed: ""
---

## Problem
`skills._read_skill_description` swallows the error that a `SKILL.md` without frontmatter raises, so
`kahnban skills list` shows such a skill with an empty description although the file has a heading
or a first line that would do. Found by the coverage work on `skills.py`; `tests/test_skills_sources.py` records the empty result today.

## Acceptance criteria
- [ ] a SKILL.md with no frontmatter is described by its first heading, or its first line (test: `python -m pytest tests/test_skills_sources.py -q -k bare_skill_file`)
- [ ] a SKILL.md with frontmatter is described exactly as before (test: `python -m pytest tests/test_skills_sources.py -q -k description_comes_from`)

## Blast radius
- `src/kahnban/skills.py`
- `tests/test_skills_sources.py`

## Implementation notes
- When `frontmatter.parse` raises, parse nothing and fall through to the same heading and first-line search on the whole text.
- Replace the `bare` assertion in `test_a_description_comes_from_the_frontmatter_then_the_first_heading_then_the_first_line` and add `test_a_bare_skill_file_is_described_by_its_first_line`.

## Validation
```
python -m pytest tests/test_skills_sources.py -q
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-25 17:51 - ready gate passed -> 2-ready | contract 169b13c85d65e848
- 2026-10-25 17:51 - claimed by claude-coder -> 3-in-progress