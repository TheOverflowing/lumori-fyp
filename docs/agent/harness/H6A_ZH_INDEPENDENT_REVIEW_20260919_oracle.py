"""Independent, standard-library-only audit of one frozen H6A Chinese item.

No project imports, compiler, provider calls, or generated code execution.
Supports only the RR/before/tail cases present in the supplied archive and
fails if its scope changes. The archive's results are comparison targets,
never inputs to scheduling decisions.
"""
from collections import deque
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re


ARCHIVE = Path(__file__).resolve().parents[1] / 'harness-experiments/H6A_20260919/deepseek_harness__cpu_zh_hard.json'


def rr(processes, scenario):
    assert scenario['policy'] == 'rr'
    assert scenario['boundary'] == 'before' and scenario['during_switch'] == 'tail'
    assert scenario['early_finish_free'] is True
    # One state step is one service interval. Arrivals are consumed in actual
    # chronological order, first through a slice end, then during switching.
    pending = deque(sorted(processes, key=lambda p: (p['arrival'], p['id'])))
    waiting, remaining = deque(), {p['id']: p['burst'] for p in processes}
    first, completed, segments = {}, {}, []
    now, previous, previous_early = 0, None, False
    switches = 0

    def arrivals():
        while pending and pending[0]['arrival'] <= now:
            waiting.append(pending.popleft()['id'])

    def segment(kind, start, end, **labels):
        current = {'kind': kind, **labels, 'start': start, 'end': end}
        if (segments and kind == 'run' and segments[-1]['kind'] == 'run'
                and segments[-1]['process_id'] == labels['process_id']
                and segments[-1]['end'] == start):
            segments[-1]['end'] = end
        else:
            segments.append(current)

    while pending or waiting:
        arrivals()
        if not waiting:
            end = pending[0]['arrival']
            segment('idle', now, end)
            now, previous, previous_early = end, None, False
            arrivals()
        current = waiting.popleft()  # Selection precedes the switch.
        if previous is not None and current != previous:
            switches += 1
            if not previous_early:
                end = now + scenario['switch_cost']
                segment('switch', now, end, from_process_id=previous, to_process_id=current)
                now = end
                arrivals()
        first.setdefault(current, now)
        length = min(scenario['quantum'], remaining[current])
        end = now + length
        segment('run', now, end, process_id=current)
        now = end
        remaining[current] -= length
        # This fixture has boundary=before, including arrivals exactly now.
        arrivals()
        if remaining[current]:
            waiting.append(current)
        else:
            completed[current] = now
        previous = current
        previous_early = remaining[current] == 0 and length < scenario['quantum']

    rows = {p['id']: {'first_start': first[p['id']],
                      'response': first[p['id']] - p['arrival'],
                      'completion': completed[p['id']],
                      'turnaround': completed[p['id']] - p['arrival']}
            for p in processes}
    averages = {key: Fraction(sum(row[key] for row in rows.values()), len(rows))
                for key in ('response', 'turnaround')}
    return {'timeline': segments, 'per_process': rows, 'averages': averages,
            'switch_count': switches,
            'overhead': sum(s['end'] - s['start'] for s in segments if s['kind'] == 'switch'),
            'idle': sum(s['end'] - s['start'] for s in segments if s['kind'] == 'idle'),
            'makespan': now}


def rational(value):
    return Fraction(value['numerator'], value['denominator'])


def metric(result, name):
    return result['averages'][name.removeprefix('mean_')] if name.startswith('mean_') else Fraction(result[name])


def audit():
    raw = ARCHIVE.read_bytes()
    data = json.loads(raw)
    slot = data['evidence']['agent']['slots'][0]
    attempt = slot['attempts'][0]
    compiled = attempt['compiled_spec']
    spec = compiled['canonical_spec']['spec']
    assert len(data['evidence']['agent']['slots']) == len(slot['attempts']) == 1
    assert not spec['remaining_queries']  # 0 requested; not a tested success rate.
    question = slot['accepted_asset']['questions'][0]
    answer = question['answer']
    results = {s['id']: rr(spec['processes'], s) for s in spec['scenarios']}
    rows_checked = scalars_checked = intervals_checked = aggregate_checked = 0
    for archived in compiled['tool_results']:
        sid, expected = archived['scenario_id'], archived['result']
        found = results[sid]
        assert found['timeline'] == expected['timeline'], sid + ': timeline'
        intervals_checked += len(found['timeline'])
        assert found['per_process'] == expected['per_process'], sid + ': process metrics'
        rows_checked += len(found['per_process'])
        scalars_checked += len(found['per_process']) * 4
        for key in ('response', 'turnaround'):
            assert found['averages'][key] == rational(expected['averages'][key])
            aggregate_checked += 1
        for key in ('switch_count', 'overhead', 'makespan'):
            assert found[key] == expected[key]
            aggregate_checked += 1
        assert sum(p['burst'] for p in spec['processes']) + found['idle'] + found['overhead'] == found['makespan']
        # Check the rendered student-facing canonical answer as well as the
        # structured calculation archive. No compiler rendering is called.
        start = answer.index(sid + ': ')
        stop = answer.find('\nRR_', start + 1)
        block = answer[start:stop if stop >= 0 else len(answer)]
        timeline_text = block.splitlines()[0].split(': ', 1)[1]
        parsed = []
        for entry in timeline_text.split('; '):
            match = re.fullmatch(r'\[(\d+), (\d+)\): (.+)', entry)
            assert match, entry
            start_time, end_time, label = match.groups()
            segment = {'start': int(start_time), 'end': int(end_time)}
            if label.startswith('切换 '):
                before, after = label[3:].split('→')
                segment.update(kind='switch', from_process_id=before, to_process_id=after)
            else:
                segment.update(kind='run', process_id=label)
            parsed.append(segment)
        assert parsed == found['timeline'], sid + ': rendered timeline'
        for pid, values in found['per_process'].items():
            assert (pid + ' | ' + ' | '.join(str(values[key]) for key in
                    ('first_start', 'response', 'completion', 'turnaround'))) in block.splitlines()
        for label, value in [('平均响应时间', found['averages']['response']),
                             ('平均周转时间', found['averages']['turnaround']),
                             ('进程切换次数', found['switch_count']),
                             ('切换总开销', found['overhead']),
                             ('最终完成时刻', found['makespan'])]:
            assert f'{label}={value}' in block

    feasibility = {sid: True for sid in results}
    operators = {'le': lambda a, b: a <= b, 'lt': lambda a, b: a < b,
                 'ge': lambda a, b: a >= b, 'gt': lambda a, b: a > b,
                 'eq': lambda a, b: a == b}
    comparisons = {}
    for sid, result in results.items():
        for constraint in spec['selection']['constraints']:
            okay = operators[constraint['operator']](metric(result, constraint['metric']), rational(constraint['threshold']))
            comparisons[(sid, constraint['metric'])] = okay
            feasibility[sid] &= okay
    feasible = [sid for sid, okay in feasibility.items() if okay]
    selected_metric = spec['selection']['metric']
    assert spec['selection']['direction'] == 'min'
    best = min(metric(results[sid], selected_metric) for sid in feasible)
    optima = [sid for sid in feasible if metric(results[sid], selected_metric) == best]
    claim_count = 0
    for claim in compiled['claims']:
        kind = claim['type']
        if kind == 'conservation':
            found = results[claim['scenario_id']]
            assert claim['service'] == sum(p['burst'] for p in spec['processes'])
            assert all(claim[k] == found[k] for k in ('idle', 'overhead', 'makespan'))
            explanation = f"{claim['scenario_id']}：总服务 {claim['service']} + 空闲 {found['idle']} + 切换开销 {found['overhead']} = 最终完成时刻 {found['makespan']}。"
            assert explanation in question['explanation'].splitlines()
        elif kind == 'threshold_comparison':
            assert rational(claim['value']) == metric(results[claim['scenario_id']], claim['metric'])
            assert claim['satisfied'] == comparisons[(claim['scenario_id'], claim['metric'])]
            constraint = next(c for c in spec['selection']['constraints'] if c['metric'] == claim['metric'])
            assert claim['operator'] == constraint['operator'] and claim['threshold'] == constraint['threshold']
            label = {'overhead': '切换总开销', 'switch_count': '进程切换次数'}[claim['metric']]
            line = (f"{claim['scenario_id']}: {label} {rational(claim['value'])} <= {rational(claim['threshold'])} → "
                    + ('满足' if claim['satisfied'] else '不满足'))
            assert line in answer.splitlines()
        elif kind == 'optimal_selection':
            assert claim['feasible_scenario_ids'] == feasible
            assert claim['optimal_scenario_ids'] == optima and rational(claim['optimal_value']) == best
            assert f"最优方案：{'、'.join(optima)}；平均响应时间={best}。" in answer
        else:
            raise AssertionError('Unsupported claim: ' + kind)
        assert claim['verified'] is True
        claim_count += 1

    print(json.dumps({'archive_sha256': sha256(raw).hexdigest(), 'scenarios': len(results),
                      'timeline_intervals': intervals_checked, 'process_rows': rows_checked,
                      'process_scalars': scalars_checked, 'aggregate_metrics': aggregate_checked,
                      'claims': claim_count, 'threshold_checks': len(comparisons),
                      'remaining_queries': len(spec['remaining_queries']),
                      'feasible': feasible, 'optima': optima,
                      'rows': {sid: {k: str(metric(r, k)) for k in
                               ('mean_response', 'mean_turnaround', 'switch_count', 'overhead', 'makespan')}
                               for sid, r in results.items()}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    audit()
