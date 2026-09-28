import json
from copy import deepcopy
import pytest
from scripts.difficulty_judge_v2 import messages, validate
from scripts.difficulty_judge_comparison import baseline, summarize, DATA

@pytest.fixture
def case():
    return {'id':'x', 'domain':'math', 'learner_profile':'Knows algebra', 'student_visible_text':'Prove x² ≥ 0 for real x.', 'teacher_label':'hard', 'target_difficulty':'hard'}

@pytest.fixture
def result():
    return {'eligibility':'eligible','eligibility_reason':'Complete conditions',
        'cognitive_demand':'routine_application','supplied_support':[],
        'remaining_demands':[{'quote':'Prove x² ≥ 0','finding':'Apply square nonnegativity'}],
        'knowledge_integration':'One familiar concept','strategy_selection':'Familiar rule',
        'justification_required':'State why a square is nonnegative','estimated_difficulty':'easy',
        'adjacent_level_reason':'No additional analysis required','uncertainty_reasons':[], 'confidence':'medium'}

def test_exact_evidence(case,result):
    assert validate(result,case)['estimated_difficulty']=='easy'
    result['remaining_demands'][0]['quote']='Invented proof requirement'
    with pytest.raises(ValueError): validate(result,case)

def test_private_reference_cannot_validate_quote(case,result):
    case['private_reference']='Invented proof requirement'
    result['remaining_demands'][0]['quote']=case['private_reference']
    with pytest.raises(ValueError): validate(result,case)

@pytest.mark.parametrize('eligibility',['invalid_question','insufficient_profile'])
def test_ineligible_abstains(case,result,eligibility):
    result['eligibility']=eligibility
    with pytest.raises(ValueError): validate(result,case)
    result['estimated_difficulty']='uncertain'
    with pytest.raises(ValueError): validate(result,case)
    result['uncertainty_reasons']=['Missing necessary information']
    assert validate(result,case)['estimated_difficulty']=='uncertain'

def test_blind_prompts(case):
    template=json.loads((DATA/'baseline_template.json').read_text())
    for prompt in (messages(case),baseline(case,template)):
        payload=json.loads(prompt[1]['content'])
        assert 'teacher_label' not in payload and 'target_difficulty' not in payload
        assert case['student_visible_text'] in prompt[1]['content']
    payload=json.loads(baseline(case,template)[1]['content'])
    assert payload['reference_chunks']==[]
    assert payload['student_visible_context']['sections']==[]
    assert set(payload['question'])=={'kind','stem','options'}

def test_failures_do_not_inflate_stability_or_controls():
    dataset={'cases':[{'id':'a','domain':'math'},{'id':'b','domain':'math'}],
             'relations':[{'a':'a','b':'b','expectation':'equal'}]}
    rows=[dict(arm=arm,case_id=id,domain='math',repeat=r,status='valid',label='medium')
          for arm in ('v1','v2') for id in ('a','b') for r in (0,1)]
    rows[0]['status']='failed';rows[0].pop('label')
    summary=summarize(rows,dataset,2)
    assert summary['arms']['v1']['stable_cases']==1
    assert summary['arms']['v1']['controls'][0]['comparable']==1
    assert summary['human_accuracy'] is None
    assert summary['weighted_kappa'] is None

def test_stable_abstention_not_determinate():
    dataset={'cases':[{'id':'a','domain':'math'}],'relations':[]}
    rows=[dict(arm=arm,case_id='a',domain='math',repeat=r,status='valid',label='uncertain')
          for arm in ('v1','v2') for r in (0,1)]
    summary=summarize(rows,dataset,2)['arms']['v2']
    assert summary['stable_cases']==1
    assert summary['determinate_stable_cases']==0
    assert summary['abstentions']==2

def test_corpus_has_no_claimed_gold_and_relations_resolve():
    dataset=json.loads((DATA/'cases.json').read_text())
    ids={c['id'] for c in dataset['cases']}
    assert len(ids)==len(dataset['cases'])==8
    assert all(c['teacher_label'] is None and c['empirical_difficulty'] is None for c in dataset['cases'])
    assert all(r['a'] in ids and r['b'] in ids for r in dataset['relations'])
