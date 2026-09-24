"""Runner contracts use isolated mocked HTTP, never live credentials/providers."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest

from app.config import Endpoint, Settings
from app.providers import ApiProviders
from app.store import Store, dumps
from scripts import quality_latency_baseline as baseline
from tests.test_generation_agent import AgentWire


class BaselineWire(AgentWire):
    def __call__(self, request):
        data = json.loads(request.content)
        if request.url.path.endswith('/embeddings'):
            return httpx.Response(200, json={'data': [{'index': i, 'embedding': [1., .5, .25]}
                for i in range(len(data['input']))], 'usage': {'prompt_tokens': 10, 'total_tokens': 10}})
        contract = json.loads(data['messages'][1]['content'])
        result = super().__call__(request)
        raw = json.loads(result.json()['choices'][0]['message']['content'])
        if contract['task'] == 'agent_author':
            source = contract['reference_chunks'][0]['id']
            question = raw['questions'][0]
            question['citation_ids'] = [source]
            if contract['request']['question_type'] == 'mcq':
                question.update(kind='mcq', options=['Fixture correct.', 'Fixture distractor B.',
                    'Fixture distractor C.', 'Fixture distractor D.'], answer='A')
        return self.response(raw)


def fixture_settings(path):
    return Settings(data_dir=path, generation_workflow='agent_v1',
        text=Endpoint('https://fixture.invalid/v1', 'DO_NOT_EXPORT_TEST_SECRET', 'fixture-text', '/chat/completions'),
        embedding=Endpoint('https://fixture.invalid/v1', 'DO_NOT_EXPORT_TEST_SECRET', 'fixture-embedding', '/embeddings'),
        retrieval_strategy='hybrid_dense_lexical_v1')


def arguments(tmp_path, *extra):
    return baseline.parser().parse_args(['--output', str(tmp_path / 'experiment'), *extra])


def test_dataset_quotes_and_bilingual_pairing_are_frozen():
    dataset = baseline.load_dataset(baseline.DATASET)
    assert len(dataset['cases']) == 24
    assert len({case['need_id'] for case in dataset['cases']}) == 12


def test_generator_never_receives_grading_keys_or_gold_document_filter():
    case = deepcopy(baseline.load_dataset(baseline.DATASET)['cases'][0])
    case.update(grading_expectations='PRIVATE GOLD ANSWER', review_criteria=['PRIVATE RUBRIC'],
                expected_evidence=[{'source_id': 'private-source', 'quote': 'PRIVATE EVIDENCE'}])
    request = baseline.make_request(case).model_dump()
    assert request['document_ids'] == []
    assert 'PRIVATE' not in dumps(request)
    assert request['count'] == 1 and request['include_explanations'] is False
    assert not request.get('query_fusion') and not request.get('auto_explore')


def test_dry_run_does_not_load_credentials_or_create_provider(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Dry run must not access credentials or create providers')
    monkeypatch.setattr(baseline.Settings, 'from_env', forbidden)
    path = asyncio.run(baseline.run(arguments(tmp_path), providers_factory=forbidden))
    manifest = json.loads((path / 'manifest.json').read_text())
    assert manifest['live'] is False and manifest['planned_cases'] == 24
    assert not (path / 'runtime').exists()
    assert len(json.loads((path / 'case_runs.json').read_text())) == 24


def test_mocked_live_pipeline_runs_real_retrieval_and_preserves_all_results(tmp_path):
    wire = BaselineWire()
    args = arguments(tmp_path, '--live')
    def factory(settings, store):
        return ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    path = asyncio.run(baseline.run(args, base=fixture_settings(tmp_path / 'untouched'), providers_factory=factory))
    manifest = json.loads((path / 'manifest.json').read_text())
    rows = json.loads((path / 'case_runs.json').read_text())
    assert manifest['status'] == 'completed'
    assert len(rows) == 24 and all(row['status'] == 'succeeded' for row in rows)
    assert manifest['configuration']['concurrency'] == 1
    store = Store(path / 'runtime')
    assert store.one("SELECT count(*) AS n FROM calls WHERE capability='text'")['n'] == 72
    assert store.one("SELECT count(*) AS n FROM calls WHERE capability='embedding'")['n'] >= 36
    assert not (tmp_path / 'untouched').exists()
    evidence = json.loads(next((path / 'cases').glob('*.json')).read_text())['evidence']
    assert evidence['retrieval']['configuration']['strategy'] == 'hybrid_dense_lexical_v1'
    assert evidence['sources'] and len(list((path / 'cases').glob('*.json'))) == 24
    for artifact in path.glob('*.json'):
        assert 'DO_NOT_EXPORT_TEST_SECRET' not in artifact.read_text()
    before = store.one('SELECT count(*) AS n FROM calls')['n']
    args.resume = True
    asyncio.run(baseline.run(args, base=fixture_settings(tmp_path / 'untouched'), providers_factory=factory))
    assert store.one('SELECT count(*) AS n FROM calls')['n'] == before


def test_provider_access_failure_stops_without_spending_remaining_plan(tmp_path):
    def failure(request):
        return httpx.Response(402, text='private upstream data must not be exported')
    def factory(settings, store):
        return ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(failure)))
    path = asyncio.run(baseline.run(arguments(tmp_path, '--live'),
        base=fixture_settings(tmp_path / 'untouched'), providers_factory=factory))
    manifest = json.loads((path / 'manifest.json').read_text())
    assert manifest['status'] == 'stopped' and manifest['stop_reason'] == 'index_failed'
    assert Store(path / 'runtime').one('SELECT count(*) AS n FROM calls')['n'] == 1
    rows = json.loads((path / 'case_runs.json').read_text())
    assert all(row['job_id'] is None for row in rows)
    assert 'private upstream data' not in dumps(manifest)


def test_resuming_changed_budget_or_dataset_requires_new_run(tmp_path):
    args = arguments(tmp_path)
    asyncio.run(baseline.run(args))
    args.resume = True
    args.call_cap += 1
    with pytest.raises(ValueError, match='Frozen'):
        asyncio.run(baseline.run(args))


def test_incompatible_runtime_fails_before_provider_creation(tmp_path):
    settings = fixture_settings(tmp_path / 'untouched')
    settings.agent_runtime = 'deepseek_harness'
    def forbidden(*args, **kwargs):
        pytest.fail('An incompatible protocol must not create a provider')
    with pytest.raises(ValueError, match='native'):
        asyncio.run(baseline.run(arguments(tmp_path, '--live'), base=settings, providers_factory=forbidden))


def test_unclean_session_time_is_not_reset_to_zero():
    from datetime import datetime, timedelta, timezone
    previous = [{'started_at': (datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()}]
    assert baseline.spent_session_seconds(previous) >= 120
    assert previous[0]['timing_complete'] is False
