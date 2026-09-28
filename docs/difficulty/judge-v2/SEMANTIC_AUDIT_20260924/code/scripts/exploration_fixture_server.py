"""Disposable browser fixture: synthetic sources/model responses, no external calls.

Run: .venv/bin/uvicorn scripts.exploration_fixture_server:create_fixture --factory --port 8767
Sign in with exploration@example.test / Fixture browser password 2026!
The 1.5-second waits exist only to inspect animations; they are not performance evidence.
"""
import asyncio
import json
from pathlib import Path
import runpy
from tempfile import mkdtemp

import httpx
from fastapi.testclient import TestClient

from app import exploration_sources
from app.config import Endpoint, Settings
from app.main import create_app
from app.providers import ApiProviders

QUOTE = 'Retrieved course material provides reference evidence; its claims still need careful verification.'
BODY = QUOTE + ' Source citations identify the original passage and do not automatically establish correctness. '
BODY += 'Learning exercises can use new examples if their definitions and reasoning are grounded in the supplied reference.'
URL = 'https://example.org/lumori-ui-fixture'


def response(value):
    return httpx.Response(200, json={'choices':[{'finish_reason':'stop', 'message':{'content':json.dumps(value)}}]})


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_workflow.py'))
    settings = Settings(data_dir=Path(mkdtemp(prefix='lumori-exploration-ui-')),
        auth_cookie_name='lumori_exploration_fixture', generation_workflow='legacy_v3')
    for capability, path in [('text','/chat/completions'), ('embedding','/embeddings')]:
        setattr(settings, capability, Endpoint('https://fixture.invalid/v1','test-key-not-real','UI fixture model',path))
    ordinary = helpers['Wire']()

    async def wire(request):
        await asyncio.sleep(1.5)
        data = json.loads(request.content)
        if 'messages' in data:
            payload = json.loads(data['messages'][1]['content'])
            if set(payload) == {'topic','material','learner_profile','language'}:
                return response(dict(status='ready',question='',options=[],reason='Isolated UI fixture.',anchor_quote='',missing_information=''))
            if payload.get('task') == 'exploration_coverage':
                sources = payload['sources']
                status = 'sufficient' if sources else 'missing_knowledge'
                if 'missing image' in payload['request']['topic']: status='needs_user_input'
                requirement = dict(id='g1',need='Course retrieval evidence',covered=bool(sources),
                    supports=[dict(source_id=sources[0]['id'],quote=QUOTE)] if sources else [],
                    queries=[] if sources or status=='needs_user_input' else [
                        dict(query='course evidence retrieval',language='en'),dict(query='课程证据 检索',language='zh')])
                return response(dict(status=status,requirements=[requirement]))
            if payload.get('task') == 'exploration_selection':
                return response(dict(accept=True,reason_code='supports_gap',supports=[dict(gap_id='g1',quote=QUOTE)]))
            if 'query' in payload and set(payload) <= {'query','clarification'}:
                return response(dict(query='',needs_clarification=True,reason='Fixture only.'))
        return ordinary(request)

    async def search(settings, query, language='en', limit=8):
        await asyncio.sleep(1.5)
        return [dict(url=URL,title='Reference · synthetic UI fixture',provider='curated',
                     snippet='Synthetic fixture only.',storage_policy='open_license',license='Fixture only')]

    async def fetch(settings, url):
        await asyncio.sleep(1.5)
        return dict(url=URL,original_url=URL,content_type='text/html',
            raw=('<html><title>Synthetic reference</title><main><p>'+BODY+'</p></main></html>').encode(),
            storage_policy='open_license',license='Fixture only')

    exploration_sources.search, exploration_sources.fetch_source = search, fetch
    factory = lambda config, store: ApiProviders(config,store,httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    with TestClient(create_app(settings,factory)) as client:
        helpers['authenticate'](client,email='exploration@example.test',password='Fixture browser password 2026!')
        client.post('/api/courses',json={'name':'自动探索 · 界面测试（模拟资料）'})
    return create_app(settings,factory)
