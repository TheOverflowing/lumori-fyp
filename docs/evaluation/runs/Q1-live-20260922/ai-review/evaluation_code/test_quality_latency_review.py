"""Review masking is an evaluation boundary, not an accuracy test."""
import hashlib
import json
import pytest

from scripts.quality_latency_review import prepare, review_candidate
from scripts.quality_latency_review_summary import summarize


def asset():
    return {'title': 'Fixture', 'evidence_sufficient': True, 'learning_objectives': [],
        'sections': [], 'questions': [{'slot_id': 'q1', 'difficulty': 'hard',
        'kind': 'short_answer', 'stem': 'Explain this fixture.', 'options': [],
        'answer': 'HIDDEN ANSWER', 'explanation': 'HIDDEN EXPLANATION',
        'difficulty_reason': 'HIDDEN DESIGN', 'citation_ids': ['s1']}]}


def test_rejected_candidate_is_reviewable_without_mutating_provider_response():
    value = asset()
    artifact = {'job': {'status': 'failed'}, 'evidence': {'sources': [], 'agent': {'slots': [
        {'attempts': [{'number': 1, 'author': {'response': value}},
                      {'number': 2, 'author': {'response': {'invalid': True}}}]}]}}}
    before = json.dumps(artifact, sort_keys=True)
    selected = review_candidate(artifact)
    assert selected[0]['questions'][0]['answer'] == 'HIDDEN ANSWER'
    assert selected[2:] == ('unpublished_latest_parseable_author', 1)
    assert json.dumps(artifact, sort_keys=True) == before


def test_packets_hide_target_answer_and_gate_and_preserve_original_hash(tmp_path):
    run = tmp_path / 'run'; cases = run / 'cases'; cases.mkdir(parents=True)
    case = {'id': 'case1', 'need_id': 'need1', 'language': 'en', 'difficulty': 'hard',
            'topic': 'Fixture objective', 'learner_profile': 'CS undergraduate'}
    (run / 'dataset.json').write_text(json.dumps({'cases': [case]}))
    artifact = {'run': {'case_id': 'case1', 'job_id': 'j1'}, 'job': {'status': 'failed'},
        'evidence': {'sources': [{'id': 's1', 'text': 'Exact evidence'}], 'agent': {'slots': [
        {'attempts': [{'number': 1, 'author': {'response': asset()},
                      'review': {'response': {'answer_correct': True}}}]}]}}}
    path = cases / 'case1.json'; path.write_text(json.dumps(artifact))
    out = tmp_path / 'review'
    assert prepare(run, out) == 1
    student_text = (out / 'student_packets.json').read_text()
    assert all(secret not in student_text for secret in ('HIDDEN', 'hard', 'failed', 'answer_correct', 'case1'))
    answers = json.loads((out / 'answer_packets.json').read_text())
    assert answers[0]['answer'] == 'HIDDEN ANSWER'
    mapping = json.loads((out / 'mapping.DO_NOT_READ_BEFORE_RATING.json').read_text())
    assert mapping[0]['target_difficulty'] == 'hard'
    assert mapping[0]['artifact_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert json.loads((out / 'manifest.json').read_text())['review_items'] == 1


def sealed_review(tmp_path):
    run = tmp_path / 'run'; batch = run / 'ai-review' / 'batch1'
    batch.mkdir(parents=True); (run / 'cases').mkdir()
    def write(path, value):
        path.write_text(json.dumps(value))
    artifact = run / 'cases' / 'case1.json'; write(artifact, {'fixture': True})
    write(run / 'metrics_summary.json', {'denominators': {'submitted': 1}, 'cases': [
        {'case_id': 'case1', 'delivered': True, 'outcome': 'strict'}]})
    write(batch / 'student_packets.json', [{'blind_id': 'Q001', 'question': {'stem': 'Question', 'options': []}}])
    write(batch / 'answer_packets.json', [{'blind_id': 'Q001', 'answer': 'Answer', 'explanation': 'Explanation',
        'citation_ids': ['s1'], 'sources': [{'id': 's1', 'text': 'Exact source evidence'}]}])
    write(batch / 'mapping.DO_NOT_READ_BEFORE_RATING.json', [{'blind_id': 'Q001', 'case_id': 'case1',
        'candidate_scope': 'published', 'target_difficulty': 'hard',
        'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}])
    first = {'blind_id': 'Q001', 'independent_answer': 'Independent', 'assessed_difficulty': 'easy'}
    second = {**first, **{k: 'pass' for k in ('answerability', 'answer_correctness',
        'explanation_correctness', 'objective_alignment')}, 'unique_answer': 'not_applicable',
        'citation_support': 'supported', 'severity': 'none', 'concise_rationale': 'Fixture',
        'evidence_quotes': [{'source_id': 's1', 'quote': 'Exact source evidence'}]}
    for phase, value in [('pass1', first), ('pass2', second)]:
        write(batch / f'{phase}.json', [value])
        write(batch / f'{phase}.seal.json', {'sha256': hashlib.sha256((batch / f'{phase}.json').read_bytes()).hexdigest()})
    return run, batch


def test_audit_keeps_difficulty_separate_from_core_quality(tmp_path):
    run, _ = sealed_review(tmp_path)
    result = summarize(run)
    assert result['published']['core_quality_pass']['numerator'] == 1
    assert result['published']['difficulty_match']['numerator'] == 0


def test_audit_rejects_post_rating_change(tmp_path):
    run, batch = sealed_review(tmp_path)
    (batch / 'pass1.json').write_text('[]')
    with pytest.raises(ValueError, match='seal mismatch'):
        summarize(run)


def test_audit_rejects_nonliteral_evidence_even_with_a_valid_seal(tmp_path):
    run, batch = sealed_review(tmp_path)
    path = batch / 'pass2.json'; value = json.loads(path.read_text())
    value[0]['evidence_quotes'][0]['quote'] = 'Fabricated source text'
    path.write_text(json.dumps(value))
    (batch / 'pass2.seal.json').write_text(json.dumps({'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    with pytest.raises(ValueError, match='nonliteral quote'):
        summarize(run)
