"""Q1: bounded real-RAG quality/latency pilot; dry-run unless --live is explicit.

Uses a dedicated database and source snapshots. Review labels never enter a
generation request. A resume continues only unstarted tasks, not failed paid work.
"""
import argparse
import asyncio
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.models import GenerateRequest
from app.pipeline import Pipeline, parse_document, document_chunk_ids
from app.providers import ApiProviders
from app.store import dumps, now
from scripts.difficulty_experiment import CappedStore, digest, public_parameters, write_json

DATASET = ROOT / 'benchmarks/quality_latency_v1/dataset.json'
SCHEMA = 'quality-latency-baseline-v1'
LIMITATIONS = [
    'Small AI-prepared development pilot, not an independent human-labelled benchmark or production reliability estimate.',
    'Twelve knowledge needs with paired Chinese/English requests are twelve topic clusters, not twenty-four independent topics.',
    'Source languages and source families may not be balanced; record them separately from request language.',
    'One question per job does not measure the latency, diversity or scheduling of multi-question jobs.',
    'Current provider/model and all role prompts are shared; model gate success is not independent answer correctness.',
    'Exact reference-quote presence is a retrieval diagnostic, not semantic recall or citation support.',
    'One serial run per request; no causal speedup or statistically established strategy superiority.',
    'Indexing/setup calls are separate from per-question calls. Missing usage/cost remain unknown.',
    'Public prepared text excerpts bypass OCR/parser evaluation. Fusion, clarification and automatic exploration are disabled.',
]


def load_dataset(path):
    dataset = json.loads(Path(path).read_text())
    docs, cases = dataset['source_documents'], dataset['cases']
    by_id = {doc['id']: doc for doc in docs}
    if not docs or len(by_id) != len(docs) or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Source and case IDs must be unique.')
    if len(cases) != 24 or len({c['need_id'] for c in cases}) != 12:
        raise ValueError('Q1 requires twelve bilingual knowledge needs, twenty-four requests.')
    for doc in docs:
        if not doc.get('text', '').strip() or not doc.get('url') or not doc.get('license'):
            raise ValueError('Each source needs text, provenance URL and a license record.')
        if hashlib.sha256(doc['text'].encode()).hexdigest() != doc['text_sha256']:
            raise ValueError('Source text hash does not match the frozen dataset.')
    for need_id in {c['need_id'] for c in cases}:
        pair = [c for c in cases if c['need_id'] == need_id]
        if len(pair) != 2 or {c['language'] for c in pair} != {'zh', 'en'}:
            raise ValueError('Every need requires one Chinese and one English input.')
        if len({(c['course'], c['difficulty'], c['question_type']) for c in pair}) != 1:
            raise ValueError('Language pairs must keep course, target difficulty and question kind fixed.')
    if sorted(Counter(c['difficulty'] for c in cases).values()) != [8, 8, 8]:
        raise ValueError('Q1 needs eight cases per target difficulty.')
    if sorted(Counter(c['course'] for c in cases).values()) != [8, 8, 8]:
        raise ValueError('Q1 needs eight cases per course.')
    for case in cases:
        make_request(case)
        if not case.get('expected_evidence'):
            raise ValueError('Every request needs provisional evidence targets.')
        for target in case['expected_evidence']:
            doc = by_id.get(target['source_id'])
            if not doc or doc['course'] != case['course'] or not target['quote'].strip() or target['quote'] not in doc['text']:
                raise ValueError('A provisional evidence quote is absent from its course source.')
    return dataset


def course_id(course):
    return 'q1-course-' + digest(course)[:20]


def document_id(source_id):
    return 'q1-doc-' + digest(source_id)[:20]


def make_request(case):
    # Deliberate allowlist. No expected evidence, reference answer, grade, or
    # per-case gold-document filter is transmitted to retrieval/generation.
    return GenerateRequest(course_id=course_id(case['course']), topic=case['topic'],
        material='quiz', difficulty=case['difficulty'], question_type=case['question_type'],
        count=1, language=case['language'], learner_profile=case['learner_profile'],
        document_ids=[], include_explanations=False, query_fusion=False, auto_explore=False,
        request_key='q1-generation-' + case['id'])


def source_files():
    return sorted(path for path in (ROOT / 'app').rglob('*.py') if '__pycache__' not in path.parts) + [ROOT / path for path in (
        'scripts/quality_latency_baseline.py', 'scripts/quality_latency_metrics.py',
        'scripts/difficulty_experiment.py')]


def code_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files()}


def snapshot_code(output):
    index = code_hashes()
    for relative in index:
        target = output / 'code' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return index


def environment_record():
    packages = {}
    for name in ('pydantic', 'numpy', 'httpx', 'tokenizers', 'pypdf', 'fastapi'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {'python': sys.version, 'packages': packages,
        'dependency_file_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(ROOT.glob('requirements*.txt'))}}


def spent_session_seconds(sessions):
    total = 0
    for session in sessions:
        duration = session.get('wall_seconds')
        if not isinstance(duration, (int, float)) or duration < 0:
            # A hard-killed session has no observed stop time. Include downtime
            # conservatively rather than granting a fresh hour on resume.
            start = datetime.fromisoformat(session['started_at'])
            duration = max(0, (datetime.now(timezone.utc) - start).total_seconds())
            session['wall_seconds'] = duration
            session['timing_complete'] = False
            session['timing_note'] = 'Conservative elapsed upper bound after an unclean interruption; includes downtime.'
        total += duration
    return total


def make_settings(base, output, args):
    return replace(base, data_dir=output / 'runtime', max_daily_calls=args.call_cap,
                   agent_max_calls=min(base.agent_max_calls, args.per_job_cap))


def public_configuration(settings, pipeline):
    # Never serialize Settings or Endpoint: they contain credentials.
    return {'text_model': settings.text.model, 'text_endpoint_signature': settings.text.signature,
        'text_parameters': public_parameters(settings.text.extra), 'text_json_mode': settings.text_json_mode,
        'embedding_model': settings.embedding.model, 'embedding_signature': pipeline.embedding_signature(),
        'retrieval': pipeline.retrieval_configuration(), 'chunking': pipeline.chunking_configuration(),
        'workflow': settings.generation_workflow, 'runtime': settings.agent_runtime,
        'orchestration': settings.agent_orchestration, 'question_spec': settings.agent_question_spec,
        'agent_max_calls': settings.agent_max_calls, 'agent_max_repairs': settings.agent_max_repairs,
        'agent_context_chars': settings.agent_context_chars, 'timeout': settings.timeout,
        'harness': {key: getattr(settings, 'harness_' + key) for key in
            ('timeout', 'max_requests', 'max_output_tokens', 'reasoning_effort', 'response_format', 'schema_repairs')},
        'concurrency': 1, 'question_count': 1, 'include_explanations': False,
        'query_fusion': False, 'auto_explore': False, 'clarification': False}


def seed_documents(store, pipeline, dataset):
    directory = pipeline.settings.data_dir / 'documents'
    directory.mkdir(exist_ok=True)
    for course in sorted({doc['course'] for doc in dataset['source_documents']}):
        store.execute('INSERT OR IGNORE INTO courses VALUES(?,?,?)', (course_id(course), course, now()))
    config = pipeline.chunking_configuration()
    for doc in dataset['source_documents']:
        did = document_id(doc['id'])
        if store.one('SELECT 1 FROM documents WHERE id=?', (did,)):
            continue
        raw = doc['text'].encode()
        name = doc['id'] + '.md'
        (directory / (did + '.md')).write_bytes(raw)
        pages, chunks = parse_document(name, raw, **config)
        for chunk in chunks:
            chunk['metadata']['benchmark_source_id'] = doc['id']
        with store.connect() as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',
                (did, course_id(doc['course']), name, hashlib.sha256(raw).hexdigest(), 'parsed', len(pages), now()))
            store.save_chunks(db, did, document_chunk_ids(chunks, did), config)


def export_case(store, output, entry):
    if not entry.get('job_id'):
        return
    jid = entry['job_id']
    job = store.one('SELECT * FROM jobs WHERE id=?', (jid,))
    evidence = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (jid,))
    content = store.one('SELECT * FROM contents WHERE job_id=?', (jid,))
    record = {'run': entry, 'job': job, 'evidence': json.loads(evidence['evidence']) if evidence else None,
              'calls': store.calls_for_job(jid)}
    if content:
        record['content'] = {**content, **{key: json.loads(content[key]) for key in ('asset', 'sources', 'config')}}
    write_json(output / 'cases' / (entry['case_id'] + '.json'), record)


def export_run(store, output, manifest, rows, cases):
    from scripts.quality_latency_metrics import summarize_run, export_summary
    write_json(output / 'case_runs.json', rows)
    summary = summarize_run(store, rows, frozen_cases=cases)
    export_summary(summary, output)
    write_json(output / 'manifest.json', manifest)
    return summary


async def run(args, *, base=None, providers_factory=ApiProviders):
    if not 5 <= args.per_job_cap <= 24 or not 5 <= args.call_cap <= 256:
        raise ValueError('Per-job cap must be 5–24 and total cap 5–256.')
    if not 60 <= args.max_seconds <= 7200:
        raise ValueError('Run time cap must be between 60 and 7200 seconds.')
    dataset = load_dataset(args.dataset)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(args.output or ROOT / 'docs/evaluation/runs' / ('Q1-' + stamp)).resolve()
    if output == ROOT or output == (ROOT / 'data').resolve():
        raise ValueError('Experiment output must not be the workspace or product data directory.')
    cases = json.loads(dumps(dataset['cases']))
    for case in cases:
        for target in case['expected_evidence']:
            target['document_id'] = document_id(target['source_id'])
    if args.resume:
        manifest = json.loads((output / 'manifest.json').read_text())
        if (manifest['dataset_sha256'] != digest(dataset) or manifest['code_sha256'] != code_hashes()
                or manifest['live'] != args.live or manifest['call_cap'] != args.call_cap
                or manifest['per_job_cap'] != args.per_job_cap or manifest['seed'] != args.seed
                or manifest['max_seconds'] != args.max_seconds):
            raise ValueError('Frozen code, dataset, mode or budget changed; use a new run directory.')
        rows = json.loads((output / 'case_runs.json').read_text())
    else:
        output.mkdir(parents=True, exist_ok=False)
        order = [case['id'] for case in cases]
        random.Random(args.seed).shuffle(order)
        rows = [{'case_id': case, 'job_id': None, 'status': 'not_run'} for case in order]
        manifest = {'schema_version': SCHEMA, 'created_at': now(), 'live': args.live,
            'status': 'prepared', 'dataset_sha256': digest(dataset), 'code_sha256': snapshot_code(output),
            'call_cap': args.call_cap, 'per_job_cap': args.per_job_cap, 'max_seconds': args.max_seconds,
            'seed': args.seed, 'case_order': order, 'planned_cases': len(cases),
            'limitations': LIMITATIONS, 'environment': environment_record(), 'sessions': []}
        write_json(output / 'dataset.json', dataset)
        write_json(output / 'frozen_cases.json', cases)
        write_json(output / 'manifest.json', manifest)
        write_json(output / 'case_runs.json', rows)
    if not args.live:
        print(dumps({'dry_run': True, 'output': str(output), 'planned_cases': len(cases), 'actual_calls': 0}), flush=True)
        return output
    settings = make_settings(base or Settings.from_env(), output, args)
    settings.text.require('text'); settings.embedding.require('embedding')
    if (settings.generation_workflow, settings.agent_runtime, settings.agent_orchestration,
            settings.agent_question_spec) != ('agent_v1', 'native', 'sequential_v1', 'none'):
        raise ValueError('Q1 freezes agent_v1/native/sequential_v1/none; use a separate protocol for other runtimes.')
    store = CappedStore(output / 'runtime', args.call_cap)
    providers = providers_factory(settings, store)
    pipeline = Pipeline(settings, store, providers)
    public = public_configuration(settings, pipeline)
    if manifest.get('configuration') and manifest['configuration'] != public:
        await providers.close()
        raise ValueError('Provider/runtime configuration changed; use a new run directory.')
    manifest['configuration'] = public
    previous_seconds = spent_session_seconds(manifest['sessions'])
    manifest['sessions'].append({'started_at': now(), 'resume': args.resume})
    session = manifest['sessions'][-1]
    started = time.monotonic()
    deadline = args.max_seconds - previous_seconds
    by_id = {case['id']: case for case in cases}
    manifest['status'] = 'running'
    write_json(output / 'manifest.json', manifest)
    setup = manifest.setdefault('setup_jobs', [])
    stop_reason = None
    try:
        seed_documents(store, pipeline, dataset)
        for doc in dataset['source_documents']:
            did = document_id(doc['id'])
            current = store.one('SELECT status FROM documents WHERE id=?', (did,))
            if current['status'] == 'ready':
                continue
            remaining = deadline - (time.monotonic()-started)
            if remaining <= 0:
                stop_reason = 'time_cap'; break
            if store.one('SELECT count(*) AS n FROM calls')['n'] >= args.call_cap:
                stop_reason = 'call_cap'; break
            key = 'q1-index-' + doc['id']
            job, created = store.job(key, 'index', {'document_id': did})
            if not created and job['status'] != 'queued':
                stop_reason = 'index_failed_or_interrupted'
                break
            setup.append({'source_id': doc['id'], 'job_id': job['id']})
            await asyncio.wait_for(pipeline.run(job['id']), timeout=remaining)
            job = store.one('SELECT status,error FROM jobs WHERE id=?', (job['id'],))
            if job['status'] != 'succeeded':
                stop_reason = 'index_failed'
                print(dumps({'index_failed': doc['id'], 'error': job['error']}), flush=True)
                break
        if stop_reason:
            return output
        write_json(output / 'chunks.json', store.all('SELECT c.id,c.document_id,c.page,c.text,m.metadata FROM chunks c LEFT JOIN chunk_metadata m ON m.chunk_id=c.id'))
        consecutive_transport_failures = 0
        for entry in rows:
            if entry.get('job_id'):
                # Never silently replay an uncertain/failed billable request.
                old = store.one('SELECT status FROM jobs WHERE id=?', (entry['job_id'],))
                if old and old['status'] in ('queued', 'running'):
                    store.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=?",
                        ('Experiment session interrupted; automatic replay disabled.', now(), entry['job_id']))
                entry.update(status=old['status'] if old and old['status'] not in ('queued', 'running') else 'failed')
                export_case(store, output, entry)
                continue
            if code_hashes() != manifest['code_sha256']:
                stop_reason = 'code_changed'; break
            count = store.one('SELECT count(*) AS n FROM calls')['n']
            if count >= args.call_cap:
                stop_reason = 'call_cap'; break
            remaining = deadline - (time.monotonic()-started)
            if remaining <= 0:
                stop_reason = 'time_cap'; break
            case = by_id[entry['case_id']]
            request = make_request(case)
            job, created = store.job(request.request_key, 'generate', request.model_dump())
            if not created:
                raise ValueError('Unrecorded existing job prevents a safe automatic retry.')
            entry.update(job_id=job['id'], status='running', started_at=now())
            write_json(output / 'case_runs.json', rows)
            print(dumps({'starting': case['id'], 'calls_so_far': count}), flush=True)
            case_start = time.monotonic()
            try:
                await asyncio.wait_for(pipeline.run(job['id']), timeout=remaining)
            finally:
                entry.update(ended_at=now(), wall_seconds=round(time.monotonic()-case_start, 6))
                final = store.one('SELECT status,error FROM jobs WHERE id=?', (job['id'],))
                entry.update(status=final['status'], error=final['error'])
                export_case(store, output, entry)
                export_run(store, output, manifest, rows, cases)
            calls = store.calls_for_job(job['id'])
            transport_failed = any(call['status'] == 'failed' for call in calls)
            consecutive_transport_failures = consecutive_transport_failures + 1 if transport_failed else 0
            print(dumps({'finished': case['id'], 'status': entry['status'],
                'wall_seconds': entry['wall_seconds'], 'calls': len(calls)}), flush=True)
            if any(call.get('http_status') in (401, 402, 403) for call in calls):
                stop_reason = 'provider_access'; break
            if consecutive_transport_failures >= 3:
                stop_reason = 'provider_circuit_breaker'; break
        if stop_reason is None:
            manifest['status'] = 'completed'
    except TimeoutError:
        stop_reason = 'time_cap'
    except BaseException as exc:
        stop_reason = 'interrupted' if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError)) else 'runner_error'
        manifest['runner_error_type'] = type(exc).__name__
        raise
    finally:
        session.update(ended_at=now(), wall_seconds=round(time.monotonic()-started, 6), timing_complete=True)
        if stop_reason:
            manifest.update(status='stopped', stop_reason=stop_reason)
        for row in rows:
            if row.get('job_id'):
                export_case(store, output, row)
        export_run(store, output, manifest, rows, cases)
        await providers.close()
        print(dumps({'output': str(output), 'status': manifest['status'], 'stop_reason': stop_reason,
                     'actual_calls': store.one('SELECT count(*) AS n FROM calls')['n']}), flush=True)
    return output


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--dataset', type=Path, default=DATASET)
    result.add_argument('--output', type=Path)
    result.add_argument('--live', action='store_true')
    result.add_argument('--resume', action='store_true')
    result.add_argument('--call-cap', type=int, default=192)
    result.add_argument('--per-job-cap', type=int, default=12)
    result.add_argument('--max-seconds', type=int, default=3600)
    result.add_argument('--seed', type=int, default=20260922)
    return result


if __name__ == '__main__':
    asyncio.run(run(parser().parse_args()))
