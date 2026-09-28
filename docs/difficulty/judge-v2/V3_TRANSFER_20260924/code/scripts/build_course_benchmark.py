#!/usr/bin/env python3
"""Strict offline conversion of reviewed course CSVs; never invents labels.

Field validation establishes a complete provenance declaration, not proof of a
person's identity or expertise. Actual human review must happen outside this tool.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag_evaluation import validate_dataset

DEFAULT_PACK = ROOT / "benchmarks/rag/course_sources"


def required(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing nonempty human field: {field}")
    return value.strip()


def timestamp(row, field):
    value = required(row, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp must include timezone: {field}")
    return parsed


def review(row, original_time):
    reviewer = required(row, "reviewer_id")
    reviewed_at = timestamp(row, "reviewed_at")
    if reviewed_at < original_time:
        raise ValueError("Review date precedes authorship or judgment date")
    if required(row, "review_status") not in ("reviewed", "adjudicated"):
        raise ValueError("Human review is incomplete: reviewed/adjudicated required")
    return {"reviewer_id": reviewer, "reviewed_at": row["reviewed_at"], "review_status": row["review_status"]}


def load_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV headers must be present and unique")
        rows = []
        for row in reader:
            if None in row:
                raise ValueError("CSV has more fields than its header")
            if any(value and value.strip() for value in row.values()):
                rows.append(row)
        return rows


def build_dataset(corpus, query_rows, judgment_rows, *, dataset_id):
    if not query_rows or not judgment_rows:
        raise ValueError("Empty human annotation tables: cannot produce human_reviewed benchmark")
    if corpus.get("schema_version") != "course-corpus-v1":
        raise ValueError("Unsupported course corpus schema")
    sources = corpus.get("sources", [])
    source_ids = {required(source, "id") for source in sources}
    if not source_ids or len(source_ids) != len(sources):
        raise ValueError("Corpus must declare unique source IDs")
    documents = corpus.get("documents", [])
    doc_ids = set()
    for doc in documents:
        doc_id = required(doc, "id")
        text = required(doc, "text")
        if doc_id in doc_ids or doc.get("source_id") not in source_ids:
            raise ValueError("Duplicate passage or invalid source ID")
        if hashlib.sha256(doc["text"].encode()).hexdigest() != doc.get("text_sha256"):
            raise ValueError("Passage text hash mismatch")
        doc_ids.add(doc_id)
    if not doc_ids:
        raise ValueError("Corpus has no passages")

    queries = []
    query_by_id = {}
    for row in query_rows:
        query_id = required(row, "query_id")
        if query_id in query_by_id:
            raise ValueError("Duplicate human query ID")
        author = required(row, "author_id")
        authored_at = timestamp(row, "authored_at_utc")
        provenance = {"author_id": author, "authored_at_utc": row["authored_at_utc"], **review(row, authored_at)}
        answerable = required(row, "answerable")
        if answerable not in ("true", "false"):
            raise ValueError("answerable must be literal true or false")
        language = required(row, "query_language")
        if language not in ("zh", "en"):
            raise ValueError("query_language must be zh or en")
        query = {
            "id": query_id, "text": required(row, "query_text"),
            "language": language, "category": required(row, "category"),
            "split": required(row, "proposed_split"), "family_id": required(row, "family_id"),
            "answerable": answerable == "true", "relevance": {}, "required_evidence_groups": [],
            "annotation_provenance": provenance, "annotation_notes": row.get("notes", ""),
        }
        if not query["answerable"] and not query["annotation_notes"].strip():
            raise ValueError("Unanswerable queries require a human rationale in notes")
        queries.append(query)
        query_by_id[query_id] = query

    judgments = {query_id: {} for query_id in query_by_id}
    evidence = {query_id: {} for query_id in query_by_id}
    raw_judgments = []
    for row in judgment_rows:
        query_id, doc_id = required(row, "query_id"), required(row, "passage_id")
        if query_id not in query_by_id or doc_id not in doc_ids:
            raise ValueError("Judgment references unknown query or passage")
        if doc_id in judgments[query_id]:
            raise ValueError("Duplicate judgment pair: adjudicate conflicts into a separate final CSV")
        required(row, "annotator_id")
        judged_at = timestamp(row, "judged_at_utc")
        review(row, judged_at)
        grade = required(row, "relevance_grade")
        if grade not in ("0", "1", "2"):
            raise ValueError("relevance_grade must be the exact integer string 0, 1, or 2")
        required(row, "rationale")
        judgments[query_id][doc_id] = int(grade)
        if grade != "0":
            query_by_id[query_id]["relevance"][doc_id] = int(grade)
        raw_groups = row.get("required_evidence_group") or ""
        groups = [group.strip() for group in raw_groups.split(";") if group.strip()]
        if len(groups) != len(set(groups)):
            raise ValueError("Duplicate evidence group in judgment")
        if groups and grade != "2":
            raise ValueError("Necessary fact groups require direct supporting evidence graded 2")
        for group in groups:
            evidence[query_id].setdefault(group, []).append(doc_id)
        raw_judgments.append(dict(row))
    for query in queries:
        if set(judgments[query["id"]]) != doc_ids:
            raise ValueError(f"Incomplete judgment coverage for {query['id']}: every frozen passage needs an explicit grade")
        query["required_evidence_groups"] = list(evidence[query["id"]].values())
        query["evidence_group_names"] = list(evidence[query["id"]])
    dataset = {
        "schema_version": "rag-benchmark-v1", "dataset_id": dataset_id,
        "label_status": "human_reviewed",
        "evaluation_scope": "Human-declared complete judgments over the frozen bilingual undergraduate course corpus. The converter validates fields and coverage, not identities, expertise, representativeness, or truth of the review declaration.",
        "documents": documents, "queries": queries,
        "annotation_provenance": {"judgment_coverage": "exhaustive_with_explicit_zeroes", "raw_final_judgments": raw_judgments, "source_corpus_id": corpus.get("corpus_id"), "sources": sources},
    }
    validate_dataset(dataset)
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_PACK / "corpus.json")
    parser.add_argument("--queries", type=Path, default=DEFAULT_PACK / "human_queries.csv")
    parser.add_argument("--judgments", type=Path, default=DEFAULT_PACK / "human_judgments.csv")
    parser.add_argument("--dataset-id", default="undergraduate_cs_bilingual_human_v1")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks/rag/course_human_v1.json")
    args = parser.parse_args()
    try:
        corpus_bytes = args.corpus.read_bytes()
        corpus = json.loads(corpus_bytes)
        manifest_bytes = (args.corpus.parent / "manifest.json").read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != corpus.get("source_manifest_sha256"):
            raise ValueError("Source manifest hash mismatch; rebuild and refreeze the annotation inventory")
        manifest = json.loads(manifest_bytes)
        manifest_sources = {source["id"]: source for source in manifest["sources"]}
        for doc in corpus.get("documents", []):
            source = manifest_sources.get(doc.get("source_id"))
            if source is None:
                raise ValueError("Passage source ID is absent from the frozen manifest")
            matches = [item for item in source["downloads"] if item["role"] == "course_text" and item["repository_path"] == doc.get("repository_path")]
            if len(matches) != 1 or matches[0]["sha256"] != doc.get("source_sha256") or source["revision"] != doc.get("revision"):
                raise ValueError("Passage provenance does not match the frozen source manifest")
        dataset = build_dataset(corpus, load_csv(args.queries), load_csv(args.judgments), dataset_id=args.dataset_id)
        dataset["input_sha256"] = {"corpus": hashlib.sha256(corpus_bytes).hexdigest(), "queries": hashlib.sha256(args.queries.read_bytes()).hexdigest(), "judgments": hashlib.sha256(args.judgments.read_bytes()).hexdigest()}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Annotation conversion refused: {exc}\n")
    print(json.dumps({"output": str(args.output), "queries": len(dataset["queries"]), "label_status": dataset["label_status"]}))


if __name__ == "__main__":
    main()
