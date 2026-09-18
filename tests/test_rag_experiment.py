"""Runner contracts on tiny test-only data; never loads the pilot or calls an API."""
import asyncio
from copy import deepcopy
import csv
import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from app.config import Endpoint, Settings
from app.providers import ApiProviders, ProviderError
from scripts import rag_experiment as experiment

ARCHIVED_CODE_FILES = experiment.CODE_FILES


@pytest.fixture
def dataset():
    return {
        'schema_version': 'rag-benchmark-v1', 'dataset_id': 'runner-unit-fixture',
        'label_status': 'assistant_authored_unreviewed',
        'documents': [
            {'id': 'a', 'text': 'alpha concept'},
            {'id': 'b', 'text': 'beta method'},
            {'id': 'c', 'text': 'gamma context'},
        ],
        'queries': [
            {'id': 'qa', 'text': 'alpha', 'split': 'dev', 'category': 'definition', 'language': 'en',
             'family_id': 'alpha', 'answerable': True, 'relevance': {'a': 2}},
            {'id': 'qb', 'text': 'beta', 'split': 'test', 'category': 'definition', 'language': 'en',
             'family_id': 'beta', 'answerable': True, 'relevance': {'b': 2}},
            {'id': 'qn', 'text': 'unrelated', 'split': 'test', 'category': 'unanswerable', 'language': 'en',
             'family_id': 'absent', 'answerable': False, 'relevance': {}},
        ],
    }


@pytest.fixture
def cache(dataset):
    # This is explicitly a unit-test record, not real experimental evidence.
    return {
        'schema_version': 'rag-embedding-cache-v1', 'status': 'complete',
        'source': 'live_provider', 'model': 'test-only-vector-fixture',
        'embedding_signature': 'test-only-provider-signature', 'dimensions': 2,
        'input_format': experiment.INPUT_FORMAT, 'input_sha256': experiment.input_hash(dataset),
        'documents': {'a': [1., 0.], 'b': [0., 1.], 'c': [-1., 0.]},
        'queries': {'qa': [1., 0.], 'qb': [0., 1.], 'qn': [1., 1.]},
        'test_fixture': True,
    }


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def cli_files(dataset, cache, tmp_path, monkeypatch):
    dataset_path = tmp_path / 'dataset.json'
    cache_path = tmp_path / 'cache.json'
    protocol = tmp_path / 'protocol.md'
    experiment.write_json(dataset_path, dataset)
    experiment.write_json(cache_path, cache)
    protocol.write_text('# Unit-test protocol\nFixed candidates; no provider network.\n')
    monkeypatch.setattr(experiment, 'PROTOCOL', protocol)
    # Keep source snapshots real while avoiding unrelated/changing source files.
    monkeypatch.setattr(experiment, 'CODE_FILES', ('scripts/rag_experiment.py', 'app/rag_evaluation.py', 'app/retrieval.py'))
    output = tmp_path / 'runs'
    return {'dataset': dataset_path, 'cache': cache_path, 'protocol': protocol, 'output': output}


def invoke_replay(monkeypatch, files, extra_args=()):
    monkeypatch.setattr(sys, 'argv', ['rag_experiment.py', '--dataset', str(files['dataset']),
                                    '--cache', str(files['cache']), '--output-dir', str(files['output']), *extra_args])
    return experiment.main()


def only_run(files):
    runs = [path for path in files['output'].iterdir() if path.is_dir()]
    assert len(runs) == 1
    return runs[0]


def forbid_provider_setup(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline replay must not load credentials or construct a provider.')
    monkeypatch.setattr(experiment.Settings, 'from_env', forbidden)
    monkeypatch.setattr(experiment, 'ApiProviders', forbidden)
    monkeypatch.setattr(experiment, 'embed_dataset', forbidden)


def test_cache_validates_identity_and_keeps_frozen_vectors_unchanged(dataset, cache):
    before = deepcopy(cache)
    assert experiment.validate_cache(cache, dataset) is cache
    assert cache == before
    changed = deepcopy(dataset)
    changed['queries'][0]['text'] += ' changed'
    with pytest.raises(ValueError, match='inputs'):
        experiment.validate_cache(cache, changed)
    changed = deepcopy(dataset)
    changed['documents'][0]['text'] += ' changed'
    with pytest.raises(ValueError, match='inputs'):
        experiment.validate_cache(cache, changed)


def test_embedding_input_hash_covers_input_order_and_format_but_not_qrel_reannotation(dataset, cache):
    changed = deepcopy(dataset)
    changed['queries'][0]['relevance']['a'] = 1
    assert experiment.input_hash(changed) == experiment.input_hash(dataset)
    assert experiment.digest(experiment.encoded(changed)) != experiment.digest(experiment.encoded(dataset))
    assert experiment.validate_cache(cache, changed) is cache
    changed['documents'].reverse()
    assert experiment.input_hash(changed) != experiment.input_hash(dataset)


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'wrong'), ('status', 'started'), ('source', 'mock'),
    ('input_format', 'other-query-instruction'), ('input_sha256', 'wrong'),
    ('model', ''), ('model', None), ('model', 12),
    ('embedding_signature', ' '), ('embedding_signature', None),
    ('dimensions', True), ('dimensions', 2.0), ('dimensions', 0), ('dimensions', 3),
])
def test_cache_rejects_missing_or_inconsistent_identity_and_strict_dimensions(dataset, cache, field, value):
    cache[field] = value
    with pytest.raises(ValueError):
        experiment.validate_cache(cache, dataset)


@pytest.mark.parametrize('mutation', [
    lambda value: value['documents'].pop('a'),
    lambda value: value['queries'].update(unknown=[1., 0.]),
    lambda value: value['queries'].update(qa=[1., 0., 0.]),
    lambda value: value['documents'].update(a=[0., 0.]),
    lambda value: value['documents'].update(a=[True, 0.]),
    lambda value: value['documents'].update(a=['1', '0']),
    lambda value: value['queries'].update(qa=[float('nan'), 0.]),
    lambda value: value['queries'].update(qa=[float('inf'), 0.]),
])
def test_cache_rejects_id_coverage_dimension_or_invalid_vector_content(dataset, cache, mutation):
    mutation(cache)
    with pytest.raises(ValueError):
        experiment.validate_cache(cache, dataset)


def test_cache_rejects_nonobject_record(dataset):
    with pytest.raises(ValueError, match='object'):
        experiment.validate_cache([], dataset)


def test_declared_strategy_parameters_match_every_actual_ranking_call(dataset, cache, monkeypatch):
    original = experiment.rank_chunks
    calls = []
    def observed(chunks, query, vector, **kwargs):
        calls.append(kwargs.copy())
        return original(chunks, query, vector, **kwargs)
    monkeypatch.setattr(experiment, 'rank_chunks', observed)
    runs, rankings, comparisons, failures = experiment.run_rankings(dataset, cache)
    assert not failures
    assert set(runs) == set(experiment.STRATEGIES)
    assert set(comparisons) == set(experiment.STRATEGIES) - {'dense_v1'}
    assert len(calls) == len(experiment.STRATEGIES) * len(dataset['queries']) * 4
    for call in calls:
        config = runs[call['strategy']]['configuration']
        for name, value in call.items():
            assert config[name] == value
    for strategy, selected in rankings.items():
        for query_id, rows in selected.items():
            assert len(rows) <= runs[strategy]['configuration']['top_k']
            assert all(row['retrieval']['strategy'] == strategy for row in rows)
            if strategy.startswith('hybrid') and query_id == 'qn':
                assert all(row['retrieval']['effective_strategy'] == 'dense_v1' for row in rows)
    assert rankings['bm25_v1']['qn'] == []


def test_offline_replay_writes_complete_tables_reports_and_auditable_hashes(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    assert invoke_replay(monkeypatch, cli_files) == 0
    run = only_run(cli_files)
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'completed'
    assert manifest['cache_replay'] is True
    assert manifest['new_api_attempts'] == 0
    assert manifest['expected_embedding_calls'] == 0
    assert manifest['human_review_performed_by_this_run'] is False
    assert json.loads((run / 'provider-calls.json').read_text()) == []
    assert (run / 'dataset.json').read_bytes() == cli_files['dataset'].read_bytes()
    assert manifest['dataset_sha256'] == experiment.digest(cli_files['dataset'].read_bytes())
    assert manifest['protocol_sha256'] == experiment.digest(cli_files['protocol'].read_bytes())
    assert manifest['embedding_cache_sha256'] == experiment.digest((run / 'embedding-cache.json').read_bytes())
    for name, expected_hash in manifest['source_code_sha256'].items():
        assert experiment.digest((run / 'code' / name).read_bytes()) == expected_hash
    for name, expected_hash in manifest['artifact_sha256'].items():
        assert experiment.digest((run / name).read_bytes()) == expected_hash
    metrics = json.loads((run / 'metrics.json').read_text())
    comparisons = json.loads((run / 'comparisons.json').read_text())
    table = read_csv(run / 'metrics.csv')
    per_query = read_csv(run / 'per-query.csv')
    changes = read_csv(run / 'changes.csv')
    annotations = read_csv(run / 'annotation-review.csv')
    assert len(per_query) == len(experiment.STRATEGIES) * 3
    assert len(changes) == (len(experiment.STRATEGIES) - 1) * 3
    assert len(annotations) == 3 * 3
    assert all(row['human_relevance_0_1_2'] == row['reviewer_id'] == row['reviewed_at'] == '' for row in annotations)
    assert {row['strategy'] for row in per_query} == set(experiment.STRATEGIES)
    row = next(row for row in table if row['strategy'] == 'dense_v1' and row['group_by'] == 'split'
               and row['group'] == 'test' and row['metric'] == 'recall@5')
    assert float(row['value']) == metrics['dense_v1']['metrics']['groups']['split']['test']['answerable_metrics']['recall@5']
    assert json.loads(row['denominators'])['answerable_queries'] == 1
    row = next(row for row in changes if row['strategy'] == 'bm25_v1' and row['query_id'] == 'qb')
    expected = next(row for row in comparisons['bm25_v1']['per_query_deltas'] if row['query_id'] == 'qb')
    assert json.loads(row['delta']) == expected['delta']
    report = (run / 'report.md').read_text()
    for strategy in experiment.STRATEGIES:
        assert strategy in report
    assert 'dev 固定划分' in report and 'test 固定划分' in report
    assert '本次新增 API 尝试：0' in report
    assert '百分点' in report and '95%' in report


def test_replay_reproduces_rankings_and_comparisons_while_timing_remains_observational(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    assert invoke_replay(monkeypatch, cli_files) == 0
    first = only_run(cli_files)
    assert invoke_replay(monkeypatch, cli_files) == 0
    second = next(path for path in cli_files['output'].iterdir() if path.is_dir() and path != first)
    for filename in ('rankings.json', 'comparisons.json'):
        assert json.loads((first / filename).read_text()) == json.loads((second / filename).read_text())
    left, right = [json.loads((path / 'metrics.json').read_text()) for path in (first, second)]
    for strategy in experiment.STRATEGIES:
        assert left[strategy]['metrics'] == right[strategy]['metrics']
        assert left[strategy]['configuration'] == right[strategy]['configuration']


def test_failed_query_is_recorded_penalized_and_kept_in_csv_and_paired_comparison(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    original = experiment.rank_chunks
    def fail_one(chunks, query, vector, **kwargs):
        if kwargs['strategy'] == 'hybrid_rrf_v1' and query == 'beta':
            raise RuntimeError('Private fixture input must not be copied to evidence.')
        return original(chunks, query, vector, **kwargs)
    monkeypatch.setattr(experiment, 'rank_chunks', fail_one)
    assert invoke_replay(monkeypatch, cli_files) == 1
    run = only_run(cli_files)
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'completed_with_failures'
    assert manifest['ranking_failures'] == 1
    assert json.loads((run / 'failures.json').read_text()) == [
        {'strategy': 'hybrid_rrf_v1', 'query_id': 'qb', 'error_type': 'RuntimeError'},
    ]
    metrics = json.loads((run / 'metrics.json').read_text())['hybrid_rrf_v1']['metrics']
    assert metrics['overall']['denominators']['answerable_queries'] == 2
    assert metrics['overall']['answerable_metrics']['recall@5'] == .5
    assert metrics['groups']['split']['test']['answerable_metrics']['recall@5'] == 0
    comparison = json.loads((run / 'comparisons.json').read_text())['hybrid_rrf_v1']
    assert comparison['overall']['denominators']['paired_answerable_queries'] == 2
    assert comparison['groups']['split']['test']['metrics']['recall@5']['difference_pp'] == -100
    row = next(row for row in read_csv(run / 'per-query.csv') if row['strategy'] == 'hybrid_rrf_v1' and row['query_id'] == 'qb')
    assert row['ranking_status'] == 'missing'
    assert json.loads(row['metrics'])['recall@5'] == 0
    assert 'Private fixture input' not in (run / 'failures.json').read_text()


def test_all_ranking_failures_have_unmeasured_timing_and_a_complete_failure_report(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError('fixture failure')
    monkeypatch.setattr(experiment, 'rank_chunks', fail)
    assert invoke_replay(monkeypatch, cli_files) == 1
    run = only_run(cli_files)
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'completed_with_failures'
    assert manifest['ranking_failures'] == len(experiment.STRATEGIES) * 3
    for result in json.loads((run / 'metrics.json').read_text()).values():
        assert result['timing']['median_ms'] is None
        assert result['metrics']['overall']['answerable_metrics']['recall@5'] == 0
        assert result['metrics']['overall']['unanswerable']['empty_return_rate'] == 0
    assert '| N/A |' in (run / 'report.md').read_text()


def test_corrupted_provider_log_cannot_mask_original_failure_or_claim_zero_attempts(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    def fail_export(dataset, runs, rankings, comparisons, run):
        (run / 'provider-calls.json').write_text('not JSON')
        raise RuntimeError('original export failure')
    monkeypatch.setattr(experiment, 'tables', fail_export)
    assert invoke_replay(monkeypatch, cli_files) == 1
    run = only_run(cli_files)
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['status'] == 'failed'
    assert manifest['error_type'] == 'RuntimeError'
    assert manifest['provider_call_evidence_error_type'] == 'JSONDecodeError'
    assert manifest['new_api_attempts'] is None
    assert 'provider-calls.json' in manifest['artifact_sha256']
    assert manifest['finished_at']


def test_failed_mock_provider_batch_preserves_partial_vectors_and_exact_attempt_count(dataset, tmp_path, monkeypatch):
    calls = []
    def transport(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 2:
            return httpx.Response(503, json={'error': 'test-only failure'})
        return httpx.Response(200, json={'model': 'unit-embedding-model', 'data': [
            {'index': index, 'embedding': [1., float(index + 1)]} for index, _ in enumerate(body['input'])
        ]})
    def provider(settings, store):
        return ApiProviders(settings, store, client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    monkeypatch.setattr(experiment, 'ApiProviders', provider)
    settings = Settings(embedding=Endpoint(base_url='https://unit-test.invalid', api_key='test-only-key',
                                          model='unit-embedding-model', path='/embeddings'))
    run = tmp_path / 'mock-live-run'
    run.mkdir()
    with pytest.raises(ProviderError):
        asyncio.run(experiment.embed_dataset(dataset, settings, run, max_calls=2))
    assert len(calls) == 2
    partial = json.loads((run / 'embedding-cache.partial.json').read_text())
    assert partial['status'] == 'started'
    assert set(partial['documents']) == {'a', 'b', 'c'}
    assert partial['queries'] == {}
    assert not (run / 'embedding-cache.json').exists()
    recorded = json.loads((run / 'provider-calls.json').read_text())
    assert len(recorded) == 2
    assert sorted(row['status'] for row in recorded) == ['failed', 'succeeded']
    assert all(row['capability'] == 'embedding' for row in recorded)
    assert all(body['model'] == 'unit-embedding-model' for body in calls)
    assert 'test-only-key' not in (run / 'provider-calls.json').read_text()


def test_preflight_is_zero_call_and_never_creates_a_run(cli_files, monkeypatch, capsys):
    forbid_provider_setup(monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['rag_experiment.py', '--dataset', str(cli_files['dataset']),
                                    '--output-dir', str(cli_files['output'])])
    assert experiment.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['expected_embedding_calls'] == 2
    assert result['strategies'] == list(experiment.STRATEGIES)
    assert not cli_files['output'].exists()


def test_history_refresh_failure_does_not_change_the_completed_frozen_run(cli_files, monkeypatch, capsys):
    forbid_provider_setup(monkeypatch)
    attempted = []
    def failed_history(directory):
        attempted.append(directory)
        # The hook must run after a finalized manifest is available.
        manifest = json.loads(next(directory.glob('*/manifest.json')).read_text())
        assert manifest['status'] == 'completed'
        assert manifest['artifact_sha256']
        raise OSError('fixture history index failure')
    monkeypatch.setattr(experiment, 'refresh_history', failed_history)
    assert invoke_replay(monkeypatch, cli_files) == 0
    assert attempted == [cli_files['output']]
    manifest = json.loads((only_run(cli_files) / 'manifest.json').read_text())
    assert manifest['status'] == 'completed'
    assert manifest['new_api_attempts'] == 0
    assert 'History index refresh failed (OSError)' in capsys.readouterr().out


@pytest.mark.parametrize('custom_protocol', [False, True])
def test_archived_code_contains_all_dependencies_and_replays_without_modifying_its_sources(cli_files, monkeypatch, tmp_path, custom_protocol):
    forbid_provider_setup(monkeypatch)
    monkeypatch.setattr(experiment, 'CODE_FILES', ARCHIVED_CODE_FILES)
    protocol = cli_files['protocol']
    args = []
    if custom_protocol:
        protocol = tmp_path / 'external-protocol.md'
        protocol.write_text('# External test protocol\nA different frozen source and evaluation scope.\n')
        args = ['--protocol', str(protocol)]
        # The explicit path must work even when the default is unavailable.
        monkeypatch.setattr(experiment, 'PROTOCOL', tmp_path / 'missing-default.md')
    assert invoke_replay(monkeypatch, cli_files, args) == 0
    original = only_run(cli_files)
    assert (original / 'protocol.md').read_bytes() == protocol.read_bytes()
    original_manifest = json.loads((original / 'manifest.json').read_text())
    assert original_manifest['protocol_source'] == str(protocol.resolve())
    assert original_manifest['protocol_sha256'] == experiment.digest(protocol.read_bytes())
    code = original / 'code'
    required = {
        'app/__init__.py', 'app/store.py', 'app/models.py', 'app/difficulty.py', 'app/pipeline.py',
        'app/config.py', 'app/providers.py', 'app/retrieval.py', 'app/rag_evaluation.py',
        'scripts/rag_experiment.py', 'scripts/rag_history.py', 'requirements.lock.txt', 'requirements.txt',
        'docs/rag/EXPERIMENT_PROTOCOL.md',
    }
    assert required <= set(ARCHIVED_CODE_FILES)
    assert all((code / name).is_file() for name in required)
    assert (code / 'docs/rag/EXPERIMENT_PROTOCOL.md').read_bytes() == (original / 'protocol.md').read_bytes()
    before = {str(path.relative_to(code)): experiment.digest(path.read_bytes()) for path in code.rglob('*') if path.is_file()}
    output = tmp_path / 'archived-replay-output'
    completed = subprocess.run([
        sys.executable, '-B', str(code / 'scripts/rag_experiment.py'),
        '--dataset', str(original / 'dataset.json'), '--cache', str(original / 'embedding-cache.json'),
        '--output-dir', str(output),
    ], cwd=code, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    replay = next(path for path in output.iterdir() if path.is_dir())
    manifest = json.loads((replay / 'manifest.json').read_text())
    assert manifest['new_api_attempts'] == 0
    assert manifest['cache_replay'] is True
    assert (replay / 'protocol.md').read_bytes() == protocol.read_bytes()
    assert manifest['protocol_sha256'] == original_manifest['protocol_sha256']
    for name in ('rankings.json', 'comparisons.json'):
        assert json.loads((replay / name).read_text()) == json.loads((original / name).read_text())
    after = {str(path.relative_to(code)): experiment.digest(path.read_bytes()) for path in code.rglob('*') if path.is_file()}
    assert after == before


@pytest.mark.parametrize('status,expected_boundary', [
    ('public_human_relevance', '公开数据原有的人工相关性'),
    ('public_human_qa_derived', '不是穷尽的人工检索 qrels'),
    ('community_duplicate_labels', '社区重复问题关系'),
])
def test_external_source_report_does_not_relabel_data_as_synthetic_or_teacher_reviewed(cli_files, monkeypatch, status, expected_boundary):
    forbid_provider_setup(monkeypatch)
    dataset = json.loads(cli_files['dataset'].read_text())
    dataset.update(label_status=status, evaluation_scope='External source; limited candidate pool; conversion remains unreviewed.')
    experiment.write_json(cli_files['dataset'], dataset)
    assert invoke_replay(monkeypatch, cli_files) == 0
    run = only_run(cli_files)
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['label_status'] == status
    assert manifest['evaluation_scope'] == dataset['evaluation_scope']
    assert manifest['human_review_performed_by_this_run'] is False
    report = (run / 'report.md').read_text()
    assert status in report and expected_boundary in report
    assert dataset['evaluation_scope'] in report
    assert 'test 仍属于合成试点集' not in report
    assert '自编、尚未人工复核的数据' not in report


def test_missing_selected_protocol_stops_before_provider_setup_or_run_creation(cli_files, monkeypatch):
    forbid_provider_setup(monkeypatch)
    missing = cli_files['protocol'].parent / 'not-found.md'
    with pytest.raises(FileNotFoundError):
        invoke_replay(monkeypatch, cli_files, ['--protocol', str(missing)])
    assert not cli_files['output'].exists()
