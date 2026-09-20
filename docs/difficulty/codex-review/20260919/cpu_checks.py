"""Condition-masked retrospective AI-assisted CPU-question checks.

Only packets.json CPU questions, their sources, and the review protocol are read.
No mappings, original experiment files or previous ratings are used. This helper
does not assign difficulty or group scores. Inputs are AI-transcribed; scheduling
calculations are deterministic and explicitly branch on missing boundary rules.
"""
from collections import deque
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE.parents[1] / 'CODEX_REVIEW_PROTOCOL_V1.md'


def fraction(value, denominator=1):
    number = Fraction(value, denominator)
    return {'exact': str(number), 'decimal': float(number)}


def rr(jobs, q, overhead=0, boundary='before', during_switch='tail', early_finish_free=False):
    remaining = {name: service for name, (arrival, service) in jobs.items()}
    pending = sorted(jobs, key=lambda name: (jobs[name][0], name))
    ready = deque()
    segments = []
    time = 0
    previous = None
    previous_early_finish = False
    switches = 0
    charged = 0

    def arrive(until, inclusive=True, before_anchor=None):
        while pending and (jobs[pending[0]][0] <= until if inclusive else jobs[pending[0]][0] < until):
            name = pending.pop(0)
            if before_anchor in ready:
                ready.insert(ready.index(before_anchor), name)
            else:
                ready.append(name)

    arrive(time)
    while ready or pending:
        if not ready:
            time = jobs[pending[0]][0]
            arrive(time)
        name = ready.popleft()
        if previous is not None and name != previous:
            switches += 1
            cost = 0 if early_finish_free and previous_early_finish else overhead
            if cost:
                segments.append({'kind': 'switch', 'from': previous, 'to': name, 'start': time, 'end': time + cost})
                anchor = previous if during_switch == 'before_preempted' and remaining[previous] else None
                arrive(time + cost, before_anchor=anchor)
                time += cost
                charged += 1
        duration = min(q, remaining[name])
        end = time + duration
        segments.append({'kind': 'run', 'job': name, 'start': time, 'end': end})
        remaining[name] -= duration
        arrive(end, inclusive=False)
        if boundary == 'before':
            arrive(end)
        if remaining[name]:
            ready.append(name)
        if boundary == 'after':
            arrive(end)
        previous = name
        previous_early_finish = remaining[name] == 0 and duration < q
        time = end
    result = metrics(segments, jobs)
    result.update(q=q, switch_cost=overhead, boundary_arrivals=boundary,
                  during_switch=during_switch, early_finish_switch_free=early_finish_free,
                  context_switches=switches, charged_switches=charged)
    return result


def stcf(jobs):
    remaining = {name: service for name, (_, service) in jobs.items()}
    segments = []
    time = 0
    while any(remaining.values()):
        ready = [name for name in jobs if jobs[name][0] <= time and remaining[name]]
        if not ready:
            time += 1
            continue
        name = min(ready, key=lambda key: (remaining[key], key))
        segments.append({'kind': 'run', 'job': name, 'start': time, 'end': time + 1})
        remaining[name] -= 1
        time += 1
    return metrics(segments, jobs)


def metrics(segments, jobs):
    runs = [segment for segment in segments if segment['kind'] == 'run']
    first = {name: min(row['start'] for row in runs if row['job'] == name) for name in jobs}
    complete = {name: max(row['end'] for row in runs if row['job'] == name) for name in jobs}
    delivered = {name: sum(row['end'] - row['start'] for row in runs if row['job'] == name) for name in jobs}
    assert delivered == {name: data[1] for name, data in jobs.items()}
    assert all(row['start'] >= jobs[row['job']][0] for row in runs)
    assert all(left['end'] == right['start'] for left, right in zip(segments, segments[1:]))
    response = {name: first[name] - data[0] for name, data in jobs.items()}
    turnaround = {name: complete[name] - data[0] for name, data in jobs.items()}
    switch_time = sum(row['end'] - row['start'] for row in segments if row['kind'] == 'switch')
    total_service = sum(data[1] for data in jobs.values())
    assert segments[-1]['end'] == total_service + switch_time
    return {'timeline': segments, 'first_run': first, 'completion': complete,
            'response': response, 'turnaround': turnaround,
            'average_response': fraction(sum(response.values()), len(jobs)),
            'average_turnaround': fraction(sum(turnaround.values()), len(jobs)),
            'total_turnaround': sum(turnaround.values()), 'maximum_response': max(response.values()),
            'switch_time': switch_time, 'makespan': segments[-1]['end'],
            'overhead_fraction': fraction(switch_time, total_service + switch_time),
            'delivered_service': delivered}


def calculations():
    j532 = {'A': (0, 5), 'B': (1, 3), 'C': (2, 2)}
    j631 = {'A': (0, 6), 'B': (1, 3), 'C': (2, 1)}
    out = {
        'Q002': {'q2_zero_cost': rr(j532, 2),
                 'q2_cost1': rr(j532, 2, 1, during_switch='before_preempted')},
        'Q003': {f'q{q}_{boundary}': rr(j532, q, boundary=boundary)
                 for q in (1, 2) for boundary in ('before', 'after')},
        'Q004': {f'q{q}': rr({'A': (0, 8), 'B': (2, 4), 'C': (4, 2)}, q, 1) for q in (1, 2)},
        'Q016': {'rr_q2': rr(j631, 2), 'stcf': stcf(j631)},
        'Q021': {f'q{q}_fifo_rr': rr({'A': (0, 3), 'B': (1, 2), 'C': (2, 1)}, q) for q in (1, 2)},
        'Q023': {f'q{q}_conditional_zero_cost': rr({'A': (0, 8), 'B': (0, 4), 'C': (0, 2)}, q) for q in (1, 2, 4)},
        'Q025': {f'q{q}_early_finish_free': rr({'A': (0, 6), 'B': (1, 3), 'C': (2, 2)}, q, 1, early_finish_free=True) for q in (2, 4)},
        'Q031': {f'q{q}_{boundary}': rr(j631, q, 1, boundary=boundary)
                 for q in (1, 2) for boundary in ('before', 'after')},
        'Q032': {f'q{q}': rr({'A': (0, 6), 'B': (2, 3), 'C': (4, 3)}, q, 1) for q in (1, 3, 6)},
        'Q040': {f'q{q}': rr(j631, q, 1, during_switch='before_preempted') for q in (1, 3)},
    }
    # Hand-checkable regression boundaries independent of answer text.
    assert out['Q016']['rr_q2']['average_response']['exact'] == '1'
    assert out['Q016']['rr_q2']['average_turnaround']['exact'] == '20/3'
    assert out['Q025']['q4_early_finish_free']['switch_time'] == 1
    assert out['Q032']['q3']['maximum_response'] == 8
    return out


NOTES = {
    'Q002': {
        'finding': '前两问的时间线和周转总量正确；第三问混用无开销响应时间与有开销占比，并把总服务量10误当作5。',
        'answerability': '两种计算情形明确；第三问应对带开销系统检验两个约束，不能用第一问的响应值。',
        'details': 'q=2且开销1时响应为0/2/4，平均2；开销5、有效服务10，占比5/15=1/3。两项约束均失败，而非只有开销失败。增大片长或MLFQ的泛化建议不构成满足约束的证明。'},
    'Q003': {
        'finding': '多个实质错误：q=2答案没有正确处理C在t=2到达，A少分配CPU；q=1答案也使A少获1单位服务；约束判断把首次运行时间当响应时间。',
        'answerability': '没有明确片尾同时到达与被抢占任务的相对顺序；切换期间规则不能在s=0时唯一补足片尾规则。输出两种条件计算，不选一个冒充唯一答案。',
        'details': '新到优先时q=2响应0/1/2、q=1响应0/0/1，两者均满足最大响应≤2；被抢占优先时q=2响应0/1/4不满足、q=1响应0/1/2满足。两种解释均与原答案的服务量和部分约束结论不符。'},
    'Q004': {
        'finding': '参考答案把C错误排在已经等待的A之前。B在t=2开始切换时A已排队，C在t=4才到达，必须排在A后。',
        'answerability': '数值任务基本可判定；当前q=1/q=2轨迹没有需额外处理的切换内部新到达事件。最终双目标没有给开销阈值，故不应唯一断言最优设计。',
        'details': 'q=2应为A0–2、切换2–3、B3–5、切换5–6、A6–8、切换8–9、C9–11、切换11–12、B12–14、切换14–15、A15–19。平均响应2，平均周转38/3；原答案1及35/3错误。q=1最大响应3，小于q=2的5，但切换次数从5增至10。'},
    'Q016': {
        'finding': 'RR错误地让C超过已等待的B；STCF时间线和计算正确。',
        'answerability': '题干条件完整。该题与同会话此前见过的错误案例相同；本核查属条件遮盖回顾性辅助核查，不能称为独立盲评。',
        'details': 'RR应为A0–2、B2–4、C4–5、A5–7、B7–8、A8–10；平均响应1、平均周转20/3。STCF平均响应0、平均周转5。推荐STCF的相对结论仍成立。'},
    'Q021': {
        'finding': '两组答案均违反CPU服务量：q=1给A分配4而非3；q=2给B分配1而非2；q=1还让C插到既有等待A前。',
        'answerability': '“多个任务可用时按到达早者优先”若用于每次派发会与RR队列轮转冲突。这里给出保留RR FIFO、到达顺序仅用于入队的条件计算，需澄清该措辞。',
        'details': '标准RR下q=1为A0–1 B1–2 A2–3 C3–4 B4–5 A5–6，响应0/0/1、周转6/4/2；q=2为A0–2 B2–4 C4–5 A5–6，响应0/1/2、周转6/3/3。两者平均周转均4，并非原答案所称q=2更优；切换次数5与3。'},
    'Q023': {
        'finding': '切换开销大小未给，且未明确忽略；固定响应时刻和可行性不可直接得出。即使条件性令开销为0，三个切换计数也错误，所列轮转序列还违反各任务服务量。',
        'answerability': '关键数值条件缺失。令每次切换开销为s≥0，不能把s=0作为题设事实。',
        'details': 'q=1/2/4首次运行分别为(0,1+s,2+2s)/(0,2+s,4+2s)/(0,4+s,8+2s)；不同任务间切换次数分别10/5/3，而非13/7/4。原q=1序列给A7单位、B5单位，而要求A8/B4；q=2多一次B，q=4多一次A。s=0时仅q=1满足最大响应≤2；任何s>0时三个候选均不满足。移除响应约束后q=4切换最少。'},
    'Q025': {
        'finding': '答案忽略题干“提前完成后的转换免费”的明确例外，仍逐次计费；R2最后B→A、R4的B→C与C→A均不该收费。',
        'answerability': '把具体提前完成条款作为一般切换收费规则的例外，可以唯一计算；原答案末尾重复例外却未执行。',
        'details': 'R2完成A/B/C=15/13/8，平均响应2、平均周转11，付费切换4；R4首次0/5/8，完成12/8/10，平均响应10/3、平均周转9，付费切换1（任务转换仍有3次）。按主要目标仍选R2，但原指标均有实质错误。'},
    'Q031': {
        'finding': '答案同时遗漏arrival减项、给B超额CPU、最后同一A续跑仍计切换，并给出与时间线不一致的切换数。',
        'answerability': '未直接规定片尾到达者与被抢占者的先后；一般alphabetical tie规则未说明是否针对这类入队事件。列出前后两种解释，不据此假定唯一时间线。',
        'details': '新到先入队时q=2平均响应2、平均周转31/3；q=1平均响应5/3、平均周转34/3。被抢占先入队时q=2平均响应3、平均周转34/3；q=1平均响应7/3、平均周转12。两种情况下q=1都改善响应却恶化平均周转；原答案称周转也改善不成立。'},
    'Q032': {
        'finding': 'q=1在只有A可运行时凭空计切换，且给出的完成时刻与服务+开销守恒不符；q=3让切换结束才到达的C超过此前已排队A，导致把不可行方案误判可行。q=6计算正确。',
        'answerability': '切换结束到达的C应进入已有FIFO队尾；题干只对“片尾到达”规定新到先于被抢占者，不能把规则扩展到已经在队列等待的A。MLFQ泛化建议不能保证一个数值响应上限。',
        'details': 'q=1首次0/3/7、完成22/16/20、响应0/1/3、开销10；q=3首次0/4/12、完成11/7/15、响应0/2/8、开销3；q=6响应0/5/7、开销2。因此三个给定候选均不能同时满足响应≤4和开销≤4，并非q=3可行。'},
    'Q040': {
        'finding': 'q=1在C完成后错把B排到A前，导致后续完成时刻、平均周转、切换总数和占比错误；q=3结果正确。',
        'answerability': '计算采用题设切换期间新到任务插在被抢占者前，并在切换结束派发前处理该时刻到达。该事件顺序需在模拟证据中明确。两个平均值同时最小没有权重，但可判定两个候选均违反开销硬约束。',
        'details': 'q=1为A0–1、切换1–2、B2–3、切换3–4、C4–5、切换5–6、A6–7、切换7–8、B8–9、切换9–10、A10–11、切换11–12、B12–13、切换13–14、A14–17。平均响应1、平均周转32/3、7次切换，占比7/17。q=3平均响应3、平均周转26/3、开销3/13。两者均超过20%。'},
}


def brief_timeline(result):
    merged = []
    for row in result['timeline']:
        label = row['job'] if row['kind'] == 'run' else f"switch {row['from']}→{row['to']}"
        if merged and merged[-1][0] == label and merged[-1][2] == row['start']:
            merged[-1] = (label, merged[-1][1], row['end'])
        else:
            merged.append((label, row['start'], row['end']))
    return ' → '.join(f'{label} {start}–{end}' for label, start, end in merged)


def main():
    packets = [packet for packet in json.loads((HERE / 'packets.json').read_text())
               if 'cpu_scheduling' in packet['source_key']]
    source_keys = {packet['source_key'] for packet in packets}
    all_sources = json.loads((HERE / 'sources.json').read_text())
    sources = {key: all_sources[key] for key in sorted(source_keys)}
    encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    calculated = calculations()
    assert {packet['blind_id'] for packet in packets} == set(calculated) == set(NOTES)
    report = {
        'review_kind': 'Condition-masked retrospective AI-assisted factual and numerical check',
        'independent_human_review': False, 'independent_model_vote': False,
        'prior_context_known': 'Same conversation contains earlier canary analysis; Q016 is recognized.',
        'final_difficulty_or_group_scores_assigned': False,
        'original_or_previous_scores_read_or_modified': False,
        'cpu_packets_sha256': hashlib.sha256(encode(packets)).hexdigest(),
        'cpu_sources_sha256': hashlib.sha256(encode(sources)).hexdigest(),
        'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        'method': 'AI transcription of each stem; deterministic FIFO RR/STCF simulation, exact fractions, service/arrival/time-conservation assertions. Missing rules produce explicitly conditional variants.',
        'checks': [{'blind_id': packet['blind_id'], 'source_key': packet['source_key'],
                    'question_sha256': hashlib.sha256(encode(packet['question'])).hexdigest(),
                    **NOTES[packet['blind_id']], 'calculations': calculated[packet['blind_id']]}
                   for packet in packets],
    }
    (HERE / 'cpu_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# CPU 调度题事实与数值辅助核查', '',
             '这是条件遮盖的回顾性 AI 辅助核查。同会话已见过一个错误案例（此包 Q016），不是独立人审或多模型投票；不在此文件给最终难度、逐题子分或组分。未读取映射、旧评分或原实验目录。', '',
             '题干语义解释与参数录入由 AI 完成；以下数值来自可复跑的确定性模拟。缺失条件列出不同解释，不把补充假定当成原题事实。模拟检查 CPU 服务量守恒、到达前无执行、时间连续性和总服务加开销等于完成总长。', '',
             f"CPU题包哈希：`{report['cpu_packets_sha256']}`。CPU资料哈希：`{report['cpu_sources_sha256']}`。协议哈希：`{report['protocol_sha256']}`。", '']
    for item in report['checks']:
        lines += [f"## {item['blind_id']}", '', item['finding'], '',
                  '可作答性：' + item['answerability'], '', item['details'], '']
        for name, result in item['calculations'].items():
            lines += [f'**{name}**：{brief_timeline(result)}。', '',
                      f"首次运行 {result['first_run']}；完成 {result['completion']}；响应 {result['response']}；周转 {result['turnaround']}。平均响应 {result['average_response']['exact']}；平均周转 {result['average_turnaround']['exact']}；开销 {result['switch_time']}；占比 {result['overhead_fraction']['exact']}。", '']
    lines += ['复跑：`python docs/difficulty/codex-review/20260919/cpu_checks.py`。只生成本目录 cpu_checks.json 与 cpu_checks.md，不改评分或题包。', '']
    (HERE / 'cpu_checks.md').write_text('\n'.join(lines))
    for item in report['checks']:
        print(item['blind_id'], item['finding'])


if __name__ == '__main__':
    main()
