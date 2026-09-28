"""Verify frozen blind analyses under one explicitly chosen review protocol.

Run the same selected source rows twice, once per protocol, to compare the
verification stage without regenerating a solution. Dry by default. Labels and
targets stay local; failures and rows stopped before a call retain their slots.
"""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import types
import uuid
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.providers import ApiProviders, ProviderError, ProviderOutputError
from scripts.difficulty_experiment import CappedStore, call_rows, write_json
from scripts.difficulty_review_v2_compare import _load_run, _meter
from scripts.difficulty_review_v2_eval import digest, input_case, stage_parameters, MAX_PROMPT_BYTES

REVISION = 'verification-only-paired-v1'
SNAPSHOT_FILES = ('app/difficulty_judge.py', 'app/providers.py', 'app/config.py',
    'app/store.py', 'app/task_control.py', 'scripts/difficulty_experiment.py',
    'scripts/difficulty_review_v2_eval.py', 'scripts/difficulty_review_v2_compare.py',
    'scripts/difficulty_review_v2_verify_eval.py')
CONTENT_CHECKS = ('conditions_complete', 'reference_correct', 'explanation_consistent', 'source_support')


def file_hash(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    try:
        raw = path.read_bytes()
        return json.loads(raw), raw
    except (OSError, ValueError):
        raise ValueError(f'Missing or invalid frozen artifact: {path.name}') from None


def load_protocol(path, dependency_directory):
    """Use an isolated app subpackage so relative imports bind to frozen code."""
    path = Path(path).resolve()
    dependency_directory = Path(dependency_directory).resolve()
    if not path.is_file() or not (dependency_directory / 'difficulty_judge.py').is_file():
        raise ValueError('Protocol source and frozen catalogue dependency are required')
    package_name = 'app._verify_snapshot_' + uuid.uuid4().hex
    package = types.ModuleType(package_name)
    package.__path__ = [str(dependency_directory)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(package_name + '.protocol', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for name in ('REVISION', 'Analysis', 'protocol_fingerprint', 'analysis_messages',
                 'validate_analysis', 'verification_messages', 'validate_verification', 'decide'):
        if not hasattr(module, name):
            raise ValueError('Selected protocol lacks a required interface')
    return module


def _safe_identity(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value))


def collect_sources(directories, case_keys=None):
    roots = [Path(path).resolve() for path in directories]
    if not roots or len(set(roots)) != len(roots) or len({root.name for root in roots}) != len(roots):
        raise ValueError('Source directories must be nonempty, distinct and have unique basenames')
    if case_keys and len(set(case_keys)) != len(case_keys):
        raise ValueError('Duplicate selected case key')
    available = {}
    archives = {}
    skipped = []
    for root in roots:
        if not _safe_identity(root.name):
            raise ValueError('Unsafe source run basename')
        frozen = _load_run(root)
        manifest = frozen['manifest']
        if frozen['unattributed_call_ids']:
            raise ValueError('Source ledger has unattributed calls')
        code_hashes = manifest.get('code_sha256')
        if not isinstance(code_hashes, dict) or not {'app/difficulty_review_v2.py', 'app/difficulty_judge.py'} <= set(code_hashes):
            raise ValueError('Missing original protocol/dependency hashes')
        blobs = {}
        for relative, expected in code_hashes.items():
            relative_path = Path(relative)
            if relative_path.is_absolute() or '..' in relative_path.parts:
                raise ValueError('Unsafe frozen code path')
            path = root / 'code' / relative_path
            try:
                raw = path.read_bytes()
            except OSError:
                raise ValueError('Missing frozen code file') from None
            if file_hash(raw) != expected:
                raise ValueError('Frozen source code hash mismatch')
            blobs['code/' + relative] = raw
        original = load_protocol(root / 'code/app/difficulty_review_v2.py', root / 'code/app')
        if original.protocol_fingerprint() != manifest['protocol_sha256']:
            raise ValueError('Original protocol fingerprint differs from manifest')
        for name in ('manifest.json', 'dataset.json', 'records.json', 'calls.json'):
            _, raw = read_json(root / name)
            blobs[name] = raw
        for (case_id, repeat), saved in frozen['entries'].items():
            if not _safe_identity(case_id):
                raise ValueError('Unsafe source case ID')
            key = f'{root.name}:{case_id}:{repeat}'
            row = saved['row']
            analysis = row.get('analysis', {})
            if analysis.get('status') != 'validated':
                skipped.append(key)
                continue
            case = frozen['cases'][case_id]
            clean = input_case(case)
            item = f'{case_id}_{repeat}'
            raw, raw_bytes = read_json(root / 'items' / item / 'analysis_response.json')
            prompt, prompt_bytes = read_json(root / 'items' / item / 'analysis_prompt.json')
            if digest(prompt) != analysis.get('prompt_sha256') or original.analysis_messages(clean) != prompt:
                raise ValueError('Original analysis prompt does not match its input or record')
            result = analysis.get('result')
            if not isinstance(result, dict) or not isinstance(raw, dict):
                raise ValueError('Validated analysis has no structured raw/result')
            try:
                normalized = original.validate_analysis(deepcopy(raw), deepcopy(clean))
            except Exception:
                raise ValueError('Original analysis raw does not validate') from None
            # The original validator may strip strings or order candidates.
            # Reuse raw bytes unchanged, comparing its complete original
            # normalization (including bindings) to the saved result instead.
            if normalized != result:
                raise ValueError('Original analysis normalization or binding mismatch')
            ids = analysis.get('call_ids')
            if not isinstance(ids, list) or len(ids) != 1:
                raise ValueError('Validated analysis needs exactly one attributed call')
            call = frozen['calls'][ids[0]]
            if call.get('status') != 'succeeded' or call.get('capability') != 'text' or call.get('model') != manifest.get('model'):
                raise ValueError('Analysis ledger status or model does not match')
            blobs[f'items/{item}/analysis_response.json'] = raw_bytes
            blobs[f'items/{item}/analysis_prompt.json'] = prompt_bytes
            provenance = {'source_directory': str(root), 'source_run': root.name,
                'source_case_id': case_id, 'source_repeat': repeat,
                'source_record_sha256': digest(row), 'source_case_sha256': digest(case),
                'input_sha256': digest(clean), 'analysis_raw_sha256': digest(raw),
                'analysis_raw_file_sha256': file_hash(raw_bytes),
                'original_protocol_sha256': manifest['protocol_sha256'],
                'original_protocol_revision': original.REVISION,
                'original_analysis_model': call['model'], 'original_analysis_call_ids': ids,
                'original_analysis_parameters': manifest.get('analyst_parameters', manifest.get('parameters'))}
            available[key] = {'case_key': key, 'case_id': case_id, 'repeat': repeat,
                              'case': deepcopy(case), 'input': clean, 'raw': raw, 'reuse': provenance}
        archives[root.name] = blobs
        if read_json(root / 'manifest.json')[0] != manifest:
            raise ValueError('Source manifest changed during collection')
    selected = set(case_keys) if case_keys else set(available)
    if not selected or selected - set(available):
        raise ValueError('Unknown case key or selected analysis is not validated')
    return [available[key] for key in sorted(selected)], archives, skipped


def summarize(records, selected, calls):
    by_key = {item['case_key']: item for item in selected}
    content_false_clear, content_false_issue = [], []
    for row in records:
        if row.get('verification', {}).get('status') != 'validated':
            continue
        checks = row['verification']['result']['checks']
        states = [checks.get(name, {}).get('status') for name in CONTENT_CHECKS]
        expected = by_key[row['case_key']]['case'].get('expected', {}).get('content_status')
        if expected == 'fail' and states == ['pass'] * len(CONTENT_CHECKS):
            content_false_clear.append(row['case_key'])
        if expected == 'pass' and 'fail' in states:
            content_false_issue.append(row['case_key'])
    return {'submitted': len(records), 'verification_validated': sum(
        row.get('verification', {}).get('status') == 'validated' for row in records),
        'record_status_counts': dict(Counter(row['status'] for row in records)),
        'outcomes': dict(Counter(row.get('decision', {}).get('status', 'unavailable') for row in records)),
        'content_false_clears_against_saved_expectations': content_false_clear,
        'content_false_issues_against_saved_expectations': content_false_issue,
        'verifier_reported_solution_checks': dict(Counter(
            row.get('verification', {}).get('result', {}).get('checks', {}).get('solution_correct', {})
               .get('status', 'not_verified') if row.get('verification', {}).get('status') == 'validated'
            else 'not_verified' for row in records)),
        'metering': _meter(calls), 'human_accuracy': None, 'production_ready': False,
        'interpretation': 'Verification-only diagnostic; saved expectations are not independent teacher gold.'}


async def run(args):
    if type(args.max_calls) is not int or not 1 <= args.max_calls <= 24:
        raise ValueError('Verification call cap must be 1-24')
    if not isinstance(args.model, str) or not re.fullmatch(r'[A-Za-z0-9_:/@.+-]{1,160}', args.model):
        raise ValueError('Invalid verification model')
    parameters = stage_parameters(args.effort)
    selected, archives, excluded = collect_sources(args.source_dir, args.case_key)
    if len(selected) > args.max_calls:
        raise ValueError('Selected rows exceed the hard verification call cap')
    source_protocol = ROOT / 'app/difficulty_review_v2.py' if args.protocol_file == 'current' else Path(args.protocol_file).resolve()
    if not source_protocol.is_file():
        raise ValueError('Selected protocol file does not exist')
    output = args.output.resolve()
    if any(output == Path(root).resolve() or Path(root).resolve() in output.parents for root in args.source_dir):
        raise ValueError('Do not write inside a frozen source run')
    output.mkdir(parents=True, exist_ok=False)
    code_hashes = {}
    for name in SNAPSHOT_FILES:
        raw = (ROOT / name).read_bytes()
        target = output / 'code' / name
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        code_hashes[name] = file_hash(raw)
    protocol_bytes = source_protocol.read_bytes()
    (output / 'code/app/difficulty_review_v2.py').write_bytes(protocol_bytes)
    code_hashes['app/difficulty_review_v2.py'] = file_hash(protocol_bytes)
    reviewer = load_protocol(output / 'code/app/difficulty_review_v2.py', output / 'code/app')
    artifact_hashes = {}
    for run_name, blobs in archives.items():
        for relative, raw in blobs.items():
            path = output / 'source_evidence' / run_name / relative
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            artifact_hashes[str(path.relative_to(output))] = file_hash(raw)
    cases = [{**item['case'], 'case_key': item['case_key']} for item in selected]
    write_json(output / 'dataset.json', {'cases': cases})
    records = []
    for index, item in enumerate(selected):
        item_id = f'item_{index:03d}'
        write_json(output / 'items' / item_id / 'analysis_response.json', item['raw'])
        records.append({'case_key': item['case_key'], 'case_id': item['case_id'], 'repeat': item['repeat'],
            'item_id': item_id, 'status': 'pending', 'input_sha256': digest(item['input']),
            'reuse': item['reuse']})
    timeout = 45 if args.effort == 'none' else 120
    pairing = [{'case_key': item['case_key'], 'input_sha256': digest(item['input']),
                'analysis_raw_sha256': digest(item['raw'])} for item in selected]
    manifest = {'kind': 'difficulty-review-verification-only', 'revision': REVISION, 'live': args.live,
        'status': 'prepared', 'protocol_file': str(source_protocol), 'protocol_revision': reviewer.REVISION,
        'protocol_sha256': reviewer.protocol_fingerprint(), 'code_sha256': code_hashes,
        'source_artifact_sha256': artifact_hashes, 'dataset_sha256': digest(cases),
        'paired_input_sha256': digest(pairing), 'pairing': pairing,
        'selected_case_keys': [item['case_key'] for item in selected],
        'excluded_unvalidated_analysis_keys': excluded, 'planned_calls': len(records), 'call_cap': args.max_calls,
        'analysis_calls': 0, 'verifier_model': args.model, 'verifier_parameters': parameters,
        'verifier_timeout': timeout, 'max_prompt_bytes': MAX_PROMPT_BYTES,
        'comparison_scope': 'protocol changes intentionally; compare only identical pairing and verifier controls',
        'human_accuracy': None, 'production_ready': False}
    write_json(output / 'manifest.json', manifest); write_json(output / 'records.json', records)
    write_json(output / 'calls.json', [])
    if not args.live:
        write_json(output / 'summary.json', summarize(records, selected, []))
        print(json.dumps({'status': 'prepared', 'planned_calls': len(records),
                          'paired_input_sha256': manifest['paired_input_sha256']}), flush=True)
        return manifest
    base = Settings.from_env()
    settings = replace(base, text_json_mode=True, timeout=timeout,
                       text=replace(base.text, model=args.model, extra=parameters))
    store = CappedStore(Path(tempfile.mkdtemp(prefix='lumori-verify-only-')), args.max_calls)
    provider = ApiProviders(settings, store)
    manifest.update(status='running', verifier_endpoint_signature=settings.text.signature)
    write_json(output / 'manifest.json', manifest)
    try:
        settings.text.require('text')
        for row, item in zip(records, selected):
            started = time.monotonic(); row['status'] = 'running'
            record = row['verification'] = {'status': 'not_attempted', 'call_ids': []}
            write_json(output / 'records.json', records)
            try:
                analysis = reviewer.validate_analysis(deepcopy(item['raw']), deepcopy(item['input']))
                row['analysis'] = {'status': 'validated', 'origin': 'reused_raw_revalidated',
                                   'call_ids': [], 'result': analysis}
                write_json(output / 'items' / row['item_id'] / 'analysis_normalized.json', analysis)
                prompts = reviewer.verification_messages(item['input'], analysis)
                write_json(output / 'items' / row['item_id'] / 'verification_prompt.json', prompts)
                size = len(json.dumps(prompts, ensure_ascii=False).encode())
                record.update(prompt_bytes=size, prompt_sha256=digest(prompts))
                if size > MAX_PROMPT_BYTES:
                    raise ValueError('Verification prompt size limit exceeded')
                if store.one('SELECT count(*) AS n FROM calls')['n'] >= args.max_calls:
                    raise ValueError('Verification call budget exhausted')
                record['status'] = 'in_flight'; write_json(output / 'records.json', records)
                raw = await asyncio.wait_for(provider.generate(prompts, row['item_id']), timeout=timeout)
                write_json(output / 'items' / row['item_id'] / 'verification_response.json', raw)
                result = reviewer.validate_verification(raw, item['input'], analysis)
                write_json(output / 'items' / row['item_id'] / 'verification_normalized.json', result)
                record.update(status='validated', result=result)
                row['status'] = 'complete'
            except (asyncio.CancelledError, KeyboardInterrupt):
                record.update(status='interrupted_not_retried', error_type='Interrupted')
                row['status'] = 'failed'; manifest['stop_reason'] = 'interrupted'; raise
            except Exception as exc:
                record.update(status='failed', error_type=type(exc).__name__)
                if getattr(exc, 'code', None): record['error_code'] = exc.code
                if isinstance(exc, ValidationError):
                    record['validation_issues'] = [{'type': issue['type'], 'location': list(issue['loc'])}
                        for issue in exc.errors(include_input=False, include_context=False, include_url=False)]
                row['status'] = 'failed'
                if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or (
                        isinstance(exc, ProviderError) and not isinstance(exc, ProviderOutputError)):
                    manifest['stop_reason'] = getattr(exc, 'code', None) or type(exc).__name__
            finally:
                record['call_ids'] = [call['id'] for call in store.all('SELECT id FROM calls WHERE job_id=?', (row['item_id'],))]
                row['decision'] = reviewer.decide(row.get('analysis', {}), record, item['case'].get('target_difficulty'))
                row['duration_ms'] = round((time.monotonic() - started) * 1000)
                write_json(output / 'items' / row['item_id'] / 'decision.json', row['decision'])
                write_json(output / 'records.json', records)
            if manifest.get('stop_reason'): break
    except Exception as exc:
        manifest['stop_reason'] = type(exc).__name__
    finally:
        cleanup_error = None
        try:
            await provider.close()
        except BaseException as exc:
            cleanup_error = exc
            manifest['cleanup_error_type'] = type(exc).__name__
        for row in records:
            if row['status'] in ('pending', 'running'):
                row['status'] = 'not_attempted' if row['status'] == 'pending' else 'failed'
                row['decision'] = reviewer.decide({}, {}, None)
        calls = call_rows(store)
        write_json(output / 'records.json', records); write_json(output / 'calls.json', calls)
        metering = _meter(calls)
        manifest.update(status='complete' if all(row['status'] == 'complete' for row in records)
                        else 'completed_with_failures', actual_calls=len(calls), metering=metering,
                        calls_without_cost=metering['calls_missing_usage']['cost'],
                        calls_without_total_tokens=metering['calls_missing_usage']['total_tokens'])
        write_json(output / 'manifest.json', manifest)
        write_json(output / 'summary.json', summarize(records, selected, calls))
        if isinstance(cleanup_error, (asyncio.CancelledError, KeyboardInterrupt)):
            raise cleanup_error
    return manifest


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--source-dir', type=Path, action='append', required=True)
    result.add_argument('--case-key', action='append')
    result.add_argument('--protocol-file', default='current')
    result.add_argument('--max-calls', type=int, default=24)
    result.add_argument('--model', default='deepseek-v4-pro')
    result.add_argument('--effort', choices=('none', 'low', 'high', 'max'), default='low')
    result.add_argument('--output', type=Path, required=True)
    result.add_argument('--live', action='store_true')
    return result


if __name__ == '__main__':
    asyncio.run(run(parser().parse_args()))
