"""Validate frozen raw v4 responses after reference-capacity fix. No API calls."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts import difficulty_judge_v4 as fixed
from scripts.difficulty_experiment import write_json
from scripts.difficulty_judge_comparison import summarize,report
from scripts.difficulty_judge_report import consolidate


def replay(parent):
    source_manifest=json.loads((parent/'manifest.json').read_text())
    if source_manifest['status']!='complete' or source_manifest['arms']!=['v3','v4']:
        raise ValueError('Requires completed v3-v4 pilot')
    frozen=parent/'code/scripts/difficulty_judge_v4.py'
    expected=source_manifest['code_sha256']['scripts/difficulty_judge_v4.py']
    if hashlib.sha256(frozen.read_bytes()).hexdigest()!=expected:raise ValueError('Frozen validator hash mismatch')
    spec=importlib.util.spec_from_file_location('frozen_v4_capacity',frozen)
    original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
    original_schema=original.CompactJudgement.model_json_schema()
    revised_schema=fixed.CompactJudgement.model_json_schema()
    comparison=deepcopy(original_schema)
    # A post-hoc capacity-only replay must not relax any other rule.
    for key in ('request_ids','condition_ids','solution_ids'):
        comparison['$defs']['TaskAudit']['properties'][key]['maxItems']=fixed.MAX_REFERENCES
    if comparison!=revised_schema:raise ValueError('Not a capacity-only schema change')
    dataset=json.loads((parent/'dataset.json').read_text());cases={c['id']:c for c in dataset['cases']}
    rows=json.loads((parent/'records.json').read_text())
    output=parent/'CAPACITY_REPLAY';output.mkdir(exist_ok=False)
    recovered=[];hashes={}
    for row in rows:
        if row['arm']!='v4':continue
        source=parent/'items'/row['id']/'response.json'
        hashes[row['id']]=hashlib.sha256(source.read_bytes()).hexdigest()
        raw=json.loads(source.read_text())
        try:original.validate(raw,cases[row['case_id']]);old_valid=True
        except Exception:old_valid=False
        if old_valid != (row['status']=='valid'):raise ValueError('Cannot reproduce original validity')
        try:
            parsed=fixed.validate(raw,cases[row['case_id']])
            if old_valid and parsed!=row['result']:raise ValueError('Existing valid judgement changed')
            if not old_valid:recovered.append(row['id'])
            row.update(status='valid',label=parsed['estimated_difficulty'],eligibility=parsed['eligibility'],result=parsed)
            row.pop('error',None)
        except Exception as exc:
            if old_valid:raise
            row.update(status='failed',error={'type':type(exc).__name__})
    manifest={**source_manifest,'revision':fixed.REVISION,'live':False,'kind':'post_hoc_validation_replay',
        'parent_run':str(parent.resolve()),'additional_api_calls':0,'actual_calls':0,'total_tokens':0,'calls_without_cost':0,'reported_cost_usd':0,
        'raw_response_sha256':hashes,'recovered_records':recovered,'original_live_calls':source_manifest['actual_calls'],
        'limitation':'Offline acceptance of unchanged raw replies; not a fresh live test of the revised schema or accuracy.'}
    manifest.pop('code_sha256',None)
    paths=['scripts/difficulty_judge_v4.py','scripts/difficulty_capacity_replay.py','tests/test_difficulty_judge_v4.py']
    manifest['code_sha256']={}
    for rel in paths:
        dest=output/'code'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
        manifest['code_sha256'][rel]=hashlib.sha256(dest.read_bytes()).hexdigest()
    write_json(output/'manifest.json',manifest);write_json(output/'records.json',rows);write_json(output/'dataset.json',dataset)
    summary=summarize(rows,dataset,source_manifest['repeats'],('v3','v4'))
    write_json(output/'summary.json',summary)
    body='# 容量修正后的离线原始响应回放\n\n没有新增 API 调用。下方 v4 指 v4.1 校验器对原始 v4 回复的回放；v3 沿用父试验记录。不是一轮新的在线实验。仅引用数量上限由 5/6 提高到 64，等级、原文编号及理由没有编辑。\n\n'
    (output/'REPORT.md').write_text(body+report(summary,manifest))
    consolidate(output)
    return {'output':str(output),'recovered':recovered,'additional_calls':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('parent',type=Path)
    print(json.dumps(replay(p.parse_args().parent),ensure_ascii=False))
