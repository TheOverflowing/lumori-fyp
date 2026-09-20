"""Independent AI-assisted arithmetic audit of one archived scheduling question.

Run with Python's standard library. This reads only the named original asset,
not experiment records, strategy labels or Qwen judge output. Job parameters and
policy conventions were interpreted from the question by an AI reviewer; the
calculations below are deterministic. This is not human annotation, student
calibration, or a replacement for the original experimental score.
"""
from collections import deque
from fractions import Fraction
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSET = Path('docs/difficulty/experiments/20260919T085353763975Z/items/9c4722009bbb28649377/asset.json')
ASSET_SHA256 = '2e0706fe28fb04dd82f8053f894b789937c1526fcd9c422fe8740f6e49bcf532'
STEM_SHA256 = '074997e80f5659966d1b6fe1482261366da7ac70bced8805b44c98be762c0097'
JOBS = {'A': {'arrival': 0, 'service': 6},
        'B': {'arrival': 1, 'service': 3},
        'C': {'arrival': 2, 'service': 1}}


def round_robin(jobs, quantum=2):
    remaining = {name: job['service'] for name, job in jobs.items()}
    pending = sorted(jobs, key=lambda name: (jobs[name]['arrival'], name))
    ready = deque()
    timeline = []
    time = 0

    def enqueue_through(boundary):
        # Existing queued jobs stay ahead of any new arrivals. Arrivals up to
        # and including the boundary are inserted before the preempted job.
        while pending and jobs[pending[0]]['arrival'] <= boundary:
            ready.append(pending.pop(0))

    enqueue_through(time)
    while ready or pending:
        if not ready:
            time = jobs[pending[0]]['arrival']
            enqueue_through(time)
        name = ready.popleft()
        end = time + min(quantum, remaining[name])
        timeline.append({'start': time, 'end': end, 'job': name})
        remaining[name] -= end - time
        enqueue_through(end)
        if remaining[name]:
            ready.append(name)
        time = end
    return timeline


def shortest_time_to_completion(jobs):
    # This question has integer arrivals and CPU lengths. One-unit simulation
    # independently reselects the shortest remaining job at every possible event.
    remaining = {name: job['service'] for name, job in jobs.items()}
    timeline = []
    time = 0
    while any(remaining.values()):
        available = [name for name in jobs if jobs[name]['arrival'] <= time and remaining[name] > 0]
        if not available:
            time += 1
            continue
        name = min(available, key=lambda item: (remaining[item], item))
        if timeline and timeline[-1]['job'] == name and timeline[-1]['end'] == time:
            timeline[-1]['end'] = time + 1
        else:
            timeline.append({'start': time, 'end': time + 1, 'job': name})
        remaining[name] -= 1
        time += 1
    return timeline


def describe(timeline, jobs):
    first = {name: min(row['start'] for row in timeline if row['job'] == name) for name in jobs}
    completion = {name: max(row['end'] for row in timeline if row['job'] == name) for name in jobs}
    response = {name: first[name] - jobs[name]['arrival'] for name in jobs}
    turnaround = {name: completion[name] - jobs[name]['arrival'] for name in jobs}
    delivered = {name: sum(row['end'] - row['start'] for row in timeline if row['job'] == name) for name in jobs}
    assert all(delivered[name] == job['service'] for name, job in jobs.items())
    assert all(row['start'] >= jobs[row['job']]['arrival'] for row in timeline)
    assert all(left['end'] == right['start'] for left, right in zip(timeline, timeline[1:]))

    def average(values):
        exact = Fraction(sum(values.values()), len(jobs))
        return {'exact': str(exact), 'decimal': float(exact)}

    return {'timeline': timeline, 'first_run': first, 'completion': completion,
            'response_time': response, 'turnaround_time': turnaround,
            'average_response_time': average(response), 'average_turnaround_time': average(turnaround),
            'cpu_service_delivered': delivered}


def build_report():
    raw = (ROOT / ASSET).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ASSET_SHA256:
        raise ValueError('The archived asset differs from the audited snapshot.')
    asset = json.loads(raw)
    stem = asset['questions'][0]['stem']
    if hashlib.sha256(stem.encode()).hexdigest() != STEM_SHA256:
        raise ValueError('The question stem differs from the audited snapshot.')
    rr = describe(round_robin(JOBS), JOBS)
    stcf = describe(shortest_time_to_completion(JOBS), JOBS)
    assert rr['first_run'] == {'A': 0, 'B': 2, 'C': 4}
    assert rr['completion'] == {'A': 10, 'B': 8, 'C': 5}
    assert rr['average_response_time']['exact'] == '1'
    assert rr['average_turnaround_time']['exact'] == '20/3'
    assert stcf['first_run'] == {'A': 0, 'B': 1, 'C': 2}
    assert stcf['completion'] == {'A': 10, 'B': 5, 'C': 3}
    assert stcf['average_response_time']['exact'] == '0'
    assert stcf['average_turnaround_time']['exact'] == '5'
    return {
        'audit_id': 'rr-canary-20260919', 'audit_date': '2026-09-19',
        'evidence_type': 'Additional AI review with deterministic calculation',
        'human_review': False, 'student_difficulty_calibrated': False,
        'original_strategy_labels_read': False, 'original_qwen_score_read': False,
        'original_qwen_score_modified': False, 'original_experiment_modified': False,
        'source_asset': str(ASSET), 'source_asset_sha256': ASSET_SHA256,
        'question_stem_sha256': STEM_SHA256, 'question_stem': stem,
        'scope': 'Correctness of this single scheduling answer; no new difficulty rating or whole-run accuracy estimate.',
        'inputs': {'jobs': JOBS, 'rr_quantum': 2, 'context_switch_overhead': 0,
                   'tie_breaking': 'Alphabetical job names',
                   'boundary_rule': 'New arrivals enqueue after existing waiting jobs but before the preempted job.'},
        'round_robin': rr, 'stcf': stcf,
        'findings': [
            {'kind': 'queue_order_error', 'original': 'At t=2: C, B, A',
             'correct': 'At t=2: B, C, A',
             'reason': 'B has waited since t=1. C arriving at t=2 precedes preempted A, but cannot overtake B.'},
            {'kind': 'rr_average_response_time', 'original': '2/3', 'correct': '1'},
            {'kind': 'rr_average_turnaround_time', 'original': '6', 'correct': '20/3'},
            {'kind': 'stcf_calculation', 'result': 'The original first-run/completion times and averages agree with this calculation.'},
            {'kind': 'recommendation', 'result': 'STCF still minimizes average response time among the two specified policies for this workload.'},
            {'kind': 'visual_prompt', 'result': 'The original visual_prompt repeats the incorrect RR timeline.'},
        ],
        'limitations': [
            'An AI reviewer translated the natural-language problem into these fixed scheduler inputs and interpreted the discrepancy.',
            'The calculations establish arithmetic for these rules and jobs; they do not calibrate educational difficulty.',
            'This additional audit is separate from the immutable original Qwen score and original experiment denominator.',
        ],
    }


def markdown(report):
    rr, stcf = report['round_robin'], report['stcf']
    def times(values):
        return ' / '.join(str(values[name]) for name in JOBS)
    def timeline(result):
        return ' → '.join(f"{row['job']} {row['start']}–{row['end']}" for row in result['timeline'])
    return f'''# RR canary 独立计算审计 — 2026-09-19

本记录是 **额外 AI 审查与确定性计算**，不是人工标注或学生实测。未读取原始策略标签或 Qwen 评分，未改变原始评分、题目或实验分母。不据此给整轮实验重新排名。

原始题目：[asset.json](../experiments/20260919T085353763975Z/items/9c4722009bbb28649377/asset.json)。原始文件 SHA-256：`{ASSET_SHA256}`。题干 SHA-256：`{STEM_SHA256}`。

## 结论

Round Robin 参考答案有队列顺序错误；STCF 计算正确。题干规定边界时刻的新到达任务先于被抢占任务入队，不能让新到达任务超过已经等待的任务。B 从 t=1 开始等待，所以 t=2 的队列应为 **B → C → A**，而非原答案的 C → B → A。

- RR，时间片 2：{timeline(rr)}。
- STCF：{timeline(stcf)}。

| 指标（任务顺序 A / B / C） | RR | STCF |
|---|---|---|
| 首次运行 | {times(rr['first_run'])} | {times(stcf['first_run'])} |
| 完成时间 | {times(rr['completion'])} | {times(stcf['completion'])} |
| 响应时间 | {times(rr['response_time'])} | {times(stcf['response_time'])} |
| 平均响应时间 | {rr['average_response_time']['exact']} | {stcf['average_response_time']['exact']} |
| 周转时间 | {times(rr['turnaround_time'])} | {times(stcf['turnaround_time'])} |
| 平均周转时间 | {rr['average_turnaround_time']['exact']} | {stcf['average_turnaround_time']['exact']} |

原答案的 RR 平均响应时间 2/3 和平均周转时间 6 均应修正。STCF 在题目指定的两个候选策略及该工作负载中仍更符合平均响应时间目标。原 `visual_prompt` 同样复制了错误的 RR 时间线。

## 核算方法与边界

AI 审查者从题干录入到达／服务时间 A=(0,6)、B=(1,3)、C=(2,1)，忽略切换开销，采用题干规定的边界入队顺序与字母顺序平局规则。RR 使用就绪队列事件模拟；STCF 使用独立的逐时间单位剩余时长选择模拟。本题输入均为整数，该步长覆盖所有决策时刻。程序检查服务量守恒、无到达前执行、无时间重叠或无故空档，并用有理数计算平均值。

复跑：`python docs/difficulty/audits/rr_canary_20260919.py`。脚本只读取被哈希绑定的原始 asset；输出本目录的 [JSON 计算证据](rr_canary_20260919.json) 与本说明，不读取或改写实验 records/judge 文件。模拟证明的是该题给定规则下的时间线和算术，不是题目难度、人类判断或整个评审模型的准确率。
'''


if __name__ == '__main__':
    report = build_report()
    here = Path(__file__)
    here.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    here.with_suffix('.md').write_text(markdown(report))
    print(json.dumps({'round_robin': {'average_response': report['round_robin']['average_response_time'],
                                     'average_turnaround': report['round_robin']['average_turnaround_time']},
                      'stcf': {'average_response': report['stcf']['average_response_time'],
                               'average_turnaround': report['stcf']['average_turnaround_time']},
                      'human_review': False, 'original_experiment_modified': False}, ensure_ascii=False))
