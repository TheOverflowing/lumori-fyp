"""Replay a frozen reading-order rule over unmerged Paddle predictions.

No new inference; keep every failure, all text and coordinates unchanged.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import json
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.parsing_reading_order import reorder_items
from scripts.evaluate_document_parsing import sha256, text_metrics
from scripts.evaluate_mineru_parsing import summarize

STRATEGY = 'paddleocr_3_7_vl16_mlx_unmerged_xycut'


def derive(parent, out, manifest_path):
    out.mkdir(parents=True, exist_ok=False); (out/'outputs').mkdir()
    config = json.loads((parent/'configuration.json').read_text())
    assert config['strategies'] == ['paddleocr_3_7_vl16_mlx_unmerged']
    assert config['manifest_sha256'] == sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    samples = {s['id']: s for s in manifest['samples']}
    parent_rows = json.loads((parent/'rows.json').read_text())
    assert len(parent_rows) == 3*len(samples)
    files = ['scripts/parsing_reading_order.py', 'scripts/derive_parsing_reading_order.py', 'scripts/evaluate_document_parsing.py']
    config = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'strategies': [STRATEGY],
              'manifest_path': str(manifest_path.relative_to(ROOT)), 'manifest_sha256': sha256(manifest_path),
              'variants': config['variants'], 'metric_contract': manifest['metric_contract'],
              'inference_source_run': str(parent.relative_to(ROOT)), 'inference_source_rows_sha256': sha256(parent/'rows.json'),
              'new_model_inference_calls': 0, 'execution': 'Offline coordinate-only ordering replay; elapsed_seconds = recorded parent inference time + measured replay seconds, NOT an independent timing run.',
              'source_sha256': {p: sha256(ROOT/p) for p in files}}
    (out/'configuration.json').write_text(json.dumps(config, indent=2)+'\n')
    for name in files:
        target = out/'source-snapshot'/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name, target)
    rows = []; changes = []
    for row in parent_rows:
        sample = samples[row['sample_id']]
        old_stem = f'{row["strategy"]}--{row["sample_id"]}--{row["variant"]}'
        raw = json.loads((parent/'outputs'/(old_stem+'.json')).read_text())
        stem = f'{STRATEGY}--{row["sample_id"]}--{row["variant"]}'
        directory = out/'outputs'/stem; directory.mkdir()
        started = time.perf_counter(); prediction = ''
        if not raw['error']:
            original = json.loads((parent/'outputs'/old_stem/'items.json').read_text())
            assert '\n'.join(i['text'] for i in original) == raw['prediction']
            ordered = reorder_items(original)
            assert Counter(json.dumps(i, sort_keys=True) for i in original) == Counter(json.dumps(i, sort_keys=True) for i in ordered)
            (directory/'items.json').write_text(json.dumps(ordered, ensure_ascii=False, indent=2)+'\n')
            prediction = '\n'.join(i['text'] for i in ordered)
            (directory/'prediction.txt').write_text(prediction)
            changes.append({'sample_id': row['sample_id'], 'variant': row['variant'],
                            'old_order': [i['id'] for i in original], 'new_order': [i['id'] for i in ordered]})
        replay_seconds = time.perf_counter()-started
        reference = manifest_path.parent/sample['reference']; assert sha256(reference) == sample['reference_sha256']
        updated = {**row, 'strategy': STRATEGY, 'elapsed_seconds': row['elapsed_seconds']+replay_seconds,
                   'parent_inference_seconds': row['elapsed_seconds'], 'ordering_replay_seconds': replay_seconds,
                   **text_metrics(reference.read_text(), prediction, row['language'], sample['cer_eligible'])}
        (out/'outputs'/(stem+'.json')).write_text(json.dumps({'case': updated, 'prediction': prediction,
            'error': raw['error'], 'input_sha256': raw['input_sha256'], 'inference_source': str((parent/'outputs'/old_stem).relative_to(ROOT))}, ensure_ascii=False, indent=2)+'\n')
        rows.append(updated)
    (out/'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    (out/'ordering-changes.json').write_text(json.dumps(changes, indent=2)+'\n')
    summarize(out)
    print(f'{STRATEGY}: replayed {len(rows)} cases, no new inference', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('parent', type=Path); parser.add_argument('output', type=Path); parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    derive(args.parent.resolve(), args.output.resolve(), args.manifest.resolve())
