"""Reproducible local document parsing pilot, with explicit accuracy eligibility.

This is NOT the official OmniDocBench evaluator or leaderboard protocol.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_MANIFEST = ROOT / 'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
NORMALIZATION_VERSION = 'nfkc-whitespace-strip-case-sensitive-v1'


def normalize_text(text):
    return ''.join(unicodedata.normalize('NFKC', text).split())


def english_words(text):
    return re.findall(r'\w+|[^\w\s]', unicodedata.normalize('NFKC', text), re.UNICODE)


def edit_distance(reference, prediction):
    """Exact unit-cost Levenshtein, Myers bit-vector DP (Python arbitrary integers).

    Works for characters and word-token sequences without an optional C extension.
    """
    if not reference:
        return len(prediction)
    if not prediction:
        return len(reference)
    equality = {}
    for index, value in enumerate(reference):
        equality[value] = equality.get(value, 0) | (1 << index)
    positive, negative, score = ~0, 0, len(reference)
    high = 1 << (len(reference) - 1)
    for value in prediction:
        equal = equality.get(value, 0)
        delta = (((equal & positive) + positive) ^ positive) | equal | negative
        horizontal_positive = negative | ~(delta | positive)
        horizontal_negative = positive & delta
        if horizontal_positive & high:
            score += 1
        elif horizontal_negative & high:
            score -= 1
        horizontal_positive = (horizontal_positive << 1) | 1
        horizontal_negative <<= 1
        positive = horizontal_negative | ~(delta | horizontal_positive)
        negative = delta & horizontal_positive
    return score


def text_metrics(reference, prediction, language, eligible=True):
    reference_normalized, prediction_normalized = normalize_text(reference), normalize_text(prediction)
    result = {'reference_characters': len(reference_normalized),
              'prediction_characters': len(prediction_normalized),
              'nonempty_page': bool(prediction_normalized), 'cer_eligible': eligible,
              'character_edits': None, 'cer': None, 'wer': None, 'usable_page': None}
    if not eligible:
        return result
    if not reference_normalized:
        raise ValueError('Eligible accuracy samples require a nonempty reference.')
    result['character_edits'] = edit_distance(reference_normalized, prediction_normalized)
    result['cer'] = result['character_edits'] / len(reference_normalized)
    result['usable_page'] = result['cer'] <= .10 and len(prediction_normalized) >= .8 * len(reference_normalized)
    if language == 'english':
        reference_words, prediction_words = english_words(reference), english_words(prediction)
        result['reference_words'] = len(reference_words)
        result['word_edits'] = edit_distance(reference_words, prediction_words)
        result['wer'] = result['word_edits'] / len(reference_words)
    return result


def aggregate(rows):
    eligible = [row for row in rows if row['cer_eligible']]
    english = [row for row in eligible if row['wer'] is not None]
    return {
        'cases': len(rows), 'independent_source_pages': len({r['sample_id'] for r in rows}),
        'completed_without_exception': sum(r['completed_without_exception'] for r in rows),
        'nonempty_pages': sum(r['nonempty_page'] for r in rows),
        'nonempty_page_rate': sum(r['nonempty_page'] for r in rows) / len(rows) if rows else None,
        'accuracy_eligible_cases': len(eligible),
        'usable_pages': sum(r['usable_page'] for r in eligible),
        'usable_page_rate': sum(r['usable_page'] for r in eligible) / len(eligible) if eligible else None,
        'macro_cer': sum(r['cer'] for r in eligible) / len(eligible) if eligible else None,
        'micro_cer': sum(r['character_edits'] for r in eligible)
                     / sum(r['reference_characters'] for r in eligible) if eligible else None,
        'macro_english_wer': sum(r['wer'] for r in english) / len(english) if english else None,
        'mean_seconds_per_page': sum(r['elapsed_seconds'] for r in rows) / len(rows) if rows else None,
    }


def frozen_baseline(name, raw):
    """Original pypdf-only page extraction behavior, frozen before parser changes.

    read_document_pages returned empty PDF pages; downstream chunking then rejected
    all-empty documents. Both raw return and nonempty coverage are measured here.
    """
    from pypdf import PdfReader
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF unsupported in frozen baseline.')
        if len(reader.pages) > 300:
            raise ValueError('Page limit exceeded.')
        return [p.extract_text() or '' for p in reader.pages]
    if suffix in ('.txt', '.md'):
        return [raw.decode('utf-8-sig')]
    raise ValueError('Frozen baseline supports PDF, TXT and Markdown only.')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(manifest_path, output, strategies, variants, samples=None):
    from app.document_parsing import parse_document_structured
    from pypdf import __version__ as pypdf_version

    manifest_path, output = Path(manifest_path), Path(output)
    manifest = json.loads(manifest_path.read_text())
    if output.exists():
        raise ValueError('Refusing to overwrite an experiment; choose a new output directory.')
    output.mkdir(parents=True)
    (output / 'outputs').mkdir()
    versions = {'python': sys.version, 'platform': platform.platform(), 'pypdf': pypdf_version}
    for name, command in [('tesseract', ['tesseract', '--version']),
                          ('poppler', ['pdftotext', '-v'])]:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        versions[name] = (result.stdout + result.stderr).splitlines()[0]
    configuration = {
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'manifest_path': str(manifest_path.relative_to(ROOT)), 'manifest_sha256': sha256(manifest_path),
        'strategies': strategies, 'variants': variants, 'samples': samples,
        'normalization': NORMALIZATION_VERSION, 'metric_contract': manifest['metric_contract'],
        'execution': 'Sequential local calls; warm OS cache possible; one trial per case; includes '
            'rendering/OCR subprocess startup; asset extraction disabled to isolate recognition. '
            'No network or paid API calls. Timings are descriptive, not stable throughput claims.',
        'versions': versions,
        'source_hashes': {p: sha256(ROOT / p) for p in [
            'scripts/evaluate_document_parsing.py', 'scripts/prepare_parsing_benchmark.py',
            'app/document_parsing.py']},
        'limitations': ['Small purposive pilot, not an official OmniDocBench score or representative CS-course test.',
            'No table structure/formula/semantic figure accuracy is estimated.',
            'The same source across variants is paired, not independent new data.',
            'Native PDF source revision differs from annotation revision; same released page identifier.',
            'Reference text includes annotated headers/footers in annotated order; parser ordering affects CER.']}
    (output / 'configuration.json').write_text(json.dumps(configuration, ensure_ascii=False, indent=2) + '\n')
    rows = []
    for strategy in strategies:
        for sample in manifest['samples']:
            if samples and sample['id'] not in samples:
                continue
            reference_path = manifest_path.parent / sample['reference']
            if sha256(reference_path) != sample['reference_sha256']:
                raise ValueError('Ground-truth checksum mismatch.')
            reference = reference_path.read_text()
            for variant in variants:
                file_info = sample['files'][variant]
                path = manifest_path.parent / file_info['path']
                if sha256(path) != file_info['sha256']:
                    raise ValueError('Input checksum mismatch.')
                started = time.perf_counter()
                error, report, text = None, {}, ''
                completed = False
                try:
                    if strategy == 'pypdf_baseline_v0':
                        pages = frozen_baseline(path.name, path.read_bytes())
                        report = {'method': 'pypdf-extract-text-only-frozen-v0', 'page_count': len(pages)}
                    else:
                        parsed = parse_document_structured(path.name, path.read_bytes(), strategy=strategy,
                            ocr_languages='chi_sim+eng', max_ocr_pages=4,
                            preserve_visuals=False, timeout_seconds=120)
                        pages = parsed.text_pages
                        report = parsed.report()
                    if len(pages) != 1:
                        raise ValueError(f'Expected one benchmark page, received {len(pages)}.')
                    text = '\n'.join(pages)
                    completed = True
                except Exception as exception:
                    error = {'type': type(exception).__name__, 'message': str(exception)[:1000]}
                elapsed = time.perf_counter() - started
                row = {'sample_id': sample['id'], 'strategy': strategy, 'variant': variant,
                       'language': sample['language'], 'stratum': sample['stratum'],
                       'completed_without_exception': completed, 'elapsed_seconds': elapsed,
                       'error_type': error['type'] if error else None,
                       **text_metrics(reference, text, sample['language'], sample['cer_eligible'])}
                rows.append(row)
                result = {'case': row, 'prediction': text, 'report': report, 'error': error}
                result_path = output / 'outputs' / f'{strategy}--{sample["id"]}--{variant}.json'
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
                (output / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
                print(f'{strategy} {sample["id"]} {variant}: nonempty={row["nonempty_page"]} '
                      f'CER={row["cer"]} seconds={elapsed:.2f}', flush=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (output / 'rows.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summaries = []
    for strategy in strategies:
        for variant in variants:
            for language in ['all', 'english', 'simplified_chinese']:
                selected = [r for r in rows if r['strategy'] == strategy and r['variant'] == variant
                            and (language == 'all' or r['language'] == language)]
                summaries.append({'strategy': strategy, 'variant': variant, 'language': language,
                                  **aggregate(selected)})
    (output / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + '\n')
    with (output / 'summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    return summaries


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--strategies', nargs='+', default=['pypdf_baseline_v0', 'adaptive_local_v1'])
    parser.add_argument('--variants', nargs='+', default=['native_pdf', 'image_only_pdf', 'degraded_image'])
    parser.add_argument('--samples', nargs='+')
    args = parser.parse_args()
    evaluate(args.manifest, args.output, args.strategies, args.variants, args.samples)
