"""Seal the completed P4 research artifacts, without changing historical runs."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_document_parsing import sha256

P4 = ROOT / 'docs/parsing/experiments/P4-candidate-expansion-20260918'


def main():
    audit = json.loads((P4 / 'audit.json').read_text())
    assert audit['all_passed']
    for name in ('report.md', 'FINDINGS.md', 'selection.json', 'figures/visual-verification.json',
                 'confirmation/geometry-evidence.json', 'runtime-cleanup.json'):
        assert (P4 / name).is_file(), name
    p3 = P4.parent / 'P3-mineru-20260918'
    historical = json.loads((p3 / 'artifact-manifest.json').read_text())
    for entry in historical['files']:
        path = p3 / entry['path']
        assert path.stat().st_size == entry['bytes'] and sha256(path) == entry['sha256'], path
    p1 = P4.parent / 'P1-baseline-adaptive-20260918'
    old_digest = json.loads((p3 / 'verification.json').read_text())['p1_rows_sha256']
    assert sha256(p1 / 'rows.json') == old_digest
    (P4 / 'historical-integrity.json').write_text(json.dumps({
        'verified_at_utc': datetime.now(timezone.utc).isoformat(),
        'p3_manifest_sha256': sha256(p3 / 'artifact-manifest.json'),
        'p3_files_verified_against_pre_p4_inventory': len(historical['files']),
        'p1_rows_sha256_matches_pre_p4_record': True,
        'scope': 'P3 full recorded artifact inventory and P1 rows; per-run frozen sources also audited in audit.json.'
    }, indent=2) + '\n')
    scripts = ['archive_parsing_p4.py', 'report_parsing_p4.py', 'plot_parsing_p4.py',
               'evaluate_parsing_structures.py', 'parsing_teds.py', 'parsing_reading_order.py',
               'evaluate_document_parsing.py', 'evaluate_mineru_parsing.py',
               'evaluate_mineru_regions.py', 'prepare_parsing_benchmark.py',
               'derive_parsing_reading_order.py', 'run_parsing_confirmation.py',
               'run_parsing_geometry_confirmation.py', 'evaluate_parsing_candidates.py',
               'evaluate_paddle_parsing.py', 'evaluate_paddle_unmerged.py',
               'prepare_parsing_confirmation.py', 'download_parsing_models.py']
    tests = ['test_parsing_metrics.py', 'test_mineru_evaluation.py', 'test_mineru_regions.py',
             'test_paddle_adapter.py', 'test_docling_adapter.py', 'test_parsing_teds.py',
             'test_parsing_reading_order.py']
    for folder, names in [('scripts', scripts), ('tests', tests)]:
        destination = P4 / 'support-source-snapshot' / folder
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copy2(ROOT / folder / name, destination / name)
    files = []
    for path in sorted(P4.rglob('*')):
        if not path.is_file() or path == P4 / 'artifact-manifest.json' or '__pycache__' in path.parts:
            continue
        files.append({'path': str(path.relative_to(P4)), 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    doc = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'All P4 artifacts except this inventory and bytecode. Model weight identities are recorded separately; weights remain in local runtime directories.',
           'external_manifests': {str(p.relative_to(ROOT)): sha256(p) for p in [
               ROOT / 'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json',
               ROOT / 'docs/parsing/benchmarks/omnidocbench-confirmation-v1/manifest.json']},
           'documentation_sha256': {str(p.relative_to(ROOT)): sha256(p) for p in [
               ROOT / 'docs/parsing/README.md', ROOT / 'docs/parsing/DEVELOPMENT_RECORD_20260918.md',
               ROOT / 'docs/parsing/research/REFERENCES_20260918.md']},
           'files': files}
    (P4 / 'artifact-manifest.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'bytes': sum(f['bytes'] for f in files),
                      'historical_p3_files_verified': len(historical['files'])}))


if __name__ == '__main__':
    main()
