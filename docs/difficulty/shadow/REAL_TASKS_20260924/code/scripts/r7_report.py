"""Auditable R7 graded-query report. Reads frozen evidence; never calls APIs."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

ARMS = ('original', 'conservative', 'normalize', 'dual')
LEVELS = ('L0', 'L1', 'L2', 'L3', 'L4')
QUALITY = ('pre_hit1', 'pre_hit5', 'pre_hit20', 'pre_mrr20', 'post_hit', 'post_mrr5')
SEED, SAMPLES = 20260920, 2000


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * p / 100
    left, right = math.floor(pos), math.ceil(pos)
    return values[left] + (values[right] - values[left]) * (pos - left)


def matches(row, level='all', language='all'):
    return (level == 'all' or row['level'] == level) and (language == 'all' or row['language'] == language)


def paired_rows(rows, arm, level='all', language='all'):
    indexed = {}
    for current in ('original', arm):
        selected = [r for r in rows if r['arm'] == current and matches(r, level, language)]
        result = {r['query_id']: r for r in selected}
        if len(result) != len(selected):
            raise ValueError('Duplicate scenario in ' + current)
        indexed[current] = result
    base, candidate = indexed['original'], indexed[arm]
    if not base or set(base) != set(candidate):
        raise ValueError('Incomplete pairing: ' + arm)
    pairs = []
    for key in sorted(base):
        a, b = base[key], candidate[key]
        for field in ('family_id', 'language', 'level', 'split'):
            if a[field] != b[field]:
                raise ValueError('Paired metadata mismatch: ' + key)
        pairs.append((a, b))
    return pairs


def validate_rows(rows, split):
    if {r['arm'] for r in rows} != set(ARMS):
        raise ValueError('Exactly four arms required')
    for arm in ARMS:
        paired_rows(rows, arm)
    for r in rows:
        if r['split'] != split or r['level'] not in LEVELS or r['language'] not in ('en', 'zh'):
            raise ValueError('Invalid split/level/language')
        if r['action'] not in ('retrieve', 'clarify', 'fallback'):
            raise ValueError('Invalid action')
        if r['status'] not in ('succeeded', 'failed', 'skipped_ambiguous', 'clarified'):
            raise ValueError('Invalid status')
        for metric in QUALITY:
            value = r.get(metric)
            if r['level'] == 'L4':
                if value is not None:
                    raise ValueError('L4 quality must be null, never implicit single-intent scores')
            elif not numeric(value) or not 0 <= value <= 1:
                raise ValueError('Missing/non-finite quality: ' + metric)
            elif r['action'] == 'clarify' and value != 0:
                raise ValueError('Unambiguous clarification must retain zero quality in denominator')
        if r['level'] != 'L4' and r['status'] == 'failed' and (r['post_hit'] or r['post_mrr5']):
            raise ValueError('Failed final retrieval must score zero final quality')


def summarize(rows):
    result = []
    for level in ('all',) + LEVELS:
        for language in ('all', 'en', 'zh'):
            for arm in ARMS:
                subset = [r for r in rows if r['arm'] == arm and matches(r, level, language)]
                if not subset:
                    continue
                quality = [r for r in subset if r['level'] != 'L4']
                item = dict(arm=arm, level=level, language=language, input_rows=len(subset), quality_rows=len(quality),
                            failed=sum(r['status'] == 'failed' for r in subset),
                            clarified=sum(r['action'] == 'clarify' for r in subset),
                            rewrite_fallbacks=sum(bool(r.get('rewrite_fallback')) for r in subset),
                            shared_rerank_failed=sum(bool(r.get('shared_rerank_failed')) for r in quality))
                for metric in QUALITY + ('context_tokens',):
                    values = [r[metric] for r in quality if numeric(r.get(metric))]
                    item[metric] = statistics.mean(values) if values else None
                    item[metric + '_missing'] = len(quality) - len(values)
                result.append(item)
    return result


def select_on_dev(rows):
    if any(r['split'] != 'dev' for r in rows):
        raise ValueError('Selection only accepts dev rows')
    validate_rows(rows, 'dev')
    candidates = {r['arm']: r for r in summarize(rows) if r['level'] == r['language'] == 'all'}
    if any(candidates[a]['quality_rows'] == 0 for a in ARMS):
        raise ValueError('No unambiguous dev queries')
    return max(ARMS, key=lambda a: (candidates[a]['pre_hit5'], candidates[a]['pre_mrr20'], -ARMS.index(a)))


def clustered_interval(differences):
    """Resample document components, retaining bilingual and graded query pairs."""
    if not differences:
        raise ValueError('No paired differences')
    groups = [differences[k] for k in sorted(differences)]
    sums, counts = [math.fsum(g) for g in groups], [len(g) for g in groups]
    rng, estimates = random.Random(SEED), []
    for _ in range(SAMPLES):
        draws = [rng.randrange(len(groups)) for _ in groups]
        estimates.append(math.fsum(sums[i] for i in draws) / sum(counts[i] for i in draws))
    return dict(difference=math.fsum(sums) / sum(counts), ci95=[percentile(estimates, 2.5), percentile(estimates, 97.5)],
                clusters=len(groups), paired_queries=sum(counts), seed=SEED, samples=SAMPLES,
                sampling_unit='document_connected_component', estimand='query_weighted_paired_mean_difference')


def interval(rows, component_map, arm, metric, level='all', language='all'):
    groups = defaultdict(list)
    for a, b in paired_rows(rows, arm, level, language):
        if a['level'] == 'L4':
            continue
        if a['family_id'] not in component_map:
            raise ValueError('Missing document component')
        if not numeric(a.get(metric)) or not numeric(b.get(metric)):
            raise ValueError('Missing paired metric')
        groups[str(component_map[a['family_id']])].append(b[metric] - a[metric])
    return dict(arm=arm, baseline='original', metric=metric, level=level, language=language, **clustered_interval(groups))


def degradation(rows, component_map):
    originals = [r for r in rows if r['arm'] == 'original' and r['level'] != 'L4']
    base = {(r['family_id'], r['language']): r for r in originals if r['level'] == 'L0'}
    result = []
    for level in ('L1', 'L2', 'L3'):
        for metric in ('pre_hit5', 'pre_mrr20', 'post_hit'):
            groups = defaultdict(list)
            for row in originals:
                if row['level'] != level:
                    continue
                key = (row['family_id'], row['language'])
                if key not in base or row['family_id'] not in component_map:
                    raise ValueError('Missing L0 or component for paired degradation')
                groups[str(component_map[row['family_id']])].append(base[key][metric] - row[metric])
            if groups:
                result.append(dict(level=level, metric=metric, direction='L0 minus graded; positive means degradation',
                                   **clustered_interval(groups)))
    return result


def clarification(rows):
    result = []
    for arm in ARMS:
        for language in ('all', 'en', 'zh'):
            subset = [r for r in rows if r['arm'] == arm and (language == 'all' or r['language'] == language)]
            if not subset:
                continue
            positive = [r for r in subset if r['level'] == 'L4']
            negative = [r for r in subset if r['level'] != 'L4']
            tp = sum(r['action'] == 'clarify' for r in positive)
            fp = sum(r['action'] == 'clarify' for r in negative)
            precision = tp / (tp + fp) if tp + fp else None
            recall = tp / len(positive) if positive else None
            result.append(dict(arm=arm, language=language, ambiguous=len(positive), unambiguous=len(negative),
                               tp=tp, fp=fp, fn=len(positive)-tp, tn=len(negative)-fp,
                               clarification_rate=recall, false_clarification_rate=fp/len(negative) if negative else None,
                               precision=precision, recall=recall,
                               f1=2*tp/(2*tp+fp+len(positive)-tp) if 2*tp+fp+len(positive)-tp else None,
                               unambiguous_auto_coverage=(len(negative)-fp)/len(negative) if negative else None,
                               module_status='not_implemented' if arm == 'original' else 'action_based_diagnostic'))
    return result


def metering(calls):
    records = list(calls.values()) if isinstance(calls, dict) else list(calls)
    result = {}
    for cap in sorted({r.get('capability', 'unknown') for r in records}):
        selected = [r for r in records if r.get('capability', 'unknown') == cap]
        usage = [r.get('usage') if isinstance(r.get('usage'), dict) else {} for r in selected]
        costs = [u['cost'] for u in usage if numeric(u.get('cost'))]
        durations = [r['duration_ms'] for r in selected if numeric(r.get('duration_ms'))]
        first = [r for r in selected if r.get('attempt', r.get('attempt_index', r.get('attempt_number'))) == 1]
        retries = [r for r in selected if numeric(r.get('attempt', r.get('attempt_index', r.get('attempt_number'))))
                   and r.get('attempt', r.get('attempt_index', r.get('attempt_number'))) > 1]
        groups = defaultdict(list)
        for r in selected:
            key = r.get('request_key') or r.get('logical_key') or r.get('request_id')
            if key is not None:
                groups[str(key)].append(r)
        recovered = 0
        for group in groups.values():
            ordered = sorted(group, key=lambda r: r.get('attempt', r.get('attempt_index', r.get('attempt_number', 1))))
            if len(ordered) > 1 and ordered[0].get('status') != 'succeeded' and ordered[-1].get('status') == 'succeeded':
                recovered += 1
        result[cap] = dict(attempts=len(selected), failures=sum(r.get('status') != 'succeeded' for r in selected),
                           first_attempts=len(first) if first or retries else None,
                           first_attempt_failures=sum(r.get('status') != 'succeeded' for r in first) if first else None,
                           retry_attempts=len(retries) if first or retries else None,
                           recovered_requests=recovered if len(groups) and sum(map(len, groups.values())) == len(selected) else None,
                           known_cost=math.fsum(costs) if costs else None, missing_cost_count=len(selected)-len(costs),
                           http_statuses=dict(Counter(str(r.get('http_status', 'unknown')) for r in selected)),
                           returned_models=dict(Counter(r.get('model') or 'unknown' for r in selected)),
                           p50_ms=percentile(durations, 50), p95_ms=percentile(durations, 95))
        for label, names in (('prompt_tokens', ('prompt_tokens', 'input_tokens')),
                             ('completion_tokens', ('completion_tokens', 'output_tokens')), ('total_tokens', ('total_tokens',))):
            vals = [next((u[k] for k in names if numeric(u.get(k))), None) for u in usage]
            known = [v for v in vals if v is not None]
            result[cap][label + '_known_sum'] = math.fsum(known) if known else None
            result[cap][label + '_missing_count'] = len(vals)-len(known)
    return result


def csv_rows(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, percent=False):
    return '未报告' if value is None else f'{value:.2%}' if percent else f'{value:.4f}'


def report(run):
    run = Path(run)
    dataset, components = load(run/'dataset.json'), load(run/'components.json')
    lock, calls = load(run/'selection-lock.json'), load(run/'calls.json')
    rewrites = load(run/'rewrites.json')
    rows = {split: load(run/f'{split}-per-query.json') for split in ('dev', 'test')}
    queries = {q['id']: q for q in dataset['queries']}
    if len(queries) != len(dataset['queries']):
        raise ValueError('Duplicate dataset query')
    for split, values in rows.items():
        validate_rows(values, split)
        expected = {q['id'] for q in dataset['queries'] if q['split'] == split}
        if {r['query_id'] for r in values} != expected:
            raise ValueError('Dataset/row coverage mismatch')
        for r in values:
            q = queries[r['query_id']]
            if any(r[f] != q[f] for f in ('family_id', 'language', 'level', 'split')):
                raise ValueError('Dataset metadata mismatch')
            if q['requires_clarification'] != (q['level'] == 'L4'):
                raise ValueError('Unexpected ambiguity labels; revise protocol rather than silently recode')
            if q['family_id'] not in components[split]:
                raise ValueError('Missing document component')
    if set(components['dev']) & set(components['test']):
        raise ValueError('Family split leakage')
    if set(components['dev'].values()) & set(components['test'].values()):
        raise ValueError('Document component split leakage')
    winner = select_on_dev(rows['dev'])
    if lock.get('basis') != 'dev_pre_only' or lock.get('selected_arm') != winner:
        raise ValueError('Dev selection lock disagrees with pre-only rule')
    summaries = {split: summarize(values) for split, values in rows.items()}
    intervals = []
    for arm in ARMS[1:]:
        for level in ('all', 'L0', 'L1', 'L2', 'L3'):
            for metric in ('pre_hit5', 'pre_mrr20', 'post_hit'):
                if any(matches(r, level) for r in rows['test']):
                    intervals.append(interval(rows['test'], components['test'], arm, metric, level))
    declines = degradation(rows['test'], components['test'])
    ambiguity = {split: clarification(values) for split, values in rows.items()}
    level_winners = {}
    for level in ('L0', 'L1', 'L2', 'L3'):
        subset = [r for r in summaries['test'] if r['level'] == level and r['language'] == 'all']
        if subset:
            level_winners[level] = max(subset, key=lambda r: (r['pre_hit5'], r['pre_mrr20'], -ARMS.index(r['arm'])))['arm']
    input_files = ['dataset.json', 'components.json', 'selection-lock.json', 'calls.json', 'rewrites.json',
                   'dev-per-query.json', 'test-per-query.json']
    decision = dict(dev_selected=winner, selection_basis='dev_pre_only', selection_lock_verified=True,
                    selection_rule='L0-L3 pooled pre_hit5, then pre_mrr20; exact tie original/conservative/normalize/dual',
                    test_level_winners_descriptive_only=level_winners, product_router_evaluated=False,
                    source_scope='Two textbooks; local document/topic holdout, not unseen-textbook generalization',
                    source_component_counts={s: len(set(components[s].values())) for s in components},
                    summaries=summaries, test_intervals=intervals, original_degradation=declines,
                    clarification=ambiguity, metering=metering(calls), rewrite_records=len(rewrites),
                    input_sha256={n: hashlib.sha256((run/n).read_bytes()).hexdigest() for n in input_files})
    save(run/'decision.json', decision)
    csv_rows(run/'metrics.csv', [dict(split=s, **r) for s, data in summaries.items() for r in data])
    csv_rows(run/'clarification.csv', [dict(split=s, **r) for s, data in ambiguity.items() for r in data])
    csv_rows(run/'paired-intervals.csv', [dict(r, ci95=json.dumps(r['ci95'])) for r in intervals])
    changes = [dict(query_id=a['query_id'], family_id=a['family_id'], language=a['language'], level=a['level'], arm=b['arm'],
                    pre_hit5_delta=b['pre_hit5']-a['pre_hit5'], pre_mrr20_delta=b['pre_mrr20']-a['pre_mrr20'],
                    post_hit_delta=b['post_hit']-a['post_hit'], original_action=a['action'], action=b['action'])
               for arm in ARMS[1:] for a,b in paired_rows(rows['test'], arm) if a['level'] != 'L4']
    csv_rows(run/'test-changes.csv', changes)
    lines = ['# R7：分级口语查询策略对照', '', f'dev 预先选择：**{winner}**；报告只验证选择锁，不用 test 重新选择。', '',
             'L0–L3 为可恢复意图检索实验；L4 是独立的歧义识别轴，质量字段为空，不进入质量均值或策略选择。原文、保守改写、术语归一、双路均保留每臂最多 20 候选。', '',
             '两本教材中的 12 份资料按文档关联分量划分；这是局部文档/主题留出，并非从未见过教材的泛化验证，也不是 8 本独立教材。AI 构造和复核的输入不能称为真实用户日志或人工金标。', '',
             '## 留出结果', '', '| 档位 | 策略 | 质量样本数 | 首阶段 Hit@1 | Hit@5 | Hit@20 | MRR@20 | 最终命中 |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries['test']:
        if r['language'] == 'all' and r['level'] != 'L4':
            lines.append(f"| {r['level']} | {r['arm']} | {r['quality_rows']} | {fmt(r['pre_hit1'],True)} | {fmt(r['pre_hit5'],True)} | {fmt(r['pre_hit20'],True)} | {fmt(r['pre_mrr20'])} | {fmt(r['post_hit'],True)} |")
    lines += ['', '质量的 all 行仅含 L0–L3；失败和不必要澄清按零分留在分母。中英文、档位与交叉分组见 metrics.csv。已知证据 Hit 不等同于穷尽相关性标签下的 Recall。', '',
              '## 配对差异与不确定性', '', '| 档位 | 策略 − 原文 | 指标 | 差值 | 95% 区间 | 文档分量 |', '|---|---|---|---:|---|---:|']
    for r in intervals:
        if r['metric'] == 'pre_hit5':
            lines.append(f"| {r['level']} | {r['arm']} | Hit@5 | {r['difference']*100:+.2f} pp | [{r['ci95'][0]*100:+.2f}, {r['ci95'][1]*100:+.2f}] pp | {r['clusters']} |")
    lines += ['', '按文档关联分量整体配对 bootstrap，2,000 次、种子 20260920；保留同一分量内语言和档位依赖。分量数有限，区间只作探索，无多重比较校正。逐档最高读数只描述，不是利用人工档位运行的产品路由器。', '',
              '## 原文相对清晰问法的下降', '', '| 档位 | 指标 | L0 − 当前档位 |', '|---|---|---:|']
    for r in declines:
        lines.append(f"| {r['level']} | {r['metric']} | {r['difference']:+.4f} |")
    lines += ['', '正数表示口语档位低于同一问题族/语言的 L0；负数表示更高。区间保存在 decision.json。', '',
              '## 歧义与过度澄清', '', '| 策略 | L4 条数 | L4 澄清率 | L0–L3 误澄清率 | Precision | F1 |', '|---|---:|---:|---:|---:|---:|']
    for r in ambiguity['test']:
        if r['language'] == 'all':
            label = r['arm'] + ('（未实现澄清模块）' if r['arm'] == 'original' else '')
            lines.append(f"| {label} | {r['ambiguous']} | {fmt(r['clarification_rate'],True)} | {fmt(r['false_clarification_rate'],True)} | {fmt(r['precision'],True)} | {fmt(r['f1'],True)} |")
    lines += ['', '这是实际 action 的识别诊断，未测量澄清问题质量或用户回复后的成功率；原文策略没有澄清模块。L4 不以隐藏单一原意图命中评价正确性。', '',
              '## 共享评分、服务状态与费用', '',
              '每条 L0–L3 输入对四臂候选并集共享一次重排评分，各臂仅保留自己的候选；同一次评分失败不会制造臂间 503 差异。首阶段主指标不依赖重排。共享评分最多处理 80 文档，不代表生产 20 文档请求或生产端到端延迟；不得把共享耗时除以四当作策略耗时。', '',
              '| 能力 | HTTP attempts | 失败 | 首次失败 | 重试 | 恢复请求 | 已知金额和 | 缺金额 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for cap, r in decision['metering'].items():
        show = lambda x: '未知' if x is None else str(x)
        lines.append(f"| {cap} | {r['attempts']} | {r['failures']} | {show(r['first_attempt_failures'])} | {show(r['retry_attempts'])} | {show(r['recovered_requests'])} | {show(r['known_cost'])} | {r['missing_cost_count']} |")
    lines += ['', '计费缺失为未知，不是免费；已知金额和不代表完整账单。首次尝试、重试及恢复只有在账本提供关联字段时报告，缺字段不猜测。所有 attempt 均计入调用数量。模型、HTTP 状态、token 和调用延迟分位数见 decision.json。', '',
              '## 证据与边界', '',
              '该轮可选择本冻结基准上的候选，不证明普遍最强策略。首阶段排序提升不自动等同于最终证据或题目质量改善。L4 检测与检索质量分别报告；产品默认值没有由本报告自动更改。', '',
              '从冻结输入、逐题记录、calls.json 和选择锁离线重建本报告，不新增 API。保留 R6 负结果；两轮语料和协议不同，不能把它们拼成同一召回率提升曲线。', '']
    (run/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return decision


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    result = report(args.run)
    print(json.dumps({'dev_selected': result['dev_selected'], 'report': str(args.run/'report.md')}, ensure_ascii=False))
