"""Bounded semantic audit replay of frozen judgements: 6 cases x 2 = 12 calls."""
import argparse,asyncio,hashlib,json,random,shutil,sys,tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.providers import ApiProviders
from scripts.difficulty_experiment import CappedStore,write_json,call_rows,digest,safe_error
from scripts.difficulty_semantic_audit import messages,validate,REVISION

async def run(args):
    data=json.loads((ROOT/'benchmarks/difficulty_semantic_audit_v1/cases.json').read_text())
    if len(data['cases'])!=6:raise ValueError('Frozen six-case diagnostic required')
    output=args.output.resolve();output.mkdir(exist_ok=False,parents=True)
    cases={c['id']:c for c in data['cases']}
    rows=[dict(id=f'{id}_{i}',case_id=id,repeat=i,status='pending') for id in cases for i in range(2)]
    random.Random(925).shuffle(rows)
    manifest=dict(revision=REVISION,live=args.live,planned_calls=12,call_cap=12,status='prepared',dataset_sha256=digest(data),human_labels=False)
    write_json(output/'dataset.json',data)
    plan=ROOT/'benchmarks/difficulty_semantic_audit_v1/PLAN.md';(output/'PLAN.md').write_bytes(plan.read_bytes());manifest['plan_sha256']=hashlib.sha256(plan.read_bytes()).hexdigest()
    hashes={}
    for path in list((ROOT/'app').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('test_difficulty_semantic*.py')):
        rel=path.relative_to(ROOT);dest=output/'code'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);hashes[str(rel)]=hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest['code_sha256']=hashes
    for row in rows:write_json(output/'items'/row['id']/'prompt.json',messages(cases[row['case_id']]))
    write_json(output/'manifest.json',manifest);write_json(output/'records.json',rows)
    print(json.dumps(dict(output=str(output),live=args.live,planned_calls=12)),flush=True)
    if not args.live:return
    settings=Settings.from_env();settings=replace(settings,timeout=120,text_json_mode=True,text=replace(settings.text,extra={'thinking':{'type':'disabled'},'temperature':0,'max_tokens':3000}))
    store=CappedStore(Path(tempfile.mkdtemp(prefix='lumori-semantic-audit-')),12);provider=ApiProviders(settings,store)
    manifest.update(status='running',model=settings.text.model,parameters=settings.text.extra);write_json(output/'manifest.json',manifest)
    try:
        for row in rows:
            try:
                raw=await provider.generate(messages(cases[row['case_id']]),row['id']);write_json(output/'items'/row['id']/'response.json',raw)
                row.update(status='valid',audit=validate(raw,cases[row['case_id']]))
            except Exception as exc:
                row.update(status='failed',error=safe_error(exc))
                calls=call_rows(store)
                if calls and calls[-1]['status']!='succeeded':manifest['status']='stopped_provider_failure';break
            finally:write_json(output/'records.json',rows)
            print(row['id'],row['status'],row.get('audit',{}).get('status'),flush=True)
        else:manifest['status']='complete'
    finally:
        await provider.close();calls=call_rows(store);write_json(output/'calls.json',calls)
        manifest.update(actual_calls=len(calls),total_tokens=sum(c['usage'].get('total_tokens',0) for c in calls),calls_without_cost=sum('cost' not in c['usage'] for c in calls))
        write_json(output/'manifest.json',manifest)
        positives=[r for r in rows if cases[r['case_id']]['target_present']]
        controls=[r for r in rows if not cases[r['case_id']]['target_present']]
        def matching(r):return r['status']=='valid' and any(f['certainty']=='definite' and f['category']==cases[r['case_id']]['target_category'] for f in r['audit']['findings'])
        summary=dict(valid=sum(r['status']=='valid' for r in rows),scheduled=len(rows),target_issue_checks=len(positives),target_category_detected=sum(matching(r) for r in positives),control_checks=len(controls),controls_flagged_target=sum(matching(r) for r in controls),controls_any_definite_issue=sum(r['status']=='valid' and r['audit']['status']=='correction_required' for r in controls),human_accuracy=None)
        write_json(output/'summary.json',summary)
        lines=['# 按需语义复核诊断','','本轮复核已有判级理由与样例答案，不重新定级。样例来自已见过的开发题和人工构造的改动，没有教师金标准。', '',f"实际调用 {len(calls)}，{manifest['total_tokens']} tokens；有效 {summary['valid']}/{len(rows)}。",f"预设类别检出 {summary['target_category_detected']}/{len(positives)}；对照中同类标记 {summary['controls_flagged_target']}/{len(controls)}，对照中任意明确问题 {summary['controls_any_definite_issue']}/{len(controls)}。这些不是泛化准确率。",'', '| 样例 | 两次状态 | 明确问题类别 |','|---|---|---|']
        for id in cases:
            group=sorted([r for r in rows if r['case_id']==id],key=lambda r:r['repeat'])
            lines.append('| '+id+' | '+' / '.join(r.get('audit',{}).get('status',r['status']) for r in group)+' | '+' / '.join(', '.join(f['category'] for f in r.get('audit',{}).get('findings',[]) if f['certainty']=='definite') or '无' for r in group)+' |')
        for r in rows:
            if r['status']!='valid':continue
            lines += ['',f"## {r['id']}",'']
            for finding,evidence in zip(r['audit']['findings'],r['audit']['resolved_evidence']):
                lines += [f"- {finding['category']} ({finding['certainty']}): {finding['explanation']}",f"  - 建议：{finding['suggested_correction']}", '  - 题目依据：'+' / '.join(e['text'] for e in evidence['question']),'  - 初评依据：'+' / '.join(e['path']+': '+e['text'] for e in evidence['review'])]
            if not r['audit']['findings']:lines.append('本次未发现具体问题；不等于证明判级正确。')
        (output/'REPORT.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');p.add_argument('--output',type=Path,required=True)
    asyncio.run(run(p.parse_args()))
