"""Recompute H6 archive counts without credentials, providers, or model calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False).encode()).hexdigest()


def harness_reports(value):
    if isinstance(value, dict):
        if 'session_id' in value and 'model_calls' in value and 'phase' in value:
            yield value
        else:
            for child in value.values():
                yield from harness_reports(child)
    elif isinstance(value, list):
        for child in value:
            yield from harness_reports(child)


def summarize_group(name):
    folder = ROOT / 'docs/agent/harness-experiments' / (name + '_20260919')
    manifest = json.loads((folder / 'manifest.json').read_text())
    rows = json.loads((folder / 'results.json').read_text())
    assert len(rows) == len(manifest['plan']), 'An experiment is still incomplete.'
    assert len({row['task_id'] for row in rows}) == len(rows)
    assert [row['task_id'] for row in rows] == [entry['task_id'] for entry in manifest['plan']]
    for relative, sha in manifest['code_sha256'].items():
        assert hashlib.sha256((folder / 'code' / relative).read_bytes()).hexdigest() == sha, relative
    assert digest(json.loads((folder / 'frozen_cases.json').read_text())) == manifest['frozen_cases_sha256']
    tasks = []
    for row in rows:
        record_path = folder / row['evidence_file']
        record = json.loads(record_path.read_text())
        calls = record['calls']
        assert calls == row['calls'] and len(calls) == row['actual_calls']
        assert row['status'] == record['job']['status']
        agent = record['evidence'].get('agent', {})
        slots = agent.get('slots', [])
        reports = list(harness_reports(agent))
        model_calls = [call for report in reports for call in report['model_calls']]
        assert len(model_calls) == len(calls), 'Harness audit / provider ledger mismatch.'
        succeeded_models = [call for call in model_calls if call.get('status') == 'succeeded']
        succeeded_ledger = [call for call in calls if call['status'] == 'succeeded']
        assert Counter(digest({'model': call['request']['model'], 'usage': call['response']['usage']})
                       for call in succeeded_models) == Counter(
                           digest({'model': call['model'], 'usage': call['usage']}) for call in succeeded_ledger)
        sessions = [report['session_id'] for report in reports]
        assert len(sessions) == len(set(sessions)), 'Role sessions were reused.'
        proposal = [report for report in reports if report['phase'] in ('plan', 'author')]
        assert all(report['proposal_only'] and report['tools'] == [] for report in proposal)
        assert all(call['request']['max_tokens'] == 32768 for call in model_calls)
        accepted = sum(slot['status'] == 'passed' for slot in slots)
        assert all(slot.get('accepted_asset') for slot in slots if slot['status'] == 'passed')
        assert accepted == row.get('accepted_questions', 0)
        usage = [call['usage'] for call in calls]
        costs = [entry['cost'] for entry in usage if type(entry.get('cost')) in (int, float)]
        reasoning = [entry['completion_tokens_details']['reasoning_tokens'] for entry in usage
                     if 'reasoning_tokens' in entry.get('completion_tokens_details', {})]
        tasks.append({
            'id': row['id'], 'job_id': row['job_id'], 'status': row['status'], 'agent_status': row.get('agent_status'),
            'archive_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
            'planned_questions': row['question_count'],
            'attempted_questions': sum(bool(slot['attempts']) for slot in slots),
            'candidate_attempts': sum(len(slot['attempts']) for slot in slots),
            'author_completed_candidates': sum('response' in attempt.get('author', {})
                                               for slot in slots for attempt in slot['attempts']),
            'compiled_candidates': sum(bool(attempt.get('compiled_spec'))
                                       for slot in slots for attempt in slot['attempts']),
            'accepted_questions': accepted,
            'published_questions': accepted if row['status'] == 'succeeded' else 0,
            'actual_calls': len(calls),
            'provider_statuses': dict(Counter(call['status'] for call in calls)),
            'http_statuses': dict(Counter(str(call['http_status']) for call in calls)),
            'requested_models': sorted(set(call['model'] for call in calls)),
            'response_models': sorted(set(call['response_model'] for call in calls if call['response_model'])),
            'known_total_tokens': sum(entry.get('total_tokens', 0) for entry in usage),
            'tokens_missing_calls': sum('total_tokens' not in entry for entry in usage),
            'known_reasoning_tokens': sum(reasoning), 'reasoning_missing_calls': len(calls) - len(reasoning),
            'known_cost_usd': sum(costs) if costs else None, 'cost_missing_calls': len(calls) - len(costs),
            'api_duration_ms_sum': sum(call.get('duration_ms') or 0 for call in calls),
            'role_sessions': len(sessions),
            'calls_by_phase': dict(Counter(report['phase'] for report in reports for _ in report['model_calls'])),
            'proposal_sessions_with_no_tools': len(proposal),
            'max_audit_json_request_chars': max((len(json.dumps(call['request'], ensure_ascii=False))
                                                 for call in model_calls), default=0),
            'length_finish_count': sum(choice.get('finish_reason') == 'length' for call in model_calls
                                       for choice in call.get('response', {}).get('choices', [])),
            'slots': [{'id': slot['slot_id'], 'status': slot['status'],
                       'attempts': len(slot['attempts']),
                       'dispatch_count': slot.get('worker', {}).get('dispatch_count', 0)} for slot in slots],
        })
    sum_fields = ('planned_questions', 'attempted_questions', 'candidate_attempts', 'author_completed_candidates',
                  'compiled_candidates', 'accepted_questions',
                  'published_questions', 'actual_calls', 'known_total_tokens', 'tokens_missing_calls',
                  'known_reasoning_tokens', 'reasoning_missing_calls', 'cost_missing_calls',
                  'api_duration_ms_sum', 'length_finish_count')
    assert sum(task['actual_calls'] for task in tasks) <= manifest['call_cap']
    return {'name': name, 'declared_group_call_cap': manifest['call_cap'],
            'code_files_verified': len(manifest['code_sha256']),
            'planned_tasks': len(manifest['plan']),
            'succeeded_tasks': sum(task['status'] == 'succeeded' for task in tasks),
            **{key: sum(task[key] for task in tasks) for key in sum_fields}, 'tasks': tasks}


if __name__ == '__main__':
    groups = [summarize_group(name) for name in ('H6A', 'H6B', 'H6C', 'H6D')]
    jobs = [task['job_id'] for group in groups for task in group['tasks']]
    assert len(jobs) == len(set(jobs))
    fields = ('planned_tasks', 'succeeded_tasks', 'planned_questions', 'attempted_questions',
              'candidate_attempts', 'author_completed_candidates', 'compiled_candidates',
              'accepted_questions', 'published_questions', 'actual_calls',
              'known_total_tokens', 'tokens_missing_calls', 'known_reasoning_tokens',
              'reasoning_missing_calls', 'cost_missing_calls', 'api_duration_ms_sum', 'length_finish_count')
    totals = {key: sum(group[key] for group in groups) for key in fields}
    assert totals['actual_calls'] <= 48
    result = {'schema': 'h6-supervisor-experiment-summary-v1', 'turn_call_cap': 48,
              'groups': groups, 'totals': totals,
              'limitations': [
                  'Development runs with AI-authored fixtures; retrieval is bypassed.',
                  'H6C and H6D are adaptive fresh-generation tests with revised renderer/planning prompts, not paired ablations.',
                  'Accepted and published describe the pipeline gates, not independently proven correctness or difficulty.',
                  'Pending questions remain in planned denominators and are not counted as numerically incorrect.',
                  'Attempted questions and candidate attempts count created attempt records, not completed outputs; author_completed_candidates and compiled_candidates are separate.',
                  'Missing provider cost is unknown, not zero.',
                  'Audit JSON request characters are not exact wire bytes or model context tokens.',
                  'Role sessions and per-question workers are isolated; dispatch is serial, not concurrent.',
              ]}
    destination = Path(__file__).with_name('H6_RESULTS_20260919.json')
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(destination), **totals}, ensure_ascii=False))
