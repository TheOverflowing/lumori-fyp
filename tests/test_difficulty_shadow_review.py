import json

import pytest

from app.difficulty_shadow import digest, visible_case
from app.difficulty_shadow_v2 import build_case
from scripts import difficulty_shadow_counterfactual as counterfactual
from scripts.difficulty_shadow_counterfactual import budget_snapshot, replay
from scripts.difficulty_shadow_review import collect, write_packet


def test_review_packet_is_blind_and_rejects_changed_content(tmp_path):
    run = tmp_path / 'saved_run'
    run.mkdir()
    asset = {'title': 'Exercise', 'section_scope': 'shared', 'sections': [],
             'learning_objectives': [], 'questions': [{
                 'slot_id': 'q1', 'stem': 'Explain the result.', 'options': [],
                 'answer': 'REFERENCE_ANSWER_SECRET', 'difficulty': 'medium'}]}
    case = visible_case(asset, 0, 'Introductory learner')
    observation = {'status': 'completed', 'asset_sha256': digest(asset), 'duration_ms': 42,
                   'questions': [{'slot_id': 'q1', 'original_difficulty': 'medium',
                                  'target_difficulty': 'medium', 'published_difficulty': 'medium',
                                  'visible_input_sha256': digest(case),
                                  'judge': {'status': 'validated', 'result': {
                                      'eligibility': 'eligible', 'decision': {
                                          'candidates': ['easy'], 'reason': 'Direct recall'}}},
                                  'audit': {'result': {'status': 'no_issue_found', 'findings': []}}}]}
    evidence = {'job': {'id': 'job-one'}, 'evidence': {
        'request': {'learner_profile': 'Introductory learner'},
        'difficulty_shadow': observation}}
    content = {'id': 'content-one', 'version': 1, 'asset': asset}
    (run / 'task_1_evidence.json').write_text(json.dumps(evidence))
    (run / 'task_1_content.json').write_text(json.dumps(content))

    rows = collect([run])
    assert len(rows) == 1 and rows[0]['comparison'] == 'disagrees'
    assert rows[0]['published_comparison'] == 'outside_candidates'
    output = write_packet(rows, tmp_path / 'review')
    blind = (output / 'blind_packet.md').read_text()
    assert 'Explain the result.' in blind
    assert 'REFERENCE_ANSWER_SECRET' not in blind
    assert 'medium' not in blind and 'Direct recall' not in blind
    assert 'Direct recall' in (output / 'comparison.md').read_text()
    answer_packet = (output / 'answer_review_packet.md').read_text()
    assert 'REFERENCE_ANSWER_SECRET' in answer_packet
    assert 'Direct recall' not in answer_packet
    assert 'medium' not in answer_packet
    assert 'answer_correctness' in (output / 'teacher_answer_review_template.csv').read_text()

    content['asset']['questions'][0]['stem'] = 'Changed question.'
    (run / 'task_1_content.json').write_text(json.dumps(content))
    with pytest.raises(ValueError, match='does not match observation'):
        collect([run])


def test_counterfactual_budget_snapshot_never_claims_complete_reservation():
    export = {'evidence': {'configuration': {'max_calls': 14}}, 'calls': [{}] * 14}
    assert budget_snapshot(export) == {
        'status': 'exhausted', 'job_call_cap': 14, 'recorded_job_calls': 14,
        'remaining_job_calls': 0, 'complete_rework_capacity_verified': False}
    export['calls'] = [{}] * 10
    assert budget_snapshot(export)['status'] == 'remaining_not_reserved'
    assert budget_snapshot(export)['complete_rework_capacity_verified'] is False


def write_new_review(tmp_path, status='content_issue', candidates=None,
                     recommendation='manual_review'):
    run = tmp_path / 'new_protocol_run'
    run.mkdir()
    profile = 'Introductory learner'
    asset = {'title': 'Exercise', 'section_scope': 'shared',
             'sections': [{'heading': 'Supplied rule', 'text': 'A token adds two.',
                           'citation_ids': ['shared_source']}],
             'learning_objectives': [], 'questions': [{
                 'slot_id': 'q_alpha_1', 'stem': 'What do two tokens add?', 'options': [],
                 'answer': 'REFERENCE_ANSWER_SECRET', 'explanation': 'EXPLANATION_SECRET',
                 'difficulty': 'medium', 'citation_ids': ['question_source']}]}
    sources = [{'id': 'shared_source', 'document_name': 'Shared rule',
                'text': 'A token adds two.'},
               {'id': 'question_source', 'document_name': 'Question rule',
                'text': 'Two tokens add four.'}]
    decision = {'status': status, 'candidates': candidates or [],
                'estimated_difficulty': candidates[0] if candidates and len(candidates) == 1 else 'uncertain',
                'target_relation': 'unknown', 'recommendation': recommendation,
                'reason_codes': ['SAVED_DECISION_REASON'],
                'enforcement_enabled': False, 'human_validated': False}
    question = {'slot_id': 'q_alpha_1', 'original_difficulty': 'medium',
                'target_difficulty': 'medium', 'published_difficulty': 'medium',
                'visible_input_sha256': digest(visible_case(asset, 0, profile)),
                'input_sha256': digest(build_case(asset, 0, profile, sources)),
                'analysis': {'status': 'validated', 'result': {
                    'eligibility': 'eligible', 'decision': {
                        'candidates': ['easy'], 'boundary_reason': 'BOUNDARY_REASON_SECRET'}}},
                'verification': {'status': 'validated', 'result': {'checks': {
                    'conditions_complete': {'status':'pass','reason':'Conditions checked','evidence':[]},
                    'solution_correct': {'status':'fail' if status=='insufficient_evidence' else 'pass',
                                         'reason':'Blind solution checked','evidence':[]},
                    'explanation_consistent': {'status':'pass','reason':'Explanation checked','evidence':[]},
                    'source_support': {'status':'pass','reason':'Sources checked','evidence':[]},
                    'demand_supported': {'status':'pass','reason':'Demand checked','evidence':[]},
                    'reference_correct': {
                        'status': 'fail' if status == 'content_issue' else 'pass',
                        'reason': 'CHECK_REASON_SECRET',
                        'evidence': [{'document_id': 'reference_answer',
                                      'quote': 'REFERENCE_ANSWER_SECRET'}]}}}},
                'decision': decision}
    observation = {'protocol': 'review_v2', 'status': 'completed',
                   'asset_sha256': digest(asset), 'duration_ms': 25, 'questions': [question]}
    export = {'job': {'id': 'new-job'}, 'calls': [{}] * 9,
              'evidence': {'configuration': {'max_calls': 14},
                           'request': {'learner_profile': profile},
                           'difficulty_shadow': observation}}
    content = {'id': 'new-content', 'version': 1, 'asset': asset, 'sources': sources}
    (run / 'task_1_evidence.json').write_text(json.dumps(export))
    (run / 'task_1_content.json').write_text(json.dumps(content))
    return run, export, content


def test_new_content_issue_suppresses_preliminary_grade_and_keeps_packet_blind(tmp_path):
    run, export, _ = write_new_review(tmp_path)
    rows = collect([run])
    row = rows[0]
    assert row['protocol'] == 'review_v2'
    assert row['decision'] == export['evidence']['difficulty_shadow']['questions'][0]['decision']
    assert row['candidates'] == []
    assert row['comparison'] == row['published_comparison'] == 'requires_review'
    assert row['audit_status'] == 'fail'
    assert row['content_checks']['reference_correct']['status'] == 'fail'
    assert row['content_checks']['solution_correct']['status'] == 'pass'
    assert len(row['content_checks']) == 6
    assert row['judge_reason'] == 'BOUNDARY_REASON_SECRET'
    assert {source['id'] for source in row['cited_sources']} == {'shared_source', 'question_source'}
    output = write_packet(rows, tmp_path / 'packet')
    blind = (output / 'blind_packet.md').read_text()
    for secret in ('REFERENCE_ANSWER_SECRET', 'EXPLANATION_SECRET', 'BOUNDARY_REASON_SECRET',
                   'CHECK_REASON_SECRET', 'SAVED_DECISION_REASON', 'medium', 'content_issue'):
        assert secret not in blind
    comparison = (output / 'comparison.md').read_text()
    assert '无有效判级' in comparison
    assert 'BOUNDARY_REASON_SECRET' in comparison
    assert 'reference_correct' in comparison and 'CHECK_REASON_SECRET' in comparison
    answer = (output / 'answer_review_packet.md').read_text()
    assert 'REFERENCE_ANSWER_SECRET' in answer
    assert 'BOUNDARY_REASON_SECRET' not in answer and 'CHECK_REASON_SECRET' not in answer


@pytest.mark.parametrize(('status', 'candidates', 'comparison', 'published_comparison'), [
    ('assessed', ['hard'], 'disagrees', 'outside_candidates'),
    ('boundary', ['easy', 'medium'], 'boundary', 'boundary_includes'),
    ('insufficient_evidence', [], 'requires_review', 'requires_review'),
])
def test_new_comparison_uses_saved_decision_not_blind_analysis(
        tmp_path, status, candidates, comparison, published_comparison):
    run, _, _ = write_new_review(tmp_path, status, candidates)
    row = collect([run])[0]
    assert row['candidates'] == candidates
    assert row['comparison'] == comparison
    assert row['published_comparison'] == published_comparison


def test_new_replay_preserves_archived_decision_and_observed_budget(tmp_path, monkeypatch):
    run, export, _ = write_new_review(tmp_path, 'assessed', ['hard'], 'rework_candidate')
    def legacy_must_not_run(*args):
        raise AssertionError('Current legacy policy must not reinterpret the saved new decision')
    monkeypatch.setattr(counterfactual, 'rework_candidate', legacy_must_not_run)
    report = replay([run])
    record = report['records'][0]
    decision = export['evidence']['difficulty_shadow']['questions'][0]['decision']
    assert record['baseline'] == record['counterfactual'] == decision
    assert record['decision_source'] == 'persisted_review_v2'
    assert record['budget']['remaining_job_calls'] == 5
    assert record['budget']['complete_rework_capacity_verified'] is False
    assert report['candidate_count'] == 1


def test_new_replay_does_not_turn_a_content_issue_into_a_candidate(tmp_path, monkeypatch):
    run, _, _ = write_new_review(tmp_path)
    monkeypatch.setattr(counterfactual, 'rework_candidate', lambda *args: pytest.fail('Legacy policy called'))
    report = replay([run])
    assert report['candidate_count'] == 0
    assert report['records'][0]['counterfactual']['status'] == 'content_issue'
    assert report['records'][0]['initial_candidates'] == []


def test_new_review_rejects_changed_scoped_source_even_when_asset_unchanged(tmp_path):
    run, _, content = write_new_review(tmp_path)
    content['sources'][0]['text'] = 'A changed course rule.'
    (run / 'task_1_content.json').write_text(json.dumps(content))
    with pytest.raises(ValueError, match='full review input does not match observation'):
        collect([run])


def test_new_review_still_rejects_changed_visible_input_hash(tmp_path):
    run, export, _ = write_new_review(tmp_path)
    export['evidence']['difficulty_shadow']['questions'][0]['visible_input_sha256'] = 'wrong'
    (run / 'task_1_evidence.json').write_text(json.dumps(export))
    with pytest.raises(ValueError, match='student-visible input does not match observation'):
        collect([run])


def test_new_replay_rejects_legacy_repeat_instead_of_reinterpreting(tmp_path):
    run, _, _ = write_new_review(tmp_path)
    repeat = tmp_path / 'repeat.json'
    repeat.write_text(json.dumps({'status': 'complete', 'kind': 'same_prompt_shadow_judge_repeat',
                                  'source_run': str(run), 'records': []}))
    with pytest.raises(ValueError, match='Legacy judge repeats cannot reinterpret'):
        replay([run], repeat)


def test_new_missing_decision_does_not_rebuild_it_from_validated_analysis(tmp_path, monkeypatch):
    run, export, _ = write_new_review(tmp_path)
    del export['evidence']['difficulty_shadow']['questions'][0]['decision']
    (run / 'task_1_evidence.json').write_text(json.dumps(export))
    monkeypatch.setattr(counterfactual, 'rework_candidate', lambda *args: pytest.fail('Legacy policy called'))
    row = collect([run])[0]
    assert row['candidates'] == [] and row['comparison'] == 'requires_review'
    report = replay([run])
    assert report['candidate_count'] == 0
    assert report['records'][0]['counterfactual']['status'] == 'unavailable'
    assert report['records'][0]['decision_source'] == 'missing_saved_decision'


def test_unknown_protocol_is_not_silently_read_as_legacy(tmp_path):
    run, export, _ = write_new_review(tmp_path)
    export['evidence']['difficulty_shadow']['protocol'] = 'unknown_future_protocol'
    (run / 'task_1_evidence.json').write_text(json.dumps(export))
    with pytest.raises(ValueError, match='unsupported saved shadow protocol'):
        collect([run])
