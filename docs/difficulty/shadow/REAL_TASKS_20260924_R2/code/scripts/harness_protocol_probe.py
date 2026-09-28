"""One explicitly requested diagnostic call; never retries or executes tools.

Replays a recorded Harness request into an isolated one-call ledger and retains
the redacted HTTP response even if the strict relay validator rejects its shape.
"""
import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.harness_relay import _clean, _completion
from app.providers import ApiProviders, ProviderError
from scripts.difficulty_experiment import CappedStore, write_json


async def run(args):
    record = json.loads(Path(args.evidence).read_text())
    phase = next(h['harness'] for slot in record['evidence']['agent']['slots']
        for attempt in slot['attempts'] for name in ('author', 'solve', 'review')
        for h in attempt.get(name, {}).get('history', []) if h.get('harness', {}).get('model_calls'))
    payload = phase['model_calls'][0]['request']
    if not args.live:
        print(json.dumps({'dry': True, 'max_actual_calls': 1}))
        return
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    settings = replace(Settings.from_env(), data_dir=output / 'runtime', max_daily_calls=1)
    store = CappedStore(settings.data_dir, 1)
    job, _ = store.job('harness-protocol-probe', 'generate', {})
    providers = ApiProviders(settings, store)
    secrets = [getattr(settings, name).api_key for name in ('text','embedding','rerank','speech','image','vision')]
    result = {'source_evidence': str(Path(args.evidence).resolve()), 'request': _clean(payload, secrets),
              'tools_executed': False, 'classification': 'transport_diagnostic_not_quality_evaluation'}

    def validate(data):
        result['response'] = _clean(data, secrets)
        return _completion(data)

    try:
        await providers.call('text', payload, job['id'], validator=validate)
        result['validator'] = 'accepted'
    except ProviderError:
        result['validator'] = 'rejected'
    finally:
        await providers.close()
        result['calls'] = store.calls_for_job(job['id'])
        write_json(output / 'diagnostic.json', result)
    response = result.get('response', {})
    choices = response.get('choices', [])
    print(json.dumps({'validator': result['validator'], 'response_keys': list(response),
        'choice_keys': [list(c) for c in choices],
        'finish_reasons': [c.get('finish_reason') for c in choices],
        'message_keys': [list(c.get('message', {})) for c in choices],
        'tool_shapes': [[{'keys': list(t), 'name': t.get('function', {}).get('name'),
                         'function_keys': list(t.get('function', {}))}
                         for t in c.get('message', {}).get('tool_calls') or []] for c in choices]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    asyncio.run(run(parser.parse_args()))
