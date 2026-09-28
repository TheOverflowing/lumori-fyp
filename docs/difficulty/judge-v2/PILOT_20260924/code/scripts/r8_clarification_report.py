"""Offline descriptive R8B statistics; never invokes providers."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.r5_experiment import load, save, sha
from scripts.r7_report import clustered_interval
from scripts.r8_clarification import ARMS, SOURCE, successful

METRICS = ('pre_hit1', 'pre_hit5', 'pre_hit20', 'pre_mrr20')


def mean(rows, key):
    return statistics.mean(r[key] for r in rows) if rows else None


def summarize(rows):
    output = []
    for split in ('dev', 'test'):
        for clarity in ('sufficient', 'underspecified'):
            for language in ('all', 'en', 'zh'):
                for style in ('all', 'formal', 'colloquial'):
                    for arm in ARMS:
                        subset = [r for r in rows if r['split']==split and r['clarity']==clarity and r['arm']==arm
                                  and (language=='all' or r['language']==language) and (style=='all' or r['style']==style)]
                        if not subset:
                            continue
                        output.append(dict(split=split, clarity=clarity, language=language, style=style, arm=arm,
                            n=len(subset), families=len({r['family_id'] for r in subset}),
                            **{m: mean(subset, m) for m in METRICS},
                            asked=sum(r['asked'] for r in subset), resolved=sum(r['resolved'] for r in subset),
                            unknown=sum(r['unknown'] for r in subset), fallback=sum(r['fallback'] for r in subset),
                            embedding_failed=sum(r['embedding_failed'] for r in subset)))
    return output


def compare(rows):
    comparisons = []
    for split in ('dev', 'test'):
        for clarity in ('sufficient', 'underspecified'):
            subset = [r for r in rows if r['split']==split and r['clarity']==clarity]
            for baseline, arm in (('original','normalize'), ('original','selective'), ('normalize','selective')):
                left = {r['query_id']: r for r in subset if r['arm']==baseline}
                right = {r['query_id']: r for r in subset if r['arm']==arm}
                if set(left) != set(right) or not left:
                    raise ValueError('Incomplete pairing')
                for metric in METRICS:
                    groups = defaultdict(list)
                    for key in left:
                        groups[left[key]['component']].append(right[key][metric] - left[key][metric])
                    delta = [v for values in groups.values() for v in values]
                    comparisons.append(dict(split=split, clarity=clarity, baseline=baseline, arm=arm, metric=metric,
                        gains=sum(x>0 for x in delta), losses=sum(x<0 for x in delta), ties=sum(x==0 for x in delta),
                        **clustered_interval(groups)))
    return comparisons


def csv_file(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit_projection(run):
    inputs, results = load(run/'role-inputs.json'), load(run/'interactions.json')
    general, support = [], []
    for key in sorted(results):
        role = key.rsplit(':',1)[1]
        r = results[key]
        row = dict(key=key, role=role, request={k:v for k,v in inputs[key].items() if k!='intent_profile'},
                   status=r['status'], result=r.get('result'), visible_output=r.get('visible_output'))
        if role == 'reply':
            support.append(dict(row, intent_profile=inputs[key]['intent_profile']))
        else:
            general.append(row)
    save(run/'query-only-audit-inputs.json', general)
    save(run/'reply-support-audit-inputs.json', support)


def costs(run):
    calls = load(run/'calls.json')
    roles = load(run/'interactions.json')
    result = {'actual_http_attempts':len(calls), 'by_capability':{}, 'by_text_role':{}}
    for capability in ('text','embedding','rerank'):
        items = [r for r in calls.values() if r['capability']==capability]
        result['by_capability'][capability] = dict(attempts=len(items),
            logical_requests=len({r['logical_key'] for r in items}),
            status_counts=dict(Counter(r['status'] for r in items)),
            http_status_counts=dict(Counter(str(r.get('http_status','unavailable')) for r in items)),
            known_cost_usd=sum(r.get('usage',{}).get('cost',0) for r in items),
            unknown_cost_attempts=sum('cost' not in r.get('usage',{}) for r in items),
            total_tokens=sum(r.get('usage',{}).get('total_tokens',0) for r in items),
            missing_total_tokens=sum('total_tokens' not in r.get('usage',{}) for r in items),
            returned_models=sorted({r['model'] for r in items if 'model' in r}))
    for role in ('normalize','selective','reply','resolve'):
        logical = {v['logical_key'] for k,v in roles.items() if k.endswith(':'+role)}
        items = [r for r in calls.values() if r['logical_key'] in logical]
        result['by_text_role'][role] = dict(logical_requests=len(logical),attempts=len(items),
            total_tokens=sum(r.get('usage',{}).get('total_tokens',0) for r in items),
            simulation_only=role=='reply')
    return result


def report(run):
    rows = load(run/'per-query.json')
    queries = load(run/'dataset.json')['queries']
    assert len(rows)==len(queries)*len(ARMS)==192
    assert {(r['query_id'],r['arm']) for r in rows}=={(q['id'],a) for q in queries for a in ARMS}
    for row in rows:
        for key in METRICS:
            assert 0 <= row[key] <= 1
        assert row['score_interpretation'] == ('unambiguous_evidence' if row['clarity']=='sufficient' else 'target_conditioned_alignment')
    summary, intervals, usage = summarize(rows), compare(rows), costs(run)
    save(run/'summary.json',summary)
    save(run/'paired-intervals.json',intervals)
    save(run/'costs.json',usage)
    csv_file(run/'metrics.csv',summary)
    csv_file(run/'paired-intervals.csv',intervals)
    audit_projection(run)
    frozen = load(run/'freeze.json')
    changed = [n for n,h in frozen['source_files'].items() if not (SOURCE/n).exists() or sha((SOURCE/n).read_bytes())!=h]
    save(run/'source-integrity.json',{'source_files_checked':len(frozen['source_files']), 'changed':changed,'passed':not changed})
    if changed:
        raise ValueError('Source archive changed')
    lines = ['# R8B 自动统计：选择性追问与首阶段检索', '',
             '64条AI构造查询、8个新需求，已见教材；没有真实学习者、教师金标、重排或答案生成。',
             '所有追问、unknown、未解决和回退均保留分母。下面两类指标分开，不能合成一个正确率。','']
    for split in ('dev','test'):
        lines += ['## '+split,'','| 输入 | 策略 | n | Hit@5 | MRR@20 | 追问 | resolved | unknown | 回退 |',
                  '|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for r in summary:
            if r['split']==split and r['language']==r['style']=='all':
                lines.append(f"| {r['clarity']} | {r['arm']} | {r['n']} | {r['pre_hit5']:.4f} | {r['pre_mrr20']:.4f} | {r['asked']} | {r['resolved']} | {r['unknown']} | {r['fallback']} |")
        lines += ['','underspecified 表示指定模拟用户意图下的证据匹配，不把其他合理解释判成错误。','']
    lines += ['## test 配对差值','','| 输入 | 比较 | 指标 | 差值 | 95%区间 | 改善/退步/持平 |','|---|---|---|---:|---|---|']
    for r in intervals:
        if r['split']=='test' and r['metric'] in ('pre_hit5','pre_mrr20'):
            lines.append(f"| {r['clarity']} | {r['arm']} − {r['baseline']} | {r['metric']} | {r['difference']:+.4f} | [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] | {r['gains']}/{r['losses']}/{r['ties']} |")
    lines += ['','按文档分量聚类，2000次bootstrap，种子20260920。小样本探索，没有多重校正。',
              '', '## 调用与计费', '', '| 能力 | 逻辑请求 | HTTP尝试 | 已知美元 | 金额未知尝试 | tokens |',
              '|---|---:|---:|---:|---:|---:|']
    for cap,r in usage['by_capability'].items():
        lines.append(f"| {cap} | {r['logical_requests']} | {r['attempts']} | {r['known_cost_usd']:.8f} | {r['unknown_cost_attempts']} | {r['total_tokens']} |")
    lines += ['', '模拟用户reply角色的调用单列于costs.json；它是实验开销，不是产品中真人回答的模型成本。未知金额不等于零费用。',
              '', '语义、回复支持与追问必要性须结合独立AI审阅；本自动统计不宣布上线或普遍最优。']
    (run/'report.md').write_text('\n'.join(lines)+'\n')
    print(run/'report.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args()
    if args.audit_only:
        audit_projection(args.run)
    else:
        report(args.run)
