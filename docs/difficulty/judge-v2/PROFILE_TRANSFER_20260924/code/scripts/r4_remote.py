"""Prospective R4 extension: real OpenRouter Qwen8B reranking, bounded cost/calls."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from app.config import Settings
from app.providers import safe_usage
from scripts.r4_experiment import (load, save, sha, canonical, verify, context_rows, summarize,
                                  ARMS, TokenCounter)
from scripts.rag_experiment import write_csv

MODEL = 'qwen/qwen3-reranker-8b'


def prepare(run):
    assert not (run / 'selection-lock.json').exists() and not (run / 'test-per-query.json').exists()
    local = load(run / 'dev-rerank-scores.json') if (run / 'dev-rerank-scores.json').exists() else {}
    note = f'''# R4 协议补充 2：加入可用的 OpenRouter Qwen8B 专用重排

记录时间：{datetime.now(timezone.utc).isoformat()}。本地 dev 重排已完成 {len(local)}/184；尚未汇总其质量，尚无选择锁和 test 排名。

发现并真实探测 OpenRouter /api/v1/rerank 支持 qwen/qwen3-reranker-8b。首次公共示例请求 HTTP 200；记录见 openrouter-rerank-probe.json。官方参考：https://openrouter.ai/qwen/qwen3-reranker-8b 与 https://openrouter.ai/docs/api/api-reference/rerank/create-rerank （文档搜索可见，正文抓取曾 404，以真实请求验证为准）。

新增 api8b_none、api8b_parent 两组，共用原 dev 选出的 token_hybrid Top20 候选。同一原始 query、标题编码文档、top_n=全部候选；使用服务默认重排提示，接口不提供本地版本的自定义指令参数，因此比较的是完整 API 方案而不是纯参数规模消融。返回 relevance_score 按文档 index 映射；保留实际服务模型、provider、用量与耗时。不把 0–1 分数当校准正确率。

dev 完整运行 184 请求，最多并发 2、单次超时 60 秒；无自动重试。失败的请求保留失败记录，主要操作指标按空证据/0 命中计；不能只在成功子集计算主成绩。若 API 方案最终胜出，才在 test 运行 168 请求。总计最多 352 个数据集请求及 1 个探测请求，额外最多 1 USD；按已公开 0.20 USD/百万 token 估计，单请求预留 0.01 USD，逐次核对真实 usage.cost，未知计费停止批量运行。

仍按原 dev 规则选择：预算 Hit、MRR、无重排、较少上下文、预定顺序。顺序为原 12 组、本地 rerank_none、rerank_parent、api8b_none、api8b_parent。新的 API 候选不能在看到 test 后加入。默认升级门槛、数据、token 预算和 bootstrap 均不改变。

原冻结代码不修改。扩展脚本单独冻结为 remote-extension-code.py，哈希记录于 remote-extension.json；全部原始/补充协议并存。
'''
    (run / 'protocol-amendment-2.md').write_text(note)
    (ROOT / 'docs/rag/R4_PROTOCOL_AMENDMENT_2.md').write_text(note)
    code = Path(__file__).read_bytes()
    (run / 'remote-extension-code.py').write_bytes(code)
    save(run / 'remote-extension.json', {'script_sha256': sha(code), 'model': MODEL,
         'created_at': datetime.now(timezone.utc).isoformat(), 'amendment_sha256': sha(note.encode()),
         'max_usd': 1.0, 'max_dataset_requests': 352, 'max_concurrency': 2})


async def collect(run, split):
    verify(run)
    if sha(Path(__file__).read_bytes()) != load(run / 'remote-extension.json')['script_sha256']:
        raise ValueError('Remote extension changed after registration.')
    if split == 'test' and not load(run / 'selection-lock.json')['selected_arm'].startswith('api8b_'):
        raise ValueError('Only the selected remote model may use held-out inference.')
    requests = load(run / (split + '-rerank-requests.json'))
    target = run / (split + '-api8b-scores.json')
    result = load(target) if target.exists() else {}
    settings = Settings.from_env()
    if settings.embedding.base_url != 'https://openrouter.ai/api/v1':
        raise ValueError('Only the configured OpenRouter origin is authorized for key reuse.')
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(2)
    reserved = 0.0
    total = 0
    spent = load(run / 'openrouter-rerank-probe.json')['usage']['cost']
    for path in run.glob('*-api8b-scores.json'):
        previous = load(path)
        total += len(previous)
        spent += sum(v.get('usage', {}).get('cost', 0) for v in previous.values())
    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
        async def one(key, request):
            nonlocal spent, reserved, total
            async with sem:
                if key in result:
                    if result[key]['request_sha256'] != sha(canonical(request)):
                        raise ValueError('Remote request changed.')
                    return
                async with lock:
                    if total >= 352 or spent + reserved + .01 > 1.0:
                        raise ValueError('Remote rerank budget reached.')
                    reserved += .01
                    total += 1
                began = time.perf_counter()
                record = {'request_sha256': sha(canonical(request)), 'requested_model': MODEL, 'status': 'failed', 'usage': {}}
                try:
                    response = await client.post(settings.embedding.base_url + '/rerank',
                        headers={'Authorization': 'Bearer ' + settings.embedding.api_key},
                        json={'model': MODEL, 'query': request['query'],
                              'documents': [d['text'] for d in request['documents']], 'top_n': len(request['documents'])})
                    record['http_status'] = response.status_code
                    if response.status_code == 200:
                        data = response.json()
                        values = sorted(data['results'], key=lambda r: r['index'])
                        if [r['index'] for r in values] != list(range(len(request['documents']))):
                            raise ValueError('Incomplete or duplicate reranker result indices.')
                        scores = [r['relevance_score'] for r in values]
                        if not all(type(v) in (int, float) and math.isfinite(v) for v in scores):
                            raise ValueError('Invalid reranker scores.')
                        record.update(scores=scores, usage=safe_usage(data.get('usage')))
                        for k in ('model', 'provider'):
                            if isinstance(data.get(k), str) and re.fullmatch('[A-Za-z0-9_:/@.+ -]{1,160}', data[k]):
                                record[k] = data[k]
                        record['status'] = 'succeeded'
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    record['error_type'] = type(exc).__name__
                record['duration_ms'] = (time.perf_counter() - began) * 1000
                async with lock:
                    reserved -= .01
                    spent += record['usage'].get('cost', 0)
                    result[key] = record
                    save(target, result)
                    if len(result) % 10 == 0 or len(result) == 1:
                        print(split, 'API8B', len(result), '/', len(requests), 'cost', round(spent, 5), flush=True)
                if record['status'] == 'succeeded' and 'cost' not in record['usage']:
                    raise ValueError('Unknown real API cost; stop batch.')
        await asyncio.gather(*(one(k, r) for k, r in requests.items()))


def append_metrics(run, split):
    ds, gold, cuts = (load(run / (n + '.json')) for n in ('dataset', 'gold-spans', 'chunks'))
    base = load(run / 'rerank-base.json')
    chunks = {c['id']: c for c in cuts[base['configuration'][0]]}
    parents = {d['id']: d for d in ds['documents']}
    rankings = load(run / (split + '-rankings.json'))
    scores = load(run / (split + '-api8b-scores.json'))
    requests = load(run / (split + '-rerank-requests.json'))
    rows = [r for r in load(run / (split + '-per-query.json')) if not r['arm'].startswith('api8b_')]
    index = {(r['query_id'], r['mode']): r for r in rows if r['arm'] == base['arm']}
    counter = TokenCounter(run / 'tokenizer.json')
    for q in ds['queries']:
        if q['split'] != split:
            continue
        for mode in ('mixed', 'cross'):
            key = q['id'] + ':' + mode
            result = scores[key]
            if result['request_sha256'] != sha(canonical(requests[key])):
                raise ValueError('Scores do not match requests.')
            ranked = [chunks[r['id']] for r in rankings[base['arm'] + ':' + key]]
            if result['status'] == 'succeeded':
                ranked = [ranked[i] for i in sorted(range(len(ranked)), key=lambda i: (-result['scores'][i], i))]
            else:
                ranked = []
            spans = [s for s in gold[q['id']] if mode == 'mixed' or s['language'] != q['language']]
            for policy in ('none', 'parent'):
                arm = 'api8b_' + policy
                rows.append({'arm': arm, 'query_id': q['id'], 'family_id': q['family_id'], 'language': q['language'],
                    'mode': mode, 'split': split, 'ranking_ms': index[(q['id'], mode)]['ranking_ms'],
                    'rerank_ms': result['duration_ms'], 'status': result['status'],
                    **context_rows(ranked, q, spans, parents, counter, policy)})
                rankings[arm + ':' + key] = [{'id': c['id']} for c in ranked]
    save(run / (split + '-per-query.json'), rows)
    save(run / (split + '-rankings.json'), rankings)
    summary = summarize(rows)
    save(run / (split + '-summary.json'), summary)
    write_csv(run / (split + '-metrics.csv'), list(summary[0]), summary)
    for r in summary:
        if r['group'] == 'all' and r['arm'].startswith('api8b_'):
            print(r['arm'], r['budget_hit'], r['mrr5'], r['rerank_ms'])


def lock_selection(run):
    if (run / 'selection-lock.json').exists() or (run / 'test-per-query.json').exists():
        raise ValueError('Cannot select after lock or test exposure.')
    rows = load(run / 'dev-summary.json')
    expected = list(ARMS) + ['rerank_none', 'rerank_parent', 'api8b_none', 'api8b_parent']
    candidates = [r for r in rows if r['group'] == 'all']
    if {r['arm'] for r in candidates} != set(expected):
        raise ValueError('Development comparison is incomplete.')
    winner = max(candidates, key=lambda r: (r['budget_hit'], r['mrr5'],
        -int(r['arm'].startswith(('rerank_', 'api8b_'))), -r['context_tokens'], -expected.index(r['arm'])))['arm']
    save(run / 'selection-lock.json', {'selected_arm': winner, 'basis': 'dev_only_with_prospective_extensions',
         'locked_at': datetime.now(timezone.utc).isoformat(), 'dev_summary_sha256': sha(canonical(rows)),
         'reranker_evaluated': True, 'remote_reranker_evaluated': True,
         'configuration': load(run / 'arms.json').get(winner, load(run / 'rerank-base.json')['configuration'])})
    print('Locked dev winner', winner)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'collect', 'metrics', 'lock'))
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--split', choices=('dev', 'test'), default='dev')
    a = p.parse_args()
    if a.stage == 'prepare': prepare(a.run)
    elif a.stage == 'collect': asyncio.run(collect(a.run, a.split))
    elif a.stage == 'metrics': append_metrics(a.run, a.split)
    else: lock_selection(a.run)
