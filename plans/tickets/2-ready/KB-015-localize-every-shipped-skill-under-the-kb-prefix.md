---
id: KB-015
title: Localize every shipped skill under the kb- prefix
status: ready
owner: unassigned
branch: ""
worktree: ""
created: 2026-10-29
updated: 2026-10-29
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md
source_anchor: tickets/localize-every-shipped-skill-under-the-k
source_hash: d825b39e1294
validation_class: headless-verified
covers: [R1, R2, R11]
spec: SPEC-001
contract_hash: 98bf897322080243
contract_sig: c82a57301659f196b2f916565436b78baf364c1a5b5609975e07917a142df9ba
confirmed: ""
---

## Problem

## Acceptance criteria
- [ ] every skill folder and frontmatter name under src/kahnban/templates/skills starts with kb- (test: `python -m pytest tests/test_skill_localization.py -q -k prefixed`)
- [ ] no shipped skill, roles.json, agent template, AGENTS.md template, README.md or docs/how-it-works.md names an unprefixed shipped skill (test: `python -m pytest tests/test_skill_localization.py -q -k no_unprefixed_refs`)
- [ ] no shipped file mentions the Lauren Tan Clustering Invariant, /implement-spec or /retro (test: `python -m pytest tests/test_skill_localization.py -q -k no_stale_attributions`)
- [ ] kahnban skills check passes on this repo (test: `kahnban skills check`)

## Blast radius
- `src/kahnban/templates/skills/change-impact/skill.md`
- `src/kahnban/templates/skills/code-review/skill.md`
- `src/kahnban/templates/skills/coder-agent/skill.md`
- `src/kahnban/templates/skills/create-verification-skill/skill.md`
- `src/kahnban/templates/skills/factory-mode/skill.md`
- `src/kahnban/templates/skills/grill-with-docs/skill.md`
- `src/kahnban/templates/skills/harvest-learnings/skill.md`
- `src/kahnban/templates/skills/how/skill.md`
- `src/kahnban/templates/skills/no-comments/skill.md`
- `src/kahnban/templates/skills/principle-boundary-discipline/skill.md`
- `src/kahnban/templates/skills/principle-encode-lessons-in-structure/skill.md`
- `src/kahnban/templates/skills/principle-fix-root-causes/skill.md`
- `src/kahnban/templates/skills/principle-guard-the-context-window/skill.md`
- `src/kahnban/templates/skills/principle-laziness-protocol/skill.md`
- `src/kahnban/templates/skills/principle-model-the-domain/skill.md`
- `src/kahnban/templates/skills/principle-never-block-on-the-human/skill.md`
- `src/kahnban/templates/skills/principle-prove-it-works/skill.md`
- `src/kahnban/templates/skills/principle-sequence-verifiable-units/skill.md`
- `src/kahnban/templates/skills/principle-subtract-before-you-add/skill.md`
- `src/kahnban/templates/skills/qa-reviewer-agent/skill.md`
- `src/kahnban/templates/skills/reflect/skill.md`
- `src/kahnban/templates/skills/setup-kahnban-skills/skill.md`
- `src/kahnban/templates/skills/tdd/skill.md`
- `src/kahnban/templates/skills/to-spec/skill.md`
- `src/kahnban/templates/skills/to-tickets/skill.md`
- `src/kahnban/templates/skills/unslop/skill.md`
- `src/kahnban/templates/skills/why/skill.md`
- `.agents/skills/change-impact/skill.md`
- `.agents/skills/code-review/skill.md`
- `.agents/skills/coder-agent/skill.md`
- `.agents/skills/create-verification-skill/skill.md`
- `.agents/skills/factory-mode/skill.md`
- `.agents/skills/grill-with-docs/skill.md`
- `.agents/skills/harvest-learnings/skill.md`
- `.agents/skills/how/skill.md`
- `.agents/skills/no-comments/skill.md`
- `.agents/skills/principle-boundary-discipline/skill.md`
- `.agents/skills/principle-encode-lessons-in-structure/skill.md`
- `.agents/skills/principle-fix-root-causes/skill.md`
- `.agents/skills/principle-guard-the-context-window/skill.md`
- `.agents/skills/principle-laziness-protocol/skill.md`
- `.agents/skills/principle-model-the-domain/skill.md`
- `.agents/skills/principle-never-block-on-the-human/skill.md`
- `.agents/skills/principle-prove-it-works/skill.md`
- `.agents/skills/principle-sequence-verifiable-units/skill.md`
- `.agents/skills/principle-subtract-before-you-add/skill.md`
- `.agents/skills/qa-reviewer-agent/skill.md`
- `.agents/skills/reflect/skill.md`
- `.agents/skills/setup-kahnban-skills/skill.md`
- `.agents/skills/tdd/skill.md`
- `.agents/skills/to-spec/skill.md`
- `.agents/skills/to-tickets/skill.md`
- `.agents/skills/unslop/skill.md`
- `.agents/skills/why/skill.md`
- `.claude/skills/change-impact/skill.md`
- `.claude/skills/code-review/skill.md`
- `.claude/skills/coder-agent/skill.md`
- `.claude/skills/create-verification-skill/skill.md`
- `.claude/skills/factory-mode/skill.md`
- `.claude/skills/grill-with-docs/skill.md`
- `.claude/skills/harvest-learnings/skill.md`
- `.claude/skills/how/skill.md`
- `.claude/skills/no-comments/skill.md`
- `.claude/skills/principle-boundary-discipline/skill.md`
- `.claude/skills/principle-encode-lessons-in-structure/skill.md`
- `.claude/skills/principle-fix-root-causes/skill.md`
- `.claude/skills/principle-guard-the-context-window/skill.md`
- `.claude/skills/principle-laziness-protocol/skill.md`
- `.claude/skills/principle-model-the-domain/skill.md`
- `.claude/skills/principle-never-block-on-the-human/skill.md`
- `.claude/skills/principle-prove-it-works/skill.md`
- `.claude/skills/principle-sequence-verifiable-units/skill.md`
- `.claude/skills/principle-subtract-before-you-add/skill.md`
- `.claude/skills/qa-reviewer-agent/skill.md`
- `.claude/skills/reflect/skill.md`
- `.claude/skills/setup-kahnban-skills/skill.md`
- `.claude/skills/tdd/skill.md`
- `.claude/skills/to-spec/skill.md`
- `.claude/skills/to-tickets/skill.md`
- `.claude/skills/unslop/skill.md`
- `.claude/skills/why/skill.md`
- `adapters/skills/change-impact/skill.md`
- `adapters/skills/code-review/skill.md`
- `adapters/skills/coder-agent/skill.md`
- `adapters/skills/create-verification-skill/skill.md`
- `adapters/skills/factory-mode/skill.md`
- `adapters/skills/grill-with-docs/skill.md`
- `adapters/skills/harvest-learnings/skill.md`
- `adapters/skills/how/skill.md`
- `adapters/skills/no-comments/skill.md`
- `adapters/skills/principle-boundary-discipline/skill.md`
- `adapters/skills/principle-encode-lessons-in-structure/skill.md`
- `adapters/skills/principle-fix-root-causes/skill.md`
- `adapters/skills/principle-guard-the-context-window/skill.md`
- `adapters/skills/principle-laziness-protocol/skill.md`
- `adapters/skills/principle-model-the-domain/skill.md`
- `adapters/skills/principle-never-block-on-the-human/skill.md`
- `adapters/skills/principle-prove-it-works/skill.md`
- `adapters/skills/principle-sequence-verifiable-units/skill.md`
- `adapters/skills/principle-subtract-before-you-add/skill.md`
- `adapters/skills/qa-reviewer-agent/skill.md`
- `adapters/skills/reflect/skill.md`
- `adapters/skills/setup-kahnban-skills/skill.md`
- `adapters/skills/tdd/skill.md`
- `adapters/skills/to-spec/skill.md`
- `adapters/skills/to-tickets/skill.md`
- `adapters/skills/unslop/skill.md`
- `adapters/skills/why/skill.md`
- `src/kahnban/templates/skills/kb-change-impact/skill.md`
- `.agents/skills/kb-change-impact/skill.md`
- `.claude/skills/kb-change-impact/skill.md`
- `adapters/skills/kb-change-impact/skill.md`
- `src/kahnban/templates/skills/kb-code-review/skill.md`
- `.agents/skills/kb-code-review/skill.md`
- `.claude/skills/kb-code-review/skill.md`
- `adapters/skills/kb-code-review/skill.md`
- `src/kahnban/templates/skills/kb-coder-agent/skill.md`
- `.agents/skills/kb-coder-agent/skill.md`
- `.claude/skills/kb-coder-agent/skill.md`
- `adapters/skills/kb-coder-agent/skill.md`
- `src/kahnban/templates/skills/kb-create-verification-skill/skill.md`
- `.agents/skills/kb-create-verification-skill/skill.md`
- `.claude/skills/kb-create-verification-skill/skill.md`
- `adapters/skills/kb-create-verification-skill/skill.md`
- `src/kahnban/templates/skills/kb-factory-mode/skill.md`
- `.agents/skills/kb-factory-mode/skill.md`
- `.claude/skills/kb-factory-mode/skill.md`
- `adapters/skills/kb-factory-mode/skill.md`
- `src/kahnban/templates/skills/kb-grill-with-docs/skill.md`
- `.agents/skills/kb-grill-with-docs/skill.md`
- `.claude/skills/kb-grill-with-docs/skill.md`
- `adapters/skills/kb-grill-with-docs/skill.md`
- `src/kahnban/templates/skills/kb-harvest-learnings/skill.md`
- `.agents/skills/kb-harvest-learnings/skill.md`
- `.claude/skills/kb-harvest-learnings/skill.md`
- `adapters/skills/kb-harvest-learnings/skill.md`
- `src/kahnban/templates/skills/kb-how/skill.md`
- `.agents/skills/kb-how/skill.md`
- `.claude/skills/kb-how/skill.md`
- `adapters/skills/kb-how/skill.md`
- `src/kahnban/templates/skills/kb-no-comments/skill.md`
- `.agents/skills/kb-no-comments/skill.md`
- `.claude/skills/kb-no-comments/skill.md`
- `adapters/skills/kb-no-comments/skill.md`
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
- `src/kahnban/templates/skills/kb-qa-reviewer-agent/skill.md`
- `.agents/skills/kb-qa-reviewer-agent/skill.md`
- `.claude/skills/kb-qa-reviewer-agent/skill.md`
- `adapters/skills/kb-qa-reviewer-agent/skill.md`
- `src/kahnban/templates/skills/kb-reflect/skill.md`
- `.agents/skills/kb-reflect/skill.md`
- `.claude/skills/kb-reflect/skill.md`
- `adapters/skills/kb-reflect/skill.md`
- `src/kahnban/templates/skills/kb-setup-kahnban-skills/skill.md`
- `.agents/skills/kb-setup-kahnban-skills/skill.md`
- `.claude/skills/kb-setup-kahnban-skills/skill.md`
- `adapters/skills/kb-setup-kahnban-skills/skill.md`
- `src/kahnban/templates/skills/kb-tdd/skill.md`
- `.agents/skills/kb-tdd/skill.md`
- `.claude/skills/kb-tdd/skill.md`
- `adapters/skills/kb-tdd/skill.md`
- `src/kahnban/templates/skills/kb-to-spec/skill.md`
- `.agents/skills/kb-to-spec/skill.md`
- `.claude/skills/kb-to-spec/skill.md`
- `adapters/skills/kb-to-spec/skill.md`
- `src/kahnban/templates/skills/kb-to-tickets/skill.md`
- `.agents/skills/kb-to-tickets/skill.md`
- `.claude/skills/kb-to-tickets/skill.md`
- `adapters/skills/kb-to-tickets/skill.md`
- `src/kahnban/templates/skills/kb-unslop/skill.md`
- `.agents/skills/kb-unslop/skill.md`
- `.claude/skills/kb-unslop/skill.md`
- `adapters/skills/kb-unslop/skill.md`
- `src/kahnban/templates/skills/kb-why/skill.md`
- `.agents/skills/kb-why/skill.md`
- `.claude/skills/kb-why/skill.md`
- `adapters/skills/kb-why/skill.md`
- `src/kahnban/templates/roles.json`
- `src/kahnban/harnesses.py`
- `src/kahnban/dispatcher.py`
- `src/kahnban/runner.py`
- `src/kahnban/learnings.py`
- `src/kahnban/templates/agents.md`
- `src/kahnban/templates/adr.md`
- `src/kahnban/templates/glossary.md`
- `.agents/agents.md`
- `.agents/templates/adr-template.md`
- `.agents/templates/glossary-template.md`
- `adapters/agents.md`
- `adapters/readme.md`
- `adapters/templates/adr-template.md`
- `adapters/templates/glossary-template.md`
- `readme.md`
- `docs/how-it-works.md`
- `.claude/agents/kahnban-coder.md`
- `.claude/agents/kahnban-curator.md`
- `.claude/agents/kahnban-qa-reviewer.md`
- `.claude/agents/kahnban-spec-analyst.md`
- `tests/golden/agents/claude/kahnban-coder.md`
- `tests/golden/agents/claude/kahnban-curator.md`
- `tests/golden/agents/claude/kahnban-qa-reviewer.md`
- `tests/golden/agents/claude/kahnban-spec-analyst.md`
- `tests/golden/agents/cursor/kahnban-coder.md`
- `tests/golden/agents/cursor/kahnban-curator.md`
- `tests/golden/agents/cursor/kahnban-qa-reviewer.md`
- `tests/golden/agents/cursor/kahnban-spec-analyst.md`
- `tests/golden/agents/gemini/kahnban-coder.md`
- `tests/golden/agents/gemini/kahnban-curator.md`
- `tests/golden/agents/gemini/kahnban-qa-reviewer.md`
- `tests/golden/agents/gemini/kahnban-spec-analyst.md`
- `tests/sim/agent.py`
- `tests/test_audit_fixes.py`
- `tests/test_init_agentic.py`
- `tests/test_roles.py`
- `tests/test_runner_edges.py`
- `src/kahnban/cli.py`
- `tests/test_trust.py`
- `tests/test_hooks_trust_edges.py`
- `tests/test_skills.py`
- `tests/test_skills_sources.py`
- `tests/test_contracts.py`
- `.agents/skills.lock.json`
- `tests/test_skill_localization.py`

## Implementation notes

## Validation
```
python -m pytest tests/test_skill_localization.py -q
```

## Log
- 2026-10-29 20:44 - created -> 0-backlog | ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/localize-every-shipped-skill-under-the-k
- 2026-10-29 20:44 - manual move 0-backlog -> 1-refining: ingested plan section entering refinement
- 2026-10-29 20:44 - ready gate passed -> 2-ready | contract f7ba8882bc61f282
- 2026-10-29 21:13 - claimed by coder-agent -> 3-in-progress
- 2026-10-29 23:07 - verify exit=1 in 235.8s (cwd=KB-015) (no transition)
    verifying ticket/KB-015 at 5ab8e60f53f2; Running Tier 1 (Feature Tests): python -m pytest tests/test_skill_localization.py -q; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_skill_localization.py -q] && [4/4 criterion tests] && [python tests/run_parallel.py -j 8]
    === TIER 1: FEATURE TESTS ===
    ...                                                                      [100%]
    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_skill_localization.py -q -k prefixed
    ..                                                                       [100%]
    [PASS] $ python -m pytest tests/test_skill_localization.py -q -k no_unprefixed_refs
    .                                                                        [100%]
    [PASS] $ python -m pytest tests/test_skill_localization.py -q -k no_stale_attributions
    .                                                                        [100%]
    [PASS] $ kahnban skills check
    [OK] skills, roles and generated agent files agree
    === TIER 2: REGRESSION TESTS ===
    FAILED tests/test_trust.py::test_installing_says_which_tampered_file_it_restored
    FAILED tests/test_contracts.py::test_adapter_skills_match_the_shipped_templates
    FAILED tests/test_trust.py::test_a_changed_skill_or_hook_breaks_the_check_until_it_is_re_pinned
    739 tests, 8 workers, 215s, FAILURES
    full output: plans/tickets/.artifacts/KB-015-20261029-230729.log
- 2026-10-29 23:20 - manual move 3-in-progress -> 1-refining: KB-015's radius missed cli.py, test_trust.py and test_hooks_trust_edges.py (SPEC-001 breakdown error); contract must be re-frozen. Coder's attempt kept on ticket/KB-015.
- 2026-10-29 23:20 - re-ingested from .agents/specs/SPEC-001-phase-0-1-elevation-localized-skill-set-dependen.md#tickets/localize-every-shipped-skill-under-the-k (source_hash d825b39e1294)
- 2026-10-29 23:20 - ready gate passed -> 2-ready | contract 98bf897322080243
- 2026-10-29 23:24 - escalated to a human: 'claim_and_implement' made no progress after 3 attempts; last: refused: worktree path already exists: C:\github\kahnban\.worktrees\KB-015
- 2026-10-29 23:24 - unblocked: stale worktree from the pre-amend attempt was removed; the corrected contract is ready to claim