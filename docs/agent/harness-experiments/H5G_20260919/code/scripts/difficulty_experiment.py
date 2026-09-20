"""Frozen-context prompt comparisons. Dry run by default; --live is explicit.

This is an offline research harness, not a production-policy change. A different
model grades anonymized questions. Neither model provides human difficulty labels.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Endpoint, Settings
from app.models import LearningAsset
from app.pipeline import validate_asset
from app.providers import ApiProviders, ProviderError
from app.store import Store
from scripts.difficulty_prompts import (STRATEGIES, DifficultyJudgeResult,
    build_generation_messages, build_judge_messages, make_request, PROMPT_VERSION, JUDGE_VERSION)

PROTOCOL_VERSION = 'difficulty-prompt-screening-v1'
DEFAULT_DATASET = ROOT / 'benchmarks/difficulty/cases.json'
DEFAULT_JUDGE = 'qwen/qwen3-235b-a22b-2507'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def select_cases(dataset, selection):
    cases = dataset['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case IDs')
    topics = {}
    for case in cases:
        topics.setdefault(case['topic_id'], set()).add(case['split'])
        make_request(case)
        if not case['sources'] or any(not s['text'].strip() for s in case['sources']):
            raise ValueError('Every case needs a frozen source context')
        if len({s['id'] for s in case['sources']}) != len(case['sources']):
            raise ValueError('Duplicate citation IDs')
    if any(len(splits) != 1 for splits in topics.values()):
        raise ValueError('Topic leakage across splits')
    selected = [c for c in cases if (c['split'] == 'dev' and c.get('pilot'))] if selection == 'pilot' else [c for c in cases if c['split'] == selection]
    if not selected:
        raise ValueError('No cases selected')
    return selected


def summarize(records):
    """All scheduled question slots stay in the denominator, including failures."""
    result = {}
    for strategy in sorted({r['strategy'] for r in records}):
        rows = [r for r in records if r['strategy'] == strategy]
        judged = [r for r in rows if r.get('judge')]
        qualified = [r for r in rows if r.get('qualified')]
        levels = {}
        for level in ('easy', 'medium', 'hard'):
            group = [r for r in rows if r['target_difficulty'] == level]
            n = len(group)
            levels[level] = {'requested': n, 'matched': sum(bool(r.get('difficulty_match')) for r in group),
                'qualified': sum(bool(r.get('qualified')) for r in group),
                'qualified_rate': sum(bool(r.get('qualified')) for r in group) / n if n else None}
        matrix = {level: {pred: 0 for pred in ('easy', 'medium', 'hard', 'uncertain', 'ungraded')} for level in levels}
        for r in rows:
            matrix[r['target_difficulty']][r.get('judge', {}).get('assessed_difficulty', 'ungraded')] += 1
        result[strategy] = {'requested': len(rows), 'structurally_valid': sum(r.get('generation_status') == 'valid' for r in rows),
            'judged': len(judged), 'difficulty_matched': sum(bool(r.get('difficulty_match')) for r in rows),
            'qualified': len(qualified), 'difficulty_match_rate': sum(bool(r.get('difficulty_match')) for r in rows) / len(rows),
            'qualified_rate': len(qualified) / len(rows),
            'judge_uncertain_or_low_confidence': sum(r['judge']['assessed_difficulty'] == 'uncertain' or r['judge']['confidence'] == 'low' for r in judged),
            'ungraded': len(rows) - len(judged), 'by_difficulty': levels, 'confusion_matrix': matrix,
            'by_language': {lang: {'requested': sum(r['language'] == lang for r in rows),
                'qualified': sum(r['language'] == lang and bool(r.get('qualified')) for r in rows)} for lang in ('zh', 'en')}}
    return result


def score(record, judge):
    record['judge'] = judge
    record['difficulty_match'] = judge['assessed_difficulty'] == record['target_difficulty']
    record['qualified'] = bool(record['difficulty_match'] and judge['confidence'] != 'low' and
        all(judge[key] for key in ('correctness', 'grounded', 'answerable', 'ambiguity_free')))


def paired_comparisons(records):
    baseline = {(r['case_id'], r['repeat']): r for r in records if r['strategy'] == 'baseline'}
    comparisons = {}
    for strategy in sorted({r['strategy'] for r in records} - {'baseline'}):
        pairs = [(baseline[(r['case_id'], r['repeat'])], r) for r in records
                 if r['strategy'] == strategy and (r['case_id'], r['repeat']) in baseline]
        differences = [int(bool(b.get('qualified'))) - int(bool(a.get('qualified'))) for a, b in pairs]
        comparisons[strategy] = {'paired_slots': len(pairs), 'wins': differences.count(1), 'losses': differences.count(-1),
            'ties': differences.count(0), 'qualified_rate_difference': statistics.mean(differences) if differences else None,
            'interpretation': 'Descriptive paired development comparison; no statistical superiority established.'}
    return comparisons


class CappedStore(Store):
    """Per-run cap also applies across a UTC midnight, on top of provider cap."""
    def __init__(self, directory, cap):
        super().__init__(directory)
        self.cap = cap

    def reserve_call(self, job_id, capability, model, limit):
        if self.one('SELECT count(*) AS n FROM calls')['n'] >= self.cap:
            raise ValueError('Experiment call cap reached')
        return super().reserve_call(job_id, capability, model, min(limit, self.cap))


def safe_error(exc):
    # Do not copy arbitrary exceptions, upstream bodies, headers or credentials.
    result = {'type': type(exc).__name__}
    if getattr(exc, 'rule', None):
        result['rule'] = exc.rule
    return result


def call_rows(store):
    rows = store.all('SELECT * FROM calls ORDER BY created_at,id')
    for row in rows:
        row['usage'] = json.loads(row['usage'])
    return rows


def public_parameters(extra):
    result = {}
    for key in ('temperature', 'max_tokens', 'top_p', 'seed'):
        value = extra.get(key)
        if type(value) in (int, float) and math.isfinite(value):
            result[key] = value
    thinking = extra.get('thinking')
    if isinstance(thinking, dict) and thinking.get('type') in ('enabled', 'disabled'):
        result['thinking'] = {'type': thinking['type']}
    return result


def make_settings(settings, judge_model):
    if settings.embedding.base_url.rstrip('/') != 'https://openrouter.ai/api/v1':
        raise ValueError('This runner only reuses an existing OpenRouter credential at its configured host')
    settings.text.require('text')
    settings.embedding.require('embedding')
    generator = replace(settings, text=replace(settings.text, extra={**settings.text.extra, 'temperature': 0.6, 'max_tokens': 4096}), text_json_mode=True)
    judge = replace(settings, text=Endpoint(base_url=settings.embedding.base_url, api_key=settings.embedding.api_key,
        path='/chat/completions', model=judge_model, extra={'temperature': 0, 'max_tokens': 2048}), text_json_mode=True)
    if generator.text.model == judge.text.model:
        raise ValueError('The external judge must use a different model')
    return generator, judge


async def live_run(args, dataset, cases, strategies, run):
    settings = Settings.from_env()
    generator_settings, judge_settings = make_settings(settings, args.judge_model)
    cap = min(args.max_calls, settings.max_daily_calls)
    planned = len(cases) * len(strategies) * args.repeats
    if 2 * planned > cap:
        raise ValueError(f'Planned worst-case calls {2 * planned} exceed cap {cap}')
    store = CappedStore(run / 'runtime', cap)
    generator = ApiProviders(generator_settings, store)
    judge = ApiProviders(judge_settings, store)
    records = []
    for strategy in strategies:
        for case in cases:
            for repeat in range(args.repeats):
                records.append({'id': digest([args.seed, strategy, case['id'], repeat])[:20],
                    'strategy': strategy, 'case_id': case['id'], 'topic_id': case['topic_id'], 'language': case['language'],
                    'target_difficulty': case['target_difficulty'], 'repeat': repeat, 'generation_status': 'pending', 'judge_status': 'pending'})
    rng = random.Random(args.seed)
    rng.shuffle(records)
    manifest = {'protocol_version': PROTOCOL_VERSION, 'prompt_version': PROMPT_VERSION, 'judge_version': JUDGE_VERSION, 'started_at': datetime.now(timezone.utc).isoformat(),
        'selection': args.selection, 'dataset_sha256': digest(dataset), 'selected_cases_sha256': digest(cases),
        'generation_model': generator_settings.text.model, 'judge_model': judge_settings.text.model,
        'generation_endpoint_signature': generator_settings.text.signature, 'judge_endpoint_signature': judge_settings.text.signature,
        'generation_parameters': public_parameters(generator_settings.text.extra), 'judge_parameters': public_parameters(judge_settings.text.extra),
        'strategies': {key: STRATEGIES[key] for key in strategies}, 'planned_slots': planned, 'max_calls': cap,
        'concurrency': args.concurrency, 'repeats': args.repeats, 'seed': args.seed,
        'retrieval': 'Frozen context; no retrieval or indexing calls', 'generation_retries': 0, 'judge_retries': 0,
        'human_labels': False, 'student_calibrated': False, 'production_policy_changed': False,
        'limitations': ['Small development screening; no held-out superiority claim.',
            'Independent-model AI judge is not a teacher or empirical student difficulty.',
            'All requested slots, including failures, remain in the denominator.',
            'A single-call backward-design instruction is not a two-stage PFQS reproduction.',
            'No automatic prompt search or agent repair is run in this first screening.'], 'status': 'running'}
    write_json(run / 'manifest.json', manifest)
    write_json(run / 'selected-cases.json', cases)
    write_json(run / 'schedule.json', records)
    write_json(run / 'records.json', records)
    by_id = {case['id']: case for case in cases}
    semaphore = asyncio.Semaphore(args.concurrency)
    stop = asyncio.Event()

    def checkpoint():
        write_json(run / 'records.json', records)
        write_json(run / 'calls.json', call_rows(store))

    def check_provider_failure(job_id):
        calls = store.all('SELECT http_status FROM calls WHERE job_id=?', (job_id,))
        if any(row['http_status'] in (401, 402, 403, 404, 429) for row in calls):
            stop.set()

    async def generate_one(record):
        async with semaphore:
            if stop.is_set():
                record['generation_status'] = 'not_attempted_provider_stop'; checkpoint(); return
            case = by_id[record['case_id']]
            messages = build_generation_messages(case, record['strategy'])
            folder = run / 'items' / record['id']
            write_json(folder / 'generation-prompt.json', messages)
            record['generation_prompt_sha256'] = digest(messages)
            job_id = 'generation:' + record['id']
            try:
                raw = await generator.generate(messages, job_id)
                write_json(folder / 'generation-response.json', raw)
                asset = LearningAsset.model_validate(raw)
                validate_asset(asset, make_request(case), case['sources'], enforce_difficulty=True)
                if not asset.evidence_sufficient:
                    record['generation_status'] = 'insufficient_evidence'
                else:
                    record['generation_status'] = 'valid'
                    write_json(folder / 'asset.json', asset.model_dump())
            except Exception as exc:
                record['generation_status'] = 'failed'
                record['generation_error'] = safe_error(exc)
                check_provider_failure(job_id)
            checkpoint()
            print(f"generated {record['id']} {record['generation_status']}", flush=True)

    async def judge_one(record):
        if record['generation_status'] != 'valid':
            record['judge_status'] = 'not_applicable'; return
        async with semaphore:
            if stop.is_set():
                record['judge_status'] = 'not_attempted_provider_stop'; checkpoint(); return
            case = by_id[record['case_id']]
            folder = run / 'items' / record['id']
            asset = json.loads((folder / 'asset.json').read_text())
            messages = build_judge_messages(case, asset)
            write_json(folder / 'judge-prompt.json', messages)
            record['judge_prompt_sha256'] = digest(messages)
            job_id = 'judge:' + record['id']
            try:
                raw = await judge.generate(messages, job_id)
                write_json(folder / 'judge-response.json', raw)
                checked = DifficultyJudgeResult.model_validate(raw).model_dump()
                score(record, checked)
                record['judge_status'] = 'valid'
            except Exception as exc:
                record['judge_status'] = 'failed'
                record['judge_error'] = safe_error(exc)
                check_provider_failure(job_id)
            checkpoint()
            print(f"judged {record['id']} {record['judge_status']}", flush=True)

    try:
        # One complete canary first limits spend if either model endpoint fails.
        await generate_one(records[0])
        await judge_one(records[0])
        if records[0]['generation_status'] != 'valid' or records[0]['judge_status'] != 'valid':
            stop.set()
            manifest['stop_reason'] = 'canary_did_not_produce_a_valid_question_and_judgement'
        await asyncio.gather(*(generate_one(record) for record in records[1:]))
        order = records[1:].copy()
        rng.shuffle(order)
        await asyncio.gather(*(judge_one(record) for record in order))
        manifest['status'] = 'stopped_provider_error' if stop.is_set() else 'complete'
    except asyncio.CancelledError:
        manifest['status'] = 'interrupted'
        raise
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = safe_error(exc)
        raise
    finally:
        await generator.close()
        await judge.close()
        checkpoint()
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['actual_calls'] = len(call_rows(store))
        write_json(run / 'manifest.json', manifest)
        write_summary(run, records, call_rows(store))
        packet = []
        for record in records:
            prompt = run / 'items' / record['id'] / 'judge-prompt.json'
            if prompt.exists():
                packet.append({'blind_id': record['id'], 'assessment_input': json.loads(json.loads(prompt.read_text())[1]['content'])})
        random.Random(args.seed + 1).shuffle(packet)
        write_json(run / 'blind-review-packet.json', packet)
    return manifest['status'] == 'complete'


def write_summary(run, records, calls):
    summary = {'metrics': summarize(records), 'paired_vs_baseline': paired_comparisons(records),
        'calls': len(calls), 'reported_cost_usd': sum(c['usage']['cost'] for c in calls if 'cost' in c['usage']),
        'calls_with_cost': sum('cost' in c['usage'] for c in calls), 'calls_without_cost': sum('cost' not in c['usage'] for c in calls),
        'note': 'Reported cost covers only responses supplying a cost field; missing is not zero.'}
    for strategy, metric in summary['metrics'].items():
        ids = {r['id'] for r in records if r['strategy'] == strategy}
        own = [c for c in calls if c['job_id'].split(':', 1)[-1] in ids]
        metric['api_attempts'] = len(own)
        metric['reported_cost_usd'] = sum(c['usage']['cost'] for c in own if 'cost' in c['usage'])
        metric['calls_with_cost'] = sum('cost' in c['usage'] for c in own)
        metric['calls_without_cost'] = len(own) - metric['calls_with_cost']
        metric['total_tokens_reported'] = sum(c['usage'].get('total_tokens', 0) for c in own)
        metric['calls_without_total_tokens'] = sum('total_tokens' not in c['usage'] for c in own)
        metric['mean_api_duration_ms_per_requested_slot'] = sum(c.get('duration_ms') or 0 for c in own) / metric['requested']
        metric['api_attempts_per_qualified_question'] = len(own) / metric['qualified'] if metric['qualified'] else None
    write_json(run / 'summary.json', summary)
    lines = ['# D1 development screening', '', 'AI-judged frozen-context prompt comparison. No human or student calibration; no production change.', '',
        '| Strategy | Requested | Valid output | Judged | Difficulty matched | Qualified |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, row in summary['metrics'].items():
        lines.append(f"| {name} | {row['requested']} | {row['structurally_valid']} | {row['judged']} | {row['difficulty_matched']} | {row['qualified']} ({row['qualified_rate']:.1%}) |")
    lines += ['', f"API attempts: {summary['calls']}. Reported cost: ${summary['reported_cost_usd']:.6f} on {summary['calls_with_cost']} responses; {summary['calls_without_cost']} omit cost.", '',
        'These tiny development counts do not establish a strongest strategy. Keep source/model/prompt snapshots and failed cases; evaluate shortlisted prompts on untouched topics with repeats and human calibration.', '']
    (run / 'RESULTS.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--selection', choices=('pilot', 'dev', 'holdout'), default='pilot')
    parser.add_argument('--strategies', nargs='+', choices=tuple(STRATEGIES), default=list(STRATEGIES))
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20260919)
    parser.add_argument('--max-calls', type=int, default=80)
    parser.add_argument('--concurrency', type=int, choices=(1, 2, 3), default=2)
    parser.add_argument('--judge-model', default=DEFAULT_JUDGE)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay', type=Path)
    args = parser.parse_args()
    if args.replay:
        if args.live:
            parser.error('--live and --replay cannot be combined')
        records = json.loads((args.replay / 'records.json').read_text())
        calls = json.loads((args.replay / 'calls.json').read_text())
        print(json.dumps({'metrics': summarize(records), 'paired_vs_baseline': paired_comparisons(records), 'calls': len(calls)}, ensure_ascii=False, indent=2))
        return 0
    if len(set(args.strategies)) != len(args.strategies):
        parser.error('Duplicate strategies would overwrite evidence; select each strategy once')
    if args.repeats < 1 or args.max_calls < 1:
        parser.error('repeats and max-calls must be positive')
    dataset = json.loads(args.dataset.read_text())
    cases = select_cases(dataset, args.selection)
    planned = len(cases) * len(args.strategies) * args.repeats
    plan = {'cases': len(cases), 'strategies': args.strategies, 'question_slots': planned, 'max_planned_calls': planned * 2,
        'selection': args.selection, 'judge_model': args.judge_model, 'live': args.live}
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    if not args.live:
        return 0
    if planned * 2 > args.max_calls:
        parser.error('Plan exceeds max-calls; reduce cases/strategies/repeats')
    run = args.output or ROOT / 'docs/difficulty/experiments' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    for relative in ('scripts/difficulty_experiment.py', 'scripts/difficulty_prompts.py', 'app/models.py', 'app/difficulty.py', 'app/pipeline.py', 'app/providers.py'):
        target = run / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    write_json(run / 'code-hashes.json', {str(path.relative_to(run / 'code')): hashlib.sha256(path.read_bytes()).hexdigest() for path in (run / 'code').rglob('*.py')})
    success = asyncio.run(live_run(args, dataset, cases, args.strategies, run))
    print(run, flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
