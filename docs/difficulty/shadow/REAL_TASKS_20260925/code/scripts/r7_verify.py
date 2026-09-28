"""Offline R7 replay of candidates, shared requests and final metrics.

Run only after both splits have finished. The frozen runner's verify, rank and
metrics functions operate on a temporary copy; socket connections and Remote
construction are blocked. No rewrite, embedding or reranking API is called.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import r7_experiment as runner


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def compare_candidates(expected, actual):
    strip = lambda rows: {key: {field: value for field, value in row.items() if field != 'ranking_ms'}
                          for key, row in rows.items()}
    left, right = strip(expected), strip(actual)
    differences = []
    for key in sorted(set(left) | set(right)):
        if key not in left or key not in right:
            differences.append({'row': key, 'fields': ['row_presence']})
        elif left[key] != right[key]:
            fields = sorted(field for field in set(left[key]) | set(right[key])
                            if field not in left[key] or field not in right[key]
                            or left[key][field] != right[key][field])
            differences.append({'row': key, 'fields': fields})
    return {'equal_except_local_ranking_ms': left == right,
            'original_rows': len(left), 'replayed_rows': len(right),
            'different_rows': len(differences), 'first_differences': differences[:10]}


def block_network(*args, **kwargs):
    raise RuntimeError('Offline R7 replay forbids network connections.')


def replay(run, output=None):
    run = run.resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (output or ROOT/'docs/rag/r7-replays'/stamp).resolve()
    if output == run or run in output.parents:
        raise ValueError('Replay output must be outside the original run.')
    rank_outputs = ('candidates', 'pre-rows', 'shared-requests')
    required = ['freeze.json', 'calls.json', 'selection-lock.json', 'rewrites.json',
                'query-embeddings.json', 'document-vectors.npz', 'document-vector-manifest.json']
    required += [f'{split}-{name}.json' for split in ('dev', 'test')
                 for name in (*rank_outputs, 'shared-rerank', 'per-query', 'rankings')]
    missing = [name for name in required if not (run/name).is_file()]
    if missing:
        raise ValueError('Run is not ready for replay; missing: ' + ', '.join(missing))
    calls = read(run/'calls.json')
    if any(row.get('status') == 'started' for row in calls.values()):
        raise ValueError('Provider requests remain unfinished; wait before replaying.')
    runner.verify(run)
    output.mkdir(parents=True, exist_ok=False)
    before = {str(path.relative_to(run)): digest(path) for path in run.rglob('*')
              if path.is_file() and '__pycache__' not in path.parts
              and path.name != 'offline-verification.json'}
    write(output/'original-file-hashes.json', before)
    shutil.copyfile(Path(__file__), output/'r7_verify.py')
    checks, failures = {}, []
    transcript = io.StringIO()
    with tempfile.TemporaryDirectory(prefix='lumori-r7-replay-') as scratch:
        copied = Path(scratch)/'run'
        shutil.copytree(run, copied)
        with patch('socket.socket.connect', block_network), \
                patch('socket.socket.connect_ex', block_network), \
                patch('socket.create_connection', block_network), \
                patch.object(runner, 'Remote', side_effect=RuntimeError('Remote is forbidden during replay.')), \
                redirect_stdout(transcript):
            runner.verify(copied)
            # Dev may be replayed before test only in this disposable copy.
            (copied/'test-candidates.json').unlink()
            for split in ('dev', 'test'):
                if split == 'test':
                    # The selection lock binds the exact original pre-row bytes.
                    # Compare dev's replay first, then restore those bytes before
                    # the runner performs its held-out lock check.
                    shutil.copyfile(run/'dev-pre-rows.json', copied/'dev-pre-rows.json')
                runner.rank(copied, split)
                comparison = compare_candidates(read(run/f'{split}-candidates.json'),
                                                read(copied/f'{split}-candidates.json'))
                checks[split] = {'candidates': comparison}
                if not comparison['equal_except_local_ranking_ms']:
                    failures.append(split + ': candidate replay mismatch')
                for name in ('pre-rows', 'shared-requests'):
                    same = read(run/f'{split}-{name}.json') == read(copied/f'{split}-{name}.json')
                    checks[split][name + '_exact_equal'] = same
                    if not same:
                        failures.append(split + ': ' + name + ' replay mismatch')
                checks[split]['pre_rows_bytes_equal'] = digest(run/f'{split}-pre-rows.json') == digest(copied/f'{split}-pre-rows.json')
                for name in rank_outputs:
                    shutil.copyfile(copied/f'{split}-{name}.json', output/f'{split}-replayed-{name}.json')

            # Final metric reconstruction uses the exact archived stage outputs,
            # so new ranking timings cannot leak into the metric comparison.
            for split in ('dev', 'test'):
                for name in rank_outputs:
                    shutil.copyfile(run/f'{split}-{name}.json', copied/f'{split}-{name}.json')
            for split in ('dev', 'test'):
                if split == 'test':
                    shutil.copyfile(run/'dev-pre-rows.json', copied/'dev-pre-rows.json')
                runner.metrics(copied, split)
                for name in ('per-query', 'rankings'):
                    same = read(run/f'{split}-{name}.json') == read(copied/f'{split}-{name}.json')
                    checks[split][name + '_exact_equal'] = same
                    if not same:
                        failures.append(split + ': ' + name + ' replay mismatch')
                    shutil.copyfile(copied/f'{split}-{name}.json', output/f'{split}-replayed-{name}.json')
                checks[split]['metric_rows'] = len(read(copied/f'{split}-per-query.json'))
            checks['copied_calls_sha256_unchanged'] = digest(copied/'calls.json') == before['calls.json']
            checks['copied_selection_lock_sha256_unchanged'] = digest(copied/'selection-lock.json') == before['selection-lock.json']

    (output/'replay-log.txt').write_text(transcript.getvalue(), encoding='utf-8')
    changed = [name for name, expected in before.items()
               if not (run/name).is_file() or digest(run/name) != expected]
    if changed:
        failures.append('Original experiment files changed during replay.')
    for field in ('copied_calls_sha256_unchanged', 'copied_selection_lock_sha256_unchanged'):
        if not checks[field]:
            failures.append(field + ': failed')
    result = {
        'schema': 'r7-offline-verification-v1',
        'status': 'passed' if not failures else 'failed',
        'verified_at': datetime.now(timezone.utc).isoformat(),
        'original_run': str(run), 'replay_directory': str(output),
        'verifier_sha256': digest(Path(__file__)),
        'checks': checks, 'failures': failures,
        'original_file_count_checked': len(before),
        'original_files_unchanged': not changed, 'changed_original_files': changed,
        'original_calls_sha256_before': before['calls.json'],
        'original_calls_sha256_after': digest(run/'calls.json'),
        'new_api_calls': 0, 'network_connections_blocked': True,
        'candidate_comparison_exclusions': ['ranking_ms'],
        'pre_row_comparison_exclusions': [], 'shared_request_comparison_exclusions': [],
        'metric_comparison_exclusions': [],
        'method': 'Verified frozen input/code identity; replayed candidates, pre-retrieval metrics '
                  'and shared rerank requests in a temporary copy. Restored archived stage outputs '
                  'and reconstructed final rankings and all per-query metrics from recorded scores. '
                  'Original dev lock bytes preserved; no provider calls. This verifies deterministic '
                  'local processing, not fresh model quality, relevance labels or latency.',
    }
    write(output/'verification.json', result)
    write(run/'offline-verification.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return not failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if replay(args.run, args.output) else 1)
