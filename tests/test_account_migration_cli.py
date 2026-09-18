"""Local recovery CLI checks on isolated databases; no provider requests."""
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import pytest

from app.account_migration import prepare_legacy_claim
from app.store import Store, dumps, now
from scripts import manage_accounts


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def legacy(tmp_path):
    directory = tmp_path / 'runtime'
    store = Store(directory)
    stamp = now()
    store.execute('INSERT INTO courses VALUES(?,?,?)', ('course', 'Legacy course', stamp))
    store.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',
        ('document', 'course', 'notes.md', 'fixture-sha', 'ready', 1, stamp))
    store.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',
        ('chunk', 'document', 1, 'Existing course material', '[1.0,0.0]', 'fixture'))
    job, _ = store.job('legacy-request', 'generate', {'course_id': 'course', 'document_ids': ['document']})
    store.execute('INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)',
        ('content', 'course', job['id'], 1, 'draft', '{}', '[]', '{}', stamp))
    # Keep filesystem assets in the backup coverage independently of API validation.
    (directory / 'documents').mkdir()
    (directory / 'documents/notes.md').write_text('Existing document bytes')
    (directory / 'media').mkdir()
    (directory / 'media/example.bin').write_bytes(b'fixture-media-bytes')
    return store


def cli(store, *args):
    env = dict(os.environ, DATA_DIR=str(store.path.parent))
    return subprocess.run([sys.executable, str(ROOT / 'scripts/manage_accounts.py'), *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)


def row_snapshot(store):
    with store.connect() as db:
        tables = [row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {table: [tuple(row) for row in db.execute('SELECT * FROM "'+table+'" ORDER BY rowid')]
                for table in tables}


def read_recovery(path):
    source = path.read_text()
    url = html.unescape(re.search(r'<a href="([^"]+)"', source)[1])
    values = parse_qs(urlsplit(url).fragment.partition('?')[2])
    return values['token'][0], values['email'][0]


def test_status_does_not_migrate_or_change_legacy_database(legacy):
    # Simulate the exact prior schema, without account-related tables.
    with legacy.connect() as db:
        for table in ('auth_sessions', 'auth_throttles', 'course_owners', 'job_owners', 'users'):
            db.execute('DROP TABLE '+table)
    before = row_snapshot(legacy)
    result = cli(legacy, 'status')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'courses': 1, 'documents': 1, 'contents': 1, 'jobs': 1, 'assigned_courses': 0}
    assert row_snapshot(legacy) == before


@pytest.mark.parametrize('with_document_assets', [False, True])
def test_prepare_backs_up_original_data_and_stores_only_private_token_digest(legacy, tmp_path, with_document_assets):
    assets = legacy.path.parent / 'document_assets'
    png_bytes = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6'
        'lAAAAABJRU5ErkJggg==')
    expected_assets = {
        'document/page-preview.png': png_bytes,
        'document/nested/embedded-image.png': png_bytes,
        'second-document/page-preview.png': png_bytes,
    } if with_document_assets else {}
    for relative, content in expected_assets.items():
        path = assets / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    before = manage_accounts.fingerprint(legacy.path)
    output = tmp_path / 'private/recovery.html'
    result = cli(legacy, 'prepare-legacy', '--email', 'Owner@Example.test', '--output', str(output))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    token, email = read_recovery(output)
    assert email == 'owner@example.test' and len(token) == 43
    assert token not in result.stdout and token not in result.stderr
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert manage_accounts.fingerprint(legacy.path) == before
    claim = legacy.one('SELECT * FROM legacy_workspace_claims')
    assert claim['token_hash'] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in dumps(row_snapshot(legacy))
    assert legacy.all('SELECT * FROM course_owners') == []
    assert legacy.all('SELECT * FROM job_owners') == []
    backup = Path(report['backup'])
    assert stat.S_IMODE(backup.stat().st_mode) == 0o700
    assert stat.S_IMODE((backup/'studio.sqlite3').stat().st_mode) == 0o600
    assert manage_accounts.fingerprint(backup/'studio.sqlite3') == before
    assert (backup/'documents/notes.md').read_bytes() == (legacy.path.parent/'documents/notes.md').read_bytes()
    assert (backup/'media/example.bin').read_bytes() == (legacy.path.parent/'media/example.bin').read_bytes()
    saved_assets = backup / 'document_assets'
    if with_document_assets:
        assert {str(path.relative_to(saved_assets)) for path in saved_assets.rglob('*') if path.is_file()} == set(expected_assets)
        for relative, content in expected_assets.items():
            assert (saved_assets / relative).read_bytes() == content
            assert (assets / relative).read_bytes() == content
    else:
        assert not saved_assets.exists()
    evidence = json.loads((backup/'verification.json').read_text())
    assert evidence['before'] == evidence['after'] == before
    assert evidence['integrity_check'] == 'ok' and evidence['foreign_key_violations'] == []
    assert token not in (backup/'verification.json').read_text()


@pytest.mark.parametrize('path_kind', ['existing_file', 'dangling_symlink'])
def test_existing_output_failure_never_invalidates_prior_capability(legacy, tmp_path, path_kind):
    claim = prepare_legacy_claim(legacy, 'owner@example.test')
    saved = legacy.all('SELECT * FROM legacy_workspace_claims')
    output = tmp_path / 'recovery.html'
    target = tmp_path / 'unexpected-target.html'
    if path_kind == 'existing_file':
        output.write_text('Existing private output stays untouched')
    else:
        output.symlink_to(target)
    result = cli(legacy, 'prepare-legacy', '--email', 'owner@example.test', '--output', str(output))
    assert result.returncode != 0
    assert 'must be a new file' in result.stderr
    assert legacy.all('SELECT * FROM legacy_workspace_claims') == saved
    assert claim['token'] not in result.stdout + result.stderr
    if path_kind == 'existing_file':
        assert output.read_text() == 'Existing private output stays untouched'
    else:
        assert output.is_symlink() and not target.exists()
    assert not (tmp_path/'tmp/account-backups').exists()


def test_publication_failure_rolls_back_new_claim_and_keeps_previous_valid(legacy, tmp_path, monkeypatch):
    prepare_legacy_claim(legacy, 'owner@example.test')
    before = legacy.all('SELECT * FROM legacy_workspace_claims')
    output = tmp_path / 'recovery.html'
    monkeypatch.setenv('DATA_DIR', str(legacy.path.parent))
    monkeypatch.setattr('sys.argv', ['manage_accounts.py', 'prepare-legacy', '--email', 'owner@example.test', '--output', str(output)])
    def failed_flush(_):
        raise OSError('Injected filesystem flush failure')
    monkeypatch.setattr(manage_accounts.os, 'fsync', failed_flush)
    with pytest.raises(OSError, match='Injected filesystem flush failure'):
        manage_accounts.main()
    assert legacy.all('SELECT * FROM legacy_workspace_claims') == before
    assert not output.exists()


def test_token_containing_placeholder_words_survives_html_generation(legacy, tmp_path, monkeypatch, capsys):
    import app.account_migration as migration
    token = 'JOBS' + 'A'*39
    monkeypatch.setattr(migration.secrets, 'token_urlsafe', lambda _: token)
    monkeypatch.setenv('DATA_DIR', str(legacy.path.parent))
    output = tmp_path / 'recovery.html'
    monkeypatch.setattr('sys.argv', ['manage_accounts.py', 'prepare-legacy', '--email', 'owner@example.test', '--output', str(output)])
    manage_accounts.main()
    assert read_recovery(output)[0] == token
    output_text = capsys.readouterr()
    assert token not in output_text.out + output_text.err
    assert legacy.one('SELECT token_hash FROM legacy_workspace_claims')['token_hash'] == hashlib.sha256(token.encode()).hexdigest()
