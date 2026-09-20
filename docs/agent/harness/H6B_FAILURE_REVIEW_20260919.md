# H6B 独立失败审计（2026-09-19）

## 范围与结论

只读审查 `docs/agent/harness-experiments/H6B_20260919` 的冻结代码、配置、逐题证据、模型调用记录、工具审计和最终结果；本审计不调用 API、不改应用代码，也不重跑实验。本轮为中、英文各一个两题任务，使用 `supervisor_v1`、`cpu_schedule_v1`、DeepSeek `deepseek-flash`、high thinking、JSON object，单次输出上限 32,768 tokens，实验最多 28 次 API 调用，实际 23 次。

**两个任务均在第 1 题用完两次候选机会后停止，第 2 题均未执行。实际失败是题目没有满足计划要求的概念解释，并非观察到上下文超限、输出截断或已提交答案的数值错误。** 四个候选都完成计算和复核；复核所有布尔字段为 true，但 `issues` 非空，控制器按 `review_reported_issues` 拒绝，未发布任何内容。

这不能写成“4 题都算错”“中文 q1 通过”或“中文 q2 失败”。任务状态中的通用错误“第 1 题未通过答案或难度校验”也不能直接作为细分失败类型。

## 分母与实际执行范围

| 指标 | 英文 | 中文 | 合计 |
|---|---:|---:|---:|
| 计划任务数 | 1 | 1 | 2 |
| 计划题目数（有有效 brief） | 2 | 2 | 4 |
| 已派发不同题目数 | 1 | 1 | 2 |
| 候选尝试数（含重做） | 2 | 2 | 4 |
| 完成作者输出、编译、解题和复核的候选数 | 2 | 2 | 4 |
| 接受题目数（有 `accepted_asset`） | 0 | 0 | 0 |
| 已发布题目数 | 0 | 0 | 0 |
| 未派发题目数 | 1 | 1 | 2 |

两组 `q1.status=failed`，worker `dispatch_count=1`、`status=quality_failed`，内部各有两个 `rejected` attempt；两组 `q2.status=pending`、worker `dispatch_count=0`，`attempts=[]`，没有 `accepted_asset`。重做候选不等于新派发一个 worker。

可报告的比率为：计划覆盖 4/4，实际启动 2/4，已尝试题目的接受率 0/2，计划题目的交付率 0/4，完整任务交付率 0/2。不能把未执行题目放入算术正确率分母；本审计没有建立独立人工算术准确率。

## 逐题、逐次失败分类

| 任务／题目／尝试 | 观察结果 | 精确失败原因 |
|---|---|---|
| EN q1 attempt 1 | 4 个 RR 场景编译完成，解题与复核完成，难度判断 hard | brief 第 5 项要求明确解释“更小平均响应或更低切换占比不能单独证明策略对所有目标最优”；题干、参考答案及 explanation 没有这段论证。 |
| EN q1 attempt 2 | 4 个 RR 场景编译完成，难度仍为 hard | 同一解释缺项仍在。作者只把平均响应阈值从 8 改为 5，计算 workload 与场景保持不变，无法修补渲染器不生成解释段的缺口。 |
| EN q2 | 仅完成规划 | 未派发、未生成、未复核，不能判数值正确或错误。 |
| ZH q1 attempt 1 | 3 个 RR 场景编译完成，解题与复核完成，难度判断 hard | brief 第 5 项的显式取舍解释缺失；复核还认为第 3 项“切换不消耗 CPU 服务量、提前完成不占剩余时间片”在题干中表达偏隐含。后者属于要求表述充分性意见，不能直接归为数值错误。 |
| ZH q1 attempt 2 | 完成相同规格的重新生成、编译、解题与复核，难度仍为 hard | 第 5 项解释缺失再次被指出；规格 SHA 与编译资产 SHA 均和 attempt 1 完全相同。 |
| ZH q2 | 仅完成规划 | 未派发、未生成、未复核，不能判数值正确或错误。 |

四次复核中，`answer_correct`、`explanation_correct`、`source_supported`、`ambiguity_free`、`tool_inputs_match_question`、`calculations_verified`、`distinct_from_previous` 均为 true，confidence 均为 high；四次独立解题均将难度判断为 hard。控制器仍因非空 `issues` 拒绝，说明布尔正确性判断不会覆盖未解决的问题。

此处的 `quality_checks.correctness.status=failed` 是代码中的聚合门槛名称，其 `issues=['review_reported_issues']`；不能把该名称解释为“复核发现数值错误”。学生可见的编译 explanation 仅包含“服务量 + 空闲 + 切换开销 = 最终完成时刻”的恒等式。比较指标及筛选最优方案间接体现了取舍，但不能代替 brief 明确要求的解释段。

### 为什么当前重做不能解决这类缺项

本模式要求作者仅输出 CPU 规格，全部题干、答案和 explanation 由冻结渲染器生成，作者不能直接补写自由文本段落。当前 planner 却可以把“解释为何不普遍最优”等自由表述设为必需要求。于是，反馈虽然准确指出缺项，作者能修改的规格字段并不包含相应输出能力。

英文重做只改变约束阈值，中文重做返回完全相同的规格。这是“计划能力与渲染能力未对齐”的证据，不能据此归因于上下文太大或模型完全不懂调度。

### 复核及解题自由文本本身也有错误

记录复核缺项时应保留以下反例，避免把模型审核意见当成真值：

- EN attempt 1 的 `review.issues` 举例称 S4 的平均周转劣于 S3，但记录值为 S4=10、S3=45/4=11.25，因此这句比较错误。S4 因切换次数超预算而不可行，以及缺少必需解释的主结论，仍与记录相符。
- EN attempt 2 把三段“数值正确／输入匹配／约束正确”的正面核对文字也放进 `issues`。本次确有解释缺项，拒绝有依据；但这体现了 issues 字段的语义使用不稳定。
- ZH attempt 2 的独立 solver 自由文本写 q=2 有“2 次免费转换”，而同一结果为 switch_count=14、overhead=11、每次计费成本=1，且完整时间线可见 3 次免费转换（P4→P1、P1→P5、P5→P3）。这个错误属于未发布的 solver 叙述；编译答案的数字保持 14 和 11，不能把它记成已接受答案的错误。

存在工具结果时，review 收到的 `independent_solution` 只包含可解性、无歧义和是否需计算标志；上述 solver 的长篇数值叙述不会作为独立标准答案送给 review。完整记录仍保留供审计。

### 未执行 q2 的潜在规划能力不匹配

英文 q2 计划覆盖 FCFS、SJF、STCF、RR；中文 q2 要求非抢占 SJF 与 STCF 对比。冻结 CPU schema 原生支持 RR 与 STCF，当前计划验证只检查结构、槽位、难度、题型、来源和重复 brief，没有把策略选择结构化并限制在支持枚举中。因此这是已观察到的规划能力匹配缺口。

两题均没有执行，不能声称实际生成失败，也不能猜测它们会如何被作者实现。即使某个有限 workload 上 RR 可模拟某种非抢占顺序，也不能据此声称系统已原生支持任意 FCFS/SJF 比较。

## 调用、schema 与工具审计

本轮没有任何 `*_schema_repair` 阶段，schema 重评触发次数为 **0**。两个 q1 的第二次尝试是质量反馈后的完整新候选，不是 JSON 字段重评。

| 语言 | plan API | author API | solve API | review API | API 合计 | MCP CPU 工具 | MCP 来源工具 |
|---|---:|---:|---:|---:|---:|---:|---:|
| EN | 1 | 2 | 4 | 4 | 11 | 16 | 0 |
| ZH | 1 | 2 | 5 | 4 | 12 | 13 | 1 |
| 合计 | 2 | 4 | 9 | 8 | 23 | 29 | 1 |

工具数通过模型 `tool_calls` 与各阶段 `tools.jsonl` 逐项核对。29 次 CPU 工具调用是 Harness MCP 调用数，不是付费 API 调用数；也不包括宿主编译器和后续输入绑定校验执行的本地计算。

- EN 两次尝试中，solve 和 review 每阶段各调用 4 个 CPU 工具，共 16 次。
- ZH 第一次尝试 solve/review 各 3 次；第二次 solve 调用 4 次，其中 q=1 使用相同输入重复调用一次；review 调用 3 次 CPU 工具并读取一次来源。
- 第二次中文 solve 对超过 40 个区间的工具摘要重新请求相同 q=1，增加一次 API 往返，但没有获得不同规则的结果。这也解释了该阶段是 3 次 API，其他 solve/review 通常是 2 次。
- 宿主记录的 compiled/solver 场景输入绑定均通过：EN 每次 4 个，ZH 每次 3 个，共 14 个场景条目；这是重复尝试下的条目计数，不代表 14 道独立题目。
- 共有 14 个 Harness 阶段，14 个不同 session ID；最终都以 `end_turn` 完成。23 次 HTTP 全为 200，账本全为 succeeded，返回模型均为 `deepseek-flash`。
- 模型响应 finish_reason 合计 `stop=14`、`tool_calls=9`、`length=0`。本轮无输出截断、请求上限或上下文限制失败；最大单次 completion 为 21,126，低于 32,768。

## Tokens、延迟与费用

| 指标 | EN | ZH | 合计 |
|---|---:|---:|---:|
| API 调用 | 11 | 12 | 23 |
| Prompt tokens | 105,140 | 114,405 | 219,545 |
| Completion tokens | 61,786 | 67,183 | 128,969 |
| 其中 reasoning tokens | 52,093 | 57,475 | 109,568 |
| Total tokens | 166,926 | 181,588 | 348,514 |
| API duration_ms 合计（秒） | 241.152 | 263.512 | 504.664 |
| 缺失 token 记录的调用 | 0 | 0 | 0 |
| 缺失费用记录的调用 | 11 | 12 | 23 |

Reasoning tokens 是 completion tokens 的子集，不能再次加到 total。API duration 总和不包含所有 Harness 启动与本地计算耗时，不是完整用户等待时长或并发性能指标。费用全部缺失；summary 中 `known_cost_usd=0` 仅表示已知费用累加结果，不能称为免费或实际花费为零。

| 阶段 | API 调用 | Total tokens | Reasoning tokens |
|---|---:|---:|---:|
| 主计划 | 2 | 10,236 | 4,062 |
| 作者 | 4 | 80,123 | 53,010 |
| 独立解题 | 9 | 99,476 | 20,950 |
| 复核 | 8 | 158,679 | 31,546 |

逐阶段模型响应 usage 与 23 条调用账本的 usage 按执行顺序逐字段一致。本轮不是“格式修复后准确率提高”的证据，也不是增大 token 上限单独作用的消融实验：规划、上下文隔离、作者无工具及 token 预算一起改变。

## SHA 与冻结材料核对

- Manifest `code_sha256` 列出的 **19/19** 个代码快照，逐文件原始字节 SHA-256 均匹配 `code/` 内容。
- `frozen_cases.json` 按实验脚本规定的 canonical JSON 编码核对，SHA 为 `fd9034329284ff80b9501944246a2c1c41a0ea4e93046466702c827fd0f45d81`，与 manifest 一致。
- 数据集按相同 canonical 编码核对，SHA 为 `ed1b397bc4e61a5ddd19a8ed4991e219c28c79cf83356e804ef6a9212c353d5b`，与 manifest 一致。
- Canonical 算法为 `json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()` 后取 SHA-256，保留 JSON 默认分隔空格；不应把漂亮打印文件的原始字节 hash 或无空格 JSON hash 与该字段直接比较。

| 审计结果文件 | 原始文件 SHA-256 |
|---|---|
| `deepseek_harness__cpu_en_hard.json` | `f3d1f10d9a25828526391d14a8ad03666db6d9cb8f3ebd422de80507e31b1259` |
| `deepseek_harness__cpu_zh_hard.json` | `42ebf164c55448b42b1126cafac04d80cef97a9476d66f4c08bfd43e4beb7f28` |

中文两个候选的 `spec_sha256` 均为 `3444c7d0c2b8e97d6629069d85274c4bb8937e090a07f8bb71033a935513d497`，`compiled_asset_sha256` 均为 `74116b5198b75dd6c788c53c0e2f86e11b27bd1a7c5f208fdc9583ba212b1daf`。英文两个规格和编译资产 hash 不同，差异包含约束阈值 8→5，不是新 workload。

## 下一轮可检验方向

1. 把 planner 的策略、指标和必需任务编码为 CPU schema 可满足的结构化要求，并在启动 worker 前检查能力匹配。把自然语言“或”选项显式选择后冻结，避免隐含扩大履约范围。
2. 对“解释指标取舍”增加受工具事实约束的简短解释输出能力，或在本模式中禁止规划超出固定渲染器的任务；不能让无权输出该段落的作者反复重做同一规格。
3. 将逐项履约结果与算术、难度结果分开记录。复核 `issues` 只收具体未满足项，保留失败与不可靠诊断的原文；用本轮固定案例测试缺项检出和修复能力，再另做新题完整交付测试。

本审计确认的是记录、流程和失败分类。模型复核通过的布尔判断不是人工真值；固定课程片段绕过 RAG，不测召回；两门语言样本也不足以推导整体准确率或教育实测难度。
