"""Build source-linked tables for the 2026-09-12 experiment retrospective.

Read-only with respect to experiments, application data and configuration.
No network requests, inference, new labels or re-selection of strategies.
"""
from datetime import datetime, timezone
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings

OUT=ROOT/'docs/rag/daily-records/20260912'
RUNS={
    'R1': 'docs/rag/experiments/20260912T053716373758Z',
    'R2_MLQA': 'docs/rag/experiments/20260912T055718752885Z',
    'R2_T2': 'docs/rag/experiments/20260912T055800717636Z',
    'R3': 'docs/rag/chunk-experiments/20260912T062952243934Z',
    'R4': 'docs/rag/r4-experiments/20260912T072619024568Z',
    'R5': 'docs/rag/r5-experiments/20260912T085156100010Z',
}
SOURCES={}


def read(path):
    path=ROOT/path
    raw=path.read_bytes();SOURCES[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    metric_rows=[];tables=['# 2026-09-12 原始汇总值对照表','',
        '由各轮已保存的数值文件直接导出。本表没有新调用、重新评分或改变选型。不同轮次、数据、预算的成绩不构成可直接相减的时间序列。',
        'CSV 保存原始小数；百分比表仅做显示舍入。R4 本地 0.6B 未运行保留集，空白不填成零。','']
    def metric(round_,split,arm,group,name,value,n,unit,budget,source,pointer):
        data_status={'R1':'assistant_authored_unreviewed','R2_MLQA':'public_human_qa_derived',
            'R2_T2':'public_human_relevance_binary','R3':'public_human_answer_spans_previously_exposed',
            'R4':'public_human_answer_spans_heldout_families','R5':'public_human_answer_spans_heldout_families'}[round_]
        if round_ in ('R4','R5'):
            data_status='public_human_answer_spans_'+('previously_exposed_dev' if split=='dev' else 'heldout_at_initial_run')
        qualification=('failure_inclusive_pipeline_not_pure_first_stage' if round_=='R4' and
            arm.startswith('api8b') and name=='candidate_hit20' else
            'pre_rerank_candidate_coverage' if round_=='R5' and name=='candidate_hit20' else
            'stage_sum_estimate_not_online_end_to_end' if name=='stage_sum_estimate_ms' else '')
        metric_rows.append(dict(round=round_,split=split,arm=arm,group=group,metric=name,value=value,
            denominator=n,unit=unit,budget=budget,data_status=data_status,qualification=qualification,
            source_file=source,source_pointer=pointer))
    calls=[]
    for round_ in ('R1','R2_MLQA','R2_T2'):
        source=RUNS[round_]+'/metrics.json';data=read(source)
        tables += ['## '+round_,'','| 划分 | 方法 | 可答题数 | Recall@5 | Hit@5 | MRR@5 | nDCG@5 |','|---|---|---:|---:|---:|---:|---:|']
        for split in ('dev','test'):
            for arm,record in data.items():
                item=record['metrics']['groups']['split'][split]
                n=item['denominators']['answerable_queries'];values=item['answerable_metrics']
                tables.append(f"| {split} | {arm} | {n} | {values['recall@5']:.2%} | {values['hit@5']:.2%} | {values['mrr@5']:.4f} | {values['ndcg@5']:.4f} |")
                for name,value in values.items():
                    if name.endswith('@5'):
                        metric(round_,split,arm,'all_answerable',name,value,n,'ratio','top5_fixed_passages',source,
                            f"/{arm}/metrics/groups/split/{split}/answerable_metrics/{name}")
        records=read(RUNS[round_]+'/provider-calls.json')
        calls.append(dict(round=round_,embedding=len(records),text=0,rerank=0,
            failed=sum(r['status']!='succeeded' for r in records),
            known_cost=str(sum(Decimal(str(r['usage'].get('cost',0))) for r in records)),
            missing_cost=sum('cost' not in r['usage'] for r in records),
            source=RUNS[round_]+'/provider-calls.json'))
        tables += ['',f"原始来源：[{round_} 数值](../../../{RUNS[round_].removeprefix('docs/')}/metrics.json)",'']

    source=RUNS['R3']+'/metrics.json';groups=read(source)['groups']
    tables += ['## R3','', '| 方法 | 约束 | 划分 | n | 答案跨度 Hit | 平均返回片段 | 平均正文字符 |',
        '|---|---|---|---:|---:|---:|---:|']
    for index,row in enumerate(groups):
        if row['group'] not in ('split','overall'):continue
        split=row['value']
        tables.append(f"| {row['arm']} | {row['policy']} | {split} | {row['queries']} | {row['known_span_hit']:.2%} | {row['returned_chunks']:.2f} | {row['returned_characters']:.1f} |")
        for name in ('known_span_hit','known_context_coverage','returned_chunks','returned_characters','duplicate_character_ratio'):
            metric('R3',split,row['arm'],row['group'],name,row[name],row['queries'],
                'characters' if name=='returned_characters' else 'count' if name=='returned_chunks' else 'ratio',row['policy'],source,f'/groups/{index}/{name}')
    v3=read('docs/rag/chunking-verification-20260912.json')['experiment_calls']
    calls.append(dict(round='R3',embedding=v3['embedding'],text=v3['text'],rerank=0,failed=0,
        known_cost=str(v3['provider_reported_cost']),missing_cost=0,source='docs/rag/chunking-verification-20260912.json'))

    summaries={}
    for round_ in ('R4','R5'):
        summaries[round_]={}
        for split in ('dev','test'):
            source=RUNS[round_]+'/'+split+'-summary.json';data=read(source)
            summaries[round_][split]={row['arm']:row for row in data if row['group']=='all'}
            for index,row in enumerate(data):
                n=row.get('queries',row.get('rows'))
                for name in ('budget_hit','top5_hit','mrr5','candidate_hit20','context_tokens','rerank_ms','stage_sum_estimate_ms'):
                    if name not in row:continue
                    metric(round_,split,row['arm'],row['group'],name,row[name],n,
                        'ms' if name.endswith('_ms') else 'qwen_tokens' if name=='context_tokens' else 'ratio',
                        'top5_seeds_1024_qwen_source_tokens',source,f'/{index}/{name}')
    tables+=['','## R4：全部 16 个开发集配置','',
        '每个 dev 配置为 184 个场景；已运行的 test 配置各 168 个场景。MRR 使用叶片段排名。',
        'R4 API 行的 candidate_hit20 含接口失败，不能当作纯首阶段覆盖；纯首阶段查看 token_hybrid。','',
        '| 方法 | dev Hit | dev MRR | test Hit | test MRR | test 平均原文 token |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,dev in summaries['R4']['dev'].items():
        test=summaries['R4']['test'].get(arm)
        fields=(f"{test['budget_hit']:.2%} | {test['mrr5']:.4f} | {test['context_tokens']:.1f}"
            if test else '未运行 | 未运行 | 未运行')
        tables.append(f"| {arm} | {dev['budget_hit']:.2%} | {dev['mrr5']:.4f} | {fields} |")
    tables+=['','## R4：配置含义','','| 方法 | 切分 | 标题编码 | 查询指令 | 首阶段 | 扩展 |','|---|---|---|---|---|---|']
    for arm,(chunk,title,instruction,retrieval,expansion) in read(RUNS['R4']+'/arms.json').items():
        tables.append(f"| {arm} | {chunk} | {title} | {instruction} | {retrieval} | {expansion} |")
    tables+=['', 'rerank_none / rerank_parent 在 token_hybrid 的相同 Top20 上加入本地 Qwen3-Reranker-0.6B；api8b_none / api8b_parent 加入云端 Qwen3-Reranker-8B。后两组由保留集曝光前的补充协议加入。','']
    tables+=['## R5','', '| 划分 | 方法 | n | 预算 Hit | MRR@5 | 重排前 Hit@20 | 失败场景 | 阶段合成平均 ms |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for split,values in summaries['R5'].items():
        for arm,row in values.items():
            tables.append(f"| {split} | {arm} | {row['rows']} | {row['budget_hit']:.2%} | {row['mrr5']:.4f} | {row['candidate_hit20']:.2%} | {row['failures']} | {row['stage_sum_estimate_ms']:.1f} |")
    v5=read(RUNS['R5']+'/decision.json')['metering']
    # R4 measured accounting is also stated in its verified result report; the
    # API probe is included, runtime activation requests are explicitly excluded.
    read(RUNS['R4']+'/decision.json')
    calls.append(dict(round='R4',embedding=42,text=0,rerank=353,failed=7,
        known_cost='0.29398760',missing_cost=7,source='docs/rag/R4_RESULTS_20260912.md'))
    calls.append(dict(round='R5',embedding=v5['embedding']['attempts'],text=v5['text']['attempts'],rerank=v5['rerank']['attempts'],
        failed=sum(v['failures'] for v in v5.values()),
        known_cost=str(sum(Decimal(str(v['known_cost'])) for v in v5.values())),
        missing_cost=sum(v['missing_cost'] for v in v5.values()),source=RUNS['R5']+'/decision.json'))
    tables+=['','## 研究运行调用账目','',
        '仅下列固定研究运行；R4 含 1 次重排探测。排除 CA1、难度验收、应用索引迁移、模型下载及离线重放。cost 为已返回金额合计，缺失不代表免费。','',
        '| 运行 | 嵌入 | 翻译/文字 | 重排 | 请求失败 | 已返回 cost | cost 缺失次数 |','|---|---:|---:|---:|---:|---:|---:|']
    for c in calls:
        tables.append(f"| {c['round']} | {c['embedding']} | {c['text']} | {c['rerank']} | {c['failed']} | {Decimal(c['known_cost']):.8f} | {c['missing_cost']} |")
    totals={k:sum(c[k] for c in calls) for k in ('embedding','text','rerank','failed','missing_cost')}
    totals['known_cost']=str(sum(Decimal(c['known_cost']) for c in calls))
    tables+=['',f"合计 {totals['embedding']+totals['text']+totals['rerank']} 次 API 尝试；已返回 cost 合计 {Decimal(totals['known_cost']):.8f}，不代表账号全天或合并完整账单。",'']
    settings=Settings.from_env()
    fields=('chunk_strategy','chunk_max_tokens','chunk_overlap_chars','retrieval_strategy','retrieval_candidate_k',
        'top_k','retrieval_metadata_weight','retrieval_document_encoding','retrieval_query_encoding','retrieval_context_tokens','retrieval_expansion')
    snapshot={name:getattr(settings,name) for name in fields}
    snapshot.update(text_model=settings.text.model,embedding_model=settings.embedding.model,reranker_model=settings.rerank.model)
    for path in ('app/chunking.py','app/rag_candidates.py','app/rag_runtime.py','app/retrieval.py','app/pipeline.py','app/config.py'):
        SOURCES[path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    # Preserve a source seal even for human-authored high-level accounting text.
    path='docs/rag/R4_RESULTS_20260912.md';SOURCES[path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    save(OUT/'record-index.json',dict(date='2026-09-12',compiled_at=datetime.now(timezone.utc).isoformat(),
        scope='Historical synthesis; no new model requests, labels, experiment results or model selection.',
        runs=RUNS,active_configuration=snapshot,call_ledger=calls,call_totals=totals,
        metric_rows=len(metric_rows),source_sha256=SOURCES))
    with (OUT/'metric-summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(metric_rows[0]));writer.writeheader();writer.writerows(metric_rows)
    (OUT/'comparison-tables.md').write_text('\n'.join(tables)+'\n')
    print(json.dumps({'metric_rows':len(metric_rows),'research_calls':totals,'output':str(OUT)},ensure_ascii=False))


if __name__=='__main__':build()
