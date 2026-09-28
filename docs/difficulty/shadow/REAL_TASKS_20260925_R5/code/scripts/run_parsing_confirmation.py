"""Freeze finalists from complete development results, then run disjoint pages."""
from pathlib import Path
from datetime import datetime, timezone
import json
import importlib.util
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_mineru_parsing as mineru
from scripts import evaluate_parsing_candidates as docling
from scripts import evaluate_paddle_parsing as paddle
from scripts import evaluate_paddle_unmerged as unmerged
from scripts import evaluate_document_parsing as baseline

P4 = ROOT/'docs/parsing/experiments/P4-candidate-expansion-20260918'
MANIFEST = ROOT/'docs/parsing/benchmarks/omnidocbench-confirmation-v1/manifest.json'


def frozen_adaptive(out):
    """Use the actual P1 parser snapshot, not a later application revision."""
    source = ROOT/'docs/parsing/experiments/P1-baseline-adaptive-20260918/source-snapshot/app/document_parsing.py'
    spec = importlib.util.spec_from_file_location('p4_frozen_adaptive', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous_bytecode_setting = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    manifest = json.loads(MANIFEST.read_text())
    out.mkdir(exist_ok=False); (out/'outputs').mkdir()
    files = [str(source.relative_to(ROOT)), 'scripts/run_parsing_confirmation.py', 'scripts/evaluate_document_parsing.py']
    config = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'strategies': ['adaptive_local_v1'],
              'manifest_path': str(MANIFEST.relative_to(ROOT)), 'manifest_sha256': baseline.sha256(MANIFEST),
              'variants': mineru.VARIANTS, 'metric_contract': manifest['metric_contract'],
              'source_sha256': {name: baseline.sha256(ROOT/name) for name in files},
              'execution': 'Exact P1 application parser snapshot; adaptive_local_v1, chi_sim+eng, max_ocr_pages4, preserve_visualsFalse, timeout120; frozen model-free/Tesseract baseline.'}
    (out/'configuration.json').write_text(json.dumps(config, indent=2)+'\n')
    for name in files:
        dest = out/'source-snapshot'/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name, dest)
    rows = []
    for sample in manifest['samples']:
        ref = MANIFEST.parent/sample['reference']; assert baseline.sha256(ref) == sample['reference_sha256']
        for variant in mineru.VARIANTS:
            entry = sample['files'][variant]; path = MANIFEST.parent/entry['path']
            assert baseline.sha256(path) == entry['sha256']
            started = time.perf_counter(); prediction = ''; error = None; report = {}
            try:
                parsed = module.parse_document_structured(path.name, path.read_bytes(), strategy='adaptive_local_v1',
                    ocr_languages='chi_sim+eng', max_ocr_pages=4, preserve_visuals=False, timeout_seconds=120)
                pages = parsed.text_pages
                if len(pages) != 1:
                    raise ValueError(f'Expected one benchmark page, received {len(pages)}')
                prediction = '\n'.join(pages)
                report = parsed.report()
            except Exception as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}; prediction = ''
            row = {'sample_id': sample['id'], 'strategy': 'adaptive_local_v1', 'variant': variant,
                   'language': sample['language'], 'stratum': sample['stratum'],
                   'completed_without_exception': error is None, 'elapsed_seconds': time.perf_counter()-started,
                   'error_type': error['type'] if error else None,
                   **baseline.text_metrics(ref.read_text(), prediction, sample['language'], sample['cer_eligible'])}
            stem = f'adaptive_local_v1--{sample["id"]}--{variant}'
            (out/'outputs'/(stem+'.json')).write_text(json.dumps({'case': row, 'prediction': prediction, 'error': error,
                'report': report, 'input_sha256': entry['sha256']}, ensure_ascii=False, indent=2)+'\n')
            rows.append(row); (out/'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
            print(stem, 'CER', row['cer'], 'error', error, flush=True)
    mineru.summarize(out)


def main():
    # Documented development-stage ablation; confirmation data remains untouched.
    prediction, seconds, error = unmerged.run_case(ROOT/'tmp/mineru-runtime/smoke.png',
                                                 P4/'preflight/paddle-unmerged', 240)
    (P4/'preflight/paddle-unmerged-result.json').write_text(json.dumps(
        {'prediction': prediction, 'seconds': seconds, 'error': error}, ensure_ascii=False, indent=2)+'\n')
    if error or not prediction.strip():
        raise RuntimeError('Unmerged configuration preflight failed; no formal variant or confirmation started.')
    unmerged.evaluate(docling.PILOT, P4/'runs/paddle-unmerged', 240)
    ranking = []
    for name in ('advanced', 'docling-tess', 'granite-mlx', 'paddle-mlx', 'paddle-unmerged'):
        run = P4/'runs'/name
        rows = json.loads((run/'rows.json').read_text())
        assert len(rows) == 36 and (run/'summary.json').exists()
        eligible = [r for r in rows if r['cer_eligible']]
        assert len(eligible) == 18
        ranking.append({'run': name, 'strategy': rows[0]['strategy'],
                        'macro_cer': sum(r['cer'] for r in eligible)/len(eligible),
                        'rows_sha256': baseline.sha256(run/'rows.json')})
    ranking.sort(key=lambda x: (x['macro_cer'], x['strategy']))
    choice = ranking[0]
    frozen = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'selection_plan': 'Incumbent Standard + lowest development CER new candidate + adaptive baseline; no confirmation predictions inspected.',
              'development_ranking': ranking, 'challenger': choice,
              'finalists': ['mineru_4_0_2_standard_onnx', choice['strategy'], 'adaptive_local_v1'],
              'confirmation_manifest_sha256': baseline.sha256(MANIFEST),
              'runner_sha256': baseline.sha256(Path(__file__))}
    dest = P4/'confirmation'; dest.mkdir(exist_ok=False)
    (dest/'frozen-finalists.json').write_text(json.dumps(frozen, indent=2)+'\n')
    shutil.copy2(Path(__file__), dest/'runner-snapshot.py')
    frozen_adaptive(dest/'adaptive')
    print('Confirmation adaptive complete', flush=True)
    mineru.MANIFEST = MANIFEST
    mineru.evaluate(dest/'standard', ['standard'], 240)
    print('Confirmation Standard complete', flush=True)
    if choice['run'] == 'advanced':
        mineru.evaluate(dest/'challenger', ['advanced'], 240)
    elif choice['run'] == 'paddle-mlx':
        paddle.evaluate(MANIFEST, dest/'challenger', 240)
    elif choice['run'] == 'paddle-unmerged':
        unmerged.evaluate(MANIFEST, dest/'challenger', 240)
    else:
        key = {'docling-tess': 'docling_tess_v2', 'granite-mlx': 'granite_mlx'}[choice['run']]
        docling.evaluate(key, MANIFEST, dest/'challenger', 240)
    print('Confirmation complete', flush=True)


if __name__ == '__main__':
    main()
