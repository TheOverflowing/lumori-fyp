"""Measure configured text endpoint with identical tiny JSON requests.

This isolates provider response latency from stochastic educational content
gates. It does not measure end-to-end generation or learner quality.
"""
import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402
from app.providers import ApiProviders  # noqa: E402
from app.store import Store  # noqa: E402


MESSAGES = [
    {'role': 'system', 'content': 'Return only one JSON object with ok=true and topic="machine learning".'},
    {'role': 'user', 'content': '{"task":"fixed JSON response","topic":"machine learning"}'},
]


async def sample(provider, store, cap, repeat, requests):
    job, _ = store.job(f'fixed-concurrency-{repeat}-{cap}', 'generate', {})
    sem = asyncio.Semaphore(cap)
    outcomes = []

    async def call_one():
        async with sem:
            start = time.perf_counter()
            try:
                value = await provider.generate(MESSAGES, job['id'])
                status = 'succeeded' if value.get('ok') is True else 'unexpected_json'
            except Exception as exc:
                status = getattr(exc, 'code', None) or type(exc).__name__
            outcomes.append({'status': status, 'duration_ms': round((time.perf_counter() - start) * 1000)})

    start = time.perf_counter()
    await asyncio.gather(*(call_one() for _ in range(requests)))
    return {'repeat': repeat, 'parallel_limit': cap,
        'elapsed_ms': round((time.perf_counter() - start) * 1000),
        'successes': sum(o['status'] == 'succeeded' for o in outcomes),
        'requests': requests, 'statuses': [o['status'] for o in outcomes],
        'median_request_ms': statistics.median(o['duration_ms'] for o in outcomes),
        'p95_request_ms': sorted(o['duration_ms'] for o in outcomes)[(95 * requests + 99) // 100 - 1]}


async def run(args):
    settings = Settings.from_env()
    if not settings.text.configured:
        raise SystemExit('Text endpoint not configured; no calls started.')
    with tempfile.TemporaryDirectory(prefix='lumori-provider-concurrency-') as temp:
        settings.data_dir = Path(temp)
        settings.max_daily_calls = max(settings.max_daily_calls, args.requests * args.repeats * len(args.limits) + 10)
        store = Store(settings.data_dir)
        provider = ApiProviders(settings, store)
        try:
            samples = []
            for repeat in range(1, args.repeats + 1):
                for cap in (args.limits if repeat % 2 else tuple(reversed(args.limits))):
                    result = await sample(provider, store, cap, repeat, args.requests)
                    samples.append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            await provider.close()
    return {'type': 'fixed_prompt_live_provider_concurrency', 'model': settings.text.model,
        'requests_per_condition': args.requests, 'repeats': args.repeats,
        'limits': args.limits,
        'scope': 'Identical short JSON calls; no full agent workflow or educational quality.',
        'samples': samples,
        'summary': {str(cap): {
            'median_elapsed_ms': statistics.median(s['elapsed_ms'] for s in samples if s['parallel_limit'] == cap),
            'successes': sum(s['successes'] for s in samples if s['parallel_limit'] == cap),
            'requests': sum(s['requests'] for s in samples if s['parallel_limit'] == cap)}
            for cap in args.limits}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requests', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--limits', type=str, default='1,2,3,4')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        args.limits = tuple(int(value) for value in args.limits.split(','))
    except ValueError:
        parser.error('limits must be comma-separated integers')
    if (not 1 <= args.requests <= 64 or not 1 <= args.repeats <= 5 or
            not args.limits or len(set(args.limits)) != len(args.limits) or
            any(not 1 <= cap <= 40 for cap in args.limits) or
            max(args.limits) > args.requests):
        parser.error('requests must be 1..64, repeats 1..5, unique limits 1..40 and at most requests')
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
