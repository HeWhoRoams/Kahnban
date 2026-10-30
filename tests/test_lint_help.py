"""lint --help must name the real first/last rule ids, not a stale hardcoded range."""

from __future__ import annotations

import re

from kahnban import cli, linter


def _lint_help() -> str:
    # argparse prints a subparser's ``help=`` text in the *parent's* listing,
    # not in the subcommand's own ``--help`` output.
    return cli.build_parser().format_help()


def test_help_range_from_table() -> None:
    rule_ids = sorted(linter.RULES)
    first, last = rule_ids[0], rule_ids[-1]
    help_text = _lint_help()
    match = re.search(r"\bBL\d+-BL\d+\b", help_text)
    assert match, f"no rule range found in help text: {help_text!r}"
    assert match.group(0) == f"{first}-{last}", (
        f"help names {match.group(0)!r} but the rule table spans {first}-{last}"
    )
