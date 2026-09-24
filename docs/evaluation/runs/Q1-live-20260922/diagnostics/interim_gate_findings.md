# Q1 运行中检查器诊断

快照时间：2026-09-22T12:11:05.304370+00:00。已完成案例 17，尝试 33。

本记录只读已导出的原始证据，没有更改实验代码、原始结果或已保存的模型响应。以下复核布尔值与文字均为模型检查器自述，不代表独立答案正确性。

## 1. 无计算题被工具检查拦截

共观察到 6 次尝试、3 个案例存在该矛盾：solver 声明无需计算、工具请求和执行结果均为空，但 review 将工具相关布尔值设为 false。

| 案例 | 尝试 | 状态 | false 字段 | 主机拒绝原因 |
|---|---:|---|---|---|
| db_serialization_retry_en | 1 | rejected | tool_inputs_match_question, calculations_verified | tool_inputs_match_question, calculations_verified, difficulty_mismatch |
| db_serialization_retry_en | 3 | rejected | tool_inputs_match_question | tool_inputs_match_question, difficulty_mismatch |
| db_transaction_snapshot_zh | 1 | rejected | tool_inputs_match_question | tool_inputs_match_question |
| db_transaction_snapshot_zh | 2 | rejected | tool_inputs_match_question | tool_inputs_match_question |
| db_transaction_snapshot_zh | 3 | rejected | tool_inputs_match_question | tool_inputs_match_question |
| os_interrupt_deadlock_zh | 1 | rejected | tool_inputs_match_question | tool_inputs_match_question |

其中 `db_transaction_snapshot_zh` 的三次尝试均只有 `tool_inputs_match_question` 导致拒绝；review 的其他布尔值均为 true，issues 为空，反馈明确说明无需工具或无计算。这能证明检查契约中的适用性处理存在矛盾，不能仅据此宣称三道候选题均已独立验证正确。

## 2. os_interrupt_deadlock_en 为什么失败

这是复核响应字段不符合契约，不是本次 API 服务中断。该任务五次调用（embedding、rerank、三个 text）均成功返回。review 使用了 evidence_ok、mcq_key_ok、explanation_ok、sources_ok、numeric_ok、context_ok 等替代字段，缺少 explanation_correct、source_supported、tool_inputs_match_question、calculations_verified、distinct_from_previous 五个必填字段。native 路径没有启用现有 Harness 专用的一次 schema 修复，因此直接进入 protocol_failure。

solver 同时将目标 hard 评为 medium，但当前终止的直接原因是 review schema 无效；不能将其归结为难度不合格，也不能将 review 的正面文字当作通过核查。

## 3. 可定位的代码根因

- `Review` 全部使用 StrictBool，没有不适用状态（`app/generation_agent.py:68–79`）。
- system prompt 已写明无计算可以 vacuously true，实际返回仍有 false / 不适用语义冲突（约 1207–1209 行）。
- 1229 行把所有 false 布尔值无条件收集为失败；1271–1274 行进一步生成“工具输入不匹配”的修复提示，虽然工具根本没执行。
- `checked_role_call` 约 321–325 行仅为 deepseek_harness 允许一次完整 JSON 的 schema 重评估；native 路径直接抛异常。

## 4. 最小修复设计（尚未实施）

1. 为工具检查补充明确适用性，可用通过 / 失败 / 不适用三态。只有 solver、reviewer 对无需计算一致、没有工具请求/结果、没有主机数值触发时才允许不适用；矛盾先做一次有上限的独立重评估，不直接把 false 改成 true。实际算题、缺失工具和不匹配仍必须失败。
2. 将现有一次全新 schema 重评估能力独立成运行时无关的冻结策略，native 也可使用。保留原响应、校验诊断和两次调用记录；不把旧别名机械翻译为正确性通过。网络错误不自动重试。
3. 修复提示根据真实缺陷生成。无工具时不得宣称工具输入不一致；保留每次判断供回放。

## 5. 其他值得独立复核的实例

`os_lost_wakeup_en` 第 2 次出现 answer_correct / explanation_correct / source_supported=false；第 3 次虽然被保留为 adjusted，但 reviewer 明确反驳独立 solver 的答案。这属于语义判断分歧，不能因为最后通过就忽略，应检查实际题干、选项及引用原文。

`net_cumulative_ack_en` 的题目包含序号区间推导，但 solver 和 reviewer 均声明无需计算。当前主机的数值补充触发只覆盖带数字的 RR/STCF 调度词，未普遍证明网络序号算术被工具校验。此现象是能力边界，不在本记录中直接判为答案错误。

JSON 中保存每个实例的 JSON pointer、模型字段、反馈、主机拒绝原因及源文件 SHA-256，可供后续对照；本次只做小样本运行中诊断，不报告优化提升率。
