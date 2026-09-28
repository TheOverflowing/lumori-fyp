"""Small isolated DeepSeek latency check for explicit per-question workers.

Three identical 3-question jobs differ only in worker limit. This is a small
operational sample, not an educational-quality evaluation or provider SLA.
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
from app.config import Settings
from app.models import GenerateRequest
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import Store, now


SOURCE = {'id': 'benchmark-ml-source-1', 'document_id': 'benchmark-ml-document-1',
    'document_name': 'Controlled ML course note', 'page': 1,
    'text': (
        'Supervised machine learning uses labelled examples to fit a model that predicts an output for a new input. '
        'In classification the output is a category, such as spam or not spam; in regression it is a continuous number. '
        'A training set is used to fit parameters. A validation set is used for model selection and hyperparameter tuning. '
        'A held-out test set estimates generalization after model selection; using it repeatedly for tuning leaks information. '
        'Overfitting means strong training performance but weaker performance on unseen examples. '
        'Regularization, simpler models, and more representative training data can reduce overfitting. '
        'Feature scaling is fitted on training data only, then applied to validation and test data to prevent leakage. '
        'Accuracy is the fraction of correct classifications, but class imbalance can make it misleading. '
        'Precision measures the fraction of predicted positives that are truly positive; recall measures the fraction '
        'of actual positives identified. Choosing a metric depends on the cost of false positives and false negatives.'),
    'metadata': {'source_kind': 'text', 'extraction_method': 'controlled_benchmark',
        'extraction_status': 'ready', 'extraction_warnings': []}}


async def one(limit, root):
    settings = Settings.from_env()
    settings.data_dir = root / f'limit-{limit}'
    settings.generation_workflow = 'agent_v1'
    settings.agent_runtime = 'native'
    settings.agent_orchestration = 'sequential_v1'
    settings.agent_max_parallel_questions = limit
    settings.agent_max_calls = 24
    settings.max_daily_calls = 100
    store = Store(settings.data_dir)
    store.execute('INSERT INTO courses VALUES(?,?,?)', ('benchmark-course', 'ML benchmark', now()))
    provider = ApiProviders(settings, store)
    pipeline = Pipeline(settings, store, provider, enforce_account_ownership=False)

    async def retrieve(request, job_id, *, with_trace=False):
        assert with_trace
        return [SOURCE], {'configuration': {'strategy': 'frozen_controlled_source'}, 'selected_count': 1}

    pipeline.retrieve = retrieve
    request = GenerateRequest(course_id='benchmark-course',
        topic='Create three distinct introductory machine-learning practice questions about data splits, overfitting, and evaluation metrics.',
        material='quiz', difficulty='easy', count=3, language='en',
        learner_profile='Undergraduate students beginning machine learning',
        question_type='short_answer', include_explanations=False,
        use_subagents=True, request_key=f'live-parallel-limit-{limit}')
    job, _ = store.job(request.request_key, 'generate', request.model_dump())
    started = time.perf_counter()
    try:
        await pipeline.run(job['id'])
    finally:
        await provider.close()
    elapsed = round(time.perf_counter() - started, 2)
    final = store.one('SELECT status FROM jobs WHERE id=?', (job['id'],))
    calls = store.all('SELECT capability,status,duration_ms,usage,http_status FROM calls WHERE job_id=?', (job['id'],))
    text_calls = [call for call in calls if call['capability'] == 'text']
    evidence = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
    state = json.loads(evidence['evidence'])['agent'] if evidence else {}
    return {'parallel_limit': limit, 'elapsed_seconds': elapsed, 'status': final['status'],
        'text_calls': len(text_calls), 'successful_text_calls': sum(c['status'] == 'succeeded' for c in text_calls),
        'http_statuses': [c['http_status'] for c in text_calls if c['http_status'] and c['http_status'] != 200],
        'median_text_call_ms': round(statistics.median(c['duration_ms'] for c in text_calls), 1)
            if text_calls else None,
        'agent_status': state.get('status'),
        'attempts_per_question': [len(s.get('attempts', [])) for s in state.get('slots', [])],
        'failed_gate_codes': sorted({issue for slot in state.get('slots', [])
            for attempt in slot.get('attempts', [])
            for issue in attempt.get('feedback', {}).get('issues', [])}),
        'passed_questions': sum(s.get('status') == 'passed' for s in state.get('slots', [])),
        'total_questions': len(state.get('slots', []))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.text.configured:
        raise SystemExit('Text model is not configured; no live calls started.')
    with tempfile.TemporaryDirectory(prefix='lumori-live-parallel-') as temp:
        results = []
        for limit in (1, 2, 3):
            result = asyncio.run(one(limit, Path(temp)))
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    record = {'type': 'live_provider_small_sample', 'model': settings.text.model,
        'date': now(), 'source': 'controlled synthetic ML course note',
        'repetitions_per_limit': 1,
        'limits': [1, 2, 3], 'results': results,
        'interpretation_boundary': 'One job per limit, fixed source and task, but model output and service load vary. Do not treat as a reliable p95 or quality ranking.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
