"""Small paired native/Harness comparison of the current supervisor_v2 path.

Dry by default. Live runs use frozen fictional sources, a separate database,
the same model parameters and a hard provider-call cap. This measures the
whole runtime strategy, not an isolated Harness tool-loop effect.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import dumps
from scripts.difficulty_experiment import CappedStore, digest, public_parameters, write_json
from scripts.difficulty_prompts import make_request
from scripts.flexible_answer_experiment import (COURSE_ID, frozen_cases, numeric_usage,
    question_records, seed_documents)


LIMITATIONS = [
    'Frozen AI-authored fictional passages bypass retrieval and have no teacher or student labels.',
    'One sample per case and runtime cannot establish a quality or cost advantage.',
    'The runtime changes its prompt wrapper and tool protocol as well as its model loop.',
    'Model gate acceptance is separate from independent factual, logical and difficulty review.',
    'Unknown provider costs remain unknown; a zero known-cost sum is not a zero price.',
]


def plan_for(cases, selected_runtime='both'):
    # Alternate the first runtime across cases to limit simple order bias.
    return [{'case_id': case_id, 'runtime': runtime, 'task_id': case_id + '__' + runtime}
            for case_id in cases
            for runtime in (('native', 'deepseek_harness') if case_id == 'humanities_zh'
                            else ('deepseek_harness', 'native'))
            if runtime == selected_runtime or selected_runtime == 'both']


def output_token_budget(args):
    if args.max_output_tokens is not None:
        return args.max_output_tokens
    return 16384 if getattr(args, 'thinking', 'off') == 'high' else 8192


def settings_for(base, directory, runtime, args):
    extra = {key: value for key, value in base.text.extra.items() if key != 'reasoning_effort'}
    thinking = getattr(args, 'thinking', 'off')
    token_budget = output_token_budget(args)
    extra.update(max_tokens=token_budget,
                 thinking={'type': 'enabled' if thinking == 'high' else 'disabled'})
    if thinking == 'high':
        extra['reasoning_effort'] = 'high'
    return replace(base, data_dir=directory, text=replace(base.text, extra=extra),
        text_json_mode=True, generation_workflow='agent_v1', agent_runtime=runtime,
        agent_orchestration='supervisor_v2', agent_question_spec='none',
        agent_max_calls=args.per_task_cap, agent_max_repairs=1, max_daily_calls=args.call_cap,
        harness_max_requests=4, harness_max_output_tokens=token_budget,
        harness_reasoning_effort=thinking, harness_response_format='json_object',
        harness_schema_repairs=1)


def summary(rows, plan):
    result = {'planned_tasks': len(plan), 'recorded_tasks': len(rows), 'by_runtime': {},
              'limitations': LIMITATIONS}
    for runtime in ('native', 'deepseek_harness'):
        selected = [row for row in rows if row['runtime'] == runtime]
        calls = [call for row in selected for call in row.get('calls', [])]
        missing_cost = sum(numeric_usage(call, 'cost') is None for call in calls)
        missing_tokens = sum(numeric_usage(call, 'total_tokens') is None for call in calls)
        result['by_runtime'][runtime] = {
            'planned_tasks': sum(item['runtime'] == runtime for item in plan),
            'recorded_tasks': len(selected),
            'saved_drafts': sum(row.get('published_questions', 0) for row in selected),
            'strict_target_questions': sum(row.get('strict_target_questions', 0) for row in selected),
            'adjusted_difficulty_questions': sum(row.get('adjusted_difficulty_questions', 0) for row in selected),
            'accepted_questions': sum(row.get('accepted_questions', 0) for row in selected),
            'actual_calls': len(calls), 'known_total_tokens': sum(
                numeric_usage(call, 'total_tokens') or 0 for call in calls),
            'tokens_missing_calls': missing_tokens,
            'known_cost_usd': sum(numeric_usage(call, 'cost') or 0 for call in calls),
            'cost_missing_calls': missing_cost,
            'wall_seconds': sum(row.get('wall_seconds', 0) for row in selected),
            'status_by_case': {row['case_id']: row['status'] for row in selected},
        }
    result['actual_calls'] = sum(value['actual_calls'] for value in result['by_runtime'].values())
    return result


async def run(args):
    args.max_output_tokens = output_token_budget(args)
    if not 1 <= args.call_cap <= 32 or not 4 <= args.per_task_cap <= 12:
        raise ValueError('Call cap must be 1..32 and per-task cap 4..12.')
    if not 256 <= args.max_output_tokens <= 32768:
        raise ValueError('Output-token cap must be 256..32768.')
    if not args.cases or any(case not in ('humanities_zh', 'humanities_en') for case in args.cases):
        raise ValueError('This paired comparison supports humanities_zh and humanities_en only.')
    cases, dataset_hashes = frozen_cases(args.cases)
    if args.english_difficulty != 'hard' and 'humanities_en' in cases:
        cases['humanities_en']['target_difficulty'] = args.english_difficulty
    plan = plan_for(cases, args.runtime)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (Path(args.output) if args.output else
              ROOT / 'docs/agent/runtime-comparison' / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    code_hashes = {}
    for source in sorted((ROOT / 'app').rglob('*.py')) + [ROOT / 'scripts/runtime_paired_comparison.py',
            ROOT / 'scripts/flexible_answer_experiment.py', ROOT / 'scripts/difficulty_prompts.py',
            ROOT / 'scripts/difficulty_experiment.py']:
        relative = source.relative_to(ROOT)
        target = output / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        code_hashes[str(relative)] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {'schema': 'runtime-paired-comparison-v1', 'created_at': stamp,
        'live': args.live, 'plan': plan, 'call_cap': args.call_cap,
        'per_task_cap': args.per_task_cap, 'max_output_tokens': args.max_output_tokens,
        'english_difficulty': args.english_difficulty,
        'reasoning': args.thinking, 'response_format': 'json_object', 'orchestration': 'supervisor_v2',
        'question_count': 1, 'use_subagents': True, 'dataset_sha256': dataset_hashes,
        'frozen_cases_sha256': digest(cases), 'code_sha256': code_hashes,
        'limitations': LIMITATIONS}
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'frozen_cases.json', cases)
    write_json(output / 'results.json', [])
    write_json(output / 'summary.json', summary([], plan))
    if not args.live:
        print(dumps({'dry_run': True, 'output': str(output), 'plan': plan,
                     'max_live_calls': args.call_cap}), flush=True)
        return output

    base = Settings.from_env()
    base.text.require('text')
    example = settings_for(base, output / 'runtime', 'native', args)
    manifest['provider'] = {'model': example.text.model,
        'endpoint_signature': example.text.signature,
        'public_parameters': public_parameters(example.text.extra)}
    write_json(output / 'manifest.json', manifest)
    store = CappedStore(output / 'runtime', args.call_cap)
    seed_documents(store, cases)
    rows = []
    for entry in plan:
        filename = entry['task_id'] + '.json'
        row = entry | {'status': 'not_run_budget_exhausted', 'calls': [],
                       'accepted_questions': 0, 'published_questions': 0,
                       'strict_target_questions': 0, 'adjusted_difficulty_questions': 0,
                       'questions': [], 'wall_seconds': 0}
        if store.one('SELECT count(*) AS n FROM calls')['n'] < args.call_cap:
            case = cases[entry['case_id']]
            settings = settings_for(base, output / 'runtime', entry['runtime'], args)
            request = make_request(case).model_copy(update={'course_id': COURSE_ID,
                'request_key': 'runtime-pair-' + entry['task_id'], 'count': 1,
                'use_subagents': True})
            providers = ApiProviders(settings, store)
            pipeline = Pipeline(settings, store, providers, enforce_account_ownership=False)

            async def retrieve(request, job_id, with_trace=True):
                return deepcopy(case['sources']), {'mode': 'frozen_fixture_context',
                    'case_id': case['id'], 'source_sha256': digest(case['sources']), 'api_calls': 0}

            pipeline.retrieve = retrieve
            job, _ = store.job(request.request_key, 'generate', request.model_dump())
            print(dumps({'starting': entry['task_id']}), flush=True)
            start = time.perf_counter()
            interrupted = None
            try:
                await pipeline.run(job['id'])
            except Exception as exc:
                interrupted = type(exc).__name__
            finally:
                await providers.close()
            row['wall_seconds'] = round(time.perf_counter() - start, 3)
            saved_job = store.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
            evidence_row = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
            evidence = json.loads(evidence_row['evidence']) if evidence_row else {}
            calls = store.calls_for_job(job['id'])
            content = store.one('SELECT * FROM contents WHERE job_id=? ORDER BY version DESC LIMIT 1', (job['id'],))
            if content:
                content = {**content, 'asset': json.loads(content['asset']),
                           'sources': json.loads(content['sources'])}
            questions = question_records(evidence)
            acceptance = evidence.get('difficulty_acceptance', {})
            delivered = bool(content and saved_job['status'] == 'succeeded')
            row.update(status=saved_job['status'], agent_status=evidence.get('agent', {}).get('status'),
                error=saved_job['error'], interrupted_type=interrupted, job_id=job['id'],
                calls=calls, questions=questions,
                difficulty_acceptance=acceptance,
                strict_target_questions=sum(item.get('strict_passed') is True for item in acceptance.get('items', []))
                    if delivered else 0,
                adjusted_difficulty_questions=sum(item.get('strict_passed') is False for item in acceptance.get('items', []))
                    if delivered else 0,
                accepted_questions=sum(q['status'] == 'passed' for q in questions),
                published_questions=len(content['asset'].get('questions', []))
                    if content and saved_job['status'] == 'succeeded' else 0)
            write_json(output / filename, {'job': saved_job, 'evidence': evidence,
                'calls': calls, 'published_content': content})
            print(dumps({'finished': entry['task_id'], 'status': row['status'],
                         'actual_calls': len(calls), 'saved_drafts': row['published_questions']}), flush=True)
        else:
            write_json(output / filename, {'job': None, 'evidence': {'experiment': entry},
                'calls': [], 'published_content': None})
        rows.append(row)
        write_json(output / 'results.json', rows)
        write_json(output / 'summary.json', summary(rows, plan))
    print(dumps({'output': str(output), 'actual_calls': summary(rows, plan)['actual_calls']}), flush=True)
    return output


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--live', action='store_true', help='Use real provider calls; omitted by default.')
    result.add_argument('--runtime', choices=('both', 'native', 'deepseek_harness'), default='both')
    result.add_argument('--cases', nargs='+', default=['humanities_zh', 'humanities_en'],
                        help='Frozen humanities_zh and/or humanities_en cases.')
    result.add_argument('--call-cap', type=int, default=24)
    result.add_argument('--per-task-cap', type=int, default=8)
    result.add_argument('--max-output-tokens', type=int,
                        help='Per-call combined output cap; defaults to 8192 for off and 16384 for high.')
    result.add_argument('--thinking', choices=('off', 'high'), default='off')
    result.add_argument('--english-difficulty', choices=('hard', 'medium'), default='hard',
                        help='Explicit experimental target; medium is a separate condition, not a hard success.')
    result.add_argument('--output', help='New output directory; existing paths are never overwritten.')
    return result


if __name__ == '__main__':
    asyncio.run(run(parser().parse_args()))
