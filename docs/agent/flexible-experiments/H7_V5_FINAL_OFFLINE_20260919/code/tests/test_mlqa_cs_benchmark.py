"""Conversion contracts on synthetic zip fixtures, never external rankings or APIs.

The fixture spans simulate the source schema; they are not human annotations or
experimental evidence. Official frozen source data is not loaded by these tests.
"""
from copy import deepcopy
import json
import zipfile

import pytest

from scripts import build_mlqa_cs_benchmark as builder


def question(identifier, language):
    answer = 'memory' if language == 'en' else '内存'
    context = ('This unit-test paragraph describes memory and processors.' if language == 'en'
               else '这个单元测试段落说明内存和处理器。')
    return context, {'id': identifier,
                     'question': 'What does this fixture describe?' if language == 'en' else '该测试段落描述什么？',
                     'answers': [{'answer_start': context.index(answer), 'text': answer}]}


def source_payload(identifiers, language, title=None):
    context = question('unused', language)[0]
    return {'data': [{'title': title or ('Internet' if language == 'en' else '互联网'),
                      'paragraphs': [{'context': context,
                                      'qas': [question(identifier, language)[1] for identifier in identifiers]}]}]}


@pytest.fixture
def payloads():
    return {(split, language): source_payload(['dev-family'] if split == 'dev' else ['test-family'], language)
            for split in ('dev', 'test') for language in ('en', 'zh')}


def write_archive(tmp_path, payloads, name='unit-source.zip'):
    path = tmp_path / name
    with zipfile.ZipFile(path, 'w') as archive:
        for (split, language), payload in payloads.items():
            archive.writestr(f'MLQA_V1/{split}/{split}-context-{language}-question-{language}.json',
                             json.dumps(payload, ensure_ascii=False))
    return path


def convert(tmp_path, payloads, name='unit-source.zip'):
    return builder.build(write_archive(tmp_path, payloads, name), verify_archive=False)


def answer_record(payloads, split='dev', language='en'):
    return payloads[(split, language)]['data'][0]['paragraphs'][0]['qas'][0]['answers'][0]


@pytest.mark.parametrize('language', ['en', 'zh'])
@pytest.mark.parametrize('change', [
    {'answer_start': -1}, {'answer_start': True}, {'answer_start': 0},
    {'text': ''}, {'text': 'not present in the source'},
])
def test_selected_span_offset_or_text_mismatch_is_rejected(tmp_path, payloads, language, change):
    answer_record(payloads, language=language).update(change)
    with pytest.raises(ValueError, match='span does not match'):
        convert(tmp_path, payloads)


def test_selected_question_without_an_answer_is_not_turned_into_a_positive(tmp_path, payloads):
    payloads[('dev', 'zh')]['data'][0]['paragraphs'][0]['qas'][0]['answers'] = []
    with pytest.raises(ValueError, match='has no answer'):
        convert(tmp_path, payloads)


def test_missing_chinese_source_pair_is_recorded_and_never_translated_or_fabricated(tmp_path, payloads):
    context, missing = question('english-only', 'en')
    payloads[('dev', 'en')]['data'][0]['paragraphs'].append({'context': context, 'qas': [missing]})
    dataset, selection = convert(tmp_path, payloads)
    assert not any(query['family_id'] == 'english-only' for query in dataset['queries'])
    skipped = next(row for row in selection if row['original_id'] == 'english-only')
    assert skipped['decision'] == 'no_human_zh_pair'
    assert {query['family_id'] for query in dataset['queries']} == {'dev-family', 'test-family'}


def test_parallel_questions_keep_original_spans_splits_and_one_alternative_source_group(tmp_path, payloads):
    dataset, selection = convert(tmp_path, payloads)
    docs = {document['id']: document for document in dataset['documents']}
    assert dataset['label_status'] == 'public_human_qa_derived'
    assert 'not exhaustive passage relevance' in dataset['evaluation_scope']
    assert len(dataset['queries']) == 4
    assert all(row['decision'] == 'included' for row in selection)
    for split, identifier in [('dev', 'dev-family'), ('test', 'test-family')]:
        pair = [query for query in dataset['queries'] if query['family_id'] == identifier]
        assert {query['language'] for query in pair} == {'en', 'zh'}
        assert {query['split'] for query in pair} == {split}
        assert pair[0]['relevance'] == pair[1]['relevance']
        assert len(pair[0]['relevance']) == 2
        assert set(pair[0]['relevance'].values()) == {2}
        assert {docs[doc_id]['language'] for doc_id in pair[0]['relevance']} == {'en', 'zh'}
        for query in pair:
            assert len(query['required_evidence_groups']) == 1
            assert set(query['required_evidence_groups'][0]) == set(query['relevance'])
            source = payloads[(split, query['language'])]['data'][0]['paragraphs'][0]
            assert query['original_answers'] == source['qas'][0]['answers']
            assert query['text'] == source['qas'][0]['question']
            document = docs[query['original_context_id']]
            assert document['text'] == source['context']
            assert document['text_sha256'] == builder.sha(source['context'].encode())
            assert query['source_member'] == f"MLQA_V1/{split}/{split}-context-{query['language']}-question-{query['language']}.json"
            # Identical contexts may be deduplicated across source members. The
            # query keeps its exact origin; the document's stored origin must
            # still contain that exact text, without claiming it is exhaustive.
            valid_origins = {
                f'MLQA_V1/{origin_split}/{origin_split}-context-{language}-question-{language}.json'
                for (origin_split, language), payload in payloads.items()
                if language == query['language'] and any(
                    paragraph['context'] == document['text']
                    for article in payload['data'] for paragraph in article['paragraphs'])
            }
            assert document['source_member'] in valid_origins
            assert document['license'] == 'CC-BY-SA-3.0'
            assert 'unjudged, not human-confirmed negatives' in query['annotation_note']


def test_selected_family_cannot_cross_official_splits(tmp_path, payloads):
    for language in ('en', 'zh'):
        payloads[('test', language)] = source_payload(['dev-family'], language)
    with pytest.raises(ValueError, match='overlaps dev and test'):
        convert(tmp_path, payloads)


def test_article_cap_and_selection_are_independent_of_source_input_order(tmp_path, payloads):
    eligible = ['candidate-one', 'candidate-two', 'candidate-three', 'candidate-four', 'candidate-five']
    for language in ('en', 'zh'):
        payloads[('test', language)] = source_payload(eligible, language)
        extra = source_payload(['other-article'], language,
                               title='Virtual memory' if language == 'en' else '虚拟内存')
        payloads[('test', language)]['data'].extend(extra['data'])
    first, first_selection = convert(tmp_path, payloads, 'ordered.zip')
    shuffled = deepcopy(payloads)
    for data in shuffled.values():
        data['data'].reverse()
        for article in data['data']:
            article['paragraphs'].reverse()
            for paragraph in article['paragraphs']:
                paragraph['qas'].reverse()
    second, second_selection = convert(tmp_path, shuffled, 'reordered.zip')
    assert first['documents'] == second['documents']
    assert first['queries'] == second['queries']
    assert first_selection == second_selection
    # Original-byte provenance should change even when the chosen examples do not.
    assert first['provenance']['archive_sha256'] != second['provenance']['archive_sha256']
    chosen = {row['original_id'] for row in first_selection
              if row['split'] == 'test' and row['title'] == 'Internet' and row['decision'] == 'included'}
    expected = set(sorted(eligible, key=lambda identifier: builder.sha(identifier.encode()))[:3])
    assert chosen == expected
    assert sum(row['decision'] == 'article_cap' for row in first_selection) == 2
    assert any(query['family_id'] == 'other-article' for query in first['queries'])


def test_duplicate_official_question_id_is_rejected_before_selection(tmp_path, payloads):
    qas = payloads[('dev', 'en')]['data'][0]['paragraphs'][0]['qas']
    qas.append(deepcopy(qas[0]))
    with pytest.raises(ValueError, match='Duplicate source question ID'):
        convert(tmp_path, payloads)


def test_default_checksum_gate_rejects_a_different_archive_release(tmp_path, payloads):
    archive = write_archive(tmp_path, payloads)
    with pytest.raises(ValueError, match='checksum changed'):
        builder.build(archive)
