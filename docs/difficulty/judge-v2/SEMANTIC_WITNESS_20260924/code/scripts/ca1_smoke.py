"""CA1 preflight by default; --live explicitly calls real text/embedding providers.

Runs use isolated data. Optional review-flow checks restore the material to draft
and never assign a human reviewer or fill content-quality ratings.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import secrets
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Settings

SAMPLE = ROOT / 'sample_data/ca1_rag_course.md'
CASES = (
    {'case': 'lesson', 'material': 'lesson', 'difficulty': 'easy',
     'topic': 'Explain RAG ingestion and retrieval, including how passages become vectors and how a learning objective selects evidence.',
     'expected_status': 'succeeded', 'source_terms': ['RAG ingestion']},
    {'case': 'quiz', 'material': 'quiz', 'difficulty': 'medium',
     'topic': 'Assess citation support: why can an existing citation identifier fail to support an answer? Use a concrete example from the notes.',
     'expected_status': 'succeeded', 'source_terms': ['Citation support']},
    {'case': 'assignment', 'material': 'assignment', 'difficulty': 'hard',
     'topic': 'Compare embedding compatibility after a model change with a reviewed text version after an edit. Explain what needs rebuilding or renewed approval.',
     'expected_status': 'succeeded',
     'source_terms': ['Embedding compatibility', 'reviewed text version']},
    {'case': 'unsupported_objective', 'material': 'lesson', 'difficulty': 'easy',
     'topic': 'State the experimentally measured superconducting critical temperature of the fictional material CA1-Zirconium-999 in kelvin, with the laboratory measurement method.',
     'expected_status': 'insufficient_evidence', 'source_terms': []},
)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def wait_job(client, response, timeout=600):
    response.raise_for_status()
    job_id = response.json()['job_id']
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get('/api/jobs/' + job_id)
        response.raise_for_status()
        job = response.json()
        if job['status'] not in ('queued', 'running'):
            return job
        time.sleep(.05)
    return {'id': job_id, 'status': 'timeout', 'result': None,
            'error': 'Observation timed out. Inspect the existing job before retrying.'}


def retrieval_observation(sources, chunks, expected_terms):
    """Phrase presence and a selected subset are not human relevance judgments."""
    selected = {source['id'] for source in sources}
    known = {chunk['id'] for chunk in chunks}
    combined = '\n'.join(source['text'] for source in sources).casefold()
    return {
        'candidate_chunk_count': len(chunks), 'retrieved_chunk_count': len(sources),
        'retrieved_ids_belong_to_index': bool(selected) and selected <= known,
        'selection_excludes_some_candidates': bool(selected) and selected < known,
        'expected_topic_phrase_presence': {term: term.casefold() in combined for term in expected_terms},
        'ranking': [{'rank': rank, 'chunk_id': source['id'], 'score': source.get('score'),
                     'page': source['page'], 'document_name': source['document_name']}
                    for rank, source in enumerate(sources, 1)],
        'human_relevance_review': 'pending',
        'limitation': 'Phrase presence and a ranked subset do not establish semantic relevance or factual support.',
    }


def exercise_review_flow(client, content, run_dir):
    """Preserve v1, exercise approval mechanics, and leave the final text draft."""
    content_id = content['id']
    base = '/api/contents/' + content_id
    learn = '/api/learn/' + content_id
    checks = {}
    result = {'content_id': content_id, 'checks': checks, 'human_quality_verified': False,
              'approval_purpose': 'Automated workflow demonstration only; no human review or evaluation rating.'}
    try:
        checks['draft_hidden_from_learning'] = client.get(learn).status_code == 404
        edited = deepcopy(content['asset'])
        edited['title'] = ('[Workflow demo] ' + edited['title'])[:200]
        saved = client.post(base + '/review', json={
            'version': content['version'], 'action': 'save', 'asset': edited})
        saved.raise_for_status()
        version = saved.json()['version']
        checks['save_creates_new_draft'] = version == content['version'] + 1 and saved.json()['status'] == 'draft'
        checks['stale_approval_rejected'] = client.post(base + '/review', json={
            'version': content['version'], 'action': 'approve'}).status_code == 409
        approval = client.post(base + '/review', json={'version': version, 'action': 'approve'})
        approval.raise_for_status()
        checks['current_version_approved'] = approval.json()['status'] == 'approved'
        hidden = client.get(learn)
        revealed = client.get(learn, params={'reveal_answers': True})
        hidden.raise_for_status()
        revealed.raise_for_status()
        write_json(run_dir / 'review-learning-hidden.json', hidden.json())
        write_json(run_dir / 'review-learning-revealed.json', revealed.json())
        questions = hidden.json()['asset']['questions']
        checks['answers_hidden_by_default'] = bool(questions) and all(
            not {'answer', 'explanation', 'difficulty_reason'} & question.keys() for question in questions)
        questions = revealed.json()['asset']['questions']
        checks['answers_available_on_reveal'] = bool(questions) and all(
            {'answer', 'explanation', 'difficulty_reason'} <= question.keys() for question in questions)
        checks['learning_uses_approved_version'] = hidden.json()['version'] == version
        export = client.get(base + '/export')
        export.raise_for_status()
        (run_dir / 'review-approved-export.md').write_text(export.text, encoding='utf-8')
        bundle = client.get(base + '/evidence')
        bundle.raise_for_status()
        write_json(run_dir / 'review-approved-evidence.json', bundle.json())
    finally:
        # Technical approval is never left behind, even if a later check fails.
        current = client.get(base)
        if current.status_code == 200 and current.json()['status'] == 'approved':
            row = current.json()
            reset = client.post(base + '/review', json={
                'version': row['version'], 'action': 'save', 'asset': row['asset']})
            checks['returned_to_draft'] = reset.status_code == 200 and reset.json()['status'] == 'draft'
        else:
            checks['returned_to_draft'] = current.status_code == 200 and current.json()['status'] == 'draft'
        checks['edited_version_hidden_again'] = client.get(learn).status_code == 404
        final_bundle = client.get(base + '/evidence')
        if final_bundle.status_code == 200:
            bundle = final_bundle.json()
            write_json(run_dir / 'review-final-evidence.json', bundle)
            original = next((row for row in bundle['revisions'] if row['version'] == content['version']), None)
            checks['original_draft_preserved'] = original is not None and original['asset'] == content['asset']
        write_json(run_dir / 'review-workflow.json', result)
    return result


def safe_exception(exc):
    # Arbitrary exception text can include URLs, headers, or provider bodies.
    result = {'type': type(exc).__name__,
              'message': 'Evidence collection interrupted; inspect the saved jobs and completed steps.'}
    if getattr(exc, 'response', None) is not None:
        result['http_status'] = exc.response.status_code
    return result


def smoke_account_credentials(*, use_app_data=False, account_email=None, account_password=None):
    """Resolve secrets in memory, before opening an existing application database."""
    if use_app_data:
        email = account_email if account_email is not None else os.getenv('FYP_SMOKE_ACCOUNT_EMAIL', '')
        password = account_password if account_password is not None else os.getenv('FYP_SMOKE_ACCOUNT_PASSWORD', '')
        if not email or not password:
            raise ValueError('Existing application data requires FYP_SMOKE_ACCOUNT_EMAIL and FYP_SMOKE_ACCOUNT_PASSWORD, or explicit account arguments.')
        return email, password
    return 'smoke-' + secrets.token_hex(12) + '@example.invalid', secrets.token_urlsafe(32)


@contextmanager
def authenticated_smoke_client(app, credentials, *, existing_account=False):
    """Exercise real auth APIs; never save passwords, cookies or CSRF tokens."""
    from fastapi.testclient import TestClient
    scheme = 'https' if app.state.settings.auth_cookie_secure else 'http'
    with TestClient(app, base_url=scheme+'://testserver') as client:
        email, password = credentials
        payload = {'email': email, 'password': password}
        if not existing_account:
            payload['display_name'] = 'Isolated smoke test'
        response = client.post('/api/auth/login' if existing_account else '/api/auth/register', json=payload)
        response.raise_for_status()
        session = response.json()
        client.headers['X-CSRF-Token'] = session['csrf_token']
        client.headers['X-Account-ID'] = session['user']['id']
        try:
            yield client, {'mode': 'existing_account_login' if existing_account else 'isolated_account_registration',
                           'user_id': session['user']['id']}
        finally:
            client.post('/api/auth/logout').raise_for_status()
            client.headers.pop('X-CSRF-Token', None)
            client.headers.pop('X-Account-ID', None)


def run_live(settings, output_root, *, providers_factory=None,
             review_flow=False, use_app_data=False, job_timeout=600,
             account_email=None, account_password=None):
    from app.main import create_app

    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir = Path(output_root) / ('live-' + run_id)
    run_dir.mkdir(parents=True)
    if not use_app_data:
        settings = replace(settings, data_dir=Path(output_root) / 'tmp/runtime' / run_id)
    report = {
        'run_id': run_id, 'results': [], 'checks': {},
        'isolated_data': not use_app_data, 'runtime_directory': str(settings.data_dir),
        'review_flow_requested': review_flow,
        'manual_quality_verified': False, 'technical_checks_passed': False,
        'note': 'This is a small integration demonstration, not a model benchmark. Human quality ratings remain blank. No speech or image calls are requested.',
    }

    def checkpoint():
        write_json(run_dir / 'results.json', report)

    def record_job(client, name, response, expected):
        started = time.monotonic()
        job = wait_job(client, response, job_timeout)
        item = {'case': name, 'job': job, 'expected_status': expected,
                'expected_status_observed': job['status'] == expected,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'manual_review': 'pending'}
        report['results'].append(item)
        checkpoint()
        # Refusals/failures are useful evidence without a content object.
        evidence = client.get('/api/jobs/' + job['id'] + '/evidence')
        item['job_evidence_http_status'] = evidence.status_code
        if evidence.status_code == 200:
            write_json(run_dir / (name + '-job-evidence.json'), evidence.json())
            item['job_evidence_file'] = name + '-job-evidence.json'
        checkpoint()
        return item

    checkpoint()
    try:
        credentials = smoke_account_credentials(use_app_data=use_app_data,
            account_email=account_email, account_password=account_password)
        raw = SAMPLE.read_bytes()
        report['source_file'] = SAMPLE.name
        report['source_sha256'] = hashlib.sha256(raw).hexdigest()
        (run_dir / SAMPLE.name).write_bytes(raw)
        app = create_app(settings) if providers_factory is None else create_app(settings, providers_factory)
        with authenticated_smoke_client(app, credentials, existing_account=use_app_data) as (client, authentication):
            report['authentication'] = authentication
            before = client.get('/api/status')
            before.raise_for_status()
            report['status_before'] = before.json()
            course = client.post('/api/courses', json={'name': 'CA1 live smoke ' + run_id})
            course.raise_for_status()
            course_id = course.json()['id']
            report['course_id'] = course_id
            upload = client.post('/api/documents', data={'course_id': course_id},
                                 files={'file': (SAMPLE.name, raw, 'text/markdown')})
            upload.raise_for_status()
            document = upload.json()
            report['document'] = document
            chunk_response = client.get('/api/documents/' + document['id'] + '/chunks')
            chunk_response.raise_for_status()
            chunks = chunk_response.json()
            write_json(run_dir / 'source-chunks.json', chunks)
            report['checks']['multiple_source_chunks'] = len(chunks) > 1
            report['checks']['more_candidates_than_top_k'] = len(chunks) > settings.top_k
            assessment_cases=sum(case['material']!='lesson' for case in CASES)
            report['nominal_provider_attempts'] = (len(chunks) + 15) // 16 + 2 * len(CASES) + assessment_cases
            report['maximum_with_one_structural_repair_per_generation'] = report['nominal_provider_attempts'] + len(CASES) + assessment_cases
            index = record_job(client, 'index', client.post('/api/documents/' + document['id'] + '/index'), 'succeeded')
            if index['expected_status_observed']:
                for case in CASES:
                    request = {key: case[key] for key in ('topic', 'material', 'difficulty')}
                    request.update(course_id=course_id, question_type='short_answer', count=1,
                                   language='en', document_ids=[document['id']],
                                   request_key='ca1-' + run_id + '-' + case['case'])
                    item = record_job(client, case['case'], client.post('/api/generations', json=request), case['expected_status'])
                    job = item['job']
                    if job['status'] == 'succeeded':
                        content_id = job['result']['content_id']
                        response = client.get('/api/contents/' + content_id)
                        response.raise_for_status()
                        content = response.json()
                        write_json(run_dir / (case['case'] + '-draft-v1.json'), content)
                        evidence = client.get('/api/contents/' + content_id + '/evidence')
                        evidence.raise_for_status()
                        write_json(run_dir / (case['case'] + '-evidence.json'), evidence.json())
                        export = client.get('/api/contents/' + content_id + '/export')
                        export.raise_for_status()
                        (run_dir / (case['case'] + '-export-v1.md')).write_text(export.text, encoding='utf-8')
                        item['checks'] = {
                            'initial_version_is_draft': content['version'] == 1 and content['status'] == 'draft',
                            'draft_hidden_from_learning': client.get('/api/learn/' + content_id).status_code == 404,
                            'markdown_export_contains_title': content['asset']['title'] in export.text,
                            'job_evidence_available': item['job_evidence_http_status'] == 200,
                        }
                        observation = retrieval_observation(content['sources'], chunks, case['source_terms'])
                        item['retrieval_observation'] = observation
                        item['checks']['retrieval_ids_belong_to_index'] = observation['retrieved_ids_belong_to_index']
                        item['checks']['retrieval_selects_subset'] = observation['selection_excludes_some_candidates']
                        if case['case'] == 'quiz' and review_flow:
                            item['review_flow'] = exercise_review_flow(client, content, run_dir)
                    elif job['status'] == 'insufficient_evidence':
                        item['checks'] = {
                            'refusal_has_reason': bool(job.get('result', {}).get('message')),
                            'refusal_has_no_content_id': not job.get('result', {}).get('content_id'),
                            'job_evidence_available': item['job_evidence_http_status'] == 200,
                        }
                    checkpoint()
            else:
                report['skipped_cases'] = [case['case'] for case in CASES]
            after = client.get('/api/status')
            after.raise_for_status()
            report['status_after'] = after.json()
            report['observed_provider_attempts'] = after.json()['calls_today'] - before.json()['calls_today']
            final_contents = client.get('/api/contents', params={'course_id': course_id})
            final_contents.raise_for_status()
            report['final_contents'] = final_contents.json()
            report['checks']['all_materials_left_as_drafts'] = all(row['status'] == 'draft' for row in final_contents.json())
    except Exception as exc:
        report['fatal_error'] = safe_exception(exc)
    finally:
        expected = {case['case'] for case in CASES} | {'index'}
        report['all_expected_outcomes_observed'] = (
            {row['case'] for row in report['results']} == expected
            and all(row['expected_status_observed'] for row in report['results']))
        # Kept for readers of older reports; an expected refusal is not succeeded.
        report['all_tasks_succeeded'] = (len(report['results']) == len(expected)
            and all(row['job']['status'] == 'succeeded' for row in report['results']))
        checks = list(report['checks'].values())
        for row in report['results']:
            checks.extend(row.get('checks', {}).values())
            checks.extend(row.get('review_flow', {}).get('checks', {}).values())
        report['technical_checks_passed'] = (report['all_expected_outcomes_observed']
            and not report.get('fatal_error') and bool(checks) and all(checks))
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        checkpoint()
    return report, run_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicitly call the configured text and embedding providers.')
    parser.add_argument('--exercise-review-flow', action='store_true', help='Exercise quiz editing, approval, learning and return-to-draft without human scoring.')
    parser.add_argument('--use-app-data', action='store_true', help='Use the normal application database and an existing account. Requires FYP_SMOKE_ACCOUNT_EMAIL/PASSWORD. Stop the normal server first.')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/ca1/evidence')
    args = parser.parse_args(argv)
    if not args.live and (args.exercise_review_flow or args.use_app_data):
        parser.error('--exercise-review-flow and --use-app-data require --live')
    settings = Settings.from_env()
    if args.use_app_data:
        try:
            smoke_account_credentials(use_app_data=True)
        except ValueError as exc:
            parser.error(str(exc))
    errors = []
    for capability in ('text', 'embedding'):
        try:
            getattr(settings, capability).require(capability)
        except ValueError as exc:
            errors.append(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    preflight = {
        'checked_at': datetime.now(timezone.utc).isoformat(), 'live_requested': args.live,
        'text_configured': settings.text.configured, 'embedding_configured': settings.embedding.configured,
        'status': 'blocked_missing_configuration' if errors else 'configuration_present_not_validated',
        'messages': errors, 'live_model_verified': False,
    }
    write_json(args.output_dir / 'api-preflight.json', preflight)
    print(json.dumps(preflight, ensure_ascii=False, indent=2))
    if not args.live or errors:
        return 2 if errors else 0
    report, run_dir = run_live(settings, args.output_dir, review_flow=args.exercise_review_flow,
                               use_app_data=args.use_app_data)
    print(run_dir)
    return 0 if report['technical_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
