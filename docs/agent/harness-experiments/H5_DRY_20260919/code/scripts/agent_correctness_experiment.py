"""A1 bounded frozen-context smoke + regression gate; dry by default.

This is not a new human-labelled benchmark or a causal comparison with D1.
Canary author output is deliberately injected; only its solve/review are live.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import dumps, now
from scripts.difficulty_prompts import make_request
from scripts.difficulty_experiment import CappedStore, digest, write_json

CASES = ['cpu_scheduling_en_hard', 'cpu_scheduling_zh_hard', 'transactions_zh_medium']
CORRECTED_ANSWER = (
    'RR q=2: A 0–2, B 2–4, C 4–5, A 5–7, B 7–8, A 8–10. '
    'First start A=0,B=2,C=4; completion A=10,B=8,C=5. Response A=0,B=1,C=2, mean=1. '
    'Turnaround A=10,B=7,C=3, mean=20/3. At t=2 B has already waited since t=1, '
    'so the queue is B,C,A. C precedes the preempted A but not the previously waiting B. '
    'STCF: A 0–1, B 1–2, C 2–3, B 3–5, A 5–10. First start A=0,B=1,C=2; '
    'completion A=10,B=5,C=3. Response times are all zero, mean=0. Turnaround A=10,B=4,C=1, mean=5. '
    'Choose STCF for the stated finite workload and objective: lower mean response (0 versus 1), '
    'and all jobs finish. The mean response advantage does not imply universal superiority for '
    'different workloads, fairness or overhead objectives.')


class CanaryProviders(ApiProviders):
    def __init__(self, settings, store, asset=None):
        super().__init__(settings, store)
        self.injected_asset = asset

    async def generate(self, messages, job_id):
        if self.injected_asset is not None and json.loads(messages[1]['content']).get('task') == 'agent_author':
            return self.injected_asset
        return await super().generate(messages, job_id)


def canary_asset(case, corrected):
    packet = next(p for p in json.loads((ROOT / 'docs/difficulty/codex-review/20260919/packets.json').read_text())
                  if p['blind_id'] == 'Q016')
    q = packet['question'] | {'slot_id': 'q1', 'difficulty': 'hard',
        'difficulty_reason': 'Compare policies under a stated objective and justify the limits of the recommendation.',
        'citation_ids': [case['sources'][0]['id']], 'difficulty_design': {
            'cognitive_process': 'evaluate', 'concepts': ['RR', 'STCF', 'response and turnaround'],
            'expected_steps': ['Construct both schedules.', 'Compute response and turnaround.',
                               'Recommend a policy under the objective and discuss limits.']}}
    if corrected:
        q['answer'] = CORRECTED_ANSWER
        q['explanation'] = 'FIFO RR does not let a new arrival jump ahead of an earlier waiting job. Response is first start minus arrival; turnaround is completion minus arrival. Use the explicitly stated zero overhead and alphabetic ties.'
    return {'title': 'Scheduling regression canary', 'evidence_sufficient': True,
            'sections': [{'heading': 'Metrics', 'text': 'Response time is first start minus arrival. Turnaround time is completion minus arrival.',
                          'citation_ids': [case['sources'][0]['id']]}], 'questions': [q]}


async def run(args):
    dataset = json.loads((ROOT / 'benchmarks/difficulty/cases.json').read_text())
    by_id = {c['id']: c for c in dataset['cases']}
    plan = [{'id': 'canary_bad_Q016', 'case_id': CASES[0], 'mode': 'injected_bad'},
            {'id': 'canary_corrected_Q016', 'case_id': CASES[0], 'mode': 'injected_corrected'}]
    plan += [{'id': c, 'case_id': c, 'mode': 'live_author'} for c in CASES]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (Path(args.output) if args.output else ROOT / 'docs/agent/experiments' / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 'agent-a1-v1', 'created_at': now(), 'live': args.live,
                'call_cap': args.call_cap, 'plan': plan, 'dataset_sha256': digest(dataset),
                'limitations': ['AI-curated sources; no human or student gold labels.',
                    'Frozen contexts bypass retrieval; this does not evaluate RAG.',
                    'Canary author is injected and not a live end-to-end generation.',
                    'Same text model for author/solver/reviewer; shared errors remain possible.',
                    'Development smoke only, no statistical superiority or comparable D1 effect size.']}
    write_json(output / 'manifest.json', manifest)
    for relative in ['app/generation_agent.py', 'app/answer_tools.py', 'app/config.py', 'app/store.py',
                     'app/providers.py', 'app/pipeline.py', 'app/models.py', 'app/difficulty.py',
                     'scripts/agent_correctness_experiment.py']:
        target = output / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    if not args.live:
        print(dumps({'dry_run': True, 'output': str(output), 'slots': len(plan), 'max_live_calls': args.call_cap}), flush=True)
        return
    base = Settings.from_env()
    base.text.require('text')
    store = CappedStore(output / 'runtime', args.call_cap)
    store.execute('INSERT INTO courses VALUES(?,?,?)', ('difficulty-experiment', 'A1 isolated research fixtures', now()))
    rows = []
    for entry in plan:
        case = by_id[entry['case_id']]
        settings = replace(base, data_dir=output / 'runtime', generation_workflow='agent_v1',
                           agent_max_calls=12, agent_max_repairs=0 if entry['mode'] != 'live_author' else 1,
                           max_daily_calls=args.call_cap)
        req = make_request(case).model_copy(update={'request_key': 'a1-' + entry['id']})
        asset = canary_asset(case, entry['mode'] == 'injected_corrected') if entry['mode'] != 'live_author' else None
        providers = CanaryProviders(settings, store, asset)
        pipeline = Pipeline(settings, store, providers)

        async def frozen_retrieve(request, job_id, with_trace=True):
            return case['sources'], {'mode': 'frozen_fixture_context', 'case_id': case['id'],
                                    'source_sha256': digest(case['sources']), 'api_calls': 0}

        pipeline.retrieve = frozen_retrieve
        job, _ = store.job(req.request_key, 'generate', req.model_dump())
        print(dumps({'starting': entry['id']}), flush=True)
        try:
            await pipeline.run(job['id'])
        finally:
            await providers.close()
        job = store.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
        evidence = json.loads(store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))['evidence'])
        evidence['experiment'] = entry | {'author_injected': asset is not None}
        calls = store.calls_for_job(job['id'])
        row = entry | {'job_id': job['id'], 'status': job['status'], 'error': job['error'],
                       'calls': calls, 'evidence_file': entry['id'] + '.json'}
        write_json(output / row['evidence_file'], {'job': job, 'evidence': evidence, 'calls': calls})
        rows.append(row)
        write_json(output / 'results.json', rows)
        print(dumps({'finished': entry['id'], 'status': job['status'], 'live_calls': len(calls)}), flush=True)
    calls = [c for row in rows for c in row['calls']]
    write_json(output / 'summary.json', {'total_slots': len(rows), 'live_calls': len(calls),
        'provider_succeeded': sum(c['status'] == 'succeeded' for c in calls),
        'total_tokens': sum(c['usage'].get('total_tokens', 0) for c in calls),
        'known_cost_usd': sum(c['usage'].get('cost', 0) for c in calls),
        'cost_missing_calls': sum('cost' not in c['usage'] for c in calls),
        'gate_outcomes': {r['id']: r['status'] for r in rows}, 'limitations': manifest['limitations']})
    print(dumps({'output': str(output), 'live_calls': len(calls)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--call-cap', type=int, default=24, choices=range(1, 41))
    parser.add_argument('--output')
    asyncio.run(run(parser.parse_args()))
