"""Replay R6 ranking and metrics offline, preserving the archived experiment.

Only r6_experiment.verify/rank/metrics are called. No Remote instance or provider
method is used. The replay runs in a temporary copy and socket connections are
blocked as an additional guard. Run after both split metrics have been saved.
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
from scripts import r6_experiment as runner


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    pending.replace(path)


def without_candidate_timing(rows):
    return {key: {field: value for field, value in row.items() if field != 'ranking_ms'}
            for key, row in rows.items()}


def compare_candidates(expected, actual):
    left, right = without_candidate_timing(expected), without_candidate_timing(actual)
    keys = sorted(set(left) | set(right))
    differences = []
    for key in keys:
        if key not in left or key not in right:
            differences.append({'row': key, 'fields': ['row_presence']})
        elif left[key] != right[key]:
            fields = sorted(k for k in set(left[key]) | set(right[key])
                            if left[key].get(k) != right[key].get(k))
            differences.append({'row': key, 'fields': fields})
    return {'equal_except_local_ranking_ms': left == right,
            'original_rows': len(left), 'replayed_rows': len(right),
            'different_rows': len(differences), 'first_differences': differences[:10]}


def block_network(*args, **kwargs):
    raise RuntimeError('Offline R6 replay forbids network connections.')


def replay(run, output=None):
    run = run.resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (output or ROOT/'docs/rag/r6-replays'/stamp).resolve()
    if output == run or run in output.parents:
        raise ValueError('The replay directory must be outside the original run.')
    required = ['freeze.json', 'calls.json', 'selection-lock.json', 'rewrites.json',
                'query-embeddings.json'] + [f'{split}-{name}.json'
                    for split in ('dev', 'test')
                    for name in ('candidates', 'rerank', 'per-query', 'rankings', 'summary')]
    missing = [name for name in required if not (run/name).is_file()]
    if missing:
        raise ValueError('Experiment is not ready for replay; missing: ' + ', '.join(missing))
    calls = read(run/'calls.json')
    if any(row.get('status') == 'started' for row in calls.values()):
        raise ValueError('Unfinished provider requests remain; wait for the experiment to finish.')
    runner.verify(run)
    output.mkdir(parents=True, exist_ok=False)
    before = {str(path.relative_to(run)): digest(path) for path in run.rglob('*')
              if path.is_file() and '__pycache__' not in path.parts
              and path.name != 'offline-verification.json'}
    write(output/'original-file-hashes.json', before)
    shutil.copyfile(Path(__file__), output/'r6_verify.py')
    checks, failures = {}, []
    transcript = io.StringIO()
    with tempfile.TemporaryDirectory(prefix='lumori-r6-replay-') as scratch:
        copied = Path(scratch)/'run'
        shutil.copytree(run, copied)
        with patch('socket.socket.connect', block_network), \
                patch('socket.socket.connect_ex', block_network), \
                patch('socket.create_connection', block_network), \
                patch.object(runner, 'Remote', side_effect=RuntimeError('Remote is forbidden during replay.')), \
                redirect_stdout(transcript):
            runner.verify(copied)
            # Remove the exposure marker only in the disposable copy. The
            # original dev summary and selection lock stay intact for rank(test).
            (copied/'test-candidates.json').unlink()
            for split in ('dev', 'test'):
                runner.rank(copied, split)
                comparison = compare_candidates(read(run/f'{split}-candidates.json'),
                                                read(copied/f'{split}-candidates.json'))
                checks[split] = {'candidates': comparison}
                if not comparison['equal_except_local_ranking_ms']:
                    failures.append(split + ': candidate replay mismatch')
                shutil.copyfile(copied/f'{split}-candidates.json',
                                output/f'{split}-replayed-candidates.json')

            # Restore archived timings before recomputing metrics. This permits
            # exact comparisons of every metric, including the latency estimates.
            for split in ('dev', 'test'):
                shutil.copyfile(run/f'{split}-candidates.json', copied/f'{split}-candidates.json')
            for split in ('dev', 'test'):
                if split == 'test':
                    # metrics(dev) writes a summary. Preserve the original bytes
                    # so the held-out guard checks the original selection basis.
                    shutil.copyfile(run/'dev-summary.json', copied/'dev-summary.json')
                runner.metrics(copied, split)
                for name in ('per-query', 'rankings', 'summary'):
                    same = read(run/f'{split}-{name}.json') == read(copied/f'{split}-{name}.json')
                    checks[split][name + '_exact_equal'] = same
                    if not same:
                        failures.append(split + ': ' + name + ' replay mismatch')
                    shutil.copyfile(copied/f'{split}-{name}.json',
                                    output/f'{split}-replayed-{name}.json')
                checks[split]['metric_rows'] = len(read(copied/f'{split}-per-query.json'))
            checks['copied_calls_sha256_unchanged'] = digest(copied/'calls.json') == before['calls.json']

    (output/'replay-log.txt').write_text(transcript.getvalue(), encoding='utf-8')
    changed = [name for name, expected in before.items()
               if not (run/name).is_file() or digest(run/name) != expected]
    if changed:
        failures.append('Original experiment files changed during replay.')
    if not checks['copied_calls_sha256_unchanged']:
        failures.append('Provider ledger changed in the offline copy.')
    result = {
        'schema': 'r6-offline-verification-v1',
        'status': 'passed' if not failures else 'failed',
        'verified_at': datetime.now(timezone.utc).isoformat(),
        'original_run': str(run), 'replay_directory': str(output),
        'verifier_sha256': digest(Path(__file__)),
        'checks': checks, 'failures': failures,
        'original_file_count_checked': len(before),
        'original_files_unchanged': not changed, 'changed_original_files': changed,
        'original_calls_sha256_before': before['calls.json'],
        'original_calls_sha256_after': digest(run/'calls.json'),
        'new_api_calls': 0,
        'network_connections_blocked': True,
        'candidate_comparison_exclusions': ['ranking_ms'],
        'metric_comparison_exclusions': [],
        'method': 'Frozen code identity verified; candidate rankings recomputed in a temporary copy. '
                  'Original candidates including archived timing restored for exact reranking-order, '
                  'per-query metric and summary reproduction from recorded provider responses. '
                  'This verifies deterministic local processing, not fresh model quality or fresh latency.',
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
