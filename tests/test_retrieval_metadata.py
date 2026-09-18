"""Offline metadata scoring checks; no experiment labels or provider calls."""
import copy
import importlib.util
import math
from pathlib import Path
import random

import pytest

from app.retrieval import (LEXICAL_BONUS_CAP, METADATA_ENCODING_VERSION, STRATEGIES,
                           rank_chunks, retrieval_config)


STRATEGY = 'hybrid_dense_lexical_v1'


def chunk(identifier, cosine, *, text='generic description', metadata=None):
    result = {'id': identifier, 'text': text, 'vector': [cosine, math.sqrt(1 - cosine * cosine)]}
    if metadata is not None:
        result['metadata'] = metadata
    return result


def rank(chunks, query='rollback', **kwargs):
    return rank_chunks(chunks, query, [1, 0], strategy=STRATEGY, metadata_weight=.5, **kwargs)


def ids(results):
    return [result['id'] for result in results]


@pytest.mark.parametrize('field,value', [('heading_path', ['Database', 'Rollback']),
                                         ('keywords', ['rollback']), ('keywords', 'rollback')])
def test_metadata_can_resolve_close_semantic_matches_outside_dense_pool(field, value):
    chunks = [chunk('general', .8), chunk('specific', .79, metadata={field: value})]
    assert ids(rank_chunks(chunks, 'rollback', [1, 0], strategy=STRATEGY, top_k=1, candidate_k=1)) == ['general']
    result = rank(chunks, top_k=1, candidate_k=1)[0]
    assert result['id'] == 'specific'
    assert result['score'] == pytest.approx(.79)
    assert result['retrieval']['selection_score'] == pytest.approx(.815)
    assert result['retrieval']['metadata_lexical_bonus'] == pytest.approx(.025)
    assert result['retrieval']['body_lexical_bonus'] == 0
    assert result['retrieval']['lexical_score'] == 0
    assert result['retrieval']['lexical_rank'] is None
    assert result['retrieval']['combined_lexical_rank'] == 1
    assert result['retrieval']['metadata_encoding_version'] == METADATA_ENCODING_VERSION


def test_metadata_never_overrides_a_cosine_gap_larger_than_the_total_cap():
    chunks = [chunk('semantic', .9), chunk('keywords_only', .8, text='rollback',
                                         metadata={'keywords': ['rollback'] * 500})]
    results = rank_chunks(chunks, 'rollback', [1, 0], strategy=STRATEGY, metadata_weight=1)
    assert ids(results) == ['semantic', 'keywords_only']
    assert results[1]['score'] == pytest.approx(.8)
    assert results[1]['retrieval']['selection_score'] == pytest.approx(.85)
    assert results[1]['retrieval']['lexical_bonus'] <= LEXICAL_BONUS_CAP


@pytest.mark.parametrize('weight', [.01, .3, .5, .9, 1])
def test_combined_body_and_metadata_bonus_has_one_shared_budget(weight):
    chunks = [chunk('both', .7, text='rollback transaction', metadata={'heading_path': ['Rollback'], 'keywords': ['transaction']}),
              chunk('body', .69, text='rollback'), chunk('metadata', .68, metadata={'keywords': ['rollback']})]
    results = rank_chunks(chunks, 'rollback transaction', [1, 0], strategy=STRATEGY, metadata_weight=weight)
    for item in results:
        details = item['retrieval']
        assert 0 <= details['combined_lexical_bonus'] <= LEXICAL_BONUS_CAP
        assert details['body_lexical_bonus'] + details['metadata_lexical_bonus'] == pytest.approx(details['lexical_bonus'])
        assert details['selection_score'] == pytest.approx(item['score'] + details['combined_lexical_bonus'])


@pytest.mark.parametrize('metadata', [None, {}, {'keywords': []}, {'heading_path': 'unrelated heading'}, {'ignored_field': 'rollback'}])
def test_absent_or_nonmatching_metadata_preserves_existing_body_ranking(metadata):
    chunks = [chunk('general', .8, metadata=metadata), chunk('body', .79, text='rollback', metadata=metadata)]
    previous = rank_chunks(chunks, 'rollback', [1, 0], strategy=STRATEGY)
    current = rank(chunks)
    assert ids(current) == ids(previous)
    for old, new in zip(previous, current):
        assert old['score'] == new['score']
        assert old['retrieval']['selection_score'] == new['retrieval']['selection_score']
        assert old['retrieval']['lexical_bonus'] == new['retrieval']['lexical_bonus']
        assert new['retrieval']['effective_metadata_weight'] == 0
        assert new['retrieval']['metadata_lexical_bonus'] == 0


def test_repeated_metadata_terms_across_fields_and_cjk_do_not_inflate_signal():
    single = [chunk('a', .7, metadata={'keywords': ['事务回滚', 'KV_Cache']}),
              chunk('b', .7, metadata={'heading_path': ['Database', 'cache']}),
              chunk('c', .7)]
    repeated = copy.deepcopy(single)
    repeated[0]['metadata'] = {'keywords': ['事务回滚', 'KV_Cache'] * 100,
                               'heading_path': ['事务回滚', 'KV_Cache', 'kv_cache'] * 100}
    first, second = rank(single, query='事务回滚 kv cache'), rank(repeated, query='事务回滚 kv cache')
    assert ids(first) == ids(second)
    assert [row['retrieval'] for row in first] == [row['retrieval'] for row in second]


def test_metadata_does_not_rewrite_inputs_text_embeddings_or_metadata():
    chunks = [chunk('a', .8, metadata={'keywords': ['rollback'], 'heading_path': ['DB']})]
    before = copy.deepcopy(chunks)
    result = rank(chunks)[0]
    assert chunks == before
    assert result['text'] == before[0]['text']
    assert result['metadata'] == before[0]['metadata']
    assert 'vector' not in result
    assert result['score'] == pytest.approx(.8)


@pytest.mark.parametrize('metadata', [True, False, 1, 'rollback', ['rollback'],
                                     {'keywords': True}, {'keywords': {'rollback': 2}},
                                     {'keywords': ['rollback', 3]}, {'heading_path': 2},
                                     {'heading_path': ['Database', None]}, {'keywords': ('rollback',)}])
def test_invalid_metadata_types_are_rejected_only_when_enabled(metadata):
    chunks = [chunk('a', .8)]
    chunks[0]['metadata'] = metadata
    with pytest.raises(ValueError, match='metadata'):
        rank(chunks)
    # Frozen strategies have always preserved arbitrary extra metadata.
    assert rank_chunks(chunks, 'rollback', [1, 0], strategy=STRATEGY, metadata_weight=0)[0]['metadata'] == metadata


@pytest.mark.parametrize('weight', [True, False, None, '0.5', [], -0.1, 1.01, math.nan, math.inf, -math.inf])
def test_invalid_metadata_weights_are_rejected(weight):
    with pytest.raises(ValueError, match='元数据权重'):
        rank_chunks([chunk('a', .8)], 'rollback', [1, 0], strategy=STRATEGY, metadata_weight=weight)


@pytest.mark.parametrize('strategy', [strategy for strategy in STRATEGIES if strategy != STRATEGY])
def test_positive_metadata_weight_cannot_silently_change_an_existing_strategy(strategy):
    with pytest.raises(ValueError, match='只支持'):
        rank_chunks([chunk('a', .8)], 'rollback', [1, 0], strategy=strategy, metadata_weight=.5)


def test_no_body_or_metadata_matches_keeps_dense_fallback_observable():
    results = rank([chunk('a', .8), chunk('b', .7)])
    assert ids(results) == ['a', 'b']
    for row in results:
        assert row['retrieval']['effective_strategy'] == 'dense_v1'
        assert row['retrieval']['combined_lexical_bonus'] == 0
        assert row['retrieval']['metadata_lexical_bonus'] == 0
        assert row['retrieval']['selection_score'] == row['score']


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_zero_weight_matches_frozen_r2_implementation_exactly(strategy):
    # Compare independent archived source, not another invocation of the new path.
    frozen_path = Path(__file__).resolve().parents[1] / 'docs/rag/experiments/20260912T055800717636Z/code/app/retrieval.py'
    spec = importlib.util.spec_from_file_location('frozen_retrieval_metadata_regression', frozen_path)
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    rng = random.Random(913)
    chunks = [{'id': str(index), 'text': ['事务 回滚 rollback', 'cache.memory and tree', '概念检索', ''][index % 4],
               'vector': [rng.uniform(-1, 1) for _ in range(4)], 'metadata': {'keywords': ['rollback'], 'unvalidated_extra': 123}}
              for index in range(24)]
    assert STRATEGIES == frozen.STRATEGIES
    assert retrieval_config(strategy=strategy, metadata_weight=0) == frozen.retrieval_config(strategy=strategy)
    for query in ['rollback 事务', 'cache.memory', 'unknownword', '']:
        options = dict(strategy=strategy, top_k=5, candidate_k=10)
        expected = frozen.rank_chunks(chunks, query, [1, .3, -.2, .4], **options)
        assert rank_chunks(chunks, query, [1, .3, -.2, .4], metadata_weight=0, **options) == expected


def test_positive_configuration_records_encoding_and_weight_without_changing_version():
    old = retrieval_config(strategy=STRATEGY)
    new = retrieval_config(strategy=STRATEGY, metadata_weight=.4)
    assert new['version'] == old['version']
    assert new['metadata_weight'] == .4
    assert new['metadata_encoding_version'] == METADATA_ENCODING_VERSION
    assert 'metadata_weight' not in old
