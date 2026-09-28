"""Frozen v1 solver versus v2 judge diagnostic. Dry by default; at most 32 calls."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.generation_agent import CheckedSolution
from app.providers import ApiProviders
from scripts.difficulty_experiment import CappedStore, call_rows, digest, write_json, safe_error
from scripts.difficulty_judge_v2 import messages, validate, REVISION
from scripts import difficulty_judge_v3 as v3
from scripts import difficulty_judge_v4 as v4

DATA = ROOT / 'benchmarks/difficulty_judge_v2'
LEVELS = {'easy': 0, 'medium': 1, 'hard': 2}

def baseline(case, template):
    result = deepcopy(template['messages'])
    contract = json.loads(result[1]['content'])
    contract['learner_profile'] = case['learner_profile']
    contract['question'] = {'kind': 'short_answer', 'stem': case['student_visible_text'], 'options': []}
    # Every required exercise fact is visible. No answer, author target, or private
    # hints from the original R8 case may leak into a new fixture.
    contract['reference_chunks'] = []
    contract['student_visible_context']['sections'] = []
    result[1]['content'] = json.dumps(contract, ensure_ascii=False)
    return result

def normalize(arm, raw, case):
    if arm in ('v2', 'v3', 'v4'):
        result = ({'v2': validate, 'v3': v3.validate, 'v4': v4.validate}[arm])(raw, case)
        return result, result['estimated_difficulty'], result['eligibility']
    result = CheckedSolution.model_validate(raw).model_dump()
    eligible = (result['answerable'] and result['ambiguity_free']
                and not result['question_checks']['condition_issues'])
    # Baseline cannot abstain on difficulty in its schema; show its raw label too.
    return result, result['assessed_difficulty'] if eligible else 'uncertain', 'eligible' if eligible else 'invalid_question'

def summarize(records, dataset, repeats, arms=('v1', 'v2')):
    summary = {'human_accuracy': None, 'weighted_kappa': None,
               'reason': 'No independent teacher labels; diagnostic fixture expectations are not gold difficulty.',
               'arms': {}}
    for arm in arms:
        rows = [r for r in records if r['arm'] == arm]
        valid = [r for r in rows if r['status'] == 'valid']
        groups = {c['id']: [r for r in rows if r['case_id'] == c['id']] for c in dataset['cases']}
        stable = 0
        determinate_stable = 0
        per_case = {}
        for id, group in groups.items():
            labels = [r.get('label', 'failed') for r in group]
            complete = len(group) == repeats and all(r['status'] == 'valid' for r in group)
            same = complete and len(set(labels)) == 1
            stable += int(same)
            determinate_stable += int(same and labels[0] != 'uncertain')
            per_case[id] = {'labels': labels, 'complete': complete, 'stable': same}
        controls = []
        for relation in dataset['relations']:
            checks = []
            for rep in range(repeats):
                a = next((r for r in groups[relation['a']] if r['repeat'] == rep), {})
                b = next((r for r in groups[relation['b']] if r['repeat'] == rep), {})
                la, lb = a.get('label'), b.get('label')
                ok = None
                if la in LEVELS and lb in LEVELS:
                    ok = la == lb if relation['expectation'] == 'equal' else LEVELS[lb] <= LEVELS[la]
                checks.append(ok)
            controls.append({**relation, 'checks': checks,
                             'comparable': sum(x is not None for x in checks),
                             'passed': sum(x is True for x in checks)})
        summary['arms'][arm] = {'scheduled': len(rows), 'valid': len(valid),
            'failures': len(rows)-len(valid), 'stable_cases': stable,
            'determinate_stable_cases': determinate_stable, 'total_cases': len(groups),
            'abstentions': sum(r['label'] == 'uncertain' for r in valid),
            'label_counts': dict(Counter(r['label'] for r in valid)),
            'by_domain': {domain: dict(Counter(r['label'] for r in valid if r['domain'] == domain))
                          for domain in sorted({c['domain'] for c in dataset['cases']})},
            'per_case': per_case, 'controls': controls}
    return summary

def report(summary, manifest):
    arms = list(summary['arms'])
    lines = [f"# 难度评委 {' / '.join(arms)} 固定题诊断", '',
        '本轮比较评估流程，两个版本使用同一模型与参数、独立上下文。不是不同模型评委实验，也不是完整 Harness 端到端复现。', '',
        f"实际调用 {manifest['actual_calls']}；报告 token {manifest['total_tokens']}；缺失费用记录 {manifest['calls_without_cost']} 条。",
        '没有教师标签和学生实测数据：准确率、加权 κ 均为 null，不能宣称新方法更准确。', '',
        '| 方法 | 有效/计划 | 稳定题数 | 明确等级且稳定 | 弃判次数 |', '|---|---:|---:|---:|---:|']
    for arm, m in summary['arms'].items():
        lines.append(f"| {arm} | {m['valid']}/{m['scheduled']} | {m['stable_cases']}/{m['total_cases']} | {m['determinate_stable_cases']}/{m['total_cases']} | {m['abstentions']} |")
    lines += ['', '稳定题数包含稳定弃判；明确等级且稳定另列。任何一次失败都不能计为稳定。有限次重复是小样本诊断。', '', f'| 题目 | {arms[0]} | {arms[1]} |', '|---|---|---|']
    for id in summary['arms'][arms[0]]['per_case']:
        labels = [', '.join(summary['arms'][a]['per_case'][id]['labels']) for a in arms]
        lines.append(f'| {id} | {labels[0]} | {labels[1]} |')
    lines += ['', '## 对照检查', '', '仅比较两次都有明确等级的配对；弃判和失败不可算通过。这些是开发者预设的行为假设，不是教师金标准。', '']
    for arm, m in summary['arms'].items():
        for c in m['controls']:
            lines.append(f"- {arm}: {c['a']} → {c['b']} ({c['expectation']}): {c['passed']}/{c['comparable']} 可比较配对通过，共 {len(c['checks'])} 对。")
    lines += ['', '正式判级流程未切换；下一步需要教师独立标注、仲裁以及与参照题分离的测试集。', '']
    return '\n'.join(lines)

async def run(args):
    dataset = json.loads(args.dataset.read_text())
    arms = tuple(args.comparison.split('-'))
    ids = [c['id'] for c in dataset['cases']]
    if len(ids) != len(set(ids)) or any(r['a'] not in ids or r['b'] not in ids for r in dataset['relations']):
        raise ValueError('Duplicate case IDs or unresolved relation')
    template = json.loads((DATA/'baseline_template.json').read_text())
    planned = len(dataset['cases']) * 2 * args.repeats
    if not 1 <= args.repeats <= 3 or not planned <= args.max_calls <= 32:
        raise ValueError('Plan must fit explicit call cap (maximum 32)')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'revision': v4.REVISION if 'v4' in arms else v3.REVISION if 'v3' in arms else REVISION, 'arms': arms, 'status': 'prepared', 'live': args.live,
        'planned_calls': planned, 'call_cap': args.max_calls, 'repeats': args.repeats,
        'dataset_sha256': digest(dataset), 'baseline_sha256': digest(template),
        'human_labels': False, 'seed': 924, 'transport': 'ApiProviders JSON; no ACP wrapper or tool execution',
        'started_at': datetime.now(timezone.utc).isoformat()}
    write_json(output/'dataset.json', dataset)
    write_json(output/'baseline_template.json', template)
    hashes = {}
    for path in list((ROOT/'app').glob('*.py')) + list((ROOT/'scripts').glob('*.py')) + list((ROOT/'tests').glob('test_difficulty_judge_v*.py')):
        rel = path.relative_to(ROOT)
        dest = output/'code'/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
        hashes[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['code_sha256'] = hashes
    rows = []
    for case in dataset['cases']:
        for arm in arms:
            for repeat in range(args.repeats):
                rows.append(dict(id=f"{case['id']}_{arm}_{repeat}", case_id=case['id'], domain=case['domain'],
                                 arm=arm, repeat=repeat, status='pending'))
    random.Random(924).shuffle(rows)
    cases = {c['id']: c for c in dataset['cases']}
    for row in rows:
        case = cases[row['case_id']]
        prompt = baseline(case, template) if row['arm'] == 'v1' else ({'v2': messages, 'v3': v3.messages, 'v4': v4.messages}[row['arm']])(case)
        write_json(output/'items'/row['id']/'prompt.json', prompt)
    write_json(output/'manifest.json', manifest)
    write_json(output/'records.json', rows)
    print(json.dumps({'output':str(output),'planned_calls':planned,'live':args.live}), flush=True)
    if not args.live:
        return
    settings = Settings.from_env()
    settings = replace(settings, timeout=120, text_json_mode=True,
        text=replace(settings.text, extra={'thinking': {'type': 'disabled'}, 'temperature': 0, 'max_tokens': 6000}))
    if not settings.text.api_key:
        raise ValueError('Configured text provider key required')
    store = CappedStore(Path(tempfile.mkdtemp(prefix='lumori-judge-v2-')), args.max_calls)
    provider = ApiProviders(settings, store)
    manifest.update(status='running', model=settings.text.model, parameters=settings.text.extra)
    write_json(output/'manifest.json', manifest)
    try:
        for row in rows:
            case = cases[row['case_id']]
            prompt = json.loads((output/'items'/row['id']/'prompt.json').read_text())
            try:
                raw = await provider.generate(prompt, row['id'])
                write_json(output/'items'/row['id']/'response.json', raw)
                result, label, eligibility = normalize(row['arm'], raw, case)
                row.update(status='valid', label=label, eligibility=eligibility, result=result)
            except Exception as exc:
                row.update(status='failed', error=safe_error(exc))
                calls = call_rows(store)
                # Stop on upstream/network errors; schema failures remain observations.
                if calls and calls[-1]['status'] != 'succeeded':
                    manifest['status'] = 'stopped_provider_failure'
                    break
            finally:
                write_json(output/'records.json', rows)
            print(row['id'], row['status'], row.get('label',''), flush=True)
        else:
            manifest['status'] = 'complete'
    finally:
        await provider.close()
        calls = call_rows(store)
        write_json(output/'calls.json', calls)
        manifest.update(actual_calls=len(calls), total_tokens=sum(c['usage'].get('total_tokens',0) for c in calls),
            calls_without_cost=sum('cost' not in c['usage'] for c in calls),
            reported_cost_usd=sum(c['usage'].get('cost',0) for c in calls) if all('cost' in c['usage'] for c in calls) else None,
            finished_at=datetime.now(timezone.utc).isoformat())
        summary = summarize(rows, dataset, args.repeats, arms)
        write_json(output/'summary.json', summary)
        write_json(output/'manifest.json', manifest)
        (output/'REPORT.md').write_text(report(summary, manifest))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--comparison', choices=['v1-v2', 'v2-v3', 'v3-v4'], default='v1-v2')
    parser.add_argument('--dataset', type=Path, default=DATA/'cases.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--max-calls', type=int, default=32)
    asyncio.run(run(parser.parse_args()))
