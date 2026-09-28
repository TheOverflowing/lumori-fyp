import asyncio
from copy import deepcopy
from dataclasses import replace
import json
import httpx
import pytest
from app.difficulty_shadow import policy,visible_case,digest,observe
from app.difficulty_judge import catalogue
from app.generation_agent import GenerationAgent,authorize_resume
from app.models import GenerateRequest
from app.store import dumps
from test_generation_agent import agent_case,AgentWire,AUTHOR_SECRET,DESIGN_SECRET

class ShadowWire:
    def __init__(self,primary,mode='ok'):
        self.primary=primary;self.mode=mode;self.shadow_calls=[]
    def __call__(self,request):
        body=json.loads(request.content);payload=json.loads(body['messages'][1]['content'])
        if 'task' in payload:return self.primary(request)
        self.shadow_calls.append(payload)
        if self.mode=='cancel':raise asyncio.CancelledError()
        if self.mode=='http':return httpx.Response(503,text='unavailable')
        if self.mode=='bad':return AgentWire.response({'invalid':True})
        if 'existing_review' in payload:
            return AgentWire.response({'findings':[]})
        text=payload['student_visible_text'];id=catalogue(text)[-1]['id']
        return AgentWire.response({'eligibility':'eligible','eligibility_reason':'Fixture',
            'cognitive_demand':'routine_application','tasks':[{'request_ids':[id],'condition_ids':[],
            'solution_ids':[],'residual_work':'Apply rule','mode':'apply_familiar'}],
            'minimum_answer':'Fixture independently described answer',
            'decision':{'candidates':['medium'],'hard_task_index':None,'reason':'Fixture different level'}})

def attach(rig,mode='ok'):
    wire=ShadowWire(rig.wire,mode)
    asyncio.run(rig.providers.client.aclose())
    rig.providers.client=httpx.AsyncClient(transport=httpx.MockTransport(wire))
    return wire

def test_off_has_no_extra_calls_and_shadow_does_not_change_asset(agent_case):
    off=agent_case(count=1);assert off.run()['status']=='succeeded'
    on=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow'})
    wire=attach(on);assert on.run()['status']=='succeeded'
    assert on.asset()==off.asset()
    assert on.text_call_count()==off.text_call_count()+2
    state=on.evidence()['difficulty_shadow'];assert state['status']=='completed'
    assert state['asset_sha256']==state['observed_asset_sha256']==digest(on.asset())
    assert state['questions'][0]['judge']['result']['estimated_difficulty']=='medium'
    assert on.asset()['questions'][0]['difficulty']=='hard'
    for p in wire.shadow_calls:
        serialized=json.dumps(p)
        assert AUTHOR_SECRET not in serialized and DESIGN_SECRET not in serialized
        assert 'target_difficulty' not in p and 'difficulty_design' not in p
    on.run();assert len(wire.shadow_calls)==2  # Published duplicate doesn't bill again.

@pytest.mark.parametrize('mode',['http','bad'])
def test_shadow_failures_still_save_original_draft(agent_case,mode):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow'});wire=attach(rig,mode)
    assert rig.run()['status']=='succeeded'
    assert len(rig.contents())==1 and len(wire.shadow_calls)==1
    assert rig.evidence()['difficulty_shadow']['questions'][0]['judge']['status']=='failed'

@pytest.mark.parametrize('cap,expected',[ (4,0),(5,1),(6,2)])
def test_shadow_respects_remaining_lifetime_budget(agent_case,cap,expected):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow','agent_max_calls':cap})
    wire=attach(rig);assert rig.run()['status']=='succeeded'
    assert len(wire.shadow_calls)==expected
    assert rig.store.one('SELECT count(*) AS n FROM calls WHERE job_id=?',(rig.job_id,))['n']<=cap

@pytest.mark.parametrize('options,expected',[({'difficulty_shadow_max_calls':0},0),({'difficulty_shadow_max_calls':1},1),({'max_daily_calls':4},0)])
def test_separate_cap_and_daily_limit_are_nonblocking(agent_case,options,expected):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow',**options});wire=attach(rig)
    assert rig.run()['status']=='succeeded' and len(wire.shadow_calls)==expected

def test_cancelled_shadow_resume_never_reissues_uncertain_call(agent_case):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow'});wire=attach(rig,'cancel')
    # Pipeline records the interrupted task; sidecar intent survives.
    try:rig.run()
    except asyncio.CancelledError:pass
    evidence=rig.evidence();assert evidence['difficulty_shadow']['status']=='interrupted'
    assert evidence['difficulty_shadow']['questions'][0]['judge']['status']=='interrupted_not_retried'
    # Simulate restart with the saved accepted slots, before publishing.
    agent=GenerationAgent(rig.pipeline,GenerateRequest.model_validate(json.loads(rig.job()['payload'])),rig.job_id)
    agent.evidence=evidence;agent.state=evidence['agent']
    before=len(wire.shadow_calls)
    piece=evidence['agent']['slots'][0]['accepted_asset']
    # Use the exact assembled input stored by the observer via rebuilding one-slot asset.
    piece=deepcopy(piece);piece['title']=agent.request.topic;piece['section_scope']='shared';piece['visual_prompt']=''
    assert digest(piece)==evidence['difficulty_shadow']['asset_sha256']
    asyncio.run(observe(agent,piece));assert len(wire.shadow_calls)==before
    assert evidence['difficulty_shadow']['status']=='completed_with_issues'
    assert evidence['difficulty_shadow']['questions'][0]['judge']['status']=='interrupted_not_retried'
    authorize_resume(rig.store,rig.job_id)
    assert rig.run()['status']=='succeeded'
    assert len(wire.shadow_calls)==before and len(rig.contents())==1

def test_context_limit_skips_without_affecting_primary(agent_case):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow'});wire=attach(rig)
    # Freeze an intentionally tiny observer-only context budget.
    import app.difficulty_shadow as shadow
    original=shadow.policy
    def small(settings,saved_config=None):
        p=original(settings,saved_config)
        if p:p['context_chars']=1
        return p
    from unittest.mock import patch
    with patch.object(shadow,'policy',small):assert rig.run()['status']=='succeeded'
    assert not wire.shadow_calls

def test_legacy_and_saved_policy_freeze(agent_case):
    settings=agent_case(count=1).settings
    settings.difficulty_shadow_mode='shadow'
    assert policy(settings,{}) is None
    saved=policy(settings);settings.difficulty_shadow_max_calls=9
    assert policy(settings,{'difficulty_shadow':saved})['max_calls']==2

def test_visible_scope_and_no_answer_leak():
    asset={'section_scope':'per_question','sections':[{'heading':'One','text':'first'},{'heading':'Two','text':'second'}],
           'questions':[{'stem':'q1','options':[],'answer':'secret'},{'stem':'q2','options':['option'],'answer':'secret'}]}
    text=visible_case(asset,1,'profile')['student_visible_text']
    assert 'second' in text and 'first' not in text and 'A. option' in text and 'secret' not in text

def test_legacy_resume_does_not_enable_new_billable_work(agent_case):
    rig=agent_case(count=1,wire_options={'fail_phase':('agent_solve',1)})
    assert rig.run()['status']=='failed'
    rig.settings.difficulty_shadow_mode='shadow';wire=attach(rig)
    authorize_resume(rig.store,rig.job_id)
    assert rig.run()['status']=='succeeded'
    assert not wire.shadow_calls and 'difficulty_shadow' not in rig.evidence()['configuration']

def test_saved_shadow_limits_survive_config_change(agent_case):
    rig=agent_case(count=1,wire_options={'fail_phase':('agent_solve',1)},settings_options={'difficulty_shadow_mode':'shadow'})
    assert rig.run()['status']=='failed'
    rig.settings.difficulty_shadow_max_calls=9;wire=attach(rig)
    authorize_resume(rig.store,rig.job_id)
    assert rig.run()['status']=='succeeded'
    assert len(wire.shadow_calls)==2
    assert rig.evidence()['configuration']['difficulty_shadow']['max_calls']==2

def test_observer_timeout_does_not_cancel_primary(agent_case):
    rig=agent_case(count=1,settings_options={'difficulty_shadow_mode':'shadow','difficulty_shadow_timeout':1})
    normal=ShadowWire(rig.wire)
    async def slow(request):
        payload=json.loads(json.loads(request.content)['messages'][1]['content'])
        if 'task' not in payload:await asyncio.sleep(2)
        return normal(request)
    asyncio.run(rig.providers.client.aclose());rig.providers.client=httpx.AsyncClient(transport=httpx.MockTransport(slow))
    assert rig.run()['status']=='succeeded'
    assert rig.evidence()['difficulty_shadow']['questions'][0]['judge']['error_type']=='TimeoutError'
