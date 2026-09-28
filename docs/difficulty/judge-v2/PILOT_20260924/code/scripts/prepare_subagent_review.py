"""Prepare a cap-blind sample of accepted questions for independent AI review.

This script does not judge correctness. It freezes the sample and separates
condition mapping from the review packet before any judgments are entered.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_subagent_scale import frozen_sources  # noqa: E402


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--per-condition', type=int, default=5)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.per_condition <= 20:
        parser.error('per-condition must be 1..20')
    sources, _ = frozen_sources()
    by_id = {source['id']: source for source in sources}
    items, mapping, condition_counts = [], [], []
    for path in args.input:
        record = json.loads(path.read_text(encoding='utf-8'))
        for run in record['results']:
            condition = f"q{run['question_count']}-c{run['parallel_limit']}-r{run['repeat']}"
            passed = [slot for slot in run['slots'] if slot['status'] == 'passed' and slot['question']]
            selected = sorted(passed, key=lambda slot: digest(condition + ':' + slot['slot_id']))[:args.per_condition]
            condition_counts.append({'condition': condition, 'passed_population': len(passed),
                'sampled': len(selected), 'source_file': str(path)})
            for slot in selected:
                review_id = digest('review:' + condition + ':' + slot['slot_id'])[:12]
                question = slot['question']
                citations = [by_id[source_id] for source_id in question['citation_ids']]
                items.append({'review_id': review_id, 'brief_focus': slot['brief_focus'],
                    'source_excerpts': [{'source_id': source['id'], 'title': source['document_name'],
                        'text': source['text']} for source in citations],
                    'stem': question['stem'], 'answer': question['answer'],
                    'explanation': question['explanation'],
                    'judgment': {'answer_correct': None, 'source_supported': None,
                        'student_solvable': None, 'brief_met': None, 'note': ''}})
                mapping.append({'review_id': review_id, 'condition': condition,
                    'slot_id': slot['slot_id']})
    items.sort(key=lambda item: digest('display:' + item['review_id']))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'blind_review.json').write_text(json.dumps({
        'reviewer_type': 'Codex AI independent review, not human or teacher label',
        'rule': 'yes/no/uncertain for each criterion; assess cited excerpt and full student-visible stem, without internal gate verdict.',
        'items': items}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output_dir / 'condition_mapping.json').write_text(json.dumps({
        'selection': 'Smallest SHA-256 of condition:slot_id among internally passed slots; presentation order independently shuffled.',
        'condition_counts': condition_counts, 'mapping': mapping}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Blind accepted-question review packet', '',
        'Rate each item from its source and student-visible question. Do not use the product gate verdict.']
    for item in items:
        lines += ['', '## ' + item['review_id'], '', 'Focus: ' + item['brief_focus'], '',
            'Question: ' + item['stem'], '', 'Answer: ' + item['answer'], '',
            'Explanation: ' + item['explanation'], '']
        for source in item['source_excerpts']:
            lines += ['Source ' + source['source_id'] + ' (' + source['title'] + '):',
                source['text'], '']
    (args.output_dir / 'blind_review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'review_items': len(items), 'conditions': condition_counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
