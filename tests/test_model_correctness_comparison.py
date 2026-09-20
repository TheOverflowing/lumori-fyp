"""Offline checks of frozen diagnostic labels, transport isolation and accounting."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest

from app.config import Endpoint, Settings
from app.providers import ApiProviders
from scripts import model_correctness_comparison as experiment


def base_settings():
    return Settings(text=Endpoint('https://api.deepseek.com', 'test-text-private-credential',
        'deepseek-flash', '/chat/completions', {'temperature': 0.2, 'private': 'do-not-copy'}),
        embedding=Endpoint('https://openrouter.ai/api/v1', 'test-router-private-credential',
        'qwen/qwen3-embedding-8b', '/embeddings'), timeout=120)


def completion(review=None, *, content=None, finish='stop', model='deepseek-flash', reasoning=None):
    if review is None:
        review = {'answer_correct': True, 'explanation_correct': True, 'issues': [], 'confidence': 'high'}
    return {'model': model, 'choices': [{'finish_reason': finish, 'message': {
        'content': json.dumps(review) if content is None else content, 'reasoning_content': reasoning}}],
        'usage': {'prompt_tokens': 50, 'completion_tokens': 10, 'total_tokens': 60,
                  'completion_tokens_details': {'reasoning_tokens': 3}}}


def test_frozen_labels_derive_distinct_numeric_and_binding_failures():
    cases, labels = experiment.build_cases()
    assert len(cases) == 6 and len(labels) == 6
    assert [case['language'] for case in cases].count('zh') == 3
    assert sum(label['fully_correct'] for label in labels.values()) == 3
    assert labels['R02']['answer_correct'] is True
    assert labels['R02']['explanation_correct'] is False
    assert labels['R02']['derivation']['remaining_P1_at_3'] == 5
    assert labels['R04']['answer_correct'] is labels['R04']['explanation_correct'] is False
    assert labels['R04']['derivation']['B_response'] == 2
    assert labels['R06']['derivation']['required_B_first_start'] == 4
    assert cases[-1]['provided_tool_execution']['result']['per_process']['B']['first_start'] == 2
    assert all(labels[key]['fully_correct'] == (labels[key]['answer_correct'] and labels[key]['explanation_correct'])
               for key in labels)


def test_messages_exclude_label_metadata_and_do_not_mutate_cases():
    cases, labels = experiment.build_cases()
    original = deepcopy(cases)
    for case in cases:
        messages = experiment.messages_for(case)
        assert messages[0]['content'] == experiment.SYSTEM
        content = json.loads(messages[1]['content'])
        assert set(content) == {'question', 'candidate_answer', 'candidate_explanation',
                                'provided_tool_execution', 'tool_semantics'}
        assert case['id'] not in messages[1]['content']
        assert all(key not in content for key in ('family', 'language', 'fully_correct', 'derivation'))
    assert cases == original
    assert 'required_execution' in labels['R06']['derivation']
    assert 'required_execution' not in experiment.messages_for(cases[-1])[1]['content']


def test_plan_rotates_order_and_keeps_identical_case_prompts():
    cases, _ = experiment.build_cases()
    plan = experiment.build_plan(cases, list(experiment.CONDITIONS))
    assert len(plan) == 18 and len({row['task_id'] for row in plan}) == 18
    assert [row['condition'] for row in plan[:3]] == list(experiment.CONDITIONS)
    assert [row['condition'] for row in plan[3:6]] == ['deepseek_high', 'gemini_high', 'deepseek_off']
    for case in cases:
        assert len([row for row in plan if row['case_id'] == case['id']]) == 3
    with pytest.raises(ValueError):
        experiment.build_plan(cases, ['deepseek_off', 'deepseek_off'])


def test_dry_mode_never_loads_credentials_or_initializes_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: pytest.fail('No dry credential read.')))
    monkeypatch.setattr(experiment, 'ApiProviders', lambda *args: pytest.fail('No dry provider.'))
    output = tmp_path / 'dry'
    args = experiment.parser().parse_args(['--output', str(output)])
    asyncio.run(experiment.run(args))
    manifest = json.loads((output / 'manifest.json').read_text())
    summary = json.loads((output / 'summary.json').read_text())
    assert manifest['live'] is False
    assert manifest['transport'] == 'direct_chat_completion_not_harness'
    assert manifest['call_cap'] == 18 and len(manifest['plan']) == 18
    assert manifest['max_output_tokens'] == 8192
    assert summary['actual_calls'] == 0
    assert not (output / 'runtime').exists()
    assert (output / 'deterministic_labels.json').is_file()
    assert (output / 'code/app/answer_tools.py').is_file()


def test_provider_configs_are_exact_isolated_whitelisted_and_omit_temperature(tmp_path):
    base = base_settings()
    original = deepcopy(base)
    arms = {condition: experiment.condition_settings(base, condition, tmp_path, 8192, 18)
            for condition in experiment.CONDITIONS}
    assert arms['deepseek_off'].text.extra == {'max_tokens': 8192, 'thinking': {'type': 'disabled'}}
    assert arms['deepseek_high'].text.extra == {'max_tokens': 8192, 'thinking': {'type': 'enabled'},
                                              'reasoning_effort': 'high'}
    gemini = arms['gemini_high'].text
    assert gemini.base_url == 'https://openrouter.ai/api/v1'
    assert gemini.model == 'google/gemini-3.8-flash'
    assert gemini.api_key == base.embedding.api_key
    assert gemini.extra == {'max_tokens': 8192, 'reasoning': {'effort': 'high'},
                            'provider': {'require_parameters': True}}
    assert all(arm.timeout >= 180 for arm in arms.values())
    assert all('temperature' not in arm.text.extra for arm in arms.values())
    assert base == original


@pytest.mark.parametrize('url', ['https://openrouter.ai.evil.invalid/api/v1', 'http://openrouter.ai/api/v1',
                                'https://key@openrouter.ai/api/v1', 'https://other.invalid'])
def test_no_openrouter_credential_reuse_from_other_host(tmp_path, url):
    base = base_settings()
    base.embedding = Endpoint(url, 'some-private-value', 'embed', '/embeddings')
    with pytest.raises(ValueError):
        experiment.condition_settings(base, 'gemini_high', tmp_path, 8192, 18)


@pytest.mark.parametrize('changes', [
    {'answer_correct': 1}, {'answer_correct': 'true'}, {'explanation_correct': None},
    {'issues': 'none'}, {'issues': ['']}, {'confidence': 'certain'}, {'extra': False},
])
def test_review_schema_is_strict(changes):
    review = {'answer_correct': True, 'explanation_correct': True, 'issues': [], 'confidence': 'high'} | changes
    with pytest.raises(ValueError):
        experiment.parse_review(completion(review))


@pytest.mark.parametrize('content,finish', [
    ('{}', 'stop'), ('[]', 'stop'), ('{"answer_correct":NaN}', 'stop'),
    ('```json\n{}\n```', 'stop'), ('', 'stop'),
    ('{"answer_correct":true,"answer_correct":false,"explanation_correct":true,"issues":[],"confidence":"high"}', 'stop'),
    ('{"answer_correct":true,"explanation_correct":true,"issues":[],"confidence":"high"}', 'length'),
])
def test_invalid_or_truncated_final_is_never_scored_as_valid(content, finish):
    with pytest.raises(ValueError):
        experiment.parse_review(completion(content=content, finish=finish))


def test_response_archive_omits_reasoning_redacts_credentials_and_bounds_content():
    data = completion(content='secret-value sk-or-v1-0123456789abcdef ' + 'x' * 110000,
                      reasoning='must-never-archive', finish='length')
    output = experiment.final_response(data, ['secret-value'])
    assert len(output['content']) == 100000
    assert output['content_archive_truncated'] is True
    assert 'secret-value' not in output['content'] and '0123456789abcdef' not in output['content']
    assert 'must-never-archive' not in json.dumps(output)
    assert output['finish_reason'] == 'length'


def test_summary_retains_failures_and_unknown_cost_in_denominator():
    cases, labels = experiment.build_cases()
    plan = experiment.build_plan(cases, ['deepseek_off'])
    correct = {'answer_correct': True, 'explanation_correct': True, 'issues': [], 'confidence': 'high'}
    wrong = {'answer_correct': False, 'explanation_correct': False, 'issues': ['wrong'], 'confidence': 'high'}
    rows = [plan[0] | {'review': correct, 'calls': [{'usage': {'total_tokens': 10}, 'duration_ms': 1}]},
            plan[1] | {'review': correct, 'calls': []},
            plan[2] | {'review': wrong, 'calls': []},
            plan[3] | {'review': None, 'calls': []}]
    summary = experiment.summarize(rows, plan, labels)['by_condition']['deepseek_off']
    assert summary['exact_label_matches'] == 1
    assert summary['score_out_of_100_all_planned'] == pytest.approx(100 / 6)
    assert summary['false_accepts'] == summary['false_rejects'] == 1
    assert summary['unparsed_or_unrun'] == 3
    assert summary['known_cost_usd'] == 0 and summary['cost_missing_calls'] == 1


def test_live_mode_mock_transport_identical_prompts_ledger_cap_and_no_secrets(tmp_path, monkeypatch):
    base = base_settings()
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: base))
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append((str(request.url), request.headers['Authorization'], payload))
        review = {'answer_correct': True, 'explanation_correct': True,
                  'issues': [base.text.api_key], 'confidence': 'high'}
        data = completion(review, model=payload['model'], reasoning='private-reasoning')
        if 'openrouter.ai' in str(request.url):
            data['usage']['cost'] = 0.001
        return httpx.Response(200, json=data)

    monkeypatch.setattr(experiment, 'ApiProviders', lambda settings, store:
                        ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    output = tmp_path / 'live'
    args = experiment.parser().parse_args(['--live', '--call-cap', '3', '--output', str(output)])
    asyncio.run(experiment.run(args))
    assert len(seen) == 3
    assert all(row[2]['messages'] == seen[0][2]['messages'] for row in seen)
    assert all(row[2]['response_format'] == {'type': 'json_object'} for row in seen)
    assert seen[0][1] == 'Bearer ' + base.text.api_key
    assert seen[2][1] == 'Bearer ' + base.embedding.api_key
    assert seen[2][2]['model'] == experiment.GEMINI_MODEL
    results = json.loads((output / 'results.json').read_text())
    assert len(results) == 18 and sum(row['status'] == 'not_run_budget_exhausted' for row in results) == 15
    assert sum(len(row['calls']) for row in results) == 3
    assert all(row['calls'][0]['response_model'] == seen[i][2]['model'] for i, row in enumerate(results[:3]))
    assert all(row['calls'][0]['usage']['completion_tokens_details']['reasoning_tokens'] == 3 for row in results[:3])
    for path in output.rglob('*.json'):
        text = path.read_text()
        assert base.text.api_key not in text and base.embedding.api_key not in text
        assert 'private-reasoning' not in text


def test_unsupported_model_halts_condition_without_fallback_or_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: base_settings()))
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(404, json={'error': 'sensitive upstream body must not persist'})

    monkeypatch.setattr(experiment, 'ApiProviders', lambda settings, store:
                        ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    output = tmp_path / 'unsupported'
    args = experiment.parser().parse_args(['--live', '--conditions', 'gemini_high', '--output', str(output)])
    asyncio.run(experiment.run(args))
    assert len(requests) == 1 and requests[0]['model'] == experiment.GEMINI_MODEL
    rows = json.loads((output / 'results.json').read_text())
    assert rows[0]['status'] == 'provider_error'
    assert all(row['status'] == 'not_run_condition_unavailable' for row in rows[1:])
    assert 'sensitive upstream body' not in (output / 'results.json').read_text()


def test_parse_failure_still_has_successful_http_ledger_and_zero_score(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: base_settings()))
    monkeypatch.setattr(experiment, 'ApiProviders', lambda settings, store:
        ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=completion(content='malformed JSON'))))))
    output = tmp_path / 'malformed'
    args = experiment.parser().parse_args(['--live', '--conditions', 'deepseek_off',
                                           '--call-cap', '1', '--output', str(output)])
    asyncio.run(experiment.run(args))
    rows = json.loads((output / 'results.json').read_text())
    assert rows[0]['status'] == 'invalid_output' and rows[0]['review'] is None
    assert rows[0]['calls'][0]['http_status'] == 200
    summary = json.loads((output / 'summary.json').read_text())['by_condition']['deepseek_off']
    assert summary['score_out_of_100_all_planned'] == 0 and summary['actual_calls'] == 1
