"""Offline, fixed-rewrite R8A hybrid fusion experiment. No network or R7 writes."""
import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import statistics
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from app.retrieval import rank_chunks
from scripts.r7_experiment import rewrite_action, span_scores
from scripts.r5_experiment import interleave

SOURCE = ROOT/'docs/rag/r7-experiments/20260919T161914951306Z'
OUTPUT_ROOT = ROOT/'docs/rag/r8a-experiments'
PROTOCOL = ROOT/'docs/rag/R8A_FUSION_PROTOCOL.md'
ARMS = ('original', 'normalize', 'interleave', 'rrf60', 'vector_a015', 'vector_a030', 'vector_a050')
ALPHAS = {'vector_a015': .15, 'vector_a030': .30, 'vector_a050': .50}
METRICS = ('pre_hit1', 'pre_hit5', 'pre_hit20', 'pre_mrr20')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def verify_snapshot(directory, expected):
    actual = snapshot(directory)
    changed = [key for key in sorted(set(expected) | set(actual)) if expected.get(key) != actual.get(key)]
    if changed:
        raise ValueError('Archived inputs changed: '+', '.join(changed[:10]))
    return len(expected)


def unit(vector):
    value = np.asarray(vector, dtype=np.float64)
    if value.ndim != 1 or not value.size or not np.isfinite(value).all():
        raise ValueError('Expected a nonempty finite vector.')
    norm = np.linalg.norm(value)
    if norm <= 1e-12:
        raise ValueError('Cannot normalize a zero vector.')
    return value/norm


def interpolate(original, rewritten, alpha):
    if not 0 <= alpha <= 1:
        raise ValueError('alpha must be between 0 and 1.')
    left, right = unit(original), unit(rewritten)
    if left.shape != right.shape:
        raise ValueError('Vector dimensions differ.')
    return unit((1-alpha)*left + alpha*right).tolist()


def rrf(left, right, corpus_order, limit=20, k=60):
    if k <= 0 or limit < 1:
        raise ValueError('Invalid RRF parameters.')
    scores, rows = {}, {}
    for ranking in (left[:limit], right[:limit]):
        if len({row['id'] for row in ranking}) != len(ranking):
            raise ValueError('Duplicate ID in one RRF input.')
        for rank, row in enumerate(ranking, 1):
            key = row['id']
            rows[key] = row
            scores[key] = scores.get(key, 0.) + 1/(k+rank)
    order = sorted(scores, key=lambda key: (-scores[key], corpus_order[key]))[:limit]
    return [rows[key] for key in order]


def block_network(*args, **kwargs):
    raise RuntimeError('R8A is offline: network/provider access is forbidden.')


def offline_guard():
    stack = ExitStack()
    for target in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                   'app.providers.ApiProviders', 'scripts.r7_experiment.Remote'):
        stack.enter_context(patch(target, side_effect=block_network))
    return stack


def baseline_parity(query, ranks, actions, expected_candidates, expected_rows, gold):
    for arm, r7_arm in (('original', 'original'), ('normalize', 'normalize'), ('interleave', 'dual')):
        key = query['id']+':'+r7_arm
        expected = expected_candidates[key]
        if [row['id'] for row in ranks[arm]] != expected['ids'] or actions[arm] != expected['action']:
            raise ValueError('R7 candidate/action parity failed: '+key)
        scores = span_scores(ranks[arm], gold[query['id']]) if query['level'] != 'L4' else dict.fromkeys(METRICS)
        if any(scores[name] != expected_rows[key][name] for name in METRICS):
            raise ValueError('R7 metric parity failed: '+key)


def csv_write(path, rows):
    if not rows:
        raise ValueError('No CSV rows.')
    with Path(path).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    result = []
    for split in ('dev', 'test'):
        for level, language in [('all', 'all')] + [(x, 'all') for x in ('L0', 'L1', 'L2', 'L3')] + [('all', x) for x in ('en', 'zh')]:
            for arm in ARMS:
                selected = [r for r in rows if r['split'] == split and r['arm'] == arm
                            and (level == 'all' or r['level'] == level)
                            and (language == 'all' or r['language'] == language)]
                result.append(dict(split=split, level=level, language=language, arm=arm, n=len(selected),
                                   **{metric: statistics.mean(r[metric] for r in selected) for metric in METRICS}))
    return result


def changes(rows):
    originals = {r['query_id']: r for r in rows if r['arm'] == 'original'}
    result = []
    for row in rows:
        if row['arm'] == 'original':
            continue
        old = originals[row['query_id']]
        delta = row['pre_mrr20']-old['pre_mrr20']
        result.append({k: row[k] for k in ('query_id', 'family_id', 'split', 'level', 'language', 'arm')} |
                      dict(original_mrr20=old['pre_mrr20'], candidate_mrr20=row['pre_mrr20'], delta_mrr20=delta,
                           outcome='win' if delta > 1e-12 else 'loss' if delta < -1e-12 else 'tie'))
    return result


def render_report(output, summary, changes_rows, verification):
    find = lambda split, level, arm: next(r for r in summary if r['split'] == split and r['level'] == level and r['language'] == 'all' and r['arm'] == arm)
    lines = ['# R8A：固定改写文本的融合消融结果', '',
             '本轮为 R7 之后的**离线探索性实验**。原 dev/test 划分仅供延续观察，结果已经暴露，不能称为新的独立测试。未修改生产默认策略。', '',
             '复用 120 条双语输入，其中 L0–L3 的 96 条评价检索；24 条 L4 歧义输入排除，不对隐藏意图打分。语料 219 份文档、380 个切片，标签由 AI 辅助形成，非教师人工金标。', '',
             '## 原 test 分组：首阶段排序', '',
             'MRR@20 越高表示首个完整证据片段越靠前。各档 16 条，总体 64 条；表述来自 8 个信息需求，不能把 64 当作独立主题。', '',
             '| 档位 | 原文 | 归一化 | 交替 | RRF60 | 向量 α=.15 | 向量 α=.30 | 向量 α=.50 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for level in ('L0', 'L1', 'L2', 'L3', 'all'):
        lines.append('| '+level+' | '+' | '.join(f"{find('test', level, arm)['pre_mrr20']:.6f}" for arm in ARMS)+' |')
    lines += ['', '## 首阶段命中与逐题变化', '', '| 策略 | Hit@1 | Hit@5 | Hit@20 | MRR 改善/持平/受损 |', '|---|---:|---:|---:|---:|']
    for arm in ARMS:
        row = find('test', 'all', arm)
        counts = Counter(r['outcome'] for r in changes_rows if r['split'] == 'test' and r['arm'] == arm)
        movement = '参照' if arm == 'original' else f"{counts['win']}/{counts['tie']}/{counts['loss']}"
        lines.append(f"| {arm} | {row['pre_hit1']:.6f} | {row['pre_hit5']:.6f} | {row['pre_hit20']:.6f} | {movement} |")
    lines += ['', '## 原 dev 分组', '', '| 策略 | Hit@5 | MRR@20 |', '|---|---:|---:|']
    for arm in ARMS:
        row = find('dev', 'all', arm)
        lines.append(f"| {arm} | {row['pre_hit5']:.6f} | {row['pre_mrr20']:.6f} |")
    lines += ['', '## 方法与限制', '',
              '- RRF60 融合原文/归一化两份 Top20，缺席路径贡献为零；向量 α 是归一化改写的权重，先各自归一化再插值。向量融合的词汇查询始终使用原文。',
              '- 全部策略最终最多 20 候选；RRF 和交替需要两次检索，两份结果合并前最多 40，计算量并不等同于单路。内部 dense 和 lexical 各最多 20，再融合输出 20。',
              '- 本轮仅比较首阶段。没有重排、上下文组装或生成调用，不能推断最终答案质量、端到端延迟或整套系统收益。',
              '- 原文/归一化/交替三个基线对全部 120 条输入的候选、动作、首阶段指标均与 R7 相同；R7 dual 对应本轮 interleave。',
              '- 不重新选择提示词或向量权重，不依据已经暴露的 test 选生产冠军；归一化的语义风险仍然存在，融合无法自动保证改写忠实。',
              '- 新 API 请求 0，新增 API 费用 0 美元。复用的改写和向量存在历史获取成本，不能称为线上免费。',
              f"- 原 R7 目录 {verification['original_file_count']} 个文件运行前后 SHA256 一致；网络连接及 Provider 构造已禁止。", '',
              '## 复现与文件', '',
              f"归档目录：`{output.relative_to(ROOT)}`。", '',
              '在仓库根目录运行 `.venv/bin/python scripts/r8_fusion.py`。每次写入新时间戳目录，不覆盖本轮或 R7。', '',
              '`freeze.json` 保存原始输入、代码和协议哈希；`protocol.md` / `r8_fusion.py` 是首次新排序前冻结的副本；`per-query.json` / `candidates.json` 保存逐题结果；`metrics.csv` / `changes.csv` / `changes-summary.csv` 保存全部分组与变化；`verification.json` 保存基线一致性、网络隔离和原档案未变证据。', '']
    return '\n'.join(lines)


def run(source=SOURCE, output=None):
    source = source.resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (output or OUTPUT_ROOT/stamp).resolve()
    if OUTPUT_ROOT.resolve() not in output.parents or source == output or source in output.parents:
        raise ValueError('Output must be a new subdirectory of the R8A experiment directory.')
    output.mkdir(parents=True, exist_ok=False)
    files = snapshot(source)
    code_paths = [Path(__file__), PROTOCOL, ROOT/'app/retrieval.py', ROOT/'scripts/r7_experiment.py',
                  ROOT/'scripts/r5_experiment.py', ROOT/'scripts/chunk_experiment.py']
    code_hashes = {str(p.relative_to(ROOT)): sha(p) for p in code_paths}
    write(output/'freeze.json', dict(schema='r8a-offline-fusion-v1', frozen_at=datetime.now(timezone.utc).isoformat(),
                                    source=str(source), original_file_hashes=files, code_hashes=code_hashes,
                                    arms=ARMS, alphas=ALPHAS, rrf_k=60, candidate_k=20, new_api_calls=0,
                                    status='exploratory_r7_already_seen', vector_lexical_query='original'))
    shutil.copyfile(__file__, output/'r8_fusion.py')
    shutil.copyfile(PROTOCOL, output/'protocol.md')
    write(output/'environment.json', dict(python=sys.version, platform=platform.platform(), numpy=np.__version__))
    # All new rankings occur only after the input/code/protocol freeze is on disk.
    with offline_guard():
        data, rewrites = read(source/'dataset.json'), read(source/'rewrites.json')
        gold, qvec = read(source/'gold-spans.json'), read(source/'query-embeddings.json')
        manifest = read(source/'document-vector-manifest.json')
        if sha(source/'document-vectors.npz') != manifest['sha256']:
            raise ValueError('R7 document vector signature mismatch.')
        with np.load(source/'document-vectors.npz', allow_pickle=False) as archive:
            vectors = dict(zip(archive['keys'].tolist(), archive['vectors']))
        chunks = [dict(c, vector=vectors[hashlib.sha256(c['title_text'].encode()).hexdigest()].tolist()) for c in read(source/'chunks.json')]
        corpus_order = {c['id']: n for n, c in enumerate(chunks)}
        expected_candidates, expected_rows = {}, {}
        for split in ('dev', 'test'):
            expected_candidates.update(read(source/f'{split}-candidates.json'))
            expected_rows.update({r['query_id']+':'+r['arm']: r for r in read(source/f'{split}-pre-rows.json')})
        response_cache = {}

        def vector_for(qid, arm):
            record = qvec.get(qid+':'+arm)
            if not record or record.get('status') != 'succeeded':
                return None
            name = record['response_file']
            if name not in response_cache:
                response_cache[name] = read(source/name)
            return response_cache[name]['result'][record['vector_index']]

        def retrieve(text, vector):
            return rank_chunks(chunks, text, vector, strategy='hybrid_dense_lexical_v1', top_k=20, candidate_k=20, metadata_weight=0.)

        rows, candidates, excluded = [], {}, []
        for q in data['queries']:
            qid = q['id']
            original_vector, normalized_vector = vector_for(qid, 'original'), vector_for(qid, 'normalize')
            original = retrieve(q['text'], original_vector) if original_vector is not None else []
            action = rewrite_action(rewrites[qid+':normalize'])
            if action == 'retrieve' and normalized_vector is None:
                action = 'fallback'
            normalized = (retrieve(rewrites[qid+':normalize']['result']['query'], normalized_vector) if action == 'retrieve'
                          else [] if action == 'clarify' else original)
            ranks = dict(original=original, normalize=normalized,
                         interleave=[] if action == 'clarify' else interleave(original, normalized, 20))
            actions = dict(original='retrieve' if original_vector is not None else 'fallback', normalize=action, interleave=action)
            baseline_parity(q, ranks, actions, expected_candidates, expected_rows, gold)
            if q['level'] == 'L4':
                excluded.append(dict(query_id=qid, split=q['split'], reason='ambiguous_input_not_scored_against_hidden_intent'))
                continue
            ranks['rrf60'] = [] if action == 'clarify' else rrf(original, normalized, corpus_order)
            for arm, alpha in ALPHAS.items():
                ranks[arm] = [] if action == 'clarify' else original if action == 'fallback' else retrieve(q['text'], interpolate(original_vector, normalized_vector, alpha))
            for arm in ARMS:
                selected = ranks[arm]
                if len(selected) > 20 or len({r['id'] for r in selected}) != len(selected):
                    raise ValueError('Candidate budget/uniqueness violated.')
                candidates[qid+':'+arm] = [c['id'] for c in selected]
                rows.append(dict(query_id=qid, family_id=q['family_id'], split=q['split'], level=q['level'], language=q['language'],
                                 arm=arm, action=actions['original'] if arm == 'original' else action, **span_scores(selected, gold[qid])))
            print('Ranked '+qid, flush=True)
        verify_snapshot(source, files)
        if any(sha(ROOT/name) != digest for name, digest in code_hashes.items()):
            raise ValueError('Frozen code/protocol changed during experiment.')
    verification = dict(status='passed', baseline_parity_rows=len(data['queries'])*3, baseline_parity_fields=['candidate_ids', 'action', *METRICS],
                        quality_rows=len(rows), excluded_queries=len(excluded), original_file_count=len(files),
                        original_files_unchanged=True, network_connections_blocked=True, new_api_calls=0, new_api_cost_usd=0,
                        candidate_max=max(map(len, candidates.values())), completed_at=datetime.now(timezone.utc).isoformat())
    summary, changed = summarize(rows), changes(rows)
    change_summary = []
    for split in ('dev', 'test'):
        for level in ('all', 'L0', 'L1', 'L2', 'L3'):
            for arm in ARMS[1:]:
                selected = [r for r in changed if r['split'] == split and r['arm'] == arm and (level == 'all' or r['level'] == level)]
                counts = Counter(r['outcome'] for r in selected)
                change_summary.append(dict(split=split, level=level, arm=arm, n=len(selected), wins=counts['win'], ties=counts['tie'], losses=counts['loss'], mean_delta_mrr20=statistics.mean(r['delta_mrr20'] for r in selected)))
    for name, value in [('verification', verification), ('candidates', candidates), ('per-query', rows), ('excluded', excluded), ('metrics', summary)]:
        write(output/(name+'.json'), value)
    csv_write(output/'metrics.csv', summary)
    csv_write(output/'changes.csv', changed)
    csv_write(output/'changes-summary.csv', change_summary)
    (output/'report.md').write_text(render_report(output, summary, changed, verification), encoding='utf-8')
    print(json.dumps(dict(output=str(output), verification=verification), ensure_ascii=False))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    run(output=args.output)
