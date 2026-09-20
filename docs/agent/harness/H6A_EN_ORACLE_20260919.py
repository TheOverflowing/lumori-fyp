"""Fixture-specific independent arithmetic audit, standard library only.

Reads only the archived H6A English case. No project imports, production data,
model API, or production scheduling implementation is used. The RR trace is a
closed-form cycle construction justified by this workload's arrival order; the
STCF trace is rebuilt one integer tick at a time from remaining service.
"""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path


ARCHIVE = Path(__file__).resolve().parent.parent / 'harness-experiments/H6A_20260919/deepseek_harness__cpu_en_hard.json'
ARRIVAL = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
BURST = {'A': 1, 'B': 10, 'C': 10, 'D': 10}


def rr_cycles(quantum):
    # At t=1, A is complete in a short slice, so the A->B transition is free.
    # At B's first slice end, C and D are queued before B is requeued: D arrives
    # exactly at t=3 for q=2, or before t=6 for q=5. No further arrivals occur.
    # The equal B/C/D bursts are multiples of q, hence later completions consume
    # a full quantum and all following different-process transitions cost 1.
    assert quantum in (2, 5)
    timeline = [{'kind': 'run', 'process_id': 'A', 'start': 0, 'end': 1}]
    previous, time = None, 1
    for pid in ['B', 'C', 'D'] * (10 // quantum):
        if previous is not None:
            timeline.append({'kind': 'switch', 'from_process_id': previous, 'to_process_id': pid,
                             'start': time, 'end': time + 1})
            time += 1
        timeline.append({'kind': 'run', 'process_id': pid, 'start': time, 'end': time + quantum})
        time += quantum
        previous = pid
    return timeline


def stcf_ticks():
    remaining = dict(BURST)
    timeline, time = [], 0
    while any(remaining.values()):
        ready = [pid for pid in remaining if remaining[pid] and ARRIVAL[pid] <= time]
        assert ready  # This particular workload has no idle interval.
        pid = min(ready, key=lambda value: (remaining[value], value))
        if timeline and timeline[-1]['process_id'] == pid:
            timeline[-1]['end'] += 1
        else:
            timeline.append({'kind': 'run', 'process_id': pid, 'start': time, 'end': time + 1})
        remaining[pid] -= 1
        time += 1
    return timeline


def metrics(timeline):
    runs = [item for item in timeline if item['kind'] == 'run']
    service = Counter()
    for item in runs:
        service[item['process_id']] += item['end'] - item['start']
    assert service == Counter(BURST)
    per_process = {}
    for pid in ARRIVAL:
        first = min(item['start'] for item in runs if item['process_id'] == pid)
        last = max(item['end'] for item in runs if item['process_id'] == pid)
        per_process[pid] = {'first_start': first, 'response': first - ARRIVAL[pid],
                            'completion': last, 'turnaround': last - ARRIVAL[pid]}
    overhead = sum(item['end'] - item['start'] for item in timeline if item['kind'] == 'switch')
    return {'timeline': timeline, 'per_process': per_process,
            'mean_response': Fraction(sum(item['response'] for item in per_process.values()), 4),
            'mean_turnaround': Fraction(sum(item['turnaround'] for item in per_process.values()), 4),
            'switch_count': sum(left['process_id'] != right['process_id'] for left, right in zip(runs, runs[1:])),
            'overhead': overhead, 'makespan': timeline[-1]['end']}


def rational(value):
    return Fraction(value['numerator'], value['denominator'])


def main():
    archive_bytes = ARCHIVE.read_bytes()
    record = json.loads(archive_bytes)
    slot = record['evidence']['agent']['slots'][0]
    attempt = slot['attempts'][0]
    spec = attempt['author']['response']['spec']
    assert spec['processes'] == [{'id': pid, 'arrival': ARRIVAL[pid], 'burst': BURST[pid]} for pid in ARRIVAL]
    assert spec['scenarios'] == [
        {'id': sid, 'policy': 'rr', 'quantum': q, 'switch_cost': 1, 'boundary': 'before',
         'during_switch': 'tail', 'early_finish_free': True} for sid, q in [('S1', 2), ('S2', 5)]
    ] + [{'id': 'S3', 'policy': 'stcf', 'switch_cost': 0}]
    assert spec['selection'] == {'metric': 'mean_response', 'direction': 'min', 'constraints': [
        {'metric': metric, 'operator': 'le', 'threshold': {'numerator': limit, 'denominator': 1}}
        for metric, limit in [('mean_turnaround', 25), ('switch_count', 8), ('overhead', 6)]]}
    assert not spec.get('remaining_queries')
    expected = {'S1': metrics(rr_cycles(2)), 'S2': metrics(rr_cycles(5)), 'S3': metrics(stcf_ticks())}
    checks = []

    def check(category, label, actual, wanted):
        checks.append({'category': category, 'label': label, 'passed': actual == wanted,
                       'actual': actual, 'expected': wanted})

    compiled = attempt['compiled_spec']
    for item in compiled['tool_results']:
        sid, actual = item['scenario_id'], item['result']
        oracle = expected[sid]
        check('scenario_timeline', sid, actual['timeline'], oracle['timeline'])
        assert len(actual['timeline']) == len(oracle['timeline'])
        for index, interval in enumerate(oracle['timeline']):
            check('timeline_interval', f'{sid}/{index}', actual['timeline'][index], interval)
        for pid, row in oracle['per_process'].items():
            check('process_row', f'{sid}/{pid}', actual['per_process'][pid], row)
            for key, value in row.items():
                check('process_scalar_field', f'{sid}/{pid}/{key}', actual['per_process'][pid][key], value)
        for key in ('mean_response', 'mean_turnaround', 'switch_count', 'overhead', 'makespan'):
            value = rational(actual['averages'][key.removeprefix('mean_')]) if key.startswith('mean_') else actual[key]
            check('scenario_aggregate', f'{sid}/{key}', value, oracle[key])

    feasible = [sid for sid, value in expected.items()
                if value['mean_turnaround'] <= 25 and value['switch_count'] <= 8 and value['overhead'] <= 6]
    optimum = min(expected[sid]['mean_response'] for sid in feasible)
    winners = [sid for sid in feasible if expected[sid]['mean_response'] == optimum]
    for index, claim in enumerate(compiled['claims']):
        sid = claim.get('scenario_id')
        actual = {key: value for key, value in claim.items() if key != 'verified'}
        if claim['type'] == 'conservation':
            oracle = expected[sid]
            wanted = {'type': 'conservation', 'scenario_id': sid, 'service': 31, 'idle': 0,
                      'overhead': oracle['overhead'], 'makespan': 31 + oracle['overhead']}
        elif claim['type'] == 'threshold_comparison':
            value = expected[sid][claim['metric']]
            threshold = {'mean_turnaround': 25, 'switch_count': 8, 'overhead': 6}[claim['metric']]
            wanted = {'type': 'threshold_comparison', 'scenario_id': sid, 'metric': claim['metric'],
                      'operator': 'le', 'value': {'numerator': Fraction(value).numerator, 'denominator': Fraction(value).denominator},
                      'threshold': {'numerator': threshold, 'denominator': 1}, 'satisfied': value <= threshold}
        else:
            assert claim['type'] == 'optimal_selection'
            wanted = {'type': 'optimal_selection', 'metric': 'mean_response', 'direction': 'min',
                      'feasible_scenario_ids': feasible, 'optimal_scenario_ids': winners,
                      'optimal_value': {'numerator': optimum.numerator, 'denominator': optimum.denominator}}
        check('compiled_claim', f'{index}/{claim["type"]}', actual, wanted)

    # Check the student-facing accepted answer too, separately from evidence and
    # the unpublished model solver's freely written answer.
    question = slot['accepted_asset']['questions'][0]
    lines = question['answer'].splitlines()
    for sid, oracle in expected.items():
        start = next(i for i, line in enumerate(lines) if line.startswith(sid + ': ['))
        segments = []
        for interval in oracle['timeline']:
            label = interval.get('process_id') or f'switch {interval["from_process_id"]}→{interval["to_process_id"]}'
            segments.append(f'[{interval["start"]}, {interval["end"]}): {label}')
        check('published_timeline', sid, lines[start], sid + ': ' + '; '.join(segments))
        for offset, (pid, row) in enumerate(oracle['per_process'].items(), 2):
            check('published_process_row', f'{sid}/{pid}', lines[start + offset],
                  ' | '.join([pid, *(str(row[key]) for key in ('first_start', 'response', 'completion', 'turnaround'))]))
        labels = [('mean response time', 'mean_response'), ('mean turnaround time', 'mean_turnaround'),
                  ('process switch count', 'switch_count'), ('total switching overhead', 'overhead'), ('makespan', 'makespan')]
        check('published_aggregate_line', sid, lines[start + 6],
              '; '.join(f'{label}={oracle[key]}' for label, key in labels))
        for metric, threshold, label in [('mean_turnaround', 25, 'mean turnaround time'),
                                         ('switch_count', 8, 'process switch count'), ('overhead', 6, 'total switching overhead')]:
            line = next(value for value in lines if value.startswith(f'{sid}: {label} '))
            status = 'satisfied' if oracle[metric] <= threshold else 'not satisfied'
            check('published_constraint', f'{sid}/{metric}', line, f'{sid}: {label} {oracle[metric]} <= {threshold} → {status}')
        check('published_conservation', sid, question['explanation'].splitlines()[int(sid[1:]) - 1],
              f'{sid}: service 31 + idle 0 + switching overhead {oracle["overhead"]} = makespan {oracle["makespan"]}.')
    check('published_optimum', 'selection', lines[-1], f'Optimal scenarios: {", ".join(winners)}; mean response time={optimum}.')
    categories = {}
    for check_item in checks:
        count = categories.setdefault(check_item['category'], {'passed': 0, 'total': 0})
        count['total'] += 1
        count['passed'] += int(check_item['passed'])
    summary = {'archive_sha256': hashlib.sha256(archive_bytes).hexdigest(),
               'independent_of_project_scheduler': True, 'calls_performed': 0,
               'counts_are_overlapping_audit_views_not_additive_accuracy_samples': True,
               'checks': categories, 'remaining_service_queries': {'total': 0, 'status': 'not_requested'},
               'feasible': feasible, 'optimal': winners, 'optimal_mean_response': str(optimum),
               'failures': [item for item in checks if not item['passed']]}
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    assert not summary['failures']


if __name__ == '__main__':
    main()
