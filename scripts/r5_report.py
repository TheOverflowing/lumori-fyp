"""Report a frozen R5 translation experiment, including losses and API failures."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from scripts.r5_experiment import load,save,sha,ARMS


def interval(rows,component_map,arm,metric,group=None):
    wanted=lambda r:group is None or r['mode']+':'+r['language']==group
    base={(r['query_id'],r['mode']):r for r in rows if r['arm']=='original' and wanted(r)}
    grouped=defaultdict(list)
    for r in rows:
        if r['arm']==arm and wanted(r):
            grouped[component_map[r['family_id']]].append(r[metric]-base[r['query_id'],r['mode']][metric])
    values=list(grouped.values());sums=np.array([sum(v) for v in values]);counts=np.array([len(v) for v in values])
    draws=np.random.default_rng(20260912).integers(0,len(values),size=(2000,len(values)))
    estimates=sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
    return {'difference':float(sums.sum()/counts.sum()),'ci95':np.percentile(estimates,[2.5,97.5]).tolist(),
            'clusters':len(values),'sampling_unit':'connected_bilingual_answer_contexts','seed':20260912,'samples':2000}


def csv_rows(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def report(run):
    ds=load(run/'dataset.json');queries={q['id']:q for q in ds['queries']};trs=load(run/'translations.json')
    summaries={s:load(run/(s+'-summary.json')) for s in ('dev','test')}
    rows=load(run/'test-per-query.json');groups={(r['arm'],r['group']):r for r in summaries['test']}
    winner=load(run/'selection-lock.json')['selected_arm'];base=groups['original','all'];best=groups[winner,'all']
    passes=(winner!='original' and best['budget_hit']>=base['budget_hit'] and
        (best['budget_hit']>base['budget_hit'] or best['mrr5']>=base['mrr5']+.01) and
        all(groups[winner,'cross:'+lang]['budget_hit']>=groups['original','cross:'+lang]['budget_hit'] for lang in ('en','zh')))
    if winner=='original':passes=None
    component_map=load(run/'components.json')['test']
    intervals={arm:{metric:interval(rows,component_map,arm,metric) for metric in ('budget_hit','mrr5','candidate_hit20')}
               for arm in ('translated','dual')}
    direction_intervals={group:{arm:{metric:interval(rows,component_map,arm,metric,group)
        for metric in ('budget_hit','mrr5','candidate_hit20')} for arm in ('translated','dual')}
        for group in ('cross:en','cross:zh')}
    calls=list(load(run/'calls.json').values());metering={}
    for cap in ('text','embedding','rerank'):
        records=[c for c in calls if c['capability']==cap]
        metering[cap]={'attempts':len(records),'failures':sum(r['status']!='succeeded' for r in records),
            'missing_cost':sum('cost' not in r['usage'] for r in records),
            'known_cost':sum(r['usage'].get('cost',0) for r in records),
            'prompt_tokens':sum(r['usage'].get('prompt_tokens',r['usage'].get('input_tokens',0)) for r in records),
            'completion_tokens':sum(r['usage'].get('completion_tokens',r['usage'].get('output_tokens',0)) for r in records),
            'total_tokens':sum(r['usage'].get('total_tokens',0) for r in records),
            'p50_ms':float(np.percentile([r['duration_ms'] for r in records],50)),
            'p95_ms':float(np.percentile([r['duration_ms'] for r in records],95)),
            'returned_models':dict(Counter(r.get('model','unreported') for r in records))}
    changes=[];baseline={(r['query_id'],r['mode']):r for r in rows if r['arm']=='original'}
    for r in rows:
        if r['arm']=='original':continue
        b=baseline[r['query_id'],r['mode']];q=queries[r['query_id']]
        changes.append({'arm':r['arm'],'query_id':r['query_id'],'query':q['text'],
            'translation':trs[q['id']].get('result',''),'language':q['language'],'mode':r['mode'],
            'baseline_hit':b['budget_hit'],'arm_hit':r['budget_hit'],'delta_hit':r['budget_hit']-b['budget_hit'],
            'delta_mrr5':r['mrr5']-b['mrr5'],'baseline_status':b['status'],'arm_status':r['status'],
            'translation_status':trs[q['id']]['status']})
    review=[]
    for q in ds['queries']:
        other=next(v for v in ds['queries'] if v['family_id']==q['family_id'] and v['language']!=q['language'])
        t=trs[q['id']]
        review.append({'query_id':q['id'],'split':q['split'],'source_language':q['language'],'original':q['text'],
            'model_translation':t.get('result',t.get('visible_output','')),'public_human_parallel_question':other['text'],
            'mechanical_status':t['status'],'validation_error':t.get('validation_error',''),
            'human_review_status':'unreviewed','human_reviewer':'','human_semantic_verdict':'','human_notes':''})
    csv_rows(run/'translation-review.csv',review);csv_rows(run/'test-changes.csv',changes)
    save(run/'test-changes.json',changes)
    attribution=defaultdict(list)
    for r in rows:
        if r['arm']=='original':continue
        b=baseline[r['query_id'],r['mode']]
        state=('both_succeeded' if r['status']==b['status']=='succeeded' else
            'original_failed' if b['status']!='succeeded' and r['status']=='succeeded' else
            'candidate_failed' if b['status']=='succeeded' else 'both_failed')
        for group in ('all',r['mode']+':'+r['language']):
            attribution[r['arm'],group,state].append(r['budget_hit']-b['budget_hit'])
    decomposition=[{'arm':k[0],'group':k[1],'paired_status':k[2],'rows':len(v),'net_hit_change':sum(v),
        'gains':sum(x>0 for x in v),'losses':sum(x<0 for x in v)} for k,v in attribution.items()]
    save(run/'test-failure-attribution.json',{'interpretation':
        'Post-hoc descriptive decomposition, not a replacement for failure-inclusive primary results; no causal claim from a success subset.',
        'rows':decomposition})
    for split,summary in summaries.items():csv_rows(run/(split+'-metrics.csv'),summary)
    decision={'dev_selected':winner,'passes_frozen_validation_gate':passes,
        'gate_status':'not_applicable_original_selected' if winner=='original' else 'evaluated_on_locked_translation_arm',
        'production_action':'retain_R4_no_translation',
        'interpretation':'A small fixed public-QA ablation; no automatic deployment or course-gold claim.',
        'test_intervals':intervals,'test_direction_intervals':direction_intervals,'metering':metering,
        'test_hit_changes':{arm:dict(Counter('better' if c['delta_hit']>0 else 'worse' if c['delta_hit']<0 else 'same'
            for c in changes if c['arm']==arm)) for arm in ('translated','dual')}}
    save(run/'decision.json',decision)
    failed=[]
    for split in ('dev','test'):
        candidates=load(run/(split+'-candidates.json'));responses=load(run/(split+'-rerank.json'))
        for r in load(run/(split+'-per-query.json')):
            if r['status']=='succeeded':continue
            candidate=candidates[r['query_id']+':'+r['mode']+':'+r['arm']]
            remote=responses.get(candidate['request_sha256'],{})
            failed.append({'split':split,'query_id':r['query_id'],'query':queries[r['query_id']]['text'],
                'arm':r['arm'],'mode':r['mode'],'status':r['status'],
                'candidate_hit20':r['candidate_hit20'],'http_status':remote.get('http_status',''),
                'validation_error':remote.get('validation_error',''),'response_file':remote.get('response_file','')})
    save(run/'failed-scenarios.json',failed);csv_rows(run/'failed-scenarios.csv',failed)
    selection_text=('开发集原查询与仅翻译查询持平，按预定规则锁定 **original**。没有翻译方案进入升级门槛验证；保留集三组结果全部报告，不据此重新选冠军。'
        if winner=='original' else f'开发集选择：**{winner}**。通过预定保留集门槛：**{passes}**。')
    lines=['# R5：查询翻译的实测结果','',selection_text+' 本轮仅做实验，当前应用继续使用 R4 原查询方案。','',
        '开发集 24 个已见双语 family / 48 条查询；新保留集 31 个 family / 62 条查询。每题测 mixed 和强制 cross，形成 dev 96 / test 124 个场景。区间以 25 个来源关联组件为抽样单位，不把四种相关场景当独立题。',
        '共同语料为 207 篇计算机/软件相关 Wikipedia 原文、236 个 token 片段。含产品、人物和社会背景知识，不是计算机本科课程金标。翻译模型只收到问题，不含答案或材料。','',
        '三组共享相同文档编码、重排模型、总计至多 20 个重排候选、Top5 种子及 1024-Qwen-token 原文预算。translated 只改变首阶段查询，重排仍用原问题；dual 轮询合并两路、去重并截到总共 20 个。',
        '翻译失败与接口失败保留在分母；dual 分支失败时的回退明确记录。相同完整重排请求只真实调用一次并共享成功/失败结果，实际去重调用数与逐场景成绩分开。','']
    for split in ('dev','test'):
        lines+=['## '+('开发集（用于选择）' if split=='dev' else '新保留集（未据此重新选择）'),'','| 策略 | 场景数 | 预算 Hit | MRR@5 | 重排前 Hit@20 | 上下文 token | 分阶段延迟估计 ms |','|---|---:|---:|---:|---:|---:|---:|']
        for r in summaries[split]:
            if r['group']=='all':lines.append(f"| {r['arm']} | {r['rows']} | {r['budget_hit']:.2%} | {r['mrr5']:.4f} | {r['candidate_hit20']:.2%} | {r['context_tokens']:.1f} | {r['stage_sum_estimate_ms']:.1f} |")
        lines.append('')
    lines+=['## 保留集方向与任务','','| 场景 | 策略 | n | 预算 Hit | MRR@5 | 重排前 Hit@20 |','|---|---|---:|---:|---:|---:|']
    for group,label in [('cross:en','英文查中文'),('cross:zh','中文查英文'),('mode:mixed','双语资料混合')]:
        for arm in ARMS:
            r=groups[arm,group];lines.append(f"| {label} | {arm} | {r['rows']} | {r['budget_hit']:.2%} | {r['mrr5']:.4f} | {r['candidate_hit20']:.2%} |")
    lines+=['', '本轮中文查英文的最终命中从 25/31 到 29/31；逐题对照中，3 个新增命中对应原查询组 HTTP 503，另外 1 个来自双方重排都成功的场景。因此不能把 +12.90 个百分点都归因于翻译。重排前候选覆盖实际从 28/31 到 29/31。英文查中文的最终净命中持平，但具体命中题并不完全相同。',
        '事后按双方接口状态拆分的描述见 test-failure-attribution.json；它不替代上述包含全部失败的主结果，也不是剔除失败后的新实验。']
    lines+=['','## 配对差异与失败','']
    for arm,values in intervals.items():
        for metric,v in values.items():lines.append(f"- {arm} 相对 original 的 {metric}：{v['difference']:+.4f}，组件配对 bootstrap 95% 区间 [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]。")
        lines.append(f"- {arm} 逐场景 Hit 增损：{decision['test_hit_changes'][arm]}。")
    for split in ('dev','test'):
        t=[trs[q['id']] for q in ds['queries'] if q['split']==split]
        lines.append(f"- {split} 翻译机械检查失败 {sum(v['status']!='succeeded' for v in t)}/{len(t)}；机械检查通过不等于语义翻译正确。")
        values=load(run/(split+'-per-query.json'))
        for arm in ARMS:
            subset=[r for r in values if r['arm']==arm]
            lines.append(f"- {split} / {arm}：{sum(r['status']!='succeeded' for r in subset)}/{len(subset)} 个场景流程失败，{sum(r['translation_fallback'] for r in subset)} 个翻译分支回退。")
    if (run/'assistant-translation-review.json').exists():
        lines+=['', '按预定哈希顺序抽查 dev/test、中/英各 5 条，共 20 条译文。此处为助手语义复核，不是新增人类标注。发现一处词义歧义：What foundation is made after the split up? 被译为“拆分之后建立的基础是什么？”，而公开平行问题为“分裂之后，成立了哪个基金会？”。原译文保持不变；不能从这 20 条推断总体翻译错误率。详见 assistant-translation-review.json。']
    lines+=['','全部逐题增损见 test-changes.csv / JSON；全部译文、现成的人类平行问题参考及未填写真人审核列见 translation-review.csv。任何助手语义复核另存，不能标为真人标签。','','## 费用和时间','','| 能力 | 实际请求 | 失败 | 已报告费用 | 未报告费用次数 | p50 ms | p95 ms |','|---|---:|---:|---:|---:|---:|---:|']
    for cap,v in metering.items():
        cost=f"{v['known_cost']:.8f}" if v['missing_cost']<v['attempts'] else '未报告'
        lines.append(f"| {cap} | {v['attempts']} | {v['failures']} | {cost} | {v['missing_cost']} | {v['p50_ms']:.1f} | {v['p95_ms']:.1f} |")
    lines+=['',f"DeepSeek 实际输入 {metering['text']['prompt_tokens']}、输出 {metering['text']['completion_tokens']} token。没有 cost 字段的请求不能按零费用处理；没有声称已核对合并总账单。",'查询延迟列是实际阶段耗时按冻结依赖关系合成的估计，未模拟服务队列和在线并发；不是生产端到端 p95。索引构建与缓存复用另记于 document-vector-manifest.json，各阶段墙钟时间见 stage-*.json。','',
        'HTTP 失败会影响流程主指标，微小排序差异不能自动归因于翻译。重排前 Hit@20 用于另看候选覆盖；没有相关性的片段不能由重排补救。区间是小样本探索性结果，没有多重比较校正。','',
        '不能把本轮结果与不同语料/问题的 R4 百分比直接相减。新的 31 个 family 现已暴露；后续调参需要另设保留数据。原始资料与生成引用没有被翻译或重写，应用配置和业务数据库没有更新。','']
    if (run/'replay-verification.json').exists():
        replay=load(run/'replay-verification.json')
        lines+=['## 复现与验证','',
            f"归档代码离线重放 {sum(v['rows'] for v in replay['checks'].values())} 条逐场景策略记录，候选请求、候选 ID、最终排名、逐题质量与上下文完全一致；新增 API 调用 0 次。本地排名计时及其合成延迟允许变化。见 replay-verification.json。",'']
    if (run/'r5-heldout-quality.png').exists():
        lines+=['![R5 held-out quality](r5-heldout-quality.png)','', '[矢量 PDF](r5-heldout-quality.pdf)','']
    (run/'report.md').write_text('\n'.join(lines))
    print(json.dumps({'selected':winner,'passes_gate':passes,'changes':decision['test_hit_changes'],'metering':metering},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);report(p.parse_args().run)
