# T2Ranking 中文 CS 主题补充集

本数据含 **20 条中文查询、339 个片段**，用于检索诊断。材料来自真实网页搜索，**不是大学课程讲义**。其相关性标签继承公开数据；助手只做主题筛选，没有生成或修改相关性判断。

## 来源和标签

- 上游：[THUIR/T2Ranking](https://github.com/THUIR/T2Ranking)，作者声明 Apache-2.0，许可文本和作者 README 存于 `source/`。
- 下载变体：[C-MTEB/T2Reranking](https://huggingface.co/datasets/C-MTEB/T2Reranking)，固定 revision `76631901a18387f85eaa53e5450019b87ad58ef9`，文件 120,293,598 字节；SHA-256 见 `source/download.json`。
- [上游论文 §4.1](https://arxiv.org/html/2304.03679#S4.SS1) 说明专业标注员提供直接相关性判断。官方 MTEB 的 T2Reranking 任务元数据也标明 `human-annotated`，其固定代码快照在 `source/mteb-cmteb-reranking.py.txt`。
- 此 C-MTEB 文件只给出 `query`、`positive`、`negative`。转换只采用 `positive → 1`、`negative → 0`。**没有恢复、猜测或捏造原始四级分数，也没有确认 C-MTEB 当时的四级折叠阈值。**因此它是公开人类标签的二值派生版本，不能称官方四级评测。
- 上游作者许可明确；此派生数据卡和当前 MTEB 元数据没有单独填写标准许可。该差异已保留在 `benchmark.json` 的 provenance 中，不把缺失字段补写成作者未声明的事实。

## 如何选出这 20 题

`selection-protocol.json` 在下载前冻结了 CS 术语规则和 40 题/1,000 片段上限。6,129 条源查询只有 44 条匹配，其中包含股票代码、医学检查、洗衣机故障等同字串。

在任何检索排名或模型调用前，经主任务接受较小的技术主题补充集，记录 `selection-protocol-v2.json`。助手依据纯主题标准逐条纳入 20 题、排除 24 题，全部理由保存在 `topic-decisions.json` 和 `topic-decisions.csv`。此步骤是**助手主题筛选，不是人工相关性标注**。原 v1 文件保留，没有为达到数量目标扩充不相关题目。

纳入内容为 Python/C/HTML 编程、SQL、Linux、虚拟化、网络协议/固件、数据编码、排序、AI 概念等；兼有编程学习内容和语言选择问题，因此也不能把所有查询都称本科考试题。

所有纳入题目的原正负片段均保留，不截断、不清洗 HTML、不改写句子、不新增负例。相同片段按完整文本哈希合并；此版本 339 条源判断对应 339 个不同片段。原来源没有提供 passage ID，因此文档 ID 是原文本 SHA-256，另保留源行号、正负列表和列表位置。

## 划分与指标边界

源数据仅使用公开 **official dev**，从未读取 official test。20 条查询按固定种子和规范化查询哈希排序，交替划成本地 dev/test 各 10 题。它们是本项目本地划分，不是 T2Ranking 官方测试集；本地 test 不参与调参。

每题正例写入 `relevance`，全部判断保存于 `judgments` 和 `judgments.csv`，明确负例另存 `explicit_negative_document_ids`。所有题的候选合并为一个 339 片段语料库，**跨题新增组合是未判断项，不是人工负例**。因此 Recall/nDCG 等是此缩减语料上的“已知正例”指标，不能直接与 230 万片段官方榜单比较。也可另按 `source_candidate_document_ids` 进行原候选池内重排，但须另行声明实验任务。

`required_evidence_groups` 仅包含一个“所有正例均为可命中选择”的组，其 `all_evidence@k` 等价于 Hit@k，**不能解释为答案所有必要证据均已找齐**。该元数据只是为了适配统一评测器，不是源数据新提供了必要证据组。

20 题只用于诊断和选定下一轮假设，不足以证明泛化提升。来源年代较早，是否出现在嵌入模型训练数据中未知。

## 文件与复现

- `benchmark.json`：统一 `rag-benchmark-v1`，`label_status=public_human_relevance`。
- `build-manifest.json`：原数据、协议、筛选、生成数据和构建脚本的 SHA-256。
- `source/dev.parquet`：固定公开下载源；`source/keyword-candidates.jsonl`：44 条原关键词候选（含排除项），供不安装 Parquet 库的离线重建。
- `judgments.csv`：所有源正负判断。`original_four_level_grade` 列空白代表未提供，不代表 0。

在项目根目录运行：

```bash
.venv/bin/python scripts/build_t2ranking_benchmark.py --check
```

以上只使用本地缓存和 Python 标准库，校验缓存固定哈希并要求重建结果逐字节相同。重新生成文件可去掉 `--check`。

如需从完整 Parquet 独立核查 44 条提取结果，可在临时或独立环境安装 `pyarrow==21.0.0`，再运行：

```bash
.venv/bin/python scripts/build_t2ranking_benchmark.py --verify-source --check
```

若完整源文件缺失，可加 `--download` 下载固定 revision 并核验固定哈希。构建没有嵌入或文本模型调用。
