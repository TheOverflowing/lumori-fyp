"""Recompute P3 from raw results and compare only matched P1 metric contracts."""
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_document_parsing import text_metrics,aggregate,paired_cer_bootstrap,sha256
from scripts.evaluate_mineru_parsing import extract_pages,VARIANTS
from scripts.evaluate_mineru_regions import evaluate as evaluate_regions


def summarize(root):
    manifest_path=ROOT/'docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json'
    manifest=json.loads(manifest_path.read_text());samples={s['id']:s for s in manifest['samples']}
    p1=ROOT/'docs/parsing/experiments/P1-baseline-adaptive-20260918'
    p1rows=json.loads((p1/'rows.json').read_text())
    strategies=['pypdf_baseline_v0','adaptive_local_v1','rapidocr_v1']
    rows=[r for r in p1rows if r['strategy'] in strategies]
    p1config=json.loads((p1/'configuration.json').read_text())
    assert p1config['manifest_sha256']==sha256(manifest_path)
    assert len(rows)==len(strategies)*len(samples)*len(VARIANTS)
    for sample in samples.values():
        assert sha256(manifest_path.parent/sample['reference'])==sample['reference_sha256']
        for variant in VARIANTS:
            entry=sample['files'][variant]
            assert sha256(manifest_path.parent/entry['path'])==entry['sha256']
    for row in rows:
        raw=json.loads((p1/'outputs'/f'{row["strategy"]}--{row["sample_id"]}--{row["variant"]}.json').read_text())
        sample=samples[row['sample_id']]
        metrics=text_metrics((manifest_path.parent/sample['reference']).read_text(),raw['prediction'],sample['language'],sample['cer_eligible'])
        assert row==raw['case'] and all(row[k]==v for k,v in metrics.items())
    p1_verified_rows=len(rows)
    audits=[];resources=[];region_summaries=[]
    for run in sorted((root/'runs').iterdir()):
        if not (run/'rows.json').is_file():continue
        config=json.loads((run/'configuration.json').read_text());rr=json.loads((run/'rows.json').read_text())
        expected={(strategy,sid,variant) for strategy in config['strategies'] for sid in samples for variant in VARIANTS}
        assert {(r['strategy'],r['sample_id'],r['variant']) for r in rr}==expected
        assert len(rr)==len(expected)
        assert config['manifest_sha256']==sha256(manifest_path)
        for r in rr:
            stem=f'{r["strategy"]}--{r["sample_id"]}--{r["variant"]}'
            raw=json.loads((run/'outputs'/(stem+'.json')).read_text());s=samples[r['sample_id']]
            original=manifest_path.parent/s['files'][r['variant']]['path'];assert sha256(original)==raw['input_sha256']
            reference=manifest_path.parent/s['reference'];assert sha256(reference)==s['reference_sha256']
            if not raw['error']:
                package=run/'outputs'/stem
                document=json.loads((package/'middle_json.json').read_text());prediction='\n'.join(extract_pages(document))
                assert prediction==raw['prediction']==(package/'prediction.txt').read_text()
                info=json.loads((package/'worker.json').read_text())
                assert info['extension']['tier']==run.name
                assert info['producer']['version']=='4.0.2'
                for asset in info['assets']:assert sha256(package/asset['path'])==asset['sha256']
                resources.append({'strategy':r['strategy'],'variant':r['variant'],'rss_bytes':info['worker_max_rss_bytes'],'seconds':r['elapsed_seconds']})
            else:
                assert raw['prediction']==''
            recomputed=text_metrics(reference.read_text(),raw['prediction'],s['language'],s['cer_eligible'])
            assert all(r[key]==value for key,value in recomputed.items())
            assert r==raw['case']
        for filename,expected_sha in config['source_sha256'].items():
            assert sha256(run/'source-snapshot'/filename)==expected_sha
        strategies+=config['strategies'];rows+=rr
        audits.append({'run':str(run.relative_to(root)),'cases_verified':len(rr),'success':sum(r['completed_without_exception'] for r in rr),'verified':True})
        region_summaries+=evaluate_regions(run)
    results=[]
    for strategy in strategies:
        for variant in VARIANTS:
            group=[r for r in rows if r['strategy']==strategy and r['variant']==variant]
            results.append({'strategy':strategy,'variant':variant,**aggregate(group)})
    (root/'comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    with (root/'comparison.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    bootstrap=[paired_cer_bootstrap(rows,'adaptive_local_v1',strategy,variant)
        for strategy in strategies if strategy.startswith('mineru_') for variant in VARIANTS]
    language_results=[];paired_changes=[]
    for strategy in ['adaptive_local_v1']+[s for s in strategies if s.startswith('mineru_')]:
        for variant in VARIANTS:
            for language in ['english','simplified_chinese']:
                group=[r for r in rows if r['strategy']==strategy and r['variant']==variant and r['language']==language]
                language_results.append({'strategy':strategy,'variant':variant,'language':language,**aggregate(group)})
            if strategy.startswith('mineru_'):
                old={r['sample_id']:r for r in rows if r['strategy']=='adaptive_local_v1' and r['variant']==variant and r['cer_eligible']}
                current=[r for r in rows if r['strategy']==strategy and r['variant']==variant and r['cer_eligible']]
                paired_changes.append({'strategy':strategy,'variant':variant,
                    'improved':[r['sample_id'] for r in current if r['cer']<old[r['sample_id']]['cer']],
                    'worse':[r['sample_id'] for r in current if r['cer']>old[r['sample_id']]['cer']],
                    'unchanged':[r['sample_id'] for r in current if r['cer']==old[r['sample_id']]['cer']]})
    audit={'manifest_sha256':sha256(manifest_path),'runs':audits,'paired_cer_intervals':bootstrap,
        'p1_comparison_rows_recomputed':p1_verified_rows,'p1_rows_sha256':sha256(p1/'rows.json'),
        'language_results':language_results,'paired_changes':paired_changes,
        'limits':'Same 12-source development pilot and P1 metric contract; 6 prose pages only for CER; no held-out generalization claim. Timings are descriptive: P1 concurrent pytest; P3 Basic overlapped model downloads, smoke checks and Standard. Basic ran in the sandbox on CPU; Standard required host Metal access. No fair throughput ranking.'}
    (root/'verification.json').write_text(json.dumps(audit,indent=2)+'\n')
    lines=['# P3：MinerU 4.0.2 本机对照', '',
        '日期：2026-09-18。此前只比较了轻量文本/OCR候选，本轮将专业结构解析器加入同一固定公开样本；不把未测试候选排除为“不适用”。', '',
        f'另见[结果解释与选型](FINDINGS.md)、[安装与精确复现说明](SETUP.md)。正式运行{sum(r["cases_verified"] for r in audits)}次，成功返回{sum(r["success"] for r in audits)}次；有输出与内容准确分开统计。', '',
        '## 配置与证据范围', '',
        '- 上游工具：MinerU 4.0.2；小模型：官方 MinerU-4 ONNX bundle，CPU、4 intra / 1 inter线程；Standard 采用官方配置的 MinerU2.5-Pro-2605-1.2B Q8_0 GGUF + llama.cpp。',
        '- 本机：Apple Silicon arm64、16 GiB统一内存、10核CPU。依赖位于独立 `.venv-mineru`，配置和权重位于 `tmp/mineru-runtime/`。主应用依赖、资料与默认解析器未修改。',
        '- 先冻结[方案](preregistration.json)，通过非基准自编图的运行检查后，再运行全部12页×3变体。档位分别存档，不把安装/下载失败当识别准确率，也不删除正式运行中的失败。',
        '- 与P1相同：CER仅评6个正文页；NFKC去空白、保留大小写和标点；达标要求CER≤10%且文字长度≥金标准80%。复杂页保存结构输出，未计算TEDS、CDM或图意准确率。',
        '- 用MiddleJson有序正文span评分，保留页眉页脚及原输出顺序，不将Markdown新增标记、图片路径作为正文。未基于答案纠字、重排或筛选样本。',
        '- 权重先下载、校验，再设为local离线推理；worker不继承API密钥。未调用付费模型API，也未上传私人课程。', '',
        '## 相同样本的对照结果', '',
        '| 策略 | 输入 | 有文字/12 | 正文达标/6 | Macro CER | Micro CER | 平均秒/页* |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f'| {r["strategy"]} | {r["variant"]} | {r["nonempty_pages"]}/{r["cases"]} | {r["usable_pages"]}/{r["accuracy_eligible_cases"]} | {r["macro_cer"]:.2%} | {r["micro_cer"]:.2%} | {r["mean_seconds_per_page"]:.2f} |')
    lines+=['','*时间为一次性描述记录，不是公平吞吐排名：P1同期有pytest负载；P3 Basic与模型下载、运行检查及Standard有重叠。Basic在沙箱中使用CPU，Standard因沙箱无法创建Metal队列而在宿主环境使用本机GPU。每页为独立进程，包含导入、加载、解析与结构/图片保存；操作系统及着色器缓存可能被复用。P1未包含图片资产导出。', '',
        '## 语言分层与逐页退化', '',
        '每种语言仅3个正文源页，避免让混合均值掩盖差异。以下均为Macro CER。', '',
        '| 策略 | 输入 | 英文 CER（n=3） | 中文 CER（n=3） |', '|---|---|---:|---:|']
    for strategy in ['adaptive_local_v1']+[s for s in strategies if s.startswith('mineru_')]:
        for variant in VARIANTS:
            group={r['language']:r for r in language_results if r['strategy']==strategy and r['variant']==variant}
            lines.append(f'| {strategy} | {variant} | {group["english"]["macro_cer"]:.2%} | {group["simplified_chinese"]["macro_cer"]:.2%} |')
    lines+=['', '与现有adaptive方案逐页配对；均值改善不等于每页都改善。', '',
        '| 候选 | 输入 | 改善页/6 | 退化页/6 | 不变页/6 | 退化样本 |', '|---|---|---:|---:|---:|---|']
    for r in paired_changes:
        lines.append(f'| {r["strategy"]} | {r["variant"]} | {len(r["improved"])} | {len(r["worse"])} | {len(r["unchanged"])} | {", ".join(r["worse"]) or "无"} |')
    lines+=['', '以源页为重采样单位、语言内配对的729种bootstrap组合，以下为CER降低百分点（当前adaptive−候选）。这是小型开发样本的探索性区间，不能转化为课程总体或统计显著性保证。', '',
        '| 候选 | 输入 | 平均降低（百分点） | 95%探索性区间 |', '|---|---|---:|---:|']
    for r in bootstrap:
        lower,upper=r['percentile_interval_95']
        lines.append(f'| {r["candidate"]} | {r["variant"]} | {r["mean_cer_reduction"]*100:.2f} | [{lower*100:.2f}, {upper*100:.2f}] |')
    lines+=['',
        '## 配图区域定位（新口径，不是图意理解）','',
        '预测image/chart框与官方figure标注包围框按归一化坐标做IoU≥0.5的一对一最大匹配。所有12页计入，因此无图页的误报也进入精确率分母；失败保留。原PDF和扫描版分别评分；退化图需要额外坐标配准，在评分前即排除。详见[冻结协议](setup/figure-protocol.json)。','',
        '| 档位 | 输入 | 匹配/标注区域 | 预测区域 | 区域召回 | 区域精确率 |','|---|---|---:|---:|---:|---:|']
    for r in region_summaries:
        precision=f'{r["precision"]:.2%}' if r['precision'] is not None else '未定义'
        lines.append(f'| {r["strategy"]} | {r["variant"]} | {r["matched_regions"]}/{r["gold_regions"]} | {r["predicted_regions"]} | {r["recall"]:.2%} | {precision} |')
    lines+=['','整页预览保留率与此处区域召回不同，不能直接拿P1的4/4页预览和这里的Figure框比较。原PDF与标注版本、渲染页面可能存在细微差异；这是开发样本上的局部定位评测。', '',
        'Basic的p04将金标准合并标注的上下两张子图分别提取，各自与整图的IoU不足0.5，按冻结规则计为未命中。这是分组差异，并不直接证明子图丢失；未在看到结果后合并框或调阈值。另对p06/p10各一张Basic裁图与原页目视核对，详见[视觉检查记录](visual-review.json)，不作为新增人类标注。', '',
        '## 运行资源和审计','',
        '| 档位 | 已完成调用 | 峰值RSS中位数 | 最大RSS |','|---|---:|---:|---:|']
    for strategy in strategies:
        rr=[r for r in resources if r['strategy']==strategy]
        if rr:lines.append(f'| {strategy} | {len(rr)} | {statistics.median(r["rss_bytes"] for r in rr)/2**30:.2f} GiB | {max(r["rss_bytes"] for r in rr)/2**30:.2f} GiB |')
    lines+=['','RSS是macOS工作进程的观测值，不等于整个系统峰值或完整GPU显存。模型文件大小、Python环境占用和运行RSS也不是同一指标。', '',
        f'原始结构、Markdown、图片、预测正文、运行日志、每页分数分别位于各 `runs/<tier>/outputs/`。`comparison.csv/json`为汇总；[verification.json](verification.json)从{sum(r["cases_verified"] for r in audits)}份MinerU结果（成功时读取原始结构，失败时保留空预测）和{p1_verified_rows}份P1对照预测重新计算指标，校验输入/参考答案/资产/源码哈希，并保存同页配对的小样本bootstrap。评分与适配的软件检查见本轮[JUnit记录](metric-tests.xml)；软件检查不等于识别准确率。', '',
        '12个源页中只有6个正文准确率样本，三种变体不能写成36个独立样本。所有选型仍属于同一开发集；不宣称官方OmniDocBench成绩或对所有课程最强。高质量表格、公式、配图内容还需要专项标注与独立测试。','',
        '## 复现','', '```sh',
        '.venv/bin/python scripts/evaluate_mineru_parsing.py --prepare',
        '# 模型下载/验证需使用 setup/config.yaml 对应的 MINERU_HOME / MINERU_CONFIG；具体冻结环境见run配置。',
        '.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers basic --output NEW_EXPERIMENT/runs/basic',
        '.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers standard --output NEW_EXPERIMENT/runs/standard',
        '.venv/bin/python scripts/summarize_mineru_experiment.py NEW_EXPERIMENT',
        '```','',
        '官方依据：[MinerU4发布](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.2-released)、[档位与硬件](https://opendatalab.github.io/MinerU/usage/tiers/)、[本地SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)、[输出协议](https://opendatalab.github.io/MinerU/reference/output_files/)、[模型下载](https://opendatalab.github.io/MinerU/usage/model_source/)。核验日期2026-09-18。']
    (root/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'runs':audits,'comparison_rows':len(results),'region_summary':region_summaries},indent=2))


if __name__=='__main__':summarize(Path(sys.argv[1]).resolve())
