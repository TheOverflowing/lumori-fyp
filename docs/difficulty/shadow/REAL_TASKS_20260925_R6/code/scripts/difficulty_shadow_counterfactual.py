"""Replay saved shadow decisions without provider calls or production changes."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.difficulty_shadow import digest,rework_candidate
from scripts.difficulty_shadow_review import collect


def budget_snapshot(export):
    """Report observed headroom only; no reservation or new provider call."""
    maximum=export.get('evidence',{}).get('configuration',{}).get('max_calls')
    calls=export.get('calls')
    if type(maximum) is not int or maximum<0 or not isinstance(calls,list):
        return {'status':'unknown','job_call_cap':maximum,'recorded_job_calls':None,
                'remaining_job_calls':None,'complete_rework_capacity_verified':False}
    used=len(calls)
    remaining=max(0,maximum-used)
    return {'status':'exhausted' if remaining==0 else 'remaining_not_reserved',
            'job_call_cap':maximum,'recorded_job_calls':used,
            'remaining_job_calls':remaining,'complete_rework_capacity_verified':False}


def replay(directories, repeat_path=None):
    cases=collect(directories)  # Verifies saved content and student-visible input hashes.
    repeats=None
    if repeat_path:
        repeats=json.loads(repeat_path.read_text())
        if repeats.get('status')!='complete' or repeats.get('kind')!='same_prompt_shadow_judge_repeat':
            raise ValueError('Repeat run is incomplete or has the wrong protocol')
    records=[]
    for case in cases:
        directory=Path(case['source_directory'])
        evidence_path=next((p for p in directory.glob('task_*_evidence.json')
            if json.loads(p.read_text())['job']['id']==case['job_id']),None)
        if evidence_path is None:raise ValueError('Saved job evidence is missing')
        export=json.loads(evidence_path.read_text())
        evidence=export['evidence']
        question=next(q for q in evidence['difficulty_shadow']['questions'] if q['slot_id'] in
                      {case['case_id'].rsplit('_',1)[-1]})
        baseline=rework_candidate(question)
        observed=[]
        if repeats and Path(repeats['source_run']).resolve()==directory.resolve():
            if repeats['source_asset_sha256']!=evidence['difficulty_shadow']['asset_sha256']:
                raise ValueError('Repeat input differs from saved accepted asset')
            if repeats['prompt_sha256']!=question.get('judge',{}).get('prompt_sha256'):
                raise ValueError('Repeat prompt differs from saved judge prompt')
            for item in repeats['records']:
                updated=deepcopy(question)
                updated['judge_repeat']={'status':item['status'],'result':item.get('result',{})}
                observed.append({'repeat':item['repeat'],'decision':rework_candidate(updated),
                                 'candidates':item.get('result',{}).get('decision',{}).get('candidates')})
        final=baseline
        if observed:
            # An invalid or contradictory repeat cannot be overridden by a good one.
            if all(item['decision']['action']=='rework_candidate' for item in observed):
                final=observed[0]['decision']
            else:
                final={'action':'manual_review','scope':'difficulty_only','enforcement_enabled':False,
                       'human_validated':False,'reason':'repeat_runs_not_unanimous'}
        records.append({'case_id':case['case_id'],'asset_sha256':case['asset_sha256'],
                        'target_difficulty':case['target_difficulty'],
                        'original_difficulty':case['original_difficulty'],
                        'initial_candidates':case['candidates'],
                        'audit_status':case['audit_status'],
                        'baseline':baseline,'repeats':observed,'counterfactual':final,
                        'budget':budget_snapshot(export)})
    return {'kind':'offline_counterfactual_no_provider_calls','enforcement_enabled':False,
            'human_accuracy':None,'unique_completed_questions':len(records),'records':records,
            'candidate_count':sum(r['counterfactual']['action']=='rework_candidate' for r in records),
            'limitations':['AI judgments are not human difficulty labels.',
                           'A rework candidate does not certify answer correctness or question clarity.',
                           'No automatic rework is enabled.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories',type=Path,nargs='+')
    parser.add_argument('--repeat',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=replay(args.directories,args.repeat)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise SystemExit('Output already exists')
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'unique_completed_questions':result['unique_completed_questions'],
                      'candidate_count':result['candidate_count']},ensure_ascii=False))
