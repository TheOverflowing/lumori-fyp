"""CA1 runner regression checks using HTTP fixtures; no live provider calls."""
import json
from pathlib import Path

import httpx
import pytest

from app.config import Endpoint, Settings
from app.auth import AuthService
from app.pipeline import parse_document
from app.providers import ApiProviders
from app.store import Store
from scripts.ca1_smoke import SAMPLE, main, run_live
from test_workflow import apply_difficulty_fixture, difficulty_judge_fixture


class DemoWire:
    def __init__(self, mode='valid'):
        self.mode = mode
        self.calls = []

    def __call__(self, request):
        self.calls.append(request.url.path)
        data = json.loads(request.content)
        if self.mode == 'provider_failure':
            return httpx.Response(401, text='fixture-private-key forbidden upstream body')
        if request.url.path.endswith('/embeddings'):
            rows = []
            for index, value in enumerate(data['input']):
                value = value.casefold()
                vector = [float(value.count(term)) + .1 for term in
                          ('rag ingestion', 'citation support', 'embedding compatibility', 'reviewed text version')]
                rows.append({'index': index, 'embedding': vector})
            return httpx.Response(200, json={'data': rows, 'model': 'fixture-embedding',
                                            'usage': {'prompt_tokens': 1, 'total_tokens': 1}})
        if request.url.path.endswith('/chat/completions'):
            instruction = json.loads(data['messages'][1]['content'])
            if instruction.get('task') == 'difficulty_assessment':
                result=difficulty_judge_fixture(instruction,self.difficulty_levels)
                return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
            unsupported = 'CA1-Zirconium-999' in instruction['request']['topic']
            sufficient = not unsupported or self.mode == 'false_answer'
            refs = [instruction['reference_chunks'][0]['id']]
            asset = {'title': 'Fixture teaching material', 'evidence_sufficient': sufficient,
                     'evidence_note': '' if sufficient else 'The supplied course has no measurement for that material.',
                     'learning_objectives': [], 'sections': [], 'questions': [], 'visual_prompt': ''}
            if sufficient:
                asset['sections'] = [{'heading': 'Fixture explanation',
                                      'text': 'Retrieval supplies passages for review.', 'citation_ids': refs}]
                asset['questions'] = [{
                    'kind': 'short_answer', 'stem': 'What does retrieval supply?', 'options': [],
                    'answer': 'Passages for review.', 'explanation': 'The passages provide inspectable evidence.',
                    'difficulty_reason': 'One direct relationship.', 'citation_ids': refs,
                } for _ in range(instruction['question_count'])]
            self.difficulty_levels=apply_difficulty_fixture(asset,instruction)
            return httpx.Response(200, json={'model': 'fixture-text', 'usage': {'total_tokens': 2},
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(asset)}}]})
        raise AssertionError('Unexpected provider capability requested')


@pytest.fixture
def configured(tmp_path):
    settings = Settings(data_dir=tmp_path / 'normal-app-data')
    settings.text = Endpoint('https://fixture.invalid/v1', 'fixture-private-key',
                             'fixture-text', '/chat/completions')
    settings.embedding = Endpoint('https://fixture.invalid/v1', 'fixture-private-key',
                                  'fixture-embedding', '/embeddings')
    return settings


def collect(settings, output, **kwargs):
    wire = DemoWire(kwargs.pop('mode', 'valid'))
    def provider_factory(config, store):
        return ApiProviders(config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire)))
    report, folder = run_live(settings, output, providers_factory=provider_factory, job_timeout=5, **kwargs)
    return report, folder, wire


def test_sample_has_selectable_passages_with_one_embedding_batch():
    _, chunks = parse_document(SAMPLE.name, SAMPLE.read_bytes())
    assert Settings().top_k < len(chunks) <= 16
    assert len({chunk['text'] for chunk in chunks}) == len(chunks)
    assert 'CA1-Zirconium-999' not in SAMPLE.read_text()


def test_ca1_collects_all_cases_and_restores_demo_draft(configured, tmp_path):
    configured.data_dir.mkdir()
    sentinel = configured.data_dir / 'existing-data.txt'
    sentinel.write_text('Do not change the normal application database')
    report, folder, wire = collect(configured, tmp_path / 'evidence', review_flow=True)
    assert report['technical_checks_passed'], report
    assert report['all_expected_outcomes_observed']
    assert report['manual_quality_verified'] is False
    assert not report['all_tasks_succeeded']  # Expected evidence refusal is a separate outcome.
    assert report['isolated_data']
    assert report['authentication']['mode'] == 'isolated_account_registration'
    assert sentinel.read_text() == 'Do not change the normal application database'
    assert list(configured.data_dir.iterdir()) == [sentinel]
    assert report['nominal_provider_attempts'] == len(wire.calls) == report['observed_provider_attempts'] == 11
    assert report['maximum_with_one_structural_repair_per_generation'] == 17
    assert len(report['final_contents']) == 3
    assert all(row['status'] == 'draft' for row in report['final_contents'])
    initial = json.loads((folder / 'quiz-draft-v1.json').read_text())
    final = json.loads((folder / 'review-final-evidence.json').read_text())
    assert initial['version'] == 1 and final['version'] == 3
    assert final['revisions'][0]['asset'] == initial['asset']
    assert final['asset']['title'].startswith('[Workflow demo]')
    assert Store(Path(report['runtime_directory'])).all('SELECT * FROM evaluations') == []
    assert Store(Path(report['runtime_directory'])).all('SELECT * FROM auth_sessions') == []
    refusal = json.loads((folder / 'unsupported_objective-job-evidence.json').read_text())
    assert refusal['job']['status'] == 'insufficient_evidence'
    assert refusal['evidence']['sources']
    for artifact in folder.glob('*.json'):
        assert 'fixture-private-key' not in artifact.read_text()
    for row in report['results'][1:4]:
        assert row['retrieval_observation']['candidate_chunk_count'] > row['retrieval_observation']['retrieved_chunk_count']
        assert row['retrieval_observation']['human_relevance_review'] == 'pending'


def test_ca1_default_never_approves_or_edits(configured, tmp_path):
    report, folder, wire = collect(configured, tmp_path / 'evidence')
    assert report['technical_checks_passed'], report
    assert len(wire.calls) == 11
    assert not (folder / 'review-workflow.json').exists()
    assert all(row['version'] == 1 and row['status'] == 'draft' for row in report['final_contents'])


def test_ca1_unsupported_answer_is_retained_as_failure(configured, tmp_path):
    report, folder, wire = collect(configured, tmp_path / 'evidence', mode='false_answer')
    assert not report['technical_checks_passed']
    unsupported = next(row for row in report['results'] if row['case'] == 'unsupported_objective')
    assert unsupported['job']['status'] == 'succeeded'
    assert not unsupported['expected_status_observed']
    assert (folder / 'unsupported_objective-draft-v1.json').is_file()
    assert (folder / 'unsupported_objective-evidence.json').is_file()
    assert len(report['final_contents']) == 4
    assert len(wire.calls) == 11


def test_ca1_provider_failure_stops_after_index_and_preserves_record(configured, tmp_path):
    report, folder, wire = collect(configured, tmp_path / 'evidence', mode='provider_failure')
    assert not report['technical_checks_passed']
    assert len(wire.calls) == 1
    assert report['results'][0]['job']['status'] == 'failed'
    assert len(report['skipped_cases']) == 4
    assert json.loads((folder / 'results.json').read_text()) == report
    assert (folder / 'index-job-evidence.json').is_file()
    assert 'fixture-private-key' not in (folder / 'results.json').read_text()


def test_ca1_interruption_still_writes_report(configured, tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.ca1_smoke.SAMPLE', tmp_path / 'missing-source.md')
    report, folder, wire = collect(configured, tmp_path / 'evidence')
    assert not report['technical_checks_passed']
    assert report['fatal_error']['type'] == 'FileNotFoundError'
    assert report['results'] == [] and wire.calls == []
    assert json.loads((folder / 'results.json').read_text()) == report


def test_ca1_preflight_does_not_create_app_or_contact_provider(configured, tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.ca1_smoke.Settings.from_env', lambda: configured)
    def forbidden(*args, **kwargs):
        raise AssertionError('Preflight must not create the application')
    monkeypatch.setattr('scripts.ca1_smoke.run_live', forbidden)
    assert main(['--output-dir', str(tmp_path / 'evidence')]) == 0
    result = json.loads((tmp_path / 'evidence/api-preflight.json').read_text())
    assert result['live_model_verified'] is False
    assert not list((tmp_path / 'evidence').glob('live-*'))


def test_ca1_existing_data_requires_credentials_before_database_open(configured, tmp_path, monkeypatch):
    monkeypatch.delenv('FYP_SMOKE_ACCOUNT_EMAIL', raising=False)
    monkeypatch.delenv('FYP_SMOKE_ACCOUNT_PASSWORD', raising=False)
    report, _, wire = collect(configured, tmp_path / 'evidence', use_app_data=True)
    assert report['fatal_error']['type'] == 'ValueError'
    assert not report['technical_checks_passed']
    assert not configured.data_dir.exists()
    assert wire.calls == []


def test_ca1_existing_account_login_scopes_data_and_does_not_register(configured, tmp_path, monkeypatch):
    password = 'An explicit smoke account password 84!'
    store = Store(configured.data_dir)
    auth = AuthService(store, configured)
    existing = auth.register('existing@example.test', password, 'Existing account')
    auth.logout(existing.token)
    # A legacy course remains unclaimed and does not appear in smoke results.
    store.execute('INSERT INTO courses VALUES(?,?,?)', ('legacy', 'Untouched legacy course', 'before-test'))
    monkeypatch.setenv('FYP_SMOKE_ACCOUNT_EMAIL', 'existing@example.test')
    monkeypatch.setenv('FYP_SMOKE_ACCOUNT_PASSWORD', password)
    def registration_forbidden(*args, **kwargs):
        raise AssertionError('Existing-data smoke must log in, never register a replacement account.')
    monkeypatch.setattr(AuthService, 'register', registration_forbidden)
    report, folder, wire = collect(configured, tmp_path / 'evidence', use_app_data=True)
    assert report['technical_checks_passed'], report
    assert report['authentication'] == {'mode': 'existing_account_login', 'user_id': existing.user['id']}
    assert len(store.all('SELECT * FROM users')) == 1
    assert not store.one('SELECT * FROM course_owners WHERE course_id=?', ('legacy',))
    assert len(store.all('SELECT * FROM courses')) == 2
    assert store.all('SELECT * FROM auth_sessions') == []
    assert len(wire.calls) == 11
    for artifact in folder.glob('*.json'):
        assert password not in artifact.read_text()
        assert existing.token not in artifact.read_text()
        assert 'csrf_token' not in artifact.read_text()


def test_ca1_wrong_existing_password_never_falls_back_to_registration(configured, tmp_path):
    store = Store(configured.data_dir)
    auth = AuthService(store, configured)
    existing = auth.register('existing@example.test', 'A known existing account password 23!', 'Existing')
    auth.logout(existing.token)
    report, folder, wire = collect(configured, tmp_path / 'evidence', use_app_data=True,
        account_email='existing@example.test', account_password='An incorrect password with length 23!')
    assert report['fatal_error']['http_status'] == 401
    assert wire.calls == []
    assert len(store.all('SELECT * FROM users')) == 1
    assert store.all('SELECT * FROM courses') == []
    assert 'An incorrect password' not in (folder / 'results.json').read_text()


def test_ca1_secure_cookie_is_used_without_disabling_its_protection(configured, tmp_path):
    configured.auth_cookie_secure = True
    report, _, _ = collect(configured, tmp_path / 'evidence')
    assert report['technical_checks_passed'], report


def test_difficulty_smoke_uses_real_account_session_with_provider_fixtures(configured, tmp_path, monkeypatch):
    import app.main as main_module
    import scripts.difficulty_smoke as runner
    original_create_app = main_module.create_app
    class DifficultyWire(DemoWire):
        def __call__(self, request):
            response = super().__call__(request)
            if request.url.path.endswith('/chat/completions'):
                payload = response.json()
                asset = json.loads(payload['choices'][0]['message']['content'])
                if 'questions' in asset:
                    for number, question in enumerate(asset['questions'], 1):
                        question['stem'] = f'Question {number}: ' + question['stem']
                    payload['choices'][0]['message']['content'] = json.dumps(asset)
                    return httpx.Response(200, json=payload)
            return response
    wire = DifficultyWire()
    def create_fixture_app(settings):
        return original_create_app(settings, lambda config, store: ApiProviders(
            config, store, httpx.AsyncClient(transport=httpx.MockTransport(wire))))
    monkeypatch.setattr(main_module, 'create_app', create_fixture_app)
    monkeypatch.setattr(runner.Settings, 'from_env', lambda: configured)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['difficulty_smoke.py', '--live'])
    assert runner.main() == 0
    reports = list((tmp_path / 'docs/ca1/evidence').glob('difficulty-*/results.json'))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report['technical_checks_passed']
    assert report['authentication']['mode'] == 'isolated_account_registration'
    assert report['provider_attempts'] == len(wire.calls) == 7
    store = Store(Path(report['runtime_directory']))
    assert len(store.all('SELECT * FROM users')) == 1
    assert store.all('SELECT * FROM auth_sessions') == []
