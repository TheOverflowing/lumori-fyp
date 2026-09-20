import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.config import Endpoint, Settings
from scripts import chunk_experiment as experiment
from scripts.rag_experiment import input_hash


@pytest.fixture
def dataset():
    english = '  ' + 'Context ' * 20 + 'needle' + ' end' * 30 + '  '
    chinese = '  ' + '上下文' * 30 + '答案' + '结尾' * 35 + '  '
    documents = [{'id': 'en-doc', 'text': english, 'language': 'en'},
                 {'id': 'zh-doc', 'text': chinese, 'language': 'zh'}]
    queries = []
    for language, text, answer, context in [('en', english, 'needle', 'en-doc'), ('zh', chinese, '答案', 'zh-doc')]:
        queries.append({'id': language, 'text': 'Where is needle?' if language == 'en' else '答案在哪里？',
                        'language': language, 'split': 'dev', 'category': 'qa', 'family_id': 'family1',
                        'answerable': True, 'relevance': {'en-doc': 2, 'zh-doc': 2},
                        'original_context_id': context,
                        'original_answers': [{'answer_start': text.index(answer), 'text': answer}]})
    return {'schema_version': 'rag-benchmark-v1', 'dataset_id': 'test',
            'label_status': 'public_human_qa_derived', 'documents': documents, 'queries': queries}


def r2_cache(dataset):
    return {'schema_version': 'rag-embedding-cache-v1', 'status': 'complete', 'source': 'live_provider',
            'model': 'test-model', 'embedding_signature': 'test-signature', 'dimensions': 2,
            'input_format': experiment.INPUT_FORMAT, 'input_sha256': input_hash(dataset),
            'documents': {doc['id']: [1.0, 2.0] for doc in dataset['documents']},
            'queries': {query['id']: [2.0, 1.0] for query in dataset['queries']}}


def new_cache(dataset, texts):
    cache = {'schema_version': 'chunk-embedding-cache-v1', 'status': 'complete', 'source': 'live_provider',
             'model': 'test-model', 'embedding_signature': 'test-signature', 'dimensions': 2,
             'input_format': experiment.INPUT_FORMAT, 'input_sha256': experiment.input_identity(dataset, texts),
             'texts': {key: [1.0, 2.0] for key in texts},
             'queries': {query['id']: [2.0, 1.0] for query in dataset['queries']}}
    cache['vectors_sha256'] = experiment.vector_hash(cache)
    return cache


def chunk(parent, start, end, text=None):
    return {'id': f'{parent}:{start}', 'parent_id': parent, 'source_start': start,
            'source_end': end, 'text': text if text is not None else 'x' * (end - start)}


def test_both_language_answers_are_mapped_from_original_offsets(dataset):
    spans = experiment.gold_spans(dataset)
    assert spans['en'] == spans['zh']
    assert {span['parent_id'] for span in spans['en']} == {'en-doc', 'zh-doc'}
    assert {span['text'] for span in spans['en']} == {'needle', '答案'}


@pytest.mark.parametrize('change', ['bad_offset', 'bad_answer', 'missing_context', 'missing_peer', 'boolean_offset'])
def test_invalid_original_labels_fail_without_synthetic_replacement(dataset, change):
    query = dataset['queries'][0]
    if change == 'bad_offset':
        query['original_answers'][0]['answer_start'] += 1
    elif change == 'bad_answer':
        query['original_answers'][0]['text'] = 'invented'
    elif change == 'missing_context':
        query['original_context_id'] = 'missing'
    elif change == 'missing_peer':
        dataset['queries'].pop()
    else:
        query['original_answers'][0]['answer_start'] = True
    with pytest.raises(ValueError):
        experiment.gold_spans(dataset)


def test_parent_relevance_is_not_copied_to_non_answer_chunks():
    spans = [{'parent_id': 'doc', 'start': 50, 'end': 60}]
    metrics = experiment.span_metrics([chunk('doc', 0, 20)], spans)
    assert metrics['known_span_hit'] == metrics['best_span_coverage'] == 0


def test_intersecting_intervals_do_not_double_count_and_partial_is_not_full():
    spans = [{'parent_id': 'doc', 'start': 50, 'end': 60}]
    metrics = experiment.span_metrics([chunk('doc', 40, 55), chunk('doc', 52, 58)], spans)
    assert metrics['best_span_coverage'] == .8
    assert metrics['known_span_hit'] == 0
    assert metrics['returned_characters'] == 21
    assert metrics['unique_source_characters'] == 18
    assert metrics['duplicate_character_ratio'] == pytest.approx(3 / 21)


def test_adjacent_chunks_can_cover_span_without_one_complete_chunk():
    metrics = experiment.span_metrics([chunk('doc', 40, 55), chunk('doc', 55, 65)],
                                     [{'parent_id': 'doc', 'start': 50, 'end': 60}])
    assert metrics['known_span_hit'] == 1
    assert metrics['single_chunk_span_hit'] == 0
    assert metrics['best_span_coverage'] == 1


def test_other_language_is_valid_alternative_not_both_required():
    spans = [{'parent_id': 'en', 'start': 10, 'end': 20}, {'parent_id': 'zh', 'start': 5, 'end': 7}]
    metrics = experiment.span_metrics([chunk('zh', 0, 10)], spans)
    assert metrics['known_span_hit'] == 1
    assert metrics['single_chunk_span_hit'] == 1
    assert metrics['known_context_coverage'] == .5


def test_budget_is_character_prefix_with_no_skip_or_truncation():
    ranked = [chunk('a', 0, 3500), chunk('b', 0, 3000), chunk('c', 0, 100)]
    assert experiment.select_context(ranked, 'chars6000') == ranked[:1]
    assert experiment.select_context(ranked, 'top5') == ranked
    assert len(experiment.select_context([chunk(str(i), 0, 1200) for i in range(9)], 'chars6000')) == 5


@pytest.mark.parametrize('config', list(experiment.CUTS.values()))
def test_all_chunk_offsets_are_exact_original_slices(dataset, config):
    chunks = experiment.make_chunks(dataset['documents'], config)
    parents = {doc['id']: doc['text'] for doc in dataset['documents']}
    for item in chunks:
        assert item['text'] == parents[item['parent_id']][item['source_start']:item['source_end']]


def test_new_text_cache_requires_valid_r2_identity(dataset):
    cache = r2_cache(dataset)
    assert len(experiment.reuse_vectors(dataset, cache)) == 4
    cache['input_format'] = 'new-query-instruction'
    with pytest.raises(ValueError):
        experiment.reuse_vectors(dataset, cache)


@pytest.mark.parametrize('change', ['text_input', 'query_input', 'hash', 'bool_dimension', 'model', 'signature', 'nan', 'zero', 'missing_vector', 'dimension', 'status'])
def test_chunk_cache_rejects_mixed_or_corrupt_inputs(dataset, change):
    texts = {'hash1': 'a passage'}
    cache = new_cache(dataset, texts)
    if change == 'text_input':
        texts['hash2'] = 'different'
    elif change == 'query_input':
        dataset['queries'][0]['text'] = 'different'
    elif change == 'hash':
        cache['texts']['hash1'][0] = 3
    elif change == 'bool_dimension':
        cache['dimensions'] = True
    elif change in ('model', 'signature'):
        cache['model' if change == 'model' else 'embedding_signature'] = ''
    elif change == 'nan':
        cache['texts']['hash1'] = [float('nan'), 1]
    elif change == 'zero':
        cache['texts']['hash1'] = [0, 0]
    elif change == 'missing_vector':
        cache['texts'] = {}
    elif change == 'dimension':
        cache['queries']['en'] = [1, 2, 3]
    else:
        cache['status'] = 'started'
    with pytest.raises(ValueError):
        experiment.validate_chunk_cache(cache, dataset, texts)


def test_valid_cache_can_be_replayed_without_credentials(dataset):
    texts = {'a': 'passage'}
    cache = new_cache(dataset, texts)
    assert experiment.validate_chunk_cache(cache, dataset, texts) is cache


def test_failed_queries_remain_in_metric_denominators(dataset, monkeypatch):
    cuts = {name: experiment.make_chunks(dataset['documents'], config) for name, config in experiment.CUTS.items()}
    cache = new_cache(dataset, experiment.all_texts(cuts))
    def fail(*args, **kwargs):
        raise RuntimeError('arbitrary provider-sensitive content must not be serialized')
    monkeypatch.setattr(experiment, 'rank_chunks', fail)
    records, _, failures = experiment.run_rankings(dataset, cuts, cache, experiment.gold_spans(dataset))
    assert len(failures) == 10
    assert all('error_type' in failure and len(failure) == 3 for failure in failures)
    for summary in experiment.summarize(records):
        assert summary['failed_queries'] == summary['queries']
        assert summary['known_span_hit'] == 0


def test_embedding_identity_and_budget_checked_before_provider(dataset, tmp_path, monkeypatch):
    reuse = r2_cache(dataset)
    settings = Settings(embedding=Endpoint('https://example.com', 'secret', 'test-model', '/embeddings'))
    reuse['embedding_signature'] = settings.embedding.signature
    def forbidden(*args, **kwargs):
        pytest.fail('Provider constructed before preflight rejection')
    monkeypatch.setattr(experiment, 'ApiProviders', forbidden)
    with pytest.raises(ValueError, match='budget'):
        asyncio.run(experiment.embed_missing(dataset, {str(i): str(i) for i in range(17)}, reuse, settings, tmp_path, 1))
    reuse['embedding_signature'] = 'wrong'
    with pytest.raises(ValueError, match='identity'):
        asyncio.run(experiment.embed_missing(dataset, {'one': 'new'}, reuse, settings, tmp_path, 2))


def setup_run(tmp_path, dataset, mode='cache'):
    dataset_path = tmp_path / 'dataset.json'
    dataset_path.write_text(json.dumps(dataset))
    course_path = tmp_path / 'courses.json'
    raw = 'Course material. ' * 100
    course_path.write_text(json.dumps([{'id': 'course', 'text': raw, 'sha256': experiment.digest(raw.encode())}]))
    cuts = {name: experiment.make_chunks(dataset['documents'], config) for name, config in experiment.CUTS.items()}
    cache_path = tmp_path / 'cache.json'
    cache_path.write_text(json.dumps(new_cache(dataset, experiment.all_texts(cuts))))
    reuse_path = tmp_path / 'reuse.json'
    reuse_path.write_text(json.dumps(r2_cache(dataset)))
    return SimpleNamespace(dataset=dataset_path, course_snapshot=course_path, course_manifest=None,
                           cache=cache_path if mode == 'cache' else None, reuse_cache=reuse_path,
                           live=False, output_dir=tmp_path / 'runs', max_api_calls=64)


def test_default_preflight_has_no_output_run_or_api_calls(dataset, tmp_path, monkeypatch):
    args = setup_run(tmp_path, dataset, 'preflight')
    monkeypatch.setattr(Settings, 'from_env', lambda: pytest.fail('Preflight read credentials'))
    result = asyncio.run(experiment.execute(args))
    assert result['queries'] == 2
    assert not args.output_dir.exists()


def test_offline_run_persists_artifacts_and_exact_rankings(dataset, tmp_path, monkeypatch):
    args = setup_run(tmp_path, dataset)
    monkeypatch.setattr(Settings, 'from_env', lambda: pytest.fail('Offline replay read credentials'))
    run1 = asyncio.run(experiment.execute(args))
    run2 = asyncio.run(experiment.execute(args))
    assert (run1 / 'rankings.json').read_bytes() == (run2 / 'rankings.json').read_bytes()
    assert (run1 / 'metrics.json').read_bytes() == (run2 / 'metrics.json').read_bytes()
    manifest = json.loads((run1 / 'manifest.json').read_text())
    assert manifest['status'] == 'completed'
    assert manifest['new_api_calls'] == 0
    for path, checksum in manifest['artifacts_sha256'].items():
        assert experiment.digest((run1 / path).read_bytes()) == checksum
    assert 'app/chunking.py' in manifest['code_sha256']


def test_failure_keeps_frozen_inputs_manifest_without_arbitrary_exception_text(dataset, tmp_path, monkeypatch):
    args = setup_run(tmp_path, dataset)
    def fail(*args):
        raise RuntimeError('secret-must-not-appear')
    monkeypatch.setattr(experiment, 'run_rankings', fail)
    with pytest.raises(RuntimeError):
        asyncio.run(experiment.execute(args))
    run = next(args.output_dir.iterdir())
    manifest_text = (run / 'manifest.json').read_text()
    assert 'secret-must-not-appear' not in manifest_text
    assert json.loads(manifest_text)['status'] == 'failed'
    assert (run / 'dataset.json').exists()


def test_course_snapshot_checks_original_text_hash(tmp_path):
    path = tmp_path / 'course.json'
    path.write_text(json.dumps([{'id': 'course', 'text': 'wrong', 'sha256': '123'}]))
    with pytest.raises(ValueError):
        experiment.load_course_snapshot(path)


def test_archived_runner_replays_using_only_frozen_inputs_and_code(dataset, tmp_path):
    args = setup_run(tmp_path, dataset)
    run = asyncio.run(experiment.execute(args))
    output = tmp_path / 'archived-replay'
    result = subprocess.run([
        sys.executable, str(run / 'code/scripts/chunk_experiment.py'),
        '--dataset', str(run / 'dataset.json'),
        '--course-snapshot', str(run / 'course-sources.json'),
        '--cache', str(run / 'embedding-cache.json'), '--output-dir', str(output),
    ], cwd=tmp_path, env={**os.environ, 'PYTHONPATH': ''}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    replay = next(output.iterdir())
    assert (run / 'rankings.json').read_bytes() == (replay / 'rankings.json').read_bytes()
    assert (run / 'metrics.json').read_bytes() == (replay / 'metrics.json').read_bytes()
    assert json.loads((replay / 'manifest.json').read_text())['new_api_calls'] == 0


def test_only_new_unique_chunk_texts_are_embedded(dataset, tmp_path, monkeypatch):
    reuse = r2_cache(dataset)
    settings = Settings(embedding=Endpoint('https://example.com', 'secret', 'test-model', '/embeddings'))
    reuse['embedding_signature'] = settings.embedding.signature
    received, closed = [], []
    class Provider:
        def __init__(self, *args):
            pass
        async def embed(self, texts, job_id):
            received.extend(texts)
            return [[3., 4.] for _ in texts]
        async def close(self):
            closed.append(True)
    monkeypatch.setattr(experiment, 'ApiProviders', Provider)
    existing = dataset['documents'][0]['text']
    texts = {experiment.digest(existing.encode()): existing, experiment.digest(b'new'): 'new'}
    cache = asyncio.run(experiment.embed_missing(dataset, texts, reuse, settings, tmp_path, 1))
    assert received == ['new']
    assert closed == [True]
    assert cache['queries'] == reuse['queries']
    assert cache['reused_texts'] == 1
    assert experiment.validate_chunk_cache(cache, dataset, texts) is cache
