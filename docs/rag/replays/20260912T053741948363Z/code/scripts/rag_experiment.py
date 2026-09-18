"""Freeze, run and replay RAG retrieval comparisons without text generation.

Default: preflight only. --live: embed the frozen pilot using the configured
provider, then evaluate all predefined strategies. --cache FILE: evaluate offline
using previously saved vectors; no provider credentials are required for replay.
"""
import argparse
import asyncio
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.providers import ApiProviders, ProviderError
from app.rag_evaluation import evaluate_run, compare_runs, validate_dataset
from app.retrieval import STRATEGIES, normalize_vectors, rank_chunks, retrieval_config
from app.store import Store
from scripts.rag_history import refresh_history

DEFAULT_DATASET = ROOT / 'benchmarks/rag/pilot_v1.json'
PROTOCOL = ROOT / 'docs/rag/EXPERIMENT_PROTOCOL.md'
KS = (1, 3, 5, 10)
PARAMETERS = dict(top_k=10, candidate_k=20, rrf_k=60, mmr_lambda=0.7)
INPUT_FORMAT = 'raw_text_v1_no_query_instruction'
CODE_FILES = tuple(str(path.relative_to(ROOT)) for path in sorted((ROOT / 'app').glob('*.py'))) + (
    'scripts/rag_experiment.py', 'scripts/rag_history.py', 'requirements.lock.txt', 'requirements.txt',
    'docs/rag/EXPERIMENT_PROTOCOL.md',
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def embedding_inputs(dataset):
    return {kind: [{key: item[key] for key in ('id', 'text')} for item in dataset[kind]]
            for kind in ('documents', 'queries')}


def input_hash(dataset):
    return digest(encoded({'format': INPUT_FORMAT, 'inputs': embedding_inputs(dataset)}))


def validate_cache(cache, dataset):
    if not isinstance(cache, dict):
        raise ValueError('Embedding cache must be an object.')
    if cache.get('schema_version') != 'rag-embedding-cache-v1' or cache.get('status') != 'complete':
        raise ValueError('Embedding cache must be a complete rag-embedding-cache-v1 record.')
    for field in ('model', 'embedding_signature'):
        if not isinstance(cache.get(field), str) or not cache[field].strip():
            raise ValueError(f'Embedding cache {field} must be recorded as nonempty text.')
    if type(cache.get('dimensions')) is not int or cache['dimensions'] < 1:
        raise ValueError('Embedding cache dimensions must be a positive strict integer.')
    if cache.get('input_sha256') != input_hash(dataset) or cache.get('input_format') != INPUT_FORMAT:
        raise ValueError('Embedding cache inputs or query format do not match the dataset.')
    dimensions = set()
    for kind in ('documents', 'queries'):
        vectors = cache.get(kind)
        if not isinstance(vectors, dict) or set(vectors) != {item['id'] for item in dataset[kind]}:
            raise ValueError('Embedding cache IDs do not cover the exact dataset inputs.')
        matrix = normalize_vectors(list(vectors.values()))
        dimensions.add(matrix.shape[1])
    if len(dimensions) != 1 or cache.get('dimensions') != next(iter(dimensions)):
        raise ValueError('Embedding cache dimensions disagree.')
    if cache.get('source') != 'live_provider':
        raise ValueError('This experiment runner requires recorded provider vectors, not mock vectors.')
    return cache


async def embed_dataset(dataset, settings, run, max_calls):
    """One attempt per batch; partial output and failed calls remain recorded."""
    store = Store(run / 'runtime')
    provider = ApiProviders(replace(settings, max_daily_calls=max_calls), store)
    cache = {'schema_version': 'rag-embedding-cache-v1', 'status': 'started',
             'source': 'live_provider', 'model': settings.embedding.model,
             'embedding_signature': settings.embedding.signature,
             'input_format': INPUT_FORMAT, 'input_sha256': input_hash(dataset),
             'created_at': datetime.now(timezone.utc).isoformat(),
             'documents': {}, 'queries': {}, 'batches': []}
    try:
        for kind, items in embedding_inputs(dataset).items():
            for offset in range(0, len(items), 16):
                batch = items[offset:offset + 16]
                began = time.perf_counter()
                vectors = await provider.embed([item['text'] for item in batch], run.name)
                cache[kind].update({item['id']: vector for item, vector in zip(batch, vectors)})
                cache['batches'].append({'kind': kind, 'ids': [item['id'] for item in batch],
                                         'duration_ms': (time.perf_counter() - began) * 1000})
                write_json(run / 'embedding-cache.partial.json', cache)
                print(f'Embedded {kind}: {min(offset + 16, len(items))}/{len(items)}', flush=True)
        cache['dimensions'] = len(next(iter(cache['documents'].values())))
        cache['status'] = 'complete'
        cache['calls'] = store.calls_for_job(run.name)
        validate_cache(cache, dataset)
        write_json(run / 'embedding-cache.json', cache)
        return cache
    finally:
        write_json(run / 'provider-calls.json', store.calls_for_job(run.name))
        await provider.close()


def csv_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def write_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_cell(row.get(key, '')) for key in fields})


def annotate_export(dataset, path):
    """An empty review worksheet; generated judgments never become human ratings."""
    rows = []
    for query in dataset['queries']:
        for document in dataset['documents']:
            rows.append({'query_id': query['id'], 'query': query['text'], 'split': query['split'],
                         'document_id': document['id'], 'passage': document['text'],
                         'human_relevance_0_1_2': '', 'required_evidence_group': '',
                         'reviewer_id': '', 'reviewed_at': '', 'notes': ''})
    write_csv(path, list(rows[0]), rows)


def summary_report(run, dataset, runs, comparisons, cache, api_calls):
    text = ['# RAG 检索实验记录', '', f'运行：{run.name}', '',
            '本轮仅比较检索排序。嵌入模型、查询文本、固定片段、候选语料与评测标注相同。',
            f"标注状态：{dataset['label_status']}。自编、尚未人工复核的数据只支持探索性试验，不能作为论文最终效果证明。", '',
            f"资料片段 {len(dataset['documents'])}；查询 {len(dataset['queries'])}；嵌入模型 {cache['model']}；维度 {cache['dimensions']}。",
            f'本次新增 API 尝试：{api_calls}。各策略复用完全相同的已缓存向量；排序耗时不包含嵌入网络耗时。', '',
            'Recall 按全部相关片段计算；完整证据率要求每个必要证据组至少命中一个片段。不可答查询单独统计，不进入召回均值。', '']
    for split in ('dev', 'test'):
        text.extend([f'## {split} 固定划分', '',
                     '| 策略 | Recall@5 | 完整证据率@5 | nDCG@5 | MRR@5 | 成功查询本地排序中位数 ms |',
                     '|---|---:|---:|---:|---:|---:|'])
        for strategy, result in runs.items():
            group = result['metrics']['groups']['split'].get(split)
            if not group:
                continue
            metrics = group['answerable_metrics']
            def pct(key):
                return 'N/A' if metrics[key] is None else f'{100 * metrics[key]:.2f}%'
            median_ms = result['timing']['median_ms']
            latency = 'N/A' if median_ms is None else f'{median_ms:.3f}'
            text.append(f"| {strategy} | {pct('recall@5')} | {pct('all_evidence@5')} | {pct('ndcg@5')} | {pct('mrr@5')} | {latency} |")
        text.append('')
        for strategy, result in comparisons.items():
            group = result['groups']['split'].get(split)
            if not group:
                continue
            change = group['metrics']['recall@5']
            if change['difference_pp'] is not None:
                text.append(f"- {strategy} 对比 dense_v1：Recall@5 差 {change['difference_pp']:+.2f} 个百分点；配对 bootstrap 95% 区间（百分点）：{change['bootstrap_ci95_pp']}。")
        text.append('')
    text.extend(['## 解释与边界', '',
                 '- dev 与 test 按信息需求分组冻结；本轮全部候选参数在首次排名前确定，没有按 test 结果调参。',
                 '- test 仍属于合成试点集，并非教师确认的正式保留测试集；样本量小且标注可能有偏差。',
                 '- 所有预先声明的策略和退步查询均保留；没有只导出提升案例。相对提升与绝对百分点在 comparisons.json 中分开保存。',
                 '- 未实现检索级拒答阈值。不可答查询的空返回率见 metrics.json；返回片段不代表生成模型一定会编造答案。',
                 '- 排序时间包含本次本地算法、词法统计与归一化开销；不等于用户请求总延迟，纯 BM25 的算法比较也复用缓存向量以保留余弦诊断。',
                 '- 论文正式实验需要真实课程、人工相关性与必要证据标注、更充分的样本，以及独立测试集；这些结果不证明学习效果。', '',
                 '## 文件', '',
                 '- dataset.json / protocol.md：本次冻结的数据与协议。',
                 '- embedding-cache.json：提供商实际返回的向量，支持无需 API 的离线复现。',
                 '- metrics.json / rankings.json / comparisons.json：各方法、分组、逐题指标及全部排名。',
                 '- metrics.csv / per-query.csv / changes.csv：可用于作图、统计和失败分析的表格。',
                 '- annotation-review.csv：空白人工审阅表，没有自动填写人工评分。',
                 '- manifest.json / code/：调用、版本、参数、代码与数据校验值。', ''])
    (run / 'report.md').write_text('\n'.join(text))


def run_rankings(dataset, cache):
    chunks = [document | {'vector': cache['documents'][document['id']]} for document in dataset['documents']]
    all_runs, rankings, failures = {}, {}, []
    for strategy in STRATEGIES:
        selected, timings = {}, []
        for query in dataset['queries']:
            try:
                values = []
                result = None
                # One warmup + three measured local runs. No provider work here.
                for repeat in range(4):
                    began = time.perf_counter()
                    result = rank_chunks(chunks, query['text'], cache['queries'][query['id']], strategy=strategy, **PARAMETERS)
                    if repeat:
                        values.append((time.perf_counter() - began) * 1000)
                selected[query['id']] = result
                timings.append({'query_id': query['id'], 'runs_ms': values, 'median_ms': statistics.median(values)})
            except Exception as exc:
                failures.append({'strategy': strategy, 'query_id': query['id'], 'error_type': type(exc).__name__})
        ids = {qid: [item['id'] for item in rows] for qid, rows in selected.items()}
        metrics = evaluate_run(dataset, ids, ks=KS)
        all_runs[strategy] = {'configuration': retrieval_config(strategy=strategy, **PARAMETERS), 'metrics': metrics,
                              'timing': {'median_ms': statistics.median([item['median_ms'] for item in timings]) if timings else None,
                                         'unit': 'local_ranking_only_including_corpus_preparation', 'per_query': timings}}
        rankings[strategy] = selected
    comparisons = {strategy: compare_runs(dataset,
                        {qid: [item['id'] for item in rows] for qid, rows in rankings['dense_v1'].items()},
                        {qid: [item['id'] for item in rows] for qid, rows in rankings[strategy].items()},
                        k=5, bootstrap_samples=2000, seed=20260912)
                   for strategy in STRATEGIES if strategy != 'dense_v1'}
    return all_runs, rankings, comparisons, failures


def tables(dataset, runs, rankings, comparisons, run):
    summary, per_query, changes = [], [], []
    for strategy, result in runs.items():
        for field, groups in result['metrics']['groups'].items():
            for name, values in groups.items():
                for metric, score in values['answerable_metrics'].items():
                    summary.append({'strategy': strategy, 'group_by': field, 'group': name, 'metric': metric,
                                    'value': score, 'denominators': json.dumps(values['denominators'], sort_keys=True)})
        for query in result['metrics']['per_query']:
            per_query.append({'strategy': strategy, **query})
    # Explicit per-query rankings and before/after numbers are useful for auditing regressions.
    for strategy, comparison in comparisons.items():
        for row in comparison['per_query_deltas']:
            changes.append({'strategy': strategy, **row})
    write_csv(run / 'metrics.csv', list(summary[0]), summary)
    def flatten(rows):
        return [{key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
                 for key, value in row.items()} for row in rows]
    flat = flatten(per_query)
    write_csv(run / 'per-query.csv', sorted({key for row in flat for key in row}), flat)
    flat = flatten(changes)
    write_csv(run / 'changes.csv', sorted({key for row in flat for key in row}), flat)
    annotate_export(dataset, run / 'annotation-review.csv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--cache', type=Path, help='Complete saved embedding-cache.json for a zero-call replay.')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/rag/experiments')
    parser.add_argument('--max-api-calls', type=int, default=6)
    args = parser.parse_args()
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    validate_dataset(dataset)
    expected = sum(math.ceil(len(dataset[kind]) / 16) for kind in ('documents', 'queries'))
    if not args.live and args.cache is None:
        print(json.dumps({'dataset_id': dataset['dataset_id'], 'label_status': dataset['label_status'],
                          'documents': len(dataset['documents']), 'queries': len(dataset['queries']),
                          'expected_embedding_calls': expected, 'strategies': STRATEGIES,
                          'instruction': 'Use --live for the first run or --cache FILE for zero-call replay.'}, ensure_ascii=False))
        return 0
    if args.cache and args.live:
        parser.error('Choose --live or --cache, not both.')
    if args.max_api_calls < 1 or (args.live and expected > args.max_api_calls):
        parser.error('The declared API call cap is too small; no calls were made.')
    cache = validate_cache(json.loads(args.cache.read_bytes()), dataset) if args.cache else None
    settings = Settings.from_env() if args.live else None
    if settings:
        settings.embedding.require('embedding')
    run = args.output_dir / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    (run / 'dataset.json').write_bytes(dataset_bytes)
    (run / 'protocol.md').write_bytes(PROTOCOL.read_bytes())
    hashes = {}
    for name in CODE_FILES:
        raw = (PROTOCOL if name == 'docs/rag/EXPERIMENT_PROTOCOL.md' else ROOT / name).read_bytes()
        target = run / 'code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        hashes[name] = digest(raw)
    manifest = {'schema_version': 'rag-experiment-v1', 'run_id': run.name, 'status': 'started',
                'started_at': datetime.now(timezone.utc).isoformat(), 'dataset_sha256': digest(dataset_bytes),
                'protocol_sha256': digest((run / 'protocol.md').read_bytes()), 'input_sha256': input_hash(dataset),
                'label_status': dataset['label_status'], 'source_code_sha256': hashes,
                'environment': {'python': platform.python_version(), 'platform': platform.platform()},
                'command': [sys.executable, *sys.argv],
                'strategies': {s: retrieval_config(strategy=s, **PARAMETERS) for s in STRATEGIES},
                'ks': KS, 'bootstrap': {'samples': 2000, 'seed': 20260912, 'unit': 'query', 'paired': True},
                'cache_replay': bool(args.cache), 'new_api_attempts': 0,
                'expected_embedding_calls': expected if args.live else 0, 'max_api_calls': args.max_api_calls,
                'runtime_database_isolated': True, 'production_default_changed': False,
                'human_review_performed_by_this_run': False, 'learning_effect_measured': False}
    write_json(run / 'manifest.json', manifest)
    try:
        if cache is None:
            cache = asyncio.run(embed_dataset(dataset, settings, run, args.max_api_calls))
        else:
            write_json(run / 'embedding-cache.json', cache)
            write_json(run / 'provider-calls.json', [])
        manifest['embedding_cache_sha256'] = digest((run / 'embedding-cache.json').read_bytes())
        manifest['embedding_model'] = cache['model']
        manifest['dimensions'] = cache['dimensions']
        calls = json.loads((run / 'provider-calls.json').read_text())
        manifest['new_api_attempts'] = len(calls)
        runs, rankings, comparisons, failures = run_rankings(dataset, cache)
        write_json(run / 'metrics.json', runs)
        write_json(run / 'rankings.json', rankings)
        write_json(run / 'comparisons.json', comparisons)
        write_json(run / 'failures.json', failures)
        tables(dataset, runs, rankings, comparisons, run)
        summary_report(run, dataset, runs, comparisons, cache, len(calls))
        manifest['status'] = 'completed_with_failures' if failures else 'completed'
        manifest['ranking_failures'] = len(failures)
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error_type'] = type(exc).__name__
        if isinstance(exc, ProviderError):
            manifest['safe_error'] = str(exc)
        # No arbitrary exception text: it could contain authored text or API inputs.
        print('Experiment failed; saved manifest and partial evidence.', flush=True)
    finally:
        if (run / 'provider-calls.json').exists():
            try:
                call_evidence = json.loads((run / 'provider-calls.json').read_text())
                if not isinstance(call_evidence, list):
                    raise ValueError('Provider-call evidence must be a list.')
                manifest['new_api_attempts'] = len(call_evidence)
            except (OSError, ValueError, TypeError) as evidence_error:
                # Keep the original failure and still finalize its manifest.
                # An unreadable call log cannot support a claim of zero calls.
                manifest['status'] = 'failed'
                manifest.setdefault('error_type', type(evidence_error).__name__)
                manifest['provider_call_evidence_error_type'] = type(evidence_error).__name__
                manifest['new_api_attempts'] = None
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['artifact_sha256'] = {str(path.relative_to(run)): digest(path.read_bytes())
                                      for path in sorted(run.rglob('*')) if path.is_file()
                                      and path.name != 'manifest.json' and 'runtime' not in path.relative_to(run).parts}
        write_json(run / 'manifest.json', manifest)
        try:
            refresh_history(args.output_dir)
        except Exception as history_error:
            # The convenience index is separate from the frozen experiment.
            print(f'History index refresh failed ({type(history_error).__name__}); run evidence is preserved.', flush=True)
        print(run, flush=True)
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
