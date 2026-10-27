---
id: KB-005
title: "Rename the bundled blast-radius skill: it collides with the ticket field of the same name"
status: verifying
owner: claude-coder
branch: ticket/KB-005
worktree: .worktrees/KB-005
created: 2026-10-25
updated: 2026-10-26
legacy_id: ""
design_docs: []
depends_on: []
blocked_on: ""
junctions: []
source_doc: ""
source_anchor: ""
source_hash: ""
validation_class: headless-verified
contract_hash: 1ef52016b0f3a7a1
confirmed: ""
verified_sha: 4a03df13f52a76c221bc77f2ce85fca4a076a2df
reviewer: Tim Niles
approved_sha: 4a03df13f52a76c221bc77f2ce85fca4a076a2df
approval_sig: 1353ede6636fd40c60d95b48c7080ae43542f0eb5fcb68290920a4bb0fc6d2f0
integrated_sha: ""
---

## Problem
The bundled skill `blast-radius` shares its name with the ticket field `## Blast radius`, so `/blast-radius` and the field are easy to
confuse (the field is the files a coder may touch; the skill is a method for finding what a change breaks elsewhere). Rename the
skill to `change-impact` (decided with the user, 2026-10-26) everywhere it is shipped: the bundle, `adapters/skills`, `.agents/skills` and the lock.
Mentions of the ticket field stay as they are. The rename needs more files than the usual limit of 3, so `max_blast_radius_files`
is raised for this one ticket and restored when it is done.

## Acceptance criteria
- [x] the bundled skills include `change-impact` and no longer include `blast-radius` (test: `python -m pytest tests/test_skills_sources.py -q -k change_impact`)
- [x] `/blast-radius` in the factory-mode skill now reads `/change-impact`, and `kahnban skills check` passes (test: `python -m pytest tests/test_skills_sources.py -q -k change_impact_is_referenced`)

## Blast radius
- `src/kahnban/templates/skills/blast-radius/SKILL.md`
- `src/kahnban/templates/skills/change-impact/SKILL.md`
- `src/kahnban/templates/skills/factory-mode/SKILL.md`
- `adapters/skills/blast-radius/SKILL.md`
- `adapters/skills/change-impact/SKILL.md`
- `adapters/skills/factory-mode/SKILL.md`
- `.agents/skills/blast-radius/SKILL.md`
- `.agents/skills/change-impact/SKILL.md`
- `.agents/skills/factory-mode/SKILL.md`
- `.agents/skills.lock.json`
- `tests/test_skills_sources.py`

## Implementation notes
- Do it in the bundle first (`git mv`, then `name:` and the `# Blast radius` heading in SKILL.md, and the factory-mode line), then copy the same files to `adapters/skills` and `.agents/skills`, then `kahnban skills lock`.
- Leave the other skills' wording about the ticket's blast radius alone.
- Tests: read the bundled skill names from `src/kahnban/templates/skills` and check factory-mode's text.

## Validation
```
python -m pytest tests/test_skills_sources.py -q
python -m kahnban skills check
```

## Log
- 2026-10-25 17:51 - created -> 0-backlog | captured
- 2026-10-26 22:25 - manual move 0-backlog -> 1-refining: refine
- 2026-10-26 22:25 - ready gate passed -> 2-ready | contract 1ef52016b0f3a7a1
- 2026-10-26 22:25 - claimed by claude-coder -> 3-in-progress
- 2026-10-26 22:26 - verify exit=0 in 204.0s (cwd=KB-005) -> 4-verifying
    verifying ticket/KB-005 at 4a03df13f52a; Running Tier 1 (Feature Tests): python -m pytest tests/test_skills_sources.py -q
python -m kahnban skills check; Running Tier 2 (Regression Tests): python tests/run_parallel.py -j 8
    $ [python -m pytest tests/test_skills_sources.py -q
python -m kahnban skills check] && [2/2 criterion tests] && [python tests/run_parallel.py -j 8] && [red check vs 3431e14e7483]
    === TIER 1: FEATURE TESTS ===
    $ python -m pytest tests/test_skills_sources.py -q
    ................                                                         [100%]

    $ python -m kahnban skills check
    [OK] skills, roles and generated agent files agree


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_skills_sources.py -q -k change_impact
    ..                                                                       [100%]

    [PASS] $ python -m pytest tests/test_skills_sources.py -q -k change_impact_is_referenced
    .                                                                        [100%]


    === TIER 2: REGRESSION TESTS ===
    715 tests, 8 workers, 182s, all passed


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    $ python -m pytest tests/test_skills_sources.py -q
    ..............FF                                                         [100%]
    ================================== FAILURES ===================================
    ________ test_the_bundle_ships_change_impact_and_no_blast_radius_skill ________

        def test_the_bundle_ships_change_impact_and_no_blast_radius_skill() -> None:
            names = {path.name for path in BUNDLE.iterdir() if path.is_dir()}

    >       assert "change-impact" in names
    E       AssertionError: assert 'change-impact' in {'blast-radius', 'code-review', 'coder-agent', 'create-verification-skill', 'factory-mode', 'grill-with-docs', ...}

    tests\test_skills_sources.py:218: AssertionError
    ______________ test_change_impact_is_referenced_by_factory_mode _______________

        def test_change_impact_is_referenced_by_factory_mode() -> None:
            text = (BUNDLE / "factory-mode" / "SKILL.md").read_text(encoding="utf-8")

    >       assert "`/change-impact`" in text
    E       assert '`/change-impact`' in '---\nname: factory-mode\ndescription: "Master agent conductor for the Kahnban Software Factory. Orchestrates the full..../learnings/` queue through the 4-tier structural escalation ladder into persistent rules, skills, and linter hooks.\n'

    tests\test_skills_sources.py:226: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_skills_sources.py::test_the_bundle_ships_change_impact_and_no_blast_radius_skill
    FAILED tests/test_skills_sources.py::test_change_impact_is_referenced_by_factory_mode

    [line 1 of 2 exited 1; rest skipped]
    full output: plans/tickets/.artifacts/KB-005-20261026-222619.log
- 2026-10-26 22:39 - approved by Tim Niles at 4a03df13f52a