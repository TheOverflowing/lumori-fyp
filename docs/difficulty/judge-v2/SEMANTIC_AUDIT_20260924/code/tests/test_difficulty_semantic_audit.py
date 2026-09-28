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
