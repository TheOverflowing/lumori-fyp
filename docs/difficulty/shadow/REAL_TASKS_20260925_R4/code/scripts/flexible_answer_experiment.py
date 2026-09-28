"""Bounded supervisor_v2 development experiment; no model calls by default.

Frozen AI-authored humanities passages permit multiple defensible answers;
the existing CPU fixture exercises compiled facts plus narrative composition.
Production settings, courses and existing experiment archives are unchanged.
"""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.assessment_contracts import FLEXIBLE_PLANNER_REVISION, AssessmentPlan, RequirementCheck
from app.cpu_problem_spec import CPU_SPEC_REVISION
from app.generation_agent import PROMPT_REVISION, HARNESS_QUALITY_REVISION
from app.harness_profile import HARNESS_RUNTIME_VERSION
from app.harness_runner import ADAPTER_REVISION
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import dumps, now
from scripts.difficulty_experiment import CappedStore, digest, public_parameters, write_json
from scripts.difficulty_prompts import make_request


COURSE_ID = 'flexible-answer-experiment'
FIXTURE_PATH = ROOT / 'benchmarks/agent/flexible_answers.json'
CASE_IDS = ('humanities_zh', 'humanities_en', 'cpu_en')
LIMITATIONS = [
    'Development experiment with AI-authored sources and no human gold answers or empirical difficulty labels.',
    'Humanities passages describe fictional people, places and events; they are not real historical evidence.',
    'Chinese and English humanities cases use different topics; they are not a controlled translation pair.',
    'Frozen source snapshots bypass retrieval; this experiment does not measure RAG quality.',
    'CPU uses deterministic facts plus flexible composition; humanities use flexible authoring, so paths differ.',
    'Model acceptance and requirement checks are not independent correctness or human difficulty labels.',
    'Failed, rejected, interrupted and unrun planned questions remain in the denominator.',
    'Missing usage and cost fields remain unknown, not zero; known totals are partial when fields are missing.',
    'This small nonrandomized run cannot establish statistical superiority, generalization or production reliability.',
]


def select_cases(requested):
    selected = {piece.strip() for value in (requested or list(CASE_IDS))
                for piece in value.split(',') if piece.strip()}
    if not selected or not selected <= set(CASE_IDS):
        raise ValueError('Cases must be humanities_zh, humanities_en or cpu_en.')
    return [case_id for case_id in CASE_IDS if case_id in selected]


def frozen_cases(requested):
    dataset = json.loads(FIXTURE_PATH.read_text())
    by_id = {case['id']: case for case in dataset['cases']}
    if set(by_id) != set(CASE_IDS) or len(by_id) != len(dataset['cases']):
        raise ValueError('The fixture must contain exactly the three declared cases.')
    existing_path = ROOT / 'benchmarks/difficulty/cases.json'
    existing = json.loads(existing_path.read_text())
    existing_by_id = {case['id']: case for case in existing['cases']}
    result = {}
    for case_id in select_cases(requested):
        entry = deepcopy(by_id[case_id])
        if case_id == 'cpu_en':
            if entry['existing_case'] != {'path': 'benchmarks/difficulty/cases.json',
                                          'case_id': 'cpu_scheduling_en_hard'}:
                raise ValueError('CPU fixture must reference the frozen existing CPU case.')
            case = deepcopy(existing_by_id['cpu_scheduling_en_hard'])
            case['origin_case_id'] = case['id']
            case['id'] = case_id
            case['origin_dataset_sha256'] = digest(existing)
        else:
            case = entry
            if case['provenance']['kind'] != 'ai_authored_fictional_educational_fixture':
                raise ValueError('Humanities fixture provenance must remain explicit.')
        make_request(case)  # Validate before loading any provider settings.
        if not case['sources'] or len({s['id'] for s in case['sources']}) != len(case['sources']):
            raise ValueError('Frozen source IDs must be nonempty and unique within each case.')
        for source in case['sources']:
            if not source['text'].strip() or source['page'] is not None:
                raise ValueError('AI study fixtures need nonempty text and no invented page number.')
            source['document_id'] = 'fixture-doc-' + digest([COURSE_ID, case_id, source['id']])[:24]
        result[case_id] = case
    return result, {'flexible_answers': digest(dataset), 'difficulty_cases': digest(existing)}


def snapshot_code(output):
    # Archive all application Python modules, including new v2 contracts, along
    # with every imported experiment helper and both exact source datasets.
    files = sorted(path for path in (ROOT / 'app').rglob('*.py') if '__pycache__' not in path.parts)
    files += [ROOT / path for path in ('scripts/flexible_answer_experiment.py',
              'scripts/difficulty_experiment.py', 'scripts/difficulty_prompts.py',
              'benchmarks/agent/flexible_answers.json', 'benchmarks/difficulty/cases.json')]
    index = {}
    for source in files:
        relative = str(source.relative_to(ROOT))
        target = output / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        index[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    return index


def seed_documents(store, cases):
    store.execute('INSERT INTO courses VALUES(?,?,?)', (COURSE_ID, 'Isolated flexible-answer research fixtures', now()))
    for case in cases.values():
        for source in case['sources']:
            store.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',
                          (source['document_id'], COURSE_ID, source['document_name'],
                           digest(source['text']), 'indexed', 1, now()))


def question_records(evidence):
    """Compact index; the original complete attempts remain in the case archive."""
    records = []
    for slot in evidence.get('agent', {}).get('slots', []):
        attempts = []
        for attempt in slot.get('attempts', []):
            coverage = deepcopy(attempt.get('quality_checks', {}).get('requirements', {}))
            review = (attempt.get('review_evidence_repair', {}).get('response')
                      or attempt.get('review_schema_repair', {}).get('response')
                      or attempt.get('review', {}).get('response') or {})
            final_review_phase = next((phase for phase in ('review_evidence_repair', 'review_schema_repair', 'review')
                                       if attempt.get(phase, {}).get('response')), None)
            attempts.append({
                'number': attempt.get('number'), 'status': attempt.get('status'),
                'quality_checks': deepcopy(attempt.get('quality_checks', {})),
                'requirements': coverage,
                'requirement_checks': deepcopy(review.get('requirement_checks', [])),
                'final_review_phase': final_review_phase,
                'final_review_phase_status': attempt.get(final_review_phase, {}).get('status')
                    if final_review_phase else None,
                'repair_target': attempt.get('feedback', {}).get('repair_target'),
                'author_origin': deepcopy(attempt.get('author', {}).get('origin')),
                'compiled_asset_sha256': attempt.get('compiled_asset_sha256'),
                'composed_asset_sha256': attempt.get('composed_asset_sha256'),
            })
        records.append({'slot_id': slot.get('slot_id'), 'status': slot.get('status'),
                        'brief': deepcopy(slot.get('brief')), 'verification': slot.get('verification'),
                        'attempt_count': len(attempts), 'attempts': attempts,
                        'requirements_status': attempts[-1]['requirements'].get('status', 'not_recorded')
                            if attempts else 'not_recorded'})
    return records


def numeric_usage(call, key):
    value = (call.get('usage') or {}).get(key)
    return value if type(value) in (int, float) and math.isfinite(value) else None


def summarize(rows, plan):
    calls = [call for row in rows for call in row.get('calls', [])]
    known_tokens = sum(numeric_usage(call, 'total_tokens') or 0 for call in calls)
    known_cost = sum(numeric_usage(call, 'cost') or 0 for call in calls)
    missing_tokens = sum(numeric_usage(call, 'total_tokens') is None for call in calls)
    missing_cost = sum(numeric_usage(call, 'cost') is None for call in calls)
    questions = [question for row in rows for question in row.get('questions', [])]
    return {'planned_tasks': len(plan), 'planned_questions': sum(p['question_count'] for p in plan),
            'recorded_tasks': len(rows), 'status_counts': dict(Counter(row['status'] for row in rows)),
            'accepted_questions': sum(row.get('accepted_questions', 0) for row in rows),
            'published_questions': sum(row.get('published_questions', 0) for row in rows),
            'attempts': sum(q['attempt_count'] for row in rows for q in row.get('questions', [])),
            'requirements_status_counts': dict(Counter(q.get('requirements_status', 'not_recorded') for q in questions)),
            'requirement_verdict_counts_all_attempts': dict(Counter(
                check.get('status', 'not_recorded') for q in questions for attempt in q['attempts']
                for check in attempt.get('requirement_checks', []))),
            'actual_calls': len(calls),
            'provider_succeeded': sum(call['status'] == 'succeeded' for call in calls),
            'known_total_tokens': known_tokens, 'tokens_missing_calls': missing_tokens,
            'total_tokens': None if missing_tokens else known_tokens,
            'known_cost_usd': known_cost, 'cost_missing_calls': missing_cost,
            'total_cost_usd': None if missing_cost else known_cost,
            'by_case': {row['id']: {key: row.get(key) for key in
                        ('status', 'agent_status', 'planned_questions', 'accepted_questions',
                         'published_questions', 'questions', 'actual_calls')} for row in rows},
            'limitations': LIMITATIONS}


def make_settings(base, directory, entry, cap):
    extras = {key: value for key, value in base.text.extra.items() if key != 'reasoning_effort'}
    extras.update(max_tokens=32768, thinking={'type': 'enabled'}, reasoning_effort='high')
    return replace(base, data_dir=directory, text=replace(base.text, extra=extras),
        text_json_mode=True, generation_workflow='agent_v1', agent_runtime='deepseek_harness',
        agent_orchestration='supervisor_v2', agent_plan_batch_size=8,
        agent_question_spec=entry['question_spec'], agent_max_calls=min(cap, 16),
        agent_max_repairs=1, max_daily_calls=cap, harness_max_requests=4,
        harness_max_output_tokens=32768, harness_reasoning_effort='high',
        harness_response_format='json_object', harness_schema_repairs=1)


async def run(args):
    if type(args.call_cap) is not int or not 1 <= args.call_cap <= 32:
        raise ValueError('Call cap must be between 1 and 32.')
    if type(args.questions_per_case) is not int or args.questions_per_case not in (1, 2):
        raise ValueError('Questions per case must be 1 or 2.')
    cases, dataset_hashes = frozen_cases(args.cases)
    plan = [{'id': case_id, 'task_id': 'supervisor_v2__' + case_id,
             'runtime': 'deepseek_harness', 'question_count': args.questions_per_case,
             'question_spec': 'cpu_schedule_v1' if case_id == 'cpu_en' else 'none'} for case_id in cases]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (Path(args.output) if args.output else ROOT / 'docs/agent/flexible-experiments' / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'flexible-answer-experiment-v1', 'created_at': now(),
        'live': args.live, 'call_cap': args.call_cap, 'plan': plan,
        'orchestration': 'supervisor_v2', 'questions_per_case': args.questions_per_case,
        'agent_prompt_revision': PROMPT_REVISION, 'harness_quality_revision': HARNESS_QUALITY_REVISION,
        'flexible_planner_revision': FLEXIBLE_PLANNER_REVISION,
        'assessment_plan_schema_sha256': digest(AssessmentPlan.model_json_schema()),
        'requirement_check_schema_sha256': digest(RequirementCheck.model_json_schema()),
        'cpu_spec_revision': CPU_SPEC_REVISION, 'harness_adapter_revision': ADAPTER_REVISION,
        'harness_runtime_version': HARNESS_RUNTIME_VERSION,
        'dataset_sha256': dataset_hashes, 'frozen_cases_sha256': digest(cases),
        'reasoning_effort': 'high', 'response_format': 'json_object', 'schema_repairs': 1,
        'harness_max_requests': 4, 'harness_max_output_tokens': 32768,
        'agent_max_calls': min(args.call_cap, 16), 'agent_max_repairs': 1,
        'plan_batch_size': 8, 'limitations': LIMITATIONS, 'code_sha256': snapshot_code(output)}
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'frozen_cases.json', cases)
    write_json(output / 'results.json', [])
    write_json(output / 'summary.json', summarize([], plan))
    if not args.live:
        print(dumps({'dry_run': True, 'output': str(output), 'planned_tasks': len(plan),
                     'planned_questions': len(plan) * args.questions_per_case,
                     'max_live_calls': args.call_cap, 'actual_calls': 0}), flush=True)
        return output

    base = Settings.from_env()
    base.text.require('text')
    public = public_parameters(make_settings(base, output / 'runtime', plan[0], args.call_cap).text.extra)
    public['reasoning_effort'] = 'high'
    manifest['provider'] = {'model': base.text.model, 'endpoint_signature': base.text.signature,
                            'public_parameters': public}
    write_json(output / 'manifest.json', manifest)
    store = CappedStore(output / 'runtime', args.call_cap)
    seed_documents(store, cases)
    rows = []
    for entry in plan:
        filename = entry['task_id'] + '.json'
        row = entry | {'planned_questions': entry['question_count'], 'accepted_questions': 0,
                       'published_questions': 0, 'questions': [], 'calls': [], 'actual_calls': 0,
                       'evidence_file': filename}
        interrupted = None
        if store.one('SELECT count(*) AS n FROM calls')['n'] >= args.call_cap:
            row.update(status='not_run_budget_exhausted', job_id=None)
            write_json(output / filename, {'job': None, 'evidence': {'experiment': entry},
                                          'calls': [], 'published_content': None, 'status': row['status']})
        else:
            case = cases[entry['id']]
            settings = make_settings(base, output / 'runtime', entry, args.call_cap)
            request = make_request(case).model_copy(update={'course_id': COURSE_ID,
                'request_key': 'flexible-' + entry['task_id'], 'count': args.questions_per_case})
            providers = ApiProviders(settings, store)
            pipeline = Pipeline(settings, store, providers, enforce_account_ownership=False)

            async def retrieve(request, job_id, with_trace=True):
                return deepcopy(case['sources']), {'mode': 'frozen_fixture_context',
                    'case_id': case['id'], 'source_sha256': digest(case['sources']), 'api_calls': 0}

            pipeline.retrieve = retrieve
            job, _ = store.job(request.request_key, 'generate', request.model_dump())
            print(dumps({'starting': entry['task_id']}), flush=True)
            try:
                await pipeline.run(job['id'])
            except BaseException as exc:
                interrupted = exc
            finally:
                try:
                    await providers.close()
                except BaseException as exc:
                    interrupted = interrupted or exc
                saved_job = store.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
                saved_evidence = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
                evidence = json.loads(saved_evidence['evidence']) if saved_evidence else {}
                evidence['experiment'] = entry | {'source_provenance': deepcopy(case['provenance'])}
                calls = store.calls_for_job(job['id'])
                content = store.one('SELECT * FROM contents WHERE job_id=? ORDER BY version DESC,created_at DESC LIMIT 1', (job['id'],))
                if content:
                    content = {**content, 'asset': json.loads(content['asset']), 'sources': json.loads(content['sources']),
                               'config': json.loads(content['config'])}
                questions = question_records(evidence)
                row.update(job_id=job['id'], status=saved_job['status'],
                    agent_status=evidence.get('agent', {}).get('status'),
                    accepted_questions=sum(q['status'] == 'passed' for q in questions),
                    published_questions=len(content['asset'].get('questions', []))
                        if content and saved_job['status'] == 'succeeded' else 0,
                    questions=questions, calls=calls, actual_calls=len(calls))
                if interrupted:
                    row['interrupted_type'] = type(interrupted).__name__
                write_json(output / filename, {'job': saved_job, 'evidence': evidence,
                    'calls': calls, 'published_content': content})
        rows.append(row)
        write_json(output / 'results.json', rows)
        write_json(output / 'summary.json', summarize(rows, plan))
        print(dumps({'finished': entry['task_id'], 'status': row['status'],
                     'actual_calls': row['actual_calls'], 'published_questions': row['published_questions']}), flush=True)
        if interrupted:
            raise interrupted
    print(dumps({'output': str(output), 'actual_calls': summarize(rows, plan)['actual_calls']}), flush=True)
    return output


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--live', action='store_true', help='Explicitly enable paid model calls; default only freezes the plan.')
    result.add_argument('--cases', nargs='+', default=list(CASE_IDS), help='Space- or comma-separated humanities_zh,humanities_en,cpu_en.')
    result.add_argument('--questions-per-case', type=int, choices=(1, 2), default=1)
    result.add_argument('--call-cap', type=int, choices=range(1, 33), default=24)
    result.add_argument('--output', help='New output directory; existing paths are never overwritten.')
    return result


if __name__ == '__main__':
    asyncio.run(run(parser().parse_args()))
