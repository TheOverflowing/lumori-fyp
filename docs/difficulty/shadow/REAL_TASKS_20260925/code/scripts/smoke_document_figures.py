"""Small, opt-in live smoke using public benchmark material and isolated storage.

Not an accuracy benchmark. Does not modify the user's courses or prior archives.
"""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Settings,ROOT
from app.store import Store,dumps,now,uid
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.document_jobs import parse_document,enrich
from app.models import GenerateRequest


async def main(output,live):
    output.mkdir(parents=True,exist_ok=True)
    settings=replace(Settings.from_env(),data_dir=output/'runtime',document_max_figures=3,document_worker_timeout=300)
    store=Store(settings.data_dir);providers=ApiProviders(settings,store);pipeline=Pipeline(settings,store,providers)
    source=ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/samples/p06/image-only.pdf'
    raw=source.read_bytes();cid=uid();did=uid()
    store.execute('INSERT INTO courses VALUES(?,?,?)',(cid,'Public document integration smoke',now()))
    store.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',(did,cid,'public-p06.pdf',hashlib.sha256(raw).hexdigest(),'pending',1,now()))
    folder=settings.data_dir/'documents';folder.mkdir();(folder/(did+'.pdf')).write_bytes(raw)
    evidence={'scope':'Live integration smoke; not held-out accuracy or retrieval evaluation','source':str(source.relative_to(ROOT)),
        'sha256':hashlib.sha256(raw).hexdigest(),'image_analysis':False,'stages':[]}
    def save():
        evidence['calls']=store.all('SELECT capability,model,status,usage,duration_ms,http_status,response_model FROM calls')
        for c in evidence['calls']:c['usage']=json.loads(c['usage'])
        (output/'results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    try:
        for tier in ('standard','advanced'):
            started=time.perf_counter();job,_=store.job(uid(),'parse',{'document_id':did,'tier':tier,'images':live})
            result=await parse_document(pipeline,{'document_id':did,'tier':tier,'images':live},job['id'])
            report=json.loads(store.one('SELECT report FROM document_parsing WHERE document_id=?',(did,))['report'])
            (output/(tier+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
            evidence['stages'].append(dict(stage='mineru_'+tier,seconds=round(time.perf_counter()-started,3),pages=len(report['pages']),characters=len(report['pages'][0]['text']),chunks=result['chunks']))
            print('Completed MinerU '+tier,flush=True);save()
        if live:
            started=time.perf_counter();job,_=store.job(uid(),'figures',{'document_id':did})
            result=await enrich(pipeline,{'document_id':did},job['id'])
            evidence['stages'].append(dict(stage='docling_vision_embedding',seconds=round(time.perf_counter()-started,3),result=result))
            print('Completed figure pipeline',flush=True);save()
            job,_=store.job(uid(),'index',{'document_id':did})
            result=await pipeline.index(did,job['id']);evidence['stages'].append(dict(stage='text_index',result=result));save()
            job,_=store.job(uid(),'generate',{'course_id':cid})
            sources,trace=await pipeline.retrieve(GenerateRequest(course_id=cid,topic='Describe the figure and the relationships shown in the diagram',material='lesson',request_key=uid()),job['id'],with_trace=True)
            evidence['stages'].append(dict(stage='retrieval',sources=sources,trace=trace));save()
            before=store.one('SELECT count(*) AS n FROM calls')['n']
            result=await enrich(pipeline,{'document_id':did},job['id'])
            after=store.one('SELECT count(*) AS n FROM calls')['n']
            evidence['stages'].append(dict(stage='cached_retry',new_api_calls=after-before,result=result));save()
        evidence['completed']=True
    except Exception as exc:
        evidence['completed']=False;evidence['error_type']=type(exc).__name__
        # Safe app-level error only; avoid raw transport or model output.
        evidence['error']='Integration stopped; inspect stage statuses and run a bounded diagnostic.'
        print('Stopped:',type(exc).__name__,flush=True)
    finally:save();await providers.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--live',action='store_true')
    args=p.parse_args();asyncio.run(main(args.output,args.live))
