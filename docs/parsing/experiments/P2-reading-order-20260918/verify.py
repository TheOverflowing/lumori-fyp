"""Read-only replay/score audit; writes only a new verification.json receipt."""
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    freeze = json.loads((HERE / 'freeze.json').read_text())
    assert sha(HERE / 'configuration.json') == freeze['configuration_sha256']
    assert freeze['configuration_sha256'] == '09e768622e359ad97c624360f1ecc0ce3f036859d609ec8b17014632246cdfe6'
    for path, expected in freeze['source_sha256'].items():
        assert sha(HERE / 'source-snapshot' / Path(path).name) == expected, path
    order = load_module('frozen_order', HERE / 'source-snapshot/reorder_ocr_blocks.py')
    scorer = load_module('frozen_score', HERE / 'source-snapshot/evaluate_document_parsing.py')
    config = json.loads((HERE / 'configuration.json').read_text())
    integrity = json.loads((HERE / 'input-integrity.json').read_text())
    manifest_path = ROOT / config['manifest_path']
    assert sha(manifest_path) == integrity['manifest_sha256']
    manifest = json.loads(manifest_path.read_text())
    samples = {sample['id']: sample for sample in manifest['samples']}
    rows = json.loads((HERE / 'rows.json').read_text())
    hashes = {(row['sample_id'], row['variant']): row for row in integrity['input_cases']}
    expected_pairs = {(sample, variant) for sample in config['scored_sample_ids'] for variant in config['variants']}
    assert len(rows) == 18 and {(row['sample_id'], row['variant']) for row in rows} == expected_pairs
    checked = []
    for row in rows:
        sample_id, variant = row['sample_id'], row['variant']
        sample, expected = samples[sample_id], hashes[(sample_id, variant)]
        assert sample['cer_eligible']
        source_path = ROOT / config['input_experiment'] / 'outputs' / f'rapidocr_v1--{sample_id}--{variant}.json'
        psm6_path = source_path.with_name(f'tesseract_psm6_v1--{sample_id}--{variant}.json')
        output_path = HERE / 'outputs' / f'geometry_two_column_v1--{sample_id}--{variant}.json'
        reference_path = manifest_path.parent / sample['reference']
        assert sha(source_path) == expected['rapid_input_sha256']
        assert sha(psm6_path) == expected['psm6_input_sha256']
        assert sha(reference_path) == sample['reference_sha256'] == expected['reference_sha256']
        source, psm6, output = [json.loads(path.read_text()) for path in (source_path, psm6_path, output_path)]
        assert output['input_sha256'] == sha(source_path)
        assert output['original_prediction'] == source['prediction']
        assert Counter(output['prediction']) == Counter(source['prediction'])
        replay = order.reorder_page(source['report']['pages'][0], config)
        assert replay['text'] == output['prediction'] and replay['trace'] == output['trace']
        assert sorted(output['trace']['order_indices']) == list(range(len(source['report']['pages'][0]['blocks'])))
        reference = reference_path.read_text()
        for prefix, prediction in [('rapid', source['prediction']), ('reordered', output['prediction']), ('psm6', psm6['prediction'])]:
            metric = scorer.text_metrics(reference, prediction, sample['language'], eligible=True)
            for key in ('cer', 'character_edits', 'usable_page', 'prediction_characters', 'wer'):
                assert row[f'{prefix}_{key}'] == metric[key], (sample_id, variant, prefix, key)
            assert row['reference_characters'] == metric['reference_characters']
        assert row['cer_reduction'] == row['rapid_cer'] - row['reordered_cer']
        for field in ('changed', 'two_column_gate_passed', 'characters_unchanged', 'reason'):
            assert row[field] == output['trace'][field]
        assert row['postprocess_seconds'] == output['postprocess_seconds']
        checked.append({'sample_id': sample_id, 'variant': variant, 'output_sha256': sha(output_path)})
    with (HERE / 'rows.csv').open(newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(rows)
    for row, csv_row in zip(rows, csv_rows):
        assert {key: '' if value is None else str(value) for key, value in row.items()} == csv_row
    summary = json.loads((HERE / 'summary.json').read_text())
    assert summary['all'] == order._summarize(rows)
    for variant, values in summary['by_variant'].items():
        assert values == order._summarize([row for row in rows if row['variant'] == variant])
    for language, values in summary['by_language'].items():
        assert values == order._summarize([row for row in rows if row['language'] == language])
    result = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
        'cases_replayed': len(rows), 'metric_sets_recomputed': 3 * len(rows), 'character_multisets_preserved': len(rows),
        'new_ocr_calls': 0, 'new_model_calls': 0, 'input_hashes_verified': True,
        'frozen_configuration_and_source_snapshot_verified': True, 'csv_matches_json': True,
        'all_summary_groups_recomputed': True, 'verify_script_sha256': sha(Path(__file__)),
        'rows_sha256': sha(HERE / 'rows.json'), 'summary_sha256': sha(HERE / 'summary.json'),
        'outputs_verified': checked,
        'scope': 'Deterministic replay and scoring audit only. This is not an independent held-out experiment or additional OCR run.'}
    target = HERE / 'verification.json'
    if target.exists():
        raise ValueError('Refusing to overwrite the audit receipt.')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'outputs_verified'}, indent=2))


if __name__ == '__main__':
    main()
