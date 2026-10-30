---
id: KB-017
title: Re-base the Pocock-derived skills on mattpocock/skills v1.3.2
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-016]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/re-base-the-pocock-derived-skills-on-mat
source_hash: 0c2bf7a1a71e
validation_class: headless-verified
covers: [R4]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] kb-grilling and kb-domain-modeling (with ADR-FORMAT.md and GLOSSARY-FORMAT.md) are shipped and installed (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k new_skills_shipped`)
- [ ] provenance for the seven skills names mattpocock/skills at v1.3.2 and each upstream path (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k provenance_pinned`)
- [ ] each of the seven ends with a '## Kahnban adaptations' section listing every deviation from upstream, and nothing else differs (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k adaptations_declared`)
- [ ] kb-to-tickets still requires exact file paths, the file cap, Covers R-ids and kahnban ingest (test: `python -m pytest tests/test_skill_upstream_pocock.py -q -k gate_rules_kept`)
- [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)

## Blast radius
- `src/kahnban/templates/skills/kb-grill-with-docs/skill.md`
- `.agents/skills/kb-grill-with-docs/skill.md`
- `.claude/skills/kb-grill-with-docs/skill.md`
- `adapters/skills/kb-grill-with-docs/skill.md`
- `src/kahnban/templates/skills/kb-grilling/skill.md`
- `.agents/skills/kb-grilling/skill.md`
- `.claude/skills/kb-grilling/skill.md`
- `adapters/skills/kb-grilling/skill.md`
- `src/kahnban/templates/skills/kb-to-spec/skill.md`
- `.agents/skills/kb-to-spec/skill.md`
- `.claude/skills/kb-to-spec/skill.md`
- `adapters/skills/kb-to-spec/skill.md`
- `src/kahnban/templates/skills/kb-to-tickets/skill.md`
- `.agents/skills/kb-to-tickets/skill.md`
- `.claude/skills/kb-to-tickets/skill.md`
- `adapters/skills/kb-to-tickets/skill.md`
- `src/kahnban/templates/skills/kb-code-review/skill.md`
- `.agents/skills/kb-code-review/skill.md`
- `.claude/skills/kb-code-review/skill.md`
- `adapters/skills/kb-code-review/skill.md`
- `src/kahnban/templates/skills/kb-tdd/skill.md`
- `src/kahnban/templates/skills/kb-tdd/mocking.md`
- `src/kahnban/templates/skills/kb-tdd/tests.md`
- `.agents/skills/kb-tdd/skill.md`
- `.agents/skills/kb-tdd/mocking.md`
- `.agents/skills/kb-tdd/tests.md`
- `.claude/skills/kb-tdd/skill.md`
- `.claude/skills/kb-tdd/mocking.md`
- `.claude/skills/kb-tdd/tests.md`
- `adapters/skills/kb-tdd/skill.md`
- `adapters/skills/kb-tdd/mocking.md`
- `adapters/skills/kb-tdd/tests.md`
- `src/kahnban/templates/skills/kb-domain-modeling/skill.md`
- `src/kahnban/templates/skills/kb-domain-modeling/adr-format.md`
- `src/kahnban/templates/skills/kb-domain-modeling/glossary-format.md`
- `.agents/skills/kb-domain-modeling/skill.md`
- `.agents/skills/kb-domain-modeling/adr-format.md`
- `.agents/skills/kb-domain-modeling/glossary-format.md`
- `.claude/skills/kb-domain-modeling/skill.md`
- `.claude/skills/kb-domain-modeling/adr-format.md`
- `.claude/skills/kb-domain-modeling/glossary-format.md`
- `adapters/skills/kb-domain-modeling/skill.md`
- `adapters/skills/kb-domain-modeling/adr-format.md`
- `adapters/skills/kb-domain-modeling/glossary-format.md`
- `src/kahnban/templates/provenance.json`
- `.agents/skills.lock.json`
- `tests/test_skill_upstream_pocock.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skill_upstream_pocock.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/re-base-the-pocock-derived-skills-on-mat