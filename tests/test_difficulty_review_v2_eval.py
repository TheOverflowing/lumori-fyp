"""Diagnostic reporting guards; these tests do not measure judge accuracy."""

import json
import pytest

from app import difficulty_review_v2 as reviewer
from scripts.difficulty_review_v2_eval import input_case, score, stage_parameters


def example_case(identity='item', content_status='pass', candidates=None):
    return {
        'id': identity,
        'split': 'heldout',
        'domain': 'synthetic',
        'learner_profile': 'Knows integer addition.',
        'student_visible_text': 'Course rule: a token adds 2 points. What do two tokens add?',
        'reference_answer': 'REFERENCE_SECRET_4',
        'reference_explanation': 'EXPLANATION_SECRET_two_plus_two',
        'sources': [{'id': 'source_1', 'text': 'SOURCE_SECRET_course_rule'}],
        'expected': {
            'eligibility': 'eligible',
            'candidates': ['easy'] if candidates is None else candidates,
            'content_status': content_status,
            'issue': 'EXPECTED_SECRET_do_not_prompt',
        },
        'label_provenance': 'PROVENANCE_SECRET_not_gold',
        'target_difficulty': 'TARGET_SECRET',
        'teacher_label': 'TEACHER_SECRET',
    }


def test_input_case_removes_labels_targets_and_selection_metadata():
    cleaned = input_case(example_case())
    assert set(cleaned) == {
        'learner_profile', 'student_visible_text', 'reference_answer',
        'reference_explanation', 'sources',
    }
    encoded = json.dumps(cleaned)
    for hidden in ('EXPECTED_SECRET', 'TARGET_SECRET', 'TEACHER_SECRET',
                   'PROVENANCE_SECRET', 'heldout'):
        assert hidden not in encoded


def test_first_stage_prompt_omits_reference_sources_and_calibration_labels():
    messages = reviewer.analysis_messages(input_case(example_case()))
    encoded = json.dumps(messages)
    for hidden in ('REFERENCE_SECRET', 'EXPLANATION_SECRET', 'SOURCE_SECRET',
                   'EXPECTED_SECRET', 'TARGET_SECRET', 'TEACHER_SECRET',
                   'PROVENANCE_SECRET', 'heldout'):
        assert hidden not in encoded
    assert 'Course rule' in encoded
    assert 'Knows integer addition' in encoded


def test_score_keeps_failed_and_unattempted_slots_in_coverage_denominator():
    cases = [example_case('correct'), example_case('wrong'), example_case('skipped'),
             example_case('defect', 'fail')]
    records = [
        {'case_id': 'correct', 'status': 'complete',
         'decision': {'status': 'assessed', 'estimated_difficulty': 'easy'}},
        {'case_id': 'wrong', 'status': 'complete',
         'decision': {'status': 'assessed', 'estimated_difficulty': 'medium'}},
        {'case_id': 'skipped', 'status': 'not_attempted',
         'decision': {'status': 'unavailable'}},
        {'case_id': 'defect', 'status': 'complete',
         'decision': {'status': 'assessed', 'estimated_difficulty': 'easy'}},
    ]
    result = score(records, cases)
    assert result['submitted'] == 4
    assert result['control_cases'] == 3
    assert result['control_single_grade_coverage'] == 2 / 3
    assert result['control_single_grade_agreement'] == 1 / 2
    assert result['defects_cleared'] == ['defect']
    assert result['human_accuracy'] is None
    assert result['production_ready'] is False
    assert result['release_blockers']


def test_boundaries_and_abstentions_do_not_count_as_successful_single_grades():
    cases = [example_case('boundary'), example_case('failure'), example_case('rejected')]
    records = [
        {'case_id': 'boundary', 'decision': {
            'status': 'boundary', 'candidates': ['easy', 'medium']}},
        {'case_id': 'failure', 'status': 'failed'},
        {'case_id': 'rejected', 'decision': {'status': 'content_issue'}},
    ]
    result = score(records, cases)
    assert result['submitted'] == 3
    assert result['control_single_grade_coverage'] == 0
    assert result['control_single_grade_agreement'] is None
    assert result['controls_rejected'] == ['rejected']
    assert result['outcomes'] == {'boundary': 1, 'unavailable': 1, 'content_issue': 1}


def test_repeats_remain_separate_attempts_and_require_both_validated_stages():
    case = example_case()
    records = [
        {'case_id': case['id'], 'repeat': 0,
         'analysis': {'status': 'validated'}, 'verification': {'status': 'validated'},
         'decision': {'status': 'assessed', 'estimated_difficulty': 'easy'}},
        {'case_id': case['id'], 'repeat': 1,
         'analysis': {'status': 'validated'}, 'verification': {'status': 'failed'},
         'decision': {'status': 'unavailable'}},
    ]
    result = score(records, [case])
    assert result['submitted'] == 2
    assert result['stages_validated'] == 1
    assert result['control_single_grade_coverage'] == 0.5
    assert result['control_single_grade_agreement'] == 1
    assert result['production_ready'] is False


def test_diagnostic_gate_requires_explicit_defect_evidence_and_single_grades():
    cases = [example_case('hard', candidates=['hard']), example_case('bad', 'fail')]
    records = [
        {'case_id': 'hard', 'analysis': {'status': 'validated'},
         'verification': {'status': 'validated'},
         'decision': {'status': 'boundary', 'candidates': ['medium', 'hard']}},
        {'case_id': 'bad', 'analysis': {'status': 'validated'},
         'verification': {'status': 'validated', 'result': {'checks': {
             'reference_correct': {'status': 'fail'}}}}, 'decision': {'status': 'content_issue'}},
    ]
    result = score(records, cases)
    assert result['ai_diagnostic_gate_passed'] is False
    assert result['control_expected_candidate_coverage'] == 1
    assert result['control_single_grade_coverage'] == 0
    assert result['production_ready'] is False
    records[0]['decision'] = {'status': 'assessed', 'candidates': ['hard'], 'estimated_difficulty': 'hard'}
    assert score(records, cases)['ai_diagnostic_gate_passed'] is True
    records[1]['verification']['result']['checks'] = {}
    assert score(records, cases)['defects_detected'] == []
    records[1]['decision'] = {'status': 'boundary', 'candidates': ['easy', 'medium']}
    result = score(records, cases)
    assert result['ai_diagnostic_gate_passed'] is False
    assert result['defects_given_difficulty'] == ['bad']
    assert result['defects_detected'] == []


def test_content_miss_is_reported_even_when_solver_failure_blocks_final_grade():
    case = example_case('bad', 'fail')
    checks = {name: {'status': 'pass'} for name in (
        'conditions_complete', 'reference_correct', 'explanation_consistent', 'source_support')}
    checks['solution_correct'] = {'status': 'fail'}
    row = {'case_id': 'bad', 'verification': {'status': 'validated', 'result': {'checks': checks}},
           'decision': {'status': 'insufficient_evidence'}}
    result = score([row], [case])
    assert result['defects_cleared'] == []
    assert result['defects_with_all_content_checks_passed'] == ['bad']
    assert result['verifier_reported_solution_checks'] == {'fail': 1}
    assert result['independent_solution_accuracy'] is None


def test_missing_profile_is_not_reported_as_content_rejection():
    case = example_case()
    result = score([{'case_id': 'item', 'decision': {'status': 'ungradable',
        'reason_codes': ['insufficient_profile']}}], [case])
    assert result['controls_ungradable'] == ['item']
    assert result['controls_with_content_failure'] == []


@pytest.mark.parametrize('effort', ['none', 'low', 'high', 'max'])
def test_stage_parameters_keep_fixed_caps_and_exclude_ineffective_temperature(effort):
    params = stage_parameters(effort)
    assert params['max_tokens'] == (2400 if effort == 'none' else 12288)
    assert ('temperature' in params) == (effort == 'none')
    params['thinking']['type'] = 'changed'
    assert stage_parameters(effort)['thinking']['type'] != 'changed'
