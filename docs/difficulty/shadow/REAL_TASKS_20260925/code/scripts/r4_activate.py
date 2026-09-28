"""Prepare a verified index copy, then atomically promote only its index tables."""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings, Endpoint
from app.store import Store
from app.pipeline import Pipeline, read_document_pages
from app.providers import ApiProviders
from app.models import GenerateRequest
from app.rag_candidates import TokenCounter


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def state(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: {'count': len(rows), 'sha256': digest(rows)} for name in tables
            for rows in [[list(row) for row in db.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]]}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def profile(settings, directory):
    if settings.embedding.base_url != 'https://openrouter.ai/api/v1':
        raise ValueError('This activation is specific to the verified OpenRouter endpoint.')
    return replace(settings, data_dir=directory, chunk_strategy='recursive_token_v1',
        chunk_max_tokens=256, chunk_overlap_chars=0, retrieval_document_encoding='title_path_v1',
        retrieval_query_encoding='cs_instruction_v1', retrieval_strategy='hybrid_dense_lexical_v1',
        retrieval_candidate_k=20, top_k=5, retrieval_context_tokens=1024, retrieval_expansion='none',
        rag_tokenizer_path=ROOT/'.rag-models/embedding-tokenizer/tokenizer.json',
        rerank=Endpoint(settings.embedding.base_url, settings.embedding.api_key,
                        'qwen/qwen3-reranker-8b', '/rerank'))


async def prepare(run):
    directory = run/'runtime/activation'
    directory.mkdir(parents=True, exist_ok=False)
    settings = Settings.from_env()
    live = sqlite3.connect('file:' + str(settings.data_dir/'studio.sqlite3') + '?mode=ro', uri=True)
    before = state(live)
    if live.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]:
        raise ValueError('Wait for active application jobs before preparing an upgrade.')
    backup = sqlite3.connect(directory/'original.sqlite3')
    live.backup(backup); backup.close(); live.close()
    cloned = directory/'prepared'; cloned.mkdir()
    shutil.copyfile(directory/'original.sqlite3', cloned/'studio.sqlite3')
    (cloned/'documents').mkdir()
    psettings = profile(settings, cloned)
    store = Store(cloned)
    today = datetime.now(timezone.utc).isoformat()[:10]
    used = store.one('SELECT count(*) AS n FROM calls WHERE substr(created_at,1,10)=?', (today,))['n']
    psettings.max_daily_calls = min(psettings.max_daily_calls, used + 10)
    docs = store.all('SELECT * FROM documents ORDER BY id')
    if len(docs) != 2:
        raise ValueError('This bounded activation expects the two verified sample documents.')
    for doc in docs:
        source = settings.data_dir/'documents'/(doc['id']+Path(doc['name']).suffix.lower())
        raw = source.read_bytes()
        sample = ROOT/'sample_data'/doc['name']
        if hashlib.sha256(raw).hexdigest() != doc['sha256'] or not sample.is_file() or raw != sample.read_bytes():
            raise ValueError('Sample source identity changed; no API requests made.')
        shutil.copyfile(source, cloned/'documents'/source.name)
    provider = ApiProviders(psettings, store)
    pipeline = Pipeline(psettings, store, provider)
    old_calls = {r['id'] for r in store.all('SELECT id FROM calls')}
    evidence = {'prepared_at': datetime.now(timezone.utc).isoformat(), 'before': before,
        'profile': pipeline.retrieval_configuration(), 'chunking': pipeline.chunking_configuration(),
        'embedding_signature': pipeline.embedding_signature(), 'indexes': [], 'retrieval_smoke': []}
    try:
        for doc in docs:
            result = await pipeline.index(doc['id'], None)
            evidence['indexes'].append(result)
            print('Indexed', doc['name'], result['chunks'], flush=True)
        counter = TokenCounter(psettings.rag_tokenizer_path)
        for i, doc in enumerate(docs):
            topic = ('Why does RAG use source citations to check generated answers?' if i == 0
                     else '检索增强生成如何使用课程资料减少缺乏依据的回答？')
            request = GenerateRequest(course_id=doc['course_id'], document_ids=[doc['id']],
                                      topic=topic, request_key='r4-activation-'+str(i), language='en' if i == 0 else 'zh')
            sources, trace = await pipeline.retrieve(request, None, with_trace=True)
            if not sources or counter.count('\n\n'.join(s['text'] for s in sources)) > 1024:
                raise ValueError('Live retrieval returned empty or oversized evidence.')
            raw = (cloned/'documents'/(doc['id']+Path(doc['name']).suffix.lower())).read_bytes()
            pages = read_document_pages(doc['name'], raw)
            for s in sources:
                m = s['metadata']
                if s['document_id'] != doc['id'] or pages[s['page']-1][m['page_char_start']:m['page_char_end']] != s['text']:
                    raise ValueError('Context no longer matches the selected original document.')
            evidence['retrieval_smoke'].append({'language': request.language, 'sources': len(sources),
                'verified_source_offsets': True, 'trace': trace})
            print('Verified retrieval', request.language, 'tokens', trace['context_tokens'], flush=True)
        with store.connect() as db:
            after = state(db)
        for table in before.keys() - {'chunks', 'chunk_metadata', 'document_chunking', 'calls'}:
            if before[table] != after[table]:
                raise ValueError('Unexpected mutation to preserved table: ' + table)
        evidence['prepared_state'] = after
        evidence['new_call_ids'] = [r['id'] for r in store.all('SELECT id FROM calls') if r['id'] not in old_calls]
        evidence['calls'] = [{k: v for k, v in c.items() if k not in ('id', 'job_id')}
                             for c in store.all('SELECT * FROM calls') if c['id'] not in old_calls]
        if len(evidence['new_call_ids']) > 10 or any(c['status'] != 'succeeded' for c in evidence['calls']):
            raise ValueError('Activation call cap or success check failed.')
        evidence['application_code_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app').glob('*.py')}
        save(run/'activation-prepared.json', evidence)
    finally:
        await provider.close()


def commit(run):
    evidence = json.loads((run/'activation-prepared.json').read_text())
    settings = Settings.from_env()
    for name, expected in evidence['application_code_sha256'].items():
        if hashlib.sha256((ROOT/'app'/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Application code changed after prepared verification.')
    store = Store(settings.data_dir)
    clone = sqlite3.connect(run/'runtime/activation/prepared/studio.sqlite3')
    if state(clone) != evidence['prepared_state']:
        raise ValueError('Prepared database changed.')
    with store.connect() as live:
        live.execute('BEGIN IMMEDIATE')
        if state(live) != evidence['before']:
            raise ValueError('Live data changed while preparing the upgrade; nothing promoted.')
        live.execute('DELETE FROM chunk_metadata')
        live.execute('DELETE FROM chunks')
        live.execute('DELETE FROM document_chunking')
        for table in ('chunks', 'chunk_metadata', 'document_chunking'):
            rows = clone.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
            if rows:
                live.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in rows[0])+')', rows)
        for call_id in evidence['new_call_ids']:
            row = clone.execute('SELECT * FROM calls WHERE id=?',(call_id,)).fetchone()
            live.execute('INSERT INTO calls VALUES('+','.join('?' for _ in row)+')', row)
        promoted = state(live)
        for table in evidence['before'].keys() - {'chunks', 'chunk_metadata', 'document_chunking', 'calls'}:
            if promoted[table] != evidence['before'][table]:
                raise ValueError('Preserved content changed during promotion.')
    clone.close()
    save(run/'activation-promoted.json', {'promoted_at': datetime.now(timezone.utc).isoformat(),
        'after': promoted, 'preserved_courses_documents_jobs_contents_revisions': True,
        'calls_transferred': len(evidence['new_call_ids']), 'backup': str(run/'runtime/activation/original.sqlite3')})
    print('Atomically promoted verified indexes and actual API call records.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'commit'))
    p.add_argument('--run', type=Path, required=True)
    a = p.parse_args()
    decision = json.loads((a.run/'decision.json').read_text())
    if not decision['passes_frozen_upgrade_gate'] or decision['recommended_arm'] != 'api8b_none':
        raise SystemExit('This activation does not match the locked, validated strategy.')
    if a.stage == 'prepare': asyncio.run(prepare(a.run))
    else: commit(a.run)
