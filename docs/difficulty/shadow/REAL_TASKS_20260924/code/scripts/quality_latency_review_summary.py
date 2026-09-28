"""Validate sealed AI review evidence and join it after rating, never before."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(n, d):
    return {'numerator': n, 'denominator': d, 'rate': n / d if d else None}


def summarize(run_dir):
    run = Path(run_dir)
    metrics = read(run / 'metrics_summary.json')
    runtime = {x['case_id']: x for x in metrics['cases']}
    records, packet_count = [], 0
    for batch in sorted((run / 'ai-review').glob('batch*')):
        if not batch.is_dir():
            continue
        student = {x['blind_id']: x for x in read(batch / 'student_packets.json')}
        answers = {x['blind_id']: x for x in read(batch / 'answer_packets.json')}
        mapping = {x['blind_id']: x for x in read(batch / 'mapping.DO_NOT_READ_BEFORE_RATING.json')}
        packet_count += len(student)
        if not (batch / 'pass2.seal.json').exists():
            continue
        for phase in ('pass1', 'pass2'):
            if sha(batch / f'{phase}.json') != read(batch / f'{phase}.seal.json')['sha256']:
                raise ValueError(f'{batch.name}: {phase} seal mismatch')
        pass1 = {x['blind_id']: x for x in read(batch / 'pass1.json')}
        pass2 = read(batch / 'pass2.json')
        if len(pass2) != len(student) or {x['blind_id'] for x in pass2} != set(student):
            raise ValueError(f'{batch.name}: review IDs incomplete or duplicated')
        for review in pass2:
            key = review['blind_id']; hidden = mapping[key]; answer = answers[key]
            for field in ('independent_answer', 'assessed_difficulty'):
                if review[field] != pass1[key][field]:
                    raise ValueError(f'{batch.name}/{key}: sealed {field} changed')
            if sha(run / 'cases' / f"{hidden['case_id']}.json") != hidden['artifact_sha256']:
                raise ValueError('Original case changed since masking')
            for field in ('answerability', 'answer_correctness', 'explanation_correctness',
                          'objective_alignment', 'unique_answer'):
                if review[field] not in ('pass', 'fail', 'uncertain', 'not_applicable'):
                    raise ValueError(f'Invalid {field}')
            if review['citation_support'] not in ('supported', 'partially_supported', 'unsupported', 'uncertain'):
                raise ValueError('Invalid citation label')
            if review['assessed_difficulty'] not in ('easy', 'medium', 'hard', 'uncertain'):
                raise ValueError('Invalid difficulty label')
            source_text = {s['id']: [s.get('text', '')] for s in answer['sources']}
            question = student[key]['question']
            source_text.update(question=[question['stem'], *question.get('options', [])],
                               answer=[answer['answer']], explanation=[answer['explanation']])
            for quote in review['evidence_quotes']:
                origin, text = quote['source_id'], quote['quote']
                if not text or not any(text in s for s in source_text.get(origin, [])):
                    raise ValueError(f'{batch.name}/{key}: nonliteral quote {origin}: {text[:60]}')
                if origin not in ('question', 'answer', 'explanation') and origin not in answer['citation_ids']:
                    raise ValueError(f'{batch.name}/{key}: quotation from uncited context')
            core_pass = all(review[f] == 'pass' for f in ('answerability', 'answer_correctness',
                'explanation_correctness', 'objective_alignment')) and review['unique_answer'] in ('pass', 'not_applicable') and review['citation_support'] == 'supported'
            current = runtime[hidden['case_id']]
            records.append({**hidden, 'batch': batch.name, 'delivered': current['delivered'],
                'runtime_outcome': current['outcome'], 'core_quality_pass': core_pass,
                'difficulty_match': review['assessed_difficulty'] == hidden['target_difficulty'],
                'review': review})
    if len({r['case_id'] for r in records}) != len(records):
        raise ValueError('A candidate was reviewed in more than one batch')
    published = [r for r in records if r['delivered']]

    def group(rows):
        return {'reviewed': len(rows), 'core_quality_pass': rate(sum(r['core_quality_pass'] for r in rows), len(rows)),
            'difficulty_match': rate(sum(r['difficulty_match'] for r in rows), len(rows)),
            'severity': dict(Counter(r['review']['severity'] for r in rows)),
            'labels': {f: dict(Counter(r['review'][f] for r in rows)) for f in ('answerability',
                'answer_correctness', 'explanation_correctness', 'citation_support', 'objective_alignment', 'unique_answer')},
            'difficulty_confusion': {t: dict(Counter(r['review']['assessed_difficulty'] for r in rows
                if r['target_difficulty'] == t)) for t in ('easy', 'medium', 'hard')}}
    return {'schema_version': 'quality-latency-ai-review-summary-v1',
        'evidence_tier': 'Two-pass masked Codex AI-assisted review. No human or learner validation.',
        'reviewer_assignment': 'One AI rater per candidate, three agents across four batches; not inter-rater agreement.',
        'rubric': 'Core quality requires answerability, answer, explanation, objective alignment all pass; MCQ uniqueness pass; citations supported. Target difficulty is reported separately.',
        'packet_count': packet_count, 'reviewed': len(records), 'published': group(published),
        'all_candidates': group(records),
        'published_core_quality_per_submitted': rate(sum(r['core_quality_pass'] for r in published), metrics['denominators']['submitted']),
        'not_reviewed_case_ids': sorted(set(runtime) - {r['case_id'] for r in records}),
        'validation': {'sealed_files_verified': True, 'pass1_answers_and_difficulty_unchanged': True,
            'original_case_hashes_verified': True, 'quoted_spans_and_citation_membership_verified': True},
        'records': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    result = summarize(args.run_dir)
    path = args.run_dir / 'ai-review' / 'summary.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    fields = ['case_id', 'candidate_scope', 'delivered', 'runtime_outcome', 'target_difficulty',
              'assessed_difficulty', 'difficulty_match', 'core_quality_pass', 'severity',
              'answerability', 'answer_correctness', 'explanation_correctness', 'citation_support',
              'objective_alignment', 'unique_answer', 'concise_rationale']
    with (path.parent / 'case_reviews.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for record in result['records']:
            joined = {**record, **record['review']}
            writer.writerow({field: joined[field] for field in fields})
    print(json.dumps({k: result[k] for k in ('reviewed', 'packet_count', 'published')}, ensure_ascii=False))
