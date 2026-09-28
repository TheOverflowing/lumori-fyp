"""Frozen image localization and additional table diagnostics across parsers."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_document_parsing import sha256
from scripts.evaluate_mineru_regions import match_regions
from scripts.parsing_teds import teds


def predicted_regions(directory):
    pictures, tables = [], []
    if (directory / 'middle_json.json').exists():
        doc = json.loads((directory / 'middle_json.json').read_text())
        for page in doc['pages']:
            for block in page['blocks']:
                if block['type'] in ('image', 'chart') and block.get('bbox'):
                    pictures.append(block['bbox'])
                if block['type'] == 'table':
                    for child in block.get('content', []):
                        if child['type'] == 'table_body' and child.get('bbox'):
                            tables.append({'bbox': child['bbox'], 'html': child.get('content', '')})
    else:
        for item in json.loads((directory / 'items.json').read_text()):
            for box in item['boxes']:
                if item['is_picture']:
                    pictures.append(box['bbox'])
                if item.get('table_html'):
                    tables.append({'bbox': box['bbox'], 'html': item['table_html']})
    return pictures, tables


def evaluate(run, manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    config = json.loads((run / 'configuration.json').read_text())
    assert sha256(manifest_path) == config['manifest_sha256']
    rows = []
    for strategy in config['strategies']:
        for variant in ('native_pdf', 'image_only_pdf'):
            for sample in manifest['samples']:
                annotation = manifest_path.parent / sample['annotation']
                assert sha256(annotation) == sample['annotation_sha256']
                doc = json.loads(annotation.read_text())
                w, h = doc['page_info']['width'], doc['page_info']['height']
                gold_pictures, gold_tables = [], []
                for block in doc['layout_dets']:
                    poly = block['poly']
                    box = [min(poly[::2])/w, min(poly[1::2])/h, max(poly[::2])/w, max(poly[1::2])/h]
                    if block['category_type'] == 'figure':
                        gold_pictures.append(box)
                    elif block['category_type'] == 'table' and block.get('html'):
                        gold_tables.append({'bbox': box, 'html': block['html']})
                stem = f'{strategy}--{sample["id"]}--{variant}'
                raw = json.loads((run / 'outputs' / (stem + '.json')).read_text())
                pictures, tables = ([], []) if raw['error'] else predicted_regions(run / 'outputs' / stem)
                matches = match_regions([t['bbox'] for t in gold_tables], [t['bbox'] for t in tables])
                matched = {m['gold']: m for m in matches}
                scores = []
                for i, gold in enumerate(gold_tables):
                    match = matched.get(i)
                    predicted = tables[match['prediction']]['html'] if match else ''
                    scores.append({'gold': i, 'match': match, 'teds_structure': teds(predicted, gold['html'], True),
                                   'teds_content': teds(predicted, gold['html'], False)})
                rows.append({'strategy': strategy, 'variant': variant, 'sample_id': sample['id'],
                             'failed': bool(raw['error']), 'gold_pictures': gold_pictures, 'predicted_pictures': pictures,
                             'picture_matches': match_regions(gold_pictures, pictures),
                             'gold_tables': gold_tables, 'predicted_tables': tables, 'table_scores': scores})
    summaries = []
    for strategy in config['strategies']:
        for variant in ('native_pdf', 'image_only_pdf'):
            selected = [r for r in rows if r['strategy'] == strategy and r['variant'] == variant]
            result = {'strategy': strategy, 'variant': variant, 'pages': len(selected)}
            for name in ('pictures', 'tables'):
                gold = sum(len(r['gold_' + name]) for r in selected)
                pred = sum(len(r['predicted_' + name]) for r in selected)
                found = sum(len(r['picture_matches']) if name == 'pictures' else sum(s['match'] is not None for s in r['table_scores']) for r in selected)
                result[name] = {'gold': gold, 'predicted': pred, 'matched': found,
                                'recall': found/gold if gold else None, 'precision': found/pred if pred and gold else None}
            scores = [s for r in selected for s in r['table_scores']]
            for metric in ('teds_structure', 'teds_content'):
                result[metric] = sum(s[metric] for s in scores)/len(scores) if scores else None
            summaries.append(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'manifest_sha256': sha256(manifest_path), 'source_sha256': sha256(Path(__file__)),
                                 'teds_source_sha256': sha256(ROOT/'scripts/parsing_teds.py'),
                                 'summary': summaries, 'rows': rows}, ensure_ascii=False, indent=2)+'\n')
    return summaries


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--manifest', type=Path, default=ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.run, args.manifest, args.output), indent=2))
