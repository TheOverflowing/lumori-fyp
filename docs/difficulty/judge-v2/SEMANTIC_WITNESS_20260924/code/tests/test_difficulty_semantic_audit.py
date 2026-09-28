import json
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.difficulty_semantic_audit import messages,validate,review_catalogue,audit_gate

def cases():return json.loads(Path('benchmarks/difficulty_semantic_audit_v1/cases.json').read_text())['cases']

def test_scope_and_blinding():
    for c in cases():
        p=json.loads(messages(c)[1]['content'])
        assert set(p)=={'learner_profile','student_visible_text','question_catalogue','existing_review','review_catalogue','schema'}
        assert 'target_present' not in p and 'target_category' not in p and 'provenance' not in p
        for span in review_catalogue(c['review']):assert span['path'] and span['text']

def test_no_findings_does_not_certify_accuracy():
    r=validate({'findings':[]},cases()[0]);assert r['status']=='no_issue_found' and r['human_validated'] is False
    with pytest.raises(ValueError):validate({'findings':[],'estimated_difficulty':'easy'},cases()[0])

@pytest.mark.parametrize('field',['question_ids','review_ids'])
def test_false_evidence_rejected(field):
    c=cases()[0];raw={'findings':[dict(category='optional_method_as_required',certainty='definite',question_ids=['S001'],review_ids=['R001'],explanation='Mismatch',suggested_correction='Use optional method wording')]}
    raw['findings'][0][field]=['nonexistent']
    with pytest.raises(ValueError):validate(raw,c)

def test_gate_preserves_original_grade_and_no_promotion():
    d={'status':'provisional_consensus','estimated_difficulty':'medium'};original=deepcopy(d)
    assert audit_gate(d,None)['status']=='review_required'
    assert audit_gate(d,{'status':'correction_required'})['estimated_difficulty']=='medium'
    assert audit_gate({'status':'review_required'},{'status':'no_issue_found'})['status']=='review_required'
    assert d==original

def test_pairs_do_not_change_target_grade():
    cs=cases()
    for a,b in zip(cs[::2],cs[1::2]):
        assert a['student_visible_text']==b['student_visible_text']
        assert a['review']['decision']['candidates']==b['review']['decision']['candidates']

def test_execution_witness_distinguishes_hang_wrong_and_correct():
    from scripts.difficulty_execution_witness import trace,witness
    assert trace([1,2],2)['status']=='nontermination_repeated_state'
    wrong=trace([1],2);assert wrong['actual_return']==0 and wrong['expected_return']==1
    good=trace([2,3],2);assert good['actual_return']==good['expected_return']==0
    with pytest.raises(ValueError):witness('arbitrary unrelated code')

def test_withdrawn_finding_is_not_a_valid_error():
    from scripts.difficulty_semantic_audit_v2 import validate
    raw={'findings':[dict(category='unsupported_claim',certainty='definite',question_ids=['S001'],review_ids=['R001'],explanation='Actually accurate.',suggested_correction='No change needed; it is correct.')]}
    with pytest.raises(ValueError):validate(raw,cases()[0])
