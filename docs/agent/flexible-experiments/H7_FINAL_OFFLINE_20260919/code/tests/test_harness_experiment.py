"""Offline experiment planning/injection and controller checkpoint isolation."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.config import Endpoint, Settings
from app.generation_agent import GenerationAgent, authorize_resume
from app.harness_tools import MANIFEST_SCHEMA, ScopedTeachingTools
from app.models import GenerateRequest
from app.store import Store
from scripts import harness_correctness_experiment as experiment
from test_generation_agent import SOURCE, agent_case


def test_default_plan_interleaves_both_runtimes_and_retains_each_case():
    plan = experiment.build_plan(['all'], 'both')
    assert len(plan) == 10
    for first, second in zip(plan[::2], plan[1::2]):
        assert first['id'] == second['id']
        assert (first['runtime'], second['runtime']) == ('native', 'deepseek_harness')
    assert len({row['task_id'] for row in plan}) == 10


@pytest.mark.parametrize('requested,runtime,expected', [
    (['canary'], 'both', 4), (['live'], 'native', 3),
    (['canary_bad,canary_corrected'], 'deepseek_harness', 2),
    (['cpu_scheduling_en_hard', 'cpu_zh_hard'], 'native', 2),
    (['canary_bad', 'canary_bad_Q016'], 'native', 1),
])
def test_case_subset_and_aliases(requested, runtime, expected):
    assert len(experiment.build_plan(requested, runtime)) == expected


def test_unknown_case_or_runtime_is_rejected():
    with pytest.raises(ValueError):
        experiment.build_plan(['unknown'], 'both')
    with pytest.raises(ValueError):
        experiment.build_plan(['all'], 'arbitrary-runtime')


def test_dry_run_never_reads_provider_configuration_or_creates_runtime(tmp_path, monkeypatch):
    def forbidden(cls):
        pytest.fail('Dry mode must not load credentials or provider configuration.')
    monkeypatch.setattr(Settings, 'from_env', classmethod(forbidden))
    output = tmp_path / 'dry'
    args = experiment.parser().parse_args(['--output', str(output)])
    asyncio.run(experiment.run(args))
    manifest = json.loads((output / 'manifest.json').read_text())
    summary = json.loads((output / 'summary.json').read_text())
    assert manifest['live'] is False and manifest['call_cap'] == 64
    assert manifest['shared_thinking'] == {'type': 'disabled'}
    assert manifest['harness_max_requests'] == 6
    assert manifest['harness_max_output_tokens'] == 4096
    assert len(manifest['plan']) == 10 and summary['actual_calls'] == 0
    assert summary['recorded_tasks'] == 0
    assert 'app/harness_tools.py' in manifest['code_sha256']
    assert (output / 'code/scripts/harness_correctness_experiment.py').is_file()
    assert not (output / 'runtime').exists()


def test_source_seed_is_real_and_scope_compatible_without_altering_dataset(tmp_path):
    dataset = json.loads((experiment.ROOT / 'benchmarks/difficulty/cases.json').read_text())
    before = deepcopy(dataset)
    cases = experiment.frozen_cases(dataset, experiment.build_plan(['all'], 'both'))
    assert dataset == before
    store = Store(tmp_path / 'data')
    experiment.seed_documents(store, cases)
    for case in cases.values():
        request = experiment.make_request(case)
        job, _ = store.job(request.request_key, 'generate', request.model_dump())
        manifest = {'schema': MANIFEST_SCHEMA, 'job_id': job['id'], 'course_id': request.course_id,
            'data_dir': str(tmp_path / 'data'), 'owner_id': None, 'enforce_account_ownership': False,
            'sources': case['sources'], 'audit_path': str(tmp_path / (case['id'] + '.jsonl'))}
        result = ScopedTeachingTools(manifest).get_reference_chunks()
        assert result['ok'] and result['sources'] == case['sources']
        for source in case['sources']:
            doc = store.one('SELECT * FROM documents WHERE id=?', (source['document_id'],))
            assert doc['course_id'] == request.course_id and doc['status'] == 'indexed'


def test_fixture_author_injection_costs_no_call_and_other_phases_delegate(agent_case, monkeypatch):
    rig = agent_case(count=1)
    request = GenerateRequest.model_validate_json(rig.job()['payload'])
    fixture = {'title': 'Fixture only', 'questions': []}
    origin = {'kind': 'injected_regression_fixture', 'api_call_performed': False}
    agent = experiment.FixtureGenerationAgent(rig.pipeline, request, rig.job_id, fixture, origin)
    agent.state = {'phase': 'author', 'resume_count': 0, 'call_count': 0}
    agent.evidence = {'agent': agent.state, 'sources': []}
    delegated = []

    async def fake_base_call(self, attempt, phase, contract, system):
        delegated.append(phase)
        return {'from_base_runtime': phase}

    monkeypatch.setattr(GenerationAgent, 'call', fake_base_call)
    attempt = {}
    answer = asyncio.run(agent.call(attempt, 'author', {'task': 'agent_author'}, 'shared v3 system'))
    assert answer == fixture and answer is not fixture
    fixture['title'] = 'mutated original'
    assert attempt['author']['response']['title'] == 'Fixture only'
    assert attempt['author']['history'][0]['status'] == 'fixture_injected'
    assert attempt['author']['history'][0]['fixture_origin'] == origin
    assert attempt['author']['history'][0]['api_call_performed'] is False
    assert attempt['author']['history'][0]['messages'][0]['content'] == 'shared v3 system'
    assert attempt['author']['history'][0]['prompt_sha256']
    asyncio.run(agent.call(attempt, 'author', {'task': 'agent_author'}, 'shared v3 system'))
    assert len(attempt['author']['history']) == 1
    assert agent.state['call_count'] == 0 and rig.text_call_count() == 0
    assert rig.wire.contracts == []
    assert asyncio.run(agent.call(attempt, 'solve', {}, '')) == {'from_base_runtime': 'solve'}
    assert delegated == ['solve']


def test_local_provider_settings_disable_thinking_for_both_runtimes(tmp_path, monkeypatch):
    original = Settings(text=Endpoint('https://fixture.invalid/v1', 'fixture-not-real-key',
        'fixture-model', '/chat/completions', {'thinking': {'type': 'enabled'},
        'temperature': 0.2, 'private_unknown': 'must-not-be-persisted'}))
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: original))
    seen = []

    class FakeProviders:
        def __init__(self, settings, store):
            seen.append(settings)
        async def close(self):
            pass

    class FakePipeline:
        def __init__(self, settings, store, providers, **kwargs):
            self.store = store
        async def run(self, job_id):
            self.store.execute("UPDATE jobs SET status='failed',error='offline fixture' WHERE id=?", (job_id,))

    monkeypatch.setattr(experiment, 'ApiProviders', FakeProviders)
    monkeypatch.setattr(experiment, 'ExperimentPipeline', FakePipeline)
    output = tmp_path / 'offline-patched-live-path'
    args = experiment.parser().parse_args(['--live', '--cases', 'canary_bad', '--output', str(output)])
    asyncio.run(experiment.run(args))
    assert [item.agent_runtime for item in seen] == ['native', 'deepseek_harness']
    assert all(item.text.extra['thinking'] == {'type': 'disabled'} for item in seen)
    assert all(item.text.extra['max_tokens'] == item.harness_max_output_tokens == 4096 for item in seen)
    assert original.text.extra['thinking'] == {'type': 'enabled'}
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['provider']['public_parameters'] == {
        'temperature': 0.2, 'max_tokens': 4096, 'thinking': {'type': 'disabled'}}
    assert 'fixture-not-real-key' not in (output / 'manifest.json').read_text()
    assert 'must-not-be-persisted' not in (output / 'manifest.json').read_text()
    assert json.loads((output / 'summary.json').read_text())['actual_calls'] == 0


def seed_interrupted_checkpoint(rig, monkeypatch):
    import app.harness_runner
    monkeypatch.setattr(app.harness_runner, 'verify_runtime', lambda settings: None)
    retrievals = []

    async def frozen(request, job_id, with_trace=True):
        retrievals.append(job_id)
        return [deepcopy(SOURCE)], {'mode': 'test-frozen', 'api_calls': 0}

    rig.pipeline.retrieve = frozen
    request = GenerateRequest.model_validate_json(rig.job()['payload'])
    controller = GenerationAgent(rig.pipeline, request, rig.job_id)
    asyncio.run(controller.initialize())
    controller.state['slots'][0].update(status='passed', accepted_asset={'fixture': 'must-preserve'})
    controller.state.update(status='provider_error', phase='solve', call_count=7)
    controller.save()
    rig.store.execute("UPDATE jobs SET status='failed' WHERE id=?", (rig.job_id,))
    return request, deepcopy(controller.evidence), retrievals


@pytest.mark.parametrize('initial_runtime,field,value', [
    ('native', 'agent_runtime', 'deepseek_harness'),
    ('deepseek_harness', 'agent_runtime', 'native'),
    ('deepseek_harness', 'harness_max_requests', 5),
    ('deepseek_harness', 'harness_max_output_tokens', 2048),
    ('deepseek_harness', 'harness_timeout', 99),
])
def test_controller_resume_rejects_changed_runtime_configuration_before_calls(
        agent_case, monkeypatch, initial_runtime, field, value):
    rig = agent_case(count=2, settings_options={'agent_runtime': initial_runtime})
    _, before, retrievals = seed_interrupted_checkpoint(rig, monkeypatch)
    authorize_resume(rig.store, rig.job_id)
    setattr(rig.settings, field, value)
    assert rig.run()['status'] == 'failed'
    assert '配置已改变' in rig.job()['error']
    after = rig.evidence()
    assert after['configuration'] == before['configuration']
    assert after['agent']['slots'][0] == before['agent']['slots'][0]
    assert after['agent']['call_count'] == 7
    assert after['agent']['resume_count'] == 1
    assert len(retrievals) == 1
    assert rig.text_call_count() == 0 and rig.wire.contracts == []


@pytest.mark.parametrize('runtime', ['native', 'deepseek_harness'])
def test_same_configuration_resume_keeps_passed_checkpoint_and_frozen_context(agent_case, monkeypatch, runtime):
    rig = agent_case(count=2, settings_options={'agent_runtime': runtime})
    request, before, retrievals = seed_interrupted_checkpoint(rig, monkeypatch)
    authorize_resume(rig.store, rig.job_id)
    controller = GenerationAgent(rig.pipeline, request, rig.job_id)
    asyncio.run(controller.initialize())
    assert controller.state['slots'][0] == before['agent']['slots'][0]
    assert controller.state['call_count'] == 7 and controller.state['resume_count'] == 1
    assert len(retrievals) == 1
    assert rig.text_call_count() == 0 and rig.wire.contracts == []


def test_summary_retains_failure_denominator_and_unknown_usage():
    plan = experiment.build_plan(['canary'], 'native')
    rows = [plan[0] | {'status': 'failed', 'calls': [
        {'status': 'failed', 'usage': {}}, {'status': 'succeeded', 'usage': {'total_tokens': 20, 'cost': 0.01}}]},
        plan[1] | {'status': 'not_run_budget_exhausted', 'calls': []}]
    summary = experiment.summarize(rows, plan)['by_runtime']['native']
    assert summary['planned_tasks'] == summary['recorded_tasks'] == 2
    assert summary['status_counts'] == {'failed': 1, 'not_run_budget_exhausted': 1}
    assert summary['actual_calls'] == 2 and summary['known_total_tokens'] == 20
    assert summary['cost_missing_calls'] == summary['tokens_missing_calls'] == 1
    assert summary['known_cost_usd'] == 0.01
