"""Real authenticated application-route smoke: upload, index, retrieve, generate, observe, save.

ASGI transport calls actual FastAPI routes and workers in-process; only the HTTP
listener is omitted. Model/embedding calls are real. A fresh private database
prevents changes to existing accounts, courses, drafts or tasks. Dry by default.
"""
import argparse,asyncio,hashlib,json,secrets,sys,tempfile,time
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import httpx
from app.config import Settings
from app.main import create_app
from app.store import LocalCallLimit
from scripts.difficulty_experiment import write_json,call_rows

SOURCE='''课程资料：检索索引、课程隔离与证据检查
向量索引中的文档向量由指定版本的嵌入模型生成。查询向量必须由同一嵌入模型版本生成，才能在这个索引中比较相似度。更换嵌入模型后，应当为需要使用的课程资料重建向量索引，记录新的模型版本；不能直接拿新查询向量与旧文档向量混合检索。
不同课程的资料分别归属相应课程。检索应当限定在当前账号有权限访问的当前课程资料中，只使用已启用且未删除的资料。另一门课即使出现相同术语，也不能因此自动加入当前题目的依据。索引重建不会扩大资料权限，也不能恢复已删除资料。
如果索引版本不一致，应先确认模型与索引版本，再重建对应课程的索引，完成后检查索引版本和检索范围。这个过程应保留原文和来源标识，使每个引用都能定位到正确资料。检索相似度较高只说明文本相近，不自动证明答案正确。
生成答案时需检查题干条件是否完整、答案是否得到资料支持、引用是否准确。资料不足时应明确说明缺口并补充有权限的资料，不能编造事实或从无权限课程取用文本。对多种可行解释，应指出各自依据和不能确定的部分。以上是本课程的操作性规则，不涉及外部行业法规。'''

async def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    cases=[]
    source_groups={}
    if args.dataset_case:
        dataset=json.loads((ROOT/'benchmarks/quality_latency_v1/dataset.json').read_text())
        by_id={c['id']:c for c in dataset['cases']}
        if len(args.dataset_case)!=len(set(args.dataset_case)) or len(args.dataset_case)>2:
            raise ValueError('Choose one or two distinct cases for this bounded run')
        for case_id in args.dataset_case:
            if case_id not in by_id:raise ValueError('Unknown dataset case: '+case_id)
            case=by_id[case_id]
            cases.append({k:case[k] for k in ('id','course','topic','difficulty','question_type','language','learner_profile')})
            source_groups[case['course']]=[d for d in dataset['source_documents'] if d['course']==case['course']]
    else:
        cases=[{'id':f'index_rules_{n}','course':'index_rules','topic':topic,'difficulty':'medium',
                'question_type':'short_answer','language':'zh',
                'learner_profile':'已学习所附课程资料的本科生，能理解模型版本、课程权限和引用定位规则，尚未独立处理过混合情境。'}
               for n,topic in enumerate(['更换嵌入模型后，如何处理当前课程的索引与检索范围。请出一道条件完整、要求应用资料规则的中等简答题。',
                                         '检索命中相似文本但证据不足时，如何判断引用是否可用并处理资料缺口。请出一道条件完整的中等应用简答题。'],1)]
        source_groups={'index_rules':[{'id':'index_rules','title':'索引与证据规则','text':SOURCE}]}
    manifest={'kind':'real_application_routes_with_live_providers','live':args.live,'global_call_cap':30,
        'planned_generation_jobs':len(cases),'selected_cases':[c['id'] for c in cases],
        'per_job_call_cap':14,'per_job_shadow_cap':args.shadow_max_calls,
        'repeat_disagreements':args.repeat_disagreements,'database':'isolated_private_temp_directory',
        'transport':'in-process ASGI; real authentication, API routes, workers, retrieval and model calls',
        'no_provider_or_retrieval_mocks':True,'status':'prepared'}
    for course,documents in source_groups.items():
        for document in documents:
            (output/f'source_{course}_{document["id"]}.md').write_text(document['text'])
    hashes={}
    for path in list((ROOT/'app').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('test_difficulty_shadow.py')):
        dest=output/'code'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['code_sha256']=hashes;write_json(output/'manifest.json',manifest)
    if not args.live:print(json.dumps(manifest|{'code_sha256':'archived'}),flush=True);return
    base=Settings.from_env();directory=Path(tempfile.mkdtemp(prefix='lumori-shadow-live-'))
    settings=replace(base,data_dir=directory,allowed_hosts=['testserver'],workers=1,generation_workflow='agent_v1',agent_runtime='deepseek_harness',
        agent_orchestration='supervisor_v2',agent_question_spec='none',agent_max_calls=14,max_daily_calls=30,
        difficulty_shadow_mode='shadow',difficulty_shadow_max_calls=args.shadow_max_calls,difficulty_shadow_max_questions=1,
        difficulty_shadow_repeat_disagreements=args.repeat_disagreements,
        difficulty_shadow_timeout=30,text_json_mode=True,document_backend='legacy',retrieval_expansion='none',
        text=replace(base.text,extra={'thinking':{'type':'disabled'},'max_tokens':8192}),
        harness_reasoning_effort='off',harness_response_format='json_object',harness_schema_repairs=1,
        harness_max_requests=4,harness_max_output_tokens=8192)
    settings.text.require('text');settings.embedding.require('embedding')
    app=create_app(settings);store=app.state.store
    original_reserve=store.reserve_call
    def reserve(job_id,capability,model,limit):
        # One app worker in this isolated database; cap also survives UTC rollover.
        if store.one('SELECT count(*) AS n FROM calls')['n']>=30:raise LocalCallLimit('Validation run cap reached',scope='job')
        return original_reserve(job_id,capability,model,limit)
    store.reserve_call=reserve
    manifest.update(status='running',private_runtime_directory=str(directory),text_model=settings.text.model,embedding_model=settings.embedding.model,primary_runtime=settings.agent_runtime)
    write_json(output/'manifest.json',manifest)
    async with app.router.lifespan_context(app):
      async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver',timeout=120) as client:
        async def request(method,url,**kwargs):
            response=await client.request(method,url,**kwargs)
            if response.status_code>=400:raise RuntimeError(f'{method} {url}: HTTP {response.status_code}')
            return response.json()
        session=await request('POST','/api/auth/register',json={'email':f'shadow-{secrets.token_hex(5)}@example.invalid','password':secrets.token_urlsafe(24),'display_name':'旁路验证'})
        client.headers['x-csrf-token']=session['csrf_token']
        async def wait_job(id):
            start=time.monotonic()
            while True:
                row=await request('GET',f'/api/jobs/{id}')
                if row['status'] not in ('queued','running'):return row
                if time.monotonic()-start>600:
                    await request('POST',f'/api/jobs/{id}/cancel');raise RuntimeError('Validation job timed out; cancellation requested')
                await asyncio.sleep(.5)
        course_ids={};document_ids={}
        for course_name,documents in source_groups.items():
            course=await request('POST','/api/courses',json={'name':'旁路验证：'+course_name})
            course_ids[course_name]=course['id'];document_ids[course_name]=[]
            for source in documents:
                document=await request('POST','/api/documents',data={'course_id':course['id']},files={'file':(source['id']+'.md',source['text'].encode(),'text/markdown')})
                document_ids[course_name].append(document['id'])
                index=await request('POST',f"/api/documents/{document['id']}/index")
                indexed=await wait_job(index['job_id'])
                write_json(output/f'index_{source["id"]}_job.json',indexed)
                if indexed['status']!='succeeded':raise RuntimeError('Real indexing failed: '+str(indexed.get('error')))
            print('Uploaded and indexed course with real embedding API:',course_name,flush=True)
        manifest.update(course_ids=course_ids,document_ids=document_ids)
        tasks=[]
        for n,case in enumerate(cases,1):
            payload={'course_id':course_ids[case['course']],'topic':case['topic'],'difficulty':case['difficulty'],'question_type':case['question_type'],
                'count':1,'language':case['language'],'document_ids':document_ids[case['course']],'request_key':f'shadow-real-{n}-{secrets.token_hex(6)}',
                'learner_profile':case['learner_profile'],
                'include_explanations':True,'use_subagents':True}
            submitted=await request('POST','/api/generations',json=payload)
            print('Generation submitted:',submitted['job_id'],flush=True)
            job=await wait_job(submitted['job_id']);evidence=await request('GET',f"/api/jobs/{submitted['job_id']}/evidence")
            write_json(output/f'task_{n}.json',job);write_json(output/f'task_{n}_evidence.json',evidence)
            entry={'case_id':case['id'],'job_id':job['id'],'status':job['status'],'shadow':job.get('difficulty_shadow')}
            if job['status']=='succeeded':
                content=await request('GET',f"/api/contents/{job['result']['content_id']}")
                write_json(output/f'task_{n}_content.json',content)
                before=store.one('SELECT count(*) AS n FROM calls')['n']
                duplicate=await request('POST','/api/generations',json=payload)
                after=store.one('SELECT count(*) AS n FROM calls')['n']
                assert duplicate['job_id']==job['id'] and duplicate['reused'] and before==after
                entry.update(content_id=job['result']['content_id'],idempotent_replay_no_new_calls=True)
            tasks.append(entry);write_json(output/'tasks.json',tasks)
            print('Generation result:',json.dumps(entry,ensure_ascii=False),flush=True)
        manifest.update(status='complete',tasks=tasks)
    calls=call_rows(store);write_json(output/'calls.json',calls)
    manifest.update(actual_calls=len(calls),total_tokens=sum(c['usage'].get('total_tokens',0) for c in calls),calls_without_cost=sum('cost' not in c['usage'] for c in calls))
    write_json(output/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='code_sha256'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dataset-case',action='append',help='A frozen Q1 development case; index every source document in its course')
    parser.add_argument('--repeat-disagreements',action='store_true',help='One extra difficulty judgement and audit on eligible audited disagreements')
    parser.add_argument('--shadow-max-calls',type=int,default=2)
    args=parser.parse_args()
    if not 0<=args.shadow_max_calls<=12 or (args.repeat_disagreements and args.shadow_max_calls<4):
        parser.error('Repeated disagreements require at least four shadow calls; overall shadow cap is 0-12')
    try:
        asyncio.run(run(args))
    except Exception as exc:
        path=args.output.resolve()/'manifest.json'
        if path.exists():
            manifest=json.loads(path.read_text());manifest.update(status='failed',error_type=type(exc).__name__)
            if manifest.get('private_runtime_directory'):
                from app.store import Store
                calls=call_rows(Store(Path(manifest['private_runtime_directory'])))
                write_json(args.output/'calls.json',calls);manifest['actual_calls']=len(calls)
            write_json(path,manifest)
        raise
