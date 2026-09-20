"""Guard R7 against hidden-intent scoring, pair loss and retry-cost erasure."""
import copy
import json

import pytest

from scripts.r7_report import (ARMS, QUALITY, clarification, interval, metering,
                               report, select_on_dev, summarize, validate_rows)


def fixture(split='dev', families=('a', 'b')):
    rows = []
    for family in families:
        for language in ('en', 'zh'):
            for level in ('L0', 'L1', 'L2', 'L3', 'L4'):
                for arm in ARMS:
                    r = dict(query_id=f'{split}-{family}-{language}-{level}', family_id=f'{split}-{family}',
                             language=language, level=level, split=split, arm=arm,
                             action='retrieve', status='skipped_ambiguous' if level == 'L4' else 'succeeded',
                             rewrite_fallback=False, shared_rerank_failed=False, context_tokens=32)
                    r.update({m: None if level == 'L4' else 1 for m in QUALITY})
                    rows.append(r)
    return rows


def test_l4_excluded_from_selection_and_quality_not_silently_zeroed():
    rows = fixture()
    summary = next(r for r in summarize(rows) if r['arm'] == 'original' and r['language'] == r['level'] == 'all')
    assert summary['input_rows'] == 20
    assert summary['quality_rows'] == 16
    assert summary['pre_hit5'] == 1
    assert select_on_dev(rows) == 'original'
    bad = copy.deepcopy(rows)
    next(r for r in bad if r['level'] == 'L4')['pre_hit5'] = 1
    with pytest.raises(ValueError, match='L4 quality'):
        validate_rows(bad, 'dev')


def test_selection_is_pre_only_and_rejects_test_rows():
    rows = fixture()
    for r in rows:
        if r['level'] != 'L4' and r['arm'] == 'original':
            r['pre_hit5'] = 0
        if r['level'] != 'L4' and r['arm'] == 'conservative':
            r['post_hit'] = 0
    assert select_on_dev(rows) == 'conservative'
    with pytest.raises(ValueError, match='only accepts dev'):
        select_on_dev(fixture('test'))


def test_missing_pair_duplicate_and_missing_component_raise():
    rows = fixture()
    with pytest.raises(ValueError, match='Incomplete pairing'):
        validate_rows(rows[1:], 'dev')
    with pytest.raises(ValueError, match='Duplicate'):
        validate_rows(rows + [rows[0]], 'dev')
    with pytest.raises(ValueError, match='Missing document component'):
        interval(rows, {}, 'dual', 'pre_hit5')


def test_cluster_bootstrap_preserves_bilingual_and_graded_dependence():
    rows = fixture()
    for r in rows:
        if r['level'] != 'L4':
            r['pre_hit5'] = int(r['arm'] == 'dual' and r['family_id'] == 'dev-a')
    result = interval(rows, {'dev-a': 'chapter-a', 'dev-b': 'chapter-b'}, 'dual', 'pre_hit5')
    assert result['difference'] == .5
    assert result['ci95'] == [0, 1]
    assert result['clusters'] == 2
    assert result['paired_queries'] == 16
    assert result['seed'] == 20260920
    assert result['samples'] == 2000
    joined = interval(rows, {'dev-a': 'one', 'dev-b': 'one'}, 'dual', 'pre_hit5')
    assert joined['clusters'] == 1 and joined['ci95'] == [.5, .5]


def test_overclarification_remains_zero_in_unambiguous_denominator():
    rows = fixture()
    for r in rows:
        if r['arm'] == 'normalize':
            r['action'] = 'clarify'
            r['status'] = 'clarified'
            if r['level'] != 'L4':
                r.update({m: 0 for m in QUALITY})
    validate_rows(rows, 'dev')
    q = next(r for r in clarification(rows) if r['arm'] == 'normalize' and r['language'] == 'all')
    assert q['recall'] == 1
    assert q['false_clarification_rate'] == 1
    assert q['precision'] == .2
    assert q['unambiguous_auto_coverage'] == 0
    summary = next(r for r in summarize(rows) if r['arm'] == 'normalize' and r['level'] == r['language'] == 'all')
    assert summary['quality_rows'] == 16 and summary['pre_hit5'] == 0


def test_rerank_failure_does_not_zero_first_stage_quality():
    rows = fixture()
    for r in rows:
        if r['level'] != 'L4':
            r.update(status='failed', post_hit=0, post_mrr5=0, shared_rerank_failed=True)
    validate_rows(rows, 'dev')
    summary = next(r for r in summarize(rows) if r['arm'] == 'original' and r['level'] == r['language'] == 'all')
    assert summary['pre_hit5'] == 1 and summary['post_hit'] == 0


def test_attempt_metering_preserves_retry_failure_and_unknown_cost():
    calls = {
        'a:1': dict(capability='rerank', logical_key='a', attempt=1, status='failed', http_status=503, usage={}),
        'a:2': dict(capability='rerank', logical_key='a', attempt=2, status='succeeded', http_status=200, usage={'cost': .25}),
        'b:1': dict(capability='rerank', logical_key='b', attempt=1, status='succeeded', http_status=200, usage={'cost': 0}),
        'c:1': dict(capability='text', logical_key='c', attempt=1, status='succeeded', usage={}),
    }
    result = metering(calls)
    r = result['rerank']
    assert r['attempts'] == 3 and r['failures'] == 1
    assert r['first_attempts'] == 2 and r['first_attempt_failures'] == 1
    assert r['retry_attempts'] == 1 and r['recovered_requests'] == 1
    assert r['known_cost'] == .25 and r['missing_cost_count'] == 1
    assert result['text']['known_cost'] is None


def test_report_rebuild_checks_dataset_and_lock_without_mutating_inputs(tmp_path):
    queries, components = [], {}
    for split in ('dev', 'test'):
        rows = fixture(split)
        components[split] = {f'{split}-{f}': f'{split}-chapter-{f}' for f in ('a', 'b')}
        for r in rows:
            if r['arm'] == 'original':
                queries.append({**{k: r[k] for k in ('family_id', 'language', 'level', 'split')},
                                'id': r['query_id'], 'text': 'How does this work?',
                                'requires_clarification': r['level'] == 'L4'})
        (tmp_path/f'{split}-per-query.json').write_text(json.dumps(rows))
    files = {'dataset.json': {'documents': [], 'queries': queries}, 'components.json': components,
             'selection-lock.json': {'basis': 'dev_pre_only', 'selected_arm': 'original'}, 'calls.json': {}, 'rewrites.json': {}}
    for name, value in files.items():
        (tmp_path/name).write_text(json.dumps(value))
    lock = (tmp_path/'selection-lock.json').read_bytes()
    decision = report(tmp_path)
    assert decision['dev_selected'] == 'original'
    assert not decision['product_router_evaluated']
    assert (tmp_path/'selection-lock.json').read_bytes() == lock
    for name in ('report.md', 'decision.json', 'metrics.csv', 'clarification.csv', 'paired-intervals.csv', 'test-changes.csv'):
        assert (tmp_path/name).exists()
    files['selection-lock.json']['selected_arm'] = 'dual'
    (tmp_path/'selection-lock.json').write_text(json.dumps(files['selection-lock.json']))
    with pytest.raises(ValueError, match='selection lock'):
        report(tmp_path)
