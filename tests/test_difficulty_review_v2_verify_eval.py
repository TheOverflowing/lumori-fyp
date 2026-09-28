"""Frozen-input and billing guards for verification-only comparisons; no live API."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import httpx
import pytest

from app import difficulty_review_v2 as review
from app.config import Settings, Endpoint
from app.providers import ApiProviders as RealProviders
from scripts import difficulty_review_v2_verify_eval as runner
from scripts.difficulty_experiment import write_json
from test_difficulty_review_v2 import verification_raw


def raw_analysis():
    return {'eligibility':'eligible','eligibility_reason':'Conditions and preparation are clear.',
        'solution':'2','tasks':[{'request_ids':['S002'],'condition_ids':['S001'],'provided_ids':[],
            'residual_work':'Apply practised addition.','mode':'apply_familiar'}],
        'decision':{'candidates':['easy'],'boundary_reason':'Immediate familiar addition.','hard_task_index':None}}


def make_source(tmp_path,count=1,raw=None):
    root=tmp_path/'source_run';root.mkdir()
    cases=[];records=[];calls=[]
    for index in range(count):
        case={'id':f'case_{index}','split':'heldout','learner_profile':'Learner has repeatedly practised single-digit addition.',
            'student_visible_text':'Use addition. What is 1 + 1?','reference_answer':'2',
            'reference_explanation':'One plus one is two.','sources':[{'id':'math','text':'Adding one to one gives two.'}],
            'expected':{'content_status':'pass','candidates':['easy'],'issue':'PRIVATE_EXPECTATION'},
            'target_difficulty':'PRIVATE_TARGET','label_provenance':'PRIVATE_PROVENANCE'}
        clean=runner.input_case(case);source_raw=deepcopy(raw or raw_analysis())
        result=review.validate_analysis(source_raw,clean);prompts=review.analysis_messages(clean)
        item=f'{case["id"]}_0';identity=f'call_{index}'
        row={'case_id':case['id'],'repeat':0,'status':'failed','input_sha256':runner.digest(clean),
            'analysis':{'status':'validated','result':result,'prompt_sha256':runner.digest(prompts),'call_ids':[identity]},
            'verification':{'status':'failed','call_ids':[]}}
        write_json(root/'items'/item/'analysis_response.json',source_raw)
        write_json(root/'items'/item/'analysis_prompt.json',prompts)
        cases.append(case);records.append(row)
        calls.append({'id':identity,'job_id':item,'capability':'text','status':'succeeded','model':'original-analyst','usage':{}})
    hashes={}
    for name in ('app/difficulty_review_v2.py','app/difficulty_judge.py'):
        data=(runner.ROOT/name).read_bytes();target=root/'code'/name
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=runner.file_hash(data)
    manifest={'status':'completed_with_failures','protocol_sha256':review.protocol_fingerprint(),
        'dataset_sha256':runner.digest(cases),'code_sha256':hashes,'planned_calls':count*2,
        'actual_calls':count,'model':'original-analyst','parameters':{'max_tokens':2400}}
    for name,value in [('manifest',manifest),('dataset',{'cases':cases}),('records',records),('calls',calls)]:
        write_json(root/f'{name}.json',value)
    return root,cases,records


def args_for(root,output,**updates):
    args=runner.parser().parse_args(['--source-dir',str(root),'--output',str(output)])
    for name,value in updates.items():setattr(args,name,value)
    return args


def install_mock(monkeypatch,cases,mode='ok',close_error=False):
    bodies=[]
    clean=runner.input_case(cases[0]);analysis=review.validate_analysis(raw_analysis(),clean)
    response=verification_raw(clean,analysis)
    async def wire(request):
        body=json.loads(request.content);bodies.append(body)
        for secret in ('PRIVATE_EXPECTATION','PRIVATE_TARGET','PRIVATE_PROVENANCE'):
            assert secret not in json.dumps(body)
        if mode=='timeout':raise asyncio.TimeoutError()
        if mode=='http':return httpx.Response(503,text='PRIVATE_EXCEPTION_SECRET')
        raw={'checks':{}} if mode=='invalid' else response
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(raw)}}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30},'model':'fixture-upstream'})
    def provider(settings,store):
        result=RealProviders(settings,store,client=httpx.AsyncClient(transport=httpx.MockTransport(wire)))
        if close_error:
            original=result.close
            async def close():
                await original()
                raise RuntimeError('PRIVATE_CLEANUP_SECRET')
            result.close=close
        return result
    base=Settings(text=Endpoint('https://fixture.invalid','PRIVATE_KEY','fixture','/chat/completions'))
    monkeypatch.setattr(runner.Settings,'from_env',classmethod(lambda cls:base))
    monkeypatch.setattr(runner,'ApiProviders',provider)
    return bodies


def read(output,name):return json.loads((output/f'{name}.json').read_text())


def test_dry_reuses_failed_terminal_run_analysis_and_freezes_provenance(tmp_path,monkeypatch):
    root,cases,_=make_source(tmp_path)
    monkeypatch.setattr(runner,'ApiProviders',lambda *a,**k:pytest.fail('dry must not construct provider'))
    output=tmp_path/'dry'
    manifest=asyncio.run(runner.run(args_for(root,output,max_calls=1)))
    assert manifest['status']=='prepared' and manifest['analysis_calls']==0
    assert manifest['planned_calls']==1 and manifest['verifier_model']=='deepseek-v4-pro'
    assert manifest['verifier_parameters']['reasoning_effort']=='low'
    row=read(output,'records')[0]
    assert row['case_key']=='source_run:case_0:0'
    assert row['reuse']['input_sha256']==runner.digest(runner.input_case(cases[0]))
    assert row['reuse']['original_protocol_sha256']==review.protocol_fingerprint()
    assert read(output,'summary')['submitted']==1 and read(output,'calls')==[]
    assert (output/'source_evidence/source_run/code/app/difficulty_judge.py').is_file()
    with pytest.raises(FileExistsError):asyncio.run(runner.run(args_for(root,output)))


@pytest.mark.parametrize('mutation',['dataset','raw','normalization','code','active','ledger','missing_analysis','prompt'])
def test_tampered_or_unfinished_inputs_are_rejected_before_provider(tmp_path,mutation):
    root,cases,records=make_source(tmp_path)
    if mutation=='dataset':
        cases[0]['reference_answer']='3';write_json(root/'dataset.json',{'cases':cases})
    elif mutation=='raw':
        raw=raw_analysis();raw['solution']='3';write_json(root/'items/case_0_0/analysis_response.json',raw)
    elif mutation=='normalization':
        records[0]['analysis']['result']['case_sha256']='0'*64;write_json(root/'records.json',records)
    elif mutation=='code':
        path=root/'code/app/difficulty_judge.py';path.write_text(path.read_text()+'\n# altered\n')
    elif mutation=='active':
        manifest=read(root,'manifest');manifest['status']='running';write_json(root/'manifest.json',manifest)
    elif mutation=='ledger':write_json(root/'calls.json',[])
    elif mutation=='missing_analysis':(root/'items/case_0_0/analysis_response.json').unlink()
    else:write_json(root/'items/case_0_0/analysis_prompt.json',[{'content':'different'}])
    with pytest.raises(ValueError):runner.collect_sources([root])


def test_unknown_selection_and_call_caps_fail_before_output_creation(tmp_path):
    root,_,_=make_source(tmp_path,count=2)
    with pytest.raises(ValueError,match='Unknown'):runner.collect_sources([root],['source_run:absent:0'])
    for cap in (0,1,25):
        output=tmp_path/f'cap_{cap}'
        with pytest.raises(ValueError):asyncio.run(runner.run(args_for(root,output,max_calls=cap)))
        assert not output.exists()


def test_original_normalization_is_allowed_without_rewriting_raw(tmp_path):
    raw=raw_analysis();raw['eligibility_reason']='  Conditions and preparation are clear.  '
    raw['decision']['candidates']=['medium','easy']
    root,_,_=make_source(tmp_path,raw=raw)
    selected,_,_=runner.collect_sources([root])
    assert selected[0]['raw']==raw
    assert selected[0]['raw']['decision']['candidates']==['medium','easy']


def test_verification_only_live_path_uses_real_ledger_and_no_label_leak(tmp_path,monkeypatch):
    root,cases,_=make_source(tmp_path,count=2);bodies=install_mock(monkeypatch,cases)
    output=tmp_path/'live_mock'
    manifest=asyncio.run(runner.run(args_for(root,output,max_calls=2,live=True)))
    assert manifest['status']=='complete' and manifest['actual_calls']==2 and len(bodies)==2
    assert all(body['model']=='deepseek-v4-pro' and body['reasoning_effort']=='low' for body in bodies)
    rows=read(output,'records');calls=read(output,'calls')
    assert all(row['analysis']['call_ids']==[] for row in rows)
    assert {row['verification']['call_ids'][0] for row in rows}=={call['id'] for call in calls}
    assert all(row['analysis']['origin']=='reused_raw_revalidated' for row in rows)
    assert manifest['metering']['usage']['total_tokens']['complete_total']==60
    assert manifest['metering']['usage']['cost']['complete_total'] is None
    assert manifest['calls_without_cost']==2
    for row in rows:
        directory=output/'items'/row['item_id']
        for name in ('analysis_response','analysis_normalized','verification_prompt','verification_response','verification_normalized','decision'):
            assert (directory/f'{name}.json').is_file()
    assert 'PRIVATE_KEY' not in (output/'manifest.json').read_text()


@pytest.mark.parametrize('mode',['timeout','http'])
def test_transport_stop_keeps_unattempted_rows_and_paid_call_in_denominator(tmp_path,monkeypatch,mode):
    root,cases,_=make_source(tmp_path,count=3);bodies=install_mock(monkeypatch,cases,mode)
    output=tmp_path/'stopped'
    manifest=asyncio.run(runner.run(args_for(root,output,max_calls=3,live=True)))
    assert manifest['status']=='completed_with_failures' and manifest['actual_calls']==1 and len(bodies)==1
    assert [row['status'] for row in read(output,'records')]==['failed','not_attempted','not_attempted']
    assert read(output,'summary')['submitted']==3
    assert read(output,'calls')[0]['status']=='failed'
    assert 'PRIVATE_EXCEPTION_SECRET' not in (output/'records.json').read_text()


def test_validation_failures_keep_safe_locations_and_continue_without_retry(tmp_path,monkeypatch):
    root,cases,_=make_source(tmp_path,count=2);bodies=install_mock(monkeypatch,cases,'invalid')
    output=tmp_path/'invalid'
    manifest=asyncio.run(runner.run(args_for(root,output,max_calls=2,live=True)))
    assert manifest['actual_calls']==2 and len(bodies)==2
    for row in read(output,'records'):
        assert row['status']=='failed' and row['verification']['validation_issues']
        assert set(row['verification']['validation_issues'][0])=={'type','location'}


def test_cleanup_failure_cannot_hide_completed_billable_call(tmp_path,monkeypatch):
    root,cases,_=make_source(tmp_path);install_mock(monkeypatch,cases,close_error=True)
    output=tmp_path/'cleanup'
    manifest=asyncio.run(runner.run(args_for(root,output,max_calls=1,live=True)))
    assert manifest['actual_calls']==1 and manifest['cleanup_error_type']=='RuntimeError'
    assert len(read(output,'calls'))==1 and read(output,'records')[0]['status']=='complete'
    assert 'PRIVATE_CLEANUP_SECRET' not in (output/'manifest.json').read_text()
