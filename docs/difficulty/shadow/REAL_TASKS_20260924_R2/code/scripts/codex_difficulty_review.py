"""Prepare label-masked retrospective review packets and aggregate signed ratings.

No model APIs. Ratings are entered by the current Codex reviewer; this utility
never fabricates judgements. Input experiment archives are read-only.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = ROOT / 'docs/difficulty/experiments'
RUNS = ['20260919T085353763975Z', '20260919T090134905693Z']
COMPARISON = EXPERIMENTS / '20260919T085353763975Z-question-diagnostic-20260919T090005156316Z'
PROTOCOL = ROOT / 'docs/difficulty/CODEX_REVIEW_PROTOCOL_V1.md'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    old = {r['id']: r for r in read(COMPARISON / 'records.json')}
    rows, sources = [], {}
    inputs = {str((COMPARISON / 'records.json').relative_to(ROOT)): sha(COMPARISON / 'records.json')}
    for run_name in RUNS:
        run = EXPERIMENTS / run_name
        cases = {c['id']: c for c in read(run / 'selected-cases.json')}
        for path in [run / 'records.json', run / 'selected-cases.json', run / 'manifest.json']:
            inputs[str(path.relative_to(ROOT))] = sha(path)
        for r in read(run / 'records.json'):
            case = cases[r['case_id']]
            f = run / 'items' / r['id'] / 'generation-response.json'
            raw = read(f) if f.exists() else {}
            if f.exists():
                inputs[str(f.relative_to(ROOT))] = sha(f)
            questions = raw.get('questions', [])
            eligible = len(questions) == 1 and raw.get('evidence_sufficient') is True
            question = questions[0] if eligible else None
            if eligible:
                eligible = all(question.get(k) for k in ('stem', 'answer', 'explanation'))
            source_key = case['sources'][0]['id']
            sources[source_key] = {'learner_profile': case['learner_profile'],
                'reference_chunks': [{'id': s['id'], 'text': s['text']} for s in case['sources']]}
            comparison = old[r['id']].get('judge') if run_name == RUNS[0] else r.get('judge')
            rows.append({'run': run_name, 'original_id': r['id'], 'strategy': r['strategy'],
                'case_id': r['case_id'], 'target_difficulty': r['target_difficulty'],
                'whole_asset_valid': r['generation_status'] == 'valid', 'eligible': bool(eligible),
                'source_key': source_key, 'old_judge': comparison,
                'question': {k: question[k] for k in ('kind', 'stem', 'options', 'answer', 'explanation')} if eligible else None})
    random.Random(2026091902).shuffle(rows)
    packets, mapping = [], []
    for index, row in enumerate(rows, 1):
        blind_id = f'Q{index:03d}'
        question = row.pop('question')
        mapping.append({'blind_id': blind_id, **row})
        if row['eligible']:
            packets.append({'blind_id': blind_id, 'source_key': row['source_key'], 'question': question})
    write(output / 'packets.json', packets)
    write(output / 'sources.json', sources)
    write(output / 'mapping.DO_NOT_READ_BEFORE_RATING.json', mapping)
    write(output / 'manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': sha(PROTOCOL), 'input_hashes': inputs,
        'packet_sha256': sha(output / 'packets.json'), 'source_sha256': sha(output / 'sources.json'),
        'mapping_sha256': sha(output / 'mapping.DO_NOT_READ_BEFORE_RATING.json'),
        'requested_slots': len(rows), 'eligible_questions': len(packets),
        'reviewer': 'Current Codex assistant, assisted with bounded factual/calculation checks',
        'precise_served_model_snapshot': None, 'sampling_parameters': None,
        'fully_blind': False, 'human_rating': False, 'new_provider_calls': 0,
        'prior_exposure': 'Reviewer designed the study, saw previous aggregate scores and a specific erroneous item.'})
    print(json.dumps({'output': str(output), 'requested_slots': len(rows), 'eligible_questions': len(packets)}))


def calculate(rating, target):
    dimensions = ('correctness', 'grounding', 'answerability', 'clarity')
    if any(type(rating[k]) is not int or not 0 <= rating[k] <= 4 for k in dimensions):
        raise ValueError('Dimensions must be integers in 0..4')
    if rating['assessed_difficulty'] not in ('easy', 'medium', 'hard', 'uncertain') or rating['confidence'] not in ('low', 'medium', 'high'):
        raise ValueError('Invalid rating categories')
    if not rating.get('rationale', '').strip():
        raise ValueError('A verifiable rationale is required')
    level = {'easy': 0, 'medium': 1, 'hard': 2}
    match = rating['assessed_difficulty'] == target and rating['confidence'] != 'low'
    distance = abs(level[target] - level[rating['assessed_difficulty']]) if rating['assessed_difficulty'] in level else None
    credit = 0 if distance is None or rating['confidence'] == 'low' else {0: 40, 1: 20, 2: 0}[distance]
    quality = 7.5 * rating['correctness'] + 2.5 * sum(rating[k] for k in dimensions[1:])
    strict = match and all(rating[k] == 4 for k in dimensions[:3]) and rating['clarity'] >= 3
    return {'score': quality + credit, 'quality_score': quality, 'difficulty_credit': credit,
        'difficulty_match': match, 'strict_pass': bool(strict)}


def aggregate(output, ratings_path):
    manifest = read(output / 'manifest.json')
    for path, expected in manifest['input_hashes'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('Source evidence changed: ' + path)
    for name, key in [('packets.json', 'packet_sha256'), ('sources.json', 'source_sha256'),
                      ('mapping.DO_NOT_READ_BEFORE_RATING.json', 'mapping_sha256')]:
        if sha(output / name) != manifest[key]:
            raise ValueError('Review packet/mapping changed')
    if sha(PROTOCOL) != manifest['protocol_sha256']:
        raise ValueError('Protocol changed after preparing review')
    if (output / 'ratings.lock.json').exists():
        raise ValueError('Already frozen: create a separate version rather than overwrite ratings')
    ratings = read(ratings_path)
    mapping = read(output / 'mapping.DO_NOT_READ_BEFORE_RATING.json')
    by_id = {r['blind_id']: r for r in ratings}
    expected = {m['blind_id'] for m in mapping if m['eligible']}
    if len(by_id) != len(ratings) or set(by_id) != expected:
        raise ValueError('Ratings must cover every eligible question exactly once')
    combined = []
    for item in mapping:
        result = dict(item)
        if item['eligible']:
            rating = by_id[item['blind_id']]
            result.update(rating=rating, **calculate(rating, item['target_difficulty']))
        else:
            result.update(score=0, quality_score=0, difficulty_credit=0, difficulty_match=False, strict_pass=False)
        combined.append(result)
    groups = {}
    for run in RUNS:
        groups[run] = {}
        for strategy in sorted({r['strategy'] for r in combined if r['run'] == run}):
            rows = [r for r in combined if r['run'] == run and r['strategy'] == strategy]
            valid = [r for r in rows if r['eligible']]
            paired = [r for r in valid if r.get('old_judge')]
            groups[run][strategy] = {'requested': len(rows), 'reviewed': len(valid),
                'score_out_of_100': sum(r['score'] for r in rows) / len(rows),
                'valid_question_mean': sum(r['score'] for r in valid) / len(valid) if valid else None,
                'strict_pass': sum(r['strict_pass'] for r in rows),
                'strict_pass_rate': sum(r['strict_pass'] for r in rows) / len(rows),
                'difficulty_matches': sum(r['difficulty_match'] for r in rows),
                'whole_asset_valid': sum(r['whole_asset_valid'] for r in rows),
                'whole_asset_valid_rate': sum(r['whole_asset_valid'] for r in rows) / len(rows),
                'difficulty_confusion': {target: dict(Counter(
                    r.get('rating', {}).get('assessed_difficulty', 'ungraded') for r in rows if r['target_difficulty'] == target))
                    for target in ('easy', 'medium', 'hard')},
                'correctness_below_4': sum(r['rating']['correctness'] < 4 for r in valid),
                'difficulty_disagreements_with_qwen': sum(r['rating']['assessed_difficulty'] != r['old_judge']['assessed_difficulty'] for r in paired),
                'quality_dimension_means': {k: sum(r['rating'][k] for r in valid)/len(valid) if valid else None
                    for k in ('correctness','grounding','answerability','clarity')}}
    # Freeze before exposing group scores. None of the source archives are written.
    write(output / 'ratings.lock.json', {'sha256': sha(ratings_path), 'ratings_file': str(ratings_path.resolve()),
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'eligible_count': len(ratings)})
    write(output / 'scored-items.json', combined)
    write(output / 'summary.json', groups)
    print(json.dumps(groups, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'aggregate'))
    parser.add_argument('output', type=Path)
    parser.add_argument('--ratings', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output)
    else:
        if not args.ratings:
            parser.error('--ratings required')
        aggregate(args.output, args.ratings)


if __name__ == '__main__':
    main()
