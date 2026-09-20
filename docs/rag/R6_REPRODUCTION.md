# R6 查询改写实验：离线复现与证据阅读说明

文档日期：2026-09-19。对应归档：`docs/rag/r6-experiments/20260919T153526570109Z/`。本文仅说明如何读取和重建已保存的实验记录，不发起新的模型调用，也不改变冻结协议、脚本或默认检索策略。

## 1. 本轮实际比较什么

本轮使用旧 R5 公开软件主题来源中的 20 个双语问题族、40 条查询，以及 207 篇原文、236 个切片。口语变体由 AI 撰写并由另一位 AI 核验者仅对照问题审核，不是真实用户日志或教师人工标注。既有答案位置作为暂定相关性依据，不等于穷尽所有相关材料的课程金标。

四个条件的含义如下。

| 条件 | 首阶段查询 | 重排查询 | 比较用途 |
|---|---|---|---|
| `canonical` | 原始基准问句 | 原始基准问句 | 整体参照；不参加策略选择 |
| `original` | 合成口语输入 | 合成口语输入 | 口语基线 |
| `rewritten` | 合成口语输入的同语言改写；不能使用时回退 | 合成口语输入 | 隔离首阶段改写的影响 |
| `dual` | 原文与改写两路交替合并、去重、总计最多 20 候选 | 合成口语输入 | 检验两路召回是否补充证据 |

`canonical` 应写作“原始基准问句参照”，不能称为“人工纠错规范金标”。原始问句自身可能存在歧义或措辞问题。`original − canonical` 的差值同时包含首阶段和重排问题文本的变化，不能全部归因于第一阶段召回；后面三臂固定口语原文作为重排查询，才是本轮首阶段策略消融。

冻结划分为 dev 5 个问题族、10 条查询、5 个来源连通分量；test 15 个问题族、30 条查询、12 个来源连通分量。每条查询测 `mixed` 与 `cross`，因此每臂为 dev 20 / test 60 个场景；四臂合计为 80 / 240 条逐场景记录。问题族和场景不是相互独立样本。这里的 test 是本轮局部保留部分，旧 R5 来源已被使用，不能宣称为整个项目从未接触的最终测试集。

## 2. 只离线重建报告

等待本轮完整结束、`dev-per-query.json`、`test-per-query.json` 和 `selection-lock.json` 均存在后再执行。正在写入的 `calls.json` 或未完成的 test 文件不构成完整归档；不要用空列表补齐，也不要删除失败记录来绕过检查。

报告脚本只依赖 Python 标准库，不需要 API 密钥，不读取 `.env`，也不导入实验 runner。建议复制归档后使用归档中的代码，这样报告重建不会覆盖原始交付文件。以下命令在项目根目录执行，路径中的实验编号固定为本轮编号：

```sh
R6_RUN="$PWD/docs/rag/r6-experiments/20260919T153526570109Z"
R6_REVIEW=$(mktemp -d "${TMPDIR:-/tmp}/lumori-r6-report.XXXXXX")
cp -R "$R6_RUN/." "$R6_REVIEW/"
python3 "$R6_REVIEW/code/scripts/r6_report.py" --run "$R6_REVIEW"
```

已有项目虚拟环境时，也可以用 `.venv/bin/python` 代替 `python3`。这一步是从逐场景结果重新聚合报告与统计区间，不是重新运行检索器，不是重新评分原始响应，更不是重新调用模型。不要为重建报告执行 runner 的 `rewrite`、`embed` 或 `rerank` 阶段，它们属于在线实验步骤。

报告的直接输入有七个文件：

| 输入 | 内容 |
|---|---|
| `dataset.json` | 原始问题、口语变体、语言、问题族、划分及文档 |
| `rewrites.json` | 每条查询的真实改写响应、状态、校验信息及可见输出 |
| `components.json` | dev/test 中问题族到来源连通分量的映射 |
| `selection-lock.json` | 仅按 dev 确定的策略，以及 dev 汇总内容哈希 |
| `calls.json` | 去重后真实请求的状态、用量和耗时 |
| `dev-per-query.json` | dev 四臂逐场景结果，包括失败与回退 |
| `test-per-query.json` | test 四臂逐场景结果，包括失败与回退 |

生成文件包括 `report.md`、`decision.json`、`dev-report-summary.json`、`test-report-summary.json`、`dev-metrics.csv`、`test-metrics.csv`、`test-changes.csv` 和 `test-failure-attribution.json`。其中 `*-report-summary.json` 是报告专用聚合，不覆盖 runner 的 `dev-summary.json` / `test-summary.json`，也不改写选择锁。

报告脚本会检查四臂的 `(query_id, mode)` 配对、查询元数据和每条查询的两种场景是否完整，并重新计算 dev 的选胜结果。必需字段或配对缺失会报错，而不是静默缩小分母。最终流程失败的 `budget_hit` 和 `mrr5` 必须显式为零。保存的失败记录在不同指标中仍有不同含义，见第 5 节。

## 3. 归档完整性与选择顺序

`freeze.json` 保存联网前的数据、协议、文档向量和代码 SHA-256。`code/` 是实际冻结代码；复现时应读取它，而不是假设当前工作区中的同名脚本始终相同。下列只读检查可在上一节复制完成后执行，不会导入 runner 或访问网络：

```sh
python3 - "$R6_REVIEW" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
load = lambda path: json.loads(path.read_text(encoding="utf-8"))
digest = lambda data: hashlib.sha256(data).hexdigest()
freeze = load(run / "freeze.json")
for name, expected in freeze["files_sha256"].items():
    assert digest((run / name).read_bytes()) == expected, name
for name, expected in freeze["code_sha256"].items():
    assert digest((run / "code" / name).read_bytes()) == expected, name
lock = load(run / "selection-lock.json")
summary = load(run / "dev-summary.json")
encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
assert lock["basis"] == "dev_only"
assert digest(encoded) == lock["dev_summary_sha256"], "dev-summary.json"
print("Frozen files, archived code and dev summary lock verified.")
PY
```

上述检查验证归档内部的一致性，不是外部数字签名或第三方时间证明。联网后新生成的逐场景记录不在初始 `files_sha256` 范围内；报告的 `decision.json/input_sha256` 另存七个直接输入的内容哈希，可用于核对重建报告所读取的版本。

选择规则固定为：只在 `original`、`rewritten`、`dual` 中，按 dev 的预算 Hit、MRR@5 依次降序；完全相同时按上述顺序优先原文。先产生 `selection-lock.json`，再运行 test 候选与排名。报告重算 dev 选择并验证 `basis` / `selected_arm`；上一段额外验证选择锁引用的 dev 汇总哈希。保留部分的最高分不能反向修改已锁定策略、改写提示词、预算或样本。

## 4. 指标的精确定义

`mixed` 使用全部双语资料；`cross` 仅使用与查询语言不同的资料。因此 `cross:en` 是英文查中文，`cross:zh` 是中文查英文。`language:en/zh` 同时汇总该语言的两种资料场景，不等于跨语言结果。

命中依据是归档 `gold-spans.json` 中已知答案在原文内的字符区间。对来自同一原文的返回切片，先计算它们与答案区间的交集并合并覆盖；完整覆盖至少一个已知答案区间才记命中。不同原文之间不拼接答案区间。

| 字段 | 逐场景定义与边界 |
|---|---|
| `candidate_hit20` | 最多 20 个首阶段候选的联合区间完整覆盖至少一个已知答案 span。相邻候选可以联合完成覆盖。 |
| `candidate_single_chunk_hit20` | 至少一个候选单独完整覆盖已知答案 span；作为额外诊断保存在逐场景记录中，不能与上一项混用。 |
| `top5_hit` | 重排后前五个切片的联合区间命中，不加最终 1024-token 预算约束。 |
| `budget_hit` | 由重排结果组装的最终上下文在 1024 个源文本 Qwen token 预算内，联合区间完整命中至少一个已知答案 span；本轮主指标。 |
| `mrr5` | 重排前五名中，第一个能够**单独**完整覆盖已知答案 span 的切片排名倒数；没有则为零。因此联合覆盖命中并不保证 MRR 非零。 |
| `context_tokens` | 最终上下文使用的源文本 Qwen tokenizer token 数，不等于 DeepSeek 账单 token 或完整生成提示词长度。 |
| `stage_sum_estimate_ms` | 根据归档 API 耗时及本地排序耗时构造的阶段延迟估计；不包含真实在线队列、并发服务压力或完整生成步骤。 |

各 Hit 汇总是场景命中率，不是覆盖全部相关段落的严格 Recall，也不是生成答案正确率。MRR@5 同样只对已知答案 span 定义相关性。不能把 R6 与使用不同资料、问题或度量的历史 R1–R5 百分比直接相减形成“持续提升曲线”。

三项主要配对差值是 `original − canonical`、`rewritten − original`、`dual − original`。每个来源连通分量内保留中英文及两种场景，对**整个分量**有放回抽样 2,000 次，随机种子 20260919，再计算按场景数加权的平均差。test 的抽样单位为 12 个来源分量，不是 60 个相互独立场景。95% 区间为探索性的百分位 bootstrap 区间，没有多重比较校正；包含零不代表已经证明两种策略等效。

阶段延迟还需要区分分支依赖：`rewritten` 先改写再编码，回退时可能额外读取原文编码；`dual` 的依赖估计使用原文编码与“改写后编码”两条路径的较大值，而不是把所有并行可能性都重复相加。接口去重复用和离线批处理的墙钟时长另记，不能将场景阶段估计视为已实测的在线端到端 p95。

## 5. 三类失败和回退必须分开

本轮已完成的改写阶段可直接从 `rewrites.json` 核实：40 条响应全部为 HTTP 200；33 条通过机械校验，7 条被标为 `failed`，七条校验码均为 `rewrite_clarification_must_preserve_input`。它们的输出表示需要澄清，但未按协议原样保留口语输入，因此被本地校验器拒绝。**这七条不是 HTTP 失败。** 不得将 33/40 写成“模型语义正确率”，也不能将 7/40 写成“API 网络失败率”。

| 层次 | 读取字段 | 应如何解释 |
|---|---|---|
| HTTP / 传输 | `http_status`、`error_type`、响应文件 | HTTP 200 只说明收到成功 HTTP 响应；超时或非 200 另行统计。 |
| 输出结构与约束校验 | `status`、`validation_error`、`result`、`visible_output` | HTTP 200 后仍可能因 JSON、字面量保留、澄清原样返回等校验失败而被拒绝。 |
| 改写分支回退 | `rewrite_fallback`、`fallback_reason` | 改写失败、需要澄清、改写向量失败时，回退到原文候选；有回退不一定意味着检索失败。 |
| 最终检索流程 | `*-per-query.json` 中 `status`、`budget_hit`、`mrr5` | 无候选或重排失败会使最终证据命中和 MRR 为零，并保留分母；已经取得的候选覆盖仍可非零。 |

对于被校验拒绝的响应，验证后的 `result` 可能不存在，但 `visible_output` 仍保存模型原始可见输出。仅统计 `result.needs_clarification` 会漏掉“模型提出澄清但违反原样保留要求”的情况，应结合 `validation_error` 与可见输出审阅。AI 语义复核应另存，不修复本轮输出后重新计算原实验分数，也不伪装成人类标注。

`calls.json` 和报告费用表的 `failures` 以调用记录 `status` 判定，可能包括 HTTP 200 后的本地校验失败。报告中的“失败次数”不能自动替换为“HTTP 错误次数”。`test-failure-attribution.json` 按最终流程的双方成功、原文失败、候选策略失败、双方失败拆分净命中变化；它没有穷尽所有上游原因，仍需顺着下节的日志核查。成功配对子集是事后诊断，不替代包含失败的主要结果。

## 6. 从一项异常追溯到哪个文件

| 需要回答的问题 | 优先读取 | 后续追溯 |
|---|---|---|
| 问题原文和口语变体是否保持含义 | `query-authoring.json`、`query-audit.md`、`dataset.json` | 原始出处与 AI 核验范围；保留既有歧义，不事后删题。 |
| 改写模型实际看到了什么 | `rewrite-inputs.json` | 只有口语查询及语言；`rewrite-audit-inputs.json` 用于后续独立查询审核，不能视为模型检索输入。 |
| 改写输出为什么被拒绝 | `rewrites.json` | `response_file` 指向 `responses/*.json`；对照 `visible_output`、`validation_error` 和原始输入。 |
| 查询编码是否成功 | `query-embeddings.json` | 按 `query_id:canonical/original/rewritten` 查状态及响应；不能使用的改写可能根本没有独立向量请求。 |
| 首阶段实际召回了哪些片段 | `dev-candidates.json` / `test-candidates.json` | `ids`、`request`、`request_sha256`、`fallback_reason`、`original_branch_unavailable`；再对照 `chunks.json`。 |
| 重排是否失败、是否共享请求 | `dev-rerank.json` / `test-rerank.json` | 按候选记录中的 `request_sha256` 查响应；完全相同请求会去重，失败或成功结果也可能复用。 |
| 最终排名、预算与单题分数 | `*-rankings.json`、`*-per-query.json` | `context` 保存所用原文区间；对照 `gold-spans.json` 与原文，不用生成模型主观判断代替现有指标。 |
| 哪些题改善、哪些题受损 | `test-changes.csv` | 同时看变化方向、两臂最终状态、重排前候选变化和回退原因。 |
| 费用或延迟为什么不同 | `calls.json`、`responses/*.json`、`stage-*.json` | 请求实际去重数、返回用量、每次请求耗时和阶段墙钟；不按场景条数计算费用。 |

日志 `stage-rewrite-dev.json` 与 `stage-embed-dev.json` 的 `dev` 后缀来自 runner 命令行默认参数。冻结 runner 的 `rewrite` 与 `embed` 阶段实际遍历整个 40-query 数据集；不能根据后缀声称“只为 dev 改写和编码”。相反，`rank`、`rerank`、`metrics` 确实按传入的 split 执行；test 排名仍要求先存在并验证 dev 选择锁。

`stage-*.json` 是成功完成该命令后的墙钟记录，不是逐请求日志。阶段文件缺失不能单凭名字断定某次网络调用从未发生；如运行中断，应检查 `calls.json` 是否仍有 `started`、缺响应或不确定状态，保留现场，不盲目重试。

## 7. 费用和复现结论的边界

费用应同时报告 `known_cost` 和 `missing_cost_count`。已知 cost 为零与完全没有 cost 字段是两种情况；全部缺失时费用合计应视为未知。DeepSeek 若只有 token 用量，应记录 token，不能将它填成零费用；接口响应中的计费字段也不能充当已核对的完整账户账单。

文档向量复用了 R5 的缓存，冻结时已核对签名、输入哈希、文件哈希和 4096 维形状；这不是本轮新产生的文档编码成本。查询向量和重排请求按本轮运行记录统计。相同模型编号不能证明远端权重或服务实现从历史实验至今完全不变。

离线重建成功支持“从保存的逐题记录可重算报告及配对统计”。它不自动证明所有上游候选生成和 span 评分已经独立重放，也不证明真实用户表现、人工语义正确率或学习效果。任何新的口语变体、提示词、预算、失败重试或语义修订应作为独立后续实验保存，而不是回填这一冻结批次。

本轮协议以归档内 `protocol.md` 为准；项目当前说明见 `docs/rag/R6_PROTOCOL_V1.md`。实际代码、选择锁和原始响应优先于口头概括，任何摘要中的“规范问题”都应理解为原始基准问句参照，而非额外人工纠错金标。

## 8. 本轮已经完成的候选与指标重放

完整实验结束后，已执行独立的 `scripts/r6_verify.py`：临时复制运行目录，阻止网络连接和 Remote 初始化，重算 80 条 dev、240 条 test 候选，随后还原原候选计时并重算指标。所有候选非计时字段、逐题指标、最终排名和汇总一致；原始 437 个既有文件与 calls.json 哈希未变，新 API 调用数为零。

验证记录位于 `r6-experiments/20260919T153526570109Z/offline-verification.json`，重放文件位于 `r6-replays/20260919T154540512565Z/`。这比第 2 节的仅重建统计报告多验证了本地排序与span评分；仍不等于重新请求远程模型、重新验证语义标签或获取独立测试样本。
