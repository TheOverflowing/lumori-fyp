"""Offline safeguards for bounded supervisor experiments; no provider calls."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from app.config import Endpoint, Settings
from app.models import GenerateRequest
from scripts import harness_correctness_experiment as experiment


def forbid_runtime_loading(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Dry or invalid experiments must not load configuration or create provider/runtime instances.')

    monkeypatch.setattr(Settings, 'from_env', classmethod(forbidden))
    monkeypatch.setattr(experiment, 'ApiProviders', forbidden)
    monkeypatch.setattr(experiment, 'ExperimentPipeline', forbidden)


def supervisor_args(output, *extra):
    return experiment.parser().parse_args([
        '--runtime', 'deepseek_harness', '--orchestration', 'supervisor_v1',
        '--cases', 'cpu_en_hard', 'cpu_zh_hard', '--output', str(output), *extra,
    ])


@pytest.mark.parametrize('question_count,batch_size', [(1, 1), (4, 10)])
def test_supervisor_dry_manifest_freezes_scope_flags_and_planner_code(
        tmp_path, monkeypatch, question_count, batch_size):
    forbid_runtime_loading(monkeypatch)
    output = tmp_path / 'dry-supervisor'
    args = supervisor_args(output, '--questions-per-case', str(question_count),
        '--plan-batch-size', str(batch_size), '--max-output-tokens', '32768',
        '--question-spec', 'cpu_schedule_v1', '--thinking', 'high',
        '--response-format', 'json_object', '--schema-repairs', '1', '--call-cap', '24')

    assert asyncio.run(experiment.run(args)) == output
    manifest = json.loads((output / 'manifest.json').read_text())
    summary = json.loads((output / 'summary.json').read_text())
    cases = json.loads((output / 'frozen_cases.json').read_text())
    assert manifest['live'] is False
    assert manifest['orchestration'] == 'supervisor_v1'
    assert manifest['questions_per_case'] == question_count
    assert manifest['plan_batch_size'] == batch_size
    assert manifest['question_spec'] == 'cpu_schedule_v1'
    assert manifest['reasoning_effort'] == 'high'
    assert manifest['shared_thinking'] == {'type': 'enabled'}
    assert manifest['response_format'] == 'json_object'
    assert manifest['schema_repairs'] == 1
    assert manifest['harness_max_output_tokens'] == manifest['native_max_tokens'] == 32768
    assert manifest['call_cap'] == manifest['agent_max_calls'] == 24
    assert manifest['author_mode'] == 'original_plan'
    assert 'provider' not in manifest
    assert len(manifest['plan']) == 2
    assert all(entry['runtime'] == 'deepseek_harness' and entry['mode'] == 'live_author'
               for entry in manifest['plan'])
    assert {case['language'] for case in cases.values()} == {'en', 'zh'}
    assert manifest['frozen_cases_sha256'] == experiment.digest(cases)
    planner_snapshot = output / 'code/app/question_planning.py'
    assert planner_snapshot.is_file()
    assert manifest['code_sha256']['app/question_planning.py'] == hashlib.sha256(planner_snapshot.read_bytes()).hexdigest()
    assert (output / 'code/scripts/harness_correctness_experiment.py').is_file()
    assert summary['planned_tasks'] == 2 and summary['recorded_tasks'] == 0
    assert summary['actual_calls'] == 0
    assert not (output / 'runtime').exists()
    assert not (output / 'results.json').exists()


@pytest.mark.parametrize('option,value', [
    ('--questions-per-case', '0'), ('--questions-per-case', '5'),
    ('--questions-per-case', '2.5'), ('--questions-per-case', 'unbounded'),
    ('--plan-batch-size', '0'), ('--plan-batch-size', '11'),
    ('--plan-batch-size', '1.5'), ('--plan-batch-size', 'unbounded'),
    ('--max-output-tokens', '32769'), ('--orchestration', 'arbitrary_agent'),
])
def test_invalid_supervisor_cli_limits_fail_before_configuration(option, value, monkeypatch):
    forbid_runtime_loading(monkeypatch)
    with pytest.raises(SystemExit):
        experiment.parser().parse_args([option, value])


def test_existing_experiment_defaults_remain_sequential_single_question():
    args = experiment.parser().parse_args([])
    assert args.orchestration == 'sequential_v1'
    assert args.questions_per_case == 1 and args.plan_batch_size == 8
    assert args.max_output_tokens == 4096


@pytest.mark.parametrize('runtime', ['native', 'both'])
def test_supervisor_rejects_unsupported_runtime_before_creating_output(tmp_path, monkeypatch, runtime):
    forbid_runtime_loading(monkeypatch)
    output = tmp_path / 'must-not-exist'
    args = supervisor_args(output, '--runtime', runtime)
    with pytest.raises(ValueError, match='require the Harness runtime'):
        asyncio.run(experiment.run(args))
    assert not output.exists()


@pytest.mark.parametrize('case', ['canary_bad', 'canary_corrected', 'all'])
def test_multi_question_injection_is_rejected_before_output_or_credentials(tmp_path, monkeypatch, case):
    forbid_runtime_loading(monkeypatch)
    output = tmp_path / 'must-not-exist'
    args = supervisor_args(output, '--cases', case, '--questions-per-case', '2')
    with pytest.raises(ValueError, match='Multi-question sets require fresh author cases'):
        asyncio.run(experiment.run(args))
    assert not output.exists()


def test_multi_question_replay_is_rejected_before_reading_archive_or_credentials(tmp_path, monkeypatch):
    forbid_runtime_loading(monkeypatch)
    output = tmp_path / 'must-not-exist'
    args = supervisor_args(output, '--questions-per-case', '2', '--question-spec', 'cpu_schedule_v1',
                           '--replay-specs', str(tmp_path / 'nonexistent-archive'))
    with pytest.raises(ValueError, match='Multi-question sets require fresh author cases'):
        asyncio.run(experiment.run(args))
    assert not output.exists()


def test_fake_live_supervisor_propagates_count_sources_scope_and_budget(tmp_path, monkeypatch):
    original = Settings(text=Endpoint('https://fixture.invalid/v1', 'supervisor-fixture-not-a-real-key',
        'fixture-exact-model', '/chat/completions', {
            'thinking': {'type': 'disabled'}, 'reasoning_effort': 'off',
            'temperature': 0.2, 'private_unknown': 'private-fixture-setting',
        }), agent_orchestration='sequential_v1', agent_plan_batch_size=8, text_json_mode=False)
    original_before = deepcopy(original)
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: original))
    provider_settings, executions, closed = [], [], []

    class FakeProviders:
        def __init__(self, settings, store):
            self.settings = settings
            provider_settings.append(settings)

        async def close(self):
            closed.append(self.settings.agent_runtime)

    class FakePipeline:
        def __init__(self, settings, store, providers, *, fixture=None, fixture_origin=None):
            self.settings, self.store = settings, store
            assert providers.settings is settings
            assert fixture is None and fixture_origin is None

        async def run(self, job_id):
            job = self.store.one('SELECT * FROM jobs WHERE id=?', (job_id,))
            request = GenerateRequest.model_validate_json(job['payload'])
            sources, trace = await self.retrieve(request, job_id, with_trace=True)
            for source in sources:
                document = self.store.one('SELECT * FROM documents WHERE id=?', (source['document_id'],))
                assert document['course_id'] == request.course_id == experiment.COURSE_ID
                assert document['status'] == 'indexed'
            executions.append({'request': request, 'sources': deepcopy(sources), 'trace': trace,
                               'settings': self.settings})
            self.store.execute("UPDATE jobs SET status='failed',error='offline supervisor fixture' WHERE id=?", (job_id,))

    monkeypatch.setattr(experiment, 'ApiProviders', FakeProviders)
    monkeypatch.setattr(experiment, 'ExperimentPipeline', FakePipeline)
    output = tmp_path / 'fake-live-supervisor'
    args = supervisor_args(output, '--live', '--questions-per-case', '4', '--plan-batch-size', '2',
        '--max-output-tokens', '32768', '--question-spec', 'cpu_schedule_v1', '--thinking', 'high',
        '--response-format', 'json_object', '--schema-repairs', '1', '--call-cap', '24',
        '--harness-max-requests', '3')

    assert asyncio.run(experiment.run(args)) == output
    assert len(provider_settings) == len(executions) == 2
    assert closed == ['deepseek_harness', 'deepseek_harness']
    frozen = json.loads((output / 'frozen_cases.json').read_text())
    for item in executions:
        settings, request, trace = item['settings'], item['request'], item['trace']
        assert settings.agent_runtime == 'deepseek_harness'
        assert settings.agent_orchestration == 'supervisor_v1'
        assert settings.agent_plan_batch_size == 2
        assert settings.agent_question_spec == 'cpu_schedule_v1'
        assert settings.generation_workflow == 'agent_v1'
        assert settings.harness_max_output_tokens == settings.text.extra['max_tokens'] == 32768
        assert settings.harness_max_requests == 3
        assert settings.agent_max_calls == settings.max_daily_calls == 24
        assert settings.agent_max_repairs == 1
        assert settings.harness_reasoning_effort == 'high'
        assert settings.harness_response_format == 'json_object'
        assert settings.harness_schema_repairs == 1 and settings.text_json_mode is True
        assert settings.text.extra['thinking'] == {'type': 'enabled'}
        assert settings.text.extra['reasoning_effort'] == 'high'
        assert settings.text.model == 'fixture-exact-model'
        assert settings.data_dir == output / 'runtime'
        assert request.count == 4 and request.question_type == 'short_answer'
        assert request.difficulty == 'hard'
        assert trace['mode'] == 'frozen_fixture_context' and trace['api_calls'] == 0
        assert item['sources'] == frozen[trace['case_id']]['sources']
        assert trace['source_sha256'] == experiment.digest(item['sources'])
        assert settings is not original and settings.text is not original.text
    assert {item['request'].language for item in executions} == {'en', 'zh'}
    assert original == original_before
    manifest_text = (output / 'manifest.json').read_text()
    manifest = json.loads(manifest_text)
    assert manifest['orchestration'] == 'supervisor_v1'
    assert manifest['questions_per_case'] == 4 and manifest['plan_batch_size'] == 2
    assert manifest['provider']['model'] == 'fixture-exact-model'
    assert manifest['provider']['public_parameters'] == {
        'temperature': 0.2, 'max_tokens': 32768, 'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high',
    }
    assert 'supervisor-fixture-not-a-real-key' not in manifest_text
    assert 'private-fixture-setting' not in manifest_text
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['actual_calls'] == 0 and summary['recorded_tasks'] == 2
    for row in json.loads((output / 'results.json').read_text()):
        assert row['actual_calls'] == 0 and row['calls'] == []
        saved = json.loads((output / row['evidence_file']).read_text())
        assert json.loads(saved['job']['payload'])['count'] == 4
        assert saved['evidence']['experiment']['author_injected'] is False
        assert saved['calls'] == []
