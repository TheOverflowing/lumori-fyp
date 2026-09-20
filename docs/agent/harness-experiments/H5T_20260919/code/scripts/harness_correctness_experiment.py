"""Bounded native vs official Harness correctness smoke; dry by default.

Uses the current GenerationAgent prompts/gates and frozen course references.
Canary author responses are fixtures injected at the agent call boundary, so
solver/reviewer still exercise the selected runtime. No production flags are
changed. This small development comparison is not a human-labelled benchmark.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import fields, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.generation_agent import GenerationAgent, PROMPT_REVISION, HARNESS_QUALITY_REVISION, fingerprint
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import dumps, now
from scripts.agent_correctness_experiment import canary_asset
from scripts.difficulty_experiment import CappedStore, digest, public_parameters, write_json
from scripts.difficulty_prompts import make_request


COURSE_ID = 'difficulty-experiment'
CASE_DEFINITIONS = [
    {'id': 'canary_bad', 'case_id': 'cpu_scheduling_en_hard', 'mode': 'injected_bad'},
    {'id': 'canary_corrected', 'case_id': 'cpu_scheduling_en_hard', 'mode': 'injected_corrected'},
    {'id': 'cpu_en_hard', 'case_id': 'cpu_scheduling_en_hard', 'mode': 'live_author'},
    {'id': 'cpu_zh_hard', 'case_id': 'cpu_scheduling_zh_hard', 'mode': 'live_author'},
    {'id': 'transactions_zh_medium', 'case_id': 'transactions_zh_medium', 'mode': 'live_author'},
]
LIMITATIONS = [
    'Development smoke: one run per selected case/runtime, not statistical superiority evidence.',
    'Default mode uses current v3 role prompts. The optional CPU specification mode changes author prompts/schema and deterministically renders the question and answer; it is a combined strategy, not a same-prompt comparison. Runtimes also differ in wrappers, tools and stopping behavior, so effects cannot be attributed to the loop alone.',
    'Frozen reference snapshots bypass retrieval and do not measure RAG.',
    'Canary authors are injected AI-reviewed regression fixtures, not live author calls or human gold labels.',
    'Same model family can make correlated generation and review errors.',
    'Gate success is not independently established correctness or student difficulty.',
    'Failed, interrupted and rejected responses remain in the denominator and audit.',
    'Missing token/cost fields remain unknown; reported totals cover known usage only.',
    'Runtime order is interleaved by case but not randomized; provider drift and stochasticity remain.',
]


def select_cases(requested):
    tokens = [part.strip() for value in (requested or ['all']) for part in value.split(',') if part.strip()]
    aliases = {'canary_bad_Q016': 'canary_bad', 'canary_corrected_Q016': 'canary_corrected',
               'cpu_scheduling_en_hard': 'cpu_en_hard', 'cpu_scheduling_zh_hard': 'cpu_zh_hard'}
    selected = set()
    known = {entry['id'] for entry in CASE_DEFINITIONS}
    for token in tokens:
        if token in ('all', 'canary', 'live'):
            selected.update(e['id'] for e in CASE_DEFINITIONS if token == 'all' or
                            (e['mode'] == 'live_author') == (token == 'live'))
        else:
            token = aliases.get(token, token)
            if token not in known:
                raise ValueError('Unknown experimental case; use --help for supported selections.')
            selected.add(token)
    if not selected:
        raise ValueError('At least one experimental case is required.')
    return [deepcopy(entry) for entry in CASE_DEFINITIONS if entry['id'] in selected]


def build_plan(requested, runtime):
    runtimes = ['native', 'deepseek_harness'] if runtime == 'both' else [runtime]
    if any(item not in ('native', 'deepseek_harness') for item in runtimes):
        raise ValueError('Unsupported experimental runtime.')
    return [entry | {'runtime': current, 'task_id': current + '__' + entry['id']}
            for entry in select_cases(requested) for current in runtimes]


def frozen_cases(dataset, plan):
    by_id = {case['id']: case for case in dataset['cases']}
    result = {}
    for entry in plan:
        case = deepcopy(by_id[entry['case_id']])
        for source in case['sources']:
            # Each source is attached to an actual document row in the isolated
            # database. The model cannot supply or change the course/document id.
            name = source.get('document_name') or source['id']
            source['document_id'] = 'fixture-doc-' + digest([COURSE_ID, name])[:24]
        result[case['id']] = case
    return result


def seed_documents(store, cases):
    store.execute('INSERT INTO courses VALUES(?,?,?)', (COURSE_ID, 'Isolated Harness research fixtures', now()))
    for case in cases.values():
        for source in case['sources']:
            did = source['document_id']
            store.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?,?)',
                          (did, COURSE_ID, source.get('document_name') or source['id'],
                           digest(did), 'indexed', max(1, source.get('page') or 1), now()))


class FixtureGenerationAgent(GenerationAgent):
    def __init__(self, pipeline, request, job_id, fixture=None, fixture_origin=None):
        super().__init__(pipeline, request, job_id)
        self.fixture, self.fixture_origin = fixture, fixture_origin

    async def call(self, attempt, phase, contract, system):
        if self.fixture is None or phase != 'author':
            return await super().call(attempt, phase, contract, system)
        record = attempt.setdefault(phase, {'history': []})
        if 'response' not in record:
            self.check_scope()
            messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': dumps(contract)}]
            timestamp = now()
            record['history'].append({'status': 'fixture_injected', 'started_at': timestamp,
                'ended_at': timestamp, 'resume_count': self.state['resume_count'],
                'messages': messages, 'prompt_sha256': fingerprint(messages),
                'fixture_origin': self.fixture_origin, 'api_call_performed': False})
            record['response'] = deepcopy(self.fixture)
            record['fixture_origin'] = self.fixture_origin
            self.state['phase'] = phase
            self.save()  # No call reservation or agent call-count increment.
        return record['response']


class ExperimentPipeline(Pipeline):
    def __init__(self, settings, store, providers, *, fixture=None, fixture_origin=None):
        super().__init__(settings, store, providers, enforce_account_ownership=False)
        self.fixture, self.fixture_origin = fixture, fixture_origin

    async def generate(self, request, job_id):
        return await FixtureGenerationAgent(self, request, job_id, self.fixture, self.fixture_origin).run()


def summarize(rows, plan):
    result = {'planned_tasks': len(plan), 'recorded_tasks': len(rows), 'by_runtime': {}, 'limitations': LIMITATIONS}
    for runtime in dict.fromkeys(entry['runtime'] for entry in plan):
        selected = [row for row in rows if row['runtime'] == runtime]
        calls = [call for row in selected for call in row.get('calls', [])]
        status_counts = {}
        for row in selected:
            status_counts[row['status']] = status_counts.get(row['status'], 0) + 1
        result['by_runtime'][runtime] = {
            'planned_tasks': sum(entry['runtime'] == runtime for entry in plan),
            'recorded_tasks': len(selected), 'status_counts': status_counts,
            'actual_calls': len(calls), 'provider_succeeded': sum(c['status'] == 'succeeded' for c in calls),
            'known_total_tokens': sum(c['usage'].get('total_tokens', 0) for c in calls),
            'tokens_missing_calls': sum('total_tokens' not in c['usage'] for c in calls),
            'known_cost_usd': sum(c['usage'].get('cost', 0) for c in calls),
            'cost_missing_calls': sum('cost' not in c['usage'] for c in calls),
            'gate_outcomes': {row['id']: row['status'] for row in selected},
            'agent_outcomes': {row['id']: row.get('agent_status') for row in selected},
        }
    result['actual_calls'] = sum(item['actual_calls'] for item in result['by_runtime'].values())
    return result


def snapshot_code(output):
    files = ['app/generation_agent.py', 'app/answer_tools.py', 'app/cpu_problem_spec.py', 'app/config.py', 'app/store.py',
             'app/providers.py', 'app/pipeline.py', 'app/models.py', 'app/difficulty.py',
             'scripts/harness_correctness_experiment.py', 'scripts/agent_correctness_experiment.py',
             'scripts/difficulty_experiment.py', 'scripts/difficulty_prompts.py']
    files += [str(path.relative_to(ROOT)) for path in sorted((ROOT / 'app').glob('harness*.py'))]
    index = {}
    for relative in files:
        source, target = ROOT / relative, output / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        index[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    return index


def replay_spec_fixtures(directory, cases, plan):
    """Freeze previously compiled author proposals, retaining original sources.

    This re-tests solve/review on identical questions; it is not fresh author
    generation. No credential loading, network requests or production DB access.
    """
    from app.cpu_problem_spec import compile_cpu_spec
    from app.generation_agent import CpuSpecProposal
    result = {}
    for entry in plan:
        source = Path(directory).resolve() / (entry['task_id'] + '.json')
        record = json.loads(source.read_text())
        evidence = record['evidence']
        case = cases[entry['case_id']]
        if digest(evidence['sources']) != digest(case['sources']):
            raise ValueError('Replay references differ from the frozen experiment references.')
        slots = evidence['agent']['slots']
        if len(slots) != 1:
            raise ValueError('Specification replay requires a single-question record.')
        attempts = [a for a in slots[0]['attempts'] if a.get('compiled_spec')]
        if not attempts:
            raise ValueError('Replay record has no compiled CPU specification.')
        attempt = attempts[-1]
        proposal = CpuSpecProposal.model_validate(attempt['author']['response'])
        if not proposal.evidence_sufficient or not proposal.citation_ids or not set(proposal.citation_ids) <= {s['id'] for s in case['sources']}:
            raise ValueError('Replay proposal has no valid supported references.')
        compiled = compile_cpu_spec(proposal.spec, language=case['language'],
            difficulty=case['target_difficulty'], source_ids=proposal.citation_ids)
        if compiled['evidence']['spec_sha256'] != attempt['compiled_spec']['spec_sha256']:
            raise ValueError('Replay specification or compiler changed; do not mix experiment versions.')
        asset = {'title': case['topic'], 'evidence_sufficient': True,
            'learning_objectives': compiled.get('learning_objectives', []),
            'sections': [compiled['section']], 'questions': [compiled['question']], 'visual_prompt': ''}
        if fingerprint(asset) != attempt.get('compiled_asset_sha256'):
            raise ValueError('Replay rendering or calculation changed; the frozen question is not identical.')
        result[entry['task_id']] = {'response': proposal.model_dump(),
            'origin': {'kind': 'injected_frozen_cpu_spec', 'api_call_performed': False,
                'source_file': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'spec_sha256': compiled['evidence']['spec_sha256'],
                'compiled_asset_sha256': fingerprint(asset),
                'compiled_question_sha256': digest(compiled['question'])}}
    return result


async def run(args):
    plan = build_plan(args.cases, args.runtime)
    thinking = getattr(args, 'thinking', 'off')
    response_format = getattr(args, 'response_format', 'text')
    question_spec = getattr(args, 'question_spec', 'none')
    if question_spec != 'none' and (args.runtime != 'deepseek_harness' or any(
            entry['id'] not in ('cpu_en_hard', 'cpu_zh_hard') for entry in plan)):
        raise ValueError('The CPU specification experiment requires Harness and live-author CPU cases only.')
    dataset = json.loads((ROOT / 'benchmarks/difficulty/cases.json').read_text())
    cases = frozen_cases(dataset, plan)
    replay_dir = getattr(args, 'replay_specs', None)
    if replay_dir and question_spec != 'cpu_schedule_v1':
        raise ValueError('Specification replay requires --question-spec cpu_schedule_v1.')
    spec_fixtures = replay_spec_fixtures(replay_dir, cases, plan) if replay_dir else {}
    if spec_fixtures:
        for entry in plan:
            entry['mode'] = 'injected_spec'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (Path(args.output) if args.output else ROOT / 'docs/agent/harness-experiments' / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'harness-correctness-experiment-v1', 'created_at': now(),
        'live': args.live, 'call_cap': args.call_cap, 'plan': plan,
        'agent_prompt_revision': PROMPT_REVISION, 'dataset_sha256': digest(dataset),
        'harness_quality_revision': HARNESS_QUALITY_REVISION,
        'question_spec': question_spec,
        'frozen_cases_sha256': digest(cases), 'harness_max_requests': args.harness_max_requests,
        'harness_max_output_tokens': args.max_output_tokens, 'native_max_tokens': args.max_output_tokens,
        'shared_thinking': {'type': 'enabled' if thinking == 'high' else 'disabled'},
        'reasoning_effort': thinking, 'response_format': response_format,
        'author_mode': 'frozen_spec_replay' if spec_fixtures else 'original_plan',
        'spec_replay_sha256': digest(spec_fixtures) if spec_fixtures else None,
        'agent_max_calls': min(args.call_cap, 36), 'agent_max_repairs_live_author': 1,
        'agent_max_repairs_injected_author': 0, 'limitations': LIMITATIONS,
        'code_sha256': snapshot_code(output)}
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'frozen_cases.json', cases)
    if spec_fixtures:
        write_json(output / 'replay_inputs.json', spec_fixtures)
    write_json(output / 'summary.json', summarize([], plan))
    if not args.live:
        print(dumps({'dry_run': True, 'output': str(output), 'planned_tasks': len(plan),
                     'max_live_calls': args.call_cap, 'actual_calls': 0}), flush=True)
        return output

    required_settings = {'agent_runtime', 'harness_max_requests', 'harness_max_output_tokens'}
    if not required_settings <= {field.name for field in fields(Settings)}:
        raise RuntimeError('Harness Settings integration is not ready; no API call was made.')
    base = Settings.from_env()
    base.text.require('text')
    extras = {key: value for key, value in base.text.extra.items() if key != 'reasoning_effort'}
    extras.update(max_tokens=args.max_output_tokens,
                  thinking={'type': 'enabled' if thinking == 'high' else 'disabled'})
    if thinking == 'high':
        extras['reasoning_effort'] = 'high'
    base = replace(base, text=replace(base.text, extra=extras),
                   text_json_mode=response_format == 'json_object',
                   harness_reasoning_effort=thinking, harness_response_format=response_format)
    manifest['provider'] = {'model': base.text.model, 'endpoint_signature': base.text.signature,
                            'public_parameters': public_parameters(base.text.extra)}
    if thinking == 'high':
        manifest['provider']['public_parameters']['reasoning_effort'] = 'high'
    write_json(output / 'manifest.json', manifest)
    store = CappedStore(output / 'runtime', args.call_cap)
    seed_documents(store, cases)
    rows = []
    for entry in plan:
        filename = entry['task_id'] + '.json'
        if store.one('SELECT count(*) AS n FROM calls')['n'] >= args.call_cap:
            row = entry | {'status': 'not_run_budget_exhausted', 'job_id': None, 'calls': [],
                           'actual_calls': 0, 'evidence_file': filename}
            write_json(output / filename, {'job': None, 'evidence': {'experiment': entry}, 'calls': [],
                                          'status': row['status']})
        else:
            case = cases[entry['case_id']]
            injected = entry['mode'] != 'live_author'
            settings = replace(base, data_dir=output / 'runtime', generation_workflow='agent_v1',
                agent_runtime=entry['runtime'], harness_max_requests=args.harness_max_requests,
                agent_question_spec=question_spec,
                harness_max_output_tokens=args.max_output_tokens, agent_max_calls=min(args.call_cap, 36),
                agent_max_repairs=0 if injected else 1, max_daily_calls=args.call_cap)
            request = make_request(case).model_copy(update={'request_key': 'harness-' + entry['task_id']})
            fixture = (spec_fixtures[entry['task_id']]['response'] if entry['mode'] == 'injected_spec' else
                       canary_asset(case, entry['mode'] == 'injected_corrected') if injected else None)
            fixture_origin = {'kind': 'injected_regression_fixture', 'blind_id': 'Q016',
                'variant': entry['mode'], 'api_call_performed': False,
                'source_file': 'docs/difficulty/codex-review/20260919/packets.json',
                'asset_sha256': digest(fixture)} if injected else None
            if entry['mode'] == 'injected_spec':
                fixture_origin = spec_fixtures[entry['task_id']]['origin']
            providers = ApiProviders(settings, store)
            pipeline = ExperimentPipeline(settings, store, providers, fixture=fixture, fixture_origin=fixture_origin)

            async def retrieve(request, job_id, with_trace=True):
                return deepcopy(case['sources']), {'mode': 'frozen_fixture_context', 'case_id': case['id'],
                    'source_sha256': digest(case['sources']), 'api_calls': 0}

            pipeline.retrieve = retrieve
            job, _ = store.job(request.request_key, 'generate', request.model_dump())
            print(dumps({'starting': entry['task_id']}), flush=True)
            interrupted = None
            try:
                await pipeline.run(job['id'])
            except BaseException as exc:
                # Preserve partial records even on cancellation. Never copy an
                # arbitrary exception message, request headers or secret config.
                interrupted = exc
            finally:
                try:
                    await providers.close()
                except BaseException as exc:
                    if interrupted is None:
                        interrupted = exc
                saved_job = store.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
                evidence_row = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
                evidence = json.loads(evidence_row['evidence']) if evidence_row else {}
                evidence['experiment'] = entry | {'author_injected': injected, 'fixture_origin': fixture_origin}
                calls = store.calls_for_job(job['id'])
                row = entry | {'job_id': job['id'], 'status': saved_job['status'],
                    'agent_status': evidence.get('agent', {}).get('status'), 'error': saved_job['error'],
                    'calls': calls, 'actual_calls': len(calls), 'evidence_file': filename}
                if interrupted is not None:
                    row['interrupted_type'] = type(interrupted).__name__
                write_json(output / filename, {'job': saved_job, 'evidence': evidence, 'calls': calls})
            rows.append(row)
            write_json(output / 'results.json', rows)
            write_json(output / 'summary.json', summarize(rows, plan))
            print(dumps({'finished': entry['task_id'], 'status': row['status'], 'actual_calls': len(calls)}), flush=True)
            if interrupted is not None:
                raise interrupted
            continue
        rows.append(row)
        write_json(output / 'results.json', rows)
        write_json(output / 'summary.json', summarize(rows, plan))
    print(dumps({'output': str(output), 'actual_calls': summarize(rows, plan)['actual_calls']}), flush=True)
    return output


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--live', action='store_true', help='Opt in to real model calls; default only writes the plan/snapshot.')
    result.add_argument('--runtime', choices=['both', 'native', 'deepseek_harness'], default='both')
    result.add_argument('--question-spec', choices=['none', 'cpu_schedule_v1'], default='none',
        help='Explicit CPU structured-author experiment; only Harness live CPU cases are supported.')
    result.add_argument('--cases', nargs='+', default=['all'],
        help='Names or comma-separated names: canary_bad, canary_corrected, cpu_en_hard, cpu_zh_hard, transactions_zh_medium. Groups: all, canary, live.')
    result.add_argument('--call-cap', type=int, default=64, choices=range(1, 65))
    result.add_argument('--harness-max-requests', type=int, default=6, choices=range(1, 7))
    result.add_argument('--max-output-tokens', type=int, default=4096, choices=range(256, 8193))
    result.add_argument('--thinking', choices=['off', 'high'], default='off')
    result.add_argument('--response-format', choices=['text', 'json_object'], default='text')
    result.add_argument('--replay-specs', help='Replay compiled author specifications from an archived CPU experiment; no new author API calls.')
    result.add_argument('--output')
    return result


if __name__ == '__main__':
    asyncio.run(run(parser().parse_args()))
