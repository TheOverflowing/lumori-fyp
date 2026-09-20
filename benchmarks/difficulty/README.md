# Difficulty-prompt authoring tasks v1

本目录为难度控制提示词实验提供固定课程背景与出题需求。**资料是 AI 新写的教学 fixture，不是原课程原文，不是人工翻译，也不是人工难度金标。** `target_difficulty` 是希望生成的档位，而不是某道已存在题目的正确标签。当前没有教师或学生参与标注，也没有实际作答难度数据。

## 范围与划分

| 划分 | 主题 | Case 数 |
|---|---|---:|
| dev | 二分查找、快速排序、图遍历、栈、数据库事务、CPU 调度 | 36 |
| holdout | 哈希冲突、AVL 树、分页 | 18 |

每主题包含中文、英文各三档（easy / medium / hard），共 54 条。**同一主题的所有语言、难度与改写归属同一划分**。针对同一 case，各实验方法应接收完全相同的 `sources`、学习目标和学习者背景；不同难度也复用同一段资料。文件内容哈希记在 `validation.json`；各段文本另有 SHA-256。

`pilot=true` 只选择 6 条 dev case：

| 主题 | 档位 | 题型 | 语言 |
|---|---|---|---|
| binary_search | easy | mcq | zh、en |
| transactions | medium | short_answer | zh、en |
| cpu_scheduling | hard | short_answer | zh、en |

Pilot 用于测试接口、观察失败模式和筛选候选提示词，**不是正式效果证明**。这 6 条中主题、档位和题型存在混杂：例如全部困难题来自 CPU 调度，不能据此推断对其他主题的困难题也有效。语言配对也不是相互独立样本。单次生成不反映模型随机波动。全量集覆盖两类题型，但不是主题 × 难度 × 题型的完整因子设计。

Holdout 尚未用于生成或评分。使用它之前，应冻结提示词、评审规则与预算。若依据其结果继续修改策略，应把这次数据视为开发数据，另建保留集。仅按主题隔离不能保证广义知识域完全不重合：例如查找、树和哈希都仍属于数据结构课程；本集不宣称跨课程泛化。

## 数据约定

`cases.json` 顶层为 `{schema_version, created_at, label_status, cases}`。每条 case 包含：

- `id`：唯一标识；`topic_id`：划分和配对的主题族。
- `split`：`dev` 或 `holdout`；`pilot`：是否选入第一轮小样本实验。
- `language`、`target_difficulty`、`question_type`、`topic`、`learner_profile`：出题要求。
- `sources`：固定背景片段，含 `id`、`text`、`document_name`、`page`、`url`。
- `provenance`：AI 编写声明、人工复核状态、参考来源、许可路径与文本哈希。

`sources.url` 是背景参考链接，**不代表 `text` 从该网页逐字摘录**。`page=null` 表示说明是新写且未与原文页面对齐，不能把它当成真实页码引用。原始课程材料保存在另一个目录；本轮刻意固定短上下文，以隔离检索、切分和解析波动对提示词比较的影响。中文约 700–950 字符，英文约 500–550 词；这不是 token 数等长控制，长度差异仍应在分析中披露。

背景中明确区分课程知识和自拟练习约定，例如 CPU 到达平局如何处理、页表数值是否完整。这些约定是为了让题目可判定；其中的假设不是教材实测值。中英文说明由 AI 分别编写为语义对应材料，尚无真人核验等价性。`factual_review_status=pending_independent_review` 也不能因程序校验通过自动改成已复核。

## 参考材料与许可

算法主题参考已经下载并固定 commit 的 **Hello 算法**。作者为 krahets 与贡献者，原文件采用 CC BY-NC-SA 4.0；每条 case 记录原文件 URL、SHA-256、署名与本地许可路径。若本说明构成改编，其来源的署名、非商业与相同方式共享条件仍应保留；本目录不将第三方内容重新宣称为无条件开放许可。

原材料清单和许可见 [课程来源 manifest](../rag/course_sources/manifest.json) 与 [Hello 算法许可](../rag/course_sources/hello_algo_zh/LICENSE)。旧 RAG 目录中的人工标注表仍为空；没有将其中任何数据转换成难度金标。

其他背景参考为以下官方资料，2026-09-19 已确认链接可访问。只编写有限说明与自拟教学约定，没有下载或重发整章正文；链接页面可能更新，因此本次复现实验应使用本目录固定的 context，而不是重新抓取网页。

- [PostgreSQL 17：Transactions](https://www.postgresql.org/docs/17/tutorial-transactions.html)
- [PostgreSQL 17：Transaction Isolation](https://www.postgresql.org/docs/17/transaction-iso.html)
- [PostgreSQL 17：Serialization Failure Handling](https://www.postgresql.org/docs/17/mvcc-serialization-failure-handling.html)
- [OSTEP，第 7 章：Scheduling: Introduction](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf)
- [OSTEP，第 8 章：The Multi-Level Feedback Queue](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf)
- [OSTEP，第 18 章：Paging: Introduction](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf)

OSTEP 作者为 Remzi H. Arpaci-Dusseau 与 Andrea C. Arpaci-Dusseau；PostgreSQL 文档由 PostgreSQL Global Development Group 提供。未将它们宣称为 CC BY-NC-SA；各来源保持各自的权利与许可范围。

## 复建与核验

在仓库根目录执行：

```sh
.venv/bin/python benchmarks/difficulty/build_cases.py
```

脚本只重写本目录的 `cases.json` 与 `validation.json`，不会发起模型请求、访问用户课程或生成任何质量评分。它检查 ID 唯一、主题不跨划分、语言和档位配对、同主题资料一致、pilot 只来自 dev，以及本地课程来源哈希。输出确定性 JSON；修改资料须形成新数据版本并重新记录实验快照，不要覆盖已完成实验中的输入副本。

正式论文实验应补充真人对背景事实及双语对应性的复核，并另行组织盲评或学生作答；不能将本目录的结构检查当成这些工作已经完成。后续真实课程原文实验也应单独报告，不能与本轮 AI 整理的受控上下文混写。

## English summary

This package contains 54 **AI-curated authoring requests**, covering nine undergraduate CS topics, two languages, and three requested difficulty levels. It is not a set of existing questions with gold difficulty labels. No human difficulty annotation, expert review, translation verification, or student response study has been conducted.

Six development topics provide 36 cases; three held-out topics provide 18 cases. All languages and difficulty variants of a topic remain in the same split. Six development cases are flagged for the initial pilot. That pilot confounds topic, difficulty, and question type and is suitable only for an initial engineering screen. Do not use its scores as evidence of general difficulty calibration.

The references identify background material. The stored passages are newly written notes with explicit hypothetical exercise conventions, rather than quotations or page-aligned source extracts. Accordingly, `page` is null. Each case records provenance and its context hash. Use the frozen context and archive the full selected input for every run. The deterministic builder checks structural integrity and local source hashes; it does not validate factual quality, language equivalence, difficulty, or educational effectiveness.
