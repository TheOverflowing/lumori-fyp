"""Build a traceable CS slice of human MLQA annotations; never call a model.

Wikipedia is external knowledge material, not a university course collection.
Qrels denote known human answer-bearing contexts, not exhaustive relevance.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'benchmarks/rag/external/mlqa'
ARCHIVE_SHA = '246e8089933d13007fe80684d5c5c0713d6834cf8b3b4a0ec7c66f0a0d2baac8'
# Chosen by CS topic, before any embedding or ranking of these examples.
TITLES = (
    'Internet', 'Ternary computer', 'Coupling (computer programming)',
    'Android (operating system)', 'Mobile computing', 'Extreme programming',
    'Parallel computing', 'GPRS Tunnelling Protocol', 'Computer security',
    'Oracle Database', 'Internet Protocol', 'Data Encryption Standard',
    'Transmission Control Protocol', 'Distributed hash table',
    'Web Proxy Auto-Discovery Protocol', 'Internet Control Message Protocol for IPv6',
    'Computer file', 'Java (programming language)', 'Microcomputer', 'Computer science',
    'Software requirements specification', 'Java API for XML Processing', 'Cryptography',
    'Local area network', 'Virtual memory', 'Computer programming', 'Computer virus',
    'Internet protocol suite', 'Computational complexity theory', 'Scheme (programming language)',
    'Hypertext Transfer Protocol', 'Software design pattern', 'MySQL',
)
MAX_FAMILIES_PER_ARTICLE = 3


def sha(value):
    return hashlib.sha256(value).hexdigest()


def doc_id(language, text):
    return 'mlqa-' + language + '-' + sha(text.encode())[:20]


def read_records(archive, split, language):
    member = f'MLQA_V1/{split}/{split}-context-{language}-question-{language}.json'
    data = json.loads(archive.read(member))
    records = {}
    for article in data['data']:
        for paragraph in article['paragraphs']:
            for query in paragraph['qas']:
                if query['id'] in records:
                    raise ValueError('Duplicate source question ID')
                records[query['id']] = {'title': article['title'], 'context': paragraph['context'],
                                         'question': query['question'], 'answers': query['answers'],
                                         'source_member': member}
    return records


def build(archive_path, verify_archive=True):
    raw = Path(archive_path).read_bytes()
    if verify_archive and sha(raw) != ARCHIVE_SHA:
        raise ValueError('Source archive checksum changed; do not silently rebuild another release')
    documents, queries, selection = {}, [], []
    all_ids = set()
    with zipfile.ZipFile(archive_path) as archive:
        for split in ('dev', 'test'):
            en, zh = (read_records(archive, split, lang) for lang in ('en', 'zh'))
            counts = Counter()
            for qid in sorted(en, key=lambda q: sha(q.encode())):
                english = en[qid]
                if english['title'] not in TITLES:
                    continue
                reason = ('no_human_zh_pair' if qid not in zh else
                          'article_cap' if counts[english['title']] >= MAX_FAMILIES_PER_ARTICLE else 'included')
                selection.append({'original_id': qid, 'split': split, 'title': english['title'], 'decision': reason})
                if reason != 'included':
                    continue
                if qid in all_ids:
                    raise ValueError('Original family overlaps dev and test')
                all_ids.add(qid)
                counts[english['title']] += 1
                known = []
                for lang, record in (('en', english), ('zh', zh[qid])):
                    if not record['answers']:
                        raise ValueError('Selected human question has no answer')
                    for answer in record['answers']:
                        start, text = answer['answer_start'], answer['text']
                        if type(start) is not int or start < 0 or not text or record['context'][start:start + len(text)] != text:
                            raise ValueError('Human answer span does not match the original text')
                    identifier = doc_id(lang, record['context'])
                    known.append(identifier)
                    documents[identifier] = {'id': identifier, 'text': record['context'], 'title': record['title'],
                        'language': lang, 'source': 'MLQA_V1', 'source_member': record['source_member'],
                        'source_url': f'https://{lang}.wikipedia.org/wiki/' + quote(record['title'].replace(' ', '_')),
                        'license': 'CC-BY-SA-3.0', 'text_sha256': sha(record['context'].encode())}
                for lang, record in (('en', english), ('zh', zh[qid])):
                    queries.append({'id': f'{qid}-{lang}', 'text': record['question'], 'split': split,
                        'category': 'human_parallel_qa', 'language': lang, 'family_id': qid, 'answerable': True,
                        'relevance': {identifier: 2 for identifier in known},
                        'required_evidence_groups': [known], 'original_question_id': qid,
                        'original_answers': record['answers'], 'original_context_id': doc_id(lang, record['context']),
                        'source_member': record['source_member'],
                        'annotation_note': 'Positive contexts derived from the existing human QA span in both languages. '
                            'Either known context suffices. Other candidate contexts are unjudged, not human-confirmed negatives.'})
    return {
        'schema_version': 'rag-benchmark-v1', 'dataset_id': 'mlqa-cs-en-zh-v1',
        'label_status': 'public_human_qa_derived',
        'evaluation_scope': 'Known human answer-bearing source coverage in a small mixed-language Wikipedia CS slice; '
            'not exhaustive passage relevance, not university-course gold, not official MLQA answer-span F1. '
            'Each query has two known sources in one alternative evidence group; all_evidence@k equals hit@k here. '
            'Translated question pairs are dependent families; query-level bootstrap is descriptive only. '
            'No query-language restriction forces cross-language retrieval and no unanswerable instances are included.',
        'provenance': {'source_url': 'https://github.com/facebookresearch/MLQA',
            'archive_url': 'https://dl.fbaipublicfiles.com/MLQA/MLQA_V1.zip', 'archive_sha256': sha(raw),
            'paper': 'https://aclanthology.org/2020.acl-main.653/', 'license': 'CC-BY-SA-3.0',
            'license_url': 'https://creativecommons.org/licenses/by-sa/3.0/',
            'human_annotation': 'English crowd workers wrote questions and selected answer spans; professional translators '
                'translated questions and annotated target-language spans (paper sections 2.2 and 2.3).',
            'transformation': 'Assistant-selected CS article whitelist, original text and official splits preserved; '
                'require existing en/zh human pair; SHA256(question_id) order; at most 3 families per article; '
                'do not use retrieval scores to select examples; all selections and omissions retained.',
            'scope': 'Wikipedia knowledge passages related to undergraduate CS topics; not course handouts.',
            'max_families_per_article': MAX_FAMILIES_PER_ARTICLE, 'allowed_english_titles': list(TITLES),
            'original_test_exposed_to_ranking_before_freeze': False},
        'documents': sorted(documents.values(), key=lambda d: d['id']),
        'queries': sorted(queries, key=lambda q: (q['split'], q['id'])),
    }, selection


def main():
    dataset, selection = build(SOURCE / 'MLQA_V1.zip')
    from sys import path
    path.insert(0, str(ROOT))
    from app.rag_evaluation import validate_dataset
    validate_dataset(dataset)
    out = SOURCE / 'mlqa_cs_en_zh_v1.json'
    if out.exists():
        raise FileExistsError('Frozen output already exists; use a new version for changes')
    out.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n')
    (SOURCE / 'selection-v1.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'dataset': str(out), 'sha256': sha(out.read_bytes()),
                      'documents': len(dataset['documents']), 'queries': len(dataset['queries']),
                      'query_splits': dict(Counter(q['split'] for q in dataset['queries'])),
                      'families': len({q['family_id'] for q in dataset['queries']})}, ensure_ascii=False))


if __name__ == '__main__':
    main()
