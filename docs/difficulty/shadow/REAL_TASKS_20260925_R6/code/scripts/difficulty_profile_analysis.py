"""Frozen-profile design checks and candidate-aware paired diagnostics. No API calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.difficulty_experiment import write_json
from scripts.difficulty_judge_report import consolidate

LEVELS={'easy':0,'medium':1,'hard':2}

def validate_design(dataset):
    cases=dataset['cases'];groups={}
    if len({c['id'] for c in cases})!=len(cases):raise ValueError('Duplicate cases')
    for c in cases:
        groups.setdefault(c['family'],[]).append(c)
        if c.get('teacher_label') is not None or c.get('empirical_difficulty') is not None:
            raise ValueError('This diagnostic cannot carry claimed human or empirical labels')
    for group in groups.values():
        if len(group)!=3 or {c['profile_variant'] for c in group}!={'intro','practised','paraphrase'}:
            raise ValueError('Each family needs all three profiles')
        if len({c['student_visible_text'] for c in group})!=1:
            raise ValueError('Profile comparison must preserve the question exactly')
        if len({c['learner_profile'] for c in group})!=3 or any(not c['learner_profile'].strip() for c in group):
            raise ValueError('Need three explicit distinct profiles')
    ids={c['id']:c for c in cases}
    wanted={(next(c['id'] for c in g if c['profile_variant']=='intro'),next(c['id'] for c in g if c['profile_variant']==variant),expectation)
            for g in groups.values() for variant,expectation in [('practised','nonincrease'),('paraphrase','equal')]}
    actual={(r['a'],r['b'],r['expectation']) for r in dataset['relations']}
    if actual!=wanted or len(actual)!=len(dataset['relations']):raise ValueError('Missing, duplicate or unexpected controls')
    return groups

def compare_candidates(a,b,expectation):
    if a.get('status')!='valid' or b.get('status')!='valid':return 'unavailable'
    ca=a['result']['decision']['candidates'];cb=b['result']['decision']['candidates']
    if not ca or not cb:return 'abstained'
    aa={LEVELS[x] for x in ca};bb={LEVELS[x] for x in cb}
    if expectation=='equal':return 'equal_candidates' if aa==bb else 'changed_candidates'
    if min(bb)>max(aa):return 'reversal'
    if max(bb)<min(aa):return 'strictly_lower'
    if max(bb)<=min(aa):return 'nonincrease'
    return 'unresolved_overlap'

def analyse(directory):
    data=json.loads((directory/'dataset.json').read_text());groups=validate_design(data)
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['status']!='complete' or manifest['arms']!=['v4']:raise ValueError('Need completed single-v4 run')
    rows=json.loads((directory/'records.json').read_text())
    metrics=consolidate(directory)
    lookup={(r['case_id'],r['repeat']):r for r in rows}
    pairs=[]
    for relation in data['relations']:
        checks=[]
        for i in range(manifest['repeats']):
            a=lookup.get((relation['a'],i),{});b=lookup.get((relation['b'],i),{})
            checks.append({'repeat':i,'status':compare_candidates(a,b,relation['expectation']),
                'a_candidates':a.get('result',{}).get('decision',{}).get('candidates'),
                'b_candidates':b.get('result',{}).get('decision',{}).get('candidates')})
        pairs.append({**relation,'checks':checks})
    counts={expectation:dict(Counter(c['status'] for pair in pairs if pair['expectation']==expectation for c in pair['checks'])) for expectation in ('nonincrease','equal')}
    result={'unique_questions':len(groups),'profile_cases':len(data['cases']),'reviews':len(rows),
        'human_accuracy':None,'coverage':metrics['v4'],'pair_counts':counts,'pairs':pairs,
        'limitation':'Repeated profiles share question texts; not independent questions or empirical learner effects.'}
    write_json(directory/'PROFILE_SUMMARY.json',result)
    lines=['# 冻结 v4.1：新题与学习经历对照','','四个新题目家族，每题三种明确学生背景，每个场景评两次。12 个背景场景不是 12 道独立新题；24 次评审也不是 24 个独立教育样本。', '',
        f"实际调用 {manifest['actual_calls']} 次，{manifest['total_tokens']} tokens。没有教师标签或学生作答数据，准确率为空。",'',
        f"有效评审 {metrics['v4']['valid']}/{len(rows)}；明确单一等级 {metrics['v4']['single_level_reviews']}/{len(rows)}；候选集合重复一致 {metrics['v4']['candidate_set_stable_cases']}/{len(data['cases'])}。",'',
        '| 题目家族 | 入门经历 | 熟练经历 | 入门经历同义表述 |','|---|---|---|---|']
    for family,cs in groups.items():
        cells=[]
        for variant in ('intro','practised','paraphrase'):
            id=next(c['id'] for c in cs if c['profile_variant']==variant)
            group=sorted([r for r in rows if r['case_id']==id],key=lambda r:r['repeat'])
            cells.append('；'.join('/'.join(r['result']['decision']['candidates']) or '弃判' if r['status']=='valid' else '失败' for r in group))
        lines.append('| '+family+' | '+' | '.join(cells)+' |')
    lines+=['','## 预先规定的对照结果','','熟练经历不应升高预估难度；宽档标签相同允许。候选范围有重叠但不能保证不升高时记 unresolved_overlap，不算通过。两边都为单一等级时严格降低记 strictly_lower，否则边界不强转数字。', '',json.dumps(counts,ensure_ascii=False,indent=2),'','同义表述比较完整候选集合：两个结果虽然都显示“不确定”，候选集合不同也不算一致。失败或缺结果不会从分母消失。','','## 证据边界','','这是冻结协议在新材料上的前瞻开发诊断：没有把本轮题目的预期标签传入模型，没有修改评委后重跑挑选结果。新题仍由 AI 编写，表述等价也是开发假设。反应符合预期只能支持流程对这些信息有合理敏感性，不能证明实际学生难度或跨学科准确性。','']
    (directory/'PROFILE_REPORT.md').write_text('\n'.join(lines))
    dest=directory/'post_run_code/scripts/difficulty_profile_analysis.py';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(Path(__file__).read_bytes())
    write_json(directory/'PROFILE_ANALYSIS_MANIFEST.json',{'analysis_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'additional_api_calls':0})
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    r=analyse(p.parse_args().directory);print(json.dumps({k:r[k] for k in ('unique_questions','profile_cases','coverage','pair_counts')},ensure_ascii=False))
