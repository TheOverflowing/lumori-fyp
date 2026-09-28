#!/usr/bin/env python3
"""Rebuild the frozen T2Ranking CS web supplement without models or relevance edits."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'benchmarks/rag/external/t2ranking'
REVISION = '76631901a18387f85eaa53e5450019b87ad58ef9'
SOURCE_URL = f'https://huggingface.co/datasets/C-MTEB/T2Reranking/resolve/{REVISION}/data/dev-00000-of-00001-65d96bde8023d9b9.parquet'
SOURCE_SHA256 = 'ceaf1ba1a4777dbb7aecad86fb8aa9cae7a678af6d711d5529c238e89bb6adff'
KEYWORD_CACHE_SHA256 = '135f88ee87bbd63779bb316b1688a6036c304e6f4460f61545d1f6e683decdce'


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as handle:
        while block := handle.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def normal(value: str) -> str:
    return unicodedata.normalize('NFKC', value).casefold()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def matches(query: str, terms: list[str]) -> bool:
    query = normal(query)
    for term in terms:
        term = normal(term)
        if any('\u4e00' <= character <= '\u9fff' for character in term):
            if term in query:
                return True
        elif re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', query):
            return True
    return False


def rebuild_keyword_cache(base: Path, protocol: dict) -> None:
    """Optional full-source verification; pyarrow is only needed for this step."""
    import pyarrow.parquet as pq
    source = base / 'source/dev.parquet'
    if file_digest(source) != SOURCE_SHA256:
        raise ValueError('The full source Parquet SHA-256 does not match the frozen release.')
    rows = pq.read_table(source).to_pylist()
    if len(rows) != 6129:
        raise ValueError('Unexpected full source row count.')
    result = []
    for index, row in enumerate(rows):
        if matches(row['query'], protocol['computer_science_terms']):
            result.append(json.dumps({'source_row_index': index, **row}, ensure_ascii=False) + '\n')
    contents = ''.join(result).encode()
    cache_path = base / 'source/keyword-candidates.jsonl'
    if cache_path.exists() and cache_path.read_bytes() != contents:
        raise ValueError('Frozen keyword cache differs from a fresh full-source extraction.')
    cache_path.write_bytes(contents)


def build(base: Path) -> tuple[dict, list[dict]]:
    if file_digest(base / 'source/keyword-candidates.jsonl') != KEYWORD_CACHE_SHA256:
        raise ValueError('Frozen keyword source cache SHA-256 mismatch.')
    protocol = json.loads((base / 'selection-protocol-v2.json').read_text())
    decisions_file = base / 'topic-decisions.json'
    decisions = json.loads(decisions_file.read_text())['decisions']
    rows = [json.loads(line) for line in (base / 'source/keyword-candidates.jsonl').read_text().splitlines()]
    by_index = {row['source_row_index']: row for row in rows}
    if len(by_index) != len(rows) or set(by_index) != {item['source_row_index'] for item in decisions}:
        raise ValueError('Topic decisions must cover each frozen keyword candidate exactly once.')
    selected = []
    for decision in decisions:
        row = by_index[decision['source_row_index']]
        if digest(row['query'].encode()) != decision['query_sha256'] or row['query'] != decision['query']:
            raise ValueError('A frozen topic decision no longer matches its source query.')
        if type(decision['include']) is not bool:
            raise ValueError('Topic inclusion must be a boolean.')
        if decision['include']:
            if not row['positive'] or not row['negative']:
                raise ValueError('A selected source query lacks its positive or negative judgments.')
            selected.append(row)
    seed = protocol['seed']
    selected.sort(key=lambda row: digest((seed + '\0' + normal(row['query'])).encode()))
    if len(selected) != protocol['selected_queries']:
        raise ValueError('Selected query count differs from the frozen protocol.')
    if len({normal(row['query']) for row in selected}) != len(selected):
        raise ValueError('Duplicate normalized queries require explicit family grouping before building.')

    documents: dict[str, dict] = {}
    queries = []
    judgment_rows = []
    for order, row in enumerate(selected):
        query_id = 't2q-' + digest(row['query'].encode())[:20]
        positive_ids, negative_ids = [], []
        for polarity in ('positive', 'negative'):
            ids = positive_ids if polarity == 'positive' else negative_ids
            for position, passage in enumerate(row[polarity]):
                if not isinstance(passage, str) or not passage.strip():
                    raise ValueError('Blank or invalid passage found in the source judgments.')
                document_id = 't2d-' + digest(passage.encode())
                if document_id not in documents:
                    documents[document_id] = {
                        'id': document_id, 'text': passage, 'language': 'zh',
                        'source': 'C-MTEB/T2Reranking', 'source_revision': REVISION,
                        'source_url': SOURCE_URL, 'source_occurrences': [],
                    }
                documents[document_id]['source_occurrences'].append({
                    'source_row_index': row['source_row_index'], 'source_label': polarity,
                    'source_list_position': position,
                })
                if document_id not in ids:
                    ids.append(document_id)
                judgment_rows.append({
                    'query_id': query_id, 'document_id': document_id,
                    'source_row_index': row['source_row_index'], 'source_label': polarity,
                    'source_list_position': position, 'original_four_level_grade': '',
                    'binary_grade': int(polarity == 'positive'),
                })
        if set(positive_ids) & set(negative_ids):
            raise ValueError('Conflicting source binary labels for the same exact query-passage text.')
        queries.append({
            'id': query_id, 'text': row['query'], 'language': 'zh',
            'split': 'dev' if order % 2 == 0 else 'test',
            'category': 'cs_web_search', 'answerable': True,
            'family_id': 't2f-' + digest(normal(row['query']).encode())[:20],
            'relevance': {document_id: 1 for document_id in positive_ids},
            'required_evidence_groups': [positive_ids],
            'evidence_group_semantics': 'One group of any known relevant passage; a hit diagnostic, not human-annotated answer completeness.',
            'judgments': {**{document_id: 1 for document_id in positive_ids},
                          **{document_id: 0 for document_id in negative_ids}},
            'explicit_negative_document_ids': negative_ids,
            'source_candidate_document_ids': positive_ids + negative_ids,
            'unjudged_policy': 'Other corpus documents are unjudged for this query, not human negative labels.',
            'source_split': 'dev', 'source_row_index': row['source_row_index'],
            'source_label_schema': 'C-MTEB binary positive/negative; original 0–3 scores unavailable',
            'label_provenance': 'Inherited public T2Ranking-derived human relevance; no new assistant relevance annotation.',
        })
    if len(documents) > protocol['max_unique_passages']:
        raise ValueError('Passage budget exceeded; source judgments must not be truncated.')
    dataset = {
        'schema_version': 'rag-benchmark-v1',
        'dataset_id': 't2ranking_cs_web_binary_v1',
        'label_status': 'public_human_relevance',
        'language_scope': ['zh'],
        'task_scope': 'Small CS-topic Chinese web supplement from a public reranking pool; not course lecture retrieval.',
        'provenance': {
            'dataset': 'C-MTEB/T2Reranking', 'revision': REVISION,
            'source_sha256': SOURCE_SHA256, 'source_split': 'dev',
            'original_dataset': 'THUIR/T2Ranking',
            'original_license': 'Apache-2.0 as declared by THUIR/T2Ranking authors',
            'derived_card_license': 'not specified; retained as a provenance limitation',
            'label_mapping': 'Published positive -> 1; negative -> 0; original four-level grades are not reconstructed.',
            'topic_selection': 'Assistant topic screening only, before any ranking; all original binary lists preserved.',
            'query_split': 'Hash-sorted queries from official dev are alternated into local dev/test; official test not used.',
            'candidate_pool': 'Union of all provided judgments for selected queries; cross-query pairs are unjudged.',
            'completeness': 'Original full-collection qrels are not available in this binary reranking release.',
        },
        'limitations': [
            'Only 20 queries; intended for diagnostics, not generalization claims.',
            'All relevance metrics are known-positive metrics within a reduced, preselected corpus.',
            'The union corpus contains unjudged cross-query pairs; treating them as zero in metrics does not turn them into human negatives.',
            'Source candidate pooling can favor methods similar to original search systems.',
            'Required evidence groups are a mechanical any-positive diagnostic, not human evidence completeness annotations.',
            'The historical public data may have appeared in embedding model training; contamination is unknown.',
            'Both local splits derive from official dev; they are not the source official test benchmark.',
        ],
        'documents': list(documents.values()), 'queries': queries,
    }
    return dataset, judgment_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--download', action='store_true', help='Download the exact frozen full source if missing.')
    parser.add_argument('--verify-source', action='store_true', help='Verify/re-extract cache from full Parquet; requires pyarrow==21.0.0.')
    parser.add_argument('--check', action='store_true', help='Compare a deterministic reconstruction without changing artifacts.')
    args = parser.parse_args()
    base = args.base.resolve()
    if args.download:
        target = base / 'source/dev.parquet'
        if not target.exists():
            with urllib.request.urlopen(SOURCE_URL, timeout=60) as response, target.open('wb') as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
        if file_digest(target) != SOURCE_SHA256:
            raise ValueError('Downloaded source hash mismatch.')
    if args.verify_source:
        rebuild_keyword_cache(base, json.loads((base / 'selection-protocol-v2.json').read_text()))
    dataset, judgments = build(base)
    sys.path.insert(0, str(ROOT))
    from app.rag_evaluation import validate_dataset
    validate_dataset(dataset)
    output = base / 'benchmark.json'
    contents = json_bytes(dataset)
    if args.check:
        if output.read_bytes() != contents:
            raise ValueError('Benchmark differs from deterministic rebuild.')
        print(json.dumps({'status': 'identical', 'queries': len(dataset['queries']), 'documents': len(dataset['documents']), 'sha256': digest(contents)}))
        return
    output.write_bytes(contents)
    with (base / 'judgments.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(judgments[0]))
        writer.writeheader()
        writer.writerows(judgments)
    files = [path for path in sorted(base.rglob('*')) if path.is_file() and path.name != 'build-manifest.json']
    manifest = {
        'schema_version': 't2ranking-cs-build-v1', 'dataset_id': dataset['dataset_id'],
        'query_count': len(dataset['queries']), 'document_count': len(dataset['documents']),
        'source_judgment_count': len(judgments),
        'split_counts': {split: sum(q['split'] == split for q in dataset['queries']) for split in ('dev', 'test')},
        'source_url': SOURCE_URL, 'source_revision': REVISION, 'source_sha256': SOURCE_SHA256,
        'benchmark_sha256': digest(contents), 'builder_sha256': file_digest(Path(__file__)),
        'files': {str(path.relative_to(base)): file_digest(path) for path in files},
        'api_calls': 0, 'relevance_labels_created_by_assistant': 0,
    }
    (base / 'build-manifest.json').write_bytes(json_bytes(manifest))
    print(json.dumps({key: manifest[key] for key in ('dataset_id', 'query_count', 'document_count', 'source_judgment_count', 'split_counts', 'benchmark_sha256')}))


if __name__ == '__main__':
    main()
