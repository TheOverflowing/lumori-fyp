"""Bounded real content-consistency audit of saved, hash-checked shadow questions."""
import argparse
import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.content_consistency_audit import REVISION, messages, validate
from app.difficulty_shadow import digest, visible_case
from app.providers import ApiProviders
from scripts.difficulty_experiment import CappedStore, call_rows, safe_error, write_json


def collect(directories):
    cases = []
    for directory in directories:
        for path in sorted(directory.glob('task_*_evidence.json')):
            content_path = directory / path.name.replace('_evidence.json', '_content.json')
            if not content_path.exists():
                continue
            bundle = json.loads(path.read_text())
            content = json.loads(content_path.read_text())
            asset = content['asset']
            observation = bundle['evidence'].get('difficulty_shadow', {})
            if digest(asset) != observation.get('asset_sha256') or content['version'] != 1:
                raise ValueError('Saved content differs from the observed asset')
            profile = bundle['evidence']['request']['learner_profile']
            for index, question in enumerate(asset['questions']):
                visible = visible_case(asset, index, profile)
                saved = next((q for q in observation['questions'] if q['slot_id'] == question['slot_id']), None)
                if not saved or digest(visible) != saved['visible_input_sha256']:
                    raise ValueError('Student-visible material differs from the observed input')
                cases.append({'id': f'{directory.name}_{path.stem}_{question["slot_id"]}',
                              **visible, 'reference_answer': question['answer'],
                              'reference_explanation': question['explanation'],
                              'source_run': str(directory), 'asset_sha256': digest(asset)})
    if len({item['id'] for item in cases}) != len(cases):
        raise ValueError('Duplicate saved case IDs')
    return cases


async def run(args):
    cases = collect(args.runs)
    if not 1 <= len(cases) <= args.max_calls <= 4:
        raise ValueError('This audit requires 1-4 saved questions and one call each')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for rel in ('app/content_consistency_audit.py',
                'scripts/difficulty_content_consistency_saved.py',
                'tests/test_content_consistency_audit.py'):
        source = ROOT / rel
        target = output / 'code' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {'kind': 'saved_content_consistency_audit', 'revision': REVISION,
                'live': args.live, 'status': 'prepared', 'planned_calls': len(cases),
                'call_cap': args.max_calls, 'code_sha256': hashes,
                'thinking_effort': args.thinking_effort,
                'audit_max_tokens': args.audit_max_tokens,
                'cases': [{'id': item['id'], 'input_sha256': digest(item)} for item in cases],
                'human_accuracy': None}
    write_json(output / 'cases.json', cases)
    write_json(output / 'manifest.json', manifest)
    if not args.live:
        print(json.dumps({'status': 'prepared', 'planned_calls': len(cases)}), flush=True)
        return
    base = Settings.from_env()
    max_tokens = args.audit_max_tokens or (6000 if args.thinking_effort == 'high' else 3000)
    parameters = ({'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high', 'max_tokens': max_tokens}
                  if args.thinking_effort == 'high' else
                  {'thinking': {'type': 'disabled'}, 'temperature': 0, 'max_tokens': max_tokens})
    settings = replace(base, timeout=120, text_json_mode=True,
                       text=replace(base.text, extra=parameters))
    settings.text.require('text')
    store = CappedStore(Path(tempfile.mkdtemp(prefix='lumori-content-consistency-')), args.max_calls)
    provider = ApiProviders(settings, store)
    records = []
    manifest.update(status='running', text_model=settings.text.model, request_parameters=parameters)
    write_json(output / 'manifest.json', manifest)
    try:
        for case in cases:
            row = {'id': case['id'], 'input_sha256': digest(case), 'status': 'pending'}
            try:
                raw = await provider.generate(messages(case), case['id'])
                write_json(output / 'responses' / f'{case["id"]}.json', raw)
                row.update(status='validated', result=validate(raw, case))
            except Exception as exc:
                row.update(status='failed', error=safe_error(exc))
            records.append(row)
            write_json(output / 'records.json', records)
            print(case['id'], row['status'], row.get('result', {}).get('status'), flush=True)
        manifest['status'] = ('complete' if all(row['status'] == 'validated' for row in records)
                              else 'completed_with_failures')
    finally:
        await provider.close()
        calls = call_rows(store)
        write_json(output / 'calls.json', calls)
        manifest.update(actual_calls=len(calls), total_tokens=sum(c['usage'].get('total_tokens', 0) for c in calls),
                        calls_without_cost=sum('cost' not in c['usage'] for c in calls))
        write_json(output / 'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-calls', type=int, default=4)
    parser.add_argument('--thinking-effort', choices=('off', 'high'), default='off')
    parser.add_argument('--audit-max-tokens', type=int)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.audit_max_tokens is not None and not 1000 <= args.audit_max_tokens <= 16000:
        parser.error('Audit max tokens must be 1000-16000')
    asyncio.run(run(args))
