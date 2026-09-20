import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from scripts import r7_experiment as r7


def test_clarification_does_not_require_identical_filler():
    request={'query':'那个一分两半的方法怎么弄？','language':'zh'}
    proposal={'query':'一分两半的方法','needs_clarification':True,'reason':'缺少具体操作及任务'}
    assert r7.validate_rewrite(proposal,request)==proposal
    assert r7.rewrite_action({'status':'succeeded','result':proposal})=='clarify'


@pytest.mark.parametrize('value',[
    {'query':'CPU 栈','needs_clarification':'false','reason':''},
    {'query':'CPU with 64 bits','needs_clarification':False,'reason':''},
    {'query':'32位实现','needs_clarification':False,'reason':''},
    {'query':'CPU 32 bit','needs_clarification':False,'reason':'','answer':'bad'},
])
def test_structural_and_literal_protection(value):
    with pytest.raises(ValueError):r7.validate_rewrite(value,{'query':'CPU 32位怎么实现？','language':'zh'})


def test_failed_rewrite_is_fallback_not_clarification():
    assert r7.rewrite_action({'status':'failed','result':{'needs_clarification':True}})=='fallback'


def test_l4_cannot_change_dev_winner():
    rows=[]
    for arm in r7.ARMS:
        rows.extend([{'arm':arm,'level':'L0','pre_hit5':1,'pre_mrr20':.5},
                     {'arm':arm,'level':'L4','pre_hit5':100 if arm=='dual' else None,'pre_mrr20':None}])
    assert r7.choose(rows)[0]=='original'
    rows[2]['pre_mrr20']=.75
    assert r7.choose(rows)[0]=='conservative'


def test_union_hit_and_single_chunk_mrr_have_explicit_difference():
    spans=[{'parent_id':'p','start':0,'end':10,'text':'abcdefghij','language':'en'}]
    chunks=[{'parent_id':'p','source_start':0,'source_end':5,'text':'abcde'},
            {'parent_id':'p','source_start':5,'source_end':10,'text':'fghij'}]
    got=r7.span_scores(chunks,spans)
    assert got=={'pre_hit1':0,'pre_hit5':1,'pre_hit20':1,'pre_mrr20':0.}


def test_shared_scores_cannot_be_rebound_to_changed_ids():
    request={'query':'q','documents':['a','b'],'top_n':2}
    row={'ids':['a','b'],'request':request,'request_sha256':r7.sha(r7.canonical(request))}
    result={'request_sha256':row['request_sha256'],'ids_sha256':r7.sha(r7.canonical(row['ids']))}
    r7.verify_shared_binding(result,row)
    with pytest.raises(ValueError,match='not bound'):r7.verify_shared_binding(result,dict(row,ids=['b','a']))
    with pytest.raises(ValueError,match='not bound'):r7.verify_shared_binding(result,dict(row,request=dict(request,query='changed')))


def fake_settings():
    return SimpleNamespace(**{cap:SimpleNamespace(base_url='https://api.deepseek.com' if cap=='text' else 'https://openrouter.ai/api/v1',
        path='/mock',model='fixture-model',signature='fixture',api_key='fixture-key') for cap in r7.CAPS})


@pytest.mark.parametrize('statuses,expected_attempts,final_status',[
    ([503,200],2,'succeeded'),([503,503],2,'failed'),([400],1,'failed')])
def test_http_retry_is_bounded_and_cached(tmp_path,statuses,expected_attempts,final_status):
    async def check():
        settings=fake_settings();r7.save(tmp_path/'providers.json',r7.endpoints(settings));requests=[]
        def handler(request):
            requests.append(request)
            status=statuses[min(len(requests)-1,len(statuses)-1)]
            return httpx.Response(status,json={'ok':1,'usage':{'cost':0.001}})
        with patch.object(r7.Settings,'from_env',return_value=settings):
            remote=r7.Remote(tmp_path);await remote.client.aclose();remote.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                first=await remote.call('embedding',{'input':['a']},lambda d:d['ok'])
                again=await remote.call('embedding',{'input':['a']},lambda d:d['ok'])
                assert first==again and first['status']==final_status
                assert first['attempts']==expected_attempts and len(requests)==expected_attempts
                assert sorted(r['attempt'] for r in remote.calls.values())==list(range(1,expected_attempts+1))
                assert len({r['logical_key'] for r in remote.calls.values()})==1
                assert sum(r['usage'].get('cost',0) for r in remote.calls.values())==pytest.approx(.001 if final_status=='succeeded' else 0)
            finally:await remote.close()
    asyncio.run(check())


def test_metering_failure_survives_restart(tmp_path):
    async def check():
        settings=fake_settings();r7.save(tmp_path/'providers.json',r7.endpoints(settings))
        with patch.object(r7.Settings,'from_env',return_value=settings):
            remote=r7.Remote(tmp_path);await remote.client.aclose()
            remote.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'ok':1})))
            try:
                with pytest.raises(ValueError,match='lacked'):await remote.call('embedding',{'input':['a']},lambda d:d['ok'])
            finally:await remote.close()
            with pytest.raises(ValueError,match='Missing previous'):r7.Remote(tmp_path)
    asyncio.run(check())


def test_shared_failure_scores_all_retrieval_arms_together_and_preserves_pre_scores(tmp_path):
    q={'id':'q','family_id':'f','language':'en','level':'L0','split':'dev','text':'question'}
    r7.save(tmp_path/'dataset.json',{'queries':[q],'documents':[{'id':'d','text':'fact'}]})
    r7.save(tmp_path/'chunks.json',[{'id':'c','parent_id':'d','source_start':0,'source_end':4,'text':'fact'}])
    r7.save(tmp_path/'gold-spans.json',{'q':[{'parent_id':'d','start':0,'end':4,'text':'fact','language':'en'}]})
    candidates={};rows=[]
    for arm in r7.ARMS:
        action='clarify' if arm=='conservative' else 'retrieve'
        candidates['q:'+arm]={'ids':[] if action=='clarify' else ['c']}
        rows.append(dict(query_id='q',family_id='f',language='en',level='L0',split='dev',arm=arm,action=action,rewrite_fallback=False,
                         **dict.fromkeys(('pre_hit1','pre_hit5','pre_hit20','pre_mrr20'),0 if action=='clarify' else 1)))
    r7.save(tmp_path/'dev-candidates.json',candidates);r7.save(tmp_path/'dev-pre-rows.json',rows)
    request={'query':'question','documents':['fact'],'top_n':1}
    spec={'ids':['c'],'request':request,'request_sha256':r7.sha(r7.canonical(request))}
    r7.save(tmp_path/'dev-shared-requests.json',{'q':spec})
    r7.save(tmp_path/'dev-shared-rerank.json',{'q':{'status':'failed','http_status':503,'request_sha256':spec['request_sha256'],'ids_sha256':r7.sha(r7.canonical(spec['ids']))}})
    with patch.object(r7,'verify'),patch.object(r7,'TokenCounter',return_value=SimpleNamespace(count=len)):
        r7.metrics(tmp_path,'dev')
    results=r7.load(tmp_path/'dev-per-query.json')
    assert all(r['post_hit']==0 and r['shared_rerank_failed'] for r in results)
    assert all(r['pre_hit5']==1 for r in results if r['action']=='retrieve')
    assert next(r for r in results if r['arm']=='conservative')['status']=='clarified'
