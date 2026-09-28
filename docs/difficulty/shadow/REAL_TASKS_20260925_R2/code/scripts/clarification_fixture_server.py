"""Isolated browser QA for clarification. Uses public fixtures and zero live APIs.

Run .venv/bin/python -m uvicorn scripts.clarification_fixture_server:create_fixture --factory --port 8767
"""
import json
from pathlib import Path
import runpy
from tempfile import mkdtemp

import httpx
from fastapi.testclient import TestClient
from app.config import Settings, Endpoint
from app.main import create_app
from app.providers import ApiProviders


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1]/'tests/test_workflow.py'))
    settings = Settings(data_dir=Path(mkdtemp(prefix='lumori-clarification-ui-')),
                        auth_cookie_name='lumori_clarification_fixture', generation_workflow='legacy_v3')
    for cap, path in [('text', '/chat/completions'), ('embedding', '/embeddings')]:
        setattr(settings, cap, Endpoint('https://fixture.invalid/v1', 'test-key-not-real', 'fixture-model', path))
    ordinary = helpers['Wire']()

    def wire(request):
        data = json.loads(request.content)
        if 'messages' in data:
            user = json.loads(data['messages'][1]['content'])
            if 'query' in user and set(user) <= {'query', 'clarification'}:
                en = not any('\u3400' <= c <= '\u9fff' for c in user['query'])
                decision = {'query': 'Retrieval in course-grounded generation' if en else '课程资料检索与生成依据',
                            'needs_clarification': False, 'reason': 'Isolated fusion fixture.'}
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(decision)}}],
                                               'usage': {'total_tokens': 0}})
            if set(user) == {'topic', 'material', 'learner_profile', 'language'}:
                if 'unavailable' in user['topic']:
                    return httpx.Response(503)
                en = user['language'] == 'en'
                decision = {'status': 'clarification_required',
                            'question': 'Which part would you like to improve?' if en else '你希望重点改善哪一方面？',
                            'options': ['Running time', 'Memory use'] if en else ['运行时间', '内存占用'],
                            'reason': 'Isolated interface fixture, not a model judgment.',
                            'anchor_quote': user['topic'][:100],
                            'missing_information': 'The intended optimization target.'}
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(decision)}}],
                                               'usage': {'total_tokens': 0}})
        return ordinary(request)

    factory = lambda config, store: ApiProviders(config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    with TestClient(create_app(settings, factory)) as client:
        helpers['authenticate'](client, email='clarification@example.test', password='Fixture browser password 2026!')
        helpers['seed'](client)
        client.post('/api/auth/logout')
        client.headers.pop('X-CSRF-Token', None)
        client.headers.pop('X-Account-ID', None)
        helpers['authenticate'](client, email='second@example.test', password='Fixture browser password 2026!')
        helpers['seed'](client)
    return create_app(settings, factory)
