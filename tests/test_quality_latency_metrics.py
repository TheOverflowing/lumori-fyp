"""Metrics remain honest across failed jobs, partial usage and internal gates."""
import csv
import json

import pytest

from app import job_progress
from app.store import Store, dumps, now
from scripts.quality_latency_metrics import distribution, export_summary, summarize_run
from test_generation_agent import agent_case  # noqa: F401


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path)
    result.execute("INSERT INTO courses VALUES(?,?,?)", ("course", "Course", now()))
    return result


def case(case_id, language="en"):
    return {"id": case_id, "need_id": "paired-need", "course": "Operating systems", "language": language,
            "difficulty": "hard", "question_type": "short_answer", "topic": "Scheduling",
            "expected_evidence": [{"source_id": "frozen-source", "quote": "Shortest job first"}]}


def add_job(store, case_id, status, *, agent_status=None, strict=None, content=True, calls=(), extra=None):
    job, _ = store.job(case_id, "generate", {})
    job_id = job["id"]
    evidence = {"agent": {"status": agent_status or "completed", "slots": []},
                "sources": [], "retrieval": {}}
    if strict is not None:
        evidence["difficulty_acceptance"] = {"strict_passed": strict, "status": "strict" if strict else "adjusted"}
    if extra:
        evidence.update(extra)
    store.save_job_evidence(job_id, evidence)
    result = {}
    if status == "succeeded" and content:
        content_id = "content-" + case_id
        store.execute("INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)", (
            content_id, "course", job_id, 1, "draft", dumps({"questions": [{"stem": "Fixture"}]}), "[]", "{}", now()))
        result["content_id"] = content_id
    store.execute("UPDATE jobs SET status=?,result=? WHERE id=?", (status, dumps(result), job_id))
    for index, call in enumerate(calls):
        store.execute("INSERT INTO calls(id,job_id,capability,model,status,usage,created_at,duration_ms) VALUES(?,?,?,?,?,?,?,?)",
            (job_id + str(index), job_id, call.get("capability", "text"), "fixture-model", call.get("status", "succeeded"),
             dumps(call.get("usage", {})), now(), call.get("duration_ms", 100)))
    return {"case_id": case_id, "job_id": job_id, "wall_seconds": 1.5}


def test_all_submitted_denominator_and_strict_not_delivery(store):
    runs = [add_job(store, "strict", "succeeded", strict=True),
            add_job(store, "adjusted", "succeeded", strict=False),
            add_job(store, "failed", "failed", agent_status="quality_failed"),
            add_job(store, "provider", "failed", agent_status="provider_error"),
            add_job(store, "cancelled", "cancelled")]
    frozen = [case(run["case_id"]) for run in runs] + [case("unsubmitted")]
    summary = summarize_run(store, runs, frozen_cases=frozen)
    assert summary["denominators"]["planned"] == 6
    assert summary["denominators"]["submitted"] == 5
    assert summary["denominators"]["unsubmitted"] == ["unsubmitted"]
    assert summary["delivery"] == {"numerator": 2, "denominator": 5, "rate": .4}
    assert summary["strict_difficulty_per_submitted"]["rate"] == .2
    assert summary["strict_difficulty_per_delivered"]["rate"] == .5
    assert summary["outcomes"]["check_failed"] == 1
    assert summary["outcomes"]["provider_failed"] == 1
    assert summary["external_quality"]["correctness_rate"] is None


def test_partial_provider_usage_keeps_unknown_and_never_double_counts_cost(store):
    run = add_job(store, "metered", "succeeded", strict=True, calls=[
        {"usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15,
                   "cost": .02, "cost_details": {"upstream_inference_cost": .01}}},
        {"capability": "embedding", "usage": {}},
        {"status": "failed", "usage": {}}])
    metrics = summarize_run(store, [run], frozen_cases=[case("metered")])["calls"]
    assert metrics["count"] == 3
    assert metrics["total_tokens"] == {"known_sum": 15, "total": None, "calls_reported": 1,
                                        "calls_missing": 2, "complete": False}
    assert metrics["provider_reported_cost"]["known_sum"] == .02
    assert metrics["provider_reported_cost"]["total"] is None
    assert metrics["statuses"] == {"succeeded": 2, "failed": 1}


def test_unreported_usage_is_unknown_but_no_calls_known_zero(store):
    run = add_job(store, "unknown", "failed", calls=[{}])
    summary = summarize_run(store, [run], frozen_cases=[case("unknown")])
    assert summary["calls"]["total_tokens"]["known_sum"] is None
    empty = summarize_run(store, [], frozen_cases=[case("unknown")])
    assert empty["calls"]["total_tokens"]["total"] == 0
    assert empty["delivery"]["rate"] is None


def test_study_ledger_separates_indexing_and_generation(store):
    setup, _ = store.job("index-setup", "index", {})
    store.execute("INSERT INTO calls(id,job_id,capability,model,status,usage,created_at) VALUES(?,?,?,?,?,?,?)",
        ("index-call", setup["id"], "embedding", "fixture-embedding", "succeeded", dumps({"total_tokens": 50}), now()))
    run = add_job(store, "generate", "succeeded", strict=True, calls=[{"usage": {"total_tokens": 10}}])
    summary = summarize_run(store, [run], frozen_cases=[case("generate")])
    assert summary["calls"]["total_tokens"]["total"] == 10
    assert summary["setup_calls"]["total_tokens"]["total"] == 50
    assert summary["study_calls"]["total_tokens"]["total"] == 60
    assert summary["study_calls"]["count"] == 2


@pytest.mark.parametrize("agent_status,expected", [("running", "runtime_failed"),
    ("protocol_failure", "check_failed"), ("call_limit", "resource_limited"),
    ("quality_failed", "check_failed")])
def test_runtime_errors_are_not_automatically_provider_or_quality_failures(store, agent_status, expected):
    run = add_job(store, "failure", "failed", agent_status=agent_status)
    assert summarize_run(store, [run], frozen_cases=[case("failure")])["cases"][0]["outcome"] == expected


def test_success_requires_persisted_expected_content(store):
    run = add_job(store, "broken-success", "succeeded", strict=True, content=False)
    result = summarize_run(store, [run], frozen_cases=[case("broken-success")])["cases"][0]
    assert not result["delivered"] and result["outcome"] == "runtime_failed"
    assert "succeeded_without_expected_persisted_content" in result["diagnostics"]


def test_quote_presence_uses_identity_and_does_not_claim_semantic_support(store):
    run = add_job(store, "retrieval", "succeeded", strict=True, extra={"sources": [
        {"id": "matching", "metadata": {"benchmark_source_id": "frozen-source"}, "text": "Shortest\n job FIRST minimizes waiting under assumptions."},
        {"id": "wrong", "metadata": {"benchmark_source_id": "other"}, "text": "Unrelated."}]})
    result = summarize_run(store, [run], frozen_cases=[case("retrieval")])["cases"][0]
    check = result["evidence_presence"]["checks"][0]
    assert check["source_present"] and check["quote_present"]
    assert check["matching_chunk_ids"] == ["matching"]
    assert result["citation_support"] is None and result["correctness"] is None
    assert result["evidence_presence"]["semantic_relevance"] is None
    # Identical text from another source must not count as the annotated source.
    other = case("retrieval")
    other["expected_evidence"][0]["source_id"] = "not-retrieved"
    assert not summarize_run(store, [run], frozen_cases=[other])["cases"][0]["evidence_presence"]["checks"][0]["quote_present"]


def test_context_window_can_resolve_expected_document_without_chunk_metadata(store):
    run = add_job(store, "context", "succeeded", strict=True, extra={"sources": [
        {"id": "context-random", "document_id": "doc-corpus", "text": "Shortest job first is one policy."}]})
    frozen = case("context")
    frozen["expected_evidence"][0]["document_id"] = "doc-corpus"
    assert summarize_run(store, [run], frozen_cases=[frozen])["cases"][0]["evidence_presence"]["checks"][0]["quote_present"]


def test_role_durations_rejections_and_unknown_stage_time(store):
    state = {"status": "quality_failed", "slots": [{"slot_id": "q1", "attempts": [{"number": 1,
        "status": "rejected", "feedback": {"issues": ["ambiguous_question"], "validation": {"rule": "source_grounding"}},
        "author": {"history": [{"status": "completed", "started_at": "2026-09-22T01:00:00+00:00", "ended_at": "2026-09-22T01:00:02+00:00"}]},
        "solve": {"history": [{"status": "provider_error", "started_at": "2026-09-22T01:00:03+00:00"}]}}]}]}
    run = add_job(store, "timing", "failed", extra={"agent": state})
    result = summarize_run(store, [run], frozen_cases=[case("timing")])
    assert result["timing"]["role_seconds"]["author"]["median"] == 2
    assert result["timing"]["role_seconds"]["solve"]["n"] == 0
    assert result["cases"][0]["timeline"]["timing_complete"] is False
    assert result["rejection_issue_counts"] == {"ambiguous_question": 1}


def test_live_job_does_not_read_or_accrue_stage_timeline(store, monkeypatch):
    run = add_job(store, "live", "running")
    monkeypatch.setattr(job_progress, "snapshot", lambda *_: pytest.fail("Cannot accrue a live benchmark timer"))
    result = summarize_run(store, [run], frozen_cases=[case("live")])["cases"][0]
    assert result["timeline"] is None and result["outcome"] == "incomplete"


def test_bilingual_variants_group_by_shared_need_and_exports_keep_nulls(store, tmp_path):
    runs = [add_job(store, "english", "succeeded", strict=True),
            add_job(store, "chinese", "failed", agent_status="quality_failed")]
    summary = summarize_run(store, runs, frozen_cases=[case("english"), case("chinese", "zh")])
    assert summary["denominators"]["unique_knowledge_needs_submitted"] == 1
    assert len(summary["paired_knowledge_needs"]) == 1
    assert summary["by_language"]["zh"]["delivery"]["rate"] == 0
    paths = export_summary(summary, tmp_path / "export")
    assert json.loads(open(paths["json"]).read())["external_quality"]["correctness_rate"] is None
    with open(paths["csv"], newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2 and all(row["correctness"] == "" for row in rows)


def test_duplicate_submissions_rejected_instead_of_inflating_denominators(store):
    run = add_job(store, "once", "succeeded", strict=True)
    with pytest.raises(ValueError, match="unique members"):
        summarize_run(store, [run, run], frozen_cases=[case("once")])


def test_small_sample_percentile_and_invalid_values():
    result = distribution([1, 2, 3, None, float("nan"), -1, True])
    assert result["n"] == 3 and result["median"] == 2 and result["p90"] == 3
    assert result["small_sample"] and result["p90_method"] == "nearest_rank"


def test_actual_pipeline_records_are_read_without_model_quality_claims(agent_case):
    rig = agent_case(count=1)
    assert rig.run()["status"] == "succeeded"
    summary = summarize_run(rig.store, [{"case_id": "pipeline", "job_id": rig.job_id, "wall_seconds": 1.0}],
                            frozen_cases=[case("pipeline")])
    result = summary["cases"][0]
    assert result["delivered"] and result["question_count"] == 1
    assert result["calls"]["count"] == 4
    assert set(result["role_timing_seconds"]) == {"author", "solve", "review"}
    assert all(result["role_timing_seconds"][role]["n"] == 1 for role in ("author", "solve", "review"))
    assert result["timeline"]["recorded"] and result["timeline"]["timing_complete"]
    assert result["correctness"] is None
