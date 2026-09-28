#!/usr/bin/env python3
"""Prepare an unlabelled annotation pack from already-downloaded course sources.

No network, LLM calls, or relevance labels. Source bytes are verified before
extracting contiguous source-line passages. Existing human CSVs are preserved.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "benchmarks/rag/course_sources"
TARGET_CHARACTERS = 1200


def spans(lines: list[str]):
    """Pack whole blank-line-separated blocks; split long blocks at line boundaries."""
    blocks = []
    start = None
    for index, line in enumerate(lines + [""]):
        if line.strip() and start is None:
            start = index
        elif not line.strip() and start is not None:
            blocks.append((start, index))
            start = None
    packed = []
    for start, end in blocks:
        if packed and len("\n".join(lines[packed[-1][0]:end])) <= TARGET_CHARACTERS:
            packed[-1] = (packed[-1][0], end)
        else:
            segment_start = start
            for index in range(start + 1, end):
                if len("\n".join(lines[segment_start:index + 1])) > TARGET_CHARACTERS:
                    packed.append((segment_start, index))
                    segment_start = index
            packed.append((segment_start, end))
    return packed


def create_empty_csv(path: Path, fields: list[str]):
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=fields).writeheader()


def main():
    manifest_path = PACK / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    documents = []
    for source in manifest["sources"]:
        for download in source["downloads"]:
            path = ROOT / download["local_path"]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != download["sha256"]:
                raise ValueError(f"Source hash mismatch: {path}")
            if download["role"] != "course_text":
                continue
            lines = raw.decode("utf-8").splitlines()
            stem = Path(download["repository_path"]).stem
            for number, (start, end) in enumerate(spans(lines), 1):
                text = "\n".join(lines[start:end])
                passage_id = f"{source['id']}:{stem}:{number:03d}"
                source_url = (
                    f"https://github.com/{source['repo']}/blob/{source['revision']}/"
                    f"{download['repository_path']}#L{start + 1}-L{end}"
                )
                documents.append({
                    "id": passage_id,
                    "text": text,
                    "language": source["language"],
                    "source_id": source["id"],
                    "source_url": source_url,
                    "source_path": download["local_path"],
                    "repository_path": download["repository_path"],
                    "source_sha256": download["sha256"],
                    "revision": source["revision"],
                    "license": source["license"],
                    "authors": source["authors"],
                    "line_start": start + 1,
                    "line_end": end,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "text_format": "raw_markdown" if path.suffix == ".md" else "raw_rst",
                })
    if len({doc["id"] for doc in documents}) != len(documents):
        raise ValueError("Duplicate passage IDs")
    corpus = {
        "schema_version": "course-corpus-v1",
        "corpus_id": "undergraduate_cs_bilingual_sources_v1",
        "label_status": "pending_human_review",
        "qrels_available": False,
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "sources": [{key: source[key] for key in ("id", "language", "repo", "revision", "license", "authors")}
                    for source in manifest["sources"]],
        "preprocessing": {
            "version": "contiguous_source_lines_v1",
            "target_characters": TARGET_CHARACTERS,
            "overlap": 0,
            "description": "Whole blank-line-separated blocks packed to 1200 characters, with long blocks split at line boundaries. An individual long line can exceed the target. No content rewriting; original markup is retained. Each text exactly equals the recorded source line interval joined with LF.",
            "limitations": "This is an annotation inventory, not a validated production chunker. Unexpanded image/code/visualization references and markup-only spans are retained and may not provide standalone evidence.",
        },
        "documents": documents,
    }
    (PACK / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n")
    fields = ["passage_id", "language", "source_id", "source_url", "source_path", "line_start", "line_end", "text"]
    with (PACK / "passages.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for doc in documents:
            writer.writerow({"passage_id": doc["id"], **{key: doc[key] for key in fields[1:]}})
    create_empty_csv(PACK / "human_queries.csv", [
        "query_id", "query_text", "query_language", "author_id", "authored_at_utc",
        "family_id", "proposed_split", "category", "answerable", "notes",
        "reviewer_id", "reviewed_at", "review_status",
    ])
    create_empty_csv(PACK / "human_judgments.csv", [
        "query_id", "passage_id", "annotator_id", "judged_at_utc", "relevance_grade",
        "required_evidence_group", "rationale", "review_status", "reviewer_id", "reviewed_at",
    ])
    print(json.dumps({"corpus_documents": len(documents), "human_labels_created": 0, "network_calls": 0}))


if __name__ == "__main__":
    main()
