"""Isolated progress UI fixture. Delays are test-only; no external model calls.

Run with uvicorn scripts.progress_fixture_server:create_fixture --factory --port 8767.
Input containing 'fail' simulates a provider failure; 'insufficient' returns no evidence.
"""
import asyncio
import json
from pathlib import Path
import runpy
from tempfile import mkdtemp

import httpx
from fastapi.testclient import TestClient

from app.config import Endpoint, Settings
from app.main import create_app
from app.providers import ApiProviders


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_workflow.py'))
    settings = Settings(data_dir=Path(mkdtemp(prefix='lumori-progress-ui-')),
                        auth_cookie_name='lumori_progress_fixture', generation_workflow='legacy_v3')
    for capability, path in [('text', '/chat/completions'), ('embedding', '/embeddings'),
                             ('speech', '/audio/speech'), ('image', '/images/generations')]:
        setattr(settings, capability, Endpoint('https://fixture.invalid/v1', 'test-key-not-real', 'fixture-model', path))
    ordinary = helpers['Wire']()
    delayed = False

    async def wire(request):
        data = json.loads(request.content)
        if 'messages' in data:
            user = json.loads(data['messages'][1]['content'])
            if set(user) == {'topic', 'material', 'learner_profile', 'language'}:
                decision = {'status': 'ready', 'question': '', 'options': [],
                            'reason': 'Isolated progress fixture.', 'anchor_quote': '', 'missing_information': ''}
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(decision)}}]})
            if 'query' in user and set(user) <= {'query', 'clarification'}:
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
                    'content': json.dumps({'query': '', 'needs_clarification': True, 'reason': 'Fixture fallback.'})}}]})
            if delayed:
                await asyncio.sleep(6 if user.get('task') == 'difficulty_assessment' else 12)
            if 'request' in user:
                topic = user['request']['topic']
                if 'fail' in topic:
                    return httpx.Response(503)
                ordinary.mode = 'insufficient' if 'insufficient' in topic else 'valid'
        elif delayed:
            await asyncio.sleep(8 if 'input' in data and request.url.path.endswith('/embeddings') else 5)
        return ordinary(request)

    factory = lambda config, store: ApiProviders(config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    with TestClient(create_app(settings, factory)) as client:
        helpers['authenticate'](client, email='progress@example.test', password='Fixture browser password 2026!')
        helpers['seed'](client)
    delayed = True
    return create_app(settings, factory)
