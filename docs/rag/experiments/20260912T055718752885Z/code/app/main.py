from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import csv
import hashlib
import io
import json
import sqlite3
from urllib.parse import urlparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings
from .store import Store, uid, now, dumps, Conflict
from .providers import ApiProviders
from .pipeline import Pipeline, parse_document, validate_asset
from .models import CourseCreate, GenerateRequest, ReviewRequest, MediaRequest, MediaReview, EvaluationRequest, LearningAsset

STATIC=Path(__file__).parent/'static'

def create_app(settings=None,providers_factory=ApiProviders):
    settings=settings or Settings.from_env()
    store=Store(settings.data_dir)
    providers=providers_factory(settings,store)
    pipeline=Pipeline(settings,store,providers)
    @asynccontextmanager
    async def lifespan(app):
        await pipeline.start()
        yield
        await pipeline.stop()
    app=FastAPI(title='FYP Education Studio',version='0.1.0',lifespan=lifespan)
    app.state.store=store;app.state.pipeline=pipeline;app.state.settings=settings
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])
    @app.middleware('http')
    async def origin_guard(request,call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'仅允许同源页面操作本地应用。'},403)
        result=await call_next(request)
        result.headers['X-Content-Type-Options']='nosniff'
        result.headers['X-Frame-Options']='DENY'
        result.headers['Cache-Control']='no-store'
        return result
    app.mount('/static',StaticFiles(directory=STATIC),name='static')

    def need_course(cid):
        if not store.one('SELECT id FROM courses WHERE id=?',(cid,)):raise HTTPException(404,'课程不存在')
    def need_content(cid):
        row=store.one('SELECT * FROM contents WHERE id=?',(cid,))
        if not row:raise HTTPException(404,'材料不存在')
        return row
    def difficulty_assessment_for(row):
        config=json.loads(row['config']) if isinstance(row['config'],str) else row['config']
        asset=json.loads(row['asset']) if isinstance(row['asset'],str) else row['asset']
        result={'status':'legacy_unverified','version':None,'items':[],
                'limitation':'模型按认知要求复核，不等于教师确认或学生实际作答难度。'}
        if 'difficulty_plan' not in config:return result
        if not asset['questions']:return result|{'status':'not_applicable'}
        saved=store.one('SELECT evidence FROM job_evidence WHERE job_id=?',(row['job_id'],))
        attempts=json.loads(saved['evidence']).get('attempts',[]) if saved else []
        for attempt in reversed(attempts):
            assessment=attempt.get('assessment')
            if attempt.get('status')=='valid' and isinstance(assessment,dict):
                response=assessment.get('response',assessment)
                result.update(version=1,items=response.get('items',[]))
                break
        result['status']='model_checked' if row['version']==1 and result['items'] else 'needs_review'
        return result
    def require(*capabilities):
        for cap in capabilities:
            try:getattr(settings,cap).require(cap)
            except ValueError as exc:raise HTTPException(503,str(exc)) from None
    def submit(key,kind,payload):
        try:job,new=store.job(key,kind,payload)
        except Conflict as exc:raise HTTPException(409,str(exc)) from None
        if new:pipeline.enqueue(job['id'])
        return {'job_id':job['id'],'status':job['status'],'reused':not new}

    @app.get('/')
    async def index():return FileResponse(STATIC/'index.html')
    @app.get('/api/status')
    async def status():
        try:retrieval=pipeline.retrieval_configuration()
        except ValueError as exc:raise HTTPException(503,'检索配置无效：'+str(exc)) from None
        caps={name:{'configured':getattr(settings,name).configured,'model':getattr(settings,name).model} for name in ('text','embedding','speech','image')}
        used=store.one('SELECT count(*) AS n FROM calls WHERE substr(created_at,1,10)=?',(now()[:10],))['n']
        return {'version':'0.1.0','capabilities':caps,'calls_today':used,'daily_call_limit':settings.max_daily_calls,'mode':'local-development',
                'retrieval':retrieval}
    @app.get('/api/courses')
    async def courses():return store.all('SELECT * FROM courses ORDER BY created_at')
    @app.post('/api/courses',status_code=201)
    async def course_create(payload:CourseCreate):
        row={'id':uid(),'name':payload.name,'created_at':now()}
        store.execute('INSERT INTO courses VALUES(?,?,?)',tuple(row.values()));return row
    @app.get('/api/documents')
    async def documents(course_id:str):
        need_course(course_id)
        rows=store.all('SELECT d.*,count(c.id) AS chunks FROM documents d LEFT JOIN chunks c ON c.document_id=d.id WHERE course_id=? GROUP BY d.id ORDER BY d.created_at DESC',(course_id,))
        for row in rows:
            incompatible=store.one('SELECT count(*) AS n FROM chunks WHERE document_id=? AND (embedding_signature IS NULL OR embedding_signature!=?)',(row['id'],settings.embedding.signature))['n']
            row['index_current']=not incompatible and row['status']=='ready'
        return rows
    @app.post('/api/documents',status_code=201)
    async def upload(course_id:str=Form(...),file:UploadFile=File(...)):
        need_course(course_id)
        raw=await file.read(settings.max_upload_bytes+1)
        if len(raw)>settings.max_upload_bytes:raise HTTPException(413,'单个文件最多 10 MB')
        name=Path(file.filename or 'document.txt').name[:180]
        try:pages,chunks=await asyncio.to_thread(parse_document,name,raw,settings.max_pages,settings.max_chunks)
        except ValueError as exc:raise HTTPException(400,str(exc)) from None
        digest=hashlib.sha256(raw).hexdigest()
        previous=store.one('SELECT * FROM documents WHERE course_id=? AND sha256=?',(course_id,digest))
        if previous:return previous|{'duplicate':True}
        did=uid();row={'id':did,'course_id':course_id,'name':name,'sha256':digest,'status':'parsed','pages':len(pages),'created_at':now()}
        try:
            with store.connect() as db:
                db.execute('INSERT INTO documents VALUES(:id,:course_id,:name,:sha256,:status,:pages,:created_at)',row)
                db.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?)',[(c['id'],did,c['page'],c['text'],None,None) for c in chunks])
        except sqlite3.IntegrityError:raise HTTPException(409,'该资料已被同时导入，请刷新列表') from None
        folder=settings.data_dir/'documents';folder.mkdir(exist_ok=True)
        (folder/(did+Path(name).suffix.lower())).write_bytes(raw)
        return row|{'chunks':len(chunks)}
    @app.get('/api/documents/{did}/chunks')
    async def chunks(did:str):return store.all('SELECT id,page,text FROM chunks WHERE document_id=? ORDER BY page,rowid',(did,))
    @app.post('/api/documents/{did}/index',status_code=202)
    async def index_document(did:str):
        if not store.one('SELECT id FROM documents WHERE id=?',(did,)):raise HTTPException(404,'资料不存在')
        require('embedding')
        return submit(uid(),'index',{'document_id':did})
    @app.post('/api/generations',status_code=202)
    async def generation(payload:GenerateRequest):
        need_course(payload.course_id);require('text','embedding')
        if payload.document_ids:
            own={r['id'] for r in store.all('SELECT id FROM documents WHERE course_id=?',(payload.course_id,))}
            if not set(payload.document_ids)<=own:raise HTTPException(400,'所选资料不属于该课程')
        return submit(payload.request_key,'generate',payload.model_dump())
    # Expose only navigation metadata; job payloads can include private prompts.
    job_context_sql='''
        SELECT j.id,j.kind,j.status,j.result,j.error,j.created_at,j.updated_at,
            CASE j.kind
                WHEN 'generate' THEN json_extract(j.payload,'$.course_id')
                WHEN 'index' THEN d.course_id
                WHEN 'media' THEN c.course_id
            END AS course_id,
            COALESCE(
                CASE WHEN j.status='succeeded' THEN json_extract(j.result,'$.content_id') END,
                CASE WHEN j.kind='media' THEN json_extract(j.payload,'$.content_id') END
            ) AS content_id
        FROM jobs j
        LEFT JOIN documents d ON j.kind='index' AND d.id=json_extract(j.payload,'$.document_id')
        LEFT JOIN contents c ON j.kind='media' AND c.id=json_extract(j.payload,'$.content_id')
    '''
    @app.get('/api/jobs')
    async def jobs(course_id:str|None=None):
        if course_id is not None:need_course(course_id)
        where=' WHERE course_id=?' if course_id is not None else ''
        return store.all('SELECT id,kind,status,error,created_at,course_id,content_id FROM ('+
            job_context_sql+')'+where+' ORDER BY created_at DESC LIMIT 30',
            (course_id,) if course_id is not None else ())
    @app.get('/api/jobs/{jid}')
    async def job(jid:str):
        row=store.one('SELECT * FROM ('+job_context_sql+') WHERE id=?',(jid,))
        if not row:raise HTTPException(404,'任务不存在')
        row['result']=json.loads(row['result']) if row['result'] else None;return row
    @app.get('/api/jobs/{jid}/evidence')
    async def job_evidence(jid:str):
        row=await job(jid)
        evidence=store.one('SELECT evidence,updated_at FROM job_evidence WHERE job_id=?',(jid,))
        return {'schema_version':'ca1-job-evidence-v1','exported_at':now(),'job':row,
                'evidence':json.loads(evidence['evidence']) if evidence else None,
                'calls':store.calls_for_job(jid),
                'limitations':['Retrieved passages and citation identifiers do not establish factual correctness.',
                               'Call success describes the provider response contract; inspect job and attempt validation separately.']}
    @app.get('/api/contents')
    async def contents(course_id:str|None=None):
        if course_id is not None:need_course(course_id)
        where=' WHERE c.course_id=?' if course_id is not None else ''
        return store.all('''SELECT c.id,c.version,c.status,c.created_at,c.course_id,
            courses.name AS course_name,json_extract(c.asset,'$.title') AS title,
            COALESCE(json_extract(c.config,'$.material'),'quiz') AS material
            FROM contents c JOIN courses ON courses.id=c.course_id'''+where+
            ' ORDER BY c.created_at DESC',(course_id,) if course_id is not None else ())
    @app.get('/api/contents/{cid}')
    async def content(cid:str):
        row=need_content(cid)
        for key in ('asset','sources','config'):row[key]=json.loads(row[key])
        row['media']=store.all('SELECT id,version,kind,mime,status,metadata FROM media WHERE content_id=? AND version=?',(cid,row['version']))
        for item in row['media']:item['metadata']=json.loads(item['metadata'])
        row['difficulty_assessment']=difficulty_assessment_for(row)
        return row
    @app.post('/api/contents/{cid}/review')
    async def review(cid:str,payload:ReviewRequest):
        row=need_content(cid)
        if payload.version!=row['version']:raise HTTPException(409,'内容已更新，请刷新后重试')
        if payload.action=='save' and payload.asset is None:raise HTTPException(400,'保存时必须提供材料')
        if payload.action=='approve' and payload.asset is not None:raise HTTPException(400,'审核不能同时修改内容，请先保存新版本')
        asset=payload.asset or LearningAsset.model_validate_json(row['asset'])
        config=json.loads(row['config'])
        try:validate_asset(asset,GenerateRequest(**({'request_key':'review-validation'}|{k:v for k,v in config.items() if k in GenerateRequest.model_fields})),json.loads(row['sources']),enforce_difficulty='difficulty_plan' in config)
        except ValueError as exc:raise HTTPException(400,str(exc)) from None
        if not asset.evidence_sufficient:raise HTTPException(400,'证据不足的材料不能保存或审核')
        version=row['version']+(payload.action=='save')
        with store.connect() as db:
            changed=db.execute('UPDATE contents SET asset=?,version=?,status=? WHERE id=? AND version=?',
                (dumps(asset.model_dump()),version,'approved' if payload.action=='approve' else 'draft',cid,row['version'])).rowcount
            if not changed:raise HTTPException(409,'内容发生并发更新，请刷新')
            if payload.action=='save':db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(cid,version,dumps(asset.model_dump()),now()))
        return {'id':cid,'version':version,'status':'approved' if payload.action=='approve' else 'draft'}
    @app.post('/api/contents/{cid}/media',status_code=202)
    async def make_media(cid:str,payload:MediaRequest):
        row=need_content(cid)
        if row['version']!=payload.version or row['status']!='approved':raise HTTPException(409,'请先审核当前文本版本')
        require('speech' if payload.kind=='audio' else 'image')
        return submit(payload.request_key,'media',payload.model_dump()|{'content_id':cid})
    @app.get('/api/media/{mid}/file')
    async def media_file(mid:str):
        row=store.one('SELECT * FROM media WHERE id=?',(mid,))
        if not row:raise HTTPException(404,'媒体不存在')
        return FileResponse(settings.data_dir/'media'/row['path'],media_type=row['mime'])
    @app.post('/api/media/{mid}/approve')
    async def approve_media(mid:str,payload:MediaReview):
        row=store.one('SELECT * FROM media WHERE id=?',(mid,))
        if not row:raise HTTPException(404,'媒体不存在')
        content=need_content(row['content_id'])
        if content['version']!=payload.version or row['version']!=payload.version or content['status']!='approved':raise HTTPException(409,'媒体与审核文本版本不一致')
        store.execute("UPDATE media SET status='approved' WHERE id=?",(mid,));return {'status':'approved'}
    @app.get('/api/learn/{cid}')
    async def learn(cid:str,reveal_answers:bool=False):
        row=need_content(cid)
        if row['status']!='approved':raise HTTPException(404,'材料尚未发布')
        asset=json.loads(row['asset'])
        for q in asset['questions']:
            for key in ('slot_id','difficulty','difficulty_design'):q.pop(key,None)
        if not reveal_answers:
            for q in asset['questions']:
                q.pop('answer',None);q.pop('explanation',None);q.pop('difficulty_reason',None)
        asset.pop('visual_prompt',None)
        media=store.all("SELECT id,kind FROM media WHERE content_id=? AND version=? AND status='approved'",(cid,row['version']))
        return {'id':cid,'version':row['version'],'asset':asset,'media':media}
    @app.post('/api/contents/{cid}/evaluations',status_code=201)
    async def evaluation(cid:str,payload:EvaluationRequest):
        row=need_content(cid)
        if row['version']!=payload.version:raise HTTPException(409,'请评价当前版本')
        metrics=payload.model_dump()
        if payload.question_difficulties:
            asset=json.loads(row['asset']);config=json.loads(row['config'])
            questions={q.get('slot_id') or f'q{i}':q for i,q in enumerate(asset['questions'],1)}
            ratings={r.slot_id:r.assessed_difficulty for r in payload.question_difficulties}
            if len(ratings)!=len(payload.question_difficulties) or set(ratings)!=set(questions):
                raise HTTPException(400,'逐题难度评价须覆盖当前版本的全部题目且不能重复；不能判断时请选择“无法判断”。')
            plan={slot['slot_id']:slot['difficulty'] for slot in config.get('difficulty_plan',[])}
            checked=difficulty_assessment_for(row)
            model_levels={item['slot_id']:item['assessed_difficulty'] for item in checked['items']} if checked['status']=='model_checked' else {}
            details=[]
            for slot,level in ratings.items():
                target=plan.get(slot)
                details.append({'slot_id':slot,'assessed_difficulty':level,'target_difficulty':target,
                    'generated_difficulty':questions[slot].get('difficulty'),
                    'model_assessed_difficulty':model_levels.get(slot),
                    'matches_target':level==target if target and level!='uncertain' else None})
            metrics['question_difficulties']=details
            compared=[r for r in details if r['matches_target'] is not None]
            metrics['difficulty_agreement']={'rated':len(details),'compared':len(compared),
                'matched':sum(r['matches_target'] for r in compared),
                'uncertain':sum(r['assessed_difficulty']=='uncertain' for r in details),
                'rate':sum(r['matches_target'] for r in compared)/len(compared) if compared else None,
                'interpretation':'教师判断与目标难度的一致率，不是学生答对率。'}
        eid=uid();store.execute('INSERT INTO evaluations VALUES(?,?,?,?,?)',(eid,cid,payload.version,dumps(metrics),now()))
        return {'id':eid}
    @app.get('/api/difficulty/evaluations/export')
    async def export_difficulty_evaluations():
        out=io.StringIO();writer=csv.writer(out)
        writer.writerow(['evaluation_id','content_id','version','slot_id','target_difficulty','generated_difficulty',
                         'model_assessed_difficulty','teacher_assessed_difficulty','matches_target','created_at'])
        for row in store.all('SELECT * FROM evaluations ORDER BY created_at'):
            for rating in json.loads(row['metrics']).get('question_difficulties',[]):
                writer.writerow([row['id'],row['content_id'],row['version'],rating['slot_id'],rating.get('target_difficulty'),
                    rating.get('generated_difficulty'),rating.get('model_assessed_difficulty'),rating['assessed_difficulty'],
                    rating.get('matches_target'),row['created_at']])
        return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="difficulty-evaluations.csv"'})
    @app.get('/api/evaluations/export')
    async def export_evaluations():
        rows=store.all('SELECT * FROM evaluations ORDER BY created_at');out=io.StringIO()
        writer=csv.writer(out);writer.writerow(['content_id','version','correctness','groundedness','difficulty_match','notes','created_at'])
        for row in rows:
            m=json.loads(row['metrics']);note=m['notes']
            if note.startswith(('=','+','-','@')):note="'"+note
            writer.writerow([row['content_id'],row['version'],m['correctness'],m['groundedness'],m['difficulty_match'],note,row['created_at']])
        return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="evaluations.csv"'})
    @app.get('/api/contents/{cid}/evidence')
    async def export_evidence(cid:str):
        row=need_content(cid)
        config=json.loads(row['config'])
        sources=json.loads(row['sources'])
        config.pop('request_key',None)
        calls=store.calls_for_job(row['job_id'])
        bundle={'schema_version':'ca1-evidence-v1','exported_at':now(),
            'content_id':cid,'version':row['version'],'status':row['status'],
            'asset':json.loads(row['asset']),'sources':sources,'configuration':config,
            'difficulty_assessment':difficulty_assessment_for(row),
            'generation_calls':calls,
            'revisions':[dict(version=r['version'],asset=json.loads(r['asset']),created_at=r['created_at']) for r in store.all('SELECT * FROM revisions WHERE content_id=? ORDER BY version',(cid,))],
            'limitations':['Citation identifiers establish provenance, not factual correctness.',
                'Call records describe initial generation; content may have been edited afterwards.']}
        return Response(dumps(bundle),media_type='application/json',headers={'Content-Disposition':'attachment; filename="ca1-evidence.json"'})
    @app.get('/api/contents/{cid}/export')
    async def export_content(cid:str):
        row=need_content(cid);asset=json.loads(row['asset'])
        text='# '+asset['title']+'\n\n状态：'+row['status']+'\n\n'
        for s in asset['sections']:text+='## '+s['heading']+'\n\n'+s['text']+'\n\n引用片段：'+', '.join(s['citation_ids'])+'\n\n'
        for i,q in enumerate(asset['questions'],1):
            text+=f"## {i}. {q['stem']}\n\n"
            if q.get('difficulty'):
                text+='目标难度：'+{'easy':'简单','medium':'中等','hard':'困难'}[q['difficulty']]+'\n\n'
            text+='\n'.join(chr(65+j)+'. '+s for j,s in enumerate(q['options']))+'\n\n'
            text+='参考答案：'+q['answer']+'\n\n解析：'+q['explanation']+'\n\n引用片段：'+', '.join(q['citation_ids'])+'\n\n'
        text+='## 资料依据\n\n'
        for source in json.loads(row['sources']):text+=f"- {source['document_name']}，第 {source['page']} 页（片段 {source['id']}）\n"
        return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="learning-material.md"'})
    return app
