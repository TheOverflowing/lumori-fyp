"""Frozen, bounded evaluation of the new two-stage reviewer. Dry by default.

Expected labels and split metadata never enter model prompts. Every attempted
case remains in the denominator. AI diagnostic labels cannot open a release gate.
"""
import argparse
import asyncio
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.providers import ApiProviders, ProviderError, ProviderOutputError
from scripts.difficulty_experiment import CappedStore, call_rows, write_json

CASE_FIELDS = ('learner_profile', 'student_visible_text', 'reference_answer',
               'reference_explanation', 'sources', 'kind', 'options')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def input_case(case):
    return {key: case[key] for key in CASE_FIELDS if key in case}


def score(records, cases):
    expected = {case['id']: case for case in cases}
    counts = Counter(row.get('decision', {}).get('status', 'unavailable') for row in records)
    defects = [row for row in records if expected[row['case_id']]['expected']['content_status'] == 'fail']
    controls = [row for row in records if expected[row['case_id']]['expected']['content_status'] == 'pass']
    decided = [row for row in controls if row.get('decision', {}).get('status') == 'assessed']
    false_clear = [row['case_id'] for row in defects if row.get('decision', {}).get('status') == 'assessed']
    false_reject = [row['case_id'] for row in controls if row.get('decision', {}).get('status') in ('content_issue', 'ungradable')]
    matched = [row for row in decided if row['decision'].get('estimated_difficulty') in
               expected[row['case_id']]['expected'].get('candidates', [])]
    return {'submitted': len(records), 'outcomes': dict(counts),
            'stages_validated': sum(row.get('analysis', {}).get('status') == 'validated' and
                                    row.get('verification', {}).get('status') == 'validated' for row in records),
            'defect_cases': len(defects), 'defects_cleared': false_clear,
            'control_cases': len(controls), 'controls_rejected': false_reject,
            'control_single_grade_coverage': len(decided) / len(controls) if controls else None,
            'control_single_grade_agreement': len(matched) / len(decided) if decided else None,
            'human_accuracy': None, 'production_ready': False,
            'release_blockers': ['No independent teacher calibration has been supplied.',
                                 'This small diagnostic is not a production error-rate estimate.']}


async def run(args):
    from app import difficulty_review_v2 as reviewer
    data = json.loads(args.dataset.read_text())
    cases = [case for case in data['cases'] if args.split == 'all' or case['split'] == args.split]
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Empty selection or duplicate case IDs')
    planned = 2 * len(cases) * args.repeats
    if not 1 <= args.repeats <= 2 or not planned <= args.max_calls <= 40:
        raise ValueError('Evaluation requires two calls per case within a hard cap of 40')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'dataset.json', {'cases': cases})
    hashes = {}
    for name in ('app/difficulty_review_v2.py', 'app/difficulty_judge.py',
                 'scripts/difficulty_review_v2_eval.py'):
        target = output / 'code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    records = [{'case_id': case['id'], 'repeat': repeat, 'status': 'pending'}
               for case in cases for repeat in range(args.repeats)]
    random.Random(926).shuffle(records)
    parameters = {'thinking': {'type': 'disabled'}, 'temperature': 0, 'max_tokens': 2400}
    manifest = {'kind': 'difficulty-review-v2-diagnostic', 'live': args.live,
                'status': 'prepared', 'protocol_sha256': reviewer.protocol_fingerprint(),
                'dataset_sha256': digest(cases), 'code_sha256': hashes,
                'planned_calls': planned, 'call_cap': args.max_calls,
                'parameters': parameters, 'split': args.split,
                'verifier_model_override': args.verifier_model,
                'production_ready': False, 'human_accuracy': None}
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'records.json', records)
    if not args.live:
        print(json.dumps({'status': 'prepared', 'planned_calls': planned}), flush=True)
        return
    base = Settings.from_env()
    settings = replace(base, text_json_mode=True, timeout=45,
                       text=replace(base.text, extra=parameters))
    settings.text.require('text')
    store = CappedStore(Path(tempfile.mkdtemp(prefix='lumori-review-v2-')), args.max_calls)
    provider = ApiProviders(settings, store)
    verification_settings = replace(settings, text=replace(
        settings.text, model=args.verifier_model or settings.text.model))
    verifier = ApiProviders(verification_settings, store)
    by_id = {case['id']: case for case in cases}
    manifest.update(status='running', model=settings.text.model,
                    verifier_model=verification_settings.text.model,
                    endpoint_signature=settings.text.signature,
                    verifier_endpoint_signature=verification_settings.text.signature)
    write_json(output / 'manifest.json', manifest)
    try:
        for row in records:
            source = by_id[row['case_id']]
            case = input_case(source)
            item_id = f'{row["case_id"]}_{row["repeat"]}'
            row.update(input_sha256=digest(case), status='running')
            started = time.monotonic()
            for stage in ('analysis', 'verification'):
                record = row[stage] = {'status': 'preparing'}
                try:
                    prompts = (reviewer.analysis_messages(case) if stage == 'analysis' else
                               reviewer.verification_messages(case, row['analysis']['result']))
                    write_json(output / 'items' / item_id / f'{stage}_prompt.json', prompts)
                    record.update(status='in_flight', prompt_sha256=digest(prompts))
                    write_json(output / 'records.json', records)
                    active_provider = provider if stage == 'analysis' else verifier
                    raw = await asyncio.wait_for(active_provider.generate(prompts, item_id), timeout=45)
                    write_json(output / 'items' / item_id / f'{stage}_response.json', raw)
                    result = (reviewer.validate_analysis(raw, case) if stage == 'analysis' else
                              reviewer.validate_verification(raw, case, row['analysis']['result']))
                    record.update(status='validated', result=result)
                except Exception as exc:
                    record.update(status='failed', error_type=type(exc).__name__)
                    if getattr(exc, 'code', None):
                        record['error_code'] = exc.code
                    if isinstance(exc, ProviderError) and not isinstance(exc, ProviderOutputError):
                        manifest['stop_reason'] = getattr(exc, 'code', None) or 'provider_failure'
                    break
            # Target only enters the local decision, never either review prompt.
            target = source.get('target_difficulty')
            row['decision'] = reviewer.decide(row.get('analysis', {}), row.get('verification', {}), target)
            row.update(status='complete' if all(row.get(s, {}).get('status') == 'validated'
                                               for s in ('analysis', 'verification')) else 'failed',
                       duration_ms=round((time.monotonic() - started) * 1000))
            write_json(output / 'records.json', records)
            print(item_id, row['status'], row['decision']['status'], flush=True)
            if manifest.get('stop_reason'):
                break
    finally:
        await provider.close()
        await verifier.close()
        for row in records:
            if row['status'] == 'pending':
                row.update(status='not_attempted', decision=reviewer.decide({}, {}, None))
            elif row['status'] == 'running':
                row.update(status='failed', decision=reviewer.decide(
                    row.get('analysis', {}), row.get('verification', {}),
                    by_id[row['case_id']].get('target_difficulty')))
        calls = call_rows(store)
        write_json(output / 'calls.json', calls)
        write_json(output / 'records.json', records)
        manifest.update(status='complete' if all(row['status'] == 'complete' for row in records)
                        else 'completed_with_failures', actual_calls=len(calls),
                        total_tokens=sum(c['usage'].get('total_tokens', 0) for c in calls),
                        calls_without_total_tokens=sum('total_tokens' not in c['usage'] for c in calls),
                        calls_without_cost=sum('cost' not in c['usage'] for c in calls))
        write_json(output / 'manifest.json', manifest)
        write_json(output / 'summary.json', score(records, cases))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'heldout', 'historical', 'all'), default='development')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--max-calls', type=int, default=24)
    parser.add_argument('--verifier-model', choices=('deepseek-flash', 'deepseek-v4-pro'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    asyncio.run(run(parser.parse_args()))
