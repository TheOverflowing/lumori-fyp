# R7 离线复现说明

日期：2026-09-20。原运行：`docs/rag/r7-experiments/20260919T161914951306Z/`。

所有下面命令从项目根目录执行，只读取已有数据，不新增API。建议先复制运行目录，报告和图表输出会覆盖副本内同名文件；不要为了重建报告运行 `rewrite`、`embed`、`rerank` 在线阶段。

## 报告和分层统计

```sh
R7_SOURCE="$PWD/docs/rag/r7-experiments/20260919T161914951306Z"
R7_COPY=$(mktemp -d "${TMPDIR:-/tmp}/lumori-r7-report.XXXXXX")
cp -R "$R7_SOURCE/." "$R7_COPY/"
python3 "$R7_COPY/code/scripts/r7_report.py" --run "$R7_COPY"
```

报告脚本仅用Python标准库，读取dataset、components、selection-lock、calls、rewrites和dev/test-per-query。核验四臂对齐、L4质量为null、L0–L3不必要澄清为0分、来源分量不跨划分，并根据dev首阶段指标复核选择。生成report.md、decision.json、metrics.csv、clarification.csv、paired-intervals.csv及test-changes.csv，不修改主选择锁。

## 候选、评分和指标重放

```sh
.venv/bin/python scripts/r7_verify.py --run "$R7_SOURCE"
```

此脚本先核验输入及当前相关源码与freeze一致，在临时副本内阻断socket与Remote，重放首阶段排序和共享重排请求，再从已保存的响应重算最终排名、span分数及统计行。候选比较仅排除新测的ranking_ms，其余检查完全相等。原始calls.json和选择锁必须不变；输出独立r7-replays目录与原run/offline-verification.json。

若当前相关源码已改变，验证器会拒绝声称精确重放；应先在隔离工作区恢复freeze对应版本及environment.json中的依赖，不应删掉校验。归档code保存直接相关源码，不是可单独部署的完整项目。报告聚合脚本不依赖应用模块，可独立使用。

## AI审核与事后描述

```sh
python3 scripts/r7_semantic_analysis.py --run "$R7_COPY"
```

只把rewrite-semantic-audit.json中的AI判断与test结果关联，生成semantic-sensitivity.json。审核分类不是真人gold，不改变原始主分母、选择或prompt。任何后续修订需新建实验编号。

## 论文图

使用已安装matplotlib的Python运行：

```sh
python3 scripts/r7_plot.py --run "$R7_COPY"
```

本次用临时依赖目录 `/tmp/lumori-r7-plot-deps` 渲染，没有修改项目依赖。该目录可能被系统清理；这不影响已保存PNG/PDF/SVG。重绘需要另备matplotlib环境，并依据脚本核验每档16条、8个留出family和6个文档分量。L4单独作图，不能连入检索质量曲线。

## 日志的正确解释

- calls.json每个条目是一次HTTP attempt，用logical_key关联，attempt为1或2；240次text中2次本地字面校验失败仍为HTTP200，7次重排503通过预定的一次重试恢复。
- rewrite需要澄清时忽略query字段；失败时回退原文。`status`不能直接当语义正确率。
- embedding的26条调用记录对应批量请求，不是26条文本。实际144个新文档输入和263个去重查询输入。
- shared-requests中的并集20–30条，每个策略实际候选仍最多20。此共享计费与耗时不能用作四个独立生产请求的在线测量。
- stage-rewrite-dev和stage-embed-dev的dev来自CLI默认参数；这两阶段实际覆盖所有120条查询。真正按split执行的是rank、rerank、metrics。
- 已知cost不含缺金额记录，不能视为完整账单；DeepSeek只报告token。
- 离线一致验证本地处理可重现，不是新增独立试验、真人标注复核或远端模型性能复测。
