"""Offline planning, accounting and evidence preservation for H7."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from app.config import Endpoint, Settings
from app.store import dumps, now
from scripts import flexible_answer_experiment as experiment


def forbid_env(monkeypatch):
    def forbidden(cls):
        pytest.fail('The plan must not load provider configuration or credentials.')
    monkeypatch.setattr(Settings, 'from_env', classmethod(forbidden))


def test_dry_plan_freezes_all_cases_code_and_budgets_without_credentials(tmp_path, monkeypatch):
    forbid_env(monkeypatch)
    monkeypatch.setattr(experiment, 'ApiProviders', lambda *a, **k: pytest.fail('No dry-run provider'))
    output = tmp_path / 'dry'
    args = experiment.parser().parse_args(['--questions-per-case', '2', '--output', str(output)])
    assert asyncio.run(experiment.run(args)) == output
    manifest = json.loads((output / 'manifest.json').read_text())
    summary = json.loads((output / 'summary.json').read_text())
    assert manifest['live'] is False
    assert manifest['orchestration'] == 'supervisor_v2'
    assert manifest['call_cap'] == 24 and manifest['agent_max_calls'] == 16
    assert manifest['harness_max_output_tokens'] == 32768
    assert manifest['harness_max_requests'] == 4
    assert manifest['reasoning_effort'] == 'high' and manifest['schema_repairs'] == 1
    assert summary['planned_tasks'] == 3 and summary['planned_questions'] == 6
    assert summary['actual_calls'] == summary['published_questions'] == 0
    assert json.loads((output / 'results.json').read_text()) == []
    assert not (output / 'runtime').exists()
    assert [row['question_spec'] for row in manifest['plan']] == ['none', 'none', 'cpu_schedule_v1']
    assert 'app/cpu_problem_spec.py' in manifest['code_sha256']
    assert 'app/generation_agent.py' in manifest['code_sha256']
    assert 'app/assessment_contracts.py' in manifest['code_sha256']
    assert manifest['flexible_planner_revision'] == experiment.FLEXIBLE_PLANNER_REVISION
    assert manifest['assessment_plan_schema_sha256'] and manifest['requirement_check_schema_sha256']
    for relative, expected in manifest['code_sha256'].items():
        assert hashlib.sha256((output / 'code' / relative).read_bytes()).hexdigest() == expected
        assert '.env' not in relative
    assert experiment.digest(json.loads((output / 'frozen_cases.json').read_text())) == manifest['frozen_cases_sha256']


def test_case_selection_is_exact_and_deduplicated():
    assert experiment.select_cases(['cpu_en,humanities_zh', 'cpu_en']) == ['humanities_zh', 'cpu_en']
    for requested in (['all'], ['unknown'], [' , ']):
        with pytest.raises(ValueError):
            experiment.select_cases(requested)


@pytest.mark.parametrize('arguments', [
    ['--call-cap', '0'], ['--call-cap', '33'], ['--questions-per-case', '0'],
    ['--questions-per-case', '3'], ['--questions-per-case', '1.5'],
])
def test_cli_rejects_out_of_range_budgets(arguments, monkeypatch):
    forbid_env(monkeypatch)
    with pytest.raises(SystemExit):
        experiment.parser().parse_args(arguments)


def test_existing_output_and_unknown_cases_are_rejected_without_loading_settings(tmp_path, monkeypatch):
    forbid_env(monkeypatch)
    output = tmp_path / 'existing'
    output.mkdir()
    (output / 'keep.txt').write_text('untouched')
    with pytest.raises(FileExistsError):
        asyncio.run(experiment.run(experiment.parser().parse_args(['--output', str(output)])))
    assert (output / 'keep.txt').read_text() == 'untouched'
    unused = tmp_path / 'unused'
    with pytest.raises(ValueError):
        asyncio.run(experiment.run(experiment.parser().parse_args(['--cases', 'other', '--output', str(unused)])))
    assert not unused.exists()


def test_fictional_provenance_and_existing_cpu_sources_are_preserved():
    cases, hashes = experiment.frozen_cases(None)
    assert set(cases) == set(experiment.CASE_IDS)
    for case_id in ('humanities_zh', 'humanities_en'):
        case = cases[case_id]
        assert case['provenance']['fictional_people_places_and_events'] is True
        assert case['provenance']['original_source_excerpt'] is False
        assert case['provenance']['human_gold_answer'] is False
        assert case['provenance']['source_references'] == []
        assert len(case['sources']) == 3
        assert all(source['page'] is None for source in case['sources'])
    old = json.loads((experiment.ROOT / 'benchmarks/difficulty/cases.json').read_text())
    original = next(case for case in old['cases'] if case['id'] == 'cpu_scheduling_en_hard')
    assert cases['cpu_en']['origin_case_id'] == original['id']
    assert cases['cpu_en']['provenance'] == original['provenance']
    assert [{key: value for key, value in source.items() if key != 'document_id'}
            for source in cases['cpu_en']['sources']] == original['sources']
    assert cases['cpu_en']['origin_dataset_sha256'] == hashes['difficulty_cases']


def sample_evidence(count=1):
    return {'schema_version': 'education-agent-v1', 'agent': {'status': 'completed', 'slots': [
        {'slot_id': f'q{index+1}', 'status': 'passed', 'brief': {'requirements': [{'id': 'r1', 'description': 'Explain evidence.'}]},
         'attempts': [
             {'number': 1, 'status': 'quality_failed',
              'feedback': {'repair_target': 'narrative'},
              'quality_checks': {'requirements': {'status': 'failed', 'issues': ['requirement_coverage:r1:partial'],
                                                 'checks': [{'id': 'r1', 'status': 'partial'}]}},
              'review': {'response': {'requirement_checks': [{'id': 'r1', 'status': 'partial'}]}}},
             {'number': 2, 'status': 'passed', 'author': {'origin': 'reused_frozen_spec'},
              'compiled_asset_sha256': 'base-sha', 'composed_asset_sha256': 'composed-sha',
              'quality_checks': {'requirements': {'status': 'passed', 'issues': [],
                                                  'checks': [{'id': 'r1', 'status': 'met'}]}},
              'review': {'response': {'unexpected_schema_field': True}},
              'review_schema_repair': {'response': {'requirement_checks': [{'id': 'r1', 'status': 'met'}]}}},
         ]} for index in range(count)]}}


def test_requirement_audit_uses_schema_repair_and_keeps_rejected_attempts():
    evidence = sample_evidence()
    before = deepcopy(evidence)
    records = experiment.question_records(evidence)
    assert evidence == before
    assert records[0]['requirements_status'] == 'passed'
    assert records[0]['attempt_count'] == 2
    assert records[0]['attempts'][0]['requirements']['issues'] == ['requirement_coverage:r1:partial']
    assert records[0]['attempts'][1]['requirement_checks'] == [{'id': 'r1', 'status': 'met'}]
    assert records[0]['attempts'][0]['repair_target'] == 'narrative'
    assert records[0]['attempts'][1]['author_origin'] == 'reused_frozen_spec'
    assert records[0]['attempts'][1]['compiled_asset_sha256'] == 'base-sha'


def test_requirement_audit_prefers_evidence_repair_and_preserves_validation_status():
    evidence = sample_evidence()
    attempt = evidence['agent']['slots'][0]['attempts'][-1]
    attempt['review_evidence_repair'] = {'status': 'validated', 'response': {
        'requirement_checks': [{'id': 'r1', 'status': 'met', 'explanation': 'Final evidence review.'}]}}
    record = experiment.question_records(evidence)[0]['attempts'][-1]
    assert record['requirement_checks'][0]['explanation'] == 'Final evidence review.'
    assert record['final_review_phase'] == 'review_evidence_repair'
    assert record['final_review_phase_status'] == 'validated'
    attempt['review_evidence_repair']['status'] = 'failed'
    assert experiment.question_records(evidence)[0]['attempts'][-1]['final_review_phase_status'] == 'failed'


def test_summary_retains_planned_denominator_and_missing_costs_as_unknown():
    rows = [{'id': 'humanities_zh', 'status': 'failed', 'planned_questions': 2,
             'accepted_questions': 1, 'published_questions': 0,
             'questions': experiment.question_records(sample_evidence()),
             'calls': [{'status': 'succeeded', 'usage': {'total_tokens': 30}},
                       {'status': 'failed', 'usage': {'total_tokens': None, 'cost': None}}]}]
    summary = experiment.summarize(rows, [{'question_count': 2}, {'question_count': 2}])
    assert summary['planned_questions'] == 4 and summary['recorded_tasks'] == 1
    assert summary['accepted_questions'] == 1 and summary['published_questions'] == 0
    assert summary['actual_calls'] == 2 and summary['known_total_tokens'] == 30
    assert summary['tokens_missing_calls'] == 1 and summary['total_tokens'] is None
    assert summary['cost_missing_calls'] == 2 and summary['total_cost_usd'] is None
    assert summary['requirement_verdict_counts_all_attempts'] == {'partial': 1, 'met': 1}
    assert summary['requirements_status_counts'] == {'passed': 1}


def fake_live(monkeypatch, *, crash=False, publish=True):
    base = Settings(text=Endpoint('https://fixture.invalid/v1', 'not-a-real-private-key', 'fixture-flash',
                                  '/chat/completions', {'private_field': 'do-not-archive', 'thinking': {'type': 'disabled'}}))
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: base))
    seen = []

    class FakeProviders:
        def __init__(self, settings, store):
            self.closed = False
            seen.append(self)
            self.settings = settings
        async def close(self):
            self.closed = True

    class FakePipeline:
        def __init__(self, settings, store, providers, **kwargs):
            self.settings, self.store = settings, store
            assert kwargs == {'enforce_account_ownership': False}
        async def run(self, job_id):
            request = json.loads(self.store.one('SELECT payload FROM jobs WHERE id=?', (job_id,))['payload'])
            sources, trace = await self.retrieve(None, job_id)
            assert trace['api_calls'] == 0
            assert all(self.store.one('SELECT * FROM documents WHERE id=?', (s['document_id'],)) for s in sources)
            call_id = self.store.reserve_call(job_id, 'text', 'fixture-flash', 100)
            self.store.execute("UPDATE calls SET status='succeeded',usage=? WHERE id=?", (dumps({'total_tokens': 10}), call_id))
            self.store.save_job_evidence(job_id, sample_evidence(request['count']))
            if crash:
                raise KeyboardInterrupt('Do not persist arbitrary exception messages.')
            if publish:
                asset = {'questions': [{'slot_id': f'q{index+1}'} for index in range(request['count'])]}
                self.store.execute('INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)',
                                   ('content-'+job_id, experiment.COURSE_ID, job_id, 1, 'draft',
                                    dumps(asset), dumps(sources), '{}', now()))
            self.store.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (job_id,))

    monkeypatch.setattr(experiment, 'ApiProviders', FakeProviders)
    monkeypatch.setattr(experiment, 'Pipeline', FakePipeline)
    return base, seen


def test_mocked_live_execution_is_isolated_and_cpu_uses_hybrid_path(tmp_path, monkeypatch):
    base, seen = fake_live(monkeypatch)
    output = tmp_path / 'mock-live'
    args = experiment.parser().parse_args(['--live', '--questions-per-case', '2', '--output', str(output)])
    asyncio.run(experiment.run(args))
    assert len(seen) == 3 and all(item.closed for item in seen)
    for item in seen:
        settings = item.settings
        assert settings.data_dir == output / 'runtime'
        assert settings.agent_orchestration == 'supervisor_v2'
        assert settings.agent_runtime == 'deepseek_harness'
        assert settings.text.extra['thinking'] == {'type': 'enabled'}
        assert settings.text.extra['reasoning_effort'] == 'high'
        assert settings.text.extra['max_tokens'] == settings.harness_max_output_tokens == 32768
        assert settings.harness_schema_repairs == settings.agent_max_repairs == 1
        assert settings.agent_max_calls == 16
    assert [item.settings.agent_question_spec for item in seen] == ['none', 'none', 'cpu_schedule_v1']
    assert base.text.extra['thinking'] == {'type': 'disabled'}
    manifest_text = (output / 'manifest.json').read_text()
    assert 'not-a-real-private-key' not in manifest_text and 'do-not-archive' not in manifest_text
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['actual_calls'] == 3
    assert summary['planned_questions'] == summary['accepted_questions'] == summary['published_questions'] == 6
    assert summary['requirements_status_counts'] == {'passed': 6}
    assert summary['attempts'] == 12
    assert summary['total_cost_usd'] is None


def test_success_status_without_persisted_content_is_not_counted_as_published(tmp_path, monkeypatch):
    fake_live(monkeypatch, publish=False)
    output = tmp_path / 'missing-content'
    asyncio.run(experiment.run(experiment.parser().parse_args([
        '--live', '--cases', 'cpu_en', '--output', str(output)])))
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['accepted_questions'] == 1 and summary['published_questions'] == 0


def test_global_cap_keeps_unrun_cases_in_denominator(tmp_path, monkeypatch):
    _, seen = fake_live(monkeypatch)
    output = tmp_path / 'cap'
    asyncio.run(experiment.run(experiment.parser().parse_args(['--live', '--call-cap', '1', '--output', str(output)])))
    summary = json.loads((output / 'summary.json').read_text())
    assert len(seen) == summary['actual_calls'] == 1
    assert summary['planned_questions'] == summary['recorded_tasks'] == 3
    assert summary['status_counts'] == {'succeeded': 1, 'not_run_budget_exhausted': 2}
    assert summary['published_questions'] == 1
    for case_id in ('humanities_en', 'cpu_en'):
        archive = json.loads((output / f'supervisor_v2__{case_id}.json').read_text())
        assert archive['job'] is None and archive['calls'] == []


def test_interruption_preserves_partial_calls_and_attempts_before_reraising(tmp_path, monkeypatch):
    _, seen = fake_live(monkeypatch, crash=True)
    output = tmp_path / 'interrupted'
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(experiment.run(experiment.parser().parse_args(['--live', '--output', str(output)])))
    assert len(seen) == 1 and seen[0].closed
    summary = json.loads((output / 'summary.json').read_text())
    rows = json.loads((output / 'results.json').read_text())
    assert summary['actual_calls'] == 1 and summary['planned_questions'] == 3
    assert summary['published_questions'] == 0 and summary['attempts'] == 2
    assert rows[0]['interrupted_type'] == 'KeyboardInterrupt'
    assert 'Do not persist arbitrary exception messages' not in (output / 'results.json').read_text()


def test_failed_calls_consume_global_cap_even_after_date_change(tmp_path):
    store = experiment.CappedStore(tmp_path / 'runtime', 1)
    job, _ = store.job('offline', 'generate', {})
    call_id = store.reserve_call(job['id'], 'text', 'fixture', 100)
    store.execute("UPDATE calls SET status='failed',created_at='2000-01-01T00:00:00' WHERE id=?", (call_id,))
    with pytest.raises(ValueError, match='cap reached'):
        store.reserve_call(job['id'], 'text', 'fixture', 100)
