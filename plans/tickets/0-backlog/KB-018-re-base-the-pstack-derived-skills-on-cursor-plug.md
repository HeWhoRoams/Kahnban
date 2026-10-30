---
id: KB-018
title: Re-base the pstack-derived skills on cursor/plugins c742dd6
status: backlog
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: [KB-017]
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/re-base-the-pstack-derived-skills-on-cur
source_hash: 458c783b09a4
validation_class: headless-verified
covers: [R5]
spec: SPEC-001
---

## Problem

## Acceptance criteria
- [ ] kb-principle-build-the-lever, kb-principle-redesign-from-first-principles and kb-show-me-your-work are shipped (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k missing_skills_imported`)
- [ ] provenance for every pstack-derived skill names cursor/plugins at c742dd6 and its upstream path (blast-radius for kb-change-impact) (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k provenance_pinned`)
- [ ] supporting files in nested folders (references/, scripts/) are installed with their skill (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k nested_files_installed`)
- [ ] no shipped skill mentions poteto-mode (test: `python -m pytest tests/test_skill_upstream_pstack.py -q -k no_poteto_mode`)
- [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)

## Blast radius
- `src/kahnban/templates/skills/kb-principle-boundary-discipline/skill.md`
- `.agents/skills/kb-principle-boundary-discipline/skill.md`
- `.claude/skills/kb-principle-boundary-discipline/skill.md`
- `adapters/skills/kb-principle-boundary-discipline/skill.md`
- `src/kahnban/templates/skills/kb-principle-encode-lessons-in-structure/skill.md`
- `.agents/skills/kb-principle-encode-lessons-in-structure/skill.md`
- `.claude/skills/kb-principle-encode-lessons-in-structure/skill.md`
- `adapters/skills/kb-principle-encode-lessons-in-structure/skill.md`
- `src/kahnban/templates/skills/kb-principle-fix-root-causes/skill.md`
- `.agents/skills/kb-principle-fix-root-causes/skill.md`
- `.claude/skills/kb-principle-fix-root-causes/skill.md`
- `adapters/skills/kb-principle-fix-root-causes/skill.md`
- `src/kahnban/templates/skills/kb-principle-guard-the-context-window/skill.md`
- `.agents/skills/kb-principle-guard-the-context-window/skill.md`
- `.claude/skills/kb-principle-guard-the-context-window/skill.md`
- `adapters/skills/kb-principle-guard-the-context-window/skill.md`
- `src/kahnban/templates/skills/kb-principle-laziness-protocol/skill.md`
- `.agents/skills/kb-principle-laziness-protocol/skill.md`
- `.claude/skills/kb-principle-laziness-protocol/skill.md`
- `adapters/skills/kb-principle-laziness-protocol/skill.md`
- `src/kahnban/templates/skills/kb-principle-model-the-domain/skill.md`
- `.agents/skills/kb-principle-model-the-domain/skill.md`
- `.claude/skills/kb-principle-model-the-domain/skill.md`
- `adapters/skills/kb-principle-model-the-domain/skill.md`
- `src/kahnban/templates/skills/kb-principle-never-block-on-the-human/skill.md`
- `.agents/skills/kb-principle-never-block-on-the-human/skill.md`
- `.claude/skills/kb-principle-never-block-on-the-human/skill.md`
- `adapters/skills/kb-principle-never-block-on-the-human/skill.md`
- `src/kahnban/templates/skills/kb-principle-prove-it-works/skill.md`
- `.agents/skills/kb-principle-prove-it-works/skill.md`
- `.claude/skills/kb-principle-prove-it-works/skill.md`
- `adapters/skills/kb-principle-prove-it-works/skill.md`
- `src/kahnban/templates/skills/kb-principle-sequence-verifiable-units/skill.md`
- `.agents/skills/kb-principle-sequence-verifiable-units/skill.md`
- `.claude/skills/kb-principle-sequence-verifiable-units/skill.md`
- `adapters/skills/kb-principle-sequence-verifiable-units/skill.md`
- `src/kahnban/templates/skills/kb-principle-subtract-before-you-add/skill.md`
- `.agents/skills/kb-principle-subtract-before-you-add/skill.md`
- `.claude/skills/kb-principle-subtract-before-you-add/skill.md`
- `adapters/skills/kb-principle-subtract-before-you-add/skill.md`
- `src/kahnban/templates/skills/kb-principle-build-the-lever/skill.md`
- `.agents/skills/kb-principle-build-the-lever/skill.md`
- `.claude/skills/kb-principle-build-the-lever/skill.md`
- `adapters/skills/kb-principle-build-the-lever/skill.md`
- `src/kahnban/templates/skills/kb-principle-redesign-from-first-principles/skill.md`
- `.agents/skills/kb-principle-redesign-from-first-principles/skill.md`
- `.claude/skills/kb-principle-redesign-from-first-principles/skill.md`
- `adapters/skills/kb-principle-redesign-from-first-principles/skill.md`
- `src/kahnban/templates/skills/kb-how/skill.md`
- `src/kahnban/templates/skills/kb-how/references/explainer-prompt.md`
- `src/kahnban/templates/skills/kb-how/references/explorer-prompt.md`
- `.agents/skills/kb-how/skill.md`
- `.agents/skills/kb-how/references/explainer-prompt.md`
- `.agents/skills/kb-how/references/explorer-prompt.md`
- `.claude/skills/kb-how/skill.md`
- `.claude/skills/kb-how/references/explainer-prompt.md`
- `.claude/skills/kb-how/references/explorer-prompt.md`
- `adapters/skills/kb-how/skill.md`
- `adapters/skills/kb-how/references/explainer-prompt.md`
- `adapters/skills/kb-how/references/explorer-prompt.md`
- `src/kahnban/templates/skills/kb-why/skill.md`
- `src/kahnban/templates/skills/kb-why/references/epistemics.md`
- `src/kahnban/templates/skills/kb-why/references/investigator-prompt.md`
- `src/kahnban/templates/skills/kb-why/references/source-playbook.md`
- `src/kahnban/templates/skills/kb-why/references/synthesizer-prompt.md`
- `src/kahnban/templates/skills/kb-why/references/sources/code-archaeology.md`
- `src/kahnban/templates/skills/kb-why/references/sources/databricks.md`
- `src/kahnban/templates/skills/kb-why/references/sources/datadog.md`
- `src/kahnban/templates/skills/kb-why/references/sources/incident-postmortem.md`
- `src/kahnban/templates/skills/kb-why/references/sources/linear.md`
- `src/kahnban/templates/skills/kb-why/references/sources/notion.md`
- `src/kahnban/templates/skills/kb-why/references/sources/sentry.md`
- `src/kahnban/templates/skills/kb-why/references/sources/slack.md`
- `.agents/skills/kb-why/skill.md`
- `.agents/skills/kb-why/references/epistemics.md`
- `.agents/skills/kb-why/references/investigator-prompt.md`
- `.agents/skills/kb-why/references/source-playbook.md`
- `.agents/skills/kb-why/references/synthesizer-prompt.md`
- `.agents/skills/kb-why/references/sources/code-archaeology.md`
- `.agents/skills/kb-why/references/sources/databricks.md`
- `.agents/skills/kb-why/references/sources/datadog.md`
- `.agents/skills/kb-why/references/sources/incident-postmortem.md`
- `.agents/skills/kb-why/references/sources/linear.md`
- `.agents/skills/kb-why/references/sources/notion.md`
- `.agents/skills/kb-why/references/sources/sentry.md`
- `.agents/skills/kb-why/references/sources/slack.md`
- `.claude/skills/kb-why/skill.md`
- `.claude/skills/kb-why/references/epistemics.md`
- `.claude/skills/kb-why/references/investigator-prompt.md`
- `.claude/skills/kb-why/references/source-playbook.md`
- `.claude/skills/kb-why/references/synthesizer-prompt.md`
- `.claude/skills/kb-why/references/sources/code-archaeology.md`
- `.claude/skills/kb-why/references/sources/databricks.md`
- `.claude/skills/kb-why/references/sources/datadog.md`
- `.claude/skills/kb-why/references/sources/incident-postmortem.md`
- `.claude/skills/kb-why/references/sources/linear.md`
- `.claude/skills/kb-why/references/sources/notion.md`
- `.claude/skills/kb-why/references/sources/sentry.md`
- `.claude/skills/kb-why/references/sources/slack.md`
- `adapters/skills/kb-why/skill.md`
- `adapters/skills/kb-why/references/epistemics.md`
- `adapters/skills/kb-why/references/investigator-prompt.md`
- `adapters/skills/kb-why/references/source-playbook.md`
- `adapters/skills/kb-why/references/synthesizer-prompt.md`
- `adapters/skills/kb-why/references/sources/code-archaeology.md`
- `adapters/skills/kb-why/references/sources/databricks.md`
- `adapters/skills/kb-why/references/sources/datadog.md`
- `adapters/skills/kb-why/references/sources/incident-postmortem.md`
- `adapters/skills/kb-why/references/sources/linear.md`
- `adapters/skills/kb-why/references/sources/notion.md`
- `adapters/skills/kb-why/references/sources/sentry.md`
- `adapters/skills/kb-why/references/sources/slack.md`
- `src/kahnban/templates/skills/kb-no-comments/skill.md`
- `.agents/skills/kb-no-comments/skill.md`
- `.claude/skills/kb-no-comments/skill.md`
- `adapters/skills/kb-no-comments/skill.md`
- `src/kahnban/templates/skills/kb-unslop/skill.md`
- `.agents/skills/kb-unslop/skill.md`
- `.claude/skills/kb-unslop/skill.md`
- `adapters/skills/kb-unslop/skill.md`
- `src/kahnban/templates/skills/kb-change-impact/skill.md`
- `.agents/skills/kb-change-impact/skill.md`
- `.claude/skills/kb-change-impact/skill.md`
- `adapters/skills/kb-change-impact/skill.md`
- `src/kahnban/templates/skills/kb-create-verification-skill/skill.md`
- `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/readme.md`
- `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`
- `src/kahnban/templates/skills/kb-create-verification-skill/references/feature-map-example/search.md`
- `.agents/skills/kb-create-verification-skill/skill.md`
- `.agents/skills/kb-create-verification-skill/references/feature-map-example/readme.md`
- `.agents/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`
- `.agents/skills/kb-create-verification-skill/references/feature-map-example/search.md`
- `.claude/skills/kb-create-verification-skill/skill.md`
- `.claude/skills/kb-create-verification-skill/references/feature-map-example/readme.md`
- `.claude/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`
- `.claude/skills/kb-create-verification-skill/references/feature-map-example/search.md`
- `adapters/skills/kb-create-verification-skill/skill.md`
- `adapters/skills/kb-create-verification-skill/references/feature-map-example/readme.md`
- `adapters/skills/kb-create-verification-skill/references/feature-map-example/create-note.md`
- `adapters/skills/kb-create-verification-skill/references/feature-map-example/search.md`
- `src/kahnban/templates/skills/kb-show-me-your-work/skill.md`
- `src/kahnban/templates/skills/kb-show-me-your-work/references/decision-log-template.tsv`
- `src/kahnban/templates/skills/kb-show-me-your-work/scripts/log.sh`
- `.agents/skills/kb-show-me-your-work/skill.md`
- `.agents/skills/kb-show-me-your-work/references/decision-log-template.tsv`
- `.agents/skills/kb-show-me-your-work/scripts/log.sh`
- `.claude/skills/kb-show-me-your-work/skill.md`
- `.claude/skills/kb-show-me-your-work/references/decision-log-template.tsv`
- `.claude/skills/kb-show-me-your-work/scripts/log.sh`
- `adapters/skills/kb-show-me-your-work/skill.md`
- `adapters/skills/kb-show-me-your-work/references/decision-log-template.tsv`
- `adapters/skills/kb-show-me-your-work/scripts/log.sh`
- `src/kahnban/skills.py`
- `src/kahnban/templates/provenance.json`
- `.agents/skills.lock.json`
- `tests/test_skill_upstream_pstack.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skill_upstream_pstack.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/re-base-the-pstack-derived-skills-on-cur