# RAG 优化与实验档案

研究方向：中英文计算机本科课程的学习内容与出题证据检索。这里持续保存每一轮的算法、数据、配置、原始结果与失败分析，帮助论文区分技术实现、探索性试验和经过人工确认的正式实验。

**当日完整归档：[2026-09-12 实验总记录](DAILY_EXPERIMENT_RECORD_20260912.md)。** 汇总 CA1 与难度验收、R1–R5、当前切分和召回选择、未采用的候选、数据谱系、指标口径、费用、复现及后续论文计划。配套[全部候选对照表](daily-records/20260912/comparison-tables.md)和[带分母、单位与来源的指标台账](daily-records/20260912/metric-summary.csv)。这次归档没有新增实验或改写历史结果。

最新 [R5 跨语言查询翻译对照](R5_RESULTS_20260912.md)：比较原查询、仅译文和双路召回，固定总候选与上下文预算，使用 31 个新双语问题组验证。英文查中文的最终命中没有净提升；总体差异区间包含零，部分表面收益来自重排接口失败。译文、逐题增损、费用和零新增调用复现均已保存，本轮不启用默认翻译。

当前应用采用 [R4 文献候选实测方案](R4_RESULTS_20260912.md)：16 个开发集候选配置，先锁定再验证 42 个新双语 family。选定 token 切分、标题与任务指令、有界混合和 Qwen3-Reranker-8B；新保留集命中率持平、MRR 提高。包含真实 API 失败、成本、PNG/PDF 图和零新增调用的复现。

参考 [2026-09-12 切分与召回文献参考](research/CHUNKING_RETRIEVAL_REVIEW_20260912.md)：筛选近期论文及官方项目，比较结构/token 切分、标题上下文、父级补全、专用重排、Late Chunking 与多向量检索，附证据限制和待验证的实验顺序。原文献建议保留；可运行候选的本轮结果另见上述 R4 报告。

此前完成 [R3 递归切分对照](CHUNKING_RESULTS_20260912.md)：保留旧切分器，新增章节／段落／句子边界、原文坐标及关键词元数据。三种切分与两组混合检索消融使用相同原始人工答案跨度，分别比较 Top 5 与 6000 字符预算；1200 递归命中持平，教材重复比例从 9.20% 降至 3.41%，同时片段数增加。关键词加分本轮未带来额外命中。已见数据、嵌套代码及 RST 识别限制见报告。

此前 [R2 真实材料与公开人工标签实验](EXTERNAL_DATA_RESULTS_20260912.md)导入 12 篇真实教材，并在 MLQA 中英子集及 T2Ranking 中文子集比较五种排序策略。两组 test 上有界混合相对 dense 的已知正例 Recall@5 分别增加 0.625 和 4.17 个百分点；T2 中等权 RRF 仍更高，新方案 MRR 也有退步，默认保持 dense。教材专属真人标签仍待填写，不能与公开标签混称。

首轮 R1 的 [原始实验报告](experiments/20260912T053716373758Z/report.md)和 [验证记录](verification-20260912.json)保留不变。自编试点中的候选退步及后续改动均记于 [优化过程与结果](OPTIMIZATION_LOG.md)。

## 当前实验设计

R5 使用 [查询翻译协议](R5_PROTOCOL_V1.md)，冻结运行在 `r5-experiments/20260912T085156100010Z/`。开发集按预定平局规则选择原查询；保留集全部报告，不重新选冠军。归档代码、模型返回、向量与报告相互独立保存，完整复现说明见该轮报告。

R4 使用 [独立协议](R4_PROTOCOL_V1.md)及两次保留集曝光前的补充；数据、代码、API 返回、排名、结果和复现校验保存于 `r4-experiments/20260912T072619024568Z/`，离线重放位于 `r4-replays/20260912T081600Z/`。实际配置与索引身份说明见 [R4 接入设计](R4_RUNTIME_DESIGN.md)。不要将各轮不同数据与指标的读数直接相减。

R3 切分实验独立使用 [CHUNKING_PROTOCOL_V1.md](CHUNKING_PROTOCOL_V1.md)，结果位于 `chunk-experiments/`，重放位于 `chunk-replays/`。它的字符跨度指标与以下 R1/R2 固定 passage 的 Recall 不同，不能跨轮直接相减。切分器配置、存储迁移及关键词开关见 [实现说明](CHUNKING_DESIGN.md)。

以下命令只预检，默认复用原 R2 MLQA 缓存；真实执行加 `--live --max-api-calls 4`，本轮预计仅 4 次新嵌入请求：

```sh
.venv/bin/python scripts/chunk_experiment.py
```

精确重放已完成的 R3，零新增 API，使用归档代码及原文件快照：

```sh
.venv/bin/python -B docs/rag/chunk-experiments/20260912T062952243934Z/code/scripts/chunk_experiment.py --dataset docs/rag/chunk-experiments/20260912T062952243934Z/dataset.json --course-snapshot docs/rag/chunk-experiments/20260912T062952243934Z/course-sources.json --cache docs/rag/chunk-experiments/20260912T062952243934Z/embedding-cache.json --output-dir docs/rag/chunk-replays
```

下面继续保留 R1/R2 的固定片段排序实验与使用方法。

首次优化保留同一嵌入模型、原始查询文本及固定片段，仅比较排序策略：

| 方法 | 作用 |
|---|---|
| dense_v1 | 原始余弦相似度检索基线 |
| bm25_v1 | 中文字符单元与双字组合、英文及代码术语的关键词检索 |
| hybrid_rrf_v1 | 合并向量与 BM25 两路排名 |
| hybrid_mmr_v1 | 在融合候选中平衡相关性与内容多样性 |
| hybrid_dense_lexical_v1 | R2 新增：保留语义分数，词法加分最多为 0.05 |

参数在首次运行前固定：每路候选 20、RRF 常数 60、BM25 k1=1.2/b=0.75、MMR 权重 0.7。评估 K=1/3/5/10，主要观察 Recall@5 和全部必要证据覆盖率@5。方法定义、数据限制与后续计划见 [实验协议](EXPERIMENT_PROTOCOL.md)。

以上为 R1 原始比较参数；R2 的数据与新增策略使用 [单独冻结的协议](EXTERNAL_DATA_PROTOCOL_V1.md)。外部 QA／相关性派生标签的证据组不代表完整必要事实，须按该轮范围解释指标。

基线原始代码保存在 [首次优化前的快照](baselines/dense_v1_20260912/manifest.json)。原始实现与重构后 dense_v1 在没有并列分数时应等价；并列分数现在显式按输入顺序处理，数据库读取也显式排序。

## 记录哪些结果

- 逐题 Recall、Precision、Hit、MRR、nDCG，以及必要证据组覆盖率、全部组是否找齐。
- dev/test、中文/英文、精确术语/语义改写/跨语言/多证据等分组结果；每组保留分母。
- 基线与候选在同一批查询上的差异，区分绝对百分点与相对变化，保留固定种子的配对 bootstrap 区间。
- 无答案查询独立统计空返回情况；缺失排名按失败处理，不能从分母中删除。
- 排名和分数、算法参数、分词版本、查询格式、数据与代码 SHA-256、嵌入返回向量、调用用量及本地排序耗时。
- 每次运行都有独立目录；历史记录包含失败运行和退步结果。离线重放不是新增独立样本，不得重复计入统计。

首个 [试点评测集](../../benchmarks/rag/pilot_v1.json) 是助手自编的课程片段、查询和待复核标注。它用于检查实验方法与比较候选，不是人工标注的正式测试集。正式论文数据需要真实课程材料、明确的相关性/必要证据标注规范和人工审核；不得把本次自动生成的审阅表称为教师评分。

## 运行与复现

先明确指定数据与该轮协议，查看输入和预计调用量，不发起 API：

```sh
.venv/bin/python scripts/rag_experiment.py --dataset benchmarks/rag/external/mlqa/mlqa_cs_en_zh_v1.json --protocol docs/rag/EXTERNAL_DATA_PROTOCOL_V1.md
```

首次真实运行只调用嵌入 API，不调用文字生成 API。当前 MLQA 子集预计 12 次，设置上限 14 次，单批失败不自动重试：

```sh
.venv/bin/python scripts/rag_experiment.py --dataset benchmarks/rag/external/mlqa/mlqa_cs_en_zh_v1.json --protocol docs/rag/EXTERNAL_DATA_PROTOCOL_V1.md --live --max-api-calls 14
```

当前脚本比较五种已实现策略。精确复现历史 R1 的四种方法需使用其归档代码；用新脚本搭配旧协议运行不等于原来的预登记比较。以下离线命令也应明确使用该次冻结协议。

用已有缓存比较当前实现，不调用外部接口。将 RUN_DIR 替换为一次实际运行目录：

```sh
.venv/bin/python scripts/rag_experiment.py --dataset RUN_DIR/dataset.json --protocol RUN_DIR/protocol.md --cache RUN_DIR/embedding-cache.json
```

每个目录的 code/ 保存该次实现及协议。要使用当时版本精确重放排名和指标，运行归档脚本，并把输出写到新的目录：

```sh
.venv/bin/python -B RUN_DIR/code/scripts/rag_experiment.py --dataset RUN_DIR/dataset.json --cache RUN_DIR/embedding-cache.json --output-dir docs/rag/replays
```

向量、排名和指标应一致；运行时间依赖机器负载，不能要求完全相同。重放前应按该次 requirements.lock.txt 使用兼容的运行环境。`-B` 避免向冻结代码目录写入字节码缓存。

运行目录位于 docs/rag/experiments/，总索引为该目录下的 experiment-history.csv。每轮 report.md 用于阅读，metrics.csv、per-query.csv 和 changes.csv 用于统计与作图。annotation-review.csv 提供未填写的人工盲审工作表。检索实验数据和调用记录使用隔离数据库，不写入正常课程库。

## 在应用中选择算法

后端已共用同一套检索函数，修改本地配置后重启即可选用候选策略：

```dotenv
RETRIEVAL_STRATEGY=hybrid_rrf_v1
RETRIEVAL_TOP_K=5
RETRIEVAL_CANDIDATE_K=20
RETRIEVAL_RRF_K=60
RETRIEVAL_MMR_LAMBDA=0.7
```

仅改变排序策略不需要重新生成文档向量。以上是 R1/R2 排序开关示例；当前本地配置已采用 R4 完整方案，配置类仍保留 dense/raw 默认以兼容旧安装。修改标题编码或切分配置需要重新索引，不能只改变排序开关。生成证据会记录实际检索配置、候选数、选中片段、不同分数含义和耗时。完整诊断不会进入生成模型和难度复核的提示词。

BM25 无匹配时直接返回证据不足。其余三种方法目前没有检索级拒答阈值；相似度或融合分数不是可信度概率。纯 BM25 在应用中仍计算查询嵌入以保留统一的余弦诊断，本轮排序比较复用已缓存的向量，所以不能把本地排序时间等同于在线请求延迟。

## 后续独立实验

1. 在保持算法不变时加入经过人工审核的真实课程数据，建立有代表性的保留测试集。
2. R4 已比较 token 预算、标题、查询指令、父级与窗口扩展；后续在课程标签上独立验证跨节必要事实与复杂格式。
3. 专用重排已进入 R4；下一轮预先定义失败处理与成本限制，再验证复杂学习目标的多查询和受控补检索。
4. 将检索结果与教师的出题质量评价关联，但分别报告召回指标、内容质量与学习效果。

每轮只改变可解释的变量，不在看过测试结果后改标签或只保留有利的运行。优化是否有效由保存下来的比较结果决定。
