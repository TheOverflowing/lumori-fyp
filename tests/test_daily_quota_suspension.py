"""Temporary local daily-cap suspension; all providers use offline fixtures."""
import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from app import auto_exploration, config
from app.config import Endpoint, Settings
from app.providers import ApiProviders, ProviderError
from app.store import Store
from app.task_control import JobCancelled, LocalCallLimit
from test_auto_exploration import rig as exploration_rig
from test_generation_agent import SOURCE, agent_case
from test_workflow import rig as web_rig


@pytest.fixture
def clock(monkeypatch):
    value = SimpleNamespace(now=1000.0)
    # Replace this module's clock, without changing auth or request timing.
    monkeypatch.setattr(config, 'time', SimpleNamespace(time=lambda: value.now))
    return value


def test_default_cap_and_exact_expiry_restore_without_restart(clock):
    settings = Settings(max_daily_calls=17)
    assert settings.effective_daily_call_limit == 17
    settings.daily_api_limit_suspended_until = 2000.0
    assert settings.effective_daily_call_limit is None
    clock.now = 1999.999
    assert settings.effective_daily_call_limit is None
    clock.now = 2000.0
    assert settings.effective_daily_call_limit == 17
    clock.now = 2001.0
    assert settings.effective_daily_call_limit == 17
    assert settings.max_daily_calls == 17


@pytest.mark.parametrize('value', ['', 'tomorrow', '-1', 'nan', 'inf', '-inf', '1e999'])
def test_invalid_env_deadline_fails_closed(monkeypatch, value):
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setenv('DAILY_API_LIMIT_SUSPENDED_UNTIL', value)
    with pytest.raises(ValueError, match='DAILY_API_LIMIT_SUSPENDED_UNTIL'):
        Settings.from_env()


def test_env_deadline_is_absolute_and_retains_configured_cap(monkeypatch, clock):
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setenv('MAX_DAILY_API_CALLS', '100')
    monkeypatch.setenv('DAILY_API_LIMIT_SUSPENDED_UNTIL', '2000.5')
    settings = Settings.from_env()
    assert settings.daily_api_limit_suspended_until == 2000.5
    assert settings.max_daily_calls == 100
    assert settings.effective_daily_call_limit is None
    clock.now = 2000.5
    restarted = Settings.from_env()
    assert restarted.daily_api_limit_suspended_until == 2000.5
    assert restarted.effective_daily_call_limit == 100


def test_suspended_daily_cap_keeps_ledger_and_restored_cap_counts_it(tmp_path):
    store = Store(tmp_path)
    ids = [store.reserve_call(None, 'text', 'fixture', None) for _ in range(3)]
    assert len(set(ids)) == 3
    assert len(store.all('SELECT * FROM calls')) == 3
    with pytest.raises(LocalCallLimit) as caught:
        store.reserve_call(None, 'text', 'fixture', 1)
    assert caught.value.scope == 'daily'
    assert len(store.all('SELECT * FROM calls')) == 3


def test_suspension_preserves_frozen_job_cap_and_cancellation(tmp_path):
    store = Store(tmp_path)
    job, _ = store.job('limited', 'generate', {})
    store.save_job_evidence(job['id'], {
        'schema_version': 'education-agent-v1', 'configuration': {'max_calls': 1}})
    store.reserve_call(job['id'], 'text', 'fixture', None)
    with pytest.raises(LocalCallLimit) as caught:
        store.reserve_call(job['id'], 'text', 'fixture', None)
    assert caught.value.scope == 'job'
    assert len(store.calls_for_job(job['id'])) == 1

    cancelled, _ = store.job('cancelled', 'generate', {})
    store.request_cancel(cancelled['id'])
    with pytest.raises(JobCancelled):
        store.reserve_call(cancelled['id'], 'search', 'fixture', None)
    assert store.calls_for_job(cancelled['id']) == []


def test_provider_reservations_restore_at_expiry_without_resetting_usage(tmp_path, clock):
    settings = Settings(data_dir=tmp_path, max_daily_calls=1,
                        daily_api_limit_suspended_until=2000.0)
    settings.text = Endpoint('https://fixture.invalid', 'fixture-key', 'fixture', '/test')
    store = Store(tmp_path)
    seen = []

    def wire(request):
        seen.append(request)
        return httpx.Response(200, json={'ok': True})

    async def run():
        providers = ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
        try:
            for _ in range(2):
                assert await providers.call('text', {}, None) == {'ok': True}
            clock.now = 2000.0
            with pytest.raises(LocalCallLimit) as caught:
                await providers.call('text', {}, None)
            assert caught.value.scope == 'daily'
        finally:
            await providers.close()

    asyncio.run(run())
    assert len(seen) == 2
    assert [row['status'] for row in store.all('SELECT * FROM calls')] == ['succeeded', 'succeeded']


def test_suspension_does_not_bypass_upstream_rate_limit(tmp_path, clock):
    settings = Settings(data_dir=tmp_path, daily_api_limit_suspended_until=2000.0)
    settings.text = Endpoint('https://fixture.invalid', 'fixture-key', 'fixture', '/test')
    store = Store(tmp_path)

    async def run():
        providers = ApiProviders(settings, store, httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(429, json={'error': 'fixture limit'}))))
        try:
            with pytest.raises(ProviderError) as caught:
                await providers.call('text', {}, None)
            assert caught.value.http_status == 429
        finally:
            await providers.close()

    asyncio.run(run())
    calls = store.all('SELECT * FROM calls')
    assert len(calls) == 1 and calls[0]['status'] == 'failed'


def test_search_uses_suspension_but_keeps_its_own_budget(exploration_rig, clock):
    pipeline, request, job_id, seen, _ = exploration_rig
    pipeline.settings.max_daily_calls = 1
    pipeline.settings.daily_api_limit_suspended_until = 2000.0
    pipeline.settings.exploration_max_search_calls = 1
    pipeline.store.reserve_call(job_id, 'text', 'fixture', 1)
    run = auto_exploration._Run(pipeline, request, job_id, {
        'rounds': 1, 'search_calls': 0, 'search_audit': []})
    query = {'query': 'MLFQ priority boost', 'language': 'en'}
    assert asyncio.run(run.search(query))
    with pytest.raises(auto_exploration._Stop) as caught:
        asyncio.run(run.search(query))
    assert str(caught.value) == 'search_budget'
    assert len(seen['search']) == 1
    calls = pipeline.store.calls_for_job(job_id)
    assert len(calls) == 2 and calls[1]['capability'] == 'search'


@pytest.mark.parametrize('active', [True, False])
def test_agent_preflight_uses_live_daily_policy(agent_case, clock, active):
    rig = agent_case(count=1, settings_options={
        'max_daily_calls': 1, 'agent_max_calls': 12,
        'daily_api_limit_suspended_until': 2000.0 if active else 1000.0})
    rig.store.reserve_call(None, 'text', 'prior-fixture', 1)

    async def retrieve(request, job_id, *, with_trace=False):
        assert with_trace
        rig.retrieval_calls.append(job_id)
        call_id = rig.store.reserve_call(job_id, 'embedding', 'fixture', rig.settings.effective_daily_call_limit)
        rig.store.execute("UPDATE calls SET status='succeeded' WHERE id=?", (call_id,))
        return [copy.deepcopy(SOURCE)], {'configuration': {'strategy': 'fixture'}, 'selected_count': 1}

    rig.pipeline.retrieve = retrieve
    assert rig.run()['status'] == ('succeeded' if active else 'failed')
    if active:
        assert len(rig.store.calls_for_job(rig.job_id)) == 4
        assert len(rig.wire.contracts) == 3
        assert 'Infinity' not in json.dumps(rig.evidence(), allow_nan=False)
    else:
        assert rig.evidence()['agent']['resource_limit']['scope'] == 'daily'
        assert rig.retrieval_calls == [] and rig.wire.contracts == []
    assert rig.settings.max_daily_calls == 1


def test_suspended_agent_preflight_still_enforces_job_budget(agent_case, clock):
    rig = agent_case(count=2, settings_options={
        'max_daily_calls': 1, 'agent_max_calls': 6,
        'daily_api_limit_suspended_until': 2000.0})
    assert rig.run()['status'] == 'failed'
    assert rig.evidence()['agent']['resource_limit']['scope'] == 'job'
    assert rig.retrieval_calls == [] and rig.wire.contracts == []


def test_authenticated_status_reports_active_then_restored_policy(web_rig, clock):
    client, app, wire = web_rig
    settings = app.state.settings
    settings.daily_api_limit_suspended_until = 2000.0
    before = client.get('/api/status').json()
    assert before['daily_call_limit'] is None
    assert before['daily_call_limit_suspended_until'] == 2000.0
    clock.now = 2000.0
    after = client.get('/api/status').json()
    assert after['daily_call_limit'] == settings.max_daily_calls == 100
    assert after['daily_call_limit_suspended_until'] is None
    assert after['calls_today'] == before['calls_today'] == 0
    assert wire.calls == 0
