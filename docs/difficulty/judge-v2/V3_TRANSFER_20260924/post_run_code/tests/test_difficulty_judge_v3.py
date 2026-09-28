import json
from copy import deepcopy
import pytest
from scripts.difficulty_judge_v3 import validate, messages
from scripts.difficulty_judge_comparison import summarize

@pytest.fixture
def case():
    return {'learner_profile':'Knows algebra', 'student_visible_text':'Prove x² ≥ 0. Hint: a real square is nonnegative.', 'teacher_label':'hard'}

@pytest.fixture
def result():
    return dict(eligibility='eligible',eligibility_reason='Complete',cognitive_demand='routine_application',
        supplied_support=[dict(quote='a real square is nonnegative',finding='Known rule supplied')],
        remaining_demands=[dict(quote='Prove x² ≥ 0',finding='Explain the rule')],
        knowledge_integration='Single rule',strategy_selection='Given',justification_required='Explain nonnegativity',
        estimated_difficulty='easy',adjacent_level_reason='No new strategy',uncertainty_reasons=[],confidence='medium',
        demand_audit=[dict(quote='Prove x² ≥ 0',finding='Only explanation remains',support_quotes=['a real square is nonnegative'],supplied_extent='partly_supplied',residual_task='Explain why the rule applies to x')],
        minimum_sufficient_response='A real square is nonnegative, so x² ≥ 0.',hard_basis_quote=None,learner_relative_basis='Known rule with provided hint')

def test_valid_and_no_label_leak(case,result):
    assert validate(result,case)['estimated_difficulty']=='easy'
    assert 'teacher_label' not in json.loads(messages(case)[1]['content'])

@pytest.mark.parametrize('mutation', ['fake_support','empty_support','double_count','missing_audit','wrong_hard_basis'])
def test_reject_untraceable_or_inconsistent_work(case,result,mutation):
    if mutation=='fake_support':result['demand_audit'][0]['support_quotes']=['private answer']
    if mutation=='empty_support':result['demand_audit'][0]['support_quotes']=[]
    if mutation=='double_count':result['demand_audit'][0]['supplied_extent']='fully_supplied'
    if mutation=='missing_audit':result['demand_audit'][0]['quote']='x² ≥ 0'
    if mutation=='wrong_hard_basis':result.update(estimated_difficulty='hard',hard_basis_quote='nonexistent demand')
    with pytest.raises(ValueError):validate(result,case)

def test_hard_not_banned_but_must_point_to_remaining_work(case,result):
    result.update(estimated_difficulty='hard',hard_basis_quote='Prove x² ≥ 0')
    assert validate(result,case)['estimated_difficulty']=='hard'
    # Host checks consistency, not semantic truth: this is NOT proof the hard rating is sound.
    result['demand_audit'][0].update(supplied_extent='fully_supplied',residual_task='')
    with pytest.raises(ValueError):validate(result,case)

def test_comparison_supports_v2_v3():
    data={'cases':[{'id':'x','domain':'math'}],'relations':[]}
    rows=[dict(arm=a,case_id='x',domain='math',repeat=r,status='valid',label='medium') for a in ('v2','v3') for r in (0,1)]
    summary=summarize(rows,data,2,('v2','v3'))
    assert set(summary['arms'])=={'v2','v3'}
    assert summary['arms']['v3']['stable_cases']==1
    assert summary['human_accuracy'] is None

@pytest.mark.parametrize('labels,status', [(['easy','easy'],'provisional_consensus'),(['easy','medium'],'review_required'),(['uncertain','uncertain'],'abstained')])
def test_disagreement_is_not_averaged_into_a_label(labels,status):
    from scripts.difficulty_review_decision import review_decision
    rows=[dict(repeat=i,status='valid',label=l,eligibility='eligible') for i,l in enumerate(labels)]
    decision=review_decision(rows)
    assert decision['status']==status
    if status!='provisional_consensus':assert decision['estimated_difficulty']=='uncertain'
    assert decision['human_validated'] is False

@pytest.mark.parametrize('change',['failed','duplicate','missing','ineligible'])
def test_no_silent_fallback_to_one_review(change):
    from scripts.difficulty_review_decision import review_decision
    rows=[dict(repeat=i,status='valid',label='medium',eligibility='eligible') for i in (0,1)]
    if change=='failed':rows[1]['status']='failed'
    if change=='duplicate':rows[1]['repeat']=0
    if change=='missing':rows.pop()
    if change=='ineligible':rows[1]['eligibility']='invalid_question'
    assert review_decision(rows)['status']=='review_required'
