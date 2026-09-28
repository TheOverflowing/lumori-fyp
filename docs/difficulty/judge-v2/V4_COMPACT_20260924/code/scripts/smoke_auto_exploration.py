"""Explicit, bounded live smoke in a temporary database; never a retrieval benchmark.

Requires --live. Public concept prompts only; provider keys are loaded locally and
never exported. Search ledger entries and model/embedding calls share a bounded cap.
"""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from tempfile import mkdtemp, gettempdir
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.models import GenerateRequest
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import Store, dumps, now, uid


async def smoke(output, reuse_report=None, case='python', language='en'):
    if reuse_report:
        previous=json.loads(reuse_report.read_text())
        data=Path(previous['temporary_data_dir']).resolve()
        if (previous.get('kind')!='live_smoke_not_benchmark' or not data.is_dir()
                or not data.name.startswith('lumori-exploration-live-')
                or not data.is_relative_to(Path(gettempdir()).resolve())):
            raise ValueError('Only this smoke script\'s existing temporary database may be reused.')
    else:
        data = Path(mkdtemp(prefix='lumori-exploration-live-'))
    settings = replace(Settings.from_env(), data_dir=data, max_daily_calls=16 if case == 'python' else 28,
        exploration_search_provider='curated', exploration_max_rounds=1,
        exploration_max_documents=1, exploration_max_candidates=4,
        exploration_max_search_calls=2, exploration_max_model_calls=5,
        exploration_max_seconds=180)
    if case == 'machine-learning':
        settings = replace(settings, exploration_max_rounds=2, exploration_max_documents=3,
            exploration_max_candidates=8, exploration_max_search_calls=6, exploration_max_model_calls=8)
    store = Store(data)
    course_id = 'smoke-' + case
    store.execute('INSERT OR IGNORE INTO courses VALUES(?,?,?)', (course_id, 'Public course discovery smoke: '+case, now()))
    providers = ApiProviders(settings, store)
    model_outputs = []
    generate = providers.generate
    async def capture(messages, job_id):
        result = await generate(messages, job_id)
        payload = json.loads(messages[1]['content'])
        task = payload.get('task')
        if task in ('exploration_coverage','exploration_selection') and isinstance(result,dict):
            # This explicit smoke uses public course sources only. Retain the
            # requested structured decision fields, never provider reasoning.
            allowed = {'status','requirements'} if task == 'exploration_coverage' else {'accept','reason_code','supports'}
            input_fields = {'sources','fixed_requirements'} if task == 'exploration_coverage' else {'requirements','passages','extraction_warnings'}
            model_outputs.append({'task':task, 'input':{k:v for k,v in payload.items() if k in input_fields},
                                  'output':{k:v for k,v in result.items() if k in allowed}})
        return result
    providers.generate = capture
    pipeline = Pipeline(settings, store, providers)
    root = Path(__file__).resolve().parents[1]
    implementation = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
        'app/auto_exploration.py', 'app/exploration_staging.py', 'app/exploration_evidence.py',
        'app/exploration_context.py', 'app/exploration_sources.py', 'app/exploration_policy.py',
        'app/config.py', 'app/pipeline.py', 'app/store.py', 'scripts/smoke_auto_exploration.py')}
    request = GenerateRequest(course_id=course_id, material='lesson', difficulty='easy' if case == 'python' else 'medium', count=1,
        topic=('Explain how Python list append() and pop() implement a stack, with one small teaching example.'
               if case == 'python' else 'Could u give me a brief introduction about machine learning?'),
        learner_profile=('Undergraduate beginners who know Python variables and basic lists.'
               if case == 'python' else 'Undergraduate students who have studied the selected course materials'),
        language=language, request_key='public-'+case+'-exploration-smoke-'+uid(), auto_explore=True)
    job, _ = store.job(request.request_key, 'generate', request.model_dump())
    started = time.monotonic()
    await pipeline.run(job['id'])
    row = store.one('SELECT status,result,error FROM jobs WHERE id=?', (job['id'],))
    exploration = store.one('SELECT state FROM exploration_runs WHERE job_id=?', (job['id'],))
    evidence = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
    temporary_indexes = [json.loads(row['state']) for row in store.all(
        'SELECT state FROM exploration_candidate_indexes WHERE job_id=?', (job['id'],))]
    result = {'kind':'live_smoke_not_benchmark', 'recorded_at':now(), 'job_id':job['id'],
        'temporary_data_dir':str(data), 'request':request.model_dump(), 'status':row['status'],
        'reuses_smoke_sources':bool(reuse_report),
        'result':json.loads(row['result']) if row['result'] else None, 'error':row['error'],
        'elapsed_ms':round((time.monotonic()-started)*1000),
        'exploration':json.loads(exploration['state']) if exploration else None,
        'evidence':json.loads(evidence['evidence']) if evidence else None,
        'calls':store.calls_for_job(job['id']),
        'structured_model_outputs':model_outputs,
        'implementation_sha256': implementation,
        'storage_audit': {
            'course_document_count': store.one('SELECT COUNT(*) n FROM documents WHERE course_id=?', (course_id,))['n'],
            'course_indexed_chunk_count': store.one('SELECT COUNT(*) n FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.course_id=? AND c.vector IS NOT NULL', (course_id,))['n'],
            'temporary_indexes': [{'source_sha256':item.get('source_sha256'), 'status':item.get('status'),
                'retains_temporary_payload': any(key in item for key in ('chunks','vectors','report','passages','queries'))}
                for item in temporary_indexes]},
        'limitations':['One live smoke, not recall/precision or comparative effectiveness.',
            'No human verification or learner evaluation.', 'Currency cost is unknown; recorded usage is provider-reported.']}
    if result['result'] and result['result'].get('content_id'):
        content = store.one('SELECT asset FROM contents WHERE id=?', (result['result']['content_id'],))
        result['asset'] = json.loads(content['asset'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps(result)+'\n', encoding='utf-8')
    print(dumps({'status':result['status'], 'elapsed_ms':result['elapsed_ms'],
        'calls':len(result['calls']), 'error':result['error'], 'report':str(output.resolve())}))
    await providers.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-report', type=Path)
    parser.add_argument('--case', choices=['python', 'machine-learning'], default='python')
    parser.add_argument('--language', choices=['en','zh'], default='en')
    args = parser.parse_args()
    if not args.live: parser.error('--live is required; this smoke makes metered provider calls')
    asyncio.run(smoke(args.output, args.reuse_report, args.case, args.language))
