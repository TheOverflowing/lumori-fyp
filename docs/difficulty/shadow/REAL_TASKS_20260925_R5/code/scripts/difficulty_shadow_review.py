"""Build a blind review packet and a separate comparison from saved shadow exports.

This is read-only postprocessing: no provider calls or changes to generated content.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.difficulty_shadow import digest, visible_case


def collect(directories):
    rows = []
    for directory in directories:
        for path in sorted(directory.glob('task_*_evidence.json')):
            stem = path.name.removesuffix('_evidence.json')
            content_path = directory / f'{stem}_content.json'
            if not content_path.exists():
                continue  # A failed generation has no accepted question to grade.
            bundle = json.loads(path.read_text())
            content = json.loads(content_path.read_text())
            evidence = bundle['evidence']
            shadow = evidence.get('difficulty_shadow')
            if not shadow:
                continue
            asset = content['asset']
            sources = {item['id']: item for item in content.get('sources', [])}
            if digest(asset) != shadow['asset_sha256'] or content['version'] != 1:
                raise ValueError(f'{content_path}: accepted asset does not match observation')
            profile = evidence['request']['learner_profile']
            for index, question in enumerate(shadow['questions']):
                if index >= len(asset['questions']) or question['slot_id'] != asset['questions'][index]['slot_id']:
                    raise ValueError(f'{path}: question order or slot ID changed')
                case = visible_case(asset, index, profile)
                accepted_question = asset['questions'][index]
                if digest(case) != question['visible_input_sha256']:
                    raise ValueError(f'{path}: student-visible input does not match observation')
                judge = question.get('judge', {})
                audit = question.get('audit', {})
                result = judge.get('result', {}) if judge.get('status') == 'validated' else {}
                candidates = result.get('decision', {}).get('candidates', [])
                original = question.get('original_difficulty')
                published = question.get('published_difficulty')
                if judge.get('status') != 'validated' or result.get('eligibility') != 'eligible':
                    comparison = 'requires_review'
                elif len(candidates) != 1:
                    comparison = 'boundary'
                elif candidates[0] == original:
                    comparison = 'agrees'
                else:
                    comparison = 'disagrees'
                if judge.get('status') != 'validated' or result.get('eligibility') != 'eligible':
                    published_comparison = 'requires_review'
                elif published not in candidates:
                    published_comparison = 'outside_candidates'
                elif len(candidates) > 1:
                    published_comparison = 'boundary_includes'
                else:
                    published_comparison = 'agrees'
                acceptance = evidence.get('difficulty_acceptance') or {}
                rows.append({
                    'case_id': f'{directory.name}_{stem}_{question["slot_id"]}',
                    'job_id': bundle['job']['id'], 'content_id': content['id'],
                    'source_directory': str(directory), 'asset_sha256': shadow['asset_sha256'],
                    'learner_profile': profile, 'student_visible_text': case['student_visible_text'],
                    'reference_answer': accepted_question.get('answer', ''),
                    'reference_explanation': accepted_question.get('explanation', ''),
                    'cited_sources': [sources[source_id] for source_id in accepted_question.get('citation_ids', [])
                                      if source_id in sources],
                    'original_difficulty': original, 'published_difficulty': published,
                    'target_difficulty': question.get('target_difficulty'),
                    'acceptance_status': acceptance.get('status'),
                    'strict_passed': acceptance.get('strict_passed'),
                    'judge_status': judge.get('status'), 'eligibility': result.get('eligibility'),
                    'candidates': candidates, 'comparison': comparison,
                    'published_comparison': published_comparison,
                    'judge_reason': result.get('decision', {}).get('reason'),
                    'audit_status': audit.get('result', {}).get('status', audit.get('status')),
                    'audit_findings': audit.get('result', {}).get('findings', []),
                    'shadow_duration_ms': shadow.get('duration_ms'),
                })
    if len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate case IDs')
    return rows


def write_packet(rows, output):
    output.mkdir(parents=True, exist_ok=False)
    blind = ['# 独立难度评审材料', '',
             '请先独立填写 teacher_review_template.csv，再看 comparison.md。此处仅含学生背景与学生可见内容；不含原判级、旁路判级、参考答案。',
             '难度相对于所给学生背景判断；题目条件不足可标 invalid_question，学生背景不足可标 insufficient_profile，边界无法判定可标 uncertain。', '']
    for row in rows:
        blind += [f'## {row["case_id"]}', '', '**学生背景**', '', row['learner_profile'], '',
                  '**学生可见内容**', '', row['student_visible_text'], '']
    (output / 'blind_packet.md').write_text('\n'.join(blind))
    with (output / 'teacher_review_template.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['case_id', 'eligibility', 'cognitive_demand', 'difficulty',
                         'remaining_independent_work', 'easy_medium_boundary',
                         'medium_hard_boundary', 'uncertainty_or_issue', 'reviewer'])
        for row in rows:
            writer.writerow([row['case_id']] + [''] * 8)
    answer_lines = ['# 独立答案与来源复核材料', '',
                    '先完成 teacher_review_template.csv 中的难度判断，再打开本页。'
                    '先核对题目条件、参考答案和来源，再查看 comparison.md 中的模型判级。', '']
    for row in rows:
        answer_lines += [f'## {row["case_id"]}', '', '**学生可见内容**', '',
                         row['student_visible_text'], '', '**参考答案**', '',
                         row['reference_answer'], '', '**答案解释**', '',
                         row['reference_explanation'], '', '**题目引用的来源**', '']
        for source in row['cited_sources']:
            answer_lines += [f'### {source.get("document_name", "来源")} · {source["id"]}', '',
                             source.get('text', ''), '']
        if not row['cited_sources']:
            answer_lines += ['未在保存的内容中找到可展示的题目引用来源；需人工核查。', '']
    (output / 'answer_review_packet.md').write_text('\n'.join(answer_lines))
    with (output / 'teacher_answer_review_template.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['case_id', 'question_validity', 'answer_correctness',
                         'citation_support', 'issue_or_correction', 'reviewer'])
        for row in rows:
            writer.writerow([row['case_id']] + [''] * 5)
    lines = ['# 旁路分歧复核', '',
             '此表应在独立评审完成后查看。草稿保留等级是题目资产中的设计目标，审核页另列模型判断，学生导出不显示内部难度标签。模型判断仅是待核查线索；“一致”不等于准确，语义复核无发现不等于答案正确。', '',
             '| 样本 | 原判 | 草稿保留的目标 | 旁路候选 | 原判对比 | 目标对比 | 语义复核 | 耗时 |',
             '|---|---|---|---|---|---|---|---:|']
    for row in rows:
        candidates = '/'.join(row['candidates']) or '无有效判级'
        lines.append(f'| {row["case_id"]} | {row["original_difficulty"]} | {row["published_difficulty"]} | {candidates} | {row["comparison"]} | {row["published_comparison"]} | {row["audit_status"]} | {row["shadow_duration_ms"]} ms |')
    lines += ['', '## 分歧依据', '']
    for row in rows:
        if row['comparison'] == 'agrees' and row['published_comparison'] == 'agrees' and not row['audit_findings']:
            continue
        lines += [f'### {row["case_id"]}', '',
                  f'- 原判：{row["original_difficulty"]}；请求目标：{row["target_difficulty"]}；草稿保留的目标：{row["published_difficulty"]}；旧门槛：{row["acceptance_status"]}／strict_passed={row["strict_passed"]}；旁路候选：{row["candidates"]}。',
                  f'- 旁路依据：{row["judge_reason"] or "无有效判断"}',
                  f'- 语义复核：{json.dumps(row["audit_findings"], ensure_ascii=False)}', '']
    (output / 'comparison.md').write_text('\n'.join(lines))
    (output / 'records.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = collect(args.directories)
    if not rows:
        raise SystemExit('No completed shadow observations found')
    print(write_packet(rows, args.output))
