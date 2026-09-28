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
import itertools
import math
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


def wilson_interval(successes, trials, z=1.959963984540054):
    if not trials:
        return None
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0, center - margin), min(1, center + margin)]


def paired_cer_bootstrap(rows, reference_strategy, candidate_strategy, variant):
    """Exact enumeration of this pilot's 3-by-3 stratified bootstrap (729 draws).

    Resampling units are source pages and the same draws apply to both strategies.
    This exploratory interval does not turn a purposive sample into a population sample.
    """
    selected = {strategy: {r['sample_id']: r for r in rows if r['strategy'] == strategy
                         and r['variant'] == variant and r['cer_eligible']}
                for strategy in (reference_strategy, candidate_strategy)}
    left, right = selected[reference_strategy], selected[candidate_strategy]
    if set(left) != set(right) or not left:
        return None
    groups = []
    for language in ('english', 'simplified_chinese'):
        differences = [left[key]['cer'] - right[key]['cer']
                       for key in sorted(left) if left[key]['language'] == language]
        if len(differences) != 3:
            return None
        groups.append([sum(values) for values in itertools.product(differences, repeat=3)])
    distribution = sorted((first + second) / 6 for first in groups[0] for second in groups[1])
    return {'baseline': reference_strategy, 'candidate': candidate_strategy, 'variant': variant,
            'mean_cer_reduction': sum(left[k]['cer'] - right[k]['cer'] for k in left) / len(left),
            'percentile_interval_95': [distribution[math.floor(.025 * (len(distribution) - 1))],
                                       distribution[math.ceil(.975 * (len(distribution) - 1))]],
            'resampling': '729 exact paired bootstrap combinations; sample 3 English and 3 Chinese '
                          'source pages with replacement within language. Exploratory, no population or significance claim.'}


def summarize_experiment(output):
    output = Path(output)
    rows = json.loads((output / 'rows.json').read_text())
    config = json.loads((output / 'configuration.json').read_text())
    manifest = json.loads((ROOT / config['manifest_path']).read_text())
    if sha256(ROOT / config['manifest_path']) != config['manifest_sha256']:
        raise ValueError('Manifest has changed since this experiment.')
    summaries = []
    for strategy in config['strategies']:
        for variant in config['variants']:
            for language in ['all', 'english', 'simplified_chinese']:
                selected = [r for r in rows if r['strategy'] == strategy and r['variant'] == variant
                            and (language == 'all' or r['language'] == language)]
                result = {'strategy': strategy, 'variant': variant, 'language': language, **aggregate(selected)}
                result['usable_page_wilson_95'] = wilson_interval(result['usable_pages'], result['accuracy_eligible_cases'])
                summaries.append(result)
    intervals = [paired_cer_bootstrap(rows, 'pypdf_baseline_v0', strategy, variant)
                 for strategy in config['strategies'] if strategy != 'pypdf_baseline_v0'
                 for variant in config['variants']]
    statistics = {'scope': 'Small purposively selected pilot, not a random sample of CS-course materials. '
                  'Intervals indicate small-sample uncertainty only; model selection used this pilot, not an independent test set.',
                  'summaries': summaries, 'paired_cer_intervals': [v for v in intervals if v]}
    (output / 'statistics.json').write_text(json.dumps(statistics, ensure_ascii=False, indent=2) + '\n')
    domains = {}
    for sample in manifest['samples']:
        domain = sample['page_attributes']['data_source']
        domains[domain] = domains.get(domain, 0) + 1
    lines = ['# P1 文档解析实测记录', '',
        f'运行时间（UTC）：{config["started_at_utc"]}。实际保存 {len(rows)} 个解析输出。', '',
        '这是本机公开材料小样本实验，不是官方 OmniDocBench 分数。12 个不同源页面中，中英文各 6 页；'
        'CER 和工程合格率只评价其中的 6 页普通文字页面。每个输入类别的文字覆盖率则包含全部 12 页。', '',
        '领域分布：' + '；'.join(f'{name} {count} 页' for name, count in domains.items()) + '。不是完整计算机课程代表样本。', '',
        '工程合格规则在查看分数前固定：CER ≤ 10%，且输出非空白字符数 ≥ 参考答案的 80%。'
        '空白和异常记入分母。CER 保留大小写和标点，整页阅读顺序错误也计入。', '',
        '| 策略 | 输入 | 有文字/总页 | 工程合格/可评分页 | Macro CER | Micro CER | 秒/页 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for result in summaries:
        if result['language'] != 'all':
            continue
        lines.append(f'| {result["strategy"]} | {result["variant"]} | {result["nonempty_pages"]}/{result["cases"]} '
            f'| {result["usable_pages"]}/{result["accuracy_eligible_cases"]} '
            f'| {result["macro_cer"]:.2%} | {result["micro_cer"]:.2%} | {result["mean_seconds_per_page"]:.3f} |')
    lines += ['', '## 小样本不确定性', '',
        '6 页可评分文字中：' + '；'.join(f'{k}/6 的 Wilson 95% 参考区间为 '
            f'{wilson_interval(k,6)[0]:.1%}–{wilson_interval(k,6)[1]:.1%}' for k in range(7)) + '。', '',
        '这些区间只显示样本量很小，不能当成所有课程材料的总体保证。statistics.json 同时保留按语言分层、'
        '对同一源页面配对重采样的 Macro CER 差值区间；没有进行显著性或全球最优策略声明。', '',
        '## 解释边界与负面结果', '',
        '- 有文字并不代表文字正确。扫描 PDF 的文本覆盖率与 CER、工程合格率必须同时阅读。',
        '- `poppler_layout_v1` 保留视觉行布局，双栏串行化可能交错左右栏；直接替换原生 pypdf 文本存在阅读顺序退化。',
        '- `tesseract_psm6_v1` 假设单一文本块，复杂双栏页面可能比自动分页模式更差，不能统一启用。',
        '- 图表、公式样例只测执行和文字覆盖；结构和语义准确性未测量。图像边框、原图保存、识别置信度不是图像语义分数。',
        '- 降采样、旋转和 JPEG 是受控退化，不是真实手机拍照数据。',
        '- 每种组合只运行一次，包含子进程启动及可能的缓存影响。P1 同期另有软件 pytest 测试（含账号密码散列和少量 OCR 测试）运行，CPU 未保证空闲；这些墙钟时间仅为描述记录，不能据此做稳定吞吐或严格速度排名。',
        '- 初始 pypdf 环境未安装 fontTools，部分英文 CFF 字体发出可选依赖警告；保留真实基线，不静默补依赖后覆盖。', '',
        '## 证据与复现', '',
        '- configuration.json：运行配置、版本、数据和源代码散列。',
        '- source-snapshot/ 与 source-snapshot.json：实验时的代码副本与完整性记录。',
        '- runtime-identity.json：OCR 模型、可执行文件、训练语言数据与环境散列。',
        '- native-worker-integrity.json：运行期间资源边界修复前后的原生提取函数一致性说明；父解析器持有运行初始版本，原生子进程可能读取修复后的模块。',
        '- outputs/：每次调用的原始预测文本、解析报告与异常。',
        '- rows.json / rows.csv：逐页实际结果。summary.json / summary.csv：原始分组汇总。',
        '- statistics.json：追加的样本量、Wilson 区间和配对重采样区间。',
        '- 数据说明和使用条款在 ../../benchmarks/omnidocbench-pilot-v1/README.md。', '']
    (output / 'report.md').write_text('\n'.join(lines))
    return statistics


def audit_visual_retention(manifest_path, output):
    """Audit saved page previews, deliberately not figure-region/semantic recall."""
    from app.document_parsing import parse_document_structured
    manifest_path, output = Path(manifest_path), Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite a visual audit.')
    output.mkdir(parents=True)
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for sample in manifest['samples']:
        if not sample['category_counts'].get('figure'):
            continue
        info = sample['files']['native_pdf']
        path = manifest_path.parent / info['path']
        if sha256(path) != info['sha256']:
            raise ValueError('Visual audit source checksum mismatch.')
        parsed = parse_document_structured(path.name, path.read_bytes(), strategy='adaptive_local_v1',
                                            preserve_visuals=True, max_asset_pages=4, timeout_seconds=120)
        directory = output / sample['id']
        directory.mkdir()
        assets = []
        for asset in parsed.assets:
            suffix = '.png' if asset.mime_type == 'image/png' else '.jpg'
            file_path = directory / (asset.id + suffix)
            file_path.write_bytes(asset.data)
            assets.append({**asset.metadata(), 'path': str(file_path.relative_to(output))})
        (directory / 'report.json').write_text(json.dumps(parsed.report(), ensure_ascii=False, indent=2) + '\n')
        rows.append({'sample_id': sample['id'], 'source_sha256': info['sha256'],
                     'gold_figure_regions': sample['category_counts']['figure'],
                     'page_preview_saved': any(a['kind'] == 'page_preview' and a['byte_size'] > 0 for a in assets),
                     'embedded_raster_objects_saved': sum(a['kind'] == 'embedded_image' for a in assets),
                     'assets': assets})
    record = {'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'manifest_sha256': sha256(manifest_path), 'parser_sha256': sha256(ROOT / 'app/document_parsing.py'),
              'strategy': 'adaptive_local_v1', 'preserve_visuals': True, 'rows': rows,
              'figure_pages': len(rows), 'pages_with_saved_preview': sum(r['page_preview_saved'] for r in rows),
              'gold_figure_regions': sum(r['gold_figure_regions'] for r in rows),
              'figure_region_recall': None, 'figure_semantic_accuracy': None,
              'interpretation': 'A whole-page preview preserves a way to inspect visual evidence. '
                'PDF raster objects are not necessarily complete figures; vector figures need page rendering. '
                'No region-IoU matching or human semantic labels were used, so figure recall/meaning accuracy are unmeasured.'}
    (output / 'audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


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
    parser.add_argument('--summarize-existing', action='store_true')
    parser.add_argument('--audit-visuals', action='store_true')
    args = parser.parse_args()
    if args.audit_visuals:
        print(json.dumps(audit_visual_retention(args.manifest, args.output), ensure_ascii=False))
    elif args.summarize_existing:
        summarize_experiment(args.output)
    else:
        evaluate(args.manifest, args.output, args.strategies, args.variants, args.samples)
