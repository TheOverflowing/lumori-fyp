from copy import deepcopy
import json
import pytest
from scripts.difficulty_judge_v4 import catalogue,messages,validate
from scripts.difficulty_judge_comparison import normalize

@pytest.fixture
def case():
    return dict(student_visible_text='x 是实数。证明 x² 非负。提示：实数的平方非负。',learner_profile='已学平方',teacher_label='hard')

@pytest.fixture
def result():
    return dict(eligibility='eligible',eligibility_reason='条件完整',cognitive_demand='routine_application',
        tasks=[dict(request_ids=['S002'],condition_ids=['S001'],solution_ids=['S003'],residual_work='解释已给出的平方规则',mode='apply_familiar')],
        minimum_answer='实数的平方非负，故 x² 非负。',decision=dict(candidates=['easy'],hard_task_index=None,reason='规则已提供，剩余为熟悉解释'))

def test_catalogue_resolves_exact_original_offsets(case):
    text=case['student_visible_text']
    for span in catalogue(text):assert text[span['start']:span['end']]==span['text']
    assert len(catalogue(text))==3
    assert catalogue(text)==catalogue(text)

def test_facts_and_solutions_are_separate(case,result):
    r=validate(result,case)
    assert r['resolved_evidence'][0]['condition_ids'][0]['text']=='x 是实数。'
    assert r['resolved_evidence'][0]['solution_ids'][0]['text']=='提示：实数的平方非负。'
    assert r['estimated_difficulty']=='easy'
    assert 'teacher_label' not in json.loads(messages(case)[1]['content'])

@pytest.mark.parametrize('field',['request_ids','condition_ids','solution_ids'])
def test_unknown_ids_fail_in_all_roles(case,result,field):
    result['tasks'][0][field]=['S999']
    with pytest.raises(ValueError):validate(result,case)

def test_multiple_candidates_abstain_and_keep_boundary(case,result):
    result['decision']['candidates']=['easy','medium']
    parsed,label,eligible=normalize('v4',result,case)
    assert label=='uncertain' and eligible=='eligible'
    assert parsed['decision']['candidates']==['easy','medium']

def test_ineligible_cannot_sneak_in_label(case,result):
    result['eligibility']='insufficient_profile'
    with pytest.raises(ValueError):validate(result,case)
    result['decision']['candidates']=[]
    assert validate(result,case)['estimated_difficulty']=='uncertain'

@pytest.mark.parametrize('index',[None,7,True])
def test_hard_needs_real_task_index(case,result,index):
    result['decision'].update(candidates=['hard'],hard_task_index=index)
    with pytest.raises(ValueError):validate(result,case)

def test_missing_field_not_invented(case,result):
    del result['decision']['reason']
    with pytest.raises(ValueError):validate(result,case)

def test_duplicate_labels_or_evidence_rejected(case,result):
    original=deepcopy(result)
    result['decision']['candidates']=['easy','easy']
    with pytest.raises(ValueError):validate(result,case)
    original['tasks'][0]['condition_ids']=['S001','S001']
    with pytest.raises(ValueError):validate(original,case)

def test_postprocessing_does_not_hide_candidate_disagreement(tmp_path):
    from scripts.difficulty_judge_report import consolidate
    def put(name,value):(tmp_path/name).write_text(json.dumps(value))
    put('manifest.json',dict(status='complete',arms=['v3','v4'],repeats=2))
    put('dataset.json',dict(cases=[{'id':'case'}]))
    rows=[]
    for arm in ('v3','v4'):
        for i,candidates in enumerate([['easy','medium'],['medium','hard']]):
            rows.append(dict(arm=arm,case_id='case',repeat=i,status='valid',label='uncertain',eligibility='eligible',result=dict(decision=dict(candidates=candidates,reason='Boundary unresolved'),tasks=[],resolved_evidence=[])))
    put('records.json',rows)
    m=consolidate(tmp_path)
    assert m['v4']['candidate_set_stable_cases']==0
    assert m['v4']['boundary_reviews']==2
    assert m['v4']['single_level_reviews']==0
    assert m['v4']['decision_counts']['abstained']==1

def test_more_than_six_genuine_references_are_supported(result):
    text=''.join(f'事实{i}。' for i in range(1,20))
    case={'student_visible_text':text,'learner_profile':'能理解这些条件'}
    result['tasks'][0].update(request_ids=['S019'],condition_ids=[f'S{i:03d}' for i in range(1,19)],solution_ids=[])
    parsed=validate(result,case)
    assert len(parsed['resolved_evidence'][0]['condition_ids'])==18

def test_reference_capacity_still_bounded(result):
    case={'student_visible_text':''.join(f'事实{i}。' for i in range(1,71)),'learner_profile':'已有背景'}
    result['tasks'][0]['condition_ids']=[f'S{i:03d}' for i in range(1,66)]
    with pytest.raises(ValueError):validate(result,case)
