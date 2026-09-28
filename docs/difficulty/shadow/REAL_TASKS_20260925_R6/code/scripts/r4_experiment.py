"""R4 staged experiments. Freeze -> embed -> dev -> rerank -> lock -> test.

Test labels never influence choose(). Existing R2/R3 queries are development data.
All labels come from public original MLQA answer spans; no model-made qrels.
"""
import argparse
import asyncio
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from app.config import Settings
from app.providers import ApiProviders
from app.store import Store
from app.retrieval import rank_chunks, normalize_vectors
from app.rag_candidates import TokenCounter, token_chunks, title_input, query_input, assemble_context
from scripts.chunk_experiment import make_chunks, gold_spans, span_metrics, structure_stats
from scripts.build_mlqa_cs_benchmark import read_records, TITLES, ARCHIVE_SHA, doc_id
from scripts.rag_experiment import write_csv

BASE = ROOT / 'docs/rag/r4-experiments'
PROTOCOL = ROOT / 'docs/rag/R4_PROTOCOL_V1.md'
TOKENIZER = ROOT / '.rag-models/embedding-tokenizer/tokenizer.json'
OLD = ROOT / 'benchmarks/rag/external/mlqa/mlqa_cs_en_zh_v1.json'
OLD_CACHE = ROOT / 'docs/rag/chunk-experiments/20260912T062952243934Z/embedding-cache.json'
EXTRA_TITLES = ('Cryptanalysis', 'Data logger', 'Data mining', 'Digital rights', 'Free software movement',
                'Google Search', 'History of Linux', 'Linux Documentation Project', 'Logic gate',
                'M4 (computer language)', 'Nova (operating system)', 'Rake (software)',
                'Unobtrusive JavaScript', 'Web Services Description Language', 'Web design', 'World Wide Web')
# Each value is (cut, title_encoding, query_instruction, ranker, expansion).
ARMS = {
    'baseline': ('char1200', False, False, 'dense_v1', 'none'),
    'query_instruction': ('char1200', False, True, 'dense_v1', 'none'),
    'title': ('char1200', True, False, 'dense_v1', 'none'),
    'title_instruction': ('char1200', True, True, 'dense_v1', 'none'),
    'char_hybrid': ('char1200', False, False, 'hybrid_dense_lexical_v1', 'none'),
    'token256': ('token256', False, False, 'dense_v1', 'none'),
    'token128': ('token128', False, False, 'dense_v1', 'none'),
    'token_title_instruction': ('token256', True, True, 'dense_v1', 'none'),
    'token_hybrid': ('token256', True, True, 'hybrid_dense_lexical_v1', 'none'),
    'token_rrf': ('token256', True, True, 'hybrid_rrf_v1', 'none'),
    'token_parent': ('token256', True, True, 'hybrid_dense_lexical_v1', 'parent'),
    'token_window': ('token256', True, True, 'hybrid_dense_lexical_v1', 'window'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load(path):
    return json.loads(path.read_text())


def build_dataset():
    dataset = load(OLD)
    seen_ids = {q['family_id'] for q in dataset['queries']}
    seen_texts = {d['text'] for d in dataset['documents']}
    for q in dataset['queries']:
        q['original_split'] = q['split']
        q['split'] = 'dev'
    documents = {d['id']: d for d in dataset['documents']}
    path = OLD.parent / 'MLQA_V1.zip'
    if sha(path.read_bytes()) != ARCHIVE_SHA:
        raise ValueError('MLQA source archive changed.')
    decisions = []
    with zipfile.ZipFile(path) as archive:
        en, zh = (read_records(archive, 'test', lang) for lang in ('en', 'zh'))
        for qid in sorted(en.keys() & zh.keys()):
            if en[qid]['title'] not in set(TITLES) | set(EXTRA_TITLES):
                continue
            reason = ('previous_query' if qid in seen_ids else 'previous_context'
                      if en[qid]['context'] in seen_texts or zh[qid]['context'] in seen_texts else 'included')
            decisions.append({'family_id': qid, 'title': en[qid]['title'], 'decision': reason})
            if reason != 'included':
                continue
            known = [doc_id(lang, row['context']) for lang, row in (('en', en[qid]), ('zh', zh[qid]))]
            for lang, row in (('en', en[qid]), ('zh', zh[qid])):
                pid = doc_id(lang, row['context'])
                documents[pid] = {'id': pid, 'text': row['context'], 'title': row['title'], 'language': lang,
                                  'source': 'MLQA_V1', 'source_member': row['source_member'],
                                  'text_sha256': sha(row['context'].encode()), 'license': 'CC-BY-SA-3.0'}
                dataset['queries'].append({'id': qid + '-' + lang, 'family_id': qid, 'text': row['question'],
                    'split': 'test', 'language': lang, 'category': 'human_parallel_qa', 'answerable': True,
                    'relevance': {pid: 2 for pid in known}, 'required_evidence_groups': [known],
                    'original_context_id': pid, 'original_answers': row['answers'], 'source_member': row['source_member']})
    dataset['documents'] = list(documents.values())
    dataset['dataset_id'] = 'mlqa-cs-r4-family-context-heldout-v1'
    dataset['evaluation_scope'] = ('Known human answer-span coverage in CS-related Wikipedia; mixed and forced-cross-language tasks. '
                                   'Dev contains previously exposed queries; R4 test uses new exact-context-disjoint families. '
                                   'Not course gold or official MLQA answer-generation F1.')
    dataset['provenance']['r4'] = {'old_dataset_sha256': sha(OLD.read_bytes()), 'additional_titles': EXTRA_TITLES,
        'test_selection': 'all paired official-test CS whitelist families excluding prior family and either original context',
        'development': 'all 92 previously evaluated R2/R3 queries, including their previously seen test split',
        'limitations': 'Small CS-related Wikipedia slice including software history; not course-specific gold. '
                      'Exact contexts and families are disjoint, not all article titles. Model pretraining contamination unknown.'}
    return dataset, decisions


def freeze():
    dataset, decisions = build_dataset()
    spans = gold_spans(dataset)
    counter = TokenCounter(TOKENIZER)
    cuts = {'char1200': make_chunks(dataset['documents'], dict(strategy='recursive_v1', max_chars=1200, overlap_chars=120))}
    for size in (128, 256):
        cuts['token' + str(size)] = [c for d in dataset['documents'] for c in token_chunks(d, counter, size)]
    parents = {d['id']: d for d in dataset['documents']}
    for chunks in cuts.values():
        for c in chunks:
            c['title_text'] = title_input(c['text'], parents[c['parent_id']].get('title', ''), c['metadata'].get('heading_path', []))
    texts = {}
    for cut, title, instruct, _, _ in ARMS.values():
        for c in cuts[cut]:
            value = c['title_text'] if title else c['text']
            texts[sha(value.encode())] = value
        for q in dataset['queries']:
            value = query_input(q['text'], instruct)
            texts[sha(value.encode())] = value
    run = BASE / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    for name, value in [('dataset', dataset), ('selection-decisions', decisions), ('gold-spans', spans),
                        ('chunks', cuts), ('inputs', texts), ('arms', ARMS)]:
        save(run / (name + '.json'), value)
    (run / 'protocol.md').write_bytes(PROTOCOL.read_bytes())
    model_manifest = load(ROOT / '.rag-models/manifest.json')
    save(run / 'models.json', model_manifest)
    shutil.copyfile(TOKENIZER, run / 'tokenizer.json')
    paths = [*ROOT.glob('app/*.py'), *ROOT.glob('scripts/*r4*.py'), ROOT / 'scripts/chunk_experiment.py',
             ROOT / 'scripts/rag_experiment.py', ROOT / 'scripts/rag_history.py',
             ROOT / 'scripts/build_mlqa_cs_benchmark.py', ROOT / 'scripts/prepare_rag_models.py']
    for p in paths:
        dest = run / 'code' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    save(run / 'freeze.json', {'frozen_at': datetime.now(timezone.utc).isoformat(), 'status': 'frozen_before_ranking',
        'dataset_sha256': sha(canonical(dataset)), 'input_sha256': sha(canonical(texts)),
        'chunks_sha256': sha(canonical(cuts)), 'gold_sha256': sha(canonical(spans)),
        'protocol_sha256': sha(PROTOCOL.read_bytes()), 'arms_sha256': sha(canonical(ARMS)),
        'code_sha256': {str(p.relative_to(run / 'code')): sha(p.read_bytes()) for p in (run / 'code').rglob('*.py')},
        'queries': {split: sum(q['split'] == split for q in dataset['queries']) for split in ('dev', 'test')},
        'families': {split: len({q['family_id'] for q in dataset['queries'] if q['split'] == split}) for split in ('dev', 'test')},
        'source_documents': len(parents), 'input_texts': len(texts),
        'statistics': {cut: structure_stats(dataset['documents'], chunks) for cut, chunks in cuts.items()}})
    print(run, flush=True)
    return run


def verify(run):
    f = load(run / 'freeze.json')
    for file, key in [('dataset', 'dataset_sha256'), ('inputs', 'input_sha256'), ('arms', 'arms_sha256'),
                      ('chunks', 'chunks_sha256'), ('gold-spans', 'gold_sha256')]:
        if sha(canonical(load(run / (file + '.json')))) != f[key]:
            raise ValueError('Frozen ' + file + ' changed.')
    if sha((run / 'protocol.md').read_bytes()) != f['protocol_sha256']:
        raise ValueError('Frozen protocol changed.')
    if sha((run / 'tokenizer.json').read_bytes()) != load(run / 'models.json')['embedding-tokenizer']['files_sha256']['tokenizer.json']:
        raise ValueError('Frozen tokenizer changed.')
    for relative, digest in f['code_sha256'].items():
        if sha((ROOT / relative).read_bytes()) != digest:
            raise ValueError('Code changed after freeze: ' + relative + '; use the archived code for replay.')


async def embed(run, max_calls=100):
    verify(run)
    settings = Settings.from_env()
    inputs = load(run / 'inputs.json')
    old = load(OLD_CACHE)
    if old['embedding_signature'] != settings.embedding.signature:
        raise ValueError('Provider identity changed; reuse would mix embedding models.')
    reusable = dict(old['texts'])
    old_data = load(OLD)
    for q in old_data['queries']:
        reusable[sha(q['text'].encode())] = old['queries'][q['id']]
    vectors = {k: v for k, v in reusable.items() if k in inputs}
    batches_dir = run / 'embedding-batches'
    batches_dir.mkdir(exist_ok=True)
    for path in sorted(batches_dir.glob('*.npz')):
        data = np.load(path, allow_pickle=False)
        for key, vector in zip(data['keys'].tolist(), data['vectors']):
            if key not in inputs:
                raise ValueError('Unexpected cached input.')
            vectors[key] = vector
    missing = [(k, v) for k, v in inputs.items() if k not in vectors]
    if math.ceil(len(missing) / 16) > max_calls:
        raise ValueError('New call count exceeds explicit budget.')
    store = Store(run / 'runtime')
    provider = ApiProviders(replace(settings, data_dir=run / 'runtime', max_daily_calls=max_calls), store)
    try:
        for offset in range(0, len(missing), 16):
            batch = missing[offset:offset + 16]
            raw = await provider.embed([text for _, text in batch], run.name)
            matrix = np.asarray(raw, dtype=np.float64)
            if normalize_vectors(matrix).shape != (len(batch), old['dimensions']):
                raise ValueError('Unexpected embedding shape.')
            keys = [k for k, _ in batch]
            np.savez_compressed(batches_dir / (sha(canonical(keys)) + '.npz'), keys=np.array(keys), vectors=matrix)
            vectors.update(zip(keys, matrix))
            print(f'Embedding {min(offset + 16, len(missing))}/{len(missing)} new inputs', flush=True)
        keys = sorted(inputs)
        np.savez_compressed(run / 'embeddings.npz', keys=np.array(keys), vectors=np.array([vectors[k] for k in keys]))
        save(run / 'embedding-manifest.json', {'model': settings.embedding.model,
             'embedding_signature': settings.embedding.signature, 'dimensions': old['dimensions'],
             'input_sha256': sha(canonical(inputs)), 'npz_sha256': sha((run / 'embeddings.npz').read_bytes()),
             'new_texts_this_invocation': len(missing), 'reused_inputs': len(inputs) - len(missing)})
    finally:
        save(run / 'provider-calls.json', store.calls_for_job(run.name))
        await provider.close()


def context_rows(ranked, query, spans, parents, counter, expansion):
    selected, tokens = assemble_context(ranked, parents, counter, budget=1024, expansion=expansion)
    metrics = span_metrics(selected, spans)
    top = span_metrics(ranked[:5], spans)
    relevant = [span_metrics([c], spans)['known_span_hit'] for c in ranked[:20]]
    reciprocal = next((1 / (i + 1) for i, rel in enumerate(relevant[:5]) if rel), 0.0)
    return {'budget_hit': metrics['known_span_hit'], 'span_coverage': metrics['best_span_coverage'],
            'known_context_coverage': metrics['known_context_coverage'], 'top5_hit': top['known_span_hit'],
            'mrr5': reciprocal, 'candidate_hit20': int(any(relevant)), 'context_tokens': tokens,
            'context': [{'parent_id': c['parent_id'], 'start': c['source_start'], 'end': c['source_end']} for c in selected]}


def summarize(rows):
    groups = defaultdict(list)
    for r in rows:
        for group in ('all', 'mode:' + r['mode'], 'language:' + r['language']):
            groups[(r['arm'], group)].append(r)
    result = []
    for (arm, group), records in groups.items():
        values = {'arm': arm, 'group': group, 'queries': len(records)}
        for k in ('budget_hit', 'top5_hit', 'mrr5', 'known_context_coverage', 'candidate_hit20',
                  'span_coverage', 'context_tokens', 'ranking_ms', 'rerank_ms'):
            values[k] = statistics.mean(r[k] for r in records)
        values['p95_rerank_ms'] = float(np.percentile([r['rerank_ms'] for r in records], 95))
        result.append(values)
    return result


def choose(summary):
    rows = [r for r in summary if r['group'] == 'all']
    # Deterministic, frozen ordering: quality first, expensive ties do not win.
    return max(rows, key=lambda r: (r['budget_hit'], r['mrr5'], -int(r['arm'].startswith('rerank_')),
                                    -r['context_tokens'], -list_order(r['arm'])))['arm']


def list_order(arm):
    return list(ARMS).index(arm) if arm in ARMS else 100 + ['rerank_none', 'rerank_parent'].index(arm)


def rank(run, split, include_rerank=False):
    verify(run)
    if split == 'test' and not (run / 'selection-lock.json').exists():
        raise ValueError('Lock a dev-only choice before any held-out ranking.')
    if split == 'dev' and (run / 'test-per-query.json').exists():
        raise ValueError('Test already exposed; start a separately labeled experiment instead of retuning.')
    ds, cuts, gold, arms = (load(run / (n + '.json')) for n in ('dataset', 'chunks', 'gold-spans', 'arms'))
    manifest = load(run / 'embedding-manifest.json')
    if manifest['npz_sha256'] != sha((run / 'embeddings.npz').read_bytes()):
        raise ValueError('Embedding cache changed.')
    data = np.load(run / 'embeddings.npz', allow_pickle=False)
    vectors = dict(zip(data['keys'].tolist(), data['vectors']))
    parents = {d['id']: d for d in ds['documents']}
    counter = TokenCounter(run / 'tokenizer.json')
    rows, rankings, requests = [], {}, {}
    rerank_scores = load(run / (split + '-rerank-scores.json')) if include_rerank else {}
    rerank_base = load(run / 'rerank-base.json')['arm'] if (run / 'rerank-base.json').exists() else None
    for arm, (cut, titled, instructed, strategy, expansion) in arms.items():
        chunks = [dict(c, vector=vectors[sha((c['title_text'] if titled else c['text']).encode())].tolist()) for c in cuts[cut]]
        for q in ds['queries']:
            if q['split'] != split:
                continue
            for mode in ('mixed', 'cross'):
                candidates = [c for c in chunks if mode == 'mixed' or c['language'] != q['language']]
                spans = [s for s in gold[q['id']] if mode == 'mixed' or s['language'] != q['language']]
                began = time.perf_counter()
                ranked = rank_chunks(candidates, q['text'], vectors[sha(query_input(q['text'], instructed).encode())].tolist(),
                    strategy=strategy, top_k=20, candidate_k=20, rrf_k=60, mmr_lambda=0.7)
                ranking_ms = (time.perf_counter() - began) * 1000
                key = q['id'] + ':' + mode
                rankings[arm + ':' + key] = [{'id': c['id'], 'score': c['score']} for c in ranked]
                rows.append({'arm': arm, 'query_id': q['id'], 'family_id': q['family_id'], 'language': q['language'],
                             'mode': mode, 'split': split, 'ranking_ms': ranking_ms, 'rerank_ms': 0.,
                             **context_rows(ranked, q, spans, parents, counter, expansion)})
                if arm == rerank_base:
                    docs = [{'id': c['id'], 'text': c['title_text'] if titled else c['text']} for c in ranked]
                    requests[key] = {'query': q['text'], 'documents': docs}
                    if include_rerank:
                        output = rerank_scores[key]
                        if output['request_sha256'] != sha(canonical(requests[key])):
                            raise ValueError('Reranker cache does not match the frozen request.')
                        values = output['scores']
                        if len(values) != len(ranked) or not all(math.isfinite(s) for s in values):
                            raise ValueError('Invalid reranking scores.')
                        reranked = [ranked[i] for i in sorted(range(len(ranked)), key=lambda i: (-values[i], i))]
                        for policy in ('none', 'parent'):
                            name = 'rerank_' + policy
                            rankings[name + ':' + key] = [{'id': c['id'], 'score': values[ranked.index(c)]} for c in reranked]
                            rows.append({'arm': name, 'query_id': q['id'], 'family_id': q['family_id'], 'language': q['language'],
                                'mode': mode, 'split': split, 'ranking_ms': ranking_ms, 'rerank_ms': output['duration_ms'],
                                **context_rows(reranked, q, spans, parents, counter, policy)})
    save(run / (split + '-per-query.json'), rows)
    save(run / (split + '-rankings.json'), rankings)
    summary = summarize(rows)
    save(run / (split + '-summary.json'), summary)
    write_csv(run / (split + '-metrics.csv'), list(summary[0]), summary)
    if rerank_base:
        save(run / (split + '-rerank-requests.json'), requests)
    if split == 'dev' and not rerank_base:
        winner = choose(summary)
        save(run / 'rerank-base.json', {'arm': winner, 'configuration': arms[winner], 'selected_from': 'dev_only',
                                     'summary_sha256': sha(canonical(summary))})
    for r in summary:
        if r['group'] == 'all':
            print(r['arm'], 'budget', round(r['budget_hit'], 4), 'MRR', round(r['mrr5'], 4), flush=True)
    return summary


def lock(run):
    if (run / 'selection-lock.json').exists():
        raise ValueError('Selection already locked.')
    if (run / 'test-per-query.json').exists():
        raise ValueError('Cannot choose after test exposure.')
    rows = load(run / 'dev-summary.json')
    winner = choose(rows)
    save(run / 'selection-lock.json', {'selected_arm': winner, 'basis': 'dev_only',
         'locked_at': datetime.now(timezone.utc).isoformat(), 'dev_summary_sha256': sha(canonical(rows)),
         'reranker_evaluated': any(r['arm'].startswith('rerank_') for r in rows),
         'configuration': load(run / 'arms.json').get(winner, load(run / 'rerank-base.json')['configuration'])})
    print('Locked dev winner:', winner)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('freeze', 'embed', 'dev', 'lock', 'test'))
    p.add_argument('--run', type=Path)
    p.add_argument('--rerank', action='store_true')
    p.add_argument('--max-api-calls', type=int, default=100)
    a = p.parse_args()
    if a.stage == 'freeze':
        freeze()
    elif a.stage == 'embed':
        asyncio.run(embed(a.run, a.max_api_calls))
    elif a.stage == 'lock':
        lock(a.run)
    else:
        rank(a.run, a.stage, a.rerank)


if __name__ == '__main__':
    main()
