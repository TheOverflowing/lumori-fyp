# 真实材料与人类标签来源核查

核查日期：2026-09-12。目的：为计算机本科、中英文 RAG 实验寻找可追溯外部数据。本文件只核查来源与任务语义；未查看当前或历史检索结果，未据此筛选有利样例。

## 可以接入，但须保留标签含义

| 数据 | 真实来源与人工工作 | 适用任务 | 主要限制 |
|---|---|---|---|
| CS1QA | 真实入门 Python 课堂的学生/助教对话；众包提取 QA；有该课程助教经历的两位标注者选择相关代码行 | 代码证据定位，或明确声明转换方式的课程 QA 检索 | 主要从韩语机器译英；原 answer-retrieval 的训练正例来自 BM25，不能称人工检索 qrels |
| T2Ranking | 真实中文搜索查询、网页片段；专业标注员的直接相关性等级 | 中文片段检索，适合作为外部检索基准 | 通用网页搜索，不是课程讲义；缩小语料后只能称子集实验 |

这两者互补，不能合并成“中英文真实本科教材、教师全面标注的统一金标准”。真实课程讲义的中英文评测仍需另外收集材料，并由人标出查询对应的证据片段。

## CS1QA：课堂数据和代码行标签确实由人产生

官方入口：[论文](https://aclanthology.org/2022.naacl-main.148/)、[数据仓库](https://github.com/cyoon47/CS1QA)、[MIT LICENSE](https://raw.githubusercontent.com/cyoon47/CS1QA/main/LICENSE)。

论文定位（PDF 页码从 1 开始）：

- 第 3–4 页 §3.3–3.4：众包工作者从课堂记录提取问题和答案；每道题由两位有本课程助教经历的人选择代码文件及相关代码行。不同人的有效代码选择都保留。
- 第 2 页介绍、第 5 页 §5：主要源文本是韩语；9,237 条中 644 条原本为英语。第 6 页 §5.4 的人工检查针对抽样翻译，不能扩写为“每条英文翻译均人工复核”。
- 第 7 页实验方法：answer-retrieval 的训练标签由最高 BM25 分的问题提供。该标签不是人独立判断的相关性标签。
- 第 12 页附录 A：`taskNo`、`startLine`、`endLine` 从 0 开始。

下载文件目录：[data/final/cleaned/equal](https://github.com/cyoon47/CS1QA/tree/main/data/final/cleaned/equal)。原始 URL 模式：

```text
https://raw.githubusercontent.com/cyoon47/CS1QA/main/data/final/cleaned/equal/dev_cleaned.jsonl
https://raw.githubusercontent.com/cyoon47/CS1QA/main/data/final/cleaned/equal/dev_cleaned_orig.jsonl
https://raw.githubusercontent.com/cyoon47/CS1QA/main/data/final/cleaned/equal/test_cleaned.jsonl
https://raw.githubusercontent.com/cyoon47/CS1QA/main/data/final/cleaned/equal/test_cleaned_orig.jsonl
```

建议转换：先保留原问题、代码、原人工 span、原 split、源 ID。按固定代码窗口产生候选片段，再机械计算与人工 span 的覆盖，命名为 `human_code_span_derived`。同一源题的两个标注不应误作两道独立题；替代的有效代码选择不必全部同时召回。需要程序上下文的题不能只保留“为什么不工作”等孤立问句。不要使用 `augmented_train_cleaned.jsonl` 宣称全为真实学生提问。

仓库另有作者提示：去标识化可能不完整。下载时保留研究用途和来源记录；若发现残留个人信息，按作者 README 的要求处理，不把学生身份信息放入公开报告。

## T2Ranking：直接的人类相关性判断

官方入口：[仓库](https://github.com/THUIR/T2Ranking)、[论文 §4.1](https://arxiv.org/html/2304.03679#S4.SS1)、[官方数据文件](https://huggingface.co/datasets/THUIR/T2Ranking/tree/main/data)。仓库 License 和论文脚注均声明数据集采用 Apache-2.0。

论文 §4.1（HTML 行 125–142）说明：每对 query–passage 至少三位长期从事检索标注的人员评分；必要时第四人介入，以多数判断定标签。等级 0 无关、1 相关但不满足信息需求、2 部分满足、3 精确满足；原检索任务仅将 2、3 算相关。查询源于搜狗用户日志，片段取自多搜索引擎找到的网页。不能把“专业标注员”改称“大学课程教师”。

原始下载：

```text
https://huggingface.co/datasets/THUIR/T2Ranking/resolve/main/data/queries.dev.tsv
https://huggingface.co/datasets/THUIR/T2Ranking/resolve/main/data/qrels.dev.tsv
https://huggingface.co/datasets/THUIR/T2Ranking/resolve/main/data/qrels.retrieval.dev.tsv
https://huggingface.co/datasets/THUIR/T2Ranking/resolve/main/data/collection.tsv
```

官方 collection 文件约 3.66 GB。轻量候选为 [C-MTEB/T2Retrieval](https://huggingface.co/datasets/C-MTEB/T2Retrieval)（文件约 158 MB）和 [qrels](https://huggingface.co/datasets/C-MTEB/T2Retrieval-qrels)（约 1.15 MB）。后者可见是二值正标签；卡片缺少完整转换说明，因此在使用前要验证 ID/文本映射及其和原官方 qrels 的一致性，不能据名称直接声称保留四级人工标签。

建议转换：只按预先写定的 CS 主题规则筛查询；保留这些查询的全部已知正例，加入固定种子的背景片段，并冻结清单。必须称“CS 主题子集、有限候选库”，不与 230 万片段的官方全量分数直接比较。人工 0 级与未判断片段分开存；如果当前评估器只接受 1、2 正等级，可将原 2→1、3→2，但需明确这是项目转换后的 nDCG，不能冒充官方四级 nDCG。

## QACP：贴近中文编程教育，但不是证据检索 qrels

官方入口：[论文](https://arxiv.org/html/2402.07913)、[作者仓库](https://github.com/NTAIX/Chinese-Python-QA-Dataset)。论文 §3.1–3.2（HTML 行 97–111）说明实际学习者问题经 Python 教育者筛选整理，16 名 Python 教师撰写答案，经过两轮复核。论文总量 10,960；目前公开仓库 README 所述、可下载的是 534 条。

```text
https://raw.githubusercontent.com/NTAIX/Chinese-Python-QA-Dataset/master/QACP_Q.json
https://raw.githubusercontent.com/NTAIX/Chinese-Python-QA-Dataset/master/QACP_A.csv
```

文件通过 ID 关联问题和人工答案，未提供教材来源段落或独立检索 qrels。可做 `human_authored_qa_derived` 的答案库检索；不可把配对关系升级为“老师逐对评审了所有候选的相关性”。不能把其余答案默认为人类负例。README §3 明确面向教育和学术研究，但当前仓库未见 LICENSE 或标准开放许可；许可状态应如实保留，公开再分发前须另行厘清。

## 英文补充：CQADupStack programmers

[原论文](https://eltimster.github.io/www/pubs/adcs2015.pdf)、[原作者仓库](https://github.com/D1Doris/CQADupStack)、[BEIR 下载脚本](https://github.com/beir-cellar/beir/blob/main/examples/dataset/download_dataset.py)。原论文声明数据按 CC BY-SA 3.0 公开；代码仓库的 Apache-2.0 不能代替数据许可。来源是 StackExchange 的社区重复问题关系，不是老师对讲义段落的打分。

BEIR 官方包：`https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/cqadupstack.zip`；解包后可选 programmers 子库。可标为 `community_duplicate_labels`；若用于课堂 RAG，只能支撑相近问题检索，不直接支撑回答证据完整性。保持原帖子 ID/来源、许可与处理说明；子库/抽样规模需记录。

## 冻结与论文表述规则

下载后记录 UTC 时间、固定 revision（若可得）、SHA-256、原 split 和数据许可证副本。标签来源至少区分：`human_relevance_judgments`、`human_code_span_derived`、`human_authored_qa_derived`、`community_duplicate_labels`、`assistant_authored_unreviewed`。这些值是建议的 provenance 描述，不表示当前评估代码已经支持。

先冻结选题、语料、标签映射和参数，再运行。保留不匹配任务、翻译、标注不完整和候选库缩小等限制；不能以自动改写/翻译/模型复核冒充新增人工标注。
