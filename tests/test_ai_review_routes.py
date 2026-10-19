"""AI review API contracts with synthetic judgments and no external model calls.

These tests verify ownership, versioning, state transitions, and request costs;
predetermined model responses are not evidence of real review quality.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from threading import Event
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from app.config import Endpoint, Settings
from app.main import create_app
from app.providers import ApiProviders
from test_account_isolation import another_client
from test_workflow import Wire, authenticate, done, generated, request, seed


CHECKS = ('correctness', 'groundedness', 'answerability', 'clarity', 'objective_alignment')


def synthetic_report(instruction, status='pass'):
    sources = {source['id']: source['text'] for source in instruction['sources']}
    report = {
        'summary': 'Synthetic API fixture judgment; not a teacher or empirical quality review.',
        'checks': [{'key': key, 'status': status, 'rationale': 'Predetermined fixture check.'} for key in CHECKS],
        'items': [{
            'id': unit['id'], 'status': status, 'rationale': 'Predetermined fixture unit check.',
            'source_ids': unit['citation_ids'],
            'evidence': [{'source_id': sid, 'quote': sources[sid][:80]} for sid in unit['citation_ids']],
        } for unit in instruction['units']],
        'findings': [],
    }
    if status != 'pass':
        report['findings'] = [{
            'unit_id': unit['id'], 'severity': 'error' if status == 'fail' else 'uncertain',
            'quote': unit['content'].get('text') or unit['content']['stem'],
            'message': 'Synthetic unsupported claim.' if status == 'fail' else 'Synthetic unresolved evidence.',
            'suggestion': 'Compare this unit with its saved course source.',
            'source_ids': unit['citation_ids'],
        } for unit in instruction['units']]
    return report


class ReviewWire(Wire):
    def __init__(self):
        self.review_mode = 'pass'
        self.review_calls = []
        self.release_review = Event()
        self.release_review.set()
        self.review_started = Event()

    @staticmethod
    def response(value):
        return httpx.Response(200, json={'choices': [
            {'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]})

    async def __call__(self, request):
        instruction = (json.loads(json.loads(request.content)['messages'][1]['content'])
                       if request.url.path.endswith('/chat/completions') else {})
        if instruction.get('task') == 'content_ai_review':
            self.calls += 1
            assert request.headers['authorization'] == 'Bearer test-key-not-real'
            self.review_calls.append(deepcopy(instruction))
            self.review_started.set()
            deadline = time.monotonic() + 5
            while not self.release_review.is_set():
                assert time.monotonic() < deadline, 'Fixture review gate was not released.'
                await asyncio.sleep(.002)
            if self.review_mode == 'transport_error':
                return httpx.Response(503, text='Isolated review transport failure')
            if self.review_mode == 'malformed':
                return self.response({'summary': 'Intentionally incomplete fixture'})
            return self.response(synthetic_report(instruction, self.review_mode))
        # An explanation-only edit exercises the real question-revision worker
        # while each role's answer stays predetermined at the transport boundary.
        if instruction.get('task') == 'agent_author':
            self.calls += 1
            assert instruction['revision']['mode'] == 'explanation'
            return self.response({'explanation': '检索只提供课程参考资料，仍须检查原文是否支持答案。'})
        if instruction.get('task') in ('agent_solve', 'agent_review'):
            self.calls += 1
            question = instruction['question']
            properties = instruction['schema']['properties']
            quality = {}
            if 'question_checks' in properties:
                quality['question_checks'] = {'condition_issues': [], 'option_checks': [
                    {'label': chr(65+i), 'verdict': 'correct' if i == 0 else 'incorrect',
                     'reason': 'Synthetic option check.'} for i, _ in enumerate(question['options'])]}
            if 'explanation_issues' in properties:
                quality['explanation_issues'] = []
            if instruction['task'] == 'agent_solve':
                return self.response({
                    'answerable': True, 'ambiguity_free': True, 'assessed_difficulty': 'medium',
                    'confidence': 'high', 'answer': 'A', 'explanation': 'Use the cited course evidence.',
                    'requires_calculation': False, 'tool_requests': [], **quality,
                })
            return self.response({
                'answer_correct': True, 'explanation_correct': True, 'source_supported': True,
                'ambiguity_free': True, 'tool_inputs_match_question': True, 'calculations_verified': True,
                'distinct_from_previous': True, 'confidence': 'high', 'issues': [],
                'feedback': 'Predetermined fixture check.', 'revision_instructions_followed': True,
                'original_learning_focus_preserved': True, **quality,
            })
        return super().__call__(request)


@pytest.fixture
def review_rig(tmp_path):
    settings = Settings(data_dir=tmp_path, workers=2, exploration_enabled=False)
    for capability, path in [('text', '/chat/completions'), ('embedding', '/embeddings')]:
        setattr(settings, capability, Endpoint('https://test.invalid/v1', 'test-key-not-real', 'fixture-model', path))
    wire = ReviewWire()
    app = create_app(settings, lambda config, store: ApiProviders(
        config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire))))
    with TestClient(app) as client:
        authenticate(client)
        try:
            yield client, app, wire
        finally:
            wire.release_review.set()


def material(rig):
    client, _, _ = rig
    course, _ = seed(client)
    return generated(client, course), course


def start_review(client, cid, version=1, key='manual-ai-review-one'):
    response = client.post('/api/contents/' + cid + '/ai-review',
                           json={'version': version, 'request_key': key})
    assert response.status_code == 202, response.text
    return response


def wait_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] not in ('queued', 'running'):
            return job
        time.sleep(.005)
    pytest.fail('The isolated job did not settle.')


def automatic_review(client, app, cid, version):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        jobs = app.state.store.all("SELECT * FROM jobs WHERE kind='review_content'")
        matching = [job for job in jobs if json.loads(job['payload'])['content_id'] == cid
                    and json.loads(job['payload'])['version'] == version]
        if matching:
            assert len(matching) == 1
            return wait_job(client, matching[0]['id'])
        time.sleep(.005)
    pytest.fail('Automatic review was not queued.')


def test_manual_ai_review_approves_exact_version_and_exposes_ai_provenance(review_rig):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    assert client.get('/api/learn/' + cid).status_code == 404
    before = client.get('/api/contents/' + cid).json()
    assert before['ai_review'] is None and before['approval'] is None
    job = done(client, start_review(client, cid))
    assert job['status'] == 'succeeded', job
    assert job['result']['decision'] == 'approve' and job['result']['applied'] is True
    content = client.get('/api/contents/' + cid).json()
    assert content['status'] == 'approved' and content['version'] == 1
    assert content['approval']['method'] == 'ai'
    assert content['approval']['review_job_id'] == job['id']
    assert content['ai_review']['decision'] == 'approve'
    assert content['ai_review']['model'] == 'fixture-model'
    assert content['ai_review']['findings'] == []
    assert client.get('/api/learn/' + cid).status_code == 200
    listed = next(item for item in client.get('/api/contents').json() if item['id'] == cid)
    assert listed['approval_method'] == 'ai'
    assert len(wire.review_calls) == 1
    assert {unit['id'] for unit in wire.review_calls[0]['units']} == {'section:1', 'question:1'}
    exported = client.get('/api/contents/' + cid + '/evidence')
    assert exported.status_code == 200 and 'attachment' in exported.headers['content-disposition']
    bundle = exported.json()
    assert bundle['version'] == 1 and bundle['status'] == 'approved'
    assert bundle['approval'] == content['approval']
    assert bundle['ai_review'] == content['ai_review']
    assert bundle['ai_review']['version'] == bundle['version']
    assert bundle['ai_review']['job_id'] == bundle['approval']['review_job_id'] == job['id']
    assert bundle['ai_review_calls'] == app.state.store.calls_for_job(job['id'])
    assert len(bundle['ai_review_calls']) == 1
    assert bundle['ai_review_calls'][0]['capability'] == 'text'
    assert {call['capability'] for call in bundle['generation_calls']} == {'text', 'embedding'}
    assert 'AI review is a model judgment, not teacher review or proof of correctness.' in bundle['limitations']
    assert 'test-key-not-real' not in exported.text


@pytest.mark.parametrize('mode,decision', [('fail', 'revision_required'), ('uncertain', 'human_review')])
def test_failed_or_uncertain_judgment_leaves_draft_with_actionable_findings(review_rig, mode, decision):
    client, _, wire = review_rig
    cid, _ = material(review_rig)
    wire.review_mode = mode
    job = done(client, start_review(client, cid))
    assert job['status'] == 'succeeded', job
    content = client.get('/api/contents/' + cid).json()
    assert content['status'] == 'draft' and content['approval'] is None
    assert content['ai_review']['decision'] == decision and content['ai_review']['findings']
    assert content['ai_review']['applied'] is False
    assert client.get('/api/learn/' + cid).status_code == 404
    assert next(row for row in client.get('/api/contents').json() if row['id'] == cid)['approval_method'] is None


@pytest.mark.parametrize('mode', ['transport_error', 'malformed'])
def test_broken_ai_review_does_not_publish_or_lose_the_material(review_rig, mode):
    client, _, wire = review_rig
    cid, _ = material(review_rig)
    before = client.get('/api/contents/' + cid).json()
    wire.review_mode = mode
    job = done(client, start_review(client, cid))
    assert job['status'] == 'failed'
    content = client.get('/api/contents/' + cid).json()
    assert content['asset'] == before['asset'] and content['version'] == before['version']
    assert content['status'] == 'draft' and content['approval'] is None
    assert content['ai_review']['status'] == 'failed'
    assert client.get('/api/learn/' + cid).status_code == 404


def test_review_access_rejects_anonymous_other_account_and_missing_csrf(review_rig):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    path = '/api/contents/' + cid + '/ai-review'
    payload = {'version': 1, 'request_key': 'private-review-request'}
    with another_client(app, client) as stranger:
        assert stranger.post(path, json=payload).status_code == 401
        authenticate(stranger, email='other-review@example.test')
        assert stranger.post(path, json=payload).status_code == 404
        assert stranger.get('/api/contents/' + cid).status_code == 404
    with another_client(app, client) as no_csrf:
        no_csrf.cookies.update(client.cookies)
        assert no_csrf.post(path, json=payload).status_code == 403
    assert wire.review_calls == []


def test_completed_review_key_replays_after_approval_and_a_later_manual_edit(review_rig):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    first = start_review(client, cid)
    job = done(client, first)
    assert job['status'] == 'succeeded'
    replay = start_review(client, cid)
    assert replay.json()['job_id'] == job['id'] and replay.json()['reused'] is True
    content = client.get('/api/contents/' + cid).json()
    edited = content['asset'] | {'title': 'New version requires a separate review'}
    saved = client.post('/api/contents/' + cid + '/review', json={'version': 1, 'action': 'save', 'asset': edited})
    assert saved.status_code == 200, saved.text
    app.state.settings.text = Endpoint()
    historical = start_review(client, cid)
    assert historical.json()['job_id'] == job['id'] and historical.json()['reused'] is True
    assert len(wire.review_calls) == 1
    assert client.post('/api/contents/' + cid + '/ai-review',
                       json={'version': 2, 'request_key': 'manual-ai-review-one'}).status_code == 409
    latest = client.get('/api/contents/' + cid).json()
    assert latest['version'] == 2 and latest['status'] == 'draft'
    assert latest['approval'] is None and latest['ai_review'] is None
    assert client.get('/api/learn/' + cid).status_code == 404
    exported = client.get('/api/contents/' + cid + '/evidence')
    assert exported.status_code == 200
    bundle = exported.json()
    assert bundle['version'] == 2 and bundle['status'] == 'draft' and bundle['asset'] == edited
    assert bundle['approval'] is None and bundle['ai_review'] is None
    assert bundle['ai_review_calls'] == [], 'The old review must not appear as evidence for the edited version.'
    assert [revision['version'] for revision in bundle['revisions']] == [1, 2]
    historical_report = client.get('/api/jobs/' + job['id'] + '/evidence').json()['evidence']['report']
    assert historical_report['version'] == 1 and historical_report['decision'] == 'approve'
    assert historical_report['content_id'] == cid, 'The old review remains auditable at its original version.'


def test_overlapping_review_requests_deduplicate_active_work_and_keep_both_keys_replayable(review_rig):
    client, _, wire = review_rig
    cid, _ = material(review_rig)
    wire.release_review.clear()
    keys = ('overlap-review-one', 'overlap-review-two')
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(start_review, client, cid, 1, key) for key in keys]
            replies = [future.result(timeout=3) for future in futures]
        assert replies[0].json()['job_id'] == replies[1].json()['job_id']
        assert wire.review_started.wait(2)
    finally:
        wire.release_review.set()
    job = wait_job(client, replies[0].json()['job_id'])
    assert job['status'] == 'succeeded', job
    for key in keys:
        replay = start_review(client, cid, key=key)
        assert replay.json()['job_id'] == job['id'] and replay.json()['reused'] is True
    assert len(wire.review_calls) == 1


def test_manual_confirmation_replaces_ai_approval_provenance_for_same_version(review_rig):
    client, _, _ = review_rig
    cid, _ = material(review_rig)
    assert done(client, start_review(client, cid))['status'] == 'succeeded'
    response = client.post('/api/contents/' + cid + '/review', json={'version': 1, 'action': 'approve'})
    assert response.status_code == 200, response.text
    content = client.get('/api/contents/' + cid).json()
    assert content['approval']['method'] == 'manual'
    assert content['approval']['review_job_id'] is None
    assert content['ai_review']['decision'] == 'approve', 'The model report remains as historical evidence.'
    assert next(row for row in client.get('/api/contents').json() if row['id'] == cid)['approval_method'] == 'manual'


def test_default_generation_and_manual_save_do_not_run_automatic_review(review_rig):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    content = client.get('/api/contents/' + cid).json()
    response = client.post('/api/contents/' + cid + '/review', json={
        'version': 1, 'action': 'save', 'asset': content['asset'] | {'title': 'Ordinary manual edit'}})
    assert response.status_code == 200, response.text
    assert wire.review_calls == []
    assert app.state.store.all("SELECT id FROM jobs WHERE kind='review_content'") == []


@pytest.mark.parametrize('mode,review_status,content_status', [
    ('pass', 'succeeded', 'approved'), ('transport_error', 'failed', 'draft')])
def test_automatic_generation_review_is_separate_and_cannot_fail_saved_generation(
        review_rig, mode, review_status, content_status):
    client, app, wire = review_rig
    course, _ = seed(client)
    wire.review_mode = mode
    generation = done(client, client.post('/api/generations',
        json=request(course, 'generate-with-auto-review') | {'auto_review': True}))
    assert generation['status'] == 'succeeded', generation
    cid = generation['result']['content_id']
    review = automatic_review(client, app, cid, 1)
    assert review['id'] != generation['id'] and review['kind'] == 'review_content'
    assert review['status'] == review_status, review
    assert client.get('/api/jobs/' + generation['id']).json()['status'] == 'succeeded'
    assert client.get('/api/contents/' + cid).json()['status'] == content_status
    assert len(wire.review_calls) == 1


@pytest.mark.parametrize('mode,review_status,content_status', [
    ('pass', 'succeeded', 'approved'), ('transport_error', 'failed', 'draft')])
def test_opted_in_save_reviews_only_the_saved_version_and_keeps_edits_on_failure(
        review_rig, mode, review_status, content_status):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    content = client.get('/api/contents/' + cid).json()
    wire.review_mode = mode
    asset = content['asset'] | {'title': 'A deliberately saved second version'}
    response = client.post('/api/contents/' + cid + '/review', json={
        'version': 1, 'action': 'save', 'asset': asset, 'auto_review': True})
    assert response.status_code == 200 and response.json()['version'] == 2, response.text
    review = automatic_review(client, app, cid, 2)
    assert review['status'] == review_status, review
    saved = client.get('/api/contents/' + cid).json()
    assert saved['version'] == 2 and saved['asset'] == asset and saved['status'] == content_status
    assert saved['ai_review']['version'] == 2


@pytest.mark.parametrize('automatic', [False, True])
def test_single_question_edit_only_runs_whole_material_review_when_opted_in(review_rig, automatic):
    client, app, wire = review_rig
    cid, _ = material(review_rig)
    assert client.post('/api/contents/' + cid + '/review', json={'version': 1, 'action': 'approve'}).status_code == 200
    response = client.post('/api/contents/' + cid + '/questions/q1/revise', json={
        'version': 1, 'mode': 'explanation', 'instruction': 'Clarify the role of course evidence.',
        'request_key': 'revision-with-review-choice', 'auto_review': automatic})
    revision = done(client, response)
    assert revision['status'] == 'succeeded', revision
    if automatic:
        review = automatic_review(client, app, cid, 2)
        assert review['status'] == 'succeeded', review
    else:
        assert wire.review_calls == []
    content = client.get('/api/contents/' + cid).json()
    assert content['version'] == 2
    assert content['status'] == ('approved' if automatic else 'draft')
    if automatic:
        assert content['approval']['method'] == 'ai'
    else:
        assert content['approval'] is None
    assert content['asset']['questions'][0]['explanation'].startswith('检索只提供课程参考资料')


@pytest.mark.parametrize('operation', ['generate', 'save'])
def test_failure_to_schedule_automatic_review_is_visible_without_failing_saved_work(
        review_rig, monkeypatch, operation):
    from app import ai_review_jobs

    client, app, wire = review_rig
    cid, course = material(review_rig)

    def unavailable(*args, **kwargs):
        raise ValueError('Synthetic review queue unavailable; retry the review.')

    monkeypatch.setattr(ai_review_jobs, 'submit_review', unavailable)
    if operation == 'generate':
        generation = done(client, client.post('/api/generations',
            json=request(course, 'generate-with-schedule-failure') | {'auto_review': True}))
        assert generation['status'] == 'succeeded', generation
        cid, version = generation['result']['content_id'], 1
    else:
        before = client.get('/api/contents/' + cid).json()
        response = client.post('/api/contents/' + cid + '/review', json={
            'version': 1, 'action': 'save', 'asset': before['asset'], 'auto_review': True})
        assert response.status_code == 200, response.text
        version = 2
    # Worker completion may become visible just before its follow-up scheduling.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        content = client.get('/api/contents/' + cid).json()
        if content['ai_review']:
            break
        time.sleep(.005)
    assert content['version'] == version and content['status'] == 'draft'
    assert content['ai_review']['status'] == 'failed'
    assert 'Synthetic review queue unavailable' in content['ai_review']['error']
    assert content['approval'] is None and wire.review_calls == []
    assert app.state.store.all("SELECT id FROM jobs WHERE kind='review_content'") == []
