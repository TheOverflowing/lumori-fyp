"""Real routes, workers and revision checks with isolated model responses."""
import asyncio
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
from test_ai_review_routes import ReviewWire, wait_job
from test_workflow import authenticate, done, request, seed


class ChatWire(ReviewWire):
    def __init__(self):
        super().__init__()
        self.plan = {'action': 'answer', 'text': 'The saved source supports using retrieval as reference.',
                     'slot_id': 'q2', 'instruction': '', 'difficulty': None}
        self.chat_calls = []
        self.chat_started, self.release_chat = Event(), Event()
        self.release_chat.set()
        self.chat_failure = False
        self.author_calls = 0

    async def __call__(self, request):
        contract = json.loads(json.loads(request.content)['messages'][1]['content']) if request.url.path.endswith('/chat/completions') else {}
        if contract.get('task') == 'review_chat':
            self.chat_calls.append(deepcopy(contract))
            self.chat_started.set()
            deadline = time.monotonic() + 8
            while not self.release_chat.is_set():
                assert time.monotonic() < deadline
                await asyncio.sleep(.002)
            if self.chat_failure:
                return httpx.Response(503, text='Synthetic upstream failure')
            return self.response(self.plan)
        if contract.get('task') == 'agent_author' and contract['revision']['mode'] == 'rewrite':
            self.author_calls += 1
            question = deepcopy(contract['revision']['original_question'])
            question.update(slot_id='q1', stem=question['stem'] + ' Use this revised scenario.')
            return self.response({'title': 'Updated question', 'evidence_sufficient': True,
                'questions': [question], 'sections': contract['revision']['immutable_context']})
        return await super().__call__(request)


@pytest.fixture
def chat_rig(tmp_path):
    settings = Settings(data_dir=tmp_path, workers=2, exploration_enabled=False)
    for capability, path in [('text', '/chat/completions'), ('embedding', '/embeddings')]:
        setattr(settings, capability, Endpoint('https://test.invalid/v1', 'test-key-not-real', 'fixture-model', path))
    wire = ChatWire()
    app = create_app(settings, lambda config, store: ApiProviders(config, store,
        httpx.AsyncClient(transport=httpx.MockTransport(wire))))
    with TestClient(app) as client:
        authenticate(client)
        course, _ = seed(client)
        body = request(course); body['count'] = 3
        job = done(client, client.post('/api/generations', json=body))
        assert job['status'] == 'succeeded', job
        cid = job['result']['content_id']
        try:
            yield client, app, wire, cid
        finally:
            wire.release_chat.set()


def send(rig, *, version=1, text='Why does retrieval help?', key='chat-message-one', slot='q2', auto_review=False):
    client, _, _, cid = rig
    return client.post(f'/api/contents/{cid}/chat', json={'version': version, 'message': text,
        'slot_id': slot, 'request_key': key, 'auto_review': auto_review})


def history(rig):
    return rig[0].get(f'/api/contents/{rig[3]}/chat').json()


def edit(rig, mode='rewrite', **kwargs):
    rig[2].plan.update(action=mode, text='Updated the requested question.', instruction='Use a revised concrete scenario.')
    response = send(rig, text='Please edit question 2.', **kwargs)
    job = done(rig[0], response)
    assert job['status'] == 'succeeded', job
    return response, job


def test_answer_and_clarification_are_persistent_readonly_turns(chat_rig):
    c, app, wire, cid = chat_rig
    before = c.get(f'/api/contents/{cid}').json()
    response = send(chat_rig, auto_review=True)
    job = done(c, response)
    assert job['status'] == 'succeeded', job
    assert job['result']['modified'] is False
    assert c.get(f'/api/contents/{cid}').json()['asset'] == before['asset']
    assert history(chat_rig)['version'] == 1
    assert not wire.review_calls
    wire.plan.update(action='clarify', text='Which question should change?', slot_id=None)
    assert done(c, send(chat_rig, key='chat-message-two', text='Can we change the question?', slot=None))['status'] == 'succeeded'
    messages = history(chat_rig)['messages']
    assert [m['role'] for m in messages] == ['user', 'assistant', 'user', 'assistant']
    assert messages[-1]['action'] == 'clarify'
    assert wire.chat_calls[-1]['history'][1]['text'] == messages[1]['text']
    assert [(x['id'], x['text']) for x in wire.chat_calls[-1]['sources']] == [(x['id'], x['text']) for x in before['sources']]
    assert [q['slot_id'] for q in wire.chat_calls[0]['asset']['questions']] == ['q2']
    assert [q['slot_id'] for q in wire.chat_calls[0]['question_index']] == ['q1', 'q2', 'q3']
    assert not app.state.store.one('SELECT 1 FROM revisions WHERE content_id=? AND version>1', (cid,))


def test_rewrite_saves_actual_diff_new_draft_and_followup_context(chat_rig):
    c, app, wire, cid = chat_rig
    before = c.get(f'/api/contents/{cid}').json()
    assert c.post(f'/api/contents/{cid}/review', json={'version': 1, 'action': 'approve'}).status_code == 200
    response, job = edit(chat_rig)
    after = c.get(f'/api/contents/{cid}').json()
    assert after['version'] == 2 and after['status'] == 'draft' and after['approval'] is None
    assert after['asset']['questions'][0] == before['asset']['questions'][0]
    assert after['asset']['questions'][2] == before['asset']['questions'][2]
    assert after['asset']['sections'] == before['asset']['sections']
    message = history(chat_rig)['messages'][-1]
    assert message['slot_id'] == 'q2' and message['can_undo']
    assert all(change['field'] != 'difficulty_design' for change in message['changes'])
    assert send(chat_rig, text='Please edit question 2.').json()['job_id'] == response.json()['job_id']
    assert c.get(f'/api/contents/{cid}').json()['version'] == 2
    assert any(change['field'] == 'stem' for change in message['changes'])
    assert app.state.store.one('SELECT details FROM review_chat_messages WHERE id=?', (message['id'],))
    assert c.get('/api/jobs/' + job['id']).json()['content_id'] == cid
    assert c.get('/api/jobs/' + job['id']).json()['progress']['resumable'] is False
    wire.plan.update(action='explanation', instruction='Keep the same target and clarify its explanation.')
    follow = done(c, send(chat_rig, version=2, text='Now explain that more clearly.', key='chat-followup-two', slot=None))
    assert follow['status'] == 'succeeded', follow
    final = c.get(f'/api/contents/{cid}').json()
    assert final['version'] == 3
    before_q, final_q = deepcopy(after['asset']['questions'][1]), deepcopy(final['asset']['questions'][1])
    assert before_q.pop('explanation') != final_q.pop('explanation')
    assert before_q == final_q
    assert wire.chat_calls[-1]['history'][-1]['slot_id'] == 'q2'
    assert wire.chat_calls[-1]['history'][-1]['instruction'] == 'Use a revised concrete scenario.'
    assert history(chat_rig)['messages'][1]['can_undo'] is False


def test_undo_restores_complete_snapshot_as_new_draft_and_is_idempotent(chat_rig):
    c, app, wire, cid = chat_rig
    before = c.get(f'/api/contents/{cid}').json()
    original_config = app.state.store.one('SELECT config FROM contents WHERE id=?', (cid,))['config']
    edit(chat_rig)
    message = history(chat_rig)['messages'][-1]
    body = {'version': 2, 'message_id': message['id'], 'request_key': 'undo-message-one'}
    response = c.post(f'/api/contents/{cid}/chat/undo', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['version'] == 3
    after = c.get(f'/api/contents/{cid}').json()
    assert after['asset'] == before['asset'] and after['status'] == 'draft'
    assert json.loads(app.state.store.one('SELECT config FROM contents WHERE id=?', (cid,))['config']) == json.loads(original_config)
    assert c.post(f'/api/contents/{cid}/chat/undo', json=body).json() == response.json()
    assert len(app.state.store.all('SELECT * FROM revisions WHERE content_id=?', (cid,))) == 3
    assert history(chat_rig)['messages'][-1]['action'] == 'undo'
    assert history(chat_rig)['messages'][1]['can_undo'] is False
    body['request_key'] = 'undo-message-two'; body['version'] = 3
    assert c.post(f'/api/contents/{cid}/chat/undo', json=body).status_code == 409


def test_undo_does_not_replace_later_manual_edits(chat_rig):
    c, _, _, cid = chat_rig
    edit(chat_rig)
    message = history(chat_rig)['messages'][-1]
    asset = c.get(f'/api/contents/{cid}').json()['asset']; asset['title'] = 'Teacher title'
    assert c.post(f'/api/contents/{cid}/review', json={'version': 2, 'action': 'save', 'asset': asset}).status_code == 200
    response = c.post(f'/api/contents/{cid}/chat/undo', json={'version': 3, 'message_id': message['id'], 'request_key': 'undo-after-manual'})
    assert response.status_code == 409
    assert c.get(f'/api/contents/{cid}').json()['asset']['title'] == 'Teacher title'


def test_duplicate_and_single_active_turn_and_stale_version(chat_rig):
    c, _, wire, cid = chat_rig
    wire.release_chat.clear()
    response = send(chat_rig)
    assert response.status_code == 202
    assert wire.chat_started.wait(3)
    assert history(chat_rig)['active_job_id'] == response.json()['job_id']
    assert send(chat_rig).json()['job_id'] == response.json()['job_id']
    assert send(chat_rig, key='other-active-message').status_code == 409
    assert send(chat_rig, text='different request same key').status_code == 409
    wire.release_chat.set()
    assert done(c, response)['status'] == 'succeeded'
    assert len(wire.chat_calls) == 1 and len(history(chat_rig)['messages']) == 2
    assert send(chat_rig, version=9, key='stale-chat-message').status_code == 409


def test_version_change_during_planning_preserves_teacher_edit(chat_rig):
    c, _, wire, cid = chat_rig
    wire.plan.update(action='rewrite', instruction='Rewrite the requested question.')
    wire.release_chat.clear()
    response = send(chat_rig)
    assert wire.chat_started.wait(3)
    asset = c.get(f'/api/contents/{cid}').json()['asset']; asset['title'] = 'Manual during chat'
    assert c.post(f'/api/contents/{cid}/review', json={'version': 1, 'action': 'save', 'asset': asset}).status_code == 200
    wire.release_chat.set()
    assert done(c, response)['status'] == 'failed'
    after = c.get(f'/api/contents/{cid}').json()
    assert after['version'] == 2 and after['asset'] == asset
    assert wire.author_calls == 0
    assert history(chat_rig)['messages'][-1]['status'] == 'failed'


def test_provider_failure_and_invalid_target_never_claim_or_apply_changes(chat_rig):
    c, _, wire, cid = chat_rig
    before = c.get(f'/api/contents/{cid}').json()['asset']
    wire.chat_failure = True
    assert done(c, send(chat_rig))['status'] == 'failed'
    failed = history(chat_rig)['messages'][-1]
    assert failed['status'] == 'failed' and not failed['can_undo']
    wire.chat_failure = False
    wire.plan.update(action='rewrite', slot_id='q99', instruction='Rewrite the question.')
    assert done(c, send(chat_rig, key='bad-target-message'))['status'] == 'failed'
    assert c.get(f'/api/contents/{cid}').json()['asset'] == before
    assert history(chat_rig)['version'] == 1


def test_chat_and_undo_are_account_isolated(chat_rig):
    c, app, _, cid = chat_rig
    edit(chat_rig)
    mid = history(chat_rig)['messages'][-1]['id']
    with another_client(app, c) as other:
        authenticate(other, 'chat-other@example.test')
        assert other.get(f'/api/contents/{cid}/chat').status_code == 404
        assert other.post(f'/api/contents/{cid}/chat', json={'version': 2, 'message': 'Change it.', 'request_key': 'other-chat-message'}).status_code == 404
        assert other.post(f'/api/contents/{cid}/chat/undo', json={'version': 2, 'message_id': mid, 'request_key': 'other-undo-message'}).status_code == 404


def test_only_successful_edit_can_trigger_requested_auto_review(chat_rig):
    c, _, wire, cid = chat_rig
    _, job = edit(chat_rig, auto_review=True)
    automatic = job['result']['automatic_review']
    reviewed = wait_job(c, automatic['job_id'])
    assert reviewed['status'] == 'succeeded', reviewed
    content = c.get(f'/api/contents/{cid}').json()
    assert content['version'] == 2 and content['approval']['method'] == 'ai'
    assert len(wire.review_calls) == 1


def test_cancelled_turn_never_edits_and_remains_in_history(chat_rig):
    c, _, wire, cid = chat_rig
    wire.release_chat.clear()
    wire.plan.update(action='rewrite', instruction='Rewrite this question.')
    response = send(chat_rig)
    assert wire.chat_started.wait(3)
    assert c.post('/api/jobs/' + response.json()['job_id'] + '/cancel').status_code == 200
    wire.release_chat.set()
    assert done(c, response)['status'] == 'cancelled'
    assert history(chat_rig)['messages'][-1]['status'] == 'cancelled'
    assert history(chat_rig)['version'] == 1 and wire.author_calls == 0


def test_context_budget_asks_for_question_without_spending_a_model_call(chat_rig):
    c, app, wire, cid = chat_rig
    from app.review_chat import planning_messages
    from app.store import dumps
    row = app.state.store.one('SELECT * FROM contents WHERE id=?', (cid,))
    payload = {'asset': json.loads(row['asset']), 'sources': json.loads(row['sources']),
        'base_version': 1, 'request': {'slot_id': 'q2', 'message': 'Why does retrieval help?'}, 'history': []}
    selected_size = len(dumps(planning_messages(app.state.pipeline, payload, None)))
    app.state.settings.agent_context_chars = selected_size + 600
    result = done(c, send(chat_rig, slot=None))
    assert result['status'] == 'failed' and '选择' in result['error']
    assert not wire.chat_calls
    response = send(chat_rig, key='selected-after-large')
    assert done(c, response)['status'] == 'succeeded'
    assert history(chat_rig)['version'] == 1
