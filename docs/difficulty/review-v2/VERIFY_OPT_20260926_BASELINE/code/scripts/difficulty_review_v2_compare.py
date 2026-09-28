"""Compare two completed frozen review runs locally; never contact a provider.

This compares analyst configuration combinations, not independently measured
teacher accuracy or a causal effect of model/effort alone.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

CASE_FIELDS = ('learner_profile', 'student_visible_text', 'reference_answer',
               'reference_explanation', 'sources', 'kind', 'options')
CONTENT_CHECKS = ('conditions_complete', 'reference_correct', 'explanation_consistent', 'source_support')
STAGES = ('analysis', 'verification')
TERMINAL_RUNS = {'complete', 'completed_with_failures'}
TERMINAL_ROWS = {'complete', 'failed', 'not_attempted'}


class ComparisonError(ValueError):
    """The available evidence does not support a paired comparison."""


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ComparisonError(f'Cannot read frozen artifact {path.name}: {type(exc).__name__}') from None


def _hash(value, name):
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in '0123456789abcdef' for char in value)):
        raise ComparisonError(f'Missing or invalid {name}')
    return value


def _load_run(directory):
    directory = Path(directory).resolve()
    manifest = _read(directory / 'manifest.json')
    # Do not read rows, calls or accumulate statistics while a run is active.
    if not isinstance(manifest, dict) or manifest.get('status') not in TERMINAL_RUNS:
        raise ComparisonError(f'{directory.name}: run is not terminal; comparison refused')
    _hash(manifest.get('protocol_sha256'), 'protocol_sha256')
    _hash(manifest.get('dataset_sha256'), 'dataset_sha256')
    dataset = _read(directory / 'dataset.json')
    cases = dataset.get('cases') if isinstance(dataset, dict) else None
    if not isinstance(cases, list) or not cases or any(not isinstance(c, dict) for c in cases):
        raise ComparisonError('Frozen dataset must contain cases')
    by_id = {}
    for case in cases:
        identity = case.get('id')
        if not isinstance(identity, str) or not identity or identity in by_id:
            raise ComparisonError('Invalid or duplicate frozen case ID')
        by_id[identity] = case
    if digest(cases) != manifest['dataset_sha256']:
        raise ComparisonError('Frozen dataset does not match its manifest hash')
    rows = _read(directory / 'records.json')
    if not isinstance(rows, list) or not rows:
        raise ComparisonError('Frozen records must be a nonempty list')
    paired = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('status') not in TERMINAL_ROWS:
            raise ComparisonError('A record is nonterminal or invalid; comparison refused')
        identity, repeat = row.get('case_id'), row.get('repeat')
        if identity not in by_id or type(repeat) is not int or repeat < 0:
            raise ComparisonError('Record case/repeat is invalid')
        key = (identity, repeat)
        if key in paired:
            raise ComparisonError('Duplicate case/repeat record')
        case_input = {field: by_id[identity][field] for field in CASE_FIELDS if field in by_id[identity]}
        expected_hash = digest(case_input)
        actual_hash = row.get('input_sha256')
        if actual_hash is None and row['status'] == 'not_attempted':
            origin = 'dataset_derived_not_attempted'
        else:
            if _hash(actual_hash, 'input_sha256') != expected_hash:
                raise ComparisonError('Recorded input does not match the frozen case')
            origin = 'recorded_and_dataset_verified'
        for stage in STAGES:
            if row.get(stage, {}).get('status') in ('pending', 'preparing', 'in_flight', 'running'):
                raise ComparisonError('A stage is nonterminal; comparison refused')
        paired[key] = {'row': row, 'input_sha256': expected_hash, 'input_hash_origin': origin}
    if {key[0] for key in paired} != set(by_id):
        raise ComparisonError('Frozen records omit a submitted case')
    if manifest.get('planned_calls') != 2 * len(rows):
        raise ComparisonError('Planned call count does not cover the frozen case/repeat set')
    calls = _read(directory / 'calls.json')
    if not isinstance(calls, list) or any(not isinstance(call, dict) for call in calls):
        raise ComparisonError('Frozen calls must be a list')
    by_call = {}
    for call in calls:
        identity = call.get('id')
        if not isinstance(identity, str) or not identity or identity in by_call:
            raise ComparisonError('Invalid or duplicate call ID')
        by_call[identity] = call
    if manifest.get('actual_calls') != len(calls):
        raise ComparisonError('Actual call count does not match the frozen ledger')
    attributed = set()
    for key, entry in paired.items():
        for stage in STAGES:
            ids = entry['row'].get(stage, {}).get('call_ids')
            if ids is None:
                continue
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
                raise ComparisonError('Invalid stage call IDs')
            if set(ids) - set(by_call) or attributed.intersection(ids):
                raise ComparisonError('Missing or multiply attributed stage call')
            if any(by_call[identity].get('job_id') != f'{key[0]}_{key[1]}' for identity in ids):
                raise ComparisonError('A stage call belongs to another case/repeat')
            attributed.update(ids)
    if _read(directory / 'manifest.json') != manifest:
        raise ComparisonError('Run manifest changed while reading; comparison refused')
    return {'path': str(directory), 'manifest': manifest, 'cases': by_id, 'entries': paired,
            'calls': by_call, 'unattributed_call_ids': sorted(set(by_call) - attributed)}


def _verifier(manifest):
    result = {}
    for field in ('verifier_model', 'verifier_parameters', 'verifier_timeout', 'verifier_endpoint_signature'):
        value = manifest.get(field)
        invalid = (not isinstance(value, dict) or not value) if field == 'verifier_parameters' else (
            not _number(value) or value == 0) if field == 'verifier_timeout' else (
            not isinstance(value, str) or not value.strip())
        if invalid:
            raise ComparisonError(f'Missing verifier control: {field}')
        result[field] = value
    return result


def _analyst(manifest):
    return {'model': manifest.get('model'),
            'parameters': deepcopy(manifest.get('analyst_parameters', manifest.get('parameters'))),
            'timeout': manifest.get('analyst_timeout'),
            'endpoint_signature': manifest.get('endpoint_signature'),
            'run_call_cap': manifest.get('call_cap'),
            'max_prompt_bytes': manifest.get('max_prompt_bytes')}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _usage(call, field):
    usage = call.get('usage', {})
    if not isinstance(usage, dict):
        return None
    value = usage.get(field)
    if field == 'reasoning_tokens' and not _number(value):
        details = usage.get('completion_tokens_details', {})
        value = details.get(field) if isinstance(details, dict) else None
    return value if _number(value) else None


def _meter(calls):
    totals = {}
    missing = {}
    for field in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'cost'):
        values = [_usage(call, field) for call in calls]
        known = [value for value in values if value is not None]
        missing[field] = len(values) - len(known)
        totals[field] = {'known_sum': sum(known), 'complete_total': sum(known) if not missing[field] else None}
    return {'call_count': len(calls), 'usage': totals, 'calls_missing_usage': missing,
            'response_models': sorted({call['response_model'] for call in calls if isinstance(call.get('response_model'), str)})}


def _stage(run, row, stage):
    record = row.get(stage, {})
    ids = record.get('call_ids')
    calls = None if ids is None else [run['calls'][identity] for identity in ids]
    # A never-started stage has zero calls, while legacy missing attribution
    # remains unknown. No cost or token value is invented for either case.
    if not record:
        calls = []
    return {'status': record.get('status', 'not_attempted'),
            'error_type': record.get('error_type'), 'error_code': record.get('error_code'),
            'validation_issues': deepcopy(record.get('validation_issues', [])),
            'duration_ms': record.get('duration_ms'),
            'call_attribution': 'not_called' if not record else 'recorded' if ids is not None else 'unknown',
            'metering': _meter(calls) if calls is not None else None}


def _side(run, entry, case):
    row = entry['row']
    verifier = row.get('verification', {})
    valid = verifier.get('status') == 'validated'
    checks = verifier.get('result', {}).get('checks', {}) if valid else {}
    content = {name: deepcopy(checks.get(name, {'status': 'not_verified'})) for name in CONTENT_CHECKS}
    statuses = [content[name].get('status') for name in CONTENT_CHECKS]
    expected = case.get('expected', {}).get('content_status')
    all_pass = all(status == 'pass' for status in statuses)
    any_fail = any(status == 'fail' for status in statuses)
    decision = deepcopy(row.get('decision', {}))
    final_status = decision.get('status', 'unavailable')
    grade_class = ('singleton' if final_status == 'assessed' and len(decision.get('candidates', [])) == 1
                   else 'boundary' if final_status == 'boundary' else 'abstain')
    return {'record_status': row['status'], 'input_hash_origin': entry['input_hash_origin'],
            'analysis': _stage(run, row, 'analysis'),
            'analysis_candidates': deepcopy(row.get('analysis', {}).get('result', {}).get('decision', {}).get('candidates')),
            'verification': _stage(run, row, 'verification'),
            'verifier_reported_solution_correct': deepcopy(checks.get('solution_correct', {'status': 'not_verified'})),
            'independent_solution_correctness': 'unknown', 'content_checks': content,
            'all_content_checks_passed': all_pass if valid else None,
            'content_false_clear_against_expected': (all_pass if valid else None) if expected == 'fail' else None,
            'content_false_issue_against_expected': (any_fail if valid else None) if expected == 'pass' else None,
            'content_evaluation_scope': 'against_saved_expectations_not_independent_teacher_gold',
            'final': decision, 'grade_class': grade_class, 'duration_ms': row.get('duration_ms')}


def compare_runs(baseline_directory, candidate_directory):
    baseline = _load_run(baseline_directory)
    candidate = _load_run(candidate_directory)
    for field in ('protocol_sha256', 'dataset_sha256'):
        if baseline['manifest'][field] != candidate['manifest'][field]:
            raise ComparisonError(f'Unpaired runs: {field} differs')
    verifier = _verifier(baseline['manifest'])
    if verifier != _verifier(candidate['manifest']):
        raise ComparisonError('Unpaired runs: verifier model, parameters, timeout or endpoint differs')
    if set(baseline['entries']) != set(candidate['entries']):
        raise ComparisonError('Unpaired runs: case/repeat sets differ')
    pairs = []
    for key in sorted(baseline['entries']):
        left, right = baseline['entries'][key], candidate['entries'][key]
        if left['input_sha256'] != right['input_sha256']:
            raise ComparisonError('Unpaired runs: per-case input hashes differ')
        case = baseline['cases'][key[0]]
        pairs.append({'case_id': key[0], 'repeat': key[1], 'input_sha256': left['input_sha256'],
                      'saved_content_expectation': case.get('expected', {}).get('content_status'),
                      'label_provenance': case.get('label_provenance', 'unknown'),
                      'baseline': _side(baseline, left, case), 'candidate': _side(candidate, right, case)})
    summaries = {}
    for label, run in (('baseline', baseline), ('candidate', candidate)):
        sides = [pair[label] for pair in pairs]
        summaries[label] = {
            'submitted_case_repeats': len(pairs),
            'record_status_counts': dict(Counter(side['record_status'] for side in sides)),
            'grade_class_counts': dict(Counter(side['grade_class'] for side in sides)),
            'final_status_counts': dict(Counter(side['final'].get('status', 'unavailable') for side in sides)),
            'verifier_reported_solution_check_counts': dict(Counter(
                side['verifier_reported_solution_correct'].get('status', 'not_verified') for side in sides)),
            'content_false_clears_against_expected': [
                {'case_id': pair['case_id'], 'repeat': pair['repeat']} for pair in pairs
                if pair[label]['content_false_clear_against_expected'] is True],
            'content_false_issues_against_expected': [
                {'case_id': pair['case_id'], 'repeat': pair['repeat']} for pair in pairs
                if pair[label]['content_false_issue_against_expected'] is True],
            'content_not_verified': sum(side['all_content_checks_passed'] is None for side in sides),
            'metering': _meter(list(run['calls'].values())),
            'unattributed_call_ids': run['unattributed_call_ids']}
    analyst = {'baseline': _analyst(baseline['manifest']), 'candidate': _analyst(candidate['manifest'])}
    return {'kind': 'difficulty-review-configuration-comparison', 'paired': True,
            'comparison_scope': 'analyst_configuration_combination_not_single_factor_causal_estimate',
            'baseline_run': baseline['path'], 'candidate_run': candidate['path'],
            'controls': {'protocol_sha256': baseline['manifest']['protocol_sha256'],
                         'dataset_sha256': baseline['manifest']['dataset_sha256'], 'verifier': verifier},
            'analyst_configurations': analyst,
            'analyst_configuration_differences': [field for field in analyst['baseline']
                if analyst['baseline'][field] != analyst['candidate'][field]],
            'teacher_accuracy': 'unknown', 'independent_solution_accuracy': 'unknown',
            'statistical_significance': 'not_estimated', 'production_ready': False,
            'summaries': summaries, 'pairs': pairs}


def markdown_report(report):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')

    rows = ['# 分析端配置组合的配对比较', '',
            '仅比较相同协议、数据和核验配置。解答检查是核验模型报告；教师准确率与独立解答正确率均未知。', '',
            '| 案例 / 重复 | 配置 | 分析结构 | 核验解答检查 | 内容检查 | 最终判定 / 候选 |',
            '|---|---|---|---|---|---|']
    for pair in report['pairs']:
        for name in ('baseline', 'candidate'):
            side = pair[name]
            content = ', '.join(f'{key}:{value.get("status", "unknown")}' for key, value in side['content_checks'].items())
            final = f'{side["final"].get("status", "unavailable")} / {side["final"].get("candidates", [])}'
            values = (f'{pair["case_id"]} / {pair["repeat"]}', name, side['analysis']['status'],
                      side['verifier_reported_solution_correct'].get('status', 'not_verified'), content, final)
            rows.append('| ' + ' | '.join(cell(value) for value in values) + ' |')
    rows.extend(['', '失败、未尝试及弃判均保留。内容误放按保存的开发预期计算，即使最终弃判也记录；它不是教师金标准准确率。',
                 '各阶段耗时、调用归属、token 与费用缺项见同名 JSON；缺项没有按零计费。', ''])
    return '\n'.join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--markdown', type=Path)
    args = parser.parse_args(argv)
    report = compare_runs(args.baseline, args.candidate)
    outputs = [path.resolve() for path in (args.output, args.markdown) if path is not None]
    roots = [args.baseline.resolve(), args.candidate.resolve()]
    if len(outputs) != len(set(outputs)) or any(path.exists() for path in outputs):
        raise ComparisonError('Comparison outputs must be new, distinct files')
    if any(path == root or root in path.parents for path in outputs for root in roots):
        raise ComparisonError('Do not write comparison results inside frozen run directories')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.markdown.open('x') as handle:
            handle.write(markdown_report(report))
    return report


if __name__ == '__main__':
    main()
