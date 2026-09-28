"""Isolated browser QA server. Mock providers only; never touches project data.
Run: .venv/bin/python -m uvicorn scripts.ui_fixture_server:create_fixture --factory --port 8766
"""
from pathlib import Path
from tempfile import mkdtemp
import runpy
import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings, Endpoint
from app.providers import ApiProviders


def create_fixture():
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/test_workflow.py'))
    settings = Settings(data_dir=Path(mkdtemp(prefix='fyp-ui-qa-')), auth_cookie_name='fyp_ui_fixture_session')
    for capability, path in [('text','/chat/completions'),('embedding','/embeddings'),('speech','/audio/speech'),('image','/images/generations')]:
        setattr(settings, capability, Endpoint('https://test.invalid/v1','test-key-not-real','fixture-model',path))
    wire = helpers['Wire']()
    providers = lambda config, store: ApiProviders(config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    with TestClient(create_app(settings, providers)) as client:
        helpers['authenticate'](client, email='ui-fixture@example.test', password='Fixture browser password 2026!')
        course = client.post('/api/courses',json={'name':'界面验证 · 隔离测试课程'}).json()['id']
        document = client.post('/api/documents',data={'course_id':course},files={'file':('RAG_测试讲义.md','检索为生成提供课程参考资料。引用仍需核对。此文仅用于界面测试。'.encode())}).json()['id']
        helpers['done'](client, client.post('/api/documents/'+document+'/index'))
        first = helpers['generated'](client, course)
        client.post('/api/contents/'+first+'/review',json={'version':1,'action':'approve'})
        helpers['done'](client, client.post('/api/generations',json=helpers['request'](course,'ui-second-draft')))
    return create_app(settings, providers)
