"""Read-only paired DEV comparison; missing AI reviews are unknown, never zero.

Consumes frozen run artifacts, not live application databases. AI review integrity
must first be checked by quality_latency_review_summary.py. This comparison is
descriptive and does not establish causal gains or independent human correctness.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics


TERMINAL = {"succeeded", "failed", "cancelled", "insufficient_evidence"}
REVIEW_VALIDATION = ("sealed_files_verified", "pass1_answers_and_difficulty_unchanged",
                     "original_case_hashes_verified", "quoted_spans_and_citation_membership_verified")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return result


def rate_known(values):
    """An all-case rate is withheld while any case has an unknown outcome."""
    n, unknown = sum(v is True for v in values), sum(v is None for v in values)
    d = len(values)
    return {"numerator": n if not unknown else None, "denominator": d,
            "rate": n / d if d and not unknown else None,
            "known_pass": n, "unknown": unknown,
            "lower_bound": n / d if d else None,
            "upper_bound": (n + unknown) / d if d else None,
            "bounds_note": "Missing-outcome bounds, not a statistical confidence interval."}


def median(values):
    numbers = [v for v in values if v is not None]
    return {"n": len(numbers), "median": statistics.median(numbers) if numbers else None}


def load_run(directory):
    run = Path(directory)
    manifest, metrics = read(run / "manifest.json"), read(run / "metrics_summary.json")
    frozen = unique(read(run / "frozen_cases.json"), "id")
    runtime = unique(metrics["cases"], "case_id")
    if set(runtime) - set(frozen) or len(runtime) != metrics["denominators"]["submitted"]:
        raise ValueError("Runtime cases do not match the frozen suite or submitted count")
    if len(frozen) != metrics["denominators"]["planned"]:
        raise ValueError("Planned denominator does not match the frozen suite")
    review_path = run / "ai-review" / "summary.json"
    review_summary = read(review_path) if review_path.exists() else None
    reviews = unique(review_summary["records"], "case_id") if review_summary else {}
    if review_summary and not all(review_summary.get("validation", {}).get(k) is True for k in REVIEW_VALIDATION):
        raise ValueError("AI review summary lacks validated sealed evidence")
    if set(reviews) - set(runtime):
        raise ValueError("AI review contains an unsubmitted or unknown case")
    finalized = manifest["status"] in {"completed", "stopped"}
    rows = []
    for cid, case in frozen.items():
        observed, review = runtime.get(cid), reviews.get(cid)
        terminal = bool(observed and observed["status"] in TERMINAL)
        delivered = observed["delivered"] if terminal else (False if finalized and not observed else None)
        if review:
            if review["delivered"] is not delivered or review["target_difficulty"] != case["difficulty"]:
                raise ValueError(f"AI review status/target mismatch: {cid}")
            if review.get("job_id") != observed["job_id"]:
                raise ValueError(f"AI review job mismatch: {cid}")
            if sha(run / "cases" / f"{cid}.json") != review["artifact_sha256"]:
                raise ValueError(f"AI reviewed artifact changed: {cid}")
            if type(review.get("core_quality_pass")) is not bool or type(review.get("difficulty_match")) is not bool:
                raise ValueError(f"Invalid AI review result: {cid}")
            if delivered and review.get("candidate_scope") != "published":
                raise ValueError(f"Delivered case was not reviewed as published: {cid}")
        raw_outcome = observed["outcome"] if observed else "unsubmitted"
        diagnostic_outcome, diagnostic = raw_outcome, None
        # A documented Q1 legacy classification error. Preserve the original
        # outcome; do not infer provider failure from a local zero-call preflight.
        if observed and raw_outcome == "provider_failed" and observed["calls"]["count"] == 0:
            artifact_path = run / "cases" / f"{cid}.json"
            artifact = read(artifact_path) if artifact_path.exists() else {}
            error = str(artifact.get("job", {}).get("error", ""))
            if all(s in error for s in ("至少需要约", "API 调用", "超过当前可用上限")):
                diagnostic_outcome = "resource_limited"
                diagnostic = "Explicit local call-budget preflight error with zero upstream calls."
        core = review["core_quality_pass"] if review else None
        difficulty = review["difficulty_match"] if review else None
        rows.append({"case_id": cid, "need_id": case["need_id"], "language": case["language"],
            "course": case["course"], "target_difficulty": case["difficulty"],
            "submitted": observed is not None, "status": observed["status"] if observed else "unsubmitted",
            "delivered": delivered, "runtime_outcome": raw_outcome,
            "diagnostic_outcome": diagnostic_outcome, "diagnostic_note": diagnostic,
            "retrieval_recorded": bool(observed and observed["evidence_presence"]["retrieval_recorded"]),
            "calls": observed["calls"]["count"] if observed else 0,
            "wall_seconds": observed.get("wall_seconds") if observed else None,
            "reviewed": review is not None, "candidate_scope": review.get("candidate_scope") if review else None,
            "core_quality_pass": core, "difficulty_match": difficulty,
            "assessed_difficulty": review["review"]["assessed_difficulty"] if review else None,
            "delivered_and_core_pass": core if delivered is True else False if delivered is False else None,
            "delivered_and_target_match": difficulty if delivered is True else False if delivered is False else None})
    return {"path": str(run.resolve()), "manifest": manifest, "metrics": metrics, "cases": rows,
            "review_summary_present": review_summary is not None,
            "input_sha256": {"manifest.json": sha(run / "manifest.json"),
                             "metrics_summary.json": sha(run / "metrics_summary.json"),
                             "frozen_cases.json": sha(run / "frozen_cases.json"),
                             "ai-review/summary.json": sha(review_path) if review_path.exists() else None}}


def summarize_rows(rows):
    submitted = [r for r in rows if r["submitted"]]
    delivered = [r for r in rows if r["delivered"] is True]
    reviewed = [r for r in rows if r["reviewed"]]
    return {"planned": len(rows), "submitted": len(submitted),
        "unsubmitted_case_ids": [r["case_id"] for r in rows if not r["submitted"]],
        "retrieval_recorded": sum(r["retrieval_recorded"] for r in rows),
        "zero_call_submitted": sum(r["calls"] == 0 for r in submitted),
        "reviewed_candidates": len(reviewed), "delivered_reviewed": sum(r["reviewed"] for r in delivered),
        "delivered_unreviewed": sum(not r["reviewed"] for r in delivered),
        "delivery_per_planned": rate_known([r["delivered"] for r in rows]),
        "delivery_per_submitted": rate_known([r["delivered"] for r in submitted]),
        "core_quality_per_delivered": rate_known([r["core_quality_pass"] for r in delivered]),
        "delivered_core_per_planned": rate_known([r["delivered_and_core_pass"] for r in rows]),
        "delivered_core_per_submitted": rate_known([r["delivered_and_core_pass"] for r in submitted]),
        "target_match_per_delivered": rate_known([r["difficulty_match"] for r in delivered]),
        "hard_target_match_per_delivered": rate_known([r["difficulty_match"] for r in delivered if r["target_difficulty"] == "hard"]),
        "target_match_per_strict_delivered": rate_known([r["difficulty_match"] for r in delivered if r["runtime_outcome"] == "strict"]),
        "target_match_per_adjusted_delivered": rate_known([r["difficulty_match"] for r in delivered if r["runtime_outcome"] == "adjusted"]),
        "runtime_outcomes": dict(Counter(r["runtime_outcome"] for r in rows)),
        "diagnostic_outcomes": dict(Counter(r["diagnostic_outcome"] for r in rows)),
        "wall_seconds_submitted": median([r["wall_seconds"] for r in submitted]),
        "wall_seconds_delivered": median([r["wall_seconds"] for r in delivered]),
        "generation_calls": sum(r["calls"] for r in rows)}


def comparability(a, b):
    left, right = a["manifest"], b["manifest"]
    required = ("dataset_sha256", "case_order", "planned_cases", "call_cap", "per_job_cap", "max_seconds", "seed", "configuration")
    differences = [key for key in required if left.get(key) != right.get(key)]
    if a["input_sha256"]["frozen_cases.json"] != b["input_sha256"]["frozen_cases.json"]:
        differences.append("frozen_cases.json")
    ac, bc = left["code_sha256"], right["code_sha256"]
    changed_code = [p for p in sorted(set(ac) | set(bc)) if ac.get(p) != bc.get(p)]
    if any(p.startswith("scripts/") for p in changed_code):
        differences.append("frozen_runner_or_metrics_code")
    return {"matched_frozen_controls": not differences, "control_differences": differences,
            "changed_application_code": changed_code,
            "note": "Application changes require the pre-run intervention audit. Matching controls do not establish causality or remove provider nondeterminism."}


def compare(left, right):
    a, b = load_run(left), load_run(right)
    if {r["case_id"] for r in a["cases"]} != {r["case_id"] for r in b["cases"]}:
        raise ValueError("Paired runs must have identical planned case IDs")
    checks = comparability(a, b)
    summaries = []
    for run in (a, b):
        m = run["metrics"]
        summaries.append({"path": run["path"], "status": run["manifest"]["status"],
            "stop_reason": run["manifest"].get("stop_reason"), **summarize_rows(run["cases"]),
            "study_calls": m["study_calls"], "setup_calls": m["setup_calls"],
            "rejection_issue_counts": m["rejection_issue_counts"], "input_sha256": run["input_sha256"]})
    def delta(key, subkey="rate"):
        av, bv = summaries[0][key][subkey], summaries[1][key][subkey]
        return bv - av if checks["matched_frozen_controls"] and av is not None and bv is not None else None
    indexed_b = {r["case_id"]: r for r in b["cases"]}
    pairs, needs = [], defaultdict(list)
    for ar in a["cases"]:
        br = indexed_b[ar["case_id"]]
        row = {"case_id": ar["case_id"], "need_id": ar["need_id"], "language": ar["language"],
               "target_difficulty": ar["target_difficulty"], "baseline": ar, "candidate": br,
               "wall_seconds_delta": br["wall_seconds"] - ar["wall_seconds"]
                   if br["wall_seconds"] is not None and ar["wall_seconds"] is not None else None,
               "generation_calls_delta": br["calls"] - ar["calls"]}
        for name in ("delivered", "delivered_and_core_pass", "delivered_and_target_match"):
            row[name + "_transition"] = (f"{int(ar[name])}->{int(br[name])}"
                if ar[name] is not None and br[name] is not None else "unknown")
        pairs.append(row); needs[ar["need_id"]].append(row)
    return {"schema_version": "quality-latency-paired-comparison-v1",
        "evidence_scope": "Same-development-set paired descriptive comparison. One stochastic run per condition; AI-assisted review is neither human validation nor independent model consensus.",
        "comparability": checks, "baseline": summaries[0], "candidate": summaries[1],
        "rate_deltas_candidate_minus_baseline": {key: delta(key) for key in
            ("delivery_per_planned", "delivered_core_per_planned", "core_quality_per_delivered",
             "target_match_per_delivered", "hard_target_match_per_delivered")},
        "wall_median_delta_seconds": delta("wall_seconds_submitted", "median"),
        "paired_cases": pairs,
        "paired_knowledge_needs": [{"need_id": need, "case_ids": [r["case_id"] for r in rows],
            "baseline": summarize_rows([r["baseline"] for r in rows]),
            "candidate": summarize_rows([r["candidate"] for r in rows]),
            "note": "The bilingual variants share this need; do not treat them as independent topics."}
            for need, rows in sorted(needs.items())]}


def export(result, output):
    out = Path(output)
    # Outputs belong outside frozen input runs. Never rewrite their artifacts.
    for side in ("baseline", "candidate"):
        if out.resolve().is_relative_to(Path(result[side]["path"])):
            raise ValueError("Comparison output must be outside both frozen runs")
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ["case_id", "need_id", "language", "target_difficulty", "delivered_transition",
              "delivered_and_core_pass_transition", "delivered_and_target_match_transition",
              "wall_seconds_delta", "generation_calls_delta"]
    with (out / "paired_cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in result["paired_cases"])
    return out / "comparison.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate)
    print(export(result, args.output))
