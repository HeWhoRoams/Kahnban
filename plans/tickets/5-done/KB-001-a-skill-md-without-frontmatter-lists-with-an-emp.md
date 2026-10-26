---
id: KB-001
title: A SKILL.md without frontmatter lists with an empty description
status: done
owner: claude-coder
branch: ""
worktree: ""
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
contract_hash: 169b13c85d65e848
confirmed: ""
verified_sha: 71934668a71646bdcbe5a22a346781ccd429a860
reviewer: Tim Niles
approved_sha: 71934668a71646bdcbe5a22a346781ccd429a860
approval_sig: fab84d32111cc2a15cf4587a44469a1fb1a6b087a4138754d4385a206a915b6f
integrated_sha: c0e536357f059b9f6e9574e13badc5b5ce7fbfa8
---

## Problem
`skills._read_skill_description` swallows the error that a `SKILL.md` without frontmatter raises, so
`kahnban skills list` shows such a skill with an empty description although the file has a heading
or a first line that would do. Found by the coverage work on `skills.py`; `tests/test_skills_sources.py` records the empty result today.

## Acceptance criteria
- [x] a SKILL.md with no frontmatter is described by its first heading, or its first line (test: `python -m pytest tests/test_skills_sources.py -q -k bare_skill_file`)
- [x] a SKILL.md with frontmatter is described exactly as before (test: `python -m pytest tests/test_skills_sources.py -q -k description_comes_from`)

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
- 2026-10-25 17:52 - verify exit=0 in 8.8s (cwd=KB-001) -> 4-verifying
    verifying ticket/KB-001 at 71934668a716; Running Tier 1 (Feature Tests): python -m pytest tests/test_skills_sources.py -q
    $ [python -m pytest tests/test_skills_sources.py -q] && [2/2 criterion tests] && [red check vs 2e56c55ce927]
    === TIER 1: FEATURE TESTS ===
    ..............                                                           [100%]


    === ACCEPTANCE CRITERIA ===
    [PASS] $ python -m pytest tests/test_skills_sources.py -q -k bare_skill_file
    .                                                                        [100%]

    [PASS] $ python -m pytest tests/test_skills_sources.py -q -k description_comes_from
    .                                                                        [100%]


    === RED CHECK: FEATURE TESTS ON THE BASE SOURCE (must fail) ===
    FF............                                                           [100%]
    ================================== FAILURES ===================================
    _ test_a_description_comes_from_the_frontmatter_then_the_first_heading_then_the_first_line _

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-375/test_a_description_comes_from_0')

        def test_a_description_comes_from_the_frontmatter_then_the_first_heading_then_the_first_line(tmp_path: Path) -> None:
            front = write_skill(tmp_path, "a", "---\nname: a\ndescription: Does the thing.\n---\n# A\n")
            heading = write_skill(tmp_path, "b", "---\nname: b\n---\n# Title of b\ntext\n")
            plain = write_skill(tmp_path, "c", "---\nname: c\n---\njust a line\n")
            bare = write_skill(tmp_path, "d", "no frontmatter at all\n")

            assert skills._read_skill_description(front) == "Does the thing."
            assert skills._read_skill_description(heading) == "Title of b"
            assert skills._read_skill_description(plain) == "just a line"
    >       assert skills._read_skill_description(bare) == "no frontmatter at all"
    E       AssertionError: assert '' == 'no frontmatter at all'
    E         
    E         - no frontmatter at all

    tests\test_skills_sources.py:34: AssertionError
    ______ test_a_bare_skill_file_is_described_by_its_first_heading_or_line _______

    tmp_path = WindowsPath('C:/Users/User/AppData/Local/Temp/pytest-of-User/pytest-375/test_a_bare_skill_file_is_desc0')

        def test_a_bare_skill_file_is_described_by_its_first_heading_or_line(tmp_path: Path) -> None:
            heading = write_skill(tmp_path, "h", "# Heading of the skill\nmore text\n")
            line = write_skill(tmp_path, "l", "\nFirst line of the skill\n# later heading\n")
            broken = write_skill(tmp_path, "b", "---\nnot: closed\n# Title after broken frontmatter\n")

    >       assert skills._read_skill_description(heading) == "Heading of the skill"
    E       AssertionError: assert '' == 'Heading of the skill'
    E         
    E         - Heading of the skill

    tests\test_skills_sources.py:43: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_skills_sources.py::test_a_description_comes_from_the_frontmatter_then_the_first_heading_then_the_first_line
    FAILED tests/test_skills_sources.py::test_a_bare_skill_file_is_described_by_its_first_heading_or_line

    full output: plans/tickets/.artifacts/KB-001-20261025-175224.log
- 2026-10-26 13:28 - approved by Tim Niles at 71934668a716
- 2026-10-26 13:29 - integrated into main | merge-commit: c0e536357f059b9f6e9574e13badc5b5ce7fbfa8
    $ merge ticket/KB-001 onto main d27aa3ae2d57
    === INTEGRATION: FEATURE TESTS ===
    ..............                                                           [100%]

    full output: plans/tickets/.artifacts/KB-001-20261026-132950.log
- 2026-10-26 13:30 - done gate passed -> 5-done | merge-commit: c0e536357f059b9f6e9574e13badc5b5ce7fbfa8
- 2026-10-26 13:30 - cleanup: removed worktree: KB-001; deleted branch: ticket/KB-001