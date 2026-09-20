# H6C 双题主计划失败复核 — 2026-09-19

结论：H6C 在第一次主计划调用后停止，**没有创建题目 worker，也没有交付任何题目**。直接失败原因是 q1 的第四条要求含 **310 个字符**，超过严格契约的 300 字符上限。另外，q2 规划了当前 worker 不支持的 MLFQ、优先级、主动让出 CPU 和公平性／最大等待约束；这是独立发现的能力匹配问题，不能把它说成此次控制器已经检测并拦截的原因。

## 冻结证据

- 档案：[H6C 英文案例](../harness-experiments/H6C_20260919/deepseek_harness__cpu_en_hard.json)。SHA-256：`a13927521cb5cae0daed3c5b454a189c8206519888dfdfde8aa492c94575700d`。
- 计划版本：`question-planner-v1-20260919`；Harness adapter：`harness-acp-20260919-v5`。
- 用户任务为英文、2 道 hard 简答题；CPU 结构化 worker 模式为 `cpu_schedule_v1`。
- 原实验共 **1 次成功的上游调用、3,511 tokens**：prompt 2,496，completion 1,015，其中已报告 reasoning 335；费用字段缺失，不能按免费处理。
- 本次读取档案并做本地校验，没有追加模型调用，没有改应用代码、实验输出或主报告。

## 实际停止原因

模型返回完整 JSON，`finish_reason=stop`，主计划无工具可用。输出预算为 32,768 tokens，本次 completion 只有 1,015，**没有证据表明是上下文或输出 token 上限导致失败**。

本地再次对原始 plan 做严格 Pydantic 校验，得到一条错误：

```text
type: string_too_long
loc: questions[0].requirements[3]
message: String should have at most 300 characters
max_length: 300
actual_length: 310
```

长度按 Python 字符串 `len`（Unicode 码点数量）核对；本例该条为英文，既不是 310 tokens，也不是 310 个单词。各字段长度如下：

| Brief | focus 上限160 | learning_goal 上限600 | requirements 各条上限300 |
|---|---:|---:|---|
| q1 | 127 | 330 | 207、281、178、**310**、196 |
| q2 | 111 | 297 | 254、276、217、242、218 |

原归档的 `agent.status=protocol_failure`、`phase=plan`、`call_count=1`；首个规划批次为 `invalid_plan`。q1/q2 均仍为 `pending`，`attempts=[]`，没有 `brief`、`worker` 或 `accepted_asset`。作业记录为 `failed`，错误说明为计划未通过数量、难度、来源或结构校验，并停止创建未核实子任务。

本次计划契约整体通过率为 **0/1 批次**；需求长度检查是 **9/10 条合规**，不能把它替换成题目交付率。最终交付为 **0/2 题**；答案正确性和难度匹配均**未评估**，因为尚未进入出题阶段。

## 独立发现的能力匹配缺口

q1 要求比较有限 RR 参数方案，使用平均响应、平均周转和切换次数等指标，基本位于该 worker 的能力范围内。q2 则要求：

1. MLFQ 的队列层级、分层时间片、累计 allotment、降级与周期 priority boost。
2. 追踪一个反复主动让出 CPU 的进程的优先级路径。
3. 通过最大等待时间或公平性条件选择方案。

这些要求无法用本轮 CPU 规格中的 RR/STCF、单次 CPU burst、无 I/O、无优先级、五种聚合选择指标表达。材料确实讨论 MLFQ，所以它并非无来源的主题；但**资料包含某个概念，不等于当前计算器和渲染器具备对应能力**。

原请求已经携带 `worker_capabilities`，并非完全没有能力提示：

- description 明示无 I/O、无 priorities、无 STCF 切换开销。
- `selection_metrics` 列出 `mean_response`、`mean_turnaround`、`makespan`、`overhead`、`switch_count`。
- `requirement_scope` 限定有限场景、轨迹、进程指标、剩余量和指标阈值选择，禁止新策略及范围外指标。

缺口在于：该提示**没有把支持的策略正向列举成仅 RR/STCF**；“new policies” 容易被理解为“不要发明新策略”，而不是“不要使用资料里现成但工具不支持的 MLFQ”。主系统提示也没有明确 worker 能力是任务分配的硬边界。模型随后把题材多样化扩展到 MLFQ，同时忽略了已有的无优先级和允许指标限制。

长度方面，JSON schema 已声明 `maxLength=300`，故限制并非遗漏。仅把上限放在 schema 中不足以稳定约束英文长句；系统指令中的“compact / bounded”缺少显式数值目标与留余量要求。

## 后续改进的可验证假设

下一实验应保留 H6C 为失败样本，另立版本和目录，检查以下两个假设：

- **简洁目标假设：** 明确每项要求的长度限制，并建议明显短于硬上限的写作目标，能够减少完整 JSON 仍不符合字段长度的情况。不能截断字段后假装原响应合规。
- **能力约束假设：** 声明 worker 能力为权威边界，显式列举仅支持 RR/STCF、禁止 SJF/MLFQ，并要求仅从能力内选择不同的具体任务，能够减少无执行能力的主计划。

这两项修改同时进行属于组合改进；即使下轮成功，也不能仅归因于其中一项。计划结构通过后仍需检查要求是否真实落到生成题目，不能把 source ID 合法和 JSON 合规视为任务可执行性或答案正确性的证明。
