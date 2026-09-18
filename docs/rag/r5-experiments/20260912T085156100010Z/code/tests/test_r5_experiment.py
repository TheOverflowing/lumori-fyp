import asyncio
import json
from pathlib import Path
import httpx
import pytest
from scripts import r5_experiment as r5
from app.config import Settings,Endpoint


def test_interleave_preserves_both_routes_without_double_counting():
    row=lambda n:{'id':str(n)}
    first=list(map(row,range(20)));second=list(map(row,range(10,30)))
    result=r5.interleave(first,second)
    assert len(result)==20 and len({r['id'] for r in result})==20
    assert [r['id'] for r in result[:4]]==['0','10','1','11']
    assert r5.interleave(first,[])==first
    assert r5.interleave([],second)==second
    assert r5.interleave(first,first)==first


@pytest.mark.parametrize('source,target,text',[
    ('Explain TCP port 443.','zh','解释 TCP 的 443 端口。'),
    ('解释 TCP 的 443 端口。','en','Explain TCP port 443.'),
    ('What does getValue return?','zh','getValue 返回什么？')])
def test_translation_keeps_technical_literals(source,target,text):
    assert r5.validate_translation({'translation':text},{'source':source,'target_language':target})==text


@pytest.mark.parametrize('value',[{}, {'translation':'解释端口。'}, {'translation':'Explain TCP port 443.'},
    {'translation':''},{'translation':'解释 TCP 的 443 端口。','answer':'extra'}])
def test_invalid_translation_is_rejected(value):
    with pytest.raises(ValueError):r5.validate_translation(value,{'source':'Explain TCP port 443.','target_language':'zh'})


def test_context_components_keep_shared_sources_together():
    rows=[{'family_id':'a','relevance':{'p':2,'q':2}},
          {'family_id':'b','relevance':{'q':2,'r':2}},
          {'family_id':'c','relevance':{'x':2}}]
    c=r5.components(rows)
    assert c['a']==c['b'] and c['a']!=c['c']


def test_new_queries_are_disjoint_from_all_previous_families_and_contexts():
    ds,_=r5.build_dataset();old=r5.load(r5.R4/'dataset.json')
    old_ids={q['family_id'] for q in old['queries']};old_contexts={d['text'] for d in old['documents']}
    parents={d['id']:d for d in ds['documents']}
    test=[q for q in ds['queries'] if q['split']=='test']
    assert len(test)==62 and len({q['family_id'] for q in test})==31
    assert not old_ids & {q['family_id'] for q in test}
    assert all(parents[q['original_context_id']]['text'] not in old_contexts for q in test)
    r5.gold_spans(ds)


def test_inflight_dedup_waits_for_completion_and_failed_calls_are_shared(tmp_path,monkeypatch):
    settings=Settings(text=Endpoint('https://api.deepseek.com','fixture-t','deepseek-flash','/chat/completions'),
        embedding=Endpoint('https://openrouter.ai/api/v1','fixture-e','qwen/qwen3-embedding-8b','/embeddings'),
        rerank=Endpoint('https://openrouter.ai/api/v1','fixture-e','qwen/qwen3-reranker-8b','/rerank'))
    r5.save(tmp_path/'providers.json',r5.endpoints(settings));monkeypatch.setattr(Settings,'from_env',lambda:settings)
    async def check():
        remote=r5.Remote(tmp_path);await remote.client.aclose();count=0
        async def transport(request):
            nonlocal count
            count+=1
            await asyncio.sleep(.01)
            return httpx.Response(503,json={'error':'do not persist this body'})
        remote.client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
        a,b=await asyncio.gather(*(remote.call('rerank',{'query':'fixture','documents':['body'],'top_n':1},lambda d:d) for _ in range(2)))
        assert count==1 and a['status']==b['status']=='failed'
        assert a['duration_ms']>0 and 'error' not in a
        await remote.close()
    asyncio.run(check())
