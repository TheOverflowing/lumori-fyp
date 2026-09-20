"""Offline controls for R8B information isolation and single-turn failure handling."""
import asyncio
import json
from collections import Counter
from types import SimpleNamespace

import pytest
import numpy as np
import httpx

from scripts import r8_clarification as r8
from scripts import r8_clarification_report as r8_report


def ok(result):
    return {'status': 'succeeded', 'result': result}


def test_public_input_drops_hidden_intent_and_evaluation_fields():
    row = {'text': 'How does this work?', 'language': 'en', 'family_id': 'hidden-target',
           'clarity': 'underspecified', 'requires_clarification': True,
           'intent_profile': 'secret intent', 'evidence': ['secret answer'],
           'canonical': 'secret standard query', 'style': 'colloquial'}
    assert r8.public_input(row) == {'query': row['text'], 'language': 'en'}


def test_keep_cannot_silently_rewrite():
    with pytest.raises(ValueError, match='keep_changed_query'):
        r8.validate({'action': 'keep', 'query': 'What is the worst-case complexity?',
                     'question': '', 'reason': 'Already clear.'}, 'selective',
                    {'query': 'Can this operation be slow?', 'language': 'en'})


@pytest.mark.parametrize('proposal', [
    {'action': 'clarify', 'query': 'A guess', 'question': 'Which structure?', 'reason': 'Missing referent.'},
    {'action': 'clarify', 'query': '', 'question': 'Which structure? Which operation?', 'reason': 'Two gaps.'},
    {'action': 'rewrite', 'query': 'How does the structure work?', 'question': 'Which one?', 'reason': 'Mixed actions.'},
])
def test_one_action_contract_rejects_ambiguous_or_multiple_operations(proposal):
    with pytest.raises(ValueError):
        r8.validate(proposal, 'selective', {'query': 'How does this work?', 'language': 'en'})


@pytest.mark.parametrize('quotes', [[], ['not present in the profile'], [''], 'not a list'])
def test_known_reply_requires_actual_profile_quotes(quotes):
    request = {'query': 'How does this work?', 'language': 'en', 'question': 'What do you know?',
               'intent_profile': 'The address width is 32 bits.'}
    with pytest.raises(ValueError):
        r8.validate({'unknown': False, 'answer': 'The address width is 32 bits.',
                     'support_quotes': quotes}, 'reply', request)


@pytest.mark.parametrize('language,expected', [('en', 'That is not specified.'), ('zh', '这点没有说明。')])
def test_unknown_reply_cannot_smuggle_an_unsubstantiated_answer(language, expected):
    request = {'query': 'How does this work?', 'language': language,
               'intent_profile': 'No address width was provided.'}
    proposal = {'unknown': True, 'answer': 'I guess the address width is 64 bits.', 'support_quotes': []}
    validated = r8.validate(proposal, 'reply', request)
    assert validated['unknown'] is True
    assert validated['answer'] == expected
    assert proposal['answer'] != expected  # No mutation of the archived model payload.


@pytest.mark.parametrize('role', ['normalize', 'selective', 'resolve'])
@pytest.mark.parametrize('changed', ['How are addresses represented?', 'How are 64-bit addresses represented?'])
def test_existing_numeric_conditions_cannot_be_removed_or_replaced(role, changed):
    request = {'query': 'How are 32-bit addresses represented?', 'language': 'en'}
    proposal = {'query': changed}
    if role == 'selective':
        proposal.update(action='rewrite', question='', reason='Normalize wording.')
    elif role == 'resolve':
        proposal.update(resolved=True, reason='The user clarified the representation.')
        request.update(question='Which representation?', answer='The representation already mentioned.')
    with pytest.raises(ValueError, match='numeric_condition_changed'):
        r8.validate(proposal, role, request)


def test_only_actual_reply_can_authorize_a_new_number():
    request = {'query': 'How are addresses represented?', 'language': 'en',
               'question': 'What address width?', 'answer': 'The addresses are 32-bit.'}
    result = {'resolved': True, 'query': 'How are 32-bit addresses represented?', 'reason': 'User supplied width.'}
    assert r8.validate(result, 'resolve', request) == result
    with pytest.raises(ValueError, match='numeric_condition_changed'):
        r8.validate(dict(result, query='How are 64-bit addresses represented?'), 'resolve', request)


@pytest.mark.parametrize('before,after', [
    ('Why does index -1 work?', 'Why does index 1 work?'),
    ('What happens at x = +2?', 'What happens at x = -2?'),
    ('What happens at x = -0.5?', 'What happens at x = 0.5?'),
])
def test_numeric_guard_preserves_sign(before, after):
    with pytest.raises(ValueError, match='numeric_condition_changed'):
        r8.validate({'query': after}, 'normalize', {'query': before, 'language': 'en'})


def test_new_signed_numeric_condition_requires_actual_reply():
    request = {'query': 'How is the index interpreted?', 'language': 'en',
               'question': 'What index?', 'answer': 'The index is -1.'}
    proposal = {'resolved': True, 'query': 'How is index -1 interpreted?', 'reason': 'User supplied the index.'}
    assert r8.validate(proposal, 'resolve', request) == proposal
    with pytest.raises(ValueError, match='numeric_condition_changed'):
        r8.validate(dict(proposal, query='How is index 1 interpreted?'), 'resolve', request)


def run_fixture_interaction(tmp_path, monkeypatch, *, action='clarify', unknown=False,
                            resolved=True, failed_role=None):
    """Execute the real orchestration with a local model double; never open a socket."""
    qid = 'hidden-family:colloquial:underspecified'
    query = 'How does this operation use 32-bit addresses?'
    profile = 'PRIVATE_PROFILE_MARKER. The addresses belong to an array, not linked nodes.'
    r8.save(tmp_path / 'query-inputs.json', {qid: {'query': query, 'language': 'en'}})
    r8.save(tmp_path / 'profiles.json', {qid: profile})
    recorded = []
    closed = []
    route = {'action': action, 'query': '' if action == 'clarify' else query,
             'question': 'Are the addresses for an array or linked nodes?' if action == 'clarify' else '',
             'reason': 'The referent is absent.' if action == 'clarify' else 'The question is clear.'}
    responses = {
        'selective': route,
        'normalize': {'query': query},
        'reply': {'unknown': unknown, 'answer': 'The addresses belong to an array.',
                  'support_quotes': [] if unknown else ['The addresses belong to an array, not linked nodes.']},
        'resolve': {'resolved': resolved,
                    'query': 'How does this array operation use 32-bit addresses?' if resolved else '',
                    'reason': 'The reply established the referent.' if resolved else 'The operation remains unclear.'},
    }

    class NoNetworkRemote:
        def __init__(self, run):
            assert run == tmp_path

        async def call(self, cap, payload, validator):
            assert cap == 'text'
            role = next(k for k, prompt in r8.PROMPTS.items() if prompt == payload['messages'][0]['content'])
            request = json.loads(payload['messages'][1]['content'])
            recorded.append((role, request))
            if role == failed_role:
                return {'status': 'failed', 'error': 'offline fixture failure'}
            wire = {'choices': [{'message': {'content': json.dumps(responses[role])}}]}
            return ok(validator(wire))

        async def close(self):
            closed.append(True)

    monkeypatch.setattr(r8, 'verify', lambda run: None)
    monkeypatch.setattr(r8, 'Remote', NoNetworkRemote)
    monkeypatch.setattr(r8.r7, 'CAPS', dict(r8.r7.CAPS))
    asyncio.run(r8.interact(tmp_path))
    assert closed == [True]
    return qid, query, recorded, r8.load(tmp_path / 'effective-queries.json')


def test_workflow_keeps_private_profile_out_of_decision_and_resolution(tmp_path, monkeypatch):
    qid, query, recorded, effective = run_fixture_interaction(tmp_path, monkeypatch)
    assert [role for role, _ in recorded] == ['selective', 'normalize', 'reply', 'resolve']
    for role, request in recorded:
        allowed = {'query', 'language'}
        if role == 'reply':
            allowed |= {'question', 'intent_profile'}
        elif role == 'resolve':
            allowed |= {'question', 'answer'}
        assert set(request) == allowed
        if role != 'reply':
            assert 'PRIVATE_PROFILE_MARKER' not in json.dumps(request)
        assert qid not in json.dumps(request)  # No family/style/clarity identifier leakage.
    assert effective[qid + ':selective']['resolved'] is True
    assert effective[qid + ':selective']['asked'] is True
    assert effective[qid + ':original']['query'] == query
    assert effective[qid + ':normalize']['query'] == query


def test_unknown_reply_stops_without_inventing_resolution(tmp_path, monkeypatch):
    qid, query, recorded, effective = run_fixture_interaction(tmp_path, monkeypatch, unknown=True)
    assert [role for role, _ in recorded] == ['selective', 'normalize', 'reply']
    row = effective[qid + ':selective']
    assert row['query'] == query
    assert row['asked'] and row['unknown'] and row['fallback']
    assert not row['resolved'] and row['action'] == 'unresolved'
    assert len(effective) == 3


@pytest.mark.parametrize('failed_role', ['reply', 'resolve'])
def test_interaction_failures_remain_asked_unresolved_rows(tmp_path, monkeypatch, failed_role):
    qid, query, recorded, effective = run_fixture_interaction(tmp_path, monkeypatch, failed_role=failed_role)
    row = effective[qid + ':selective']
    assert row['query'] == query and row['asked'] and row['fallback']
    assert not row['resolved'] and row['action'] == 'unresolved'
    assert len(effective) == 3
    if failed_role == 'reply':
        assert all(role != 'resolve' for role, _ in recorded)


def test_resolution_can_decline_even_after_a_supported_reply(tmp_path, monkeypatch):
    qid, query, _, effective = run_fixture_interaction(tmp_path, monkeypatch, resolved=False)
    row = effective[qid + ':selective']
    assert row['query'] == query and row['asked'] and row['fallback']
    assert not row['resolved'] and row['action'] == 'unresolved'


@pytest.mark.parametrize('action', ['keep', 'rewrite'])
def test_nonclarifying_action_never_reads_simulated_reply(tmp_path, monkeypatch, action):
    qid, _, recorded, effective = run_fixture_interaction(tmp_path, monkeypatch, action=action)
    assert [role for role, _ in recorded] == ['selective', 'normalize']
    assert not effective[qid + ':selective']['asked']


def test_failed_router_is_fallback_not_a_keep_success(tmp_path, monkeypatch):
    qid, query, recorded, effective = run_fixture_interaction(tmp_path, monkeypatch, failed_role='selective')
    row = effective[qid + ':selective']
    assert row['action'] == 'fallback' and row['fallback'] and row['query'] == query
    assert not row['asked'] and not row['resolved']
    assert [role for role, _ in recorded] == ['selective', 'normalize']


def test_dataset_grid_and_evidence_offsets_are_complete():
    data = r8.load(r8.PACK / 'dataset.json')
    assert len(data['families']) == 8 and len(data['queries']) == 64
    assert len({q['id'] for q in data['queries']}) == 64
    assert Counter(q['clarity'] for q in data['queries']) == {'sufficient': 32, 'underspecified': 32}
    assert Counter(q['language'] for q in data['queries']) == {'en': 32, 'zh': 32}
    assert Counter(q['style'] for q in data['queries']) == {'formal': 32, 'colloquial': 32}
    docs = {d['id']: d for d in r8.load(r8.SOURCE / 'dataset.json')['documents']}
    for family in data['families']:
        rows = [q for q in data['queries'] if q['family_id'] == family['id']]
        assert {(q['language'], q['style'], q['clarity']) for q in rows} == {
            (language, style, clarity) for language in ('en', 'zh')
            for style in ('formal', 'colloquial') for clarity in ('sufficient', 'underspecified')}
        assert set(family['intent_profiles']) == {'en', 'zh'}
        assert family['evidence']
        for span in family['evidence']:
            assert docs[span['document_id']]['text'][span['start']:span['end']] == span['text']
    assert all(q['requires_clarification'] == (q['clarity'] == 'underspecified') for q in data['queries'])


def ranking_fixture(tmp_path, monkeypatch):
    """One real local ranking with archived, fabricated vectors and no provider."""
    request = {'query': 'How does array indexing work?', 'language': 'en'}
    interactions = {'q:normalize': ok({'query': request['query']}),
                    'q:selective': ok({'action': 'keep', 'query': request['query'],
                                      'question': '', 'reason': 'Clear.'})}
    effective = r8.effective_queries({'q': request}, interactions)
    encoded = r8.query_input(request['query'], True)
    digest = r8.sha(encoded.encode())
    endpoint = {'model': 'offline-vector-fixture', 'signature': 'fixture', 'base_url': 'https://unused.invalid',
                'path': '/unused'}
    body = {'input': [encoded], 'encoding_format': 'float', 'model': endpoint['model']}
    logical = r8.sha(r8.canonical({'capability': 'embedding', 'endpoint': endpoint, 'body': body}))
    vector = [1.0] + [0.0] * 4095
    response_path = 'responses/offline-embedding.json'
    record = {'status': 'succeeded', 'logical_key': logical, 'capability': 'embedding',
              'response_file': response_path, 'vector_index': 0}
    r8.save(tmp_path / response_path, dict(record, result=[vector]))
    r8.save(tmp_path / 'query-inputs.json', {'q': request})
    r8.save(tmp_path / 'interactions.json', interactions)
    r8.save(tmp_path / 'effective-queries.json', effective)
    r8.save(tmp_path / 'embedding-inputs.json', {'inputs': {digest: encoded},
                                               'mapping': {k: digest for k in effective}})
    r8.save(tmp_path / 'embeddings.json', {digest: record})
    r8.save(tmp_path / 'embedding-response-hashes.json', {response_path: r8.sha((tmp_path / response_path).read_bytes())})
    r8.save(tmp_path / 'providers.json', {'embedding': endpoint})
    title_text = 'Arrays\nArray indexing computes an offset.'
    content = 'Array indexing computes an offset.'
    r8.save(tmp_path / 'chunks.json', [{'id': 'c', 'parent_id': 'd', 'title_text': title_text,
                                      'source_start': 0, 'source_end': len(content), 'text': content}])
    np.savez(tmp_path / 'document-vectors.npz', keys=np.array([r8.sha(title_text.encode())]),
             vectors=np.array([vector]))
    r8.save(tmp_path / 'gold-spans.json', {'q': [{'parent_id': 'd', 'start': 0, 'end': len(content), 'text': content}]})
    r8.save(tmp_path / 'dataset.json', {'queries': [{'id': 'q', 'family_id': 'f', 'language': 'en',
                                                   'style': 'formal', 'clarity': 'sufficient',
                                                   'split': 'test', 'component': 'f'}]})
    monkeypatch.setattr(r8, 'verify', lambda run: None)
    return digest, response_path


def test_bound_embedding_fixture_replays_all_policy_rows(tmp_path, monkeypatch):
    ranking_fixture(tmp_path, monkeypatch)
    r8.rank(tmp_path)
    rows = r8.load(tmp_path / 'per-query.json')
    assert len(rows) == 3 and {r['arm'] for r in rows} == set(r8.ARMS)
    assert all(r['pre_hit5'] == 1 and not r['embedding_failed'] for r in rows)


@pytest.mark.parametrize('tamper', ['mapping', 'input', 'logical', 'index', 'response_bytes', 'missing_hash', 'dimension'])
def test_changed_embedding_binding_is_rejected_before_scoring(tmp_path, monkeypatch, tamper):
    digest, path = ranking_fixture(tmp_path, monkeypatch)
    if tamper in ('mapping', 'input'):
        data = r8.load(tmp_path / 'embedding-inputs.json')
        if tamper == 'mapping':
            data['mapping']['q:original'] = 'a different query digest'
        else:
            data['inputs'][digest] = 'a different encoded query'
        r8.save(tmp_path / 'embedding-inputs.json', data)
    elif tamper in ('logical', 'index'):
        data = r8.load(tmp_path / 'embeddings.json')
        data[digest]['logical_key' if tamper == 'logical' else 'vector_index'] = 'other-request' if tamper == 'logical' else 1
        r8.save(tmp_path / 'embeddings.json', data)
    elif tamper == 'missing_hash':
        r8.save(tmp_path / 'embedding-response-hashes.json', {})
    else:
        data = r8.load(tmp_path / path)
        data['result'][0] = [1.0, 0.0]
        r8.save(tmp_path / path, data)
        if tamper == 'dimension':
            # A valid archive digest still cannot make an invalid-size vector usable.
            r8.save(tmp_path / 'embedding-response-hashes.json', {path: r8.sha((tmp_path / path).read_bytes())})
    with pytest.raises(ValueError):
        r8.rank(tmp_path)
    assert not (tmp_path / 'per-query.json').exists()


def test_role_costs_count_actual_attempts_and_separate_user_simulation(tmp_path):
    r8.save(tmp_path / 'calls.json', {
        'a:1': {'logical_key': 'a', 'capability': 'text', 'status': 'failed', 'http_status': 503, 'usage': {}},
        'a:2': {'logical_key': 'a', 'capability': 'text', 'status': 'succeeded', 'http_status': 200,
                'usage': {'total_tokens': 11}},
        'b:1': {'logical_key': 'b', 'capability': 'text', 'status': 'succeeded', 'http_status': 200,
                'usage': {'total_tokens': 7}},
        'c:1': {'logical_key': 'c', 'capability': 'embedding', 'status': 'succeeded', 'http_status': 200,
                'usage': {'total_tokens': 3, 'cost': 0.001}},
    })
    r8.save(tmp_path / 'interactions.json', {
        'q1:selective': {'logical_key': 'a'}, 'q2:selective': {'logical_key': 'a'},
        'q1:reply': {'logical_key': 'b'},
    })
    result = r8_report.costs(tmp_path)
    assert result['actual_http_attempts'] == 4
    assert result['by_text_role']['selective'] == {'logical_requests': 1, 'attempts': 2,
                                                  'total_tokens': 11, 'simulation_only': False}
    assert result['by_text_role']['reply'] == {'logical_requests': 1, 'attempts': 1,
                                              'total_tokens': 7, 'simulation_only': True}
    assert result['by_capability']['text']['unknown_cost_attempts'] == 3
    assert result['by_capability']['text']['missing_total_tokens'] == 1
    assert result['by_capability']['embedding']['known_cost_usd'] == pytest.approx(0.001)


def test_every_json_mode_role_explicitly_requests_json():
    assert set(r8.PROMPTS) == {'normalize', 'selective', 'reply', 'resolve'}
    assert all('json' in prompt.lower() for prompt in r8.PROMPTS.values())


def test_missing_json_instruction_stops_before_remote_construction(tmp_path, monkeypatch):
    monkeypatch.setattr(r8, 'verify', lambda run: None)
    monkeypatch.setattr(r8, 'PROMPTS', dict(r8.PROMPTS, reply='Return a structured object.'))

    def forbidden_remote(run):
        pytest.fail('The invalid JSON-mode request must be rejected before constructing Remote.')

    monkeypatch.setattr(r8, 'Remote', forbidden_remote)
    with pytest.raises(ValueError, match='explicit JSON'):
        asyncio.run(r8.interact(tmp_path))


@pytest.mark.parametrize('status', [400, 401, 402, 403, 404, 422])
def test_permanent_http_errors_halt_without_retry_or_followup_request(tmp_path, monkeypatch, status):
    settings = SimpleNamespace(**{
        cap: SimpleNamespace(base_url='https://api.deepseek.com' if cap == 'text' else 'https://openrouter.ai/api/v1',
                             path='/offline-test', model='offline-fixture', signature='fixture', api_key='fixture-key')
        for cap in r8.LIMITS
    })
    r8.save(tmp_path / 'providers.json', r8.endpoints(settings))
    monkeypatch.setattr(r8.r7.Settings, 'from_env', lambda: settings)
    monkeypatch.setattr(r8.r7, 'CAPS', dict(r8.LIMITS))
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(status, json={'error': {'message': 'Offline permanent-error fixture.'}})

    async def check():
        remote = r8.Remote(tmp_path)
        await remote.client.aclose()
        remote.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ValueError, match='Permanent provider error'):
                await remote.call('text', {'messages': [{'role': 'user', 'content': 'Return JSON.'}]}, lambda data: data)
            assert remote.halt is True
            assert len(remote.calls) == len(sent) == 1
            record = next(iter(remote.calls.values()))
            assert record['attempt'] == 1 and record['http_status'] == status and record['status'] == 'failed'
            with pytest.raises(ValueError):
                await remote.call('text', {'messages': [{'role': 'user', 'content': 'A different JSON request.'}]}, lambda data: data)
            assert len(remote.calls) == len(sent) == 1
        finally:
            await remote.close()

    asyncio.run(check())
