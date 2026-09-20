from copy import deepcopy
import pytest
from app.config import Settings, Endpoint
from scripts.difficulty_experiment import (summarize, score, paired_comparisons,
    select_cases, make_settings, CappedStore, safe_error, public_parameters)


def record(strategy='baseline', **extra):
    return {'strategy': strategy, 'case_id': 'case', 'repeat': 0,
        'target_difficulty': 'hard', 'language': 'en', **extra}


def judgement(**extra):
    return {'assessed_difficulty': 'hard', 'confidence': 'high', 'correctness': True,
        'grounded': True, 'answerable': True, 'ambiguity_free': True, 'rationale': 'A', **extra}


def case(**extra):
    return {'id': 'id', 'topic_id': 'topic', 'split': 'dev', 'pilot': True,
        'language': 'en', 'target_difficulty': 'hard', 'question_type': 'short_answer',
        'topic': 'Explain scheduling tradeoffs', 'learner_profile': 'Undergraduate CS students',
        'sources': [{'id': 'src', 'text': 'Frozen context.', 'document_name': 'notes', 'page': 1}], **extra}


def test_failures_stay_in_denominator_and_empty_level_is_not_zero():
    good = record(generation_status='valid'); score(good, judgement())
    failed = record(case_id='failed', generation_status='failed')
    metrics = summarize([good, failed])['baseline']
    assert metrics['requested'] == 2 and metrics['qualified_rate'] == .5
    assert metrics['judged'] == 1 and metrics['ungraded'] == 1
    assert metrics['by_difficulty']['easy']['qualified_rate'] is None
    assert metrics['confusion_matrix']['hard']['ungraded'] == 1


@pytest.mark.parametrize('overrides', [
    {'correctness': False}, {'grounded': False}, {'answerable': False},
    {'ambiguity_free': False}, {'confidence': 'low'}, {'assessed_difficulty': 'uncertain'},
])
def test_matching_label_does_not_override_quality_or_uncertainty(overrides):
    row = record(); score(row, judgement(**overrides))
    assert row['qualified'] is False


def test_comparisons_pair_cases_not_output_order():
    rows = [record(qualified=True), record('rubric_axes', qualified=False),
        record(case_id='second', qualified=False), record('rubric_axes', case_id='second', qualified=True)]
    result = paired_comparisons(list(reversed(rows)))['rubric_axes']
    assert (result['wins'], result['losses'], result['ties']) == (1, 1, 0)
    assert result['qualified_rate_difference'] == 0


def test_pilot_cannot_include_holdout_or_split_translated_topics():
    data = {'cases': [case(), case(id='held', topic_id='other', split='holdout')]}
    assert [r['id'] for r in select_cases(data, 'pilot')] == ['id']
    data['cases'][1]['topic_id'] = 'topic'
    with pytest.raises(ValueError, match='leakage'):
        select_cases(data, 'pilot')


def test_duplicate_case_ids_rejected():
    with pytest.raises(ValueError, match='Duplicate case'):
        select_cases({'cases': [case(), case()]}, 'pilot')


def test_settings_keep_key_at_existing_openrouter_host_and_do_not_mutate_app():
    s = Settings(text=Endpoint('https://api.deepseek.com', 'test-text-key', 'deepseek-flash', '/chat/completions'),
        embedding=Endpoint('https://openrouter.ai/api/v1', 'test-or-key', 'embedding', '/embeddings'))
    before = deepcopy(s)
    g, j = make_settings(s, 'qwen/qwen3-235b-a22b-2507')
    assert s == before
    assert g.text.api_key == 'test-text-key'
    assert j.text.api_key == 'test-or-key' and j.text.base_url == s.embedding.base_url
    s.embedding = Endpoint('https://untrusted.example', 'test-or-key', 'embedding', '/embeddings')
    with pytest.raises(ValueError, match='configured host'):
        make_settings(s, 'judge')


def test_shared_store_caps_generator_and_judge_together(tmp_path):
    store = CappedStore(tmp_path, 2)
    store.reserve_call('generation:test', 'text', 'generator', 100)
    store.reserve_call('judge:test', 'text', 'judge', 100)
    with pytest.raises(ValueError, match='cap reached'):
        store.reserve_call('generation:next', 'text', 'generator', 100)
    assert store.one('SELECT count(*) AS n FROM calls')['n'] == 2


def test_unknown_errors_never_copy_sensitive_exception_text():
    assert safe_error(RuntimeError('Bearer super-secret-value')) == {'type': 'RuntimeError'}


def test_manifest_parameters_do_not_export_arbitrary_extra_json():
    assert public_parameters({'temperature': .6, 'max_tokens': 4096, 'api_key': 'secret',
        'thinking': {'type': 'disabled', 'private': 'secret'}, 'top_p': 'secret', 'seed': float('nan')}) == {
            'temperature': .6, 'max_tokens': 4096, 'thinking': {'type': 'disabled'}}
