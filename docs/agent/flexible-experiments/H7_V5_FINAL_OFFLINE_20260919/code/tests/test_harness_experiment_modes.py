"""Offline safeguards for thinking/JSON experiments and frozen-spec replay."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from app.config import Endpoint, Settings
from app.cpu_problem_spec import compile_cpu_spec
from app.generation_agent import authorize_resume, fingerprint
from scripts import harness_correctness_experiment as experiment
from test_generation_agent import agent_case
from test_harness_experiment import seed_interrupted_checkpoint


@pytest.mark.parametrize('value', ['255', '32769', '1.5', 'unbounded'])
def test_experiment_rejects_invalid_output_budget_before_loading_settings(value, monkeypatch):
    no_configuration_loading(monkeypatch)
    with pytest.raises(SystemExit):
        experiment.parser().parse_args(['--max-output-tokens', value])


@pytest.mark.parametrize('value,expected', [('1', 256), ('16384', 16384), ('999999', 32768)])
def test_harness_env_output_budget_remains_bounded(monkeypatch, value, expected):
    import os
    import dotenv
    monkeypatch.setattr(os, 'environ', {'HARNESS_MAX_OUTPUT_TOKENS': value})
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args, **kwargs: None)
    assert Settings.from_env().harness_max_output_tokens == expected


def test_larger_thinking_budget_is_explicit_and_default_is_unchanged():
    assert experiment.parser().parse_args([]).max_output_tokens == 4096
    assert experiment.parser().parse_args(['--max-output-tokens', '16384']).max_output_tokens == 16384


def seed_replay(tmp_path, requested=('cpu_en_hard', 'cpu_zh_hard')):
    """Build archived-shaped fixtures locally, independent of prior live runs."""
    plan = experiment.build_plan(list(requested), 'deepseek_harness')
    dataset = json.loads((experiment.ROOT / 'benchmarks/difficulty/cases.json').read_text())
    cases = experiment.frozen_cases(dataset, plan)
    directory = tmp_path / 'replay-source'
    directory.mkdir()
    records = {}
    for entry in plan:
        case = cases[entry['case_id']]
        proposal = {'evidence_sufficient': True, 'citation_ids': [case['sources'][0]['id']],
            'spec': {'processes': [{'id': 'A', 'arrival': 0, 'burst': 4},
                                   {'id': 'B', 'arrival': 1, 'burst': 2}],
                     'scenarios': [{'id': 'STCF', 'policy': 'stcf'}]}}
        compiled = compile_cpu_spec(proposal['spec'], language=case['language'],
            difficulty=case['target_difficulty'], source_ids=proposal['citation_ids'])
        asset = {'title': case['topic'], 'evidence_sufficient': True,
            'learning_objectives': compiled.get('learning_objectives', []),
            'sections': [compiled['section']], 'questions': [compiled['question']], 'visual_prompt': ''}
        record = {'evidence': {'sources': deepcopy(case['sources']), 'agent': {'slots': [
            {'attempts': [{'author': {'response': deepcopy(proposal)},
                           'compiled_spec': compiled['evidence'],
                           'compiled_asset_sha256': fingerprint(asset)}]}]}}}
        path = directory / (entry['task_id'] + '.json')
        path.write_text(json.dumps(record, ensure_ascii=False))
        records[entry['task_id']] = (path, record, compiled)
    return directory, plan, cases, records


def no_configuration_loading(monkeypatch):
    def forbidden(cls):
        pytest.fail('Planning/replay validation must not load credentials.')
    monkeypatch.setattr(Settings, 'from_env', classmethod(forbidden))


def test_high_json_replay_dry_run_freezes_bilingual_proposals_and_provenance(tmp_path, monkeypatch):
    directory, plan, cases, records = seed_replay(tmp_path)
    no_configuration_loading(monkeypatch)
    output = tmp_path / 'planned'
    args = experiment.parser().parse_args([
        '--runtime', 'deepseek_harness', '--cases', 'cpu_en_hard', 'cpu_zh_hard',
        '--question-spec', 'cpu_schedule_v1', '--thinking', 'high',
        '--response-format', 'json_object', '--schema-repairs', '1', '--replay-specs', str(directory),
        '--output', str(output),
    ])
    assert asyncio.run(experiment.run(args)) == output
    manifest = json.loads((output / 'manifest.json').read_text())
    frozen = json.loads((output / 'replay_inputs.json').read_text())
    assert manifest['live'] is False
    assert manifest['reasoning_effort'] == 'high'
    assert manifest['shared_thinking'] == {'type': 'enabled'}
    assert manifest['response_format'] == 'json_object'
    assert manifest['schema_repairs'] == 1
    assert manifest['author_mode'] == 'frozen_spec_replay'
    assert manifest['spec_replay_sha256'] == experiment.digest(frozen)
    assert all(entry['mode'] == 'injected_spec' for entry in manifest['plan'])
    assert json.loads((output / 'frozen_cases.json').read_text()) == cases
    assert json.loads((output / 'summary.json').read_text())['actual_calls'] == 0
    assert not (output / 'runtime').exists()
    for entry in plan:
        path, record, compiled = records[entry['task_id']]
        item = frozen[entry['task_id']]
        assert item['response'] == record['evidence']['agent']['slots'][0]['attempts'][0]['author']['response']
        assert item['origin'] == {
            'kind': 'injected_frozen_cpu_spec', 'api_call_performed': False,
            'source_file': str(path.resolve()),
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'spec_sha256': compiled['evidence']['spec_sha256'],
            'compiled_asset_sha256': record['evidence']['agent']['slots'][0]['attempts'][0]['compiled_asset_sha256'],
            'compiled_question_sha256': experiment.digest(compiled['question']),
        }
        # A later change to the source archive must not mutate the experiment's
        # frozen proposal: its own inputs and provenance remain inspectable.
        path.write_text('{}')
    assert json.loads((output / 'replay_inputs.json').read_text()) == frozen


@pytest.mark.parametrize('change,match', [
    ('references', 'references differ'),
    ('hash', 'compiler changed'),
    ('spec', 'compiler changed'),
    ('compiler_revision', 'compiler changed'),
    ('missing_compiled', 'no compiled CPU'),
    ('multiple_slots', 'single-question'),
    ('foreign_citation', 'valid supported references'),
    ('empty_citations', 'valid supported references'),
    ('insufficient_evidence', 'valid supported references'),
])
def test_invalid_replay_is_rejected_before_credentials_or_output_creation(tmp_path, monkeypatch, change, match):
    directory, _, _, records = seed_replay(tmp_path, ('cpu_en_hard',))
    no_configuration_loading(monkeypatch)
    path, record, _ = next(iter(records.values()))
    evidence = record['evidence']
    attempt = evidence['agent']['slots'][0]['attempts'][0]
    if change == 'references':
        evidence['sources'][0]['text'] += '\nChanged source content.'
    elif change == 'hash':
        attempt['compiled_spec']['spec_sha256'] = '0' * 64
    elif change == 'spec':
        attempt['author']['response']['spec']['processes'][0]['burst'] += 1
    elif change == 'compiler_revision':
        import app.cpu_problem_spec as compiler
        monkeypatch.setattr(compiler, 'CPU_SPEC_REVISION', 'different-compiler-fixture')
    elif change == 'missing_compiled':
        del attempt['compiled_spec']
    elif change == 'multiple_slots':
        evidence['agent']['slots'].append(deepcopy(evidence['agent']['slots'][0]))
    elif change == 'foreign_citation':
        attempt['author']['response']['citation_ids'] = ['unrelated-source']
    elif change == 'empty_citations':
        attempt['author']['response']['citation_ids'] = []
    else:
        attempt['author']['response']['evidence_sufficient'] = False
    path.write_text(json.dumps(record))
    before = path.read_bytes()
    output = tmp_path / 'must-not-be-created'
    args = experiment.parser().parse_args([
        '--runtime', 'deepseek_harness', '--cases', 'cpu_en_hard',
        '--question-spec', 'cpu_schedule_v1', '--replay-specs', str(directory),
        '--output', str(output),
    ])
    with pytest.raises(ValueError, match=match):
        asyncio.run(experiment.run(args))
    assert not output.exists()
    assert path.read_bytes() == before


@pytest.mark.parametrize('changed_part', ['answer', 'section'])
def test_replay_rejects_changed_compiler_output_even_with_unchanged_revision_and_spec_hash(
        tmp_path, monkeypatch, changed_part):
    directory, plan, cases, records = seed_replay(tmp_path, ('cpu_en_hard',))
    no_configuration_loading(monkeypatch)
    path, record, _ = next(iter(records.values()))
    frozen_spec_hash = record['evidence']['agent']['slots'][0]['attempts'][0]['compiled_spec']['spec_sha256']
    import app.cpu_problem_spec as compiler
    original_compile = compiler.compile_cpu_spec

    def changed_compiler(*args, **kwargs):
        compiled = original_compile(*args, **kwargs)
        assert compiled['evidence']['spec_sha256'] == frozen_spec_hash
        if changed_part == 'answer':
            compiled['question']['answer'] += '\nChanged numeric answer: 99.'
        else:
            compiled['section']['heading'] += ' Changed rendering.'
        return compiled

    monkeypatch.setattr(compiler, 'compile_cpu_spec', changed_compiler)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='rendering or calculation changed'):
        experiment.replay_spec_fixtures(directory, cases, plan)
    assert path.read_bytes() == before


def test_replay_without_structured_question_mode_is_rejected_before_loading_settings(tmp_path, monkeypatch):
    no_configuration_loading(monkeypatch)
    args = experiment.parser().parse_args([
        '--replay-specs', str(tmp_path / 'unused'), '--output', str(tmp_path / 'unused-output')])
    with pytest.raises(ValueError, match='requires --question-spec'):
        asyncio.run(experiment.run(args))
    assert not (tmp_path / 'unused-output').exists()


def test_high_json_live_branch_uses_local_settings_and_records_exact_public_configuration(tmp_path, monkeypatch):
    original = Settings(text=Endpoint('https://fixture.invalid/v1', 'not-a-real-key',
        'fixture-exact-model', '/chat/completions', {
            'thinking': {'type': 'disabled'}, 'reasoning_effort': 'off',
            'temperature': 0.2, 'private_unknown': 'do-not-persist-this',
        }), text_json_mode=False)
    original_before = deepcopy(original)
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: original))
    seen, closed = [], []

    class FakeProviders:
        def __init__(self, settings, store):
            self.settings = settings
            seen.append(settings)
        async def close(self):
            closed.append(self.settings.agent_runtime)

    class FakePipeline:
        def __init__(self, settings, store, providers, **kwargs):
            self.store = store
        async def run(self, job_id):
            self.store.execute("UPDATE jobs SET status='failed',error='offline fixture' WHERE id=?", (job_id,))

    monkeypatch.setattr(experiment, 'ApiProviders', FakeProviders)
    monkeypatch.setattr(experiment, 'ExperimentPipeline', FakePipeline)
    output = tmp_path / 'fake-live'
    args = experiment.parser().parse_args([
        '--live', '--cases', 'canary_bad', '--thinking', 'high',
        '--response-format', 'json_object', '--schema-repairs', '1',
        '--max-output-tokens', '6144', '--output', str(output),
    ])
    asyncio.run(experiment.run(args))
    assert [settings.agent_runtime for settings in seen] == ['native', 'deepseek_harness']
    assert closed == ['native', 'deepseek_harness']
    for settings in seen:
        assert settings.harness_reasoning_effort == 'high'
        assert settings.harness_response_format == 'json_object'
        assert settings.harness_schema_repairs == 1
        assert settings.text_json_mode is True
        assert settings.text.extra['thinking'] == {'type': 'enabled'}
        assert settings.text.extra['reasoning_effort'] == 'high'
        assert settings.text.extra['max_tokens'] == settings.harness_max_output_tokens == 6144
        assert settings.text.model == 'fixture-exact-model'
        assert settings is not original and settings.text is not original.text
    assert original == original_before
    manifest_text = (output / 'manifest.json').read_text()
    manifest = json.loads(manifest_text)
    assert manifest['reasoning_effort'] == 'high'
    assert manifest['shared_thinking'] == {'type': 'enabled'}
    assert manifest['response_format'] == 'json_object'
    assert manifest['schema_repairs'] == 1
    assert manifest['provider']['model'] == 'fixture-exact-model'
    assert manifest['provider']['public_parameters'] == {
        'temperature': 0.2, 'max_tokens': 6144, 'thinking': {'type': 'enabled'},
        'reasoning_effort': 'high',
    }
    assert 'not-a-real-key' not in manifest_text and 'do-not-persist-this' not in manifest_text
    assert json.loads((output / 'summary.json').read_text())['actual_calls'] == 0


@pytest.mark.parametrize('field,initial,changed', [
    ('harness_reasoning_effort', 'off', 'high'),
    ('harness_reasoning_effort', 'high', 'off'),
    ('harness_response_format', 'text', 'json_object'),
    ('harness_response_format', 'json_object', 'text'),
    ('harness_schema_repairs', 0, 1),
    ('harness_schema_repairs', 1, 0),
])
def test_resume_cannot_mix_thinking_or_output_modes(agent_case, monkeypatch, field, initial, changed):
    rig = agent_case(count=2, settings_options={'agent_runtime': 'deepseek_harness', field: initial})
    _, before, retrievals = seed_interrupted_checkpoint(rig, monkeypatch)
    authorize_resume(rig.store, rig.job_id)
    setattr(rig.settings, field, changed)
    assert rig.run()['status'] == 'failed'
    assert '配置已改变' in rig.job()['error']
    after = rig.evidence()
    assert after['configuration'] == before['configuration']
    assert after['agent']['slots'] == before['agent']['slots']
    assert after['agent']['call_count'] == 7
    assert after['agent']['resume_count'] == 1
    assert len(retrievals) == 1
    assert rig.text_call_count() == 0 and rig.wire.contracts == []
