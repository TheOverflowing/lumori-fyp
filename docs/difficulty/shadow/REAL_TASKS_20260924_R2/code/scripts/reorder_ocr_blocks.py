"""Experimental geometry-only reading order, isolated from production parsing.

P2 is a posthoc development ablation of saved P1 OCR lines. It makes no OCR,
model, network or application-provider calls. Geometric parameters are frozen
before scoring, and content/offset validation fails closed to the original text.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
from statistics import median
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_CONFIG = ROOT / 'docs/parsing/experiments/P2-reading-order-20260918/configuration.json'


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def digest_text(value):
    return digest_bytes(value.encode('utf-8'))


def _finite_positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def reorder_page(page, config):
    """Return unchanged text or a permutation of exact OCR lines and whitespace.

    Character spans must account for every non-whitespace character. Prefix,
    suffix and inter-line whitespace segments retain their exact positional
    sequence. No confidence score, language feature or reference is consulted.
    """
    original = page.get('text', '')
    blocks = page.get('blocks') or []
    original_order = list(range(len(blocks)))
    trace = {'algorithm_version': config['algorithm_version'], 'block_count': len(blocks),
             'original_order': original_order, 'input_text_sha256': digest_text(original),
             'candidate_diagnostics': []}

    def finish(order, reason, accepted=False):
        if order == original_order:
            prediction = original
        else:
            prediction = prefix + ''.join(blocks[index]['text'] + gaps[position]
                                          for position, index in enumerate(order))
        if sorted(order) != original_order or Counter(prediction) != Counter(original):
            raise AssertionError('Permutation or exact character preservation failed.')
        trace.update({'reason': reason, 'two_column_gate_passed': accepted,
                      'order_indices': order, 'changed': order != original_order,
                      'characters_unchanged': Counter(prediction) == Counter(original),
                      'output_text_sha256': digest_text(prediction),
                      'input_characters': len(original), 'output_characters': len(prediction)})
        return {'text': prediction, 'trace': trace}

    if not blocks:
        return finish(original_order, 'no_ocr_blocks')
    width = page.get('metrics', {}).get('ocr_image_width')
    height = page.get('metrics', {}).get('ocr_image_height')
    if not _finite_positive(width) or not _finite_positive(height):
        return finish(original_order, 'missing_or_invalid_raster_dimensions')
    geometry = []
    last_end = 0
    for index, block in enumerate(blocks):
        if block.get('kind') != 'ocr_line' or block.get('coordinate_system') != 'image_pixels_top_left':
            return finish(original_order, 'unsupported_block_geometry')
        bbox = block.get('bbox')
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return finish(original_order, 'invalid_bbox')
        if not all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in bbox):
            return finish(original_order, 'invalid_bbox')
        left, top, line_width, line_height = bbox
        if left < 0 or top < 0 or line_width <= 0 or line_height <= 0 or left + line_width > width or top + line_height > height:
            return finish(original_order, 'bbox_outside_raster')
        start, end = block.get('char_start'), block.get('char_end')
        if (type(start) is not int or type(end) is not int or start < last_end or end <= start
                or end > len(original) or original[start:end] != block.get('text')):
            return finish(original_order, 'invalid_or_mismatched_text_spans')
        if original[last_end:start].strip():
            return finish(original_order, 'untracked_nonwhitespace_text')
        last_end = end
        geometry.append({'index': index, 'left': left / width, 'right': (left + line_width) / width,
                         'top': top / height, 'bottom': (top + line_height) / height,
                         'width': line_width / width, 'height': line_height / height})
    if original[last_end:].strip():
        return finish(original_order, 'untracked_nonwhitespace_text')
    prefix = original[:blocks[0]['char_start']]
    gaps = [original[block['char_end']:blocks[index + 1]['char_start']]
            if index + 1 < len(blocks) else original[block['char_end']:]
            for index, block in enumerate(blocks)]
    trace['normalized_geometry'] = geometry
    trace['whitespace_segment_sha256'] = [digest_text(prefix), *[digest_text(gap) for gap in gaps]]
    trace['selection_rule'] = 'Fewest crossing blocks, then most lines in smaller column, then nearest page center, then lower cut.'
    half_gutter = config['gutter_width_fraction'] / 2
    accepted = []
    for cut in config['candidate_cut_fractions']:
        left = [g for g in geometry if g['right'] <= cut - half_gutter]
        right = [g for g in geometry if g['left'] >= cut + half_gutter]
        crossing = [g for g in geometry if g not in left and g not in right]
        balance = min(len(left), len(right)) / max(len(left), len(right)) if left or right else 0
        left_width = median(g['width'] for g in left) if left else 0
        right_width = median(g['width'] for g in right) if right else 0
        overlap = 0
        if left and right:
            ltop, lbottom = min(g['top'] for g in left), max(g['bottom'] for g in left)
            rtop, rbottom = min(g['top'] for g in right), max(g['bottom'] for g in right)
            overlap = max(0, min(lbottom, rbottom) - max(ltop, rtop)) / min(lbottom - ltop, rbottom - rtop)
        checks = {'enough_lines': min(len(left), len(right)) >= config['minimum_lines_per_column'],
                  'balanced_columns': balance >= config['minimum_column_balance'],
                  'wide_enough_lines': min(left_width, right_width) >= config['minimum_median_line_width_fraction'],
                  'overlapping_vertical_spans': overlap >= config['minimum_vertical_overlap_fraction'],
                  'mostly_noncrossing': len(crossing) / len(geometry) <= config['maximum_crossing_fraction']}
        trace['candidate_diagnostics'].append({'cut_fraction': cut, 'left_lines': len(left),
            'right_lines': len(right), 'crossing_lines': len(crossing), 'column_balance': balance,
            'left_median_width': left_width, 'right_median_width': right_width,
            'vertical_overlap': overlap, 'checks': checks, 'accepted': all(checks.values())})
        if all(checks.values()):
            accepted.append((len(crossing), -min(len(left), len(right)), abs(cut - .5), cut, left, right, crossing))
    if not accepted:
        return finish(original_order, 'no_confident_two_column_gutter')
    _, _, _, cut, left, right, crossing = min(accepted, key=lambda item: item[:4])
    trace['selected_cut_fraction'] = cut
    padding = config['anchor_band_padding_line_heights'] * median(g['height'] for g in geometry)
    bands = []
    for item in sorted(crossing, key=lambda g: (g['top'], g['left'], g['index'])):
        top, bottom = max(0, item['top'] - padding), min(1, item['bottom'] + padding)
        if bands and top <= bands[-1]['bottom']:
            bands[-1]['bottom'] = max(bottom, bands[-1]['bottom'])
            bands[-1]['crossing_indices'].append(item['index'])
        else:
            bands.append({'top': top, 'bottom': bottom, 'crossing_indices': [item['index']]})
    band_blocks = [[] for _ in bands]
    intervals = [{'left': [], 'right': []} for _ in range(len(bands) + 1)]
    side_by_index = {g['index']: side for side, group in [('left', left), ('right', right)] for g in group}
    for item in geometry:
        overlaps = [(min(item['bottom'], band['bottom']) - max(item['top'], band['top']), index)
                    for index, band in enumerate(bands)]
        positive = [pair for pair in overlaps if pair[0] > 0]
        if positive:
            _, band_index = max(positive, key=lambda pair: (pair[0], -pair[1]))
            band_blocks[band_index].append(item)
        else:
            if item['index'] not in side_by_index:
                raise AssertionError('Crossing block lost its anchor band.')
            interval = sum(item['top'] >= band['bottom'] for band in bands)
            intervals[interval][side_by_index[item['index']]].append(item)
    order = []
    sort_key = lambda g: (g['top'], g['left'], g['index'])
    for index, interval in enumerate(intervals):
        for side in ('left', 'right'):
            order.extend(g['index'] for g in sorted(interval[side], key=sort_key))
        if index < len(bands):
            band_order = [g['index'] for g in sorted(band_blocks[index], key=sort_key)]
            bands[index]['all_indices'] = band_order
            order.extend(band_order)
    trace['anchor_bands'] = bands
    return finish(order, 'geometry_two_column_order', accepted=True)


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _summarize(rows):
    result = {'cases': len(rows), 'independent_source_pages': len({r['sample_id'] for r in rows}),
              'reordered_cases': sum(r['changed'] for r in rows),
              'geometry_gate_passed': sum(r['two_column_gate_passed'] for r in rows),
              'all_characters_unchanged': all(r['characters_unchanged'] for r in rows),
              'improved_cases': sum(r['reordered_cer'] < r['rapid_cer'] for r in rows),
              'worse_cases': sum(r['reordered_cer'] > r['rapid_cer'] for r in rows),
              'unchanged_cer_cases': sum(r['reordered_cer'] == r['rapid_cer'] for r in rows),
              'mean_postprocess_seconds': sum(r['postprocess_seconds'] for r in rows) / len(rows)}
    for prefix in ('rapid', 'reordered', 'psm6'):
        result[prefix + '_macro_cer'] = sum(r[prefix + '_cer'] for r in rows) / len(rows)
        result[prefix + '_micro_cer'] = sum(r[prefix + '_character_edits'] for r in rows) / sum(r['reference_characters'] for r in rows)
        result[prefix + '_usable_pages'] = sum(r[prefix + '_usable_page'] for r in rows)
    result['macro_cer_reduction'] = result['rapid_macro_cer'] - result['reordered_macro_cer']
    return result


def run(config_path):
    config_path = Path(config_path).resolve()
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    output = config_path.parent
    if any((output / name).exists() for name in ['freeze.json', 'rows.json', 'outputs', 'source-snapshot']):
        raise ValueError('Refusing to overwrite an existing experiment; use a new directory/config.')
    source_files = [Path(__file__).resolve(), ROOT / 'scripts/evaluate_document_parsing.py',
                    ROOT / 'tests/test_ocr_reading_order.py']
    snapshot = output / 'source-snapshot'
    snapshot.mkdir()
    source_hashes = {}
    for path in source_files:
        data = path.read_bytes()
        (snapshot / path.name).write_bytes(data)
        source_hashes[str(path.relative_to(ROOT))] = digest_bytes(data)
    # This record is durable before reading any reference or computing any P2 metric.
    _write_json(output / 'freeze.json', {'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'configuration_sha256': digest_bytes(config_bytes), 'source_sha256': source_hashes,
        'python': sys.version, 'platform': platform.platform(), 'new_ocr_calls': 0, 'new_model_calls': 0,
        'sequence': 'Configuration and source snapshot frozen before loading reference text or calculating reordered CER.'})
    outputs = output / 'outputs'
    outputs.mkdir()
    inputs = ROOT / config['input_experiment'] / 'outputs'
    prepared = []
    for sample_id in config['scored_sample_ids']:
        for variant in config['variants']:
            source_path = inputs / f'rapidocr_v1--{sample_id}--{variant}.json'
            source_bytes = source_path.read_bytes()
            source = json.loads(source_bytes)
            if source.get('error') or not source['case']['completed_without_exception']:
                raise ValueError(f'Incomplete or failed source: {source_path.name}')
            pages = source['report']['pages']
            if len(pages) != 1 or source['prediction'] != pages[0]['text']:
                raise ValueError('P2 pilot requires one page with prediction exactly equal to saved page text.')
            start = time.perf_counter()
            result = reorder_page(pages[0], config)
            elapsed = time.perf_counter() - start
            record = {'sample_id': sample_id, 'variant': variant,
                      'input_path': str(source_path.relative_to(ROOT)), 'input_sha256': digest_bytes(source_bytes),
                      'postprocess_seconds': elapsed, 'original_prediction': source['prediction'],
                      'prediction': result['text'], 'trace': result['trace']}
            filename = f'geometry_two_column_v1--{sample_id}--{variant}.json'
            _write_json(outputs / filename, record)
            prepared.append(record)
    # Scoring is a separate phase: all reordered predictions already exist on disk.
    from scripts.evaluate_document_parsing import NORMALIZATION_VERSION, text_metrics
    manifest_path = ROOT / config['manifest_path']
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    sample_by_id = {sample['id']: sample for sample in manifest['samples']}
    rows, hashes = [], []
    for record in prepared:
        sample_id, variant = record['sample_id'], record['variant']
        sample = sample_by_id[sample_id]
        if not sample['cer_eligible']:
            raise ValueError('P2 must not score non-prose samples.')
        reference_path = manifest_path.parent / sample['reference']
        reference_bytes = reference_path.read_bytes()
        if digest_bytes(reference_bytes) != sample['reference_sha256']:
            raise ValueError('Reference hash does not match manifest.')
        reference = reference_bytes.decode('utf-8')
        psm6_path = inputs / f'tesseract_psm6_v1--{sample_id}--{variant}.json'
        psm6_bytes = psm6_path.read_bytes()
        psm6 = json.loads(psm6_bytes)
        if psm6.get('error') or not psm6['case']['completed_without_exception']:
            raise ValueError(f'Incomplete PSM6 comparator: {psm6_path.name}')
        metrics = {prefix: text_metrics(reference, prediction, sample['language'], eligible=True)
                   for prefix, prediction in [('rapid', record['original_prediction']),
                       ('reordered', record['prediction']), ('psm6', psm6['prediction'])]}
        row = {'sample_id': sample_id, 'language': sample['language'], 'variant': variant,
               'reference_characters': metrics['rapid']['reference_characters'],
               'changed': record['trace']['changed'],
               'two_column_gate_passed': record['trace']['two_column_gate_passed'],
               'reason': record['trace']['reason'],
               'selected_cut_fraction': record['trace'].get('selected_cut_fraction'),
               'characters_unchanged': record['trace']['characters_unchanged'],
               'postprocess_seconds': record['postprocess_seconds']}
        for prefix, values in metrics.items():
            for key in ('cer', 'character_edits', 'usable_page', 'prediction_characters', 'wer'):
                row[f'{prefix}_{key}'] = values[key]
        row['cer_reduction'] = row['rapid_cer'] - row['reordered_cer']
        rows.append(row)
        hashes.append({'sample_id': sample_id, 'variant': variant,
                       'rapid_input_sha256': record['input_sha256'],
                       'psm6_input_sha256': digest_bytes(psm6_bytes),
                       'reference_path': str(reference_path.relative_to(ROOT)), 'reference_sha256': digest_bytes(reference_bytes)})
    _write_json(output / 'rows.json', rows)
    with (output / 'rows.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {'all': _summarize(rows),
        'by_variant': {variant: _summarize([r for r in rows if r['variant'] == variant]) for variant in config['variants']},
        'by_language': {lang: _summarize([r for r in rows if r['language'] == lang]) for lang in sorted({r['language'] for r in rows})},
        'limitations': 'Posthoc development ablation on 6 purposively selected source pages; 18 paired variants are not independent sources. No held-out/general-best/production-promotion claim.',
        'new_ocr_calls': 0, 'new_model_calls': 0}
    _write_json(output / 'summary.json', summary)
    _write_json(output / 'input-integrity.json', {'manifest_sha256': digest_bytes(manifest_bytes),
        'normalization_version': NORMALIZATION_VERSION, 'input_cases': hashes,
        'scoring_finished_at_utc': datetime.now(timezone.utc).isoformat()})
    report = ['# P2：OCR 阅读顺序的几何后处理消融', '',
        '**这是看到 P1 双栏交错问题后开展的开发集消融实验，不是独立测试集结果。** '
        '6 个源页面（中英文各 3 页）各有 3 种输入，共 18 个配对观测；18 个变体不能当成 18 个独立页面。', '',
        '本轮重用 P1 保存的 RapidOCR 像素框、文字和坐标，不调用 OCR、不调用模型、也不请求外部 API。'
        '调整的只有整页文字的串行顺序；字母、汉字、标点、空白等字符的多重集合逐页保持完全一致。', '',
        '## 固定的几何规则', '',
        '在页面宽度 40%–60% 的固定候选切线上寻找 2% 宽的垂直栏间空隙。两侧至少各 4 行，'
        '较少/较多一侧的行数至少为 0.35；两侧行宽中位数至少为页宽的 15%；'
        '纵向跨度重叠至少为较短跨度的 50%；跨线框不超过总数的 25%。'
        '在合格候选中依次选择跨线框最少、较少一栏行数最多、最接近页中心、横坐标较小的切线。', '',
        '跨线标题/页眉/页脚形成锚点带（上下扩展半个中位行高），合并重叠锚点带并吸收纵向重叠的侧边行。'
        '锚点带内按上坐标、左坐标、原索引排序；两带之间先完整读左栏，再读右栏。'
        '缺少坐标、坐标越界、文字偏移不匹配、存在未计入框的非空白文字、或双栏判据不满足时，'
        '保留原始文本和顺序。无语言规则、关键词、置信度或参考答案参与判定。', '',
        f'参数配置 SHA256：`{digest_bytes(config_bytes)}`。`freeze.json` 与 `source-snapshot/` '
        '在读取参考文本、计算任何重排 CER 前写入；所有 18 个新预测也先于评分阶段生成。', '',
        '## 结果', '',
        'CER 越低越好；Macro CER 为逐页 CER 的均值，Micro CER 为总编辑数/总参考字符数。'
        '使用与 P1 相同的 NFKC、去空白、大小写敏感比较。工程合格代理定义为 CER ≤ 10% 且输出字符数至少为参考的 80%，不是人工可用性判断。', '',
        '| 输入（每类 6 页） | 原始 RapidOCR Macro CER | 几何重排 Macro CER | 减少（百分点） | Tesseract PSM6 Macro CER | 原始→重排工程合格 |',
        '|---|---:|---:|---:|---:|---:|']
    for variant, values in summary['by_variant'].items():
        report.append(f'| {variant} | {values["rapid_macro_cer"]:.2%} | {values["reordered_macro_cer"]:.2%} '
            f'| {100 * values["macro_cer_reduction"]:.2f} | {values["psm6_macro_cer"]:.2%} '
            f'| {values["rapid_usable_pages"]}/6 → {values["reordered_usable_pages"]}/6 |')
    overall = summary['all']
    report += ['', f'18 个变体中，{overall["geometry_gate_passed"]} 个通过双栏判据，'
        f'{overall["reordered_cases"]} 个实际改变顺序；CER 改善 {overall["improved_cases"]} 个，'
        f'退化 {overall["worse_cases"]} 个，不变 {overall["unchanged_cer_cases"]} 个。'
        f'18/18 字符多重集合一致。后处理单次平均 {overall["mean_postprocess_seconds"] * 1000:.3f} ms/页，'
        '仅是本次几何函数墙钟时间，不包括 OCR/加载/评分，不是端到端速度基准。', '',
        '| 语言（各 3 个源页 × 3 种变体） | 原始 RapidOCR Macro CER | 重排 Macro CER | PSM6 Macro CER |',
        '|---|---:|---:|---:|']
    for lang, values in summary['by_language'].items():
        report.append(f'| {lang} | {values["rapid_macro_cer"]:.2%} | {values["reordered_macro_cer"]:.2%} | {values["psm6_macro_cer"]:.2%} |')
    report += ['', '## 解释与限制', '',
        '- CER 变化来自相同 OCR 字符的排列变化，不能解释为字符识别模型本身变准确，也不能用置信度代替真实识别准确率。',
        '- 参数未按本轮分数调优，但实验选题已受到 P1 错误观察影响，仍属于事后开发集分析。需要单独冻结并标注的新课程材料测试集才能验证泛化。',
        '- 规则只覆盖满足判据的近似双栏文字。三栏、复杂跨栏、图表、边注、倾斜/透视和页面混合布局可能失败或回退；保留原序也不保证原序正确。',
        '- 坐标和原始 OCR 输出来自 P1，数据来源与使用条款沿用 P1。没有为图表、公式或照片语义提供准确率；这里的 degraded_image 是受控退化。',
        '- Tesseract PSM6 比较使用相同输入、相同参考和同一评分器的已存结果；没有在本轮重新运行，因此不能依据本轮后处理耗时作 OCR 速度排名。',
        '- 不声明全球最强；没有改动生产解析器或自动切换默认策略。下一步应在新的单栏/双栏/混合布局课程页上固定规则测试，并另评阅读顺序而非只有整页 CER。', '',
        '## 复现与审计', '',
        '- `configuration.json`：评分前固定的参数；`freeze.json`：冻结时间、代码散列。',
        '- `source-snapshot/`：本轮排序器、评分器及测试的执行前副本。',
        '- `outputs/`：18 份原文、新文、候选切线判断、锚点带与块索引置换；含输入/输出散列与字符库存检查。',
        '- `input-integrity.json`：P1 原始输出、PSM6 对照、参考文件与 manifest 散列。',
        '- `rows.json` / `rows.csv`：逐例配对结果；`summary.json`：总体及按语言/输入类型汇总。',
        '- 若重跑，先将参数复制到一个新的实验目录，再运行 '
        '`python scripts/reorder_ocr_blocks.py --config 新目录/configuration.json`。原结果目录禁止覆盖。', '']
    (output / 'report.md').write_text('\n'.join(report), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config), ensure_ascii=False, indent=2))
