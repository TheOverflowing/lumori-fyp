"""Conservative aggregation of repeated AI reviews; not human calibration."""

def review_decision(rows, repeats=2):
    base = {'reviewer_type':'AI', 'human_validated':False,
            'observed_labels':[r.get('label') for r in rows],
            'estimated_difficulty':'uncertain'}
    if repeats < 2 or len(rows) != repeats or {r.get('repeat') for r in rows} != set(range(repeats)):
        return {**base, 'status':'review_required', 'reason':'incomplete_or_duplicate_repeats'}
    if any(r.get('status') != 'valid' for r in rows):
        return {**base, 'status':'review_required', 'reason':'at_least_one_invalid_review'}
    if any(r.get('label') not in ('easy','medium','hard','uncertain') for r in rows):
        return {**base, 'status':'review_required', 'reason':'unknown_label'}
    if len({r['label'] for r in rows}) != 1:
        return {**base, 'status':'review_required', 'reason':'difficulty_disagreement'}
    if rows[0]['label'] == 'uncertain':
        return {**base, 'status':'abstained', 'reason':'all_reviews_abstained'}
    if any(r.get('eligibility') != 'eligible' for r in rows):
        return {**base, 'status':'review_required', 'reason':'eligibility_disagreement'}
    return {**base, 'status':'provisional_consensus', 'reason':'complete_repeated_agreement_not_accuracy',
            'estimated_difficulty':rows[0]['label']}
