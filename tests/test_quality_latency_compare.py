import hashlib
import json

import pytest

from scripts.quality_latency_compare import compare, export, load_run, rate_known


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def run_fixture(tmp_path, name, *, review_ids=("n_en",), delivery=(True, False), status="completed"):
    run = tmp_path / name
    frozen = [{"id": f"n_{lang}", "need_id": "n", "course": "networks", "language": lang,
               "difficulty": "hard"} for lang in ("en", "zh")]
    write(run / "frozen_cases.json", frozen)
    write(run / "manifest.json", {"status": status, "dataset_sha256": "same", "case_order": [c["id"] for c in frozen],
        "planned_cases": 2, "call_cap": 192, "per_job_cap": 12, "max_seconds": 3600, "seed": 20260922,
        "configuration": {"text_model": "fixed", "concurrency": 1},
        "code_sha256": {"app/generation_agent.py": name, "scripts/quality_latency_baseline.py": "same"}})
    rows, records = [], []
    for case, delivered in zip(frozen, delivery):
        cid = case["id"]
        artifact = run / "cases" / f"{cid}.json"
        write(artifact, {"job": {"error": "此任务至少需要约 4 次 API 调用，超过当前可用上限；请减少题数或调整额度后继续。"}})
        rows.append({"case_id": cid, "job_id": cid, "status": "succeeded" if delivered else "failed",
                     "delivered": delivered, "outcome": "adjusted" if delivered else "provider_failed",
                     "calls": {"count": 5 if delivered else 0}, "wall_seconds": 10 if delivered else 0.01,
                     "evidence_presence": {"retrieval_recorded": delivered}})
        if cid in review_ids:
            records.append({"case_id": cid, "job_id": cid, "delivered": delivered,
                "target_difficulty": "hard", "candidate_scope": "published" if delivered else "unpublished_latest_parseable_author",
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "core_quality_pass": True, "difficulty_match": False, "review": {"assessed_difficulty": "easy"}})
    write(run / "metrics_summary.json", {"cases": rows, "denominators": {"planned": 2, "submitted": 2},
        "study_calls": {"count": 17, "provider_reported_cost": {"total": None, "known_sum": 0.1, "complete": False}},
        "setup_calls": {"count": 12}, "rejection_issue_counts": {}})
    if review_ids is not None:
        write(run / "ai-review" / "summary.json", {"records": records, "validation": {
            "sealed_files_verified": True, "pass1_answers_and_difficulty_unchanged": True,
            "original_case_hashes_verified": True, "quoted_spans_and_citation_membership_verified": True}})
    return run


def test_partial_ai_review_does_not_fill_missing_with_zero(tmp_path):
    a = run_fixture(tmp_path, "a")
    b = run_fixture(tmp_path, "b", review_ids=("n_en",), delivery=(True, True))
    result = compare(a, b)
    metric = result["candidate"]["delivered_core_per_planned"]
    assert metric == {"numerator": None, "denominator": 2, "rate": None, "known_pass": 1, "unknown": 1,
                      "lower_bound": 0.5, "upper_bound": 1.0,
                      "bounds_note": "Missing-outcome bounds, not a statistical confidence interval."}
    assert result["rate_deltas_candidate_minus_baseline"]["delivered_core_per_planned"] is None
    assert result["paired_cases"][1]["delivered_and_core_pass_transition"] == "unknown"
    assert result["candidate"]["study_calls"]["provider_reported_cost"]["total"] is None


def test_failed_candidate_quality_does_not_count_as_delivery(tmp_path):
    a = run_fixture(tmp_path, "a", review_ids=("n_en", "n_zh"))
    result = compare(a, a)
    base = result["baseline"]
    assert base["reviewed_candidates"] == 2
    assert base["delivered_core_per_submitted"]["numerator"] == 1
    assert base["delivered_core_per_submitted"]["denominator"] == 2
    assert base["runtime_outcomes"] == {"adjusted": 1, "provider_failed": 1}
    assert base["diagnostic_outcomes"] == {"adjusted": 1, "resource_limited": 1}
    assert base["zero_call_submitted"] == 1
    assert base["target_match_per_strict_delivered"]["denominator"] == 0
    assert base["target_match_per_adjusted_delivered"]["numerator"] == 0
    assert len(result["paired_knowledge_needs"]) == 1


def test_absent_ai_review_is_unknown(tmp_path):
    a = run_fixture(tmp_path, "a")
    (a / "ai-review" / "summary.json").unlink()
    result = compare(a, a)
    assert result["baseline"]["core_quality_per_delivered"]["rate"] is None
    assert result["baseline"]["delivered_core_per_planned"]["unknown"] == 1
    assert result["baseline"]["delivery_per_planned"]["rate"] == 0.5


def test_control_changes_withhold_aggregate_deltas(tmp_path):
    a, b = run_fixture(tmp_path, "a"), run_fixture(tmp_path, "b")
    path = b / "manifest.json"; manifest = json.loads(path.read_text())
    manifest["configuration"]["text_model"] = "changed"
    write(path, manifest)
    result = compare(a, b)
    assert result["comparability"]["control_differences"] == ["configuration"]
    assert all(value is None for value in result["rate_deltas_candidate_minus_baseline"].values())


def test_stale_review_artifact_fails_closed(tmp_path):
    a = run_fixture(tmp_path, "a")
    write(a / "cases" / "n_en.json", {"changed": True})
    with pytest.raises(ValueError, match="artifact changed"):
        load_run(a)


def test_no_writes_into_input_archives(tmp_path):
    a = run_fixture(tmp_path, "a")
    result = compare(a, a)
    with pytest.raises(ValueError, match="outside both"):
        export(result, a / "comparison")
    assert export(result, tmp_path / "comparison").exists()


def test_unsubmitted_and_inflight_stay_in_planned_denominator(tmp_path):
    a = run_fixture(tmp_path, "a", review_ids=(), status="running")
    path = a / "metrics_summary.json"; metrics = json.loads(path.read_text())
    metrics["cases"] = metrics["cases"][:1]
    metrics["cases"][0].update(status="running", delivered=False, outcome="incomplete")
    metrics["denominators"]["submitted"] = 1
    write(path, metrics)
    result = compare(a, a)["baseline"]
    assert result["planned"] == 2 and result["submitted"] == 1
    assert result["delivery_per_planned"]["rate"] is None
    assert result["delivered_core_per_planned"]["unknown"] == 2
    assert result["unsubmitted_case_ids"] == ["n_zh"]


def test_rate_bounds_do_not_turn_uncertainty_into_failure():
    assert rate_known([])["rate"] is None
    assert rate_known([False, None])["rate"] is None
    assert rate_known([False, None])["upper_bound"] == 0.5
    assert rate_known([True, False])["rate"] == 0.5
