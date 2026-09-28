import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.difficulty_profile_analysis import validate_design,compare_candidates
from scripts.difficulty_judge_v4 import messages
from scripts.difficulty_judge_comparison import summarize,report

def dataset():return json.loads(Path('benchmarks/difficulty_profiles_v1/cases.json').read_text())

def test_frozen_questions_only_profiles_differ():
    data=dataset();assert len(validate_design(data))==4
    for group in validate_design(data).values():
        payloads=[json.loads(messages(c)[1]['content']) for c in group]
        for p in payloads:
            assert 'family' not in p and 'profile_variant' not in p and 'teacher_label' not in p
            p.pop('learner_profile')
        assert payloads[0]==payloads[1]==payloads[2]

def test_changed_question_breaks_profile_design():
    data=dataset();data['cases'][0]['student_visible_text']+='额外要求'
    with pytest.raises(ValueError):validate_design(data)

def test_missing_control_rejected():
    data=dataset();data['relations'].pop()
    with pytest.raises(ValueError):validate_design(data)

@pytest.mark.parametrize('a,b,expected',[( ['hard'],['medium'],'strictly_lower'),(['medium'],['medium'],'nonincrease'),(['easy'],['hard'],'reversal'),(['medium','hard'],['medium','hard'],'unresolved_overlap')])
def test_candidate_ranges_not_averaged(a,b,expected):
    def r(c):return {'status':'valid','result':{'decision':{'candidates':c}}}
    assert compare_candidates(r(a),r(b),'nonincrease')==expected
    assert compare_candidates(r(a),{},'nonincrease')=='unavailable'

def test_single_arm_report():
    d={'cases':[{'id':'x','domain':'math'}],'relations':[]}
    rows=[dict(arm='v4',case_id='x',domain='math',repeat=i,status='valid',label='easy') for i in (0,1)]
    s=summarize(rows,d,2,('v4',));out=report(s,dict(actual_calls=2,total_tokens=100,calls_without_cost=2))
    assert '| 题目 | v4 |' in out and '| x | easy, easy |' in out
