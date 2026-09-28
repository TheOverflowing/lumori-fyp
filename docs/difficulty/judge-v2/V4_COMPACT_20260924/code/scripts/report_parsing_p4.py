"""Audit saved predictions and build the P4 comparison; never invokes inference."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
import csv
import json
import random
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_document_parsing import text_metrics, sha256, aggregate
from scripts.evaluate_parsing_structures import evaluate as structure_evaluate

P4 = ROOT/'docs/parsing/experiments/P4-candidate-expansion-20260918'
DEV = ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
CONF = ROOT/'docs/parsing/benchmarks/omnidocbench-confirmation-v1/manifest.json'
NAMES = {'adaptive_local_v1': 'P1 adaptive（冻结基线）', 'mineru_4_0_2_basic_onnx': 'MinerU Basic',
         'mineru_4_0_2_standard_onnx': 'MinerU Standard', 'mineru_4_0_2_advanced_onnx': 'MinerU Advanced',
         'docling_2_128_tesseract_tableformer_v2': 'Docling + Tesseract + TableFormerV2',
         'docling_2_128_granite_258m_mlx': 'GraniteDocling 258M MLX', 'paddleocr_3_7_vl16_mlx': 'PaddleOCR-VL 1.6 MLX',
         'paddleocr_3_7_vl16_mlx_unmerged': 'PaddleOCR-VL 1.6（不合并块）',
         'paddleocr_3_7_vl16_mlx_unmerged_xycut': 'PaddleOCR-VL 1.6 + 几何阅读顺序'}
VARIANTS = ['native_pdf', 'image_only_pdf', 'degraded_image']


def load(run, manifest_path, strategies=None):
    config = json.loads((run/'configuration.json').read_text())
    assert config['manifest_sha256'] == sha256(manifest_path)
    samples = {s['id']: s for s in json.loads(manifest_path.read_text())['samples']}
    rows = json.loads((run/'rows.json').read_text())
    if config.get('inference_source_run'):
        parent = ROOT/config['inference_source_run']
        assert sha256(parent/'rows.json') == config['inference_source_rows_sha256']
    if strategies:
        rows = [r for r in rows if r['strategy'] in strategies]
    seen = set()
    for row in rows:
        key = (row['strategy'], row['sample_id'], row['variant']); assert key not in seen; seen.add(key)
        sample = samples[row['sample_id']]
        stem = '--'.join(key)
        raw = json.loads((run/'outputs'/(stem+'.json')).read_text())
        assert raw['case'] == row
        reference = manifest_path.parent/sample['reference']
        assert sha256(reference) == sample['reference_sha256']
        input_info = sample['files'][row['variant']]
        assert sha256(manifest_path.parent/input_info['path']) == input_info['sha256']
        if 'input_sha256' in raw:
            assert raw['input_sha256'] == input_info['sha256']
        if raw['error']:
            assert raw['prediction'] == ''
        elif raw.get('inference_source'):
            original = json.loads((ROOT/raw['inference_source']/'items.json').read_text())
            derived = json.loads((run/'outputs'/stem/'items.json').read_text())
            assert Counter(json.dumps(i, sort_keys=True) for i in original) == Counter(json.dumps(i, sort_keys=True) for i in derived)
        measured = text_metrics(reference.read_text(), raw['prediction'], row['language'], sample['cer_eligible'])
        for name, value in measured.items():
            assert value == row[name], (stem, name, value, row[name])
    assert len(rows) == len(samples)*3*len({r['strategy'] for r in rows})
    for source, digest in config.get('source_sha256', config.get('source_hashes', {})).items():
        assert sha256(run/'source-snapshot'/source) == digest
    return rows


def summaries(rows, split):
    result = []
    for strategy in dict.fromkeys(r['strategy'] for r in rows):
        for variant in ['all']+VARIANTS:
            for language in ['all', 'english', 'simplified_chinese']:
                selected = [r for r in rows if r['strategy'] == strategy and (variant == 'all' or r['variant'] == variant)
                            and (language == 'all' or r['language'] == language)]
                result.append({'split': split, 'strategy': strategy, 'variant': variant, 'language': language, **aggregate(selected)})
    return result


def interval(rows, baseline, challenger):
    # The source page is the sampling unit; its three paired conditions stay together.
    pages = defaultdict(dict)
    for strategy in (baseline, challenger):
        for row in rows:
            if row['strategy'] == strategy and row['cer_eligible']:
                pages[strategy].setdefault((row['language'], row['sample_id']), []).append(row['cer'])
    assert pages[baseline].keys() == pages[challenger].keys()
    differences = defaultdict(list)
    for key in sorted(pages[baseline]):
        assert len(pages[baseline][key]) == len(pages[challenger][key]) == 3
        differences[key[0]].append(statistics.mean(pages[baseline][key])-statistics.mean(pages[challenger][key]))
    rng = random.Random(20260918)
    draws = sorted(statistics.mean(statistics.mean(rng.choices(values, k=len(values)))
                                   for values in differences.values()) for _ in range(20000))
    return {'baseline': baseline, 'challenger': challenger,
            'mean_cer_reduction': statistics.mean(statistics.mean(v) for v in differences.values()),
            'percentile_interval_95': [draws[499], draws[19499]], 'draws': 20000, 'seed': 20260918,
            'unit': 'paired source-page clusters; all three conditions together; resample within language',
            'scope': 'Exploratory sample uncertainty, not population significance; public benchmark may occur in model training.'}


def table(rows):
    lines = ['| 策略 | 完成/尝试 | 有文字/尝试 | 原始 PDF CER | 扫描 PDF CER | 退化图 CER | 三条件平均 CER | 初筛达标/可评分调用 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for strategy in dict.fromkeys(r['strategy'] for r in rows):
        selected = [r for r in rows if r['strategy'] == strategy]
        values = [aggregate([r for r in selected if r['variant'] == v])['macro_cer'] for v in VARIANTS]
        overall = aggregate(selected)
        lines.append(f'| {NAMES[strategy]} | {overall["completed_without_exception"]}/{len(selected)} | {overall["nonempty_pages"]}/{len(selected)} | '+
                     ' | '.join(f'{v:.2%}' for v in values)+f' | {overall["macro_cer"]:.2%} | {overall["usable_pages"]}/{overall["accuracy_eligible_cases"]} |')
    return lines


def paired_cases(rows, comparisons):
    """Retain all paired cases, including ties/regressions; no oracle routing."""
    by_key = {(r['strategy'], r['sample_id'], r['variant']): r for r in rows if r['cer_eligible']}
    result = []
    for baseline, candidate in comparisons:
        keys = sorted((sample, variant) for strategy, sample, variant in by_key if strategy == baseline)
        for sample, variant in keys:
            a, b = by_key[(baseline, sample, variant)], by_key[(candidate, sample, variant)]
            delta = a['cer'] - b['cer']
            result.append({'baseline': baseline, 'candidate': candidate, 'sample_id': sample,
                           'variant': variant, 'language': a['language'], 'baseline_cer': a['cer'],
                           'candidate_cer': b['cer'], 'cer_reduction': delta,
                           'outcome': 'improved' if delta > 1e-12 else 'regressed' if delta < -1e-12 else 'tied'})
    (P4/'confirmation/paired-cases.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    with (P4/'confirmation/paired-cases.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0])); writer.writeheader(); writer.writerows(result)
    return result


def local_vlm_statistics():
    result = []
    for directory in [P4/'runs/paddle-mlx', P4/'runs/paddle-unmerged', P4/'confirmation/challenger', P4/'confirmation/geometry-raw']:
        for path in sorted(directory.glob('outputs/*/server.log')):
            requests = []
            for line in path.read_text(errors='replace').splitlines():
                if 'Request completed:' not in line:
                    continue
                values = dict(re.findall(r'(prompt_tokens|generated_tokens|elapsed|finish_reason)=([^ ]+)', line))
                requests.append(values)
            result.append({'case_path': str(path.parent.relative_to(P4)),
                           'completed_requests_with_log': len(requests),
                           'prompt_tokens_logged': sum(int(r.get('prompt_tokens', 0)) for r in requests),
                           'generated_tokens_logged': sum(int(r.get('generated_tokens', 0)) for r in requests),
                           'length_capped_requests_logged': sum(r.get('finish_reason') == 'length' for r in requests),
                           'clean_shutdown_logged': 'Finished server process' in path.read_text(errors='replace')})
    (P4/'local-vlm-usage.json').write_text(json.dumps({'scope': 'Completed PaddleOCR local MLX server requests with logs only; excludes MinerU/Granite calls. Interrupted/unlogged requests are not imputed. Token counts are server-reported, not cross-model comparable. No paid provider calls.',
                                                    'cases': result}, indent=2)+'\n')


def main():
    sources = [('p1-adaptive', ROOT/'docs/parsing/experiments/P1-baseline-adaptive-20260918', ['adaptive_local_v1']),
               ('p3-basic', ROOT/'docs/parsing/experiments/P3-mineru-20260918/runs/basic', None),
               ('p3-standard', ROOT/'docs/parsing/experiments/P3-mineru-20260918/runs/standard', None)]
    sources += [(name, P4/'runs'/name, None) for name in ('advanced', 'docling-tess', 'granite-mlx', 'paddle-mlx', 'paddle-unmerged', 'paddle-xycut')]
    development, confirmation, structures, audited = [], [], {}, []
    for name, run, allowed in sources:
        rows = load(run, DEV, allowed); development.extend(rows)
        audited.append({'split': 'development', 'run': str(run.relative_to(ROOT)), 'rows': len(rows), 'rows_sha256': sha256(run/'rows.json'),
                        'record_type': 'ordering_replay' if name == 'paddle-xycut' else 'inference'})
        if name != 'p1-adaptive':
            structures[name] = structure_evaluate(run, DEV, P4/'structures'/(name+'.json'))
    for name in ('adaptive', 'standard', 'challenger', 'geometry'):
        run = P4/'confirmation'/name
        rows = load(run, CONF); confirmation.extend(rows)
        audited.append({'split': 'confirmation', 'run': str(run.relative_to(ROOT)), 'rows': len(rows), 'rows_sha256': sha256(run/'rows.json'),
                        'record_type': 'ordering_replay' if name == 'geometry' else 'inference'})
        if name != 'adaptive':
            structures['confirmation-'+name] = structure_evaluate(run, CONF, P4/'structures'/('confirmation-'+name+'.json'))
    final = json.loads((P4/'confirmation/frozen-finalists.json').read_text())
    local_vlm_statistics()
    challenger = final['challenger']['strategy']
    uncertainty = interval(confirmation, 'mineru_4_0_2_standard_onnx', challenger)
    geometry_id = 'paddleocr_3_7_vl16_mlx_unmerged_xycut'
    geometry_uncertainty = interval(confirmation, 'mineru_4_0_2_standard_onnx', geometry_id)
    finalist_uncertainty = interval(confirmation, challenger, geometry_id)
    geometry_evidence = json.loads((P4/'confirmation/geometry-evidence.json').read_text())
    geometry_parent = ROOT/geometry_evidence['inference_source']
    geometry_raw = load(geometry_parent, CONF)
    if geometry_parent != P4/'confirmation/challenger':
        audited.append({'split': 'confirmation-raw', 'run': str(geometry_parent.relative_to(ROOT)), 'rows': len(geometry_raw),
                        'rows_sha256': sha256(geometry_parent/'rows.json'), 'record_type': 'inference'})
    geometry_rows = [r for r in confirmation if r['strategy'] == geometry_id]
    ordering_effect = interval(geometry_raw+geometry_rows, 'paddleocr_3_7_vl16_mlx_unmerged', geometry_id)
    comparisons = [('adaptive_local_v1', 'mineru_4_0_2_standard_onnx'),
                   ('mineru_4_0_2_standard_onnx', challenger), ('mineru_4_0_2_standard_onnx', geometry_id)]
    paired = paired_cases(confirmation, comparisons)
    summary = summaries(development, 'development')+summaries(confirmation, 'confirmation')
    (P4/'comparison.json').write_text(json.dumps({'summary': summary, 'confirmation_interval': uncertainty,
                                               'geometry_confirmation_interval': geometry_uncertainty, 'paired_ordering_effect': ordering_effect,
                                               'additional_finalist_interval': finalist_uncertainty,
                                               'structures': structures}, ensure_ascii=False, indent=2)+'\n')
    with (P4/'comparison.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0])); writer.writeheader(); writer.writerows(summary)
    (P4/'audit.json').write_text(json.dumps({'verified_at_utc': datetime.now(timezone.utc).isoformat(),
                                         'checks': ['input/ref hashes', 'complete unique case grid', 'raw prediction metric replay',
                                                    'failures retained as empty prediction', 'run source snapshots'],
                                         'runs': audited, 'all_passed': True,
                                         'new_p4_inference_cases': sum(r['rows'] for r in audited if r['record_type']=='inference' and r['run'].startswith(str(P4.relative_to(ROOT)))),
                                         'ordering_replay_cases': sum(r['rows'] for r in audited if r['record_type']=='ordering_replay')}, indent=2)+'\n')
    lines = ['# P4：Advanced 与其他完整解析策略对照', '',
             '本报告由保存的原始预测重新计分生成；没有重新调用模型。选型范围是本机实际测试的配置与明确时间预算。', '',
             '图表：[开发集CER](figures/development-cer.png) · [独立确认CER](figures/confirmation-cer.png) · '
             '[配对不确定性区间](figures/confirmation-uncertainty.png)。同目录另存可编辑SVG。'
             '解释与选择见 [FINDINGS.md](FINDINGS.md)。', '',
             '## 实验设计', '',
             '- 开发集：沿用 P1/P3 的 12 个源页，其中 6 页文本计 CER，中英文各 3 页；每页三个配对条件，共 36 次调用/策略。',
             '- 独立确认：新增 12 个源文档组，与开发集及彼此不重复；8 页文本，中英文各 4 页，4 页复杂材料；36 次调用/策略。清单prose层按标注类别筛选，包含试题/索引，不等于全部是连续叙述正文。',
             '- 新装的Docling/Granite/Paddle运行时先完成非基准合成样例检查；Advanced复用P3已通过检查的运行时。源文档选择先于预测；原方案确认入围者按开发集平均CER固定后才运行。',
             '- 根据开发集Paddle段落乱序案例，增加只关闭merge_layout_blocks的受控变体；这是开发阶段的数据驱动消融，追加方案在变体预测和全部确认预测之前固定，详见paddle-unmerged-amendment.json。',
             '- 原始块坐标进一步显示检测阶段就有列间乱序，追加固定几何阅读顺序规则。几何候选无条件进入第四组确认，其身份/规则先于任何确认预测固定，不根据确认结果调参；代码合成测试后的Y分割修正另有时间和哈希记录。',
             '- CER 使用 NFKC、移除空白、保留大小写/标点的整页编辑距离；阅读顺序与表示格式差异也会产生错误。失败保留，空预测 CER=100%。CER 可因插入超过100%，不改称“准确率”。',
             '- 初筛规则为 CER≤10% 且预测长度≥参考80%；是项目阈值，并非教学可用性认证。',
             '- 新专业候选每输入240秒，包括冷启动、解析和导出；既有轻量解析保留原120秒预算。单次耗时仅描述，不是严格等资源吞吐排名。',
             '- 表格/图像指标使用原始及扫描两条件；旋转退化图未进行坐标配准，事先排除。表格 TEDS 是新增描述性指标，不替代预注册正文选型。', '',
             '## 同一开发集比较', '']+table(development)+['', '## 源文档隔离确认', '',
             f'原方案按开发均值选出的新候选：**{NAMES[challenger]}**；另有事先追加的固定几何顺序候选。两者与Standard和冻结adaptive一起确认，全部规则先于确认预测固定。', '']+table(confirmation)
    lo, hi = uncertainty['percentile_interval_95']
    lines += ['', f'确认集 Standard CER − 新候选 CER = {uncertainty["mean_cer_reduction"]*100:.2f} 个百分点；'
              f'按源页和语言分层的探索性 bootstrap 95%区间为 [{lo*100:.2f}, {hi*100:.2f}] 个百分点。'
              '三个变体随同源页一起重采样，不能当成独立文档扩充样本量。', '',
              f'几何方案相对 Standard 的平均 CER 降低为 {geometry_uncertainty["mean_cer_reduction"]*100:.2f} 个百分点，探索性区间 '
              f'[{geometry_uncertainty["percentile_interval_95"][0]*100:.2f}, {geometry_uncertainty["percentile_interval_95"][1]*100:.2f}]。'
              f'在同一份未合并识别结果上，只改变排序的配对效果为 {ordering_effect["mean_cer_reduction"]*100:.2f} 个百分点。'
              '这里有多个预设候选比较，不作总体显著性或无偏最优保证。', '',
              f'两个新增入围者之间的补充描述性比较：{NAMES[challenger]} CER − 几何方案 CER = '
              f'{finalist_uncertainty["mean_cer_reduction"]*100:.2f} 个百分点，探索性区间 '
              f'[{finalist_uncertainty["percentile_interval_95"][0]*100:.2f}, {finalist_uncertainty["percentile_interval_95"][1]*100:.2f}]。'
              '此区间是在部分确认预测已可见后增加的分析，非新增预注册假设；未据此改参数、改样本或增删入围者。', '',
              '## 表格与配图', '',
              '图片按 IoU≥0.5 一对一最大匹配，所有无图页误报仍计入精确率。表格先按同样位置规则匹配，未找到的标注表格记0分，再计算 TEDS。'
              'TEDS 使用固定 IBM PubTabNet 算法的项目适配版，统一 HTML 表格包装和 th/td；结构版不比较单元格文字，内容版受 LaTeX/Unicode 表达影响。', '',
              '| 数据/配置 | 条件 | 图片匹配/标注 | 图片精确率 | 表格匹配/标注 | 表格精确率 | TEDS结构 | TEDS内容 |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for name, entries in structures.items():
        for e in entries:
            p, t = e['pictures'], e['tables']
            fmt = lambda v: 'N/A' if v is None else f'{v:.2%}'
            lines.append(f'| {name} | {e["variant"]} | {p["matched"]}/{p["gold"]} | {fmt(p["precision"])} | '
                         f'{t["matched"]}/{t["gold"]} | {fmt(t["precision"])} | {fmt(e["teds_structure"])} | {fmt(e["teds_content"])} |')
    lines += ['', '确认集没有 figure 类金标准，不能声称验证了图片召回率；该集保留3个table金标准，本轮未对公式语义计分。'
              '配图定位不代表图意解释正确；公式与代码语义、真实拍照、下游 RAG 仍未取得独立准确率。', '',
              '## 语言分层', '', '| 集合/配置 | 语言 | 三条件平均 CER | 初筛达标 |', '|---|---|---:|---:|']
    for e in summary:
        if e['variant'] == 'all' and e['language'] != 'all':
            lines.append(f'| {e["split"]}/{NAMES[e["strategy"]]} | {e["language"]} | {e["macro_cer"]:.2%} | {e["usable_pages"]}/{e["accuracy_eligible_cases"]} |')
    lines += ['', '## 确认集配对变化与反例', '',
              '下表逐项保留改善、退化和不变的次数；分母24是8个正文源页的三个变体，不能当作24份独立文档。'
              '所有配对分数见 confirmation/paired-cases.csv/json。没有依据金标准为每页选择解析器。', '',
              '| 基准 → 候选 | 改善 | 退化 | 不变 | 最不利配对案例 | CER变化 |',
              '|---|---:|---:|---:|---|---:|']
    for baseline, candidate in comparisons:
        selected = [r for r in paired if r['baseline'] == baseline and r['candidate'] == candidate]
        counts = Counter(r['outcome'] for r in selected)
        worst = min(selected, key=lambda r: r['cer_reduction'])
        lines.append(f'| {NAMES[baseline]} → {NAMES[candidate]} | {counts["improved"]} | {counts["regressed"]} | '
                     f'{counts["tied"]} | {worst["sample_id"]}/{worst["variant"]} | '
                     f'{worst["baseline_cer"]:.2%} → {worst["candidate_cer"]:.2%} |')
    lines += ['', '## 失败和耗时', '', '| 集合/配置 | 样本 | 条件 | 失败 | 秒 |', '|---|---|---|---|---:|']
    for split, rows in [('development', development), ('confirmation', confirmation)]:
        for row in rows:
            if row['error_type'] or not row['nonempty_page']:
                error = row['error_type'] or '空白输出（未抛异常）'
                lines.append(f'| {split}/{NAMES[row["strategy"]]} | {row["sample_id"]} | {row["variant"]} | {error} | {row["elapsed_seconds"]:.1f} |')
    lines += ['', '| 集合/配置 | 平均秒/调用（含失败） |', '|---|---:|']
    for e in summary:
        if e['variant'] == e['language'] == 'all':
            lines.append(f'| {e["split"]}/{NAMES[e["strategy"]]} | {e["mean_seconds_per_page"]:.1f} |')
    lines += ['', '## 可复现材料与边界', '',
              '- `preregistration.json`、`protocol-notes.md`、`table-protocol.json`：规则和后续澄清；`confirmation/frozen-finalists.json`：验证前冻结的入围者。',
              '- `runs/`、`confirmation/`：所有预测、JSON结构、裁图、日志、计分、配置与源码快照；`models/`：上游修订及权重SHA256。',
              '- `comparison.csv/json`、`structures/`、`audit.json`：分层汇总、区域/表格细分及预测重放审计。',
              '- 几何策略的开发/确认输出均从对应未合并识别结果确定性重放，所有文字、类型、坐标逐项保持不变。重放行不是新的模型调用，耗时为原识别记录加排序时间；audit.json分开计算实际推理与排序重放数量。',
              '- `SETUP.md`、`REFERENCES.md`、依赖锁文件：设备、安装和运行条件，官方参考。旧 P1/P3 记录保持原样。',
              '- 来源是公开基准及其已有人工校验标注，并非本项目新增人工标注；确认集只与本项目开发源文档隔离，不能证明未进入模型训练。',
              '- 材料是一般中英文文档，不代表计算机本科课程总体；模拟退化不是实拍照片。有限候选和小样本不能证明全球最优。',
              '- 本轮未调用付费API，也未向外部模型上传私人资料；未更改线上默认解析器、账号数据、历史索引和生成记录。',
              '- CER 改善不能直接解释为 RAG Recall 或教学事实准确性改善，后续需要固定 chunk/embedding/检索后的配对下游实验。', '']
    lines += ['- 确认p04三栏索引存在阅读顺序反例，且上游参考含疑似零字形标注噪声；已目视记录于 confirmation/case-notes.md，未改金标准、未删页、未调参。CER也受参考质量与格式影响。', '']
    (P4/'report.md').write_text('\n'.join(lines))
    print(json.dumps({'audited_cases': sum(x['rows'] for x in audited), 'challenger': challenger, 'interval': uncertainty}, indent=2))


if __name__ == '__main__':
    main()
