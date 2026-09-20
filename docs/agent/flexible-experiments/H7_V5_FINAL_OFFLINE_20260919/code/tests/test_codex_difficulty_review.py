"""Boundary checks using synthetic ratings only; no actual review packets or API."""
import pytest

from scripts import codex_difficulty_review as review


def rating(blind_id='Q001', **overrides):
    return {
        'blind_id': blind_id,
        'assessed_difficulty': 'medium',
        'confidence': 'high',
        'correctness': 4,
        'grounding': 4,
        'answerability': 4,
        'clarity': 4,
        'rationale': 'Synthetic boundary-test evidence only.',
        **overrides,
    }


@pytest.mark.parametrize('field', ['correctness', 'grounding', 'answerability'])
def test_strict_pass_rejects_substantive_or_minor_quality_defects(field):
    result = review.calculate(rating(**{field: 3}), 'medium')
    assert result['difficulty_match'] is True
    assert result['score'] > 0
    assert result['strict_pass'] is False


def test_strict_pass_allows_only_minor_clarity_defect():
    assert review.calculate(rating(clarity=3), 'medium')['strict_pass'] is True
    assert review.calculate(rating(clarity=2), 'medium')['strict_pass'] is False


@pytest.mark.parametrize('assessed,target,confidence,credit', [
    ('medium', 'medium', 'high', 40),
    ('easy', 'medium', 'high', 20),
    ('medium', 'hard', 'medium', 20),
    ('easy', 'hard', 'high', 0),
    ('uncertain', 'medium', 'high', 0),
    ('medium', 'medium', 'low', 0),
])
def test_difficulty_credit_and_strict_gate(assessed, target, confidence, credit):
    result = review.calculate(rating(assessed_difficulty=assessed, confidence=confidence), target)
    assert result['quality_score'] == 60
    assert result['difficulty_credit'] == credit
    assert result['score'] == 60 + credit
    assert result['strict_pass'] is (assessed == target and confidence != 'low')


@pytest.mark.parametrize('value', [True, False, -1, 5, 3.0, '4'])
def test_quality_dimensions_reject_coercible_or_out_of_range_values(value):
    with pytest.raises(ValueError):
        review.calculate(rating(correctness=value), 'medium')


@pytest.mark.parametrize('overrides', [
    {'assessed_difficulty': 'very_hard'},
    {'confidence': 'certain'},
    {'rationale': ''},
    {'rationale': '  '},
])
def test_missing_evidence_or_invalid_categories_cannot_be_scored(overrides):
    with pytest.raises(ValueError):
        review.calculate(rating(**overrides), 'medium')


@pytest.fixture
def synthetic_archive(tmp_path, monkeypatch):
    """Independent files; never touches or opens actual experiment evidence."""
    monkeypatch.setattr(review, 'ROOT', tmp_path)
    monkeypatch.setattr(review, 'RUNS', ['synthetic-stage-a', 'synthetic-stage-b'])
    protocol = tmp_path / 'protocol.md'
    protocol.write_text('Synthetic test protocol.\n')
    monkeypatch.setattr(review, 'PROTOCOL', protocol)
    source = tmp_path / 'source.json'
    review.write(source, {'sentinel': 'original evidence'})
    output = tmp_path / 'review'
    output.mkdir()
    rows = [
        {'blind_id': 'Q001', 'run': 'synthetic-stage-a', 'strategy': 'example',
         'eligible': True, 'target_difficulty': 'medium', 'whole_asset_valid': True,
         'old_judge': None},
        {'blind_id': 'Q002', 'run': 'synthetic-stage-a', 'strategy': 'example',
         'eligible': False, 'target_difficulty': 'medium', 'whole_asset_valid': False,
         'old_judge': None},
        {'blind_id': 'Q003', 'run': 'synthetic-stage-b', 'strategy': 'example',
         'eligible': True, 'target_difficulty': 'medium', 'whole_asset_valid': False,
         'old_judge': None},
    ]
    review.write(output / 'packets.json', [{'blind_id': 'Q001'}, {'blind_id': 'Q003'}])
    review.write(output / 'sources.json', {'synthetic': 'No real course data.'})
    review.write(output / 'mapping.DO_NOT_READ_BEFORE_RATING.json', rows)
    review.write(output / 'manifest.json', {
        'input_hashes': {'source.json': review.sha(source)},
        'protocol_sha256': review.sha(protocol),
        'packet_sha256': review.sha(output / 'packets.json'),
        'source_sha256': review.sha(output / 'sources.json'),
        'mapping_sha256': review.sha(output / 'mapping.DO_NOT_READ_BEFORE_RATING.json'),
    })
    ratings = tmp_path / 'ratings.json'
    review.write(ratings, [rating(), rating('Q003', correctness=1)])
    return output, ratings, source, protocol


def test_missing_output_stays_zero_in_requested_denominator_and_stages_stay_separate(synthetic_archive):
    output, ratings, source, _ = synthetic_archive
    original = source.read_bytes()
    review.aggregate(output, ratings)
    summary = review.read(output / 'summary.json')
    a = summary['synthetic-stage-a']['example']
    assert a['requested'] == 2
    assert a['reviewed'] == 1
    assert a['score_out_of_100'] == 50
    assert a['valid_question_mean'] == 100
    assert a['strict_pass'] == 1
    assert a['strict_pass_rate'] == 0.5
    assert a['whole_asset_valid_rate'] == 0.5
    assert a['difficulty_confusion']['medium'] == {'medium': 1, 'ungraded': 1}
    b = summary['synthetic-stage-b']['example']
    assert b['requested'] == 1
    assert b['strict_pass'] == 0  # Incorrect answer never passes.
    assert b['whole_asset_valid'] == 0
    assert b['strict_pass_rate'] == 0
    assert b['whole_asset_valid_rate'] == 0
    items = review.read(output / 'scored-items.json')
    absent = next(row for row in items if row['blind_id'] == 'Q002')
    assert absent['score'] == 0
    assert absent['strict_pass'] is False
    assert 'rating' not in absent
    assert source.read_bytes() == original


@pytest.mark.parametrize('ratings_kind', ['missing', 'duplicate', 'extra'])
def test_incomplete_duplicate_or_extra_reviews_cannot_be_frozen(synthetic_archive, ratings_kind):
    output, ratings, _, _ = synthetic_archive
    examples = {
        'missing': [rating()],
        'duplicate': [rating(), rating(), rating('Q003')],
        'extra': [rating(), rating('Q003'), rating('Q002')],
    }
    review.write(ratings, examples[ratings_kind])
    with pytest.raises(ValueError, match='exactly once'):
        review.aggregate(output, ratings)
    assert not (output / 'ratings.lock.json').exists()
    assert not (output / 'summary.json').exists()


def test_frozen_review_cannot_be_overwritten(synthetic_archive):
    output, ratings, source, _ = synthetic_archive
    review.aggregate(output, ratings)
    frozen = {name: (output / name).read_bytes() for name in
              ('ratings.lock.json', 'scored-items.json', 'summary.json')}
    original = source.read_bytes()
    review.write(ratings, [rating(correctness=0), rating('Q003', correctness=0)])
    with pytest.raises(ValueError, match='Already frozen'):
        review.aggregate(output, ratings)
    for name, expected in frozen.items():
        assert (output / name).read_bytes() == expected
    assert source.read_bytes() == original


@pytest.mark.parametrize('changed', ['source', 'protocol', 'packet', 'mapping'])
def test_changed_evidence_or_protocol_blocks_freezing(synthetic_archive, changed):
    output, ratings, source, protocol = synthetic_archive
    path = {
        'source': source, 'protocol': protocol, 'packet': output / 'packets.json',
        'mapping': output / 'mapping.DO_NOT_READ_BEFORE_RATING.json',
    }[changed]
    path.write_text(path.read_text() + '\n')
    with pytest.raises(ValueError, match='changed'):
        review.aggregate(output, ratings)
    assert not (output / 'ratings.lock.json').exists()
