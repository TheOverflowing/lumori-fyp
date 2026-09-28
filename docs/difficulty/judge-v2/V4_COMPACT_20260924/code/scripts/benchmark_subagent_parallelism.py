"""Repeatable scheduler benchmark with fixed model-shaped responses and delay.

This measures scheduling overhead and overlap only, never provider throughput or
educational quality. It reuses the network-boundary fixtures from the tests.
"""
import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_flexible_agent import flexible_wire  # noqa: E402
from test_generation_agent import agent_case  # noqa: E402
from app.store import dumps  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--delay-ms', type=int, default=60)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20 or not 1 <= args.delay_ms <= 2000:
        parser.error('repeats must be 1..20 and delay-ms must be 1..2000')
    samples = []
    with tempfile.TemporaryDirectory(prefix='lumori-parallel-benchmark-') as temp:
        monkeypatch = MonkeyPatch()
        fixture = agent_case.__wrapped__(Path(temp))
        make_case = next(fixture)
        try:
            flexible_wire.__wrapped__(monkeypatch)
            # Interleave conditions to reduce systematic cache/order bias.
            for repeat in range(args.repeats):
                for limit in (1, 2, 3, 4):
                    rig = make_case(count=4, include_explanations=False,
                        settings_options={'agent_runtime': 'native',
                            'agent_orchestration': 'sequential_v1',
                            'agent_max_parallel_questions': limit})
                    payload = json.loads(rig.job()['payload']) | {'material': 'quiz', 'use_subagents': True}
                    rig.store.execute('UPDATE jobs SET payload=? WHERE id=?', (dumps(payload), rig.job_id))
                    original = rig.providers.generate
                    in_flight = peak = 0

                    async def delayed(messages, job_id):
                        nonlocal in_flight, peak
                        contract = json.loads(messages[1]['content'])
                        if contract['task'] == 'agent_plan':
                            return await original(messages, job_id)
                        in_flight += 1
                        peak = max(peak, in_flight)
                        try:
                            await asyncio.sleep(args.delay_ms / 1000)
                            return await original(messages, job_id)
                        finally:
                            in_flight -= 1

                    rig.providers.generate = delayed
                    started = time.perf_counter()
                    job = rig.run()
                    elapsed = (time.perf_counter() - started) * 1000
                    samples.append({'repeat': repeat + 1, 'parallel_limit': limit,
                        'elapsed_ms': round(elapsed, 1), 'peak_in_flight': peak,
                        'status': job['status'], 'text_calls': rig.text_call_count(),
                        'ordered_slots': [q['slot_id'] for q in rig.asset()['questions']]
                            if job['status'] == 'succeeded' else []})
        finally:
            monkeypatch.undo()
            try:
                next(fixture)
            except StopIteration:
                pass
    summary = {str(limit): {'median_elapsed_ms': round(statistics.median(
        s['elapsed_ms'] for s in samples if s['parallel_limit'] == limit), 1),
        'all_succeeded': all(s['status'] == 'succeeded' for s in samples if s['parallel_limit'] == limit),
        'max_peak_in_flight': max(s['peak_in_flight'] for s in samples if s['parallel_limit'] == limit)}
        for limit in (1, 2, 3, 4)}
    result = {'type': 'mocked_latency_scheduler_benchmark', 'question_count': 4,
        'per_role_delay_ms': args.delay_ms, 'repeats': args.repeats,
        'scope': 'Controller concurrency only; no DeepSeek model or quality measurement.',
        'samples': samples, 'summary': summary}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
