# Q1：生成质量与耗时基线协议

版本：1.0 · 冻结日期：2026-09-22 · 状态：DEV 预实验，AI 编制，尚无独立人工或学习者验证

## 1. 本轮研究问题

在固定的本科课程资料和产品配置下，Lumori 生成一份可交付的单题测验需要多少时间与调用？失败或反复修复分别源于检索、题目条件、答案、引用、格式还是难度检查？中英文表达同一学习需求时，是否出现值得继续调查的差异？

本轮先建立基线，不把已经通过的工程测试当作内容质量实测，不预先宣称某个改写、融合或并发策略更优。根据失败分布选择下一项修改，再运行同一批任务作对照。修改后的同集结果属于开发集反馈；正式泛化结论需要另行冻结且未用于调参的课程和任务。

## 2. 数据与采样边界

数据文件：`benchmarks/quality_latency_v1/dataset.json`。

| 维度 | 设置 |
| --- | --- |
| 学习需求 | 12 个，每个需求配对英文、中文输入，共 24 个任务 |
| 课程 | 操作系统、数据库、计算机网络，各 4 个需求 / 8 个任务 |
| 目标难度 | easy、medium、hard 各 8 个任务 |
| 题型 | mcq、short_answer 各 12 个任务；每种难度各 4 MCQ、4 简答 |
| 每次生成 | 1 题，`include_explanations=False`（不添加题前教学内容，保留题目答案解析） |
| 原始材料 | 12 份英文官方开放许可原文节选，同课程资料共同入库 |
| 标注 | 需求、中文译写、证据锚点和审核准则均由 AI 准备，待独立审核 |
| 数据分割 | 全部为 `dev` / `pilot`，不是 unseen holdout |

课程覆盖有意收窄：操作系统考察 xv6 的切换与同步；数据库考察 PostgreSQL 18 事务语义；网络考察可靠传输和 TCP。三个方向不能代表全部本科计算机课程。

同一需求的中文与英文版本使用相同原始资料、目标难度、题型和审核标准。这样先控制材料变量。本轮覆盖英文需求检索英文资料、中文需求检索英文资料；**不覆盖中文原始资料、英文需求检索中文资料、扫描件解析或多模态理解**。配对译写未获人工确认，两种输入也不可能保证 token 长度完全相同。

### 2.1 来源、版权与冻结

- 操作系统：[MIT xv6 教材](https://mit-pdos.github.io/xv6-riscv-book/)，作者 Russ Cox、Frans Kaashoek、Robert Morris，MIT 许可；使用 Scheduling、Locking、Sleep and Wakeup 章节。
- 数据库：[PostgreSQL 18 Transactions](https://www.postgresql.org/docs/18/tutorial-transactions.html)、[Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html)、[Serialization Failure Handling](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html)，PostgreSQL Global Development Group，PostgreSQL 许可。
- 网络：[Computer Networks: A Systems Approach](https://book.systemsapproach.org/)，作者 Larry Peterson、Bruce Davie，CC BY 4.0；使用 Reliable Transmission、Reliable Byte Stream (TCP)、TCP Congestion Control 的相关段落。

许可文本、原始 HTML、下载 URL、下载时间与 SHA-256 全部存于数据包。HTML 发布页以下载快照哈希冻结；仓库 commit 字段仅标明许可证版本，不声称网站一定由该 commit 构建。

正文是选定的完整段落 / 标题，进行 HTML 实体解码和空白归一化，没有 AI 改写原文。只处理文字；图、代码块、表格、展示公式未纳入，因此题目必须自足，不可让学生依赖未提供的图或源代码行号。部分节选仍保留原文对图或行号的提及，这是明确记录的材料限制，也应在内容审核中检查。

### 2.2 需求清单

| 需求 ID | 课程 | 难度 | 题型 | 内容 |
| --- | --- | --- | --- | --- |
| os_context_switch | OS | easy | short_answer | 上下文保存与调度器角色 |
| os_race_condition | OS | medium | mcq | 共享更新、临界区与原子获取锁 |
| os_interrupt_deadlock | OS | hard | short_answer | 同 CPU 中断锁死与多 CPU 保护 |
| os_lost_wakeup | OS | hard | mcq | 丢失唤醒与条件循环复查 |
| db_atomicity | DB | easy | mcq | 原子性、COMMIT / ROLLBACK |
| db_statement_snapshot | DB | medium | short_answer | Read Committed 语句快照 |
| db_transaction_snapshot | DB | medium | short_answer | Repeatable Read 快照与可序列化区别 |
| db_serialization_retry | DB | hard | mcq | 序列化失败的完整事务重试 |
| net_reliable_delivery | Networks | easy | mcq | ACK、超时、重复抑制 |
| net_tcp_service | Networks | easy | short_answer | 字节流与报文段 |
| net_cumulative_ack | Networks | medium | mcq | 序号、缺口与累积确认 |
| net_flow_congestion | Networks | hard | short_answer | 流量控制、拥塞控制与有效发送约束 |

## 3. 防止答案或检索标签泄漏

生成请求仅允许读取 `course`、`language`、`difficulty`、`question_type`、`topic`、`learner_profile`。`source_ids`、`expected_evidence`、`review_criteria`、`grading_expectations` 都属于**生成后审核侧字段**，不可放入出题、解题或产品内审核模型的提示词。

必须把同课程的全部节选经真实切分与嵌入写入实验数据库，再用正常召回链路选择证据。不得按照每条 case 的 `source_ids` 先过滤成答案资料，不得向召回器注入 `expected_evidence` 或直接传入 gold chunks。课程间隔离维持产品语义。

证据锚点是检查“核心资料是否可用”的少量参考句，**不是穷尽相关性标注**。源文档命中率或锚点覆盖率不能命名为已验证的全面 Recall@k，不能证明语义引用正确。

## 4. 执行配置与复现

计划基线使用当前产品的真实原生逐题工作流：author → 独立 solve → review → 必要时修复；固定模型、thinking 设置、max tokens、检索策略、切分大小与上下文预算。fusion、自动探索关闭，避免外部资料变化干扰。实际运行值以 run manifest 为准，不能仅照抄本协议而假设服务配置未变。

每次实验使用独立数据库与资料目录，不修改用户课程、账户或生成记录。必须记录：

1. Git revision 与 dirty diff / 关键源码哈希，数据集与语料哈希。
2. 模型编号、公开 endpoint 标识、工作流、超时、重试与调用预算；绝不归档 API 密钥或认证头。
3. chunk / embedding / hybrid / reranker / context 配置，以及索引构建耗时与嵌入用量。
4. 任务顺序、运行时间、attempt / repeat 标识、每例原始结果与完整失败记录。
5. 每次上游调用的角色、起止时间、成功状态、provider usage；记录真实检索结果与证据。

先做离线完整性校验和不联网 dry run，再进行小批量真实调用；观察提供商是否正常响应、成本记录是否完整后继续。不可因某题失败便悄悄替换或删除该题。若需重试，应保留首次结果并建立新 attempt；若预算耗尽，未执行项目单列。

首轮串行执行控制同时负载，语言配对的运行次序应交错，避免把所有中文排在持续拥堵的时间段。只有一次运行时不把平均延迟当稳定性能结论。后续比较并发策略须保持模型、材料、预算与验证标准不变，并记录 rate limiting 和失败率。

### 4.1 首轮执行预算与输出约定

本轮 runner 为 `scripts/quality_latency_baseline.py`。计划总调用上限 192、每个生成任务调用上限 12、运行墙钟预算 3600 秒，任务并发为 1；全流程包含真实嵌入和配置的 reranker，不绕过检索直接注入参考答案。上限是停止条件，不是预期用量；预算耗尽后的任务标为未执行，已发生的调用仍保留。

```sh
# 只读检查数据并准备运行计划；没有 --live 不进行付费调用
.venv/bin/python benchmarks/quality_latency_v1/validate_dataset.py
.venv/bin/python scripts/quality_latency_baseline.py

# 用户已授权的真实预实验，输出到独立实验目录
.venv/bin/python scripts/quality_latency_baseline.py --live --call-cap 192 --per-job-cap 12 --max-seconds 3600
```

输出包含 `metrics_summary.json`、`case_metrics.csv`、`cases/*.json` 以及运行清单和实验数据库。AI 辅助审核另存独立文件，不覆盖产品内审核记录。应保留固定数据文件 SHA-256：`de8dc096f5e2d0648e3a056e32bf09d3cf2ce9308f46229fc46fdd0c65cbc0dd`。命令配置与协议发生分歧时，以归档的实际运行清单为准并解释差异。

## 5. 主要指标及分母

| 指标 | 定义与注意事项 |
| --- | --- |
| 完整交付率 | 成功持久化目标题数的任务 / 已实际开始的任务。adjusted 交付计入交付，但不能计入严格难度匹配。未运行不算失败，不混入分母 |
| 严格难度接受率 | 产品按原目标难度严格接受的任务 / 已开始任务；另报告“已交付题内”的比例。它是系统检查结论，不是学习者实测难度 |
| 调整后接受比例 | 难度或格式被调整后交付 / 已交付题，明确调整种类，不并入 strict |
| AI 辅助内容合格率 | 独立于产品内门控、按下述量表完成审核且全部核心项合格 / 已完成该层审核的题；给出未审核数与审核模型/日期 |
| 经独立确认的答案正确率 | 只有完成独立人工或可复算检验时报告，不能把 solve/review 自洽率更名为答案正确率 |
| 证据可用性 | 审核侧检查实际召回 / 实际送入生成上下文是否覆盖需求证据锚点；检索结果有证据但上下文截断丢失须分开 |
| 耗时 | 每任务端到端 wall time、首次可用结果时间，以及 retrieval / author / solver / reviewer / repair / persistence 阶段；失败任务耗时也报告 |
| 调用与用量 | 每角色调用数、失败调用数、重试/修复数、已知 input/output tokens；未返回 usage 标为 unknown，不填 0 |
| 每道可用题的实际消耗 | 同批所有已尝试任务的调用 / 已交付或已确认合格题数，明确可用定义；纳入失败和修复的成本。无可用题时记 null |

主要报告原始计数和分母，并按课程、语言、难度、题型拆分。24 个任务只有 12 个需求簇，两种语言版本不是独立抽样；不当作 24 个独立知识点。样本很小，p95 受单个极值影响大，可展示但不强调稳定性；同时提供逐例耗时、median 与范围。暂不进行强显著性或泛化提升声明。

索引预处理和单题在线阶段分开核算，不能把只收取一次的嵌入开销忽略后宣称总成本节省。若多任务共享 warm index，清楚写出这一条件。货币成本仅在准确账单或版本化单价可验证时计算；否则只报告调用数和可观测 tokens。

## 6. 生成后内容审核与故障分类

审核首先检查题目和材料，再对照答案。产品内模型的 `passed` 只是待核对证据，不直接作为外部标签。审核记录逐条包含 case_id、生成结果哈希、审核者类型、日期、判断、证据和不确定性。AI 复核、可执行算术检验、教师评审、学习者数据为不同证据层，不能混称“人工标注”。

核心审核项：

- **条件完整**：题干、选项和实际学生可见上下文足以解题；时间线、单位、初值、边界规则明确。
- **答案正确与唯一性**：MCQ 恰有一个可辩护答案；简答允许正确等价表述。含计算则独立复算。
- **解析一致**：结论与解析一致，无偷换假设；不能只因另一个模型选择相同答案就判正确。
- **引用支撑**：引用真实存在且直接支持相关主张；不把相近关键词、合法 citation ID 或同主题资料当作充分支撑。
- **目标与难度**：符合该需求及目标认知任务，难度来自推理与应用，而非缺条件、长句或生僻名词。
- **语言与可读性**：按目标语言输出，术语自然，段落/枚举清晰；不考察资料中没有提供的细节。

每个失败可以有多个标签，并记录一个主要诊断：`retrieval_missing`、`context_truncated`、`premise_incomplete`、`answer_incorrect`、`answer_ambiguous`、`explanation_inconsistent`、`citation_unsupported`、`difficulty_mismatch`、`format_invalid`、`reviewer_disagreement`、`provider_error`、`timeout`、`budget_exhausted`、`cancelled`、`unknown`。模型自报失败原因与独立审核诊断分别保留；无法确定时选 unknown，不强行归因。

## 7. 下一轮改动选择与论文表述

先完成这轮原始记录与审核，再选择影响最大的一个原因作定向修改。例如上下文有缺口时优化证据覆盖；条件遗漏时改 author contract；审核误判时改审核输入或标尺；调用耗时集中在独立题目时才进行有限并发实验。

对照实验保留 A / B 原始输出，使用相同需求、资料与预算；按学习需求配对分析。改善交付体验和提升内容质量是两个目标，不能通过放宽标准后只报告“通过率提高”。这轮可用于论文的方法设计、错误分类和预实验章节，最终教育效果结论仍需要独立课程/人工评审或学习者研究。
