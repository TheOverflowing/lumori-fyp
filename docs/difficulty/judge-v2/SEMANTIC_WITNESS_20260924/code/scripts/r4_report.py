"""Report the locked R4 decision without reselecting on held-out results."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scripts.r4_experiment import load, save, sha


def paired_interval(records, winner, metric):
    indexed = {(r['arm'], r['query_id'], r['mode']): r for r in records}
    families = defaultdict(list)
    for r in records:
        if r['arm'] == winner:
            baseline = indexed[('baseline', r['query_id'], r['mode'])]
            families[r['family_id']].append(r[metric] - baseline[metric])
    values = np.array([statistics.mean(v) for _, v in sorted(families.items())])
    rng = np.random.default_rng(20260912)
    samples = rng.choice(values, (2000, len(values)), replace=True).mean(axis=1)
    return {'mean_difference': float(values.mean()), 'ci95': np.percentile(samples, [2.5, 97.5]).tolist(),
            'independent_units': 'bilingual_query_family', 'families': len(values), 'bootstrap_samples': 2000,
            'seed': 20260912}


def report(run):
    lock = load(run / 'selection-lock.json')
    winner = lock['selected_arm']
    dev, test = (load(run / (split + '-summary.json')) for split in ('dev', 'test'))
    records = load(run / 'test-per-query.json')
    groups = {(r['arm'], r['group']): r for r in test}
    base, candidate = (groups[(arm, 'all')] for arm in ('baseline', winner))
    gate = (candidate['budget_hit'] >= base['budget_hit'] and candidate['mrr5'] >= base['mrr5'] - 0.02
            and all(groups[(winner, 'mode:' + mode)]['budget_hit'] >= groups[('baseline', 'mode:' + mode)]['budget_hit']
                    for mode in ('mixed', 'cross')))
    calls = load(run / 'provider-calls.json')
    remote = []
    remote_groups = {}
    for split in ('dev', 'test'):
        path = run / (split + '-api8b-scores.json')
        if path.exists():
            values = list(load(path).values())
            remote.extend(values)
            remote_groups[split] = {'attempts': len(values),
                'failed': sum(v['status'] != 'succeeded' for v in values),
                'p50_ms': float(np.percentile([v['duration_ms'] for v in values], 50)),
                'p95_ms': float(np.percentile([v['duration_ms'] for v in values], 95)),
                'provider_reported_cost': sum(v.get('usage', {}).get('cost', 0) for v in values)}
    probe = load(run / 'openrouter-rerank-probe.json')
    remote_metering = {'by_split': remote_groups, 'dataset_attempts': len(remote), 'probe_attempts': 1,
        'failed': sum(v['status'] != 'succeeded' for v in remote),
        'requests_without_reported_cost': sum('cost' not in v.get('usage', {}) for v in remote),
        'provider_reported_cost': sum(v.get('usage', {}).get('cost', 0) for v in remote) + probe['usage']['cost'],
        'total_tokens': sum(v.get('usage', {}).get('total_tokens', 0) for v in remote) + probe['usage']['total_tokens']}
    selection = {'locked_dev_winner': winner, 'passes_frozen_upgrade_gate': gate,
                 'recommended_arm': winner if gate else 'baseline',
                 'baseline_test': base, 'candidate_test': candidate,
                 'paired_test_intervals': {metric: paired_interval(records, winner, metric) for metric in ('budget_hit', 'mrr5')},
                 'interpretation': 'Selected on previously seen dev, validated once on 42 new bilingual families; not a global or course-gold SOTA claim.',
                 'remote_rerank_calls': remote_metering,
                 'calls': {'attempts': len(calls), 'failed': sum(c['status'] != 'succeeded' for c in calls),
                    'input_tokens': sum(c.get('usage', {}).get('prompt_tokens', c.get('usage', {}).get('input_tokens', 0)) for c in calls),
                    'provider_reported_cost': sum(c.get('usage', {}).get('cost', 0) for c in calls)}}
    save(run / 'decision.json', selection)
    lines = ['# R4 文献策略实测结果', '',
             f'开发集锁定候选：**{winner}**。通过预先规定升级门槛：**{gate}**；本轮建议：**{selection["recommended_arm"]}**。', '',
             '开发集为已见的 46 组双语题（92 条），新保留集为 42 组（84 条）。每题测 mixed 与强制 cross 两个任务，形成 184 / 168 行；这些行不是独立样本。',
             '所有真值继承公开 MLQA 原始人工答案跨度；材料是 CS 相关 Wikipedia，含软件历史，不能称为课程专属人工证据集。',
             '主要预算是 1024 个冻结 Qwen tokenizer token 的原文序列，不含提示词/元数据，不等同于 DeepSeek 计费 token。',
             '表中候选 Hit@20 对 API 失败同样按空列表计 0，是含失败的流程指标；分析首阶段召回上限应查看 token_hybrid 行，不能把云端失败解释为首阶段未召回。',
             '开发集比较 16 个候选配置。按查看保留集前记录的两次协议补充，保留集比较 12 个首阶段配置以及开发集胜出的重排模型的两种上下文策略；未胜出的本地 0.6B 模型没有运行保留集。原协议及补充均保留，见 protocol.md、protocol-amendment-1.md、protocol-amendment-2.md。', '']
    for label, summary in [('开发集（用于选择）', dev), ('新保留集（用于验证，未据此重新选择）', test)]:
        lines += ['## ' + label, '', '| 策略 | 预算跨度 Hit | Top5 跨度 Hit | MRR@5 | 候选 Hit@20 | 平均上下文 token | 平均重排 ms |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for r in summary:
            if r['group'] == 'all':
                lines.append(f"| {r['arm']} | {r['budget_hit']:.2%} | {r['top5_hit']:.2%} | {r['mrr5']:.4f} | {r['candidate_hit20']:.2%} | {r['context_tokens']:.1f} | {r['rerank_ms']:.1f} |")
        lines.append('')
    lines += ['## 新保留集：任务与语言', '', '| 分组 | 策略 | 行数 | 预算跨度 Hit | MRR@5 |', '|---|---|---:|---:|---:|']
    for group in ('mode:mixed', 'mode:cross', 'language:en', 'language:zh'):
        for arm in dict.fromkeys(['baseline', winner]):
            r = groups[(arm, group)]
            lines.append(f"| {group} | {arm} | {r['queries']} | {r['budget_hit']:.2%} | {r['mrr5']:.4f} |")
    lines += ['', '## 差异与成本', '']
    for metric, interval in selection['paired_test_intervals'].items():
        lo, hi = interval['ci95']
        lines.append(f"- {metric}：相对现状差异 {interval['mean_difference'] * 100:+.2f} 个百分点，按 family 配对 bootstrap 的 95% 区间 [{lo * 100:+.2f}, {hi * 100:+.2f}]。")
    metering = selection['calls']
    lines += [f"- 嵌入 API {metering['attempts']} 次尝试，失败 {metering['failed']}；输入 {metering['input_tokens']} token；接口返回 cost 合计 {metering['provider_reported_cost']:.8f}。",
              f"- 嵌入缓存压缩体积 {(run / 'embeddings.npz').stat().st_size / 1024**2:.2f} MiB；模型文件体积及 commit 见 models.json。",
              f"- 云端 8B 重排：数据集 {remote_metering['dataset_attempts']} 次，探测 1 次；失败 {remote_metering['failed']} 次，失败按空证据计 0 命中，没有重试。接口返回 cost 合计 {remote_metering['provider_reported_cost']:.8f} USD，{remote_metering['requests_without_reported_cost']} 次失败没有 cost 字段；此数是已报告金额合计，不是完整账单核对。",
              '- 无重排组的本地排名不包含嵌入网络请求。本地 0.6B 重排计时包含设备同步、分词和 warm 推理；云端 8B 计时包含一次 HTTP 往返与服务推理，均未包含前置 query embedding，不等于完整出题延迟。两种重排使用不同接口默认提示，不是纯参数规模消融。',
              '- 短切分、标题、指令、融合和扩展包含单因素及组合组；不能把组合收益都归因于某一模块。',
              '- 父级补全提高答案跨度覆盖不等于补齐出题所需前提；后续需课程人工必要事实组标签。',
              '- Jina v3.5、真正的 Late Chunking 和多向量检索未在此轮比较，不能把它们描述为已输给本轮候选。', '',
              '冻结协议、代码、模型版本、原文与答案坐标、全部候选排名、重排原始 logits 差、实际上下文、API 日志均保存在本目录。', '']
    for split, values in remote_groups.items():
        lines.append(f"- 云端重排 {split}：p50 {values['p50_ms']:.1f} ms，p95 {values['p95_ms']:.1f} ms，含失败请求；并发 2。")
    (run / 'report.md').write_text('\n'.join(lines))
    save(run / 'artifacts-manifest.json', {str(p.relative_to(run)): sha(p.read_bytes()) for p in sorted(run.rglob('*'))
                                         if p.is_file() and 'runtime' not in p.parts and '__pycache__' not in p.parts
                                         and p.name != 'artifacts-manifest.json'})
    print(json.dumps(selection, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    report(p.parse_args().run)
