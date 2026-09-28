"""Read-only paired comparison of completed verification-only protocol runs.

The protocol is the intended difference. Frozen cases, blind-analysis raw
outputs, provider controls and other snapshotted execution code must match.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.difficulty_review_v2_compare import _meter, _verifier
from scripts.difficulty_review_v2_verify_eval import (
    collect_sources, digest, file_hash, input_case, load_protocol)

TERMINAL_RUNS = {'complete', 'completed_with_failures'}
TERMINAL_ROWS = {'complete', 'failed', 'not_attempted'}
CONTENT_CHECKS = ('conditions_complete', 'reference_correct', 'explanation_consistent', 'source_support')


def _path(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe frozen artifact path')
    resolved = (root / path).resolve()
    if root not in resolved.parents:
        raise ValueError('Frozen artifact escapes its run directory')
    return resolved


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError(f'Missing or invalid frozen artifact: {path.name}') from None


def _hashes(root, mapping, prefix=''):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('Missing frozen artifact hash map')
    for name, expected in mapping.items():
        try:
            actual = file_hash(_path(root, prefix + name).read_bytes())
        except OSError:
            raise ValueError('Missing hashed artifact') from None
        if actual != expected:
            raise ValueError('Frozen artifact byte hash mismatch')


def _numeric(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _load(directory):
    root = Path(directory).resolve()
    manifest = _read(root / 'manifest.json')
    # Never inspect models' partial answers from an active experiment.
    if not isinstance(manifest, dict) or manifest.get('status') not in TERMINAL_RUNS:
        raise ValueError('Verification run is not terminal')
    if manifest.get('kind') != 'difficulty-review-verification-only':
        raise ValueError('Expected a verification-only run')
    _hashes(root, manifest.get('code_sha256'), 'code/')
    artifacts = manifest.get('source_artifact_sha256')
    _hashes(root, artifacts)
    actual_source_files = {str(path.relative_to(root)) for path in (root / 'source_evidence').rglob('*') if path.is_file()}
    if actual_source_files != set(artifacts):
        raise ValueError('Source artifact manifest is incomplete')
    reviewer = load_protocol(_path(root, 'code/app/difficulty_review_v2.py'), root / 'code/app')
    if reviewer.protocol_fingerprint() != manifest.get('protocol_sha256') or reviewer.REVISION != manifest.get('protocol_revision'):
        raise ValueError('Saved protocol does not match manifest')
    controls = _verifier(manifest)
    dataset = _read(root / 'dataset.json')
    cases = dataset.get('cases') if isinstance(dataset, dict) else None
    if not isinstance(cases, list) or not cases or digest(cases) != manifest.get('dataset_sha256'):
        raise ValueError('Frozen dataset hash mismatch')
    by_case = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('case_key'), str) or case['case_key'] in by_case:
            raise ValueError('Invalid or duplicate frozen case key')
        by_case[case['case_key']] = case
    selected = manifest.get('selected_case_keys')
    if not isinstance(selected, list) or len(set(selected)) != len(selected) or set(selected) != set(by_case):
        raise ValueError('Dataset differs from submitted case keys')
    sources = sorted({root / 'source_evidence' / Path(name).parts[1] for name in artifacts
                      if len(Path(name).parts) > 2 and Path(name).parts[0] == 'source_evidence'})
    source_items, _, _ = collect_sources(sources, selected)
    originals = {item['case_key']: item for item in source_items}
    records = _read(root / 'records.json')
    calls = _read(root / 'calls.json')
    if not isinstance(records, list) or len(records) != len(selected):
        raise ValueError('Submitted rows were removed or duplicated')
    if (not isinstance(calls, list) or manifest.get('actual_calls') != len(calls)
            or type(manifest.get('call_cap')) is not int or not 1 <= manifest['call_cap'] <= 24
            or len(calls) > manifest['call_cap'] or manifest.get('planned_calls') != len(records)
            or len(records) > manifest['call_cap'] or manifest.get('analysis_calls') != 0):
        raise ValueError('Call ledger or planned budget mismatch')
    call_map = {}
    for call in calls:
        if (not isinstance(call, dict) or not isinstance(call.get('id'), str) or not call['id']
                or call['id'] in call_map or call.get('capability') != 'text'
                or call.get('model') != controls['verifier_model']):
            raise ValueError('Invalid verification ledger entry')
        call_map[call['id']] = call
    rows = {}; item_ids = set(); attributed = set(); pairing = []
    for row in records:
        if not isinstance(row, dict) or row.get('status') not in TERMINAL_ROWS:
            raise ValueError('Nonterminal verification record')
        key = row.get('case_key'); item_id = row.get('item_id')
        if key not in originals or key in rows or not isinstance(item_id, str) or '/' in item_id or item_id in ('','.', '..') or item_id in item_ids:
            raise ValueError('Invalid, foreign or duplicate row identity')
        item_ids.add(item_id)
        original = originals[key]; case = by_case[key]
        if {name: value for name, value in case.items() if name != 'case_key'} != original['case']:
            raise ValueError('Selected case differs from frozen source')
        if row.get('case_id') != original['case_id'] or row.get('repeat') != original['repeat']:
            raise ValueError('Row belongs to another source case/repeat')
        clean = input_case(case); input_hash = digest(clean)
        if row.get('input_sha256') != input_hash:
            raise ValueError('Record input hash mismatch')
        reuse = row.get('reuse', {})
        # Collection under source_evidence changes its directory, not its provenance.
        if {k:v for k,v in reuse.items() if k != 'source_directory'} != {
                k:v for k,v in original['reuse'].items() if k != 'source_directory'}:
            raise ValueError('Raw-analysis reuse provenance mismatch')
        item_dir = f'items/{item_id}/'
        raw = _read(_path(root, item_dir + 'analysis_response.json'))
        if raw != original['raw'] or digest(raw) != reuse.get('analysis_raw_sha256'):
            raise ValueError('Frozen reused analysis raw changed')
        pairing.append({'case_key':key,'input_sha256':input_hash,'analysis_raw_sha256':digest(raw)})
        analysis = row.get('analysis', {}); verification = row.get('verification', {})
        if analysis.get('status') == 'validated':
            if analysis.get('origin') != 'reused_raw_revalidated' or analysis.get('call_ids') != []:
                raise ValueError('Unexpected billable/regenerated analysis')
            normalized = _read(_path(root, item_dir + 'analysis_normalized.json'))
            if normalized != analysis.get('result') or reviewer.validate_analysis(deepcopy(raw), deepcopy(clean)) != normalized:
                raise ValueError('Reused analysis normalization mismatch')
        if verification.get('status') in ('pending','preparing','running','in_flight'):
            raise ValueError('Verification stage is still active')
        ids = verification.get('call_ids', [])
        if (not isinstance(ids, list) or len(ids) > 1 or any(identity not in call_map for identity in ids)
                or attributed.intersection(ids) or any(call_map[identity].get('job_id') != item_id for identity in ids)):
            raise ValueError('Call attribution is missing, duplicate or belongs to another row')
        attributed.update(ids)
        prompt_hash = verification.get('prompt_sha256')
        if prompt_hash is not None:
            if analysis.get('status') != 'validated':
                raise ValueError('Verification prompt has no validated frozen analysis')
            prompts = _read(_path(root, item_dir + 'verification_prompt.json'))
            if (digest(prompts) != prompt_hash
                    or reviewer.verification_messages(clean, analysis['result']) != prompts
                    or len(json.dumps(prompts, ensure_ascii=False).encode()) != verification.get('prompt_bytes')):
                raise ValueError('Frozen verification prompt mismatch')
        if ids and prompt_hash is None:
            raise ValueError('Paid verification lacks its prompt binding')
        if verification.get('status') == 'validated':
            if len(ids) != 1 or call_map[ids[0]].get('status') != 'succeeded':
                raise ValueError('Validated verification lacks a succeeded call')
            response = _read(_path(root, item_dir + 'verification_response.json'))
            normalized = _read(_path(root, item_dir + 'verification_normalized.json'))
            if (normalized != verification.get('result')
                    or reviewer.validate_verification(response, clean, analysis['result']) != normalized):
                raise ValueError('Verification normalization or evidence binding mismatch')
        if row['status'] == 'complete' and any(row.get(stage,{}).get('status') != 'validated' for stage in ('analysis','verification')):
            raise ValueError('Completed row lacks both validated stages')
        if row['status'] == 'not_attempted' and (ids or analysis or verification):
            raise ValueError('Unattempted row contains stage work')
        decision = reviewer.decide(analysis, verification, case.get('target_difficulty')) if row['status'] != 'not_attempted' else reviewer.decide({}, {}, None)
        if row.get('decision') != decision:
            raise ValueError('Saved decision does not match frozen protocol')
        if row['status'] != 'not_attempted' and _read(_path(root, item_dir+'decision.json')) != decision:
            raise ValueError('Decision artifact mismatch')
        rows[key] = row
    if set(rows) != set(selected) or manifest.get('pairing') != sorted(pairing, key=lambda row:row['case_key']):
        raise ValueError('Pairing set or raw/case hashes differ')
    if manifest.get('paired_input_sha256') != digest(manifest['pairing']):
        raise ValueError('Paired input digest mismatch')
    if _read(root / 'manifest.json') != manifest:
        raise ValueError('Manifest changed during comparison')
    return {'root':str(root),'manifest':manifest,'controls':controls,'rows':rows,'cases':by_case,
            'calls':call_map,'unattributed_call_ids':sorted(set(call_map)-attributed)}


def _latencies(values):
    valid = [value for value in values if _numeric(value)]
    return {'known_count':len(valid),'missing_count':len(values)-len(valid),
            'sum_ms':sum(valid),'median_ms':statistics.median(valid) if valid else None,
            'max_ms':max(valid) if valid else None}


def _side(run, row):
    verification = row.get('verification', {})
    checks = verification.get('result', {}).get('checks', {}) if verification.get('status') == 'validated' else {}
    calls = [run['calls'][identity] for identity in verification.get('call_ids', [])]
    return {'record_status':row['status'],'verification_status':verification.get('status','not_attempted'),
        'checks':deepcopy(checks),'decision':deepcopy(row['decision']),
        'error_type':verification.get('error_type'),'error_code':verification.get('error_code'),
        'validation_issues':deepcopy(verification.get('validation_issues',[])),
        'duration_ms':row.get('duration_ms'),'provider_latency':_latencies([call.get('duration_ms') for call in calls]),
        'metering':_meter(calls)}


def compare_runs(baseline, candidate):
    left, right = _load(baseline), _load(candidate)
    for field in ('paired_input_sha256','pairing','dataset_sha256','max_prompt_bytes'):
        if left['manifest'].get(field) != right['manifest'].get(field):
            raise ValueError(f'Unpaired verification runs: {field} differs')
    if left['controls'] != right['controls']:
        raise ValueError('Verifier model, parameters, timeout or endpoint differs')
    dependencies = lambda run:{key:value for key,value in run['manifest']['code_sha256'].items()
                              if key != 'app/difficulty_review_v2.py'}
    if dependencies(left) != dependencies(right):
        raise ValueError('Non-protocol execution dependencies differ')
    if set(left['rows']) != set(right['rows']):
        raise ValueError('Paired row sets differ')
    check_names = sorted({name for run in (left,right) for row in run['rows'].values()
                         for name in row.get('verification',{}).get('result',{}).get('checks',{})})
    pairs = []
    for key in sorted(left['rows']):
        a,b = _side(left,left['rows'][key]),_side(right,right['rows'][key])
        changes = {name:{'baseline':a['checks'].get(name,{}).get('status','not_verified'),
                         'candidate':b['checks'].get(name,{}).get('status','not_verified')}
                   for name in check_names if a['checks'].get(name,{}).get('status','not_verified') != b['checks'].get(name,{}).get('status','not_verified')}
        pairs.append({'case_key':key,'input_sha256':left['rows'][key]['input_sha256'],
            'analysis_raw_sha256':left['rows'][key]['reuse']['analysis_raw_sha256'],
            'baseline':a,'candidate':b,'check_changes':changes,
            'final_changed':a['decision'] != b['decision']})
    summaries = {}
    for label,run in (('baseline',left),('candidate',right)):
        sides = [pair[label] for pair in pairs]
        complete = sum(side['record_status']=='complete' for side in sides)
        verified = sum(side['verification_status']=='validated' for side in sides)
        summaries[label] = {'submitted':len(pairs),'complete':complete,'completion_rate':complete/len(pairs),
            'verification_validated':verified,'verification_validated_rate':verified/len(pairs),
            'record_status_counts':dict(Counter(side['record_status'] for side in sides)),
            'decision_status_counts':dict(Counter(side['decision']['status'] for side in sides)),
            'check_status_counts':{name:dict(Counter(side['checks'].get(name,{}).get('status','not_verified') for side in sides)) for name in check_names},
            'row_latency':_latencies([side['duration_ms'] for side in sides]),
            'provider_latency':_latencies([call.get('duration_ms') for call in run['calls'].values()]),
            'metering':_meter(list(run['calls'].values())), 'unattributed_call_ids':run['unattributed_call_ids']}
    return {'kind':'verification-only-protocol-comparison','paired':True,
        'comparison_scope':'same_frozen_analysis_and_case; protocol is an intentional difference',
        'baseline_run':left['root'],'candidate_run':right['root'],
        'protocols':{label:{'revision':run['manifest']['protocol_revision'],'protocol_sha256':run['manifest']['protocol_sha256'],
                    'source_sha256':run['manifest']['code_sha256']['app/difficulty_review_v2.py']}
                    for label,run in (('baseline',left),('candidate',right))},
        'controls':{'paired_input_sha256':left['manifest']['paired_input_sha256'],'verifier':left['controls'],
                    'dataset_sha256':left['manifest']['dataset_sha256']},
        'teacher_accuracy':None,'independent_solution_accuracy':None,'production_ready':False,
        'statistical_significance':'not_estimated','end_to_end_speedup':'not_measured_analysis_was_reused',
        'summaries':summaries,'pairs':pairs}


def markdown_report(report):
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    lines=['# 固定解答的核验协议配对比较','','复用同一题目与同一份盲解题原始输出；模型、参数与服务配置相同，协议是有意变化。',
           '失败和未尝试行保留在分母中。本结果不测量教师准确率，也不代表完整流程提速。','',
           '| 协议 | 完成 | 完成率 | API 调用 | 已知 token 合计 | token 缺项 | 费用缺项 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for label in ('baseline','candidate'):
        summary=report['summaries'][label];meter=summary['metering']
        values=(label,f"{summary['complete']}/{summary['submitted']}",f"{summary['completion_rate']:.1%}",meter['call_count'],
            meter['usage']['total_tokens']['known_sum'],meter['calls_missing_usage']['total_tokens'],meter['calls_missing_usage']['cost'])
        lines.append('| '+' | '.join(cell(value) for value in values)+' |')
    lines += ['','| 样本 | 基线状态 | 新协议状态 | 检查变化 |','|---|---|---|---|']
    for pair in report['pairs']:
        changes='; '.join(f"{name}: {value['baseline']} → {value['candidate']}" for name,value in pair['check_changes'].items()) or '无'
        lines.append('| '+' | '.join(cell(value) for value in (pair['case_key'],pair['baseline']['decision']['status'],pair['candidate']['decision']['status'],changes))+' |')
    lines += ['','完整检查分布、逐行原因、时延和调用归属见 JSON。未知费用未按零计费；未归属调用仍计入总用量。','']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--markdown',type=Path,required=True)
    args=parser.parse_args(argv)
    outputs=[args.output.resolve(),args.markdown.resolve()];roots=[args.baseline.resolve(),args.candidate.resolve()]
    if len(set(outputs))!=2 or any(path.exists() for path in outputs):
        raise ValueError('Comparison outputs must be new distinct files')
    if any(path==root or root in path.parents for path in outputs for root in roots):
        raise ValueError('Comparison cannot write inside frozen runs')
    report=compare_runs(args.baseline,args.candidate)
    for path,text in ((outputs[0],json.dumps(report,ensure_ascii=False,indent=2)+'\n'),(outputs[1],markdown_report(report))):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as handle:handle.write(text)
    print(json.dumps({'paired':True,'submitted':len(report['pairs']),
                      'baseline_completion':report['summaries']['baseline']['completion_rate'],
                      'candidate_completion':report['summaries']['candidate']['completion_rate']}))
    return report


if __name__=='__main__':main()
