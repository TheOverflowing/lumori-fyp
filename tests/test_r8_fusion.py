import json
from pathlib import Path
import socket

import numpy as np
import pytest

from scripts.r8_fusion import SOURCE, baseline_parity, interpolate, offline_guard, read, rrf, snapshot, verify_snapshot


def test_interpolation_normalizes_before_weighting_and_has_endpoints():
    assert np.allclose(interpolate([3, 0], [0, 17], 0), [1, 0])
    assert np.allclose(interpolate([3, 0], [0, 17], 1), [0, 1])
    assert np.allclose(interpolate([3, 0], [0, 17], .5), np.array([1, 1])/np.sqrt(2))
    assert np.allclose(interpolate([3, 0], [0, 17], .25), np.array([3, 1])/np.sqrt(10))


@pytest.mark.parametrize('left,right,alpha', [([0, 0], [1, 0], .5), ([1, 0], [-1, 0], .5), ([1, 0], [1], .5), ([float('nan')], [1], .5), ([1], [1], -.1)])
def test_interpolation_rejects_invalid_vectors(left, right, alpha):
    with pytest.raises(ValueError):
        interpolate(left, right, alpha)


def test_rrf_accumulates_shared_result_breaks_ties_by_corpus_and_obeys_budget():
    a, b, c = ({'id': x} for x in 'abc')
    # b's two rank-2 contributions beat a/c's one rank-1 contribution.
    assert [r['id'] for r in rrf([a, b], [c, b], {'c': 0, 'b': 1, 'a': 2}, limit=3)] == ['b', 'c', 'a']
    assert len(rrf([a, b], [c, b], {'a': 0, 'b': 1, 'c': 2}, limit=2)) == 2
    with pytest.raises(ValueError, match='Duplicate'):
        rrf([a, a], [b], {'a': 0, 'b': 1})


def test_snapshot_detects_modification_addition_and_removal(tmp_path):
    path = tmp_path/'input.json'
    path.write_text('{}')
    frozen = snapshot(tmp_path)
    assert verify_snapshot(tmp_path, frozen) == 1
    path.write_text('[]')
    with pytest.raises(ValueError):
        verify_snapshot(tmp_path, frozen)
    path.write_text('{}')
    (tmp_path/'extra').write_text('x')
    with pytest.raises(ValueError):
        verify_snapshot(tmp_path, frozen)
    (tmp_path/'extra').unlink()
    path.unlink()
    with pytest.raises(ValueError):
        verify_snapshot(tmp_path, frozen)


def test_offline_guard_rejects_connection_before_io():
    with offline_guard(), pytest.raises(RuntimeError, match='offline'):
        socket.create_connection(('example.invalid', 443))


def test_r7_archived_parity_checker_accepts_reference_and_detects_corruption():
    dataset = read(SOURCE/'dataset.json')
    query = next(q for q in dataset['queries'] if q['split'] == 'test' and q['level'] == 'L0')
    archived = read(SOURCE/'test-candidates.json')
    archived_rows = {r['query_id']+':'+r['arm']: r for r in read(SOURCE/'test-pre-rows.json')}
    chunks = {c['id']: c for c in read(SOURCE/'chunks.json')}
    ranks, actions = {}, {}
    for arm, r7arm in [('original', 'original'), ('normalize', 'normalize'), ('interleave', 'dual')]:
        row = archived[query['id']+':'+r7arm]
        ranks[arm] = [chunks[key] for key in row['ids']]
        actions[arm] = row['action']
    gold = read(SOURCE/'gold-spans.json')
    baseline_parity(query, ranks, actions, archived, archived_rows, gold)
    ranks['original'] = list(reversed(ranks['original']))
    with pytest.raises(ValueError, match='parity'):
        baseline_parity(query, ranks, actions, archived, archived_rows, gold)
