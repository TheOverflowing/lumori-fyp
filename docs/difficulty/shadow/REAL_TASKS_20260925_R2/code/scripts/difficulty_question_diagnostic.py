"""Post-hoc question-only diagnosis of a frozen D1 run; never replaces D1 scores.

Reuse existing blinded judgements and grade eligible questions excluded by the
whole-asset gate. No regeneration, prompt optimization, or production writes.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.models import Question
from app.providers import ApiProviders
from scripts.difficulty_experiment import (CappedStore, call_rows, digest, make_settings,
    public_parameters, safe_error, score, write_json)
from scripts.difficulty_prompts import build_judge_messages, JUDGE_VERSION


def prepare(parent):
    manifest = json.loads((parent / 'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['judge_version'] != JUDGE_VERSION:
        raise ValueError('A completed run with the unchanged judge is required')
    cases = {c['id']: c for c in json.loads((parent / 'selected-cases.json').read_text())}
    original = json.loads((parent / 'records.json').read_text())
    records = deepcopy(original)
    pending = []
    for row in records:
        row['whole_asset_valid'] = row['generation_status'] == 'valid'
        row['diagnostic_status'] = 'reused_primary_judgement' if row.get('judge') else 'ineligible'
        row.pop('qualified', None)
        if row.get('judge'):
            score(row, row['judge'])
            continue
        source = parent / 'items' / row['id'] / 'generation-response.json'
        if not source.exists():
            row['ineligible_reason'] = 'no_parsed_generation_response'
            continue
        raw = json.loads(source.read_text())
        if raw.get('evidence_sufficient') is not True or len(raw.get('questions', [])) != 1:
            row['ineligible_reason'] = 'insufficient_evidence_or_question_count'
            continue
        case = cases[row['case_id']]
        try:
            question = Question.model_validate(raw['questions'][0])
            if question.kind != case['question_type']:
                raise ValueError('Question type mismatch')
            if not set(question.citation_ids) <= {s['id'] for s in case['sources']}:
                raise ValueError('Unknown citation')
        except Exception as exc:
            row['ineligible_reason'] = safe_error(exc)
            continue
        row['diagnostic_status'] = 'pending'
        pending.append((row, build_judge_messages(case, raw)))
    # Verify the current judge builder exactly reproduces the original prompts.
    for row in original:
        if row.get('judge'):
            item = parent / 'items' / row['id']
            asset = json.loads((item / 'generation-response.json').read_text())
            archived = json.loads((item / 'judge-prompt.json').read_text())
            if build_judge_messages(cases[row['case_id']], asset) != archived:
                raise ValueError('Judge contract changed since the original run')
    return manifest, records, pending


def summarize_questions(records):
    metrics = {}
    for strategy in sorted({r['strategy'] for r in records}):
        group = [r for r in records if r['strategy'] == strategy]
        metrics[strategy] = {
            'requested': len(group),
            'whole_asset_valid': sum(r['whole_asset_valid'] for r in group),
            'judged': sum(bool(r.get('judge')) for r in group),
            'difficulty_matched': sum(bool(r.get('difficulty_match')) for r in group),
            'question_quality_pass': sum(bool(r.get('qualified')) for r in group),
            'question_quality_pass_rate': sum(bool(r.get('qualified')) for r in group) / len(group),
            'reused_primary_judgements': sum(r['diagnostic_status'] == 'reused_primary_judgement' for r in group),
            'quality_failures': {key: sum(r.get('judge', {}).get(key) is False for r in group)
                for key in ('correctness', 'grounded', 'answerable', 'ambiguity_free')},
        }
    return metrics


async def run_diagnostic(args, parent_manifest, records, pending, output):
    _, judge_settings = make_settings(Settings.from_env(), parent_manifest['judge_model'])
    if public_parameters(judge_settings.text.extra) != parent_manifest['judge_parameters']:
        raise ValueError('Judge parameters changed')
    cap = min(args.max_calls, judge_settings.max_daily_calls)
    if len(pending) > cap:
        raise ValueError('Supplemental call plan exceeds cap')
    store = CappedStore(output / 'runtime', cap)
    provider = ApiProviders(judge_settings, store)
    semaphore = asyncio.Semaphore(2)
    stop = asyncio.Event()
    manifest = {
        'kind': 'post_hoc_question_only_diagnostic', 'status': 'running',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'parent_run': str(args.parent.resolve()), 'parent_records_sha256': digest(json.loads((args.parent / 'records.json').read_text())),
        'generation_prompt_version': parent_manifest['prompt_version'],
        'judge_version': JUDGE_VERSION, 'judge_model': judge_settings.text.model,
        'judge_parameters': public_parameters(judge_settings.text.extra),
        'planned_additional_calls': len(pending), 'max_calls': cap,
        'new_generation_calls': 0, 'reused_judgements': sum(bool(r.get('judge')) for r in records),
        'human_labels': False, 'changes_primary_scores': False,
        'limitation': 'Exploratory after observing format failures. Question quality excludes whole-asset format and author design gates; it does not measure deliverable success. All original requested slots remain in denominator.',
    }
    write_json(output / 'manifest.json', manifest)

    def checkpoint():
        write_json(output / 'records.json', records)
        write_json(output / 'calls.json', call_rows(store))

    async def assess(row, messages):
        async with semaphore:
            if stop.is_set():
                row['diagnostic_status'] = 'not_attempted_provider_stop'
                checkpoint()
                return
            item = output / 'items' / row['id']
            write_json(item / 'judge-prompt.json', messages)
            try:
                from scripts.difficulty_prompts import DifficultyJudgeResult
                raw = await provider.generate(messages, 'judge:' + row['id'])
                write_json(item / 'judge-response.json', raw)
                score(row, DifficultyJudgeResult.model_validate(raw).model_dump())
                row['diagnostic_status'] = 'additional_judgement'
            except Exception as exc:
                row['diagnostic_status'] = 'failed'
                row['diagnostic_error'] = safe_error(exc)
                calls = store.all('SELECT http_status FROM calls WHERE job_id=?', ('judge:' + row['id'],))
                if any(c['http_status'] in (401, 402, 403, 404, 429) for c in calls):
                    stop.set()
            checkpoint()
            print('diagnosed', row['id'], row['diagnostic_status'], flush=True)

    try:
        await asyncio.gather(*(assess(row, messages) for row, messages in pending))
        manifest['status'] = 'stopped_provider_error' if stop.is_set() else 'complete'
    except asyncio.CancelledError:
        manifest['status'] = 'interrupted'
        raise
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = safe_error(exc)
        raise
    finally:
        await provider.close()
        checkpoint()
        calls = call_rows(store)
        summary = {'metrics': summarize_questions(records), 'additional_calls': len(calls),
            'reported_additional_cost_usd': sum(c['usage'].get('cost', 0) for c in calls),
            'calls_without_cost': sum('cost' not in c['usage'] for c in calls)}
        write_json(output / 'summary.json', summary)
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        manifest['actual_additional_calls'] = len(calls)
        write_json(output / 'manifest.json', manifest)
    return manifest['status'] == 'complete'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--max-calls', type=int, default=30)
    args = parser.parse_args()
    manifest, records, pending = prepare(args.parent)
    print(json.dumps({'additional_judge_calls': len(pending), 'reused_judgements': sum(bool(r.get('judge')) for r in records),
        'requested_slots': len(records), 'new_generations': 0, 'live': args.live}), flush=True)
    if len(pending) > args.max_calls or args.max_calls < 1:
        parser.error('Invalid or insufficient supplemental call cap')
    if not args.live:
        return 0
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.parent.with_name(args.parent.name + '-question-diagnostic-' + stamp)
    output.mkdir(exist_ok=False)
    for relative in ('scripts/difficulty_question_diagnostic.py', 'scripts/difficulty_experiment.py',
                     'scripts/difficulty_prompts.py', 'app/models.py', 'app/providers.py'):
        dest = output / 'code' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, dest)
    write_json(output / 'code-hashes.json', {str(p.relative_to(output / 'code')): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (output / 'code').rglob('*.py')})
    success = asyncio.run(run_diagnostic(args, manifest, records, pending, output))
    print(output, flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
