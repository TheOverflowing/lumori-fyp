"""Replay two frozen reviews and a deliberately unsupported answer; dry by default."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.assessment_contracts import validate_requirement_checks
from app.config import Settings
from app.generation_agent import CheckedFlexibleReview
from app.harness_bridge import run_phase
from app.harness_evidence import REVISION
from app.pipeline import Pipeline
from app.providers import ApiProviders
from app.store import dumps
from scripts.difficulty_experiment import CappedStore, digest, write_json
from scripts.difficulty_prompts import make_request
from scripts.flexible_answer_experiment import COURSE_ID, frozen_cases, seed_documents, snapshot_code


def inputs():
    source = ROOT / 'docs/agent/runtime-comparison/R2_20260924/humanities_en__deepseek_harness.json'
    archive = json.loads(source.read_text())
    slot = archive['evidence']['agent']['slots'][0]
    cases = []
    for number in (2, 3):
        attempt = slot['attempts'][number - 1]
        messages = deepcopy(attempt['review']['history'][0]['messages'])
        cases.append({'id': f'original_attempt_{number}', 'messages': messages,
                      'brief': slot['brief'], 'origin_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    adversarial = deepcopy(cases[0])
    adversarial['id'] = 'unsupported_rejection_claim'
    contract = json.loads(adversarial['messages'][1]['content'])
    contract['question']['answer'] = (
        'Both accounts explicitly establish that the curator rejected the letter and censored its contents. '
        'The volunteer states that the curator read the letter and refused to display it. '
        'Therefore censorship is proven, and no competing interpretation is possible.')
    contract['question']['explanation'] = 'The passages prove rejection and censorship as stated facts.'
    adversarial['messages'][1]['content'] = dumps(contract)
    adversarial['mutation'] = 'Only candidate answer/explanation changed to unsupported explicit claims; not a human gold set.'
    cases.append(adversarial)
    return cases


async def run(args):
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = inputs()
    code = snapshot_code(output)
    relative = 'scripts/harness_evidence_replay.py'
    shutil.copy2(ROOT / relative, output / 'code' / relative)
    code[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    manifest = {'schema': 'harness-evidence-replay-v1', 'live': args.live,
                'call_cap': 6, 'per_case_cap': 2, 'protocol': REVISION,
                'inputs_sha256': digest(cases), 'code_sha256': code,
                'limitations': ['AI development fixtures; no teacher labels or learner data.',
                               'Semantic correctness is independent of literal evidence validity.',
                               'One observation per case; no statistical reliability estimate.']}
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'inputs.json', cases)
    if not args.live:
        print(dumps({'dry_run': True, 'cases': len(cases), 'max_calls': 6, 'output': str(output)}))
        return
    base = Settings.from_env()
    base.text.require('text')
    settings = replace(base, data_dir=output / 'runtime', max_daily_calls=6,
        text=replace(base.text, extra={'thinking': {'type': 'disabled'}, 'max_tokens': 8192}),
        text_json_mode=True, agent_runtime='deepseek_harness', agent_orchestration='supervisor_v2',
        harness_max_requests=2, harness_max_output_tokens=8192, harness_reasoning_effort='off',
        harness_response_format='json_object')
    manifest['provider'] = {'model': settings.text.model, 'endpoint_signature': settings.text.signature,
                            'parameters': settings.text.extra, 'response_format': 'json_object'}
    write_json(output / 'manifest.json', manifest)
    store = CappedStore(settings.data_dir, 6)
    sources, _ = frozen_cases(['humanities_en'])
    seed_documents(store, sources)
    rows = []
    for case in cases:
        request = make_request(sources['humanities_en']).model_copy(update={
            'course_id': COURSE_ID, 'request_key': 'review-replay-' + case['id'], 'use_subagents': True})
        job, _ = store.job(request.request_key, 'generate', request.model_dump())
        store.save_job_evidence(job['id'], {'schema_version': 'education-agent-v1',
                                          'configuration': {'max_calls': 2}})
        providers = ApiProviders(settings, store)
        pipeline = Pipeline(settings, store, providers, enforce_account_ownership=False)
        report = {}
        row = {'id': case['id'], 'status': 'failed', 'report': report}
        print(dumps({'starting': case['id']}), flush=True)
        try:
            raw = await run_phase(pipeline, request, job['id'], case['messages'], 'review',
                                  sources['humanities_en']['sources'], report)
            row['response'] = raw
            parsed = CheckedFlexibleReview.model_validate(raw)
            contract = json.loads(case['messages'][1]['content'])
            coverage = validate_requirement_checks([c.model_dump() for c in parsed.requirement_checks],
                case['brief'], contract['question'], sources['humanities_en']['sources'])
            row.update(status='completed', literal_evidence_valid=True, coverage_issues=coverage,
                       answer_correct=parsed.answer_correct, source_supported=parsed.source_supported,
                       issues=parsed.issues, explanation_issues=parsed.explanation_issues)
        except Exception as exc:
            row['error_type'] = type(exc).__name__
        finally:
            await providers.close()
            row['calls'] = store.calls_for_job(job['id'])
            rows.append(row)
            write_json(output / 'results.json', rows)
        print(dumps({'finished': case['id'], 'status': row['status'],
                     'calls': len(row['calls']), 'answer_correct': row.get('answer_correct')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', required=True)
    asyncio.run(run(parser.parse_args()))
