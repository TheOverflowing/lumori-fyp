"""Small live difficulty-control check on self-authored material; no human scores."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Settings
from scripts.ca1_smoke import (SAMPLE, wait_job, write_json, safe_exception,
                               authenticated_smoke_client, smoke_account_credentials)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    settings=Settings.from_env()
    for cap in ('text','embedding'):getattr(settings,cap).require(cap)
    if not args.live:
        print('Configuration present. --live runs an isolated 3-question all-hard case and a 1/1/1 mixed case. Nominal 7 calls, at most 11 with one repair per case.')
        return 0
    from app.main import create_app
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=ROOT/'docs/ca1/evidence'/('difficulty-'+run_id)
    folder.mkdir(parents=True)
    settings=replace(settings,data_dir=ROOT/'tmp/difficulty-live'/run_id)
    report={'run_id':run_id,'runtime_directory':str(settings.data_dir),'results':[],
        'manual_quality_verified':False,'student_difficulty_calibrated':False,
        'note':'Separate calls to the same model test operational cognitive demand, not empirical learner difficulty.'}
    checkpoint=lambda:write_json(folder/'results.json',report)
    checkpoint()
    try:
        raw=SAMPLE.read_bytes();report['source_sha256']=hashlib.sha256(raw).hexdigest()
        (folder/SAMPLE.name).write_bytes(raw)
        app=create_app(settings)
        with authenticated_smoke_client(app, smoke_account_credentials()) as (c, authentication):
            report['authentication']=authentication
            response=c.post('/api/courses',json={'name':'Difficulty control '+run_id});response.raise_for_status()
            course=response.json()['id'];report['course_id']=course
            response=c.post('/api/documents',data={'course_id':course},files={'file':(SAMPLE.name,raw,'text/markdown')});response.raise_for_status()
            doc=response.json()['id']
            index=wait_job(c,c.post('/api/documents/'+doc+'/index'))
            report['index']=index;checkpoint()
            if index['status']!='succeeded':return 1
            for name,distribution in [('all_hard',{'easy':0,'medium':0,'hard':3}),('mixed',{'easy':1,'medium':1,'hard':1})]:
                payload={'course_id':course,'document_ids':[doc],'material':'quiz','count':3,
                    'difficulty_distribution':distribution,'question_type':'short_answer','language':'zh',
                    'learner_profile':'已学习所选课程资料的计算机专业本科生，理解检索、引用与审核版本的基本概念。',
                    'topic':'考核课程资料中的检索流程、引用支持、嵌入兼容性与审核版本。按逐题难度计划设计实际任务；需要情境时可明确给定假设条件，不能虚构外部事实。',
                    'request_key':'difficulty-'+run_id+'-'+name}
                job=wait_job(c,c.post('/api/generations',json=payload))
                item={'case':name,'requested_distribution':distribution,'job':job,'passed':False}
                report['results'].append(item);checkpoint()
                response=c.get('/api/jobs/'+job['id']+'/evidence');response.raise_for_status()
                write_json(folder/(name+'-job-evidence.json'),response.json())
                if job['status']=='succeeded':
                    cid=job['result']['content_id']
                    response=c.get('/api/contents/'+cid);response.raise_for_status();content=response.json()
                    write_json(folder/(name+'-draft.json'),content)
                    response=c.get('/api/contents/'+cid+'/evidence');response.raise_for_status()
                    write_json(folder/(name+'-evidence.json'),response.json())
                    response=c.get('/api/contents/'+cid+'/export');response.raise_for_status()
                    (folder/(name+'-export.md')).write_text(response.text)
                    observed={level:sum(q['difficulty']==level for q in content['asset']['questions']) for level in distribution}
                    item.update(observed_distribution=observed,
                        assessment=content['difficulty_assessment'],
                        passed=observed==distribution and content['difficulty_assessment']['status']=='model_checked' and content['status']=='draft')
                checkpoint()
                print(name,job['status'],flush=True)
            report['provider_attempts']=c.get('/api/status').json()['calls_today']
    except Exception as exc:report['error']=safe_exception(exc)
    finally:
        report['technical_checks_passed']=len(report['results'])==2 and all(r['passed'] for r in report['results']) and not report.get('error')
        report['finished_at']=datetime.now(timezone.utc).isoformat();checkpoint();print(folder,flush=True)
    return 0 if report['technical_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
