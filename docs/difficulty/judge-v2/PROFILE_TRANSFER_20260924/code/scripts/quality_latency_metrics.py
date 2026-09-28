"""Read-only Q1 baseline diagnostics over actual Pipeline records.

An internal gate passing is not external evidence of answer correctness. Missing
provider metering stays unknown. Frozen quote presence is a diagnostic, not a
semantic relevance, citation-entailment, or educational-outcome measurement.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app import job_progress
from app.providers import safe_usage


SCHEMA_VERSION = "quality-latency-baseline-v1"
TERMINAL = {"succeeded", "failed", "cancelled", "insufficient_evidence"}
OUTCOMES = ("strict", "adjusted", "delivered_acceptance_unknown", "check_failed",
            "provider_failed", "cancelled", "insufficient_evidence",
            "resource_limited", "runtime_failed", "incomplete")


def _object(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _duration(start, end):
    try:
        return _number((datetime.fromisoformat(end.replace("Z", "+00:00")) -
                        datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds())
    except (TypeError, ValueError, AttributeError):
        return None


def distribution(values):
    """Descriptive median and nearest-rank p90; no inferential speedup claim."""
    values = sorted(value for raw in values if (value := _number(raw)) is not None)
    return {"n": len(values), "median": statistics.median(values) if values else None,
            "p90": values[math.ceil(.9 * len(values)) - 1] if values else None,
            "min": values[0] if values else None, "max": values[-1] if values else None,
            "p90_method": "nearest_rank", "small_sample": len(values) < 30}


def _rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def _meter(calls, names):
    values = []
    for call in calls:
        usage = _object(call.get("usage"))
        value = next((usage[name] for name in names if _number(usage.get(name)) is not None), None)
        if value is not None:
            values.append(value)
    # Zero calls is known zero; zero records of metering across calls is unknown.
    complete = len(values) == len(calls)
    known = sum(values) if values or not calls else None
    return {"known_sum": known, "total": known if complete else None,
            "calls_reported": len(values), "calls_missing": len(calls) - len(values),
            "complete": complete}


def _call_summary(calls):
    grouped = defaultdict(list)
    for call in calls:
        grouped[(call.get("capability"), call.get("model"), call.get("status"))].append(call)
    return {"count": len(calls),
            "statuses": dict(Counter(c.get("status", "unknown") for c in calls)),
            "duration_seconds": distribution(
                None if _number(c.get("duration_ms")) is None else c["duration_ms"] / 1000 for c in calls),
            "input_tokens": _meter(calls, ("prompt_tokens", "input_tokens")),
            "output_tokens": _meter(calls, ("completion_tokens", "output_tokens")),
            "total_tokens": _meter(calls, ("total_tokens",)),
            "provider_reported_cost": _meter(calls, ("cost",)),
            "cost_currency": "unspecified_by_stored_usage",
            "cost_note": "Provider-reported cost only; no estimated price or nested upstream-cost double count.",
            "by_capability_model_status": [
                {"capability": cap, "model": model, "status": status, "count": len(rows),
                 "duration_seconds": distribution(None if _number(c.get("duration_ms")) is None
                    else c["duration_ms"] / 1000 for c in rows),
                 "total_tokens": _meter(rows, ("total_tokens",)),
                 "provider_reported_cost": _meter(rows, ("cost",))}
                for (cap, model, status), rows in sorted(grouped.items(), key=lambda item: str(item[0]))]}


def _role_histories(state):
    """Only traverse host-owned role records, never arbitrary model responses."""
    containers = [("supervisor", batch) for batch in state.get("supervisor", {}).get("batches", [])]
    containers += [(slot.get("slot_id"), attempt)
                   for slot in state.get("slots", []) for attempt in slot.get("attempts", [])]
    invocations = []
    for slot_id, container in containers:
        for phase, record in container.items():
            if not isinstance(record, dict) or not isinstance(record.get("history"), list):
                continue
            for entry in record["history"]:
                invocations.append({"slot_id": slot_id, "attempt": container.get("number"),
                    "role": phase, "status": entry.get("status"),
                    "started_at": entry.get("started_at"), "ended_at": entry.get("ended_at"),
                    "duration_seconds": _duration(entry.get("started_at"), entry.get("ended_at"))})
    return invocations


def _rejections(state):
    results = []
    for slot in state.get("slots", []):
        for attempt in slot.get("attempts", []):
            feedback = _object(attempt.get("feedback"))
            if attempt.get("status") != "rejected" and not feedback.get("issues"):
                continue
            issues = feedback.get("issues", [])
            results.append({"slot_id": slot.get("slot_id"), "attempt": attempt.get("number"),
                "status": attempt.get("status"),
                "issues": [item for item in issues if isinstance(item, str)],
                "validation_rule": _object(feedback.get("validation")).get("rule"),
                "format_compatibility": attempt.get("format_compatibility")})
    return results


def _normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text))).strip().casefold()


def _source_ids(source, store):
    metadata = _object(source.get("metadata"))
    identities = {str(v) for v in (source.get("id"), source.get("document_id"),
        source.get("benchmark_source_id"), metadata.get("benchmark_source_id")) if v}
    document_id = source.get("document_id")
    if document_id:
        # Both are existing metadata stores; this reader never alters the corpus.
        for table, column in (("external_document_sources", "metadata"), ("document_options", "options")):
            row = store.one(f"SELECT {column} FROM {table} WHERE document_id=?", (document_id,))
            value = _object(row[column]).get("benchmark_source_id") if row else None
            if value:
                identities.add(str(value))
    return identities


def _evidence_presence(store, case, evidence):
    sources = evidence.get("sources", [])
    expected = case.get("expected_evidence", [])
    checks = []
    indexed = [(source, _source_ids(source, store)) for source in sources]
    for item in expected:
        source_id = item.get("source_id") or item.get("document_id")
        expected_ids = {str(value) for value in (item.get("source_id"), item.get("document_id")) if value}
        matching = [source for source, ids in indexed if expected_ids & ids]
        quote = _normalized(item.get("quote", ""))
        quote_found = any(quote in _normalized(source.get("text", "")) for source in matching) if quote else None
        checks.append({"source_id": source_id, "source_present": bool(matching),
            "quote_specified": bool(quote), "quote_present": quote_found,
            "matching_chunk_ids": [source.get("id") for source in matching]})
    quote_checks = [check for check in checks if check["quote_specified"]]
    recorded = isinstance(evidence.get("retrieval"), dict)
    return {"retrieval_recorded": recorded, "retrieved_context_count": len(sources),
            "expected_count": len(checks), "checks": checks,
            "source_presence": _rate(sum(c["source_present"] for c in checks), len(checks)) if recorded else None,
            "quote_presence": _rate(sum(c["quote_present"] for c in quote_checks), len(quote_checks)) if recorded else None,
            "all_expected_quotes_present": all(c["quote_present"] for c in quote_checks)
                if quote_checks and recorded else None,
            "semantic_relevance": None, "citation_support": None,
            "note": "Frozen normalized quote containment in the identified source; not semantic Recall@k."}


def _acceptance(evidence, content):
    acceptance = _object(evidence.get("difficulty_acceptance"))
    if not acceptance and content:
        acceptance = _object(_object(content.get("config")).get("difficulty_acceptance"))
    if type(acceptance.get("strict_passed")) is bool:
        return acceptance
    slots = evidence.get("agent", {}).get("slots", [])
    decisions = [s.get("difficulty_acceptance", {}) for s in slots if s.get("status") == "passed"]
    if decisions and len(decisions) == len(slots) and all(type(d.get("strict_passed")) is bool for d in decisions):
        return {"strict_passed": all(d["strict_passed"] for d in decisions), "items": decisions}
    return {}


def _outcome(status, delivered, acceptance, state, calls):
    if delivered:
        if type(acceptance.get("strict_passed")) is bool:
            return "strict" if acceptance["strict_passed"] else "adjusted"
        return "delivered_acceptance_unknown"
    if status == "cancelled":
        return "cancelled"
    if status == "insufficient_evidence":
        return "insufficient_evidence"
    if status in ("queued", "running"):
        return "incomplete"
    agent_status = state.get("status")
    if agent_status in ("quality_failed", "protocol_failure"):
        return "check_failed"
    if agent_status in ("call_limit", "context_limit"):
        return "resource_limited"
    if agent_status == "provider_error" or (not agent_status and calls and calls[-1].get("status") == "failed"):
        return "provider_failed"
    return "runtime_failed"


def _group_summary(cases):
    n = len(cases)
    delivered = sum(c["delivered"] for c in cases)
    strict = sum(c["outcome"] == "strict" for c in cases)
    return {"submitted": n, "outcomes": {key: sum(c["outcome"] == key for c in cases) for key in OUTCOMES},
            "delivery": _rate(delivered, n), "strict_difficulty_per_submitted": _rate(strict, n),
            "strict_difficulty_per_delivered": _rate(strict, delivered),
            "wall_seconds_all": distribution(c["wall_seconds"] for c in cases),
            "wall_seconds_delivered": distribution(c["wall_seconds"] for c in cases if c["delivered"])}


def summarize_run(store, case_runs: list[dict], *, frozen_cases: list[dict]) -> dict:
    """Summarize submitted jobs; unsubmitted planned cases stay explicit.

    Inputs: case_runs {case_id, job_id, wall_seconds, started_at, ended_at}; frozen
    cases {id, need_id, course, language, difficulty, question_type, topic,
    expected_evidence:[{source_id, quote}]}. SQLite is the status authority.
    """
    frozen = {case.get("id", case.get("case_id")): case for case in frozen_cases}
    if None in frozen or len(frozen) != len(frozen_cases):
        raise ValueError("Frozen case IDs must be present and unique.")
    seen_cases, seen_jobs = set(), set()
    rows, all_calls = [], []
    for run in case_runs:
        case_id, job_id = run.get("case_id"), run.get("job_id")
        if case_id not in frozen or case_id in seen_cases:
            raise ValueError("Run case IDs must be unique members of the frozen suite.")
        seen_cases.add(case_id)
        if not job_id:
            continue
        if job_id in seen_jobs:
            raise ValueError("A submitted job cannot be counted more than once.")
        seen_jobs.add(job_id)
        case = frozen[case_id]
        job = store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        status = job["status"] if job else "missing_job"
        saved = store.one("SELECT evidence FROM job_evidence WHERE job_id=?", (job_id,))
        evidence = _object(saved["evidence"]) if saved else {}
        state = _object(evidence.get("agent"))
        calls = store.calls_for_job(job_id)
        all_calls.extend(calls)
        result = _object(job.get("result")) if job else {}
        content = store.one("SELECT id,asset,config FROM contents WHERE id=? AND job_id=?",
                            (result.get("content_id"), job_id)) if result.get("content_id") else None
        questions = _object(content["asset"]).get("questions", []) if content else []
        expected_count = case.get("count", 1)
        delivered = status == "succeeded" and bool(content) and len(questions) == expected_count
        acceptance = _acceptance(evidence, content)
        role_calls = _role_histories(state)
        role_groups = defaultdict(list)
        for call in role_calls:
            role_groups[call["role"]].append(call)
        timeline = job_progress.snapshot(store, job) if job and status in TERMINAL else None
        wall = _number(run.get("wall_seconds"))
        rows.append({"case_id": case_id, "job_id": job_id,
            **{key: case.get(key) for key in ("need_id", "course", "language", "difficulty", "question_type", "topic")},
            "status": status, "agent_status": state.get("status"),
            "outcome": _outcome(status, delivered, acceptance, state, calls),
            "delivered": delivered, "content_id": content["id"] if content else None,
            "question_count": len(questions), "expected_question_count": expected_count,
            "strict_difficulty": acceptance.get("strict_passed") if delivered else None,
            "difficulty_acceptance": acceptance or None,
            "correctness": None, "citation_support": None, "external_audit_status": "not_reviewed",
            "wall_seconds": wall, "started_at": run.get("started_at", run.get("start")),
            "ended_at": run.get("ended_at", run.get("end")),
            "timeline": timeline, "retrieval_timing_ms": _object(evidence.get("retrieval")).get("timing_ms"),
            "calls": _call_summary(calls), "role_invocations": role_calls,
            "role_timing_seconds": {role: distribution(c["duration_seconds"] for c in entries)
                                    for role, entries in sorted(role_groups.items())},
            "rejections": _rejections(state), "evidence_presence": _evidence_presence(store, case, evidence),
            "diagnostics": (["missing_persisted_job"] if not job else []) +
                (["succeeded_without_expected_persisted_content"] if status == "succeeded" and not delivered else [])})
    groups = defaultdict(list)
    pairs = defaultdict(list)
    stages, roles = defaultdict(list), defaultdict(list)
    for row in rows:
        groups[row["language"] or "unknown"].append(row)
        pairs[row["need_id"] or row["case_id"]].append(row)
        for stage in (row["timeline"] or {}).get("stages", []):
            stages[stage["kind"]].append({"case_id": row["case_id"], "timing_complete": stage["timing_complete"],
                "seconds": stage["elapsed_ms"] / 1000 if _number(stage.get("elapsed_ms")) is not None else None})
        for call in row["role_invocations"]:
            roles[call["role"]].append(call["duration_seconds"])
    summary = _group_summary(rows)
    study_calls = store.all("SELECT job_id,capability,model,status,usage,duration_ms FROM calls ORDER BY created_at")
    for call in study_calls:
        call["usage"] = safe_usage(_object(call["usage"]))
    setup_calls = [call for call in study_calls if call["job_id"] not in seen_jobs]
    recorded = [row for row in rows if row["evidence_presence"]["retrieval_recorded"]]
    quotable = [row for row in recorded if row["evidence_presence"]["all_expected_quotes_present"] is not None]
    return {"schema_version": SCHEMA_VERSION,
        "evidence_scope": "Descriptive single-run pilot; bilingual variants share knowledge needs. Internal model gates, quote presence, and external correctness are separate.",
        "denominators": {"planned": len(frozen), "submitted": len(rows),
            "unsubmitted": sorted(set(frozen) - {r["case_id"] for r in rows}),
            "unique_knowledge_needs_submitted": len(pairs), "retrieval_recorded": len(recorded)},
        **summary,
        "timing": {"wall_seconds_all": summary["wall_seconds_all"],
            "wall_seconds_delivered": summary["wall_seconds_delivered"],
            "stages_seconds": {kind: {"complete": distribution(s["seconds"] for s in items if s["timing_complete"]),
                "incomplete_checkpoint_count": sum(not s["timing_complete"] for s in items)}
                for kind, items in sorted(stages.items())},
            "role_seconds": {role: distribution(values) for role, values in sorted(roles.items())},
            "note": "Wall uses runner monotonic time. Stages use recorded active time; roles use wall timestamps. They are not interchangeable or necessarily additive."},
        "calls": _call_summary(all_calls),
        "study_calls": _call_summary(study_calls),
        "setup_calls": _call_summary(setup_calls),
        "ledger_scope": "Study totals read the entire isolated study Store; setup includes every call outside submitted generation jobs.",
        "rejection_issue_counts": dict(Counter(issue for row in rows for rejection in row["rejections"] for issue in rejection["issues"])),
        "retrieval": {"all_expected_quotes_present": _rate(sum(row["evidence_presence"]["all_expected_quotes_present"] for row in quotable), len(quotable)),
            "semantic_relevance": None, "note": "Conditional on recorded retrieval and a frozen quote; excludes unexecuted retrieval, not a semantic recall metric."},
        "external_quality": {"reviewed": 0, "correctness_rate": None, "citation_support_rate": None},
        "by_language": {key: _group_summary(value) for key, value in sorted(groups.items())},
        "paired_knowledge_needs": [{"need_id": need, "case_ids": [r["case_id"] for r in entries],
            "languages": [r["language"] for r in entries], "all_delivered": all(r["delivered"] for r in entries),
            "note": "Descriptive paired variants; not independent topics or a causal language comparison."}
            for need, entries in sorted(pairs.items())],
        "cases": rows}


def export_summary(summary: dict, output_dir) -> dict:
    """Write nested JSON and one flat CSV row per submitted case."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path, csv_path = output_dir / "metrics_summary.json", output_dir / "case_metrics.csv"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    cases_dir = output_dir / "case_metrics"
    cases_dir.mkdir(exist_ok=True)
    case_paths = []
    for index, case in enumerate(summary["cases"], start=1):
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", case["case_id"])[:100]
        path = cases_dir / f"{index:02d}-{slug}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        case_paths.append(str(path))
    columns = ("case_id", "job_id", "need_id", "course", "language", "difficulty", "question_type", "status", "outcome",
               "delivered", "strict_difficulty", "wall_seconds", "calls", "tokens_reported_sum", "tokens_total",
               "tokens_missing_calls", "cost_reported_sum", "cost_total", "cost_missing_calls",
               "external_audit_status", "correctness", "citation_support")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for case in summary["cases"]:
            row = {key: case.get(key) for key in columns}
            tokens, cost = case["calls"]["total_tokens"], case["calls"]["provider_reported_cost"]
            row.update(calls=case["calls"]["count"], tokens_reported_sum=tokens["known_sum"], tokens_total=tokens["total"],
                tokens_missing_calls=tokens["calls_missing"], cost_reported_sum=cost["known_sum"],
                cost_total=cost["total"], cost_missing_calls=cost["calls_missing"])
            writer.writerow(row)
    return {"json": str(summary_path), "csv": str(csv_path), "cases": case_paths}
