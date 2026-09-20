"""Tests for paired evidence and incomplete accounting in rewrite ablations."""

import json

import pytest

from scripts.r6_report import interval, metering, paired_rows, report, select_on_dev, summarize, validate_rows


def paired_fixture():
    result = []
    for query, family, gain in (("q1", "a", 1), ("q2", "a", 1), ("q3", "a", 1), ("q4", "b", 0)):
        for arm, value in (("original", 0), ("dual", gain)):
            result.append({"query_id": query, "family_id": family, "arm": arm,
                           "mode": "cross", "language": "en", "budget_hit": value})
    return result


def test_component_bootstrap_retains_scenario_weighted_effect():
    result = interval(paired_fixture(), {"a": "source-a", "b": "source-b"}, "dual", "budget_hit")
    assert result["difference"] == pytest.approx(.75)
    assert result["clusters"] == 2
    assert result["ci95"] == [0, 1]
    assert result["sampling_unit"] == "source_connected_component"
    assert result["samples"] == 2000
    assert result["seed"] == 20260919


def test_duplicated_modes_do_not_invent_independent_sources():
    original = paired_fixture()
    both_modes = original + [dict(row, mode="mixed") for row in original]
    mapping = {"a": "source-a", "b": "source-b"}
    first = interval(original, mapping, "dual", "budget_hit")
    second = interval(both_modes, mapping, "dual", "budget_hit")
    assert second.pop("paired_scenarios") == 2 * first.pop("paired_scenarios")
    assert first == second


def test_connected_families_are_one_sampling_unit():
    result = interval(paired_fixture(), {"a": "shared", "b": "shared"}, "dual", "budget_hit")
    assert result["clusters"] == 1
    assert result["ci95"] == [.75, .75]


@pytest.mark.parametrize("drop_arm", ["original", "dual"])
def test_missing_pair_is_an_error_in_either_direction(drop_arm):
    values = [r for r in paired_fixture() if not (r["query_id"] == "q2" and r["arm"] == drop_arm)]
    with pytest.raises(ValueError, match="Incomplete pairing"):
        interval(values, {"a": "a", "b": "b"}, "dual", "budget_hit")


def test_duplicate_scenario_and_absent_component_are_errors():
    rows = paired_fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        paired_rows(rows + [rows[0]], "dual")
    with pytest.raises(ValueError, match="Missing source component"):
        interval(rows, {"a": "a"}, "dual", "budget_hit")


def test_missing_billing_fields_are_unknown_not_free_calls():
    calls = {
        "paid": {"capability": "rerank", "status": "succeeded", "usage": {"cost": .25}, "duration_ms": 20},
        "zero": {"capability": "rerank", "status": "succeeded", "usage": {"cost": 0}, "duration_ms": 30},
        "missing": {"capability": "rerank", "status": "failed", "usage": {}},
        "null": {"capability": "rerank", "status": "succeeded", "usage": {"cost": None}},
        "unknown": {"capability": "text", "status": "succeeded", "usage": None},
    }
    result = metering(calls)
    assert result["rerank"]["known_cost"] == .25
    assert result["rerank"]["cost_reported_count"] == 2
    assert result["rerank"]["missing_cost_count"] == 2
    assert result["rerank"]["attempts"] == 4
    assert result["rerank"]["failures"] == 1
    assert result["text"]["known_cost"] is None
    assert result["text"]["missing_cost_count"] == 1
    assert result["text"]["p50_ms"] is None
    assert result["text"]["prompt_tokens_known_sum"] is None


def full_fixture():
    rows = []
    for arm in ("canonical", "original", "rewritten", "dual"):
        for query in ("q1", "q2"):
            rows.append({"query_id": query, "family_id": query, "arm": arm, "mode": "cross",
                         "language": "en", "status": "succeeded" if query == "q1" else "failed",
                         "budget_hit": int(query == "q1"), "mrr5": int(query == "q1"),
                         "candidate_hit20": 1, "rewrite_fallback": query == "q2"})
    return rows


def test_failures_stay_in_denominator_and_missing_latency_is_not_zero():
    rows = full_fixture()
    validate_rows(rows, "dev")
    summary = next(row for row in summarize(rows) if row["arm"] == "original" and row["group"] == "all")
    assert summary["rows"] == 2
    assert summary["failed"] == 1
    assert summary["budget_hit"] == .5
    assert summary["candidate_hit20"] == 1
    assert summary["stage_sum_estimate_ms"] is None
    assert summary["stage_sum_estimate_ms_missing"] == 2


def test_dev_selection_excludes_canonical_and_retains_original_on_tie():
    rows = full_fixture()
    for row in rows:
        if row["arm"] == "canonical":
            row["budget_hit"] = row["mrr5"] = 1
    assert select_on_dev(rows) == "original"
    for row in rows:
        if row["arm"] == "rewritten" and row["query_id"] == "q2":
            row["budget_hit"] = 1
    assert select_on_dev(rows) == "rewritten"


def test_full_report_preserves_selection_and_emits_auditable_artifacts(tmp_path):
    queries = []
    components = {}
    for split in ("dev", "test"):
        values = []
        components[split] = {}
        for base in full_fixture():
            query_id = split + base["query_id"]
            for mode in ("mixed", "cross"):
                values.append(dict(base, query_id=query_id, family_id=query_id, mode=mode, split=split))
            components[split][query_id] = query_id
        for query_id in sorted(components[split]):
            queries.append({"id": query_id, "family_id": query_id, "language": "en", "split": split,
                            "text": "What is indexing?", "colloquial_text": "What's that indexing thing?"})
        (tmp_path / f"{split}-per-query.json").write_text(json.dumps(values))
    inputs = {"dataset.json": {"documents": [], "queries": queries}, "components.json": components,
              "rewrites.json": {}, "calls.json": {},
              "selection-lock.json": {"basis": "dev_only", "selected_arm": "original"}}
    for name, value in inputs.items():
        (tmp_path / name).write_text(json.dumps(value))
    lock_bytes = (tmp_path / "selection-lock.json").read_bytes()
    decision = report(tmp_path)
    assert decision["dev_selected"] == "original"
    assert decision["test_intervals"]["dual_minus_original"]["all"]["budget_hit"]["difference"] == 0
    assert (tmp_path / "selection-lock.json").read_bytes() == lock_bytes
    for name in ("report.md", "decision.json", "test-changes.csv", "test-failure-attribution.json",
                 "dev-metrics.csv", "test-metrics.csv"):
        assert (tmp_path / name).exists()
    incomplete = json.loads((tmp_path / "test-per-query.json").read_text())
    incomplete = [row for row in incomplete if row["mode"] != "mixed"]
    (tmp_path / "test-per-query.json").write_text(json.dumps(incomplete))
    with pytest.raises(ValueError, match="both mixed and cross"):
        report(tmp_path)
