import random

import pytest

from scripts.evaluate_document_parsing import (aggregate, edit_distance, english_words,
                                                normalize_text, text_metrics,
                                                wilson_interval, paired_cer_bootstrap)


def conventional_distance(left, right):
    previous = list(range(len(right) + 1))
    for i, first in enumerate(left, 1):
        current = [i]
        for j, second in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (first != second)))
        previous = current
    return previous[-1]


def test_bitvector_matches_independent_dynamic_programming():
    rng = random.Random(918)
    for _ in range(250):
        a = ''.join(rng.choices('中文abc🙂', k=rng.randrange(90)))
        b = ''.join(rng.choices('中文abc🙂', k=rng.randrange(90)))
        assert edit_distance(a, b) == conventional_distance(a, b)
    assert edit_distance(['the', 'cat'], ['a', 'cat', '!']) == 2


def test_normalization_preserves_case_punctuation_and_chinese():
    assert normalize_text(' Ａ B\n中 文！ ') == 'AB中文!'
    assert normalize_text('A') != normalize_text('a')
    assert english_words('Hello, world!') == ['Hello', ',', 'world', '!']


def test_empty_and_failed_predictions_are_not_successes():
    measured = text_metrics('A complete reference', '', 'english')
    assert measured['cer'] == 1
    assert measured['wer'] == 1
    assert measured['usable_page'] is False
    assert measured['nonempty_page'] is False
    assert text_metrics('abcdefghij', 'abcdefghiX', 'english')['usable_page'] is True
    assert text_metrics('abcdefghij', 'abcdefghXX', 'english')['usable_page'] is False


def test_insertions_can_produce_cer_over_one():
    assert text_metrics('a', 'abcdefghij', 'english')['cer'] == 9
    with pytest.raises(ValueError):
        text_metrics('', 'invented', 'english')


def test_structured_pages_do_not_receive_misleading_text_accuracy():
    metrics = text_metrics('table reference', 'table prediction', 'english', eligible=False)
    assert metrics['cer'] is None
    assert metrics['usable_page'] is None
    assert metrics['nonempty_page'] is True
    assert text_metrics('中文', '中文', 'simplified_chinese')['wer'] is None


def test_aggregation_keeps_failures_and_uses_character_weighting():
    rows = []
    for sample, reference, prediction in [('a', 'ab', 'a'), ('b', 'abcdefgh', '')]:
        rows.append({'sample_id': sample, 'elapsed_seconds': 1,
                     'completed_without_exception': bool(prediction),
                     **text_metrics(reference, prediction, 'english')})
    measured = aggregate(rows)
    assert measured['cases'] == 2
    assert measured['macro_cer'] == .75
    assert measured['micro_cer'] == .9
    assert measured['nonempty_page_rate'] == .5
    assert measured['usable_page_rate'] == 0


def test_small_sample_uncertainty_and_paired_resampling():
    assert wilson_interval(0, 0) is None
    assert wilson_interval(0, 6)[1] == pytest.approx(.3903343, abs=1e-6)
    assert wilson_interval(6, 6)[0] == pytest.approx(.6096657, abs=1e-6)
    rows = [{'strategy': strategy, 'sample_id': str(i), 'variant': 'scan', 'cer_eligible': True,
             'language': 'english' if i < 3 else 'simplified_chinese', 'cer': score}
            for strategy, score in [('baseline', 1.), ('candidate', .25)] for i in range(6)]
    result = paired_cer_bootstrap(rows, 'baseline', 'candidate', 'scan')
    assert result['mean_cer_reduction'] == .75
    assert result['percentile_interval_95'] == [.75, .75]
    assert paired_cer_bootstrap(rows[:-1], 'baseline', 'candidate', 'scan') is None
