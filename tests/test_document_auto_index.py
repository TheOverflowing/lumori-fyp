"""Automatic upload-to-index flow with real job ownership and mocked providers."""
import pytest
from fastapi.testclient import TestClient

from app import document_backends
from app.config import Settings,Endpoint
from app.document_parsing import ParsedDocument,ParsedPage
from app.models import GenerateRequest
from test_workflow import rig,done,authenticate
from test_figure_pipeline import rig as figure_rig,upload,await_job


@pytest.fixture
def automatic(rig):
    client,app,wire=rig
    app.state.settings.document_auto_index=True
    return client,app,wire


@pytest.fixture
def automatic_figures(figure_rig):
    client,app,wire=figure_rig
    app.state.settings.document_auto_index=True
    return client,app,wire


def source(client,*,text='A stack removes the most recently added item first.'):
    cid=client.post('/api/courses',json={'name':'Automatic indexing fixture'}).json()['id']
    response=client.post('/api/documents',data={'course_id':cid},files={'file':('notes.md',text.encode())})
    assert response.status_code==201,response.text
    return cid,response.json()


def listing(client,cid):
    return client.get('/api/documents',params={'course_id':cid}).json()[0]


def test_web_profile_indexes_automatically_by_default(monkeypatch):
    monkeypatch.delenv('DOCUMENT_AUTO_INDEX',raising=False)
    assert Settings.from_env().document_auto_index is True
    monkeypatch.setenv('DOCUMENT_AUTO_INDEX','false')
    assert Settings.from_env().document_auto_index is False


def test_text_upload_indexes_without_a_manual_index_request(automatic):
    client,app,wire=automatic
    cid,document=source(client)
    job=await_job(client,document['index_job']['job_id'])
    assert job['status']=='succeeded',job
    assert listing(client,cid)['index_current'] is True
    chunks=app.state.store.document_chunks(document['id'])
    assert chunks and all(chunk['vector'] and chunk['embedding_signature'] for chunk in chunks)
    owner=app.state.store.one('SELECT user_id FROM course_owners WHERE course_id=?',(cid,))
    assert app.state.store.one('SELECT user_id FROM job_owners WHERE job_id=?',(job['id'],))==owner
    assert wire.calls==1


@pytest.mark.parametrize('images',[False,True])
def test_async_pdf_processing_chains_into_an_owned_index(automatic_figures,images):
    client,app,wire=automatic_figures
    cid,did,parsed=upload(client,images=images)
    processed=await_job(client,parsed['result']['figures_job']['job_id']) if images else parsed
    indexed=await_job(client,processed['result']['index_job']['job_id'])
    assert indexed['status']=='succeeded',indexed
    doc=listing(client,cid)
    assert doc['index_current'] and not doc['active_jobs']
    assert all(chunk['vector'] for chunk in app.state.store.document_chunks(did))
    assert wire.vision==int(images) and wire.embeddings==1+int(images)
    assert not doc['index_error']
    if images:assert doc['figures'][0]['indexed']


def test_pure_image_pdf_becomes_searchable_after_figure_and_index_jobs(automatic_figures,monkeypatch):
    client,app,wire=automatic_figures
    async def empty_text(settings,name,raw,tier):
        return ParsedDocument(name,'fixture_image_only',[ParsedPage(1,'',method='fixture',status='unreadable')])
    monkeypatch.setattr(document_backends,'parse',empty_text)
    cid,did,parsed=upload(client)
    figures=await_job(client,parsed['result']['figures_job']['job_id'])
    indexed=await_job(client,figures['result']['index_job']['job_id'])
    assert indexed['status']=='succeeded' and indexed['result']['chunks']==0
    assert listing(client,cid)['index_current']
    request=GenerateRequest(course_id=cid,topic='binary tree',material='lesson',request_key='image-only-query')
    sources=client.portal.call(app.state.pipeline.retrieve,request,indexed['id'])
    assert sources and all(s['metadata']['source_kind']=='figure' for s in sources)


def test_failed_embedding_keeps_source_unindexed_and_allows_explicit_retry(automatic):
    client,app,wire=automatic
    wire.mode='http_error'
    cid,document=source(client)
    failed=await_job(client,document['index_job']['job_id'])
    assert failed['status']=='failed'
    doc=listing(client,cid)
    assert doc['status']=='parsed' and not doc['index_current']
    assert doc['index_error']==failed['error']
    assert all(chunk['vector'] is None for chunk in app.state.store.document_chunks(document['id']))
    assert len(app.state.store.all("SELECT id FROM jobs WHERE kind='index'"))==1
    wire.mode='valid'
    assert done(client,client.post(f"/api/documents/{document['id']}/index"))['status']=='succeeded'
    assert listing(client,cid)['index_current'] and not listing(client,cid)['index_error']


def test_partial_figure_failure_does_not_prevent_text_indexing(automatic_figures,monkeypatch):
    client,app,wire=automatic_figures
    async def fail_figure(*args,**kwargs):raise ValueError('Fixture vision failure')
    monkeypatch.setattr(app.state.pipeline.providers,'describe_image',fail_figure)
    cid,did,parsed=upload(client)
    figures=await_job(client,parsed['result']['figures_job']['job_id'])
    assert figures['result']['partial_failure'] is True
    indexed=await_job(client,figures['result']['index_job']['job_id'])
    assert indexed['status']=='succeeded'
    doc=listing(client,cid)
    assert doc['index_current'] and doc['figures'][0]['status']=='failed'
    assert '部分图片' in figures['result']['message']


def test_reparse_rebuilds_text_and_figure_indexes_automatically(automatic_figures):
    client,app,wire=automatic_figures
    cid,did,parsed=upload(client)
    figures=await_job(client,parsed['result']['figures_job']['job_id'])
    assert await_job(client,figures['result']['index_job']['job_id'])['status']=='succeeded'
    parsed=await_job(client,client.post(f'/api/documents/{did}/parse',json={'tier':'standard','images':True}).json()['job_id'])
    figures=await_job(client,parsed['result']['figures_job']['job_id'])
    assert await_job(client,figures['result']['index_job']['job_id'])['status']=='succeeded'
    assert listing(client,cid)['index_current'] and wire.embeddings==4


def test_automatic_index_job_is_private_to_the_uploading_account(automatic):
    client,app,wire=automatic
    cid,document=source(client)
    jid=document['index_job']['job_id']
    assert await_job(client,jid)['status']=='succeeded'
    other=TestClient(app);other.portal=client.portal
    try:
        authenticate(other,'other-auto-index@example.test')
        before=wire.calls
        assert other.get('/api/jobs/'+jid).status_code==404
        assert other.get('/api/jobs').json()==[]
        assert other.get('/api/documents',params={'course_id':cid}).status_code==404
        assert other.post('/api/documents',data={'course_id':cid},files={'file':('foreign.md',b'No access.')}).status_code==404
        assert wire.calls==before
    finally:
        other.close();other.portal=None


def test_duplicate_upload_reuses_pending_index_and_does_not_reembed_ready_source(automatic,monkeypatch):
    client,app,wire=automatic
    with monkeypatch.context() as paused:
        paused.setattr(app.state.pipeline,'enqueue',lambda jid:None)
        cid,document=source(client)
        duplicate=client.post('/api/documents',data={'course_id':cid},files={'file':('same.md',b'A stack removes the most recently added item first.')}).json()
        assert duplicate['duplicate'] and duplicate['id']==document['id']
        assert duplicate['index_job']==document['index_job']
        assert len(app.state.store.all("SELECT id FROM jobs WHERE kind='index'"))==1
        client.portal.call(app.state.pipeline.run,document['index_job']['job_id'])
    assert listing(client,cid)['index_current']
    duplicate=client.post('/api/documents',data={'course_id':cid},files={'file':('same.md',b'A stack removes the most recently added item first.')}).json()
    assert duplicate['duplicate'] and 'index_job' not in duplicate
    assert wire.calls==1


def test_full_queue_retains_upload_and_reports_index_deferred(automatic,monkeypatch):
    client,app,wire=automatic
    app.state.store.max_pending_jobs_per_account=1
    monkeypatch.setattr(app.state.pipeline,'enqueue',lambda jid:None)
    source(client,text='Blocking queued fixture index.')
    cid,document=source(client,text='The second source must be retained when the queue is full.')
    assert document['index_deferred'] and 'index_job' not in document
    assert '队列已满' in document['message']
    assert listing(client,cid)['status']=='parsed' and not listing(client,cid)['index_current']
    assert client.get(f"/api/documents/{document['id']}/source").status_code==200
    assert wire.calls==0


def test_unconfigured_embedding_retains_source_without_creating_a_doomed_job(automatic):
    client,app,wire=automatic
    app.state.settings.embedding=Endpoint(path='/embeddings')
    cid,document=source(client)
    assert document['index_deferred'] and '配置嵌入模型' in document['message']
    assert not listing(client,cid)['index_current'] and wire.calls==0
    assert app.state.store.all("SELECT id FROM jobs WHERE kind='index'")==[]
