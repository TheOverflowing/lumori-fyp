"""Preflight, run, and replay R3 chunking experiments with human answer offsets."""
import argparse
import asyncio
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.providers import ApiProviders
from app.rag_evaluation import validate_dataset
from app.retrieval import normalize_vectors, rank_chunks
from app.store import Store
from scripts.rag_experiment import validate_cache as validate_r2_cache, write_csv

DEFAULT_DATASET = ROOT / 'benchmarks/rag/external/mlqa/mlqa_cs_en_zh_v1.json'
DEFAULT_REUSE = ROOT / 'docs/rag/experiments/20260912T055718752885Z/embedding-cache.json'
COURSE_MANIFEST = ROOT / 'benchmarks/rag/course_sources/manifest.json'
PROTOCOL = ROOT / 'docs/rag/CHUNKING_PROTOCOL_V1.md'
INPUT_FORMAT = 'raw_text_v1_no_query_instruction'
CUTS = {
    'legacy1200': dict(strategy='legacy_char_v1', max_chars=1200, overlap_chars=120),
    'recursive1200': dict(strategy='recursive_v1', max_chars=1200, overlap_chars=120),
    'recursive800': dict(strategy='recursive_v1', max_chars=800, overlap_chars=80),
}
ARMS = {
    'legacy1200_dense': ('legacy1200', 'dense_v1', 0.0),
    'recursive1200_dense': ('recursive1200', 'dense_v1', 0.0),
    'recursive800_dense': ('recursive800', 'dense_v1', 0.0),
    'recursive1200_hybrid': ('recursive1200', 'hybrid_dense_lexical_v1', 0.0),
    'recursive1200_metadata': ('recursive1200', 'hybrid_dense_lexical_v1', 0.25),
}
CHAR_BUDGET = 6000


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def merged(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def union_length(intervals):
    return sum(end - start for start, end in merged(intervals))


def gold_spans(dataset):
    """Use both original human language annotations, never propagated parent qrels."""
    validate_dataset(dataset)
    parents = {doc['id']: doc['text'] for doc in dataset['documents']}
    families = defaultdict(list)
    for query in dataset['queries']:
        context_id = query.get('original_context_id')
        if context_id not in parents or context_id not in query['relevance']:
            raise ValueError('Missing original answer context metadata.')
        answers = query.get('original_answers')
        if not isinstance(answers, list) or not answers:
            raise ValueError('Missing human answer offsets.')
        for answer in answers:
            start, text = answer.get('answer_start'), answer.get('text')
            if type(start) is not int or start < 0 or not isinstance(text, str) or not text:
                raise ValueError('Invalid human answer span.')
            end = start + len(text)
            if parents[context_id][start:end] != text:
                raise ValueError('Human answer span does not match the frozen original context.')
            span = dict(parent_id=context_id, start=start, end=end, text=text, language=query['language'])
            if span not in families[query['family_id']]:
                families[query['family_id']].append(span)
    result = {}
    for query in dataset['queries']:
        spans = families[query['family_id']]
        if {span['parent_id'] for span in spans} != set(query['relevance']):
            raise ValueError('The family does not provide original offsets for every known context.')
        result[query['id']] = spans
    return result


def make_chunks(documents, config):
    from app.chunking import chunk_pages
    result = []
    for parent in documents:
        raw = parent['text']
        for index, chunk in enumerate(chunk_pages([raw], **config)):
            meta = chunk['metadata']
            start = meta.get('original_page_char_start', meta.get('page_char_start'))
            end = meta.get('original_page_char_end', meta.get('page_char_end'))
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
                raise ValueError('Chunk has invalid absolute source offsets.')
            if raw[start:end] != chunk['text'] or meta['source_page_sha256'] != digest(raw.encode()):
                raise ValueError('Chunk text/source offsets are not an exact frozen original slice.')
            result.append(dict(chunk, id=f"{parent['id']}:{index}:{digest(chunk['text'].encode())[:16]}",
                               parent_id=parent['id'], source_start=start, source_end=end,
                               language=parent.get('language', ''), text_sha256=digest(chunk['text'].encode())))
    if not result:
        raise ValueError('Chunking produced no searchable chunks.')
    return result


def structure_stats(documents, chunks):
    lengths = [len(chunk['text']) for chunk in chunks]
    intervals = defaultdict(list)
    for chunk in chunks:
        intervals[chunk['parent_id']].append((chunk['source_start'], chunk['source_end']))
    indexed, unique = sum(lengths), sum(union_length(items) for items in intervals.values())
    return {
        'source_documents': len(documents), 'source_characters': sum(len(doc['text']) for doc in documents),
        'chunk_count': len(chunks), 'unique_text_count': len({chunk['text_sha256'] for chunk in chunks}),
        'length_min': min(lengths), 'length_median': statistics.median(lengths),
        'length_mean': statistics.mean(lengths), 'length_max': max(lengths),
        'index_characters': indexed, 'unique_source_characters_covered': unique,
        'duplicate_character_ratio': 1 - unique / indexed if indexed else 0,
        'batch16_index_calls_estimate': math.ceil(len(chunks) / 16),
        'chunks_with_headings': sum(bool(chunk['metadata'].get('heading_path')) for chunk in chunks),
        'chunks_with_keywords': sum(bool(chunk['metadata'].get('keywords')) for chunk in chunks),
        'protected_block_split_chunks': sum(bool(chunk['metadata'].get('protected_block_split')) for chunk in chunks),
    }


def load_course_sources(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    documents = []
    for source in manifest['sources']:
        for item in source['downloads']:
            if item['role'] != 'course_text':
                continue
            path = ROOT / item['local_path']
            raw = path.read_bytes()
            if digest(raw) != item['sha256']:
                raise ValueError('Course source checksum differs from the downloaded manifest.')
            documents.append({'id': source['id'] + ':' + item['repository_path'],
                              'text': raw.decode('utf-8'), 'language': source['language'],
                              'source_url': item['url'], 'sha256': item['sha256']})
    return documents


def load_course_snapshot(path):
    documents = json.loads(path.read_text())
    if not isinstance(documents, list) or not documents:
        raise ValueError('Course source snapshot must contain original documents.')
    for document in documents:
        if digest(document['text'].encode()) != document['sha256']:
            raise ValueError('Frozen course snapshot text checksum mismatch.')
    return documents


def all_texts(cuts):
    texts = {}
    for chunks in cuts.values():
        for chunk in chunks:
            texts[chunk['text_sha256']] = chunk['text']
    return dict(sorted(texts.items()))


def input_identity(dataset, texts):
    return digest(encoded({'format': INPUT_FORMAT, 'texts': texts,
                           'queries': [{'id': q['id'], 'text': q['text']} for q in dataset['queries']]}))


def reuse_vectors(dataset, cache):
    validate_r2_cache(cache, dataset)
    result = {}
    for kind in ('documents', 'queries'):
        for item in dataset[kind]:
            result.setdefault(digest(item['text'].encode()), cache[kind][item['id']])
    return result


def vector_hash(cache):
    return digest(encoded({'texts': cache['texts'], 'queries': cache['queries']}))


def validate_chunk_cache(cache, dataset, texts):
    if not isinstance(cache, dict) or cache.get('schema_version') != 'chunk-embedding-cache-v1' or cache.get('status') != 'complete':
        raise ValueError('A complete chunk cache is required.')
    if cache.get('input_format') != INPUT_FORMAT or cache.get('input_sha256') != input_identity(dataset, texts):
        raise ValueError('Chunk cache inputs do not match this frozen experiment.')
    if cache.get('source') != 'live_provider' or any(not isinstance(cache.get(k), str) or not cache[k].strip() for k in ('model', 'embedding_signature')):
        raise ValueError('Chunk cache must record provider/model identity.')
    if type(cache.get('dimensions')) is not int or cache['dimensions'] < 1:
        raise ValueError('Chunk cache dimensions must be a positive integer.')
    if set(cache.get('texts', {})) != set(texts) or set(cache.get('queries', {})) != {q['id'] for q in dataset['queries']}:
        raise ValueError('Chunk cache does not cover the exact query and text inputs.')
    for vectors in (cache['texts'], cache['queries']):
        matrix = normalize_vectors(list(vectors.values()))
        if matrix.shape[1] != cache['dimensions']:
            raise ValueError('Chunk cache vector dimensions disagree.')
    if cache.get('vectors_sha256') != vector_hash(cache):
        raise ValueError('Chunk cache vectors checksum mismatch.')
    return cache


async def embed_missing(dataset, texts, reuse, settings, run, max_calls):
    old_vectors = reuse_vectors(dataset, reuse)
    if settings.embedding.signature != reuse['embedding_signature'] or settings.embedding.model != reuse['model']:
        raise ValueError('Configured embedding identity differs from R2; mixed-model reuse is forbidden.')
    missing = [(key, text) for key, text in texts.items() if key not in old_vectors]
    if math.ceil(len(missing) / 16) > max_calls:
        raise ValueError('New embedding call budget exceeded before starting.')
    cache = {'schema_version': 'chunk-embedding-cache-v1', 'status': 'started', 'source': 'live_provider',
             'model': reuse['model'], 'embedding_signature': reuse['embedding_signature'],
             'dimensions': reuse['dimensions'], 'input_format': INPUT_FORMAT,
             'input_sha256': input_identity(dataset, texts),
             'texts': {key: old_vectors[key] for key in texts if key in old_vectors},
             'queries': reuse['queries'], 'batches': [], 'reused_texts': len(texts) - len(missing)}
    store = Store(run / 'runtime')
    provider = ApiProviders(replace(settings, data_dir=run / 'runtime', max_daily_calls=max_calls), store)
    try:
        for offset in range(0, len(missing), 16):
            batch = missing[offset:offset + 16]
            began = time.perf_counter()
            vectors = await provider.embed([text for _, text in batch], run.name)
            matrix = normalize_vectors(vectors)
            if len(vectors) != len(batch) or matrix.shape[1] != cache['dimensions']:
                raise ValueError('Provider returned incompatible vectors for the frozen cache.')
            cache['texts'].update({key: vector for (key, _), vector in zip(batch, vectors)})
            cache['batches'].append({'text_ids': [key for key, _ in batch], 'duration_ms': (time.perf_counter() - began) * 1000})
            save(run / 'embedding-cache.partial.json', cache)
            print(f'Embedded new chunk texts: {min(offset + 16, len(missing))}/{len(missing)}', flush=True)
        cache['status'] = 'complete'
        cache['vectors_sha256'] = vector_hash(cache)
        validate_chunk_cache(cache, dataset, texts)
        save(run / 'embedding-cache.json', cache)
        return cache
    finally:
        save(run / 'provider-calls.json', store.calls_for_job(run.name))
        await provider.close()


def select_context(ranked, policy):
    if policy == 'top5':
        return ranked[:5]
    if policy != 'chars6000':
        raise ValueError('Unknown context policy.')
    selected, used = [], 0
    for chunk in ranked:
        cost = len(chunk['text'])
        if used + cost > CHAR_BUDGET:
            break
        selected.append(chunk)
        used += cost
    return selected


def span_metrics(selected, spans):
    intervals = defaultdict(list)
    for chunk in selected:
        intervals[chunk['parent_id']].append((chunk['source_start'], chunk['source_end']))
    coverages, single_hits, hits_by_parent = [], [], defaultdict(list)
    for span in spans:
        start, end = span['start'], span['end']
        covered = union_length([(max(a, start), min(b, end)) for a, b in intervals[span['parent_id']]])
        coverage = covered / (end - start)
        coverages.append(coverage)
        hits_by_parent[span['parent_id']].append(coverage == 1)
        single_hits.append(any(a <= start and b >= end for a, b in intervals[span['parent_id']]))
    total = sum(len(chunk['text']) for chunk in selected)
    unique = sum(union_length(items) for items in intervals.values())
    return {
        'known_span_hit': int(any(value == 1 for value in coverages)),
        'single_chunk_span_hit': int(any(single_hits)), 'best_span_coverage': max(coverages),
        'known_context_coverage': sum(any(hits) for hits in hits_by_parent.values()) / len(hits_by_parent),
        'returned_chunks': len(selected), 'returned_characters': total,
        'unique_source_characters': unique,
        'duplicate_character_ratio': 1 - unique / total if total else 0.0,
    }


def run_rankings(dataset, cuts, cache, spans):
    records, rankings, failures = [], {}, []
    for arm, (cut, strategy, weight) in ARMS.items():
        chunks = [dict(chunk, vector=cache['texts'][chunk['text_sha256']]) for chunk in cuts[cut]]
        rankings[arm] = {}
        for query in dataset['queries']:
            began = time.perf_counter()
            try:
                selected = rank_chunks(chunks, query['text'], cache['queries'][query['id']],
                                       strategy=strategy, top_k=len(chunks), candidate_k=max(20, len(chunks)),
                                       rrf_k=60, mmr_lambda=0.7, metadata_weight=weight)
                status = 'succeeded'
            except Exception as exc:
                failures.append({'arm': arm, 'query_id': query['id'], 'error_type': type(exc).__name__})
                selected, status = [], 'failed'
            duration = (time.perf_counter() - began) * 1000
            rankings[arm][query['id']] = [{'id': chunk['id'], 'score': chunk['score']} for chunk in selected]
            for policy in ('top5', 'chars6000'):
                context = select_context(selected, policy)
                metrics = span_metrics(context, spans[query['id']])
                records.append({'arm': arm, 'query_id': query['id'], 'family_id': query['family_id'],
                                'split': query['split'], 'language': query['language'], 'policy': policy,
                                'status': status, 'ranking_ms': duration,
                                'selected_ids': [chunk['id'] for chunk in context], **metrics,
                                'unused_character_budget': CHAR_BUDGET - metrics['returned_characters'] if policy == 'chars6000' else None})
    return records, rankings, failures


METRICS = ('known_span_hit', 'single_chunk_span_hit', 'best_span_coverage', 'known_context_coverage',
           'returned_chunks', 'returned_characters', 'unique_source_characters', 'duplicate_character_ratio')


def summarize(records):
    groups = defaultdict(list)
    for record in records:
        for dimension, value in (('overall', 'all'), ('split', record['split']), ('language', record['language'])):
            groups[(record['arm'], record['policy'], dimension, value)].append(record)
    return [{'arm': arm, 'policy': policy, 'group': dimension, 'value': value,
             'queries': len(rows), 'failed_queries': sum(row['status'] == 'failed' for row in rows),
             **{metric: statistics.mean(row[metric] for row in rows) for metric in METRICS}}
            for (arm, policy, dimension, value), rows in groups.items()]


def report(run, summaries, stats, calls):
    lines = ['# R3 切分探索记录', '', 'MLQA 的 92 条中英文查询已在 R2 使用。本轮是探索性答案跨度覆盖实验，不能作为未见测试集泛化证据。',
             '教材仅报告结构统计，没有人工标签，未计算召回。6000 的预算单位为原文字符，不是模型 token。',
             f'本轮新增嵌入 API 尝试：{calls}；所有组使用相同提供商/模型和原始正文输入。', '']
    for policy in ('top5', 'chars6000'):
        lines += [f'## {policy}', '', '| 组 | 已知span完整命中 | 单块完整命中 | 最佳span字符覆盖 | 唯一原文字符 | 重复字符比例 | 失败查询 |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for row in summaries:
            if row['group'] == 'overall' and row['policy'] == policy:
                lines.append(f"| {row['arm']} | {row['known_span_hit']:.2%} | {row['single_chunk_span_hit']:.2%} | {row['best_span_coverage']:.2%} | {row['unique_source_characters']:.1f} | {row['duplicate_character_ratio']:.2%} | {row['failed_queries']} / {row['queries']} |")
        lines.append('')
    lines += ['## 索引结构', '', '| 材料 | 切分 | 片段数 | 中位长度 | 索引原文字符 | 重复比例 |', '|---|---|---:|---:|---:|---:|']
    for scope, cutstats in stats.items():
        for cut, values in cutstats.items():
            lines.append(f"| {scope} | {cut} | {values['chunk_count']} | {values['length_median']} | {values['index_characters']} | {values['duplicate_character_ratio']:.2%} |")
    lines += ['', '前三个 dense 组是纯切分对照；后两个 hybrid 组是组合探索，metadata 0 与 0.25 构成元数据消融。',
              '已知跨度命中仅说明人工答案原字符串被覆盖，不说明答案全部教学依据齐全。两语言答案可替代，译文查询属于相关 family。',
              '逐题、split、language 的全部结果及失败保留。原文字段、metadata 与偏移见 chunks.json；冻结代码、数据、参数和哈希见 manifest.json。', '']
    (run / 'report.md').write_text('\n'.join(lines))


async def execute(args):
    if type(args.max_api_calls) is not int or args.max_api_calls < 1:
        raise ValueError('API budget must be positive.')
    dataset = json.loads(args.dataset.read_text())
    spans = gold_spans(dataset)
    cuts = {name: make_chunks(dataset['documents'], config) for name, config in CUTS.items()}
    courses = load_course_snapshot(args.course_snapshot) if args.course_snapshot else load_course_sources(args.course_manifest)
    course_cuts = {name: make_chunks(courses, config) for name, config in CUTS.items()}
    stats = {'mlqa': {name: structure_stats(dataset['documents'], chunks) for name, chunks in cuts.items()},
             'course_sources_unlabeled': {name: structure_stats(courses, chunks) for name, chunks in course_cuts.items()}}
    texts = all_texts(cuts)
    reuse, cache = None, None
    if args.cache:
        cache = validate_chunk_cache(json.loads(args.cache.read_text()), dataset, texts)
        missing = []
    else:
        reuse = json.loads(args.reuse_cache.read_text())
        available = reuse_vectors(dataset, reuse)
        missing = [key for key in texts if key not in available]
    preflight = {'queries': len(dataset['queries']), 'parents': len(dataset['documents']), 'course_sources': len(courses),
                 'unique_chunk_texts': len(texts), 'new_texts': len(missing),
                 'new_embedding_calls_required': math.ceil(len(missing) / 16), 'api_budget': args.max_api_calls,
                 'dataset_sha256': digest(args.dataset.read_bytes()), 'input_sha256': input_identity(dataset, texts),
                 'cuts': CUTS, 'arms': ARMS, 'statistics': stats}
    print(json.dumps(preflight, ensure_ascii=False), flush=True)
    if len(missing) > 16 * args.max_api_calls:
        raise ValueError('Required embedding calls exceed budget; nothing was called.')
    if not args.live and not args.cache:
        return preflight
    run = args.output_dir / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 'chunk-experiment-v1', 'status': 'started',
                'started_at': datetime.now(timezone.utc).isoformat(), 'preflight': preflight,
                'cache_replay': bool(args.cache), 'new_api_calls': 0,
                'reuse_cache_sha256': digest(args.reuse_cache.read_bytes()) if reuse else None,
                'replay_cache_sha256': digest(args.cache.read_bytes()) if args.cache else None}
    save(run / 'manifest.json', manifest)
    try:
        save(run / 'dataset.json', dataset)
        save(run / 'course-sources.json', courses)
        save(run / 'chunks.json', cuts)
        save(run / 'course-chunks.json', course_cuts)
        save(run / 'gold-spans.json', spans)
        save(run / 'statistics.json', stats)
        (run / 'protocol.md').write_bytes(PROTOCOL.read_bytes())
        files = [*sorted((ROOT / 'app').glob('*.py')), ROOT / 'scripts/chunk_experiment.py',
                 ROOT / 'scripts/rag_experiment.py', ROOT / 'scripts/rag_history.py',
                 ROOT / 'requirements.txt', ROOT / 'requirements.lock.txt', PROTOCOL]
        manifest['code_sha256'] = {}
        for path in files:
            relative = path.relative_to(ROOT)
            target = run / 'code' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            manifest['code_sha256'][str(relative)] = digest(path.read_bytes())
        if cache is None:
            cache = await embed_missing(dataset, texts, reuse, Settings.from_env(), run, args.max_api_calls)
        else:
            save(run / 'embedding-cache.json', cache)
            save(run / 'provider-calls.json', [])
        records, rankings, failures = run_rankings(dataset, cuts, cache, spans)
        summaries = summarize(records)
        save(run / 'per-query.json', records)
        save(run / 'rankings.json', rankings)
        save(run / 'failures.json', failures)
        save(run / 'metrics.json', {'schema_version': 'chunk-metrics-v1', 'exploratory': True, 'groups': summaries})
        write_csv(run / 'metrics.csv', list(summaries[0]), summaries)
        write_csv(run / 'per-query.csv', list(records[0]), [{**r, 'selected_ids': json.dumps(r['selected_ids'])} for r in records])
        calls = json.loads((run / 'provider-calls.json').read_text())
        report(run, summaries, stats, len(calls))
        manifest['status'] = 'completed_with_failures' if failures else 'completed'
        manifest['failure_count'] = len(failures)
    except Exception as exc:
        manifest['status'], manifest['error_type'] = 'failed', type(exc).__name__
        raise
    finally:
        calls_path = run / 'provider-calls.json'
        if calls_path.exists():
            manifest['new_api_calls'] = len(json.loads(calls_path.read_text()))
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['artifacts_sha256'] = {str(path.relative_to(run)): digest(path.read_bytes())
            for path in sorted(run.rglob('*')) if path.is_file() and 'runtime' not in path.parts and path.name != 'manifest.json'}
        save(run / 'manifest.json', manifest)
        print(f'Experiment {manifest["status"]}: {run}', flush=True)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--course-manifest', type=Path, default=COURSE_MANIFEST)
    parser.add_argument('--course-snapshot', type=Path, help='Use a frozen run/course-sources.json for standalone archived replay.')
    parser.add_argument('--reuse-cache', type=Path, default=DEFAULT_REUSE)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/rag/chunk-experiments')
    parser.add_argument('--max-api-calls', type=int, default=64)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--cache', type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(execute(args))
    except Exception as exc:
        print(f'Chunk experiment stopped: {type(exc).__name__}; inspect preserved manifest.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
