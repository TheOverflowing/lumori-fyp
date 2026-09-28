"""Join a completed cap-blind AI review with its frozen condition mapping."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


FIELDS = ('answer_correct', 'source_supported', 'student_solvable', 'brief_met')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = args.review_dir
    mapping = json.loads((directory / 'condition_mapping.json').read_text())
    judgment = json.loads((directory / 'judgments_codex_ai.json').read_text())
    labels = {item['review_id']: item for item in judgment['items']}
    if len(labels) != len(judgment['items']):
        raise ValueError('Duplicate review ID')
    conditions = defaultdict(list)
    for item in mapping['mapping']:
        review_id = item['review_id']
        if review_id not in labels:
            raise ValueError(f'Missing judgment: {review_id}')
        label = labels[review_id]
        if any(label.get(field) not in ('yes', 'no', 'uncertain') for field in FIELDS):
            raise ValueError(f'Incomplete judgment: {review_id}')
        conditions[item['condition']].append(label)
    if len(labels) != len(mapping['mapping']):
        raise ValueError('Judgments contain unknown IDs')
    result = {'reviewer_type': judgment['reviewer_type'],
        'sample_selection': mapping['selection'],
        'condition_counts': mapping['condition_counts'],
        'criteria': list(FIELDS), 'summary': {}}
    for condition, items in sorted(conditions.items()):
        result['summary'][condition] = {
            'sampled': len(items),
            'all_four_yes': sum(all(item[field] == 'yes' for field in FIELDS) for item in items),
            'ratings': {field: dict(Counter(item[field] for item in items)) for field in FIELDS}}
    (directory / 'review_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
