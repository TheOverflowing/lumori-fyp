"""Read-only postprocessing of a completed difficulty pilot; no model calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.difficulty_review_decision import review_decision
from scripts.difficulty_experiment import write_json


def consolidate(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['status']!='complete':raise ValueError('Only completed runs may be consolidated')
    rows=json.loads((directory/'records.json').read_text())
    dataset=json.loads((directory/'dataset.json').read_text())
    arms=manifest['arms']
    decisions={'kind':'post_run_conservative_aggregation','source_records_sha256':hashlib.sha256((directory/'records.json').read_bytes()).hexdigest(),
               'human_accuracy':None,'production_policy_changed':False,'arms':{}}
    metrics={}
    for arm in arms:
        decisions['arms'][arm]={c['id']:review_decision([r for r in rows if r['arm']==arm and r['case_id']==c['id']],manifest['repeats']) for c in dataset['cases']}
        subset=[r for r in rows if r['arm']==arm]
        valid=[r for r in subset if r['status']=='valid']
        exact_sets=0
        for case in dataset['cases']:
            group=[r for r in subset if r['case_id']==case['id']]
            if len(group)!=manifest['repeats'] or any(r['status']!='valid' for r in group):continue
            signatures=[]
            for r in group:
                result=r.get('result',{})
                candidates=result.get('decision',{}).get('candidates')
                signatures.append(tuple(sorted(candidates)) if candidates is not None else (r['label'],))
            exact_sets+=int(len(set(signatures))==1)
        metrics[arm]={'scheduled':len(subset),'valid':len(valid),
            'single_level_reviews':sum(r['label']!='uncertain' for r in valid),
            'boundary_reviews':sum(len(r.get('result',{}).get('decision',{}).get('candidates',[]))>1 for r in valid),
            'candidate_set_stable_cases':exact_sets,
            'decision_counts':dict(Counter(d['status'] for d in decisions['arms'][arm].values()))}
    write_json(directory/'CONSENSUS.json',decisions)
    write_json(directory/'COVERAGE.json',metrics)
    lines=['# 评审汇总与覆盖率','','“暂定一致”仅表示所有预定重复有效且等级相同，不是准确性证明。边界候选会归为 uncertain；多弃判不能算作更强判级能力。', '',
        '| 方法 | 有效评审 | 单一明确等级 | 多候选边界评审 | 候选集合一致题数 |','|---|---:|---:|---:|---:|']
    for arm,m in metrics.items():
        lines.append(f"| {arm} | {m['valid']}/{m['scheduled']} | {m['single_level_reviews']}/{m['scheduled']} | {m['boundary_reviews']} | {m['candidate_set_stable_cases']}/{len(dataset['cases'])} |")
    lines+=['','## 逐题合并','','失败、缺失或等级分歧不会回退到单次成功判断。两次 uncertain 仅表示弃判；若候选集合不同，集合一致指标不会计为一致。','']
    for c in dataset['cases']:
        lines += [f"### {c['id']}",'']
        for arm in arms:
            d=decisions['arms'][arm][c['id']]
            group=sorted([r for r in rows if r['arm']==arm and r['case_id']==c['id']],key=lambda r:r['repeat'])
            candidates=[r.get('result',{}).get('decision',{}).get('candidates') for r in group]
            lines.append(f"- {arm}: {d['status']} / {d['estimated_difficulty']}；观测 {d['observed_labels']}；候选集合 {candidates}。")
        lines.append('')
    lines+=['## v4 核对示例','','以下只展示每题第一次有效评审，供查看依据；不代表另一重复成功，也不替代上面的合并结果。证据由系统按编号还原，角色分类和剩余任务仍是模型判断。','']
    for c in dataset['cases']:
        found=sorted([r for r in rows if r['arm']=='v4' and r['case_id']==c['id'] and r['status']=='valid'],key=lambda r:r['repeat'])
        if not found:continue
        r=found[0];v=r['result']
        lines += [f"### {c['id']}（重复 {r['repeat']+1}）",'',v['decision']['reason'],'']
        for task,refs in zip(v['tasks'],v['resolved_evidence']):
            request=' / '.join(e['text'] for e in refs['request_ids'])
            facts=' / '.join(e['text'] for e in refs['condition_ids']) or '无引用'
            solutions=' / '.join(e['text'] for e in refs['solution_ids']) or '未引用解法提示'
            lines += [f'- 作答要求：{request}',f'  - 题目条件：{facts}',f'  - 解法提示：{solutions}',f"  - 剩余工作：{task['residual_work']}"]
        lines.append('')
    (directory/'AUDIT.md').write_text('\n'.join(lines))
    paths=['scripts/difficulty_judge_report.py','scripts/difficulty_review_decision.py']
    hashes={}
    for rel in paths:
        dest=directory/'post_run_code'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest);hashes[rel]=hashlib.sha256(dest.read_bytes()).hexdigest()
    write_json(directory/'POST_RUN_MANIFEST.json',{'kind':'deterministic_postprocessing_no_calls','code_sha256':hashes})
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    print(json.dumps(consolidate(p.parse_args().directory),ensure_ascii=False))
