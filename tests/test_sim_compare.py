"""The simulation's comparison logic: what counts as broken, worse and better."""

from __future__ import annotations

import copy

from sim.compare import compare, normalize

CARD = {
    "engine": "1.4.0",
    "scenarios": {
        "S1": {
            "title": "t",
            "ok": True,
            "invariants": {"I1": {"pass": True}, "I4": {"pass": True}},
            "expectations": {"done": {"pass": True}},
            "metrics": {
                "first_pass_yield": 1.0,
                "steps_to_done": 4,
                "worker_prompt_bytes": 1000,
                "wall_seconds": 5.0,
                "guard_refusals": 0,
            },
        }
    },
}


def changed(**metrics: object) -> dict:
    new = copy.deepcopy(CARD)
    new["scenarios"]["S1"]["metrics"].update(metrics)
    return new


def test_an_identical_scorecard_is_clean_and_wall_time_is_ignored() -> None:
    result = compare(normalize(CARD), normalize(changed(wall_seconds=50.0)))

    assert result.clean and not result.better


def test_a_broken_invariant_or_expectation_blocks() -> None:
    new = copy.deepcopy(CARD)
    new["scenarios"]["S1"]["ok"] = False
    new["scenarios"]["S1"]["invariants"]["I4"]["pass"] = False
    new["scenarios"]["S1"]["expectations"]["done"]["pass"] = False

    result = compare(normalize(CARD), normalize(new))

    assert not result.clean
    assert any("I4" in line for line in result.broken)
    assert any("expectation 'done'" in line for line in result.broken)


def test_a_scenario_that_stopped_running_is_broken() -> None:
    assert compare(normalize(CARD), {"scenarios": {}}).broken == ["S1: no longer run"]


def test_metrics_split_into_worse_and_better_by_direction() -> None:
    result = compare(normalize(CARD), normalize(changed(first_pass_yield=0.5, steps_to_done=3)))

    assert result.worse == ["S1 first_pass_yield: 1.0 -> 0.5"]
    assert result.better == ["S1 steps_to_done: 4 -> 3"]


def test_prompt_size_has_a_three_percent_tolerance() -> None:
    assert compare(normalize(CARD), normalize(changed(worker_prompt_bytes=1020))).clean
    assert compare(normalize(CARD), normalize(changed(worker_prompt_bytes=1100))).worse


def test_an_exact_metric_blocks_in_either_direction() -> None:
    assert compare(normalize(CARD), normalize(changed(guard_refusals=1))).worse


def test_a_baseline_normalizes_to_itself() -> None:
    once = normalize(CARD)

    assert normalize(once) == once


def test_a_rule_that_failed_before_and_holds_now_is_better() -> None:
    old = copy.deepcopy(CARD)
    old["scenarios"]["S1"]["invariants"]["I4"]["pass"] = False

    result = compare(normalize(old), normalize(CARD))

    assert result.clean
    assert result.better == ["S1 I4: failed before, passes now"]


def test_stability_report_names_only_the_metrics_that_moved() -> None:
    from sim.compare import stability_report

    runs = [changed(), changed(steps_to_done=5, wall_seconds=9.0), changed()]

    assert stability_report(runs) == ["S1 steps_to_done"]
    assert stability_report([CARD, copy.deepcopy(CARD)]) == []


def test_unstable_metrics_in_the_baseline_are_not_gated() -> None:
    base = normalize(CARD)
    base["unstable"] = ["S1 steps_to_done"]

    result = compare(base, normalize(changed(steps_to_done=9, first_pass_yield=0.5)))

    assert result.worse == ["S1 first_pass_yield: 1.0 -> 0.5"]
    assert normalize(base)["unstable"] == ["S1 steps_to_done"]


def test_stability_report_covers_the_union() -> None:
    from sim.compare import stability_report

    first = copy.deepcopy(CARD)
    del first["scenarios"]["S1"]["metrics"]["steps_to_done"]  # cards[0] is missing a metric the others have
    second = changed(steps_to_done=9)

    assert stability_report([first, second]) == ["S1 steps_to_done"]


def test_stability_report_handles_a_missing_scenario() -> None:
    from sim.compare import stability_report

    first = copy.deepcopy(CARD)
    second = copy.deepcopy(CARD)
    del second["scenarios"]["S1"]  # a run where the scenario didn't happen at all

    result = stability_report([first, second])

    assert result  # reported as moved, not a KeyError
    assert all(line.startswith("S1 ") for line in result)


def test_stability_accept_without_baseline(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    import pytest

    from sim import __main__ as sim_main

    baseline = tmp_path / "scorecard.json"  # does not exist
    monkeypatch.setattr(sim_main, "BASELINE", baseline)

    with pytest.raises(SystemExit) as exc:
        sim_main.main(["stability", "S1", "--runs", "1", "--accept"])

    assert exc.value.code != 0
    assert "run `compare --accept` first" in str(exc.value.code)


def test_the_stability_command_records_what_moved(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    import json

    from sim import __main__ as sim_main

    baseline = tmp_path / "scorecard.json"
    baseline.write_text(json.dumps({"engine": "x", "scenarios": {}}), encoding="utf-8")
    monkeypatch.setattr(sim_main, "BASELINE", baseline)

    assert sim_main.main(["stability", "S1", "--runs", "2", "--accept"]) == 0

    assert "moved over 2 runs" in capsys.readouterr().out
    assert isinstance(json.loads(baseline.read_text(encoding="utf-8"))["unstable"], list)
