# H3：分阶段输出字段约束的定向开发探测

日期：2026-09-19。输入：`docs/agent/harness-experiments/H3_20260919/deepseek_harness__cpu_en_hard.json` 及其保存的 MCP 审计。适配版本：`harness-acp-20260919-v2`。

本次为 Codex AI retrospective 核查，非 blind、非人类金标、非学生实测。题目在 H2 之后针对已知问题选择，属于 **targeted development probe，不是 held-out 测试**。仅只读核算并新增本报告，没有 API 调用、原始记录修改或 app 修改。

## 1. 实际执行与验证边界

v2 在每个阶段提示中列出该阶段允许的顶层字段，并对 author/review 明确禁止把 `tool_requests`、`tool_results` 附在最终 JSON 中；计算应通过 MCP 调用通道完成。该提示取自本轮代码快照 `code/app/harness_runner.py::phase_instructions`。

| 阶段 | 模型调用 | 最终停止 | 最终结构结果 | 后续路径 |
|---|---:|---|---|---|
| attempt 1 author | 3 | stop / ACP end_turn | 合法 LearningAsset，未附加顶层 tool_requests | 进入 solve |
| attempt 1 solve | 2 | stop / ACP end_turn | 合法 Solution，按契约包含 tool_requests | 判 medium，目标 hard，因此在难度门拒绝 |
| attempt 2 author | 3 | stop / ACP end_turn | JSON 内引号未转义，解析失败 | author_contract_invalid，未进入 solve |
| review | **0** | 未执行 | 无结果 | **未覆盖** |

只能说：本轮观察到 author 一次合法的顶层字段输出、solve 一次合法的顶层字段输出；第二次 author 仍发生语法错误。**本轮没有到达 review，不能说 review 的额外 tool_requests 问题已被 live 实测修复。** 更不能把 allowed-keys 提示等同于服务器强制 JSON 语法约束。

## 2. Attempt 1：C=0；D=0（本次 AI 归 medium）

C 是答案正确性（1 正确、0 存在实质错误）；D 是相对目标 hard 的难度匹配（1 符合、0 不符合）。难度判断为教学解释，置信度中，不是经验难度标定。系统实际拒绝原因只有 `difficulty_mismatch`，**没有由 review 识别以下答案错误**；这些错误来自本次额外核查。

### 题面绑定错误与正确结果

任务为 A(0,5)、B(1,4)、C(2,2)，比较 (q=2,c=1)、(q=2,c=0)、(q=3,c=1)。题面明确片尾新到达排在被抢占任务之后，即 `boundary=after`；切换期间 tail，提前完成免下一次切换，初次派发免费。

作者阶段 **3 次实际 MCP 计算都用了 `boundary=before`**。随后最终题干却写 after。solver 的 3 次计算使用 after，与题面一致。9 份 MCP 调度结果（含 attempt 2 的 3 份）本地重放均一致；错误来自题面绑定及文字答案，没有证据指向确定性工具算错。

手动关键队列：q=2 时 A 在 0–2 用完片，B 早已等待；先把 A 放回，再加入 t=2 到达的 C，所以队列是 **B,A,C**。因此 B 后应先运行 A，不能让 C 抢在 A 前。

```text
q=2,c=1:
A[0,2) S[2,3) B[3,5) S[5,6) A[6,8) S[8,9) C[9,11)
S[11,12) B[12,14) S[14,15) A[15,16)

q=2,c=0:
A[0,2) B[2,4) A[4,6) C[6,8) B[8,10) A[10,11)

q=3,c=1:
A[0,3) S[3,4) B[4,7) S[7,8) C[8,10) A[10,12) B[12,13)
```

S 表示收费切换。q=3 时 C 和 A 各只需 2<3，故后续转换免费，但仍计入不同任务转换事件数。

| 配置 | 首次运行 A,B,C | 完成 A,B,C | 平均响应 | 平均周转 | 转换事件数 | 切换耗时 |
|---|---|---|---:|---:|---:|---:|
| q=2,c=1 | 0,3,9 | 16,14,11 | 3 | 38/3 | 5 | 5 |
| q=2,c=0 | 0,2,6 | 11,10,8 | 5/3 | 26/3 | 5 | 0 |
| q=3,c=1 | 0,4,8 | 12,13,10 | 3 | 32/3 | 4 | 2 |

这里“switch intervals”在零耗时场景下表述欠精确，宜统一成转换事件数；无论理解为事件上限还是收费区间上限，本题三种配置都未超过 6，最终可行性都由响应≤2决定。按正确数值，只有 (q=2,c=0) 满足两项条件。

### 作者的具体错误

- q=2 的时间线沿用 before 的 C 优先顺序，违背最终 after 题面。
- A 被写为 0–2、9–11、14–16，总服务 **6>5**；B 最后运行 12–14 用满整片，却被说成下一次转换免费。真正应收费 14–15，然后 A 只运行最后 1 单位。
- 声称列出四段开销却有“5 switch intervals”，混淆收费区间和事件数。甚至沿用 before 时，工具实际收费也为 5，作者写 4。
- q=2,c=0 的平均响应应按 after 为 5/3，作者给 1；q=2,c=1 应为 3，作者给 2。
- 在它自己的错误数值为 2 时，又说 `2.0 is not ≤ 2 when ... strictly`，这是明确的阈值逻辑错误。**2≤2 成立**，“at most”是包含等号的限制，不能改成严格小于。

最终推荐 c=0 的方向碰巧与正确结果一致，不能抵消其数值、服务量、边界与阈值错误。

### 独立 solve 与难度

solver 的核心时间线和指标符合题面，难度判为 medium。它仍有局部说明错误：C 在 9–11 恰好用满 q=2，不能说 “faster than its 2-unit slice”；是否免收费取决于提前完成规则，不由“下一段本来从12开始”反推。其“每次切换都花整整一单位”的泛化也不适用于 q=3 的两次免费转换。调用过正确工具不保证所有解释文字都正确。

本次 AI 同样倾向 medium：题目提供了全部调度规则和指标公式，主要要求按规则模拟、比较三个配置并检验阈值；切换上限 6 对三个方案均不构成实际约束，最终选择不需要处理可行方案之间的冲突。三个长时间线和两个阈值的外观不能独自证明 hard。因此记录 C=0、D=0；不能把这次系统的难度拒绝写成“review 成功检出了作者错误”。

## 3. Attempt 2：语法失败，不给合法候选 C/D 分

第二次作者阶段成功进行了参考资料与三组 after 参数的计算，然后上游返回完整 `finish_reason=stop`，ACP 返回 `end_turn`。但是最终 JSON 的长答案字符串内出现未转义双引号，例如：

```text
... So "longer slice implies better response" is false here: ...
```

上述引号位于原始 JSON 字符串内部，没有需要的反斜杠转义。直接用标准 `json.loads` 核查，错误为：

```text
Expecting ',' delimiter: line 1 column 6356 (char 6355)
```

字符位置从 0 起计。原始内容长 9,475 字符；对应调用 completion_tokens=2,510，停止原因是 stop，不是 length。证据不支持将它归因为输出令牌截断。

原文仍完整保存在：

```text
evidence.agent.slots[0].attempts[1].author.history[0]
  .harness.model_calls[-1].response.choices[0].message.content
```

状态为 `author.history[0].status=invalid_json`，feedback 是 `author_contract_invalid` / `complete_json_object_required`，没有 `author.response`。本审查没有手工修复 JSON 后冒充系统合法输出，**不为此 attempt 赋合法作者候选 C/D 分**。应单独记录“作者结构输出失败 1 次”，并保留其调用成本与原文。

## 4. 没有观察到隐藏 provider/工具失败

- 调用账本共 **8 次**，全部 `status=succeeded`、HTTP 200；实际阶段分配为 author 3 + solve 2 + author 3。
- 三个 Harness 阶段各自保存的 model_calls 均为 succeeded，总数与账本 8 一致；最终均为 stop/end_turn，没有 review 调用。
- MCP 审计共 **11 次**：两次读取冻结参考资料、九次 CPU 计算，均返回 `ok=true`；九份计算结果重放一致。三阶段 stderr 都为空。
- 总用量 **68,649 tokens**，8 次均有 token 记录；8 次都没有费用字段。`known_cost_usd=0` 仅表示没有可求和的已知费用，**不表示免费**。

因此本轮记录里的最终失败可以具体分为：attempt 1 难度不匹配；attempt 2 返回内容不符合 JSON 语法。第二次 Harness report 的 `status=failed` 与 author 的 invalid_json 对应，不能仅见该字段就将它误报成上游网络/API失败。

原始候选记录 SHA-256：`70c5bdaac5e6387b48ad80ff75ed282f17fc2a87576216ddc24ef34538be13ec`。
