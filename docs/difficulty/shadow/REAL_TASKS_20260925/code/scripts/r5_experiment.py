"""R5: frozen query-translation ablation on public bilingual data only."""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import numpy as np
from app.config import Settings
from app.providers import ApiProviders, ProviderError, safe_usage
from app.rag_candidates import TokenCounter, token_chunks, title_input, query_input
from app.retrieval import rank_chunks
from scripts.build_mlqa_cs_benchmark import read_records, doc_id, ARCHIVE_SHA
from scripts.chunk_experiment import gold_spans, span_metrics
from scripts.r4_experiment import context_rows

R4 = ROOT/'docs/rag/r4-experiments/20260912T072619024568Z'
PROTOCOL = ROOT/'docs/rag/R5_PROTOCOL_V1.md'
TITLES = ('World Wide Web','Google','Google Glass','JavaOne','Microsoft','Microsoft MapPoint',
          'Microsoft Security Essentials','Microsoft Visual Studio','Task Manager (Windows)',
          'Windows NT','DirectX','Pulse-code modulation','Margaret Hamilton (software engineer)')
ARMS = ('original', 'translated', 'dual')
TRANSLATION_SYSTEM = ('You translate computer-science questions for document retrieval. '
    'Translate only the supplied question into the requested language. Do not answer it, infer missing referents, '
    'add facts, explanations or context. Preserve all numeric literals, abbreviations, code identifiers, URLs '
    'and named entities exactly. Retain original technical names in parentheses when helpful. '
    'Return exactly one JSON object with one string field: translation.')


def sha(value): return hashlib.sha256(value).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
def load(path): return json.loads(path.read_text())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(path)


def compact(record):
    return {k:v for k,v in record.items() if k not in ('result','visible_output')}


def build_dataset():
    previous=load(R4/'dataset.json')
    seen_ids={q['family_id'] for q in previous['queries']}
    seen_texts={d['text'] for d in previous['documents']}
    dev_ids=set(sorted(seen_ids,key=lambda k:sha(('r5-dev:'+k).encode()))[:24])
    ds=dict(previous, documents=list(previous['documents']), queries=[dict(q,split='dev',r4_split=q['split'])
        for q in previous['queries'] if q['family_id'] in dev_ids], dataset_id='mlqa-software-r5-translation-v1')
    documents={d['id']:d for d in ds['documents']}
    source=ROOT/'benchmarks/rag/external/mlqa/MLQA_V1.zip'
    if sha(source.read_bytes())!=ARCHIVE_SHA: raise ValueError('MLQA archive changed.')
    decisions=[]
    with zipfile.ZipFile(source) as z:
        for split in ('dev','test'):
            en,zh=(read_records(z,split,l) for l in ('en','zh'))
            for qid in sorted(en.keys() & zh.keys()):
                if en[qid]['title'] not in TITLES: continue
                reason=('seen_family' if qid in seen_ids else 'seen_context' if
                    en[qid]['context'] in seen_texts or zh[qid]['context'] in seen_texts else 'included')
                decisions.append({'family_id':qid,'title':en[qid]['title'],'official_split':split,'decision':reason})
                if reason!='included': continue
                known=[doc_id(l,row['context']) for l,row in (('en',en[qid]),('zh',zh[qid]))]
                for lang,row in (('en',en[qid]),('zh',zh[qid])):
                    pid=doc_id(lang,row['context'])
                    documents[pid]={'id':pid,'text':row['context'],'title':row['title'],'language':lang,
                        'source':'MLQA_V1','source_member':row['source_member'],'license':'CC-BY-SA-3.0',
                        'text_sha256':sha(row['context'].encode())}
                    ds['queries'].append({'id':qid+'-'+lang,'family_id':qid,'text':row['question'],
                        'split':'test','official_split':split,'language':lang,'category':'human_parallel_qa',
                        'answerable':True,'relevance':dict.fromkeys(known,2),'required_evidence_groups':[known],
                        'original_context_id':pid,'original_answers':row['answers'],'source_member':row['source_member']})
    ds['documents']=list(documents.values())
    ds['evaluation_scope']='Public software-related Wikipedia, not course gold; new family/context held-out from R4.'
    ds['provenance']=dict(previous['provenance'],r5={'new_titles':TITLES,'r4_sha256':sha((R4/'dataset.json').read_bytes()),
        'dev_selection':'24 families by SHA256(r5-dev:family_id); all previously exposed',
        'test_selection':'all new paired families under fixed whitelist, either old context excluded'})
    return ds,decisions


def components(queries):
    parent={q['family_id']:q['family_id'] for q in queries}
    def find(k):
        while parent[k]!=k: parent[k]=parent[parent[k]];k=parent[k]
        return k
    seen={}
    for q in queries:
        for pid in q['relevance']:
            if pid in seen:
                a,b=find(q['family_id']),find(seen[pid]);parent[max(a,b)]=min(a,b)
            seen[pid]=q['family_id']
    return {k:find(k) for k in parent}


def endpoints(settings):
    return {cap:{'base_url':getattr(settings,cap).base_url,'path':getattr(settings,cap).path,
                 'model':getattr(settings,cap).model,'signature':getattr(settings,cap).signature}
            for cap in ('text','embedding','rerank')}


def freeze():
    ds,decisions=build_dataset(); gold=gold_spans(ds)
    queries={s:[q for q in ds['queries'] if q['split']==s] for s in ('dev','test')}
    assert {s:len(qs) for s,qs in queries.items()}=={'dev':48,'test':62}
    settings=Settings.from_env()
    if (settings.text.model,settings.embedding.model,settings.rerank.model)!=('deepseek-flash','qwen/qwen3-embedding-8b','qwen/qwen3-reranker-8b'):
        raise ValueError('Configured providers differ from the planned experiment.')
    run=ROOT/'docs/rag/r5-experiments'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    shutil.copyfile(R4/'tokenizer.json',run/'tokenizer.json');counter=TokenCounter(run/'tokenizer.json')
    chunks=[]
    for d in ds['documents']:
        for c in token_chunks(d,counter,256):
            c['title_text']=title_input(c['text'],d['title'],c['metadata']['heading_path']);chunks.append(c)
    requests={q['id']:{'source':q['text'],'target_language':'zh' if q['language']=='en' else 'en'} for q in ds['queries']}
    for name,value in [('dataset',ds),('selection-decisions',decisions),('gold-spans',gold),('chunks',chunks),
                       ('translation-inputs',requests),('providers',endpoints(settings))]:save(run/(name+'.json'),value)
    save(run/'components.json',{s:components(qs) for s,qs in queries.items()})
    shutil.copyfile(PROTOCOL,run/'protocol.md')
    for p in [*ROOT.glob('app/*.py'),ROOT/'scripts/r5_experiment.py',ROOT/'scripts/r4_experiment.py',
        ROOT/'scripts/chunk_experiment.py',ROOT/'scripts/build_mlqa_cs_benchmark.py',
        ROOT/'scripts/rag_experiment.py',ROOT/'scripts/rag_history.py']:
        dest=run/'code'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    files=['dataset.json','gold-spans.json','chunks.json','translation-inputs.json','providers.json','components.json','protocol.md','tokenizer.json']
    save(run/'freeze.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),
        'files_sha256':{n:sha((run/n).read_bytes()) for n in files},
        'code_sha256':{str(p.relative_to(run/'code')):sha(p.read_bytes()) for p in (run/'code').rglob('*.py')},
        'rows':{s:len(qs) for s,qs in queries.items()},'families':{s:len({q['family_id'] for q in qs}) for s,qs in queries.items()},
        'components':{s:len(set(components(qs).values())) for s,qs in queries.items()},
        'documents':len(ds['documents']),'chunks':len(chunks),
        'previous_r4_embedding_manifest_sha256':sha((R4/'embedding-manifest.json').read_bytes())})
    print(run,flush=True)


def verify(run):
    f=load(run/'freeze.json')
    for name,want in f['files_sha256'].items():
        if sha((run/name).read_bytes())!=want:raise ValueError('Frozen file changed: '+name)
    for name,want in f['code_sha256'].items():
        if sha((ROOT/name).read_bytes())!=want:raise ValueError('Frozen code changed: use archived code. '+name)


def protected_literals(text):
    patterns=[r'\d+(?:\.\d+)*',r'`[^`]+`',r'\b[A-Z]{2,}[A-Z0-9_]*\b',
              r'\b[A-Za-z]+_[A-Za-z0-9_]+\b',r'\b[a-z]+[A-Z][A-Za-z0-9]*\b']
    return sorted(set(m.group().strip('`') for p in patterns for m in re.finditer(p,text)))


def validate_translation(value,request):
    if not isinstance(value,dict) or set(value)!={'translation'}:raise ValueError('translation_json_fields')
    text=value['translation']
    if not isinstance(text,str) or not 1<=len(text.strip())<=1500:raise ValueError('translation_length')
    text=text.strip()
    if text.casefold()==request['source'].strip().casefold():raise ValueError('translation_unchanged')
    if not re.search(r'[\u3400-\u9fff]' if request['target_language']=='zh' else '[A-Za-z]',text):
        raise ValueError('translation_target_characters')
    missing=[p for p in protected_literals(request['source']) if p not in text]
    if missing:raise ValueError('translation_missing_literals')
    return text


def interleave(first,second,k=20):
    result=[];seen=set();positions=[0,0];lists=[first,second]
    while len(result)<k:
        progressed=False
        for i,rows in enumerate(lists):
            while positions[i]<len(rows) and rows[positions[i]]['id'] in seen:positions[i]+=1
            if positions[i]<len(rows):
                item=rows[positions[i]];positions[i]+=1;seen.add(item['id']);result.append(item);progressed=True
                if len(result)==k:break
        if not progressed:break
    return result


def parse_vectors(data,count):
    vectors=ApiProviders._vectors(data,count)
    if any(len(v)!=4096 for v in vectors):raise ValueError('Unexpected embedding dimension.')
    return vectors


class Remote:
    def __init__(self,run):
        self.run=run;self.settings=Settings.from_env()
        if endpoints(self.settings)!=load(run/'providers.json'):raise ValueError('Endpoint identity changed.')
        if self.settings.embedding.base_url!='https://openrouter.ai/api/v1' or self.settings.rerank.base_url!=self.settings.embedding.base_url:
            raise ValueError('Unexpected retrieval gateway.')
        if self.settings.text.base_url!='https://api.deepseek.com':raise ValueError('Unexpected translation gateway.')
        self.client=httpx.AsyncClient(timeout=60,follow_redirects=False)
        self.locks={cap:asyncio.Semaphore(4 if cap=='embedding' else 2) for cap in ('text','embedding','rerank')}
        self.calls=load(run/'calls.json') if (run/'calls.json').exists() else {}
        if any(c['status']=='started' for c in self.calls.values()):raise ValueError('Previous uncertain requests require audit; no automatic retry.')
        self.inflight={};self.guard=asyncio.Lock();self.reserved=0.;self.halt=False

    async def call(self,cap,payload,validator):
        ep=getattr(self.settings,cap);body=dict(payload,model=ep.model)
        key=sha(canonical({'capability':cap,'endpoint':load(self.run/'providers.json')[cap],'body':body}))
        async with self.guard:
            if key in self.calls and key not in self.inflight:return load(self.run/self.calls[key]['response_file'])
            if key not in self.inflight:self.inflight[key]=asyncio.create_task(self._one(key,cap,ep,body,validator))
            task=self.inflight[key]
        return await task

    async def _one(self,key,cap,ep,body,validator):
        async with self.locks[cap]:
            async with self.guard:
                if self.halt:raise ValueError('Batch stopped after missing metering.')
                caps={'text':110,'embedding':260,'rerank':660}
                if sum(c['capability']==cap for c in self.calls.values())>=caps[cap]:raise ValueError('Request cap reached.')
                spent=sum(c.get('usage',{}).get('cost',0) for c in self.calls.values() if c['capability']!='text')
                if cap!='text':
                    if spent+self.reserved+.01>2.:raise ValueError('OpenRouter cost cap reached.')
                    self.reserved+=.01
                record={'capability':cap,'status':'started','usage':{},'requested_model':ep.model,
                        'response_file':'responses/'+key+'.json'}
                self.calls[key]=dict(record);save(self.run/'calls.json',self.calls)
            began=time.perf_counter();record['status']='failed'
            try:
                response=await self.client.post(ep.base_url+ep.path,headers={'Authorization':'Bearer '+ep.api_key},json=body)
                record['http_status']=response.status_code
                if response.status_code==200:
                    data=response.json();record['usage']=safe_usage(data.get('usage'))
                    for field in ('model','provider'):
                        v=data.get(field)
                        if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_:/@.+ -]{1,160}',v) and not any(
                            e.api_key and e.api_key in v for e in [self.settings.text,self.settings.embedding,self.settings.rerank]):record[field]=v
                    if cap=='text':
                        choice=data['choices'][0];raw=choice['message']['content']
                        if isinstance(raw,str):
                            echo=any(e.api_key and e.api_key in raw for e in [self.settings.text,self.settings.embedding,self.settings.rerank])
                            if echo:raise ValueError('translation_credential_echo')
                            record['visible_output']=raw[:6000]
                        if choice.get('finish_reason')!='stop':raise ValueError('translation_incomplete_output')
                    record['result']=validator(data);record['status']='succeeded'
            except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError,ProviderError) as exc:
                record['error_type']=type(exc).__name__
                if cap=='text' and isinstance(exc,ValueError) and str(exc).startswith('translation_'):record['validation_error']=str(exc)
            finally:
                record['duration_ms']=(time.perf_counter()-began)*1000
                record['finished_at']=datetime.now(timezone.utc).isoformat()
                async with self.guard:
                    if cap!='text':self.reserved-=.01
                    save(self.run/record['response_file'],record)
                    self.calls[key]=compact(record);save(self.run/'calls.json',self.calls)
            if cap!='text' and record['status']=='succeeded' and 'cost' not in record['usage']:
                self.halt=True
                raise ValueError('Missing OpenRouter metering; stop further batches.')
            return record

    async def close(self):await self.client.aclose()


async def translate(run):
    verify(run);requests=load(run/'translation-inputs.json');remote=Remote(run)
    result=load(run/'translations.json') if (run/'translations.json').exists() else {}
    async def one(key,request):
        if key in result:return
        def validator(data):return validate_translation(json.loads(data['choices'][0]['message']['content']),request)
        record=await remote.call('text',{'messages':[{'role':'system','content':TRANSLATION_SYSTEM},
            {'role':'user','content':json.dumps(request,ensure_ascii=False)}], 'temperature':0,'max_tokens':192,
            'thinking':{'type':'disabled'},'response_format':{'type':'json_object'},'stream':False},validator)
        result[key]=record;save(run/'translations.json',result)
        if len(result)%10==0 or len(result)==1:print('Translated',len(result),'/',len(requests),flush=True)
    try:await asyncio.gather(*(one(k,v) for k,v in requests.items()))
    finally:await remote.close()


async def embed(run):
    verify(run);remote=Remote(run);chunks=load(run/'chunks.json');queries=load(run/'dataset.json')['queries']
    translations=load(run/'translations.json');manifest=load(R4/'embedding-manifest.json')
    if manifest['embedding_signature']!=remote.settings.embedding.signature or manifest['npz_sha256']!=sha((R4/'embeddings.npz').read_bytes()):
        raise ValueError('Previous embedding cache identity changed.')
    previous=np.load(R4/'embeddings.npz',allow_pickle=False)
    vectors=dict(zip(previous['keys'].tolist(),previous['vectors'].tolist()))
    document_inputs={sha(c['title_text'].encode()):c['title_text'] for c in chunks}
    missing=[(k,v) for k,v in document_inputs.items() if k not in vectors]
    query_results=load(run/'query-embeddings.json') if (run/'query-embeddings.json').exists() else {}
    try:
        for start in range(0,len(missing),16):
            batch=missing[start:start+16]
            record=await remote.call('embedding',{'input':[v for _,v in batch],'encoding_format':'float'},lambda d:parse_vectors(d,len(batch)))
            if record['status']!='succeeded':raise ValueError('Document embedding failed; do not grade an incomplete corpus.')
            vectors.update(zip([k for k,_ in batch],record['result']))
        keys=sorted(document_inputs)
        np.savez_compressed(run/'document-vectors.npz',keys=np.array(keys),vectors=np.array([vectors[k] for k in keys],dtype=np.float64))
        save(run/'document-vector-manifest.json',{'sha256':sha((run/'document-vectors.npz').read_bytes()),
            'inputs':len(keys),'new':len(missing),'reused':len(keys)-len(missing),'embedding_signature':manifest['embedding_signature']})
        async def one(q,kind,text):
            key=q['id']+':'+kind
            if key in query_results:return
            record=await remote.call('embedding',{'input':[query_input(text,True)],'encoding_format':'float'},lambda d:parse_vectors(d,1))
            query_results[key]=compact(record);save(run/'query-embeddings.json',query_results)
            if len(query_results)%20==0:print('Query vectors',len(query_results),flush=True)
        tasks=[]
        for q in queries:
            tasks.append(one(q,'original',q['text']))
            t=translations[q['id']]
            if t['status']=='succeeded':tasks.append(one(q,'translated',t['result']))
        await asyncio.gather(*tasks)
    finally:await remote.close()


def rank(run,split):
    verify(run)
    if split=='test' and not (run/'selection-lock.json').exists():raise ValueError('Lock dev before test ranking.')
    if split=='dev' and (run/'test-candidates.json').exists():raise ValueError('Test exposed; no dev retuning.')
    ds=load(run/'dataset.json');trs=load(run/'translations.json');qvec=load(run/'query-embeddings.json')
    if load(run/'document-vector-manifest.json')['sha256']!=sha((run/'document-vectors.npz').read_bytes()):raise ValueError('Vector cache changed.')
    data=np.load(run/'document-vectors.npz',allow_pickle=False);vectors=dict(zip(data['keys'].tolist(),data['vectors']))
    chunks=[dict(c,vector=vectors[sha(c['title_text'].encode())].tolist()) for c in load(run/'chunks.json')]
    out={}
    for q in ds['queries']:
        if q['split']!=split:continue
        for mode in ('mixed','cross'):
            eligible=[c for c in chunks if mode=='mixed' or c['language']!=q['language']]
            ranks={};times={}
            for kind in ('original','translated'):
                record=qvec.get(q['id']+':'+kind,{})
                if record:record=load(run/record['response_file'])
                began=time.perf_counter()
                text=q['text'] if kind=='original' else trs[q['id']].get('result','')
                ranks[kind]=rank_chunks(eligible,text,record['result'][0],strategy='hybrid_dense_lexical_v1',top_k=20,candidate_k=20) if record.get('status')=='succeeded' else []
                times[kind]=(time.perf_counter()-began)*1000
            began=time.perf_counter();ranks['dual']=interleave(ranks['original'],ranks['translated'])
            times['dual']=times['original']+times['translated']+(time.perf_counter()-began)*1000
            for arm in ARMS:
                selected=ranks[arm]
                request={'query':q['text'],'documents':[c['title_text'] for c in selected],'top_n':len(selected)}
                out[q['id']+':'+mode+':'+arm]={'query_id':q['id'],'mode':mode,'arm':arm,'ids':[c['id'] for c in selected],
                    'ranking_ms':times[arm],'request':request,'request_sha256':sha(canonical(request)),
                    'translation_fallback':arm=='dual' and not ranks['translated'],
                    'original_branch_unavailable':not ranks['original']}
    save(run/(split+'-candidates.json'),out);print('Candidate rows',split,len(out),flush=True)


async def rerank(run,split):
    verify(run)
    if split=='test' and not (run/'selection-lock.json').exists():raise ValueError('Missing selection lock.')
    candidates=load(run/(split+'-candidates.json'))
    unique={c['request_sha256']:c['request'] for c in candidates.values() if c['ids']}
    remote=Remote(run);result=load(run/(split+'-rerank.json')) if (run/(split+'-rerank.json')).exists() else {}
    async def one(key,request):
        if key in result:return
        result[key]=await remote.call('rerank',request,lambda data:ApiProviders._rerank_scores(data,len(request['documents'])))
        save(run/(split+'-rerank.json'),result)
        if len(result)%25==0 or len(result)==1:print('Reranked',split,len(result),'/',len(unique),flush=True)
    try:await asyncio.gather(*(one(k,unique[k]) for k in sorted(unique)))
    finally:await remote.close()


def summarize(rows):
    groups=defaultdict(list)
    for row in rows:
        for group in ('all','mode:'+row['mode'],'language:'+row['language'],row['mode']+':'+row['language']):groups[row['arm'],group].append(row)
    return [dict(arm=arm,group=group,rows=len(values),**{k:statistics.mean(r[k] for r in values) for k in
        ('budget_hit','top5_hit','mrr5','candidate_hit20','context_tokens','stage_sum_estimate_ms','translation_ms','query_embedding_ms','rerank_ms')},
        failures=sum(r['status']!='succeeded' for r in values),translation_fallbacks=sum(r['translation_fallback'] for r in values))
        for (arm,group),values in groups.items()]


def metrics(run,split):
    verify(run);ds=load(run/'dataset.json');gold=load(run/'gold-spans.json')
    candidates=load(run/(split+'-candidates.json'));scores=load(run/(split+'-rerank.json'))
    chunks={c['id']:c for c in load(run/'chunks.json')};parents={d['id']:d for d in ds['documents']}
    qvec=load(run/'query-embeddings.json');translations=load(run/'translations.json');counter=TokenCounter(run/'tokenizer.json')
    rows=[];rankings={}
    for q in ds['queries']:
        if q['split']!=split:continue
        for mode in ('mixed','cross'):
            spans=[s for s in gold[q['id']] if mode=='mixed' or s['language']!=q['language']]
            for arm in ARMS:
                key=q['id']+':'+mode+':'+arm;c=candidates[key];selected=[chunks[cid] for cid in c['ids']]
                result=scores.get(c['request_sha256'],{'status':'failed','duration_ms':0})
                ranked=([selected[i] for i in sorted(range(len(selected)),key=lambda i:(-result['result'][i],i))]
                        if result['status']=='succeeded' else [])
                translation_ms=translations[q['id']]['duration_ms'] if arm!='original' else 0
                original_ms=qvec.get(q['id']+':original',{}).get('duration_ms',0)
                translated_ms=qvec.get(q['id']+':translated',{}).get('duration_ms',0)
                pre_ms=original_ms if arm=='original' else translation_ms+translated_ms
                if arm=='dual':pre_ms=max(original_ms,translation_ms+translated_ms)
                metric=context_rows(ranked,q,spans,parents,counter,'none')
                metric['candidate_hit20']=int(any(span_metrics([ch],spans)['known_span_hit'] for ch in selected))
                rows.append(dict(arm=arm,query_id=q['id'],family_id=q['family_id'],language=q['language'],mode=mode,split=split,
                    status=result['status'],translation_fallback=c['translation_fallback'],translation_ms=translation_ms,
                    query_embedding_ms=original_ms if arm=='original' else translated_ms,
                    rerank_ms=result['duration_ms'],ranking_ms=c['ranking_ms'],
                    stage_sum_estimate_ms=pre_ms+c['ranking_ms']+result['duration_ms'],**metric))
                rankings[key]=[ch['id'] for ch in ranked]
    save(run/(split+'-per-query.json'),rows);save(run/(split+'-rankings.json'),rankings)
    summary=summarize(rows);save(run/(split+'-summary.json'),summary)
    for r in summary:
        if r['group']=='all':print(r['arm'],'Hit',round(r['budget_hit'],4),'MRR',round(r['mrr5'],4),'candidate',round(r['candidate_hit20'],4),flush=True)


def lock(run):
    if (run/'selection-lock.json').exists() or (run/'test-candidates.json').exists():raise ValueError('Cannot choose after lock/test.')
    rows=load(run/'dev-summary.json');values=[r for r in rows if r['group']=='all']
    if {r['arm'] for r in values}!=set(ARMS):raise ValueError('Incomplete dev.')
    winner=max(values,key=lambda r:(r['budget_hit'],r['mrr5'],-ARMS.index(r['arm'])))['arm']
    save(run/'selection-lock.json',{'selected_arm':winner,'basis':'dev_only','locked_at':datetime.now(timezone.utc).isoformat(),
        'dev_summary_sha256':sha(canonical(rows))});print('Locked',winner)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('freeze','translate','embed','rank','rerank','metrics','lock'))
    p.add_argument('--run',type=Path);p.add_argument('--split',choices=('dev','test'),default='dev');a=p.parse_args()
    if a.stage=='freeze':freeze()
    else:
        if a.run is None:p.error('--run required')
        began=time.perf_counter()
        if a.stage in ('translate','embed'):asyncio.run(globals()[a.stage](a.run))
        elif a.stage=='rerank':asyncio.run(rerank(a.run,a.split))
        elif a.stage in ('rank','metrics'):globals()[a.stage](a.run,a.split)
        else:lock(a.run)
        save(a.run/(f'stage-{a.stage}-{a.split}.json'),{'stage':a.stage,'split':a.split,'wall_seconds':time.perf_counter()-began,
            'finished_at':datetime.now(timezone.utc).isoformat()})
