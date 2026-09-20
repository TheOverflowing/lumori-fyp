"""Audit completed H7 archives using only the Python standard library.

No provider imports, environment loading, code execution from snapshots or API
calls. Results describe preserved evidence, not independent semantic grading.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[3]
GROUPS = ('H7A', 'H7B', 'H7C')
GROUP_CAPS = {'H7A': 24, 'H7B': 12, 'H7C': 9}
TURN_CAP = 36
TERMINAL_JOBS = {'succeeded', 'failed', 'insufficient_evidence'}
SUM_FIELDS = ('planned_tasks', 'succeeded_tasks', 'planned_questions', 'attempted_questions',
              'candidate_attempts', 'compiled_candidates', 'composed_candidates',
              'reused_authors_without_call', 'accepted_questions', 'published_questions',
              'actual_calls', 'relay_attempts', 'unreserved_relay_attempts', 'schema_repair_calls', 'evidence_repair_calls',
              'candidate_repair_calls', 'known_total_tokens', 'tokens_missing_calls',
              'known_reasoning_tokens', 'reasoning_missing_calls', 'cost_missing_calls',
              'api_duration_ms_sum', 'length_finish_count')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def digest(value, *, sorted_keys=True, compact=False):
    options = {'ensure_ascii': False, 'allow_nan': False, 'sort_keys': sorted_keys}
    if compact:
        options['separators'] = (',', ':')
    return hashlib.sha256(json.dumps(value, **options).encode()).hexdigest()


def fingerprint(value):
    return digest(value, sorted_keys=False)


def safe_child(folder, relative):
    child = (folder / relative).resolve()
    require(child.is_relative_to(folder.resolve()), 'Archive path escapes its declared directory.')
    return child


def invocations(value, path=()):
    if isinstance(value, dict):
        if isinstance(value.get('harness'), dict) and 'started_at' in value:
            yield path, value, value['harness']
        for key, child in value.items():
            if key != 'harness':
                yield from invocations(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from invocations(child, path + (index,))


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def metering(value):
    """Match the frozen provider's numeric-only usage export without importing it."""
    if not isinstance(value, dict):
        return {}
    numeric_keys = {'prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens',
                    'search_units', 'prompt_cache_hit_tokens', 'prompt_cache_miss_tokens', 'cached_tokens',
                    'reasoning_tokens', 'audio_tokens', 'accepted_prediction_tokens',
                    'rejected_prediction_tokens', 'cost', 'upstream_inference_cost'}
    details = {'prompt_tokens_details', 'completion_tokens_details', 'input_tokens_details',
               'output_tokens_details', 'cost_details'}
    result = {}
    for key, entry in value.items():
        if key in numeric_keys and number(entry) is not None and entry >= 0:
            result[key] = entry
        elif key in details and isinstance(entry, dict):
            result[key] = metering(entry)
    return result


def effective_response(attempt, role):
    return (attempt.get(role + '_evidence_repair', {}).get('response')
            or attempt.get(role + '_schema_repair', {}).get('response')
            or attempt.get(role, {}).get('response'))


def review_question(attempt):
    for role in ('review_evidence_repair', 'review_schema_repair', 'review'):
        for invocation in reversed(attempt.get(role, {}).get('history', [])):
            messages = invocation.get('messages', [])
            if len(messages) > 1:
                contract = json.loads(messages[1]['content'])
                if isinstance(contract.get('question'), dict):
                    return contract['question']
    return None


def check_requirements(attempt, brief, sources):
    coverage = attempt.get('quality_checks', {}).get('requirements', {})
    review = effective_response(attempt, 'review') or {}
    checks = review.get('requirement_checks', [])
    requirements = brief.get('requirements', [])
    expected_ids = [item['id'] for item in requirements]
    require(expected_ids == [f'r{index+1}' for index in range(len(expected_ids))],
            'Noncanonical requirement IDs in frozen plan.')
    question = review_question(attempt)
    exact_coverage = (isinstance(checks, list)
                      and [item.get('id') for item in checks] == expected_ids)
    findings = []
    by_id = {item['id']: item for item in requirements}
    for check in checks:
        requirement = by_id.get(check.get('id'), {})
        allowed = set(requirement.get('source_ids', [])) & set(brief.get('source_ids', [])) & set(sources)
        if question:
            allowed &= set(question.get('citation_ids', []))
        citations = check.get('source_ids', [])
        source_valid = len(citations) == len(set(citations)) and set(citations) <= allowed
        met = check.get('status') == 'met'
        stem_quote, answer_quote = check.get('stem_evidence', ''), check.get('answer_evidence', '')
        excerpt_valid = bool(question and len(stem_quote) >= 8 and len(answer_quote) >= 8
                             and stem_quote in question.get('stem', '')
                             and any(answer_quote in question.get(field, '') for field in ('answer', 'explanation')))
        structurally_valid = source_valid and (not met or (excerpt_valid and bool(citations)))
        findings.append({'id': check.get('id'), 'model_status': check.get('status'),
                         'source_scope_valid': source_valid,
                         'met_excerpts_exist': excerpt_valid if met else None,
                         'structurally_valid': structurally_valid})
    if coverage:
        require(checks == coverage.get('checks'), 'Requirement response differs from gate evidence.')
    if coverage.get('status') == 'passed':
        require(exact_coverage and bool(checks) and all(
            item['model_status'] == 'met' and item['structurally_valid'] for item in findings),
            'A requirement gate passed without complete valid excerpts and scoped citations.')
    return {'status': coverage.get('status', 'not_recorded'),
            'issues': coverage.get('issues', []), 'planned_requirements': len(requirements),
            'reported_checks': len(checks), 'exact_id_coverage': exact_coverage,
            'checks': findings, 'semantic_correctness': 'not_established_by_this_audit'}


def check_cpu_attempt(attempt, previous, language, accepted_asset=None):
    compiled = attempt.get('compiled_spec')
    if not compiled:
        return None
    base = attempt.get('base_asset')
    require(isinstance(base, dict), 'CPU v2 candidate has no immutable base asset.')
    require(fingerprint(base) == attempt.get('compiled_asset_sha256'), 'CPU base hash mismatch.')
    require(digest(compiled['canonical_spec'], compact=True) == compiled['spec_sha256'],
            'CPU canonical specification hash mismatch.')
    fact_hash = fingerprint({'spec_sha256': compiled['spec_sha256'],
                             'tool_results': compiled['tool_results'],
                             'compiled_asset_sha256': attempt['compiled_asset_sha256']})
    reused = attempt.get('author', {}).get('origin') == 'reused_frozen_spec'
    if reused:
        original_number = attempt['author']['original_attempt']
        origin = next((a for a in previous if a['number'] == original_number), None)
        require(origin is not None, 'Reused author points to a missing original attempt.')
        require(attempt['author'].get('history') == [], 'Reused author unexpectedly contains a model invocation.')
        require(attempt['author']['response'] == origin['author']['response'], 'Reused author changed specification.')
        require(attempt['author']['original_spec_sha256'] == origin['compiled_spec']['spec_sha256']
                == compiled['spec_sha256'], 'Reused CPU spec SHA changed.')
        require(base == origin['base_asset'] and attempt['compiled_asset_sha256'] == origin['compiled_asset_sha256'],
                'Narrative repair changed the immutable numerical base.')
        require(compiled['tool_results'] == origin['compiled_spec']['tool_results'],
                'Narrative repair changed compiled tool facts.')
    narrative = effective_response(attempt, 'compose')
    composition_verified = False
    if attempt.get('composed_asset_sha256'):
        require(narrative and narrative.get('evidence_sufficient') is True, 'Composed hash has no successful narrative.')
        composed = deepcopy(base)
        question = composed['questions'][0]
        label = '进一步分析：' if language == 'zh' else 'Further analysis:'
        for field, addition in [('stem', 'additional_task'), ('answer', 'answer'), ('explanation', 'explanation')]:
            question[field] += '\n\n' + label + '\n' + narrative[addition]
        brief_goal = attempt['_audit_brief']['learning_goal']
        composed['learning_objectives'] = list(dict.fromkeys([*composed['learning_objectives'], brief_goal]))
        require(fingerprint(composed) == attempt['composed_asset_sha256'], 'Appended narrative composition hash mismatch.')
        # No model or compiler is executed to verify that the exact frozen
        # numerical text remains an unchanged prefix of the resulting asset.
        if accepted_asset:
            accepted_question = deepcopy(accepted_asset['questions'][0])
            accepted_question['slot_id'] = question['slot_id']
            require(accepted_question == question, 'Accepted CPU question differs from verified composition.')
            require(accepted_asset['sections'] == base['sections'], 'CPU narrative replaced base teaching sections.')
        composition_verified = True
    return {'spec_sha256': compiled['spec_sha256'], 'immutable_facts_sha256': fact_hash,
            'base_asset_sha256': attempt['compiled_asset_sha256'],
            'composed_asset_sha256': attempt.get('composed_asset_sha256'),
            'composition_hash_verified': composition_verified,
            'author_reused_without_invocation': reused,
            'numerical_correctness': 'not_recomputed_by_this_audit',
            'narrative_claim_correctness': 'requires_independent_content_review'}


def database_records(folder):
    path = folder / 'runtime/studio.sqlite3'
    require(path.is_file(), 'Completed live group has no experiment ledger database.')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        calls = [dict(row) for row in connection.execute('SELECT * FROM calls ORDER BY created_at')]
        jobs = [dict(row) for row in connection.execute('SELECT * FROM jobs')]
        contents = [dict(row) for row in connection.execute('SELECT * FROM contents')]
    return calls, jobs, contents


def audit_calls(agent, calls):
    invocation_records = list(invocations(agent))
    assigned = [[] for _ in invocation_records]
    for call in calls:
        created = datetime.fromisoformat(call['created_at'])
        matches = [index for index, (_, inv, _) in enumerate(invocation_records)
                   if 'ended_at' in inv and datetime.fromisoformat(inv['started_at']) <= created
                   <= datetime.fromisoformat(inv['ended_at'])]
        require(len(matches) == 1, 'A ledger call cannot be uniquely assigned to a recorded role invocation.')
        assigned[matches[0]].append(call)
    sessions, phases, schemas, evidence_repairs, repaired, unreserved, audits = [], Counter(), Counter(), Counter(), Counter(), 0, []
    for index, (path, inv, report) in enumerate(invocation_records):
        require(inv.get('status') != 'in_flight' and report.get('status') not in ('starting', 'running'),
                'A requested group still contains an unfinished role invocation.')
        if report.get('session_id'):
            sessions.append(report['session_id'])
        phase = report.get('phase', next((str(part) for part in path if part in
            ('plan', 'author', 'compose', 'solve', 'review')), 'unknown'))
        model_calls = report.get('model_calls', [])
        ledger = assigned[index]
        require(len(model_calls) >= len(ledger), 'Reserved calls missing from the Harness audit.')
        completed = [call for call in model_calls if call.get('status') == 'succeeded']
        paid_completed = [call for call in ledger if call['status'] == 'succeeded']
        require(Counter(digest({'model': c['request']['model'], 'usage': c['response'].get('usage', {})}) for c in completed)
                == Counter(digest({'model': c['model'], 'usage': c['usage']}) for c in paid_completed),
                'Successful Harness responses and ledger usage/model records differ.')
        failed_responses = [c for c in model_calls if c.get('raw_response')]
        failed_metered = [c for c in ledger if c['status'] != 'succeeded' and (c['usage'] or c['response_model'])]
        require(Counter(digest({'model': c['request']['model'], 'usage': metering(c['raw_response'].get('usage', {}))})
                        for c in failed_responses) == Counter(digest({'model': c['model'], 'usage': c['usage']})
                                                              for c in failed_metered),
                'Failed upstream responses and recorded metering differ.')
        extra = len(model_calls) - len(ledger)
        require(extra <= sum(c.get('status') in ('failed', 'cancelled') and not c.get('response')
                             and not c.get('raw_response') for c in model_calls),
                'Unreserved relay attempt unexpectedly has an upstream response.')
        unreserved += extra
        phases[phase] += len(ledger)
        if phase.endswith('_schema_repair'):
            schemas[phase] += len(ledger)
        if phase.endswith('_evidence_repair'):
            evidence_repairs[phase] += len(ledger)
        # Attempt lists are zero-based. All roles in index >= 1 are candidate
        # repairs; this overlaps schema-repair counts and is not additive.
        if 'attempts' in path and path[path.index('attempts') + 1] >= 1:
            repaired[phase] += len(ledger)
        proposal = phase.removesuffix('_schema_repair') in ('plan', 'author', 'compose')
        if proposal and report.get('session_id'):
            require(report.get('proposal_only') is True and report.get('tools') == [],
                    'Planner/author/composer unexpectedly had tools.')
        for entry in model_calls:
            require(entry['request']['max_tokens'] == 32768, 'Unexpected output-token budget.')
            require(entry['request'].get('thinking') == {'type': 'enabled'}, 'Thinking mode differs from plan.')
            require(entry['request'].get('response_format') == {'type': 'json_object'}, 'JSON mode differs from plan.')
            if proposal:
                require(not entry['request'].get('tools'), 'Proposal request offered model tools.')
        audits.extend(model_calls)
    require(len(sessions) == len(set(sessions)), 'Role sessions were reused within a task.')
    return {'sessions': sessions, 'calls_by_phase': dict(phases), 'schema_repair_calls_by_phase': dict(schemas),
            'evidence_repair_calls_by_phase': dict(evidence_repairs),
            'candidate_repair_calls_by_phase': dict(repaired), 'unreserved_relay_attempts': unreserved,
            'relay_attempts': len(audits), 'schema_repair_calls': sum(schemas.values()),
            'evidence_repair_calls': sum(evidence_repairs.values()),
            'candidate_repair_calls': sum(repaired.values()),
            'max_audit_json_request_chars': max((len(json.dumps(c['request'], ensure_ascii=False)) for c in audits), default=0),
            'length_finish_count': sum(choice.get('finish_reason') == 'length' for c in audits
                for choice in (c.get('response') or c.get('raw_response') or {}).get('choices', []))}


def summarize_group(name):
    folder = ROOT / 'docs/agent/flexible-experiments' / (name + '_20260919')
    manifest, rows = read_json(folder / 'manifest.json'), read_json(folder / 'results.json')
    require(manifest['live'] is True, 'Dry plans are not live experiment results.')
    require(len(rows) == len(manifest['plan']), f'{name} is incomplete: not all planned tasks are archived.')
    require([row['task_id'] for row in rows] == [entry['task_id'] for entry in manifest['plan']], 'Task plan/order mismatch.')
    require(len({row['task_id'] for row in rows}) == len(rows), 'Duplicate task IDs within one group.')
    require(manifest['call_cap'] <= GROUP_CAPS[name], 'Declared group cap exceeds the predeclared experiment cap.')
    require(manifest['orchestration'] == 'supervisor_v2', 'Wrong orchestration mode.')
    for relative, expected in manifest['code_sha256'].items():
        require(hashlib.sha256(safe_child(folder / 'code', relative).read_bytes()).hexdigest() == expected,
                'Archived code/data SHA mismatch: ' + relative)
    require('app/assessment_contracts.py' in manifest['code_sha256'], 'Missing v2 contract snapshot.')
    frozen = read_json(folder / 'frozen_cases.json')
    require(digest(frozen) == manifest['frozen_cases_sha256'], 'Frozen source SHA mismatch.')
    for key, path in [('flexible_answers', 'benchmarks/agent/flexible_answers.json'),
                      ('difficulty_cases', 'benchmarks/difficulty/cases.json')]:
        require(digest(read_json(folder / 'code' / path)) == manifest['dataset_sha256'][key], 'Source dataset SHA mismatch.')
    db_calls, db_jobs, db_contents = database_records(folder)
    db_jobs = {job['id']: job for job in db_jobs}
    tasks = []
    for row in rows:
        archive_path = safe_child(folder, row['evidence_file'])
        archive = read_json(archive_path)
        calls, job = archive['calls'], archive['job']
        require(calls == row['calls'] and len(calls) == row['actual_calls'], 'Exported call ledger mismatch.')
        if job is None:
            require(row['status'] == 'not_run_budget_exhausted' and not calls, 'Unrun task has unexpected records.')
            require(len(db_calls) >= manifest['call_cap'], 'Budget exhaustion reported before reaching the cap.')
            agent, slots = {}, []
        else:
            require(job['status'] in TERMINAL_JOBS, f'{name} contains a nonterminal job.')
            require(job == db_jobs[job['id']], 'Job archive differs from experiment database.')
            require(job['status'] == row['status'] and job['id'] == row['job_id'], 'Job identifiers/status mismatch.')
            expected_calls = [{key: json.loads(call['usage']) if key == 'usage' else call[key]
                               for key in ('capability', 'model', 'status', 'usage', 'created_at',
                                           'duration_ms', 'http_status', 'response_model')}
                              for call in db_calls if call['job_id'] == job['id']]
            require(calls == expected_calls, 'Case archive differs from the read-only SQLite call ledger.')
            require(all(call['status'] != 'started' for call in calls), 'An API call is unfinished.')
            agent = archive['evidence'].get('agent', {})
            slots = agent.get('slots', [])
            require(archive['evidence'].get('sources', []) == frozen[row['id']]['sources'], 'Task sources differ from frozen context.')
        call_audit = audit_calls(agent, calls)
        accepted = [slot for slot in slots if slot['status'] == 'passed']
        require(len(accepted) == row.get('accepted_questions', 0), 'Accepted-question count mismatch.')
        content = archive.get('published_content')
        published = len(content['asset']['questions']) if content and row['status'] == 'succeeded' else 0
        require(published == row.get('published_questions', 0), 'Actual published-question count mismatch.')
        if content:
            db_content = next((item for item in db_contents if item['id'] == content['id']), None)
            require(db_content is not None and db_content['job_id'] == row['job_id'], 'Published content has no matching DB row.')
            for key in ('asset', 'sources', 'config'):
                require(json.loads(db_content[key]) == content[key], 'Published content differs from its database row.')
        if published:
            require(content['asset']['questions'] == [slot['accepted_asset']['questions'][0] for slot in slots],
                    'Published assembly changed an accepted question.')
            require(fingerprint(content['asset']) == agent['supervisor']['assembled_asset_sha256'], 'Assembly SHA mismatch.')
            require(published == row['question_count'], 'Successful publication has the wrong requested count.')
        slot_records = []
        for slot in slots:
            brief = slot.get('brief', {})
            worker = slot.get('worker', {})
            if brief:
                require(fingerprint(brief) == worker.get('brief_sha256'), 'Worker brief hash mismatch.')
            attempts = []
            previous = []
            for original in slot.get('attempts', []):
                attempt = deepcopy(original)
                attempt['_audit_brief'] = brief
                passed_asset = slot.get('accepted_asset') if attempt.get('status') == 'passed' else None
                cpu = check_cpu_attempt(attempt, previous, frozen[row['id']]['language'], passed_asset)
                coverage = check_requirements(attempt, brief, {s['id'] for s in frozen[row['id']]['sources']})
                evidence_repair = None
                if 'review_evidence_repair' in attempt:
                    original_only = deepcopy(attempt)
                    original_only.pop('review_evidence_repair', None)
                    original_only.pop('review_schema_repair', None)
                    original_only.get('quality_checks', {}).pop('requirements', None)
                    original_coverage = check_requirements(original_only, brief, {s['id'] for s in frozen[row['id']]['sources']})
                    unchanged = review_question(original_only) == review_question(attempt)
                    require(unchanged, 'Evidence-only review retry changed the candidate question.')
                    evidence_repair = {
                        'status': attempt['review_evidence_repair'].get('status'),
                        'reason': attempt['review_evidence_repair'].get('reason'),
                        'same_candidate_question': unchanged,
                        'original_requirement_checks': original_coverage,
                        'final_requirement_checks': coverage,
                        'semantic_improvement': 'not_established_by_this_audit',
                    }
                if attempt.get('status') == 'passed':
                    require(coverage['status'] == 'passed', 'Accepted candidate lacks a passing requirements gate.')
                attempts.append({'number': attempt.get('number'), 'status': attempt.get('status'),
                    'quality_checks': attempt.get('quality_checks', {}),
                    'feedback_issues': attempt.get('feedback', {}).get('issues', []),
                    'feedback_validation': attempt.get('feedback', {}).get('validation'),
                    'next_repair_target': attempt.get('feedback', {}).get('repair_target'),
                    'requirements': coverage, 'review_evidence_repair': evidence_repair, 'cpu_facts': cpu})
                previous.append(original)
            if slot['status'] == 'passed':
                require(fingerprint(slot['accepted_asset']) == worker.get('asset_sha256'), 'Accepted worker asset SHA mismatch.')
            slot_records.append({'slot_id': slot['slot_id'], 'worker_id': worker.get('id'),
                                 'status': slot['status'], 'answer_policy': brief.get('answer_policy'),
                                 'brief_requirement_count': len(brief.get('requirements', [])), 'attempts': attempts})
        usage = [call['usage'] for call in calls]
        tokens = [number(u.get('total_tokens')) for u in usage]
        reasoning = [number(u.get('completion_tokens_details', {}).get('reasoning_tokens')) for u in usage]
        costs = [number(u.get('cost')) for u in usage]
        provenance = frozen[row['id']]['provenance']
        require(provenance['kind'].startswith('ai_') and provenance.get('original_source_excerpt') is False,
                'Unexpected source provenance for an AI fixture.')
        tasks.append({'id': row['id'], 'qualified_task_id': name + '/' + row['task_id'],
            'job_id': row.get('job_id'), 'status': row['status'], 'agent_status': row.get('agent_status'),
            'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            'question_spec': row['question_spec'], 'source_provenance': provenance,
            'planned_tasks': 1, 'succeeded_tasks': int(row['status'] == 'succeeded'),
            'planned_questions': row['question_count'],
            'attempted_questions': sum(bool(s.get('attempts')) for s in slots),
            'candidate_attempts': sum(len(s.get('attempts', [])) for s in slots),
            'compiled_candidates': sum(bool(a['cpu_facts']) for s in slot_records for a in s['attempts']),
            'composed_candidates': sum(bool(a['cpu_facts'] and a['cpu_facts']['composition_hash_verified'])
                                       for s in slot_records for a in s['attempts']),
            'reused_authors_without_call': sum(bool(a['cpu_facts'] and a['cpu_facts']['author_reused_without_invocation'])
                                              for s in slot_records for a in s['attempts']),
            'accepted_questions': len(accepted), 'published_questions': published,
            'actual_calls': len(calls), 'provider_statuses': dict(Counter(c['status'] for c in calls)),
            'http_statuses': dict(Counter(str(c['http_status']) for c in calls)),
            'requested_models': sorted({c['model'] for c in calls}),
            'response_models': sorted({c['response_model'] for c in calls if c['response_model']}),
            'known_total_tokens': sum(v for v in tokens if v is not None), 'tokens_missing_calls': tokens.count(None),
            'known_reasoning_tokens': sum(v for v in reasoning if v is not None), 'reasoning_missing_calls': reasoning.count(None),
            'known_cost_usd': sum(v for v in costs if v is not None) if any(v is not None for v in costs) else None,
            'cost_missing_calls': costs.count(None),
            'total_cost_usd': None if None in costs else sum(costs),
            'api_duration_ms_sum': sum(c.get('duration_ms') or 0 for c in calls),
            **call_audit, 'slots': slot_records})
    require(sum(t['actual_calls'] for t in tasks) == len(db_calls) <= manifest['call_cap'], 'Group call cap/ledger mismatch.')
    require(set(db_jobs) == {t['job_id'] for t in tasks if t['job_id']}, 'Experiment DB contains undeclared jobs.')
    aggregate = {key: sum(task[key] for task in tasks) for key in SUM_FIELDS}
    return {'name': name, 'declared_group_call_cap': manifest['call_cap'],
            'manifest_sha256': hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest(),
            'code_files_verified': len(manifest['code_sha256']),
            'frozen_cases_sha256': manifest['frozen_cases_sha256'],
            'revisions': {key: manifest.get(key) for key in ('agent_prompt_revision', 'flexible_planner_revision',
                'harness_quality_revision', 'harness_adapter_revision', 'harness_runtime_version', 'cpu_spec_revision')},
            'call_ids': [call['id'] for call in db_calls], **aggregate, 'tasks': tasks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups', nargs='+', choices=GROUPS, default=list(GROUPS),
                        help='Only completed groups are accepted; an omitted group is explicitly unaudited.')
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('H7_RESULTS_20260919.json'))
    args = parser.parse_args(argv)
    require(len(args.groups) == len(set(args.groups)), 'Duplicate requested groups.')
    groups = [summarize_group(name) for name in args.groups]
    tasks = [task for group in groups for task in group['tasks']]
    for values, label in [([task['qualified_task_id'] for task in tasks], 'group-qualified task'),
                          ([task['job_id'] for task in tasks if task['job_id']], 'job'),
                          ([call_id for group in groups for call_id in group['call_ids']], 'call'),
                          ([sid for task in tasks for sid in task['sessions']], 'session'),
                          ([slot['worker_id'] for task in tasks for slot in task['slots'] if slot['worker_id']], 'worker')]:
        require(len(values) == len(set(values)), 'Duplicate global ' + label + ' ID.')
    totals = {key: sum(group[key] for group in groups) for key in SUM_FIELDS}
    require(totals['actual_calls'] <= TURN_CAP, 'Combined H7 calls exceed the predeclared 36-call cap.')
    known_costs = [task['known_cost_usd'] for task in tasks if task['known_cost_usd'] is not None]
    totals['known_cost_usd'] = sum(known_costs) if known_costs else None
    totals['total_cost_usd'] = None if totals['cost_missing_calls'] else (sum(known_costs) if known_costs else 0)
    totals['total_tokens'] = None if totals['tokens_missing_calls'] else totals['known_total_tokens']
    omitted = [name for name in GROUPS if name not in args.groups]
    result = {'schema': 'h7-flexible-experiment-summary-v1', 'turn_call_cap': TURN_CAP,
              'requested_groups': args.groups, 'omitted_unaudited_groups': omitted,
              'coverage': 'partial_groups' if omitted else 'all_declared_groups',
              'adaptive_budget_note': 'H7A finished with 15 calls. H7B retains its 12-call cap; '
                  'the added H7C Chinese retry has a 9-call cap, so 15 + 12 + 9 <= 36. '
                  'H7A uses the original evidence-review protocol; later groups use the recorded revised protocol.',
              'groups': groups, 'totals': totals,
              'limitations': [
                  'Only the requested completed groups are audited; omitted groups have no manufactured outcomes or calls.',
                  'H7C is an adaptive follow-up after H7A, not part of the original two-group plan or a paired ablation.',
                  'AI fixtures are not human gold labels, original historical evidence or real-course RAG evaluation.',
                  'Requirement excerpt existence and scope are verified, not the semantic truth of model judgments.',
                  'Immutable CPU content and composition hashes are verified without recomputing mathematics or certifying added prose.',
                  'Accepted/published counts reflect recorded gates and stored output, not independently measured difficulty.',
                  'Reasoning tokens are a subset of completion/total tokens; they must not be added to total tokens again.',
                  'Unknown costs remain null. Known sums are partial when any calls lack usage fields.',
                  'Candidate-repair calls can include schema/evidence repair calls; these categories are not additive.',
                  'Unreserved failed relay attempts have no corresponding provider reservation and do not count as API calls.',
                  'Task names can repeat across isolated groups; group-qualified tasks and global job/call/session/worker IDs are checked.',
                  'Audit JSON character size is not an exact wire-byte size or model token count.',
              ]}
    totals['calls_by_phase'] = dict(sum((Counter(task['calls_by_phase']) for task in tasks), Counter()))
    totals['role_sessions'] = sum(len(task['sessions']) for task in tasks)
    all_attempts = [attempt for task in tasks for slot in task['slots'] for attempt in slot['attempts']]
    totals['candidate_attempt_statuses'] = dict(Counter(attempt['status'] for attempt in all_attempts))
    totals['review_evidence_repair_statuses'] = dict(Counter(
        attempt['review_evidence_repair']['status'] for attempt in all_attempts if attempt['review_evidence_repair']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'omitted_unaudited_groups': omitted, **totals}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    main()
