"""Independent H6D arithmetic audit using only Python standard library.

Prefers the final case JSON; while work is in progress it reads job evidence
through SQLite's read-only URI. It never imports project schedulers/compilers,
reads user courses, calls models, or changes experimental evidence.
"""
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sqlite3


DIRECTORY = Path(__file__).resolve().parent.parent / 'harness-experiments/H6D_20260919'


def emit(timeline, kind, start, end, **fields):
    if end <= start:
        return
    if timeline and kind in ('run', 'idle') and timeline[-1]['end'] == start:
        old = {k: v for k, v in timeline[-1].items() if k not in ('start', 'end')}
        if old == {'kind': kind, **fields}:
            timeline[-1]['end'] = end
            return
    timeline.append({'kind': kind, **fields, 'start': start, 'end': end})


def simulate(processes, scenario):
    arrivals = {p['id']: p['arrival'] for p in processes}
    bursts = {p['id']: p['burst'] for p in processes}
    remaining = dict(bursts)
    first, complete, timeline = {}, {}, []
    time, switches = 0, 0
    previous, old_slice, old_completed = None, 0, False
    if scenario['policy'] == 'stcf':
        while any(remaining.values()):
            ready = [pid for pid in remaining if remaining[pid] and arrivals[pid] <= time]
            if not ready:
                emit(timeline, 'idle', time, time + 1)
                previous = None
            else:
                pid = min(ready, key=lambda p: (remaining[p], p))
                switches += int(previous is not None and previous != pid)
                first.setdefault(pid, time)
                remaining[pid] -= 1
                if not remaining[pid]:
                    complete[pid] = time + 1
                emit(timeline, 'run', time, time + 1, process_id=pid)
                previous = pid
            time += 1
    else:
        assert scenario['policy'] == 'rr'
        pending = sorted(remaining, key=lambda p: (arrivals[p], p))
        queue = []

        def admit(until, inclusive=True, anchor=None):
            while pending and (arrivals[pending[0]] < until or inclusive and arrivals[pending[0]] == until):
                pid = pending.pop(0)
                if anchor in queue:
                    queue.insert(queue.index(anchor), pid)
                else:
                    queue.append(pid)

        admit(time)
        while any(remaining.values()):
            if not queue:
                next_arrival = arrivals[pending[0]]
                emit(timeline, 'idle', time, next_arrival)
                time, previous = next_arrival, None
                admit(time)
            pid = queue.pop(0)
            if previous is not None and previous != pid:
                switches += 1
                waived = scenario['early_finish_free'] and old_completed and old_slice < scenario['quantum']
                cost = 0 if waived else scenario['switch_cost']
                emit(timeline, 'switch', time, time + cost, from_process_id=previous, to_process_id=pid)
                time += cost
                anchor = previous if scenario['during_switch'] == 'before_preempted' and not old_completed else None
                admit(time, anchor=anchor)
            first.setdefault(pid, time)
            run_length = min(remaining[pid], scenario['quantum'])
            end = time + run_length
            emit(timeline, 'run', time, end, process_id=pid)
            remaining[pid] -= run_length
            admit(end, inclusive=False)
            if scenario['boundary'] == 'before':
                admit(end)
            if remaining[pid]:
                queue.append(pid)
            else:
                complete[pid] = end
            if scenario['boundary'] == 'after':
                admit(end)
            previous, old_slice, old_completed, time = pid, run_length, not remaining[pid], end
    per_process = {pid: {'first_start': first[pid], 'response': first[pid] - arrivals[pid],
                         'completion': complete[pid], 'turnaround': complete[pid] - arrivals[pid]}
                   for pid in sorted(remaining)}
    served = {pid: sum(r['end'] - r['start'] for r in timeline if r['kind'] == 'run' and r['process_id'] == pid)
              for pid in remaining}
    assert served == bursts
    overhead = sum(r['end'] - r['start'] for r in timeline if r['kind'] == 'switch')
    idle = sum(r['end'] - r['start'] for r in timeline if r['kind'] == 'idle')
    assert sum(bursts.values()) + overhead + idle == time
    return {'timeline': timeline, 'per_process': per_process, 'service': sum(bursts.values()), 'idle': idle,
            'mean_response': Fraction(sum(v['response'] for v in per_process.values()), len(processes)),
            'mean_turnaround': Fraction(sum(v['turnaround'] for v in per_process.values()), len(processes)),
            'switch_count': switches, 'overhead': overhead, 'makespan': time}


def fraction(value):
    return Fraction(value['numerator'], value['denominator'])


def exact(value):
    value = Fraction(value)
    return {'numerator': value.numerator, 'denominator': value.denominator}


def comparison(left, operator, right):
    return {'le': left <= right, 'lt': left < right, 'ge': left >= right, 'gt': left > right, 'eq': left == right}[operator]


def main():
    path = DIRECTORY / 'deepseek_harness__cpu_en_hard.json'
    if path.exists():
        data = path.read_bytes()
        record = json.loads(data)
        evidence = record['evidence']
        provenance = {'source': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'final_archive': True}
    else:
        path = DIRECTORY / 'runtime/studio.sqlite3'
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            rows = db.execute('SELECT evidence FROM job_evidence').fetchall()
        assert len(rows) == 1
        evidence = json.loads(rows[0][0])
        provenance = {'source': str(path), 'evidence_sha256': hashlib.sha256(rows[0][0].encode()).hexdigest(), 'final_archive': False}
    report = {'provenance': provenance, 'model_calls_performed': 0, 'independent_standard_library_simulator': True,
              'agent_status': evidence['agent']['status'], 'slots': []}
    failures = []
    for slot in evidence['agent']['slots']:
        row = {'slot_id': slot['slot_id'], 'status': slot['status'],
               'accepted_asset_present': 'accepted_asset' in slot, 'attempts': []}
        for attempt in slot['attempts']:
            compiled = attempt.get('compiled_spec')
            if compiled is None:
                continue
            spec = compiled['canonical_spec']['spec']
            outcomes = {s['id']: simulate(spec['processes'], s) for s in spec['scenarios']}
            counts = Counter()

            def check(category, label, actual, wanted):
                counts[category + '_total'] += 1
                if actual == wanted:
                    counts[category + '_passed'] += 1
                else:
                    failures.append({'slot': slot['slot_id'], 'attempt': attempt['number'], 'label': label,
                                     'actual': actual, 'expected': wanted})

            for item in compiled['tool_results']:
                sid, stored = item['scenario_id'], item['result']
                independent = outcomes[sid]
                check('scenario_timeline', sid, stored['timeline'], independent['timeline'])
                check('interval_count', sid, len(stored['timeline']), len(independent['timeline']))
                for index, interval in enumerate(independent['timeline']):
                    check('timeline_interval', f'{sid}/{index}', stored['timeline'][index], interval)
                for pid, values in independent['per_process'].items():
                    check('process_row', f'{sid}/{pid}', stored['per_process'][pid], values)
                for metric in ('mean_response', 'mean_turnaround', 'switch_count', 'overhead', 'makespan'):
                    actual = fraction(stored['averages'][metric.removeprefix('mean_')]) if metric.startswith('mean_') else stored[metric]
                    check('aggregate', f'{sid}/{metric}', actual, independent[metric])
            selection = spec.get('selection')
            feasible, winners, optimum = [], [], None
            if selection:
                feasible = [sid for sid, outcome in outcomes.items() if all(comparison(outcome[c['metric']], c['operator'], fraction(c['threshold'])) for c in selection['constraints'])]
                if feasible:
                    optimum = (min if selection['direction'] == 'min' else max)(outcomes[sid][selection['metric']] for sid in feasible)
                    winners = [sid for sid in feasible if outcomes[sid][selection['metric']] == optimum]
            for claim in compiled['claims']:
                sid = claim.get('scenario_id')
                actual = {k: v for k, v in claim.items() if k != 'verified'}
                if claim['type'] == 'conservation':
                    wanted = {'type': 'conservation', 'scenario_id': sid,
                              **{k: outcomes[sid][k] for k in ('service', 'idle', 'overhead', 'makespan')}}
                elif claim['type'] == 'threshold_comparison':
                    value = outcomes[sid][claim['metric']]
                    assert any(c['metric'] == claim['metric'] and c['operator'] == claim['operator']
                               and fraction(c['threshold']) == fraction(claim['threshold']) for c in selection['constraints'])
                    wanted = {**actual, 'value': exact(value),
                              'satisfied': comparison(value, claim['operator'], fraction(claim['threshold']))}
                elif claim['type'] == 'optimal_selection':
                    wanted = {**actual, 'feasible_scenario_ids': feasible, 'optimal_scenario_ids': winners,
                              'optimal_value': exact(optimum) if optimum is not None else None}
                else:
                    assert claim['type'] == 'remaining_service'
                    pid, time = claim['process_id'], claim['time']
                    served = sum(max(0, min(time, r['end']) - r['start']) for r in outcomes[sid]['timeline'] if r['kind'] == 'run' and r['process_id'] == pid)
                    burst = next(p['burst'] for p in spec['processes'] if p['id'] == pid)
                    wanted = {**actual, 'burst': burst, 'served': served, 'remaining': burst - served}
                check('claim', claim['type'] + '/' + str(sid), actual, wanted)
            # These are canonical candidate fields presented to review, not the
            # freely written blind solver answer. Neither candidate was delivered.
            review_contract = json.loads(attempt['review']['history'][0]['messages'][1]['content'])
            candidate = review_contract['question']
            lines = candidate['answer'].splitlines()
            labels = {'mean_response': 'mean response time', 'mean_turnaround': 'mean turnaround time',
                      'switch_count': 'process switch count', 'overhead': 'total switching overhead', 'makespan': 'makespan'}
            signs = {'le': '<=', 'lt': '<', 'ge': '>=', 'gt': '>', 'eq': '='}
            for sid, outcome in outcomes.items():
                start = next(i for i, line in enumerate(lines) if line.startswith(sid + ': ['))
                intervals = []
                for interval in outcome['timeline']:
                    label = interval.get('process_id') or ('idle' if interval['kind'] == 'idle' else
                            f'switch {interval["from_process_id"]}→{interval["to_process_id"]}')
                    intervals.append(f'[{interval["start"]}, {interval["end"]}): {label}')
                check('candidate_timeline', sid, lines[start], sid + ': ' + '; '.join(intervals))
                for offset, (pid, values) in enumerate(outcome['per_process'].items(), 2):
                    check('candidate_process_row', f'{sid}/{pid}', lines[start + offset],
                          ' | '.join([pid, *(str(values[k]) for k in ('first_start', 'response', 'completion', 'turnaround'))]))
                check('candidate_aggregate_line', sid, lines[start + 2 + len(outcome['per_process'])],
                      '; '.join(f'{label}={outcome[metric]}' for metric, label in labels.items()))
                if selection:
                    for constraint in selection['constraints']:
                        metric, operator, threshold = constraint['metric'], constraint['operator'], fraction(constraint['threshold'])
                        status = 'satisfied' if comparison(outcome[metric], operator, threshold) else 'not satisfied'
                        expected_line = f'{sid}: {labels[metric]} {outcome[metric]} {signs[operator]} {threshold} → {status}'
                        check('candidate_constraint', f'{sid}/{metric}', expected_line in lines, True)
                conservation = f'{sid}: service {outcome["service"]} + idle {outcome["idle"]} + switching overhead {outcome["overhead"]} = makespan {outcome["makespan"]}.'
                check('candidate_conservation', sid, conservation in candidate['explanation'].splitlines(), True)
            if selection:
                selected = f'Optimal scenarios: {", ".join(winners)}; {labels[selection["metric"]]}={optimum}.' if winners else 'No scenario is feasible.'
                check('candidate_optimum', 'selection', lines[-1], selected)
            inversions = {}
            for sid, outcome in outcomes.items():
                values = outcome['per_process']
                inversions[sid] = [(a, b) for a in values for b in values if values[a]['response'] < values[b]['response'] and values[a]['turnaround'] > values[b]['turnaround']]
            row['attempts'].append({'number': attempt['number'], 'status': attempt['status'],
                'spec_sha256': compiled['spec_sha256'], 'checks': dict(counts), 'remaining_queries': len(spec['remaining_queries']),
                'results': outcomes, 'feasible': feasible, 'winners': winners, 'optimum': optimum,
                'response_turnaround_order_inversions': inversions})
        report['slots'].append(row)
    report['failures'] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    assert not failures


if __name__ == '__main__':
    main()
