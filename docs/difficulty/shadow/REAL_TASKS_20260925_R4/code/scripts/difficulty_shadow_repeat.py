"""Repeat only a saved shadow difficulty judgement for stability; never generate or publish.

The supplied run must be the isolated live run, and the original prompt must match
the accepted saved content. At most two new provider calls are reserved.
"""
import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.difficulty_judge import validate
from app.difficulty_shadow import digest, visible_case
from app.providers import ApiProviders
from app.store import Store
from scripts.difficulty_experiment import write_json, call_rows


async def run(args):
    manifest = json.loads((args.run / 'manifest.json').read_text())
    if manifest.get('status') != 'complete' or manifest.get('database') != 'isolated_private_temp_directory':
        raise ValueError('Only a completed isolated live run may be repeated')
    evidence = json.loads((args.run / 'task_2_evidence.json').read_text())['evidence']
    content = json.loads((args.run / 'task_2_content.json').read_text())
    shadow = evidence['difficulty_shadow']
    if content['version'] != 1 or digest(content['asset']) != shadow['asset_sha256']:
        raise ValueError('Saved content differs from the original observation')
    question = shadow['questions'][0]
    case = visible_case(content['asset'], 0, evidence['request']['learner_profile'])
    messages = question['judge']['messages']
    if digest(case) != question['visible_input_sha256'] or digest(messages) != question['judge']['prompt_sha256']:
        raise ValueError('Original question or prompt hash differs')
    if args.repeats not in (1, 2):
        raise ValueError('Only one or two additional independent judgements are allowed')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {'kind': 'same_prompt_shadow_judge_repeat', 'source_run': str(args.run.resolve()),
              'source_asset_sha256': shadow['asset_sha256'], 'prompt_sha256': digest(messages),
              'prior_isolated_run_calls': manifest['actual_calls'],
              'other_failed_run_call_records': 1, 'planned_repeats': args.repeats,
              'human_validated': False, 'affects_primary_decision': False,
              'records': [], 'status': 'prepared'}
    write_json(output / 'results.json', record)
    if not args.live:
        return record
    base = Settings.from_env()
    frozen = evidence['configuration']['difficulty_shadow']
    settings = replace(base, text_json_mode=True, timeout=frozen['timeout'],
                       text=replace(base.text, extra=frozen['parameters']))
    settings.text.require('text')
    store = Store(Path(manifest['private_runtime_directory']))
    before = store.one('SELECT count(*) AS n FROM calls')['n']
    if before != manifest['actual_calls'] or before + args.repeats + 1 > 30:
        raise ValueError('Run call count changed or approved total cap would be exceeded')
    original_reserve = store.reserve_call
    def reserve(job_id, capability, model, limit):
        if store.one('SELECT count(*) AS n FROM calls')['n'] >= before + args.repeats:
            raise ValueError('Repeat call cap reached')
        return original_reserve(job_id, capability, model, limit)
    store.reserve_call = reserve
    job, _ = store.job('shadow-repeat-' + secrets.token_hex(8), 'shadow_repeat',
                       {'source_job_id': content['job_id'], 'prompt_sha256': digest(messages)})
    provider = ApiProviders(settings, store)
    try:
        for index in range(args.repeats):
            item = {'repeat': index + 1, 'status': 'pending'}
            try:
                raw = await asyncio.wait_for(provider.generate(messages, job['id']), timeout=frozen['timeout'])
                item.update(status='validated', response=raw, result=validate(raw, case))
            except Exception as exc:
                item.update(status='failed', error_type=type(exc).__name__)
            record['records'].append(item)
            write_json(output / 'results.json', record)
    finally:
        await provider.close()
    record['status'] = 'complete'
    record['new_calls'] = len(call_rows(store)) - before
    record['call_rows'] = [row for row in call_rows(store) if row['job_id'] == job['id']]
    write_json(output / 'results.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, default=str)[:2000])
