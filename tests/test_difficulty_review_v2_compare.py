"""Synthetic frozen runs exercise local comparison; no live artifacts are read."""
from copy import deepcopy
import json

import pytest

from scripts import difficulty_review_v2_compare as compare


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def read(path):
    return json.loads(path.read_text())


def make_run(tmp_path, name, *, model='flash', effort='disabled'):
    root = tmp_path / name
    root.mkdir()
    cases = [{'id': identity, 'learner_profile': 'Basic arithmetic.',
              'student_visible_text': f'Visible question {identity}.', 'reference_answer': '4',
              'reference_explanation': 'Two plus two.',
              'sources': [{'id': 'rule', 'text': 'Addition rule.'}],
              'expected': {'content_status': content, 'candidates': ['hard']},
              'label_provenance': 'AI_authored_not_teacher_gold'}
             for identity, content in (('control', 'pass'), ('defect', 'fail'), ('unattempted', 'pass'))]
    parameters = {'thinking': {'type': effort}, 'max_tokens': 2400 if effort == 'disabled' else 12288}
    manifest = {'status': 'completed_with_failures', 'protocol_sha256': 'a' * 64,
                'dataset_sha256': compare.digest(cases), 'planned_calls': 6, 'actual_calls': 4,
                'model': model, 'parameters': parameters, 'analyst_parameters': parameters,
                'analyst_timeout': 45 if effort == 'disabled' else 120,
                'endpoint_signature': f'analysis-{model}', 'call_cap': 6, 'max_prompt_bytes': 100000,
                'verifier_model': 'pro', 'verifier_parameters': {'thinking': {'type': 'enabled'},
                                                             'reasoning_effort': 'low', 'max_tokens': 12288},
                'verifier_timeout': 120, 'verifier_endpoint_signature': 'same-verifier'}
    rows, calls = [], []
    for case in cases:
        row = {'case_id': case['id'], 'repeat': 0, 'status': 'not_attempted',
               'decision': {'status': 'unavailable', 'candidates': []}}
        if case['id'] != 'unattempted':
            row.update(status='complete', input_sha256=compare.digest(
                {key: case[key] for key in compare.CASE_FIELDS if key in case}), duration_ms=50)
            checks = {key: {'status': 'pass', 'reason': 'Fixture statement.'}
                      for key in (*compare.CONTENT_CHECKS, 'solution_correct', 'demand_supported')}
            row['analysis'] = {'status': 'validated', 'duration_ms': 20,
                               'result': {'decision': {'candidates': ['medium', 'hard']}}}
            row['verification'] = {'status': 'validated', 'duration_ms': 30, 'result': {'checks': checks}}
            row['decision'] = {'status': 'assessed', 'candidates': ['medium'], 'estimated_difficulty': 'medium'}
            for stage in compare.STAGES:
                identity = f'{case["id"]}-{stage}'
                row[stage]['call_ids'] = [identity]
                calls.append({'id': identity, 'job_id': f'{case["id"]}_0', 'status': 'succeeded',
                              'response_model': model if stage == 'analysis' else 'pro',
                              'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15,
                                        'completion_tokens_details': {'reasoning_tokens': 2}}})
        rows.append(row)
    write(root / 'manifest.json', manifest)
    write(root / 'dataset.json', {'cases': cases})
    write(root / 'records.json', rows)
    write(root / 'calls.json', calls)
    return root


@pytest.fixture
def runs(tmp_path):
    return make_run(tmp_path, 'baseline'), make_run(tmp_path, 'candidate', model='pro', effort='enabled')


def test_pairs_different_analyst_configurations_and_preserves_denominator(runs):
    left, right = runs
    report = compare.compare_runs(left, right)
    assert report['paired'] is True
    assert len(report['pairs']) == 3
    assert report['teacher_accuracy'] == 'unknown'
    assert report['independent_solution_accuracy'] == 'unknown'
    assert report['production_ready'] is False
    assert set(report['analyst_configuration_differences']) == {'model', 'parameters', 'timeout', 'endpoint_signature'}
    last = report['pairs'][2]
    assert last['baseline']['record_status'] == 'not_attempted'
    assert last['baseline']['input_hash_origin'] == 'dataset_derived_not_attempted'
    assert report['summaries']['baseline']['submitted_case_repeats'] == 3
    assert report['summaries']['baseline']['record_status_counts']['not_attempted'] == 1


@pytest.mark.parametrize('field, value', [
    ('protocol_sha256', 'b' * 64), ('verifier_model', 'different'),
    ('verifier_parameters', {'thinking': {'type': 'disabled'}}),
    ('verifier_timeout', 121), ('verifier_endpoint_signature', 'different-provider')])
def test_changed_frozen_control_refuses_paired_claim(runs, field, value):
    left, right = runs
    manifest = read(right / 'manifest.json'); manifest[field] = value
    write(right / 'manifest.json', manifest)
    with pytest.raises(compare.ComparisonError):
        compare.compare_runs(left, right)


def test_dataset_mismatch_refused_even_with_self_consistent_new_hash(runs):
    left, right = runs
    dataset = read(right / 'dataset.json')
    dataset['cases'][0]['learner_profile'] = 'Changed preparation.'
    manifest = read(right / 'manifest.json'); manifest['dataset_sha256'] = compare.digest(dataset['cases'])
    rows = read(right / 'records.json')
    case = dataset['cases'][0]
    rows[0]['input_sha256'] = compare.digest({field: case[field] for field in compare.CASE_FIELDS if field in case})
    write(right / 'dataset.json', dataset); write(right / 'manifest.json', manifest); write(right / 'records.json', rows)
    with pytest.raises(compare.ComparisonError, match='dataset_sha256 differs'):
        compare.compare_runs(left, right)


def test_corrupted_dataset_or_per_record_input_hash_is_rejected(runs):
    left, right = runs
    rows = read(right / 'records.json'); rows[0]['input_sha256'] = 'c' * 64
    write(right / 'records.json', rows)
    with pytest.raises(compare.ComparisonError, match='Recorded input'):
        compare.compare_runs(left, right)
    rows[0].pop('input_sha256')
    write(right / 'records.json', rows)
    with pytest.raises(compare.ComparisonError, match='input_sha256'):
        compare.compare_runs(left, right)


def test_active_manifest_rejected_before_reading_records(tmp_path, monkeypatch):
    root = tmp_path / 'running'; root.mkdir()
    write(root / 'manifest.json', {'status': 'running'})
    accessed = []
    original = compare._read
    def read_tracked(path):
        accessed.append(path.name)
        return original(path)
    monkeypatch.setattr(compare, '_read', read_tracked)
    with pytest.raises(compare.ComparisonError, match='not terminal'):
        compare.compare_runs(root, root)
    assert accessed == ['manifest.json']


@pytest.mark.parametrize('stage_status', ['preparing', 'in_flight', 'running'])
def test_terminal_manifest_with_active_stage_is_rejected(runs, stage_status):
    left, right = runs
    rows = read(right / 'records.json'); rows[0]['analysis']['status'] = stage_status
    write(right / 'records.json', rows)
    with pytest.raises(compare.ComparisonError, match='stage is nonterminal'):
        compare.compare_runs(left, right)


def test_manifest_change_during_read_invalidates_frozen_claim(runs, monkeypatch):
    left, right = runs
    original = compare._read
    seen = 0
    def changing(path):
        nonlocal seen
        result = original(path)
        if path == left / 'manifest.json':
            seen += 1
            if seen == 2:
                result['status'] = 'running'
        return result
    monkeypatch.setattr(compare, '_read', changing)
    with pytest.raises(compare.ComparisonError, match='manifest changed'):
        compare.compare_runs(left, right)


def test_missing_repeat_cannot_be_disguised_as_matching_dataset(runs):
    left, right = runs
    rows = read(right / 'records.json'); rows[2]['repeat'] = 1
    write(right / 'records.json', rows)
    with pytest.raises(compare.ComparisonError, match='case/repeat sets differ'):
        compare.compare_runs(left, right)


def test_duplicate_records_and_dropped_cases_are_rejected(runs):
    left, right = runs
    rows = read(right / 'records.json')
    write(right / 'records.json', rows + [deepcopy(rows[0])])
    with pytest.raises(compare.ComparisonError, match='Duplicate case/repeat'):
        compare.compare_runs(left, right)
    write(right / 'records.json', rows[:-1])
    with pytest.raises(compare.ComparisonError, match='omit a submitted case'):
        compare.compare_runs(left, right)


def test_false_clear_is_reported_when_solver_failure_causes_final_abstention(runs):
    left, right = runs
    rows = read(right / 'records.json')
    rows[1]['verification']['result']['checks']['solution_correct']['status'] = 'fail'
    rows[1]['decision'] = {'status': 'insufficient_evidence', 'candidates': [], 'reason_codes': ['failed:solution_correct']}
    write(right / 'records.json', rows)
    report = compare.compare_runs(left, right)
    defect = next(pair for pair in report['pairs'] if pair['case_id'] == 'defect')['candidate']
    assert defect['content_false_clear_against_expected'] is True
    assert defect['grade_class'] == 'abstain'
    assert defect['verifier_reported_solution_correct']['status'] == 'fail'
    assert defect['independent_solution_correctness'] == 'unknown'
    assert report['summaries']['candidate']['content_false_clears_against_expected'] == [{'case_id': 'defect', 'repeat': 0}]


def test_solver_error_is_not_a_content_false_issue(runs):
    left, right = runs
    rows = read(right / 'records.json')
    rows[0]['verification']['result']['checks']['solution_correct']['status'] = 'fail'
    rows[0]['decision'] = {'status': 'insufficient_evidence', 'candidates': []}
    write(right / 'records.json', rows)
    report = compare.compare_runs(left, right)
    assert report['pairs'][0]['candidate']['content_false_issue_against_expected'] is False
    rows[0]['verification']['result']['checks']['reference_correct']['status'] = 'fail'
    write(right / 'records.json', rows)
    report = compare.compare_runs(left, right)
    assert report['pairs'][0]['candidate']['content_false_issue_against_expected'] is True


def test_failed_transport_not_attempted_and_boundary_remain_visible(runs):
    left, right = runs
    rows = read(right / 'records.json')
    rows[0]['status'] = 'failed'
    rows[0]['verification'].update(status='failed', error_type='TimeoutError')
    rows[0]['decision'] = {'status': 'unavailable', 'candidates': []}
    rows[1]['decision'] = {'status': 'boundary', 'candidates': ['medium', 'hard']}
    write(right / 'records.json', rows)
    report = compare.compare_runs(left, right)
    assert report['pairs'][0]['candidate']['content_checks']['reference_correct']['status'] == 'not_verified'
    assert report['pairs'][0]['candidate']['content_false_issue_against_expected'] is None
    assert report['pairs'][1]['candidate']['grade_class'] == 'boundary'
    assert report['summaries']['candidate']['grade_class_counts'] == {'abstain': 2, 'boundary': 1}


def test_stage_durations_tokens_and_missing_cost_are_not_invented(runs):
    left, right = runs
    calls = read(right / 'calls.json'); calls[0]['usage'].pop('total_tokens')
    write(right / 'calls.json', calls)
    report = compare.compare_runs(left, right)
    stage = report['pairs'][0]['candidate']['analysis']
    assert stage['duration_ms'] == 20
    assert stage['metering']['usage']['total_tokens'] == {'known_sum': 0, 'complete_total': None}
    assert stage['metering']['calls_missing_usage']['total_tokens'] == 1
    assert stage['metering']['usage']['reasoning_tokens']['complete_total'] == 2
    assert stage['metering']['usage']['cost']['complete_total'] is None
    assert report['summaries']['candidate']['metering']['usage']['total_tokens']['known_sum'] == 45


def test_legacy_absent_call_links_and_duration_are_unknown(runs):
    left, right = runs
    rows = read(right / 'records.json')
    rows[0]['analysis'].pop('call_ids'); rows[0]['analysis'].pop('duration_ms')
    write(right / 'records.json', rows)
    report = compare.compare_runs(left, right)
    stage = report['pairs'][0]['candidate']['analysis']
    assert stage['call_attribution'] == 'unknown' and stage['duration_ms'] is None
    assert stage['metering'] is None
    assert report['summaries']['candidate']['unattributed_call_ids'] == ['control-analysis']


@pytest.mark.parametrize('mutation', ['shared', 'missing', 'wrong_case'])
def test_call_attribution_errors_are_rejected(runs, mutation):
    left, right = runs
    rows = read(right / 'records.json'); calls = read(right / 'calls.json')
    if mutation == 'shared':
        rows[0]['verification']['call_ids'] = rows[0]['analysis']['call_ids']
    elif mutation == 'missing':
        rows[0]['analysis']['call_ids'] = ['unknown-call']
    else:
        calls[0]['job_id'] = 'defect_0'
    write(right / 'records.json', rows); write(right / 'calls.json', calls)
    with pytest.raises(compare.ComparisonError):
        compare.compare_runs(left, right)


def test_cli_writes_new_local_results_without_mutating_frozen_runs(runs, tmp_path):
    left, right = runs
    before = {str(path): path.read_bytes() for run in runs for path in run.iterdir()}
    output, md = tmp_path / 'comparison.json', tmp_path / 'comparison.md'
    compare.main(['--baseline', str(left), '--candidate', str(right), '--output', str(output), '--markdown', str(md)])
    assert read(output)['paired'] is True
    assert '教师准确率' in md.read_text()
    assert all(path.read_bytes() == before[str(path)] for run in runs for path in run.iterdir())
    with pytest.raises(compare.ComparisonError, match='new, distinct'):
        compare.main(['--baseline', str(left), '--candidate', str(right), '--output', str(output)])
    with pytest.raises(compare.ComparisonError, match='inside frozen'):
        compare.main(['--baseline', str(left), '--candidate', str(right), '--output', str(left / 'new.json')])
