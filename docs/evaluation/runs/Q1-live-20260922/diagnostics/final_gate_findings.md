# Q1 完整基线检查器诊断

记录时间：2026-09-22T12:18:37.280855+00:00。本文件是最终诊断补充，不替换原始指标、案例记录或运行中诊断。没有发起 API 调用。

## 完成情况与分母

- 已提交任务：24。
- 实际开始检索：23（均有查询 embedding 调用及检索记录）。
- 完整交付：20；主指标为 20/24 = 83.33%。
- 在实际开始检索的任务中交付：20/23 = 86.96%，仅作为条件统计，不能替换主指标。

## 调用账本核验

以 SQLite `mode=ro` 读取全部调用：189 次，全部 ledger.status=succeeded；其中建库 12 次，生成任务 177 次。能力分布为 embedding 35、rerank 23、text 131。

成功表示供应商适配器完成请求，不等于模型输出满足 JSON 契约，更不等于答案正确。该账本未观察到失败的上游请求。

## 最后一个任务不是供应商故障

`net_flow_congestion_zh` 的 calls=[]，agent.call_count=0，没有 retrieval。任务创建前已用 189 次，总上限 192 次，仅余 3 次。主机最低预检要求约 4 次，因此在任何模型或检索调用之前拒绝。runtime 把这种本地预算不足写成 provider_error，原始 metrics 因此标成 provider_failed。

诊断后应归为 budget_preflight_blocked / resource_limited，不能宣称 DeepSeek 或其他供应商失败。原始 metrics_summary.json 保留原样；新诊断增加更正类别。预检 4 次本身是下界，当前开启 rerank 的实际无修复路径一般需要 5 次。

| 原始分类 | 原始数量 | 诊断后数量 |
|---|---:|---:|
| strict | 15 | 15 |
| adjusted | 5 | 5 |
| check_failed | 2 | 2 |
| provider_failed | 1 | 0 |
| resource_limited | 1 | 2 |

四个未交付任务：

| 案例 | 诊断原因 | 调用数 |
|---|---|---:|
| db_transaction_snapshot_zh | na_tool_gate_exhausted | 11 |
| net_flow_congestion_zh | budget_preflight_blocked | 0 |
| net_reliable_delivery_en | per_job_call_limit | 12 |
| os_interrupt_deadlock_en | review_schema_invalid | 5 |

## 全部工具适用性矛盾

最终共 9 次尝试，涉及 5 个任务：solver.requires_calculation=false、tool_requests=[]、无工具结果，但 review.tool_inputs_match_question=false。

| 案例 | 尝试 | 额外 false 工具字段 | 主机拒绝原因 |
|---|---:|---|---|
| db_serialization_retry_en | 1 | calculations_verified | tool_inputs_match_question, calculations_verified, difficulty_mismatch |
| db_serialization_retry_en | 3 | 无 | tool_inputs_match_question, difficulty_mismatch |
| db_transaction_snapshot_zh | 1 | 无 | tool_inputs_match_question |
| db_transaction_snapshot_zh | 2 | 无 | tool_inputs_match_question |
| db_transaction_snapshot_zh | 3 | 无 | tool_inputs_match_question |
| net_reliable_delivery_en | 1 | calculations_verified | tool_inputs_match_question, calculations_verified, difficulty_mismatch |
| net_reliable_delivery_en | 2 | 无 | tool_inputs_match_question, difficulty_mismatch |
| os_context_switch_en | 1 | 无 | tool_inputs_match_question, difficulty_mismatch |
| os_interrupt_deadlock_zh | 1 | 无 | tool_inputs_match_question |

这些实例的 reviewer 文字与其布尔值冲突，常明确写“无计算”“不适用”或“vacuously satisfied”。`db_transaction_snapshot_zh` 三次都只因工具匹配 false 拒绝。`net_reliable_delivery_en` 前两轮也受此影响，随后出现 author schema / 难度设计错误，最后在第 5 次尝试复核之前达到每任务 12 次调用上限；不能把它的整个失败仅归结为一个布尔字段。

## 可复核代码根因

- `Review` 只有必填布尔字段，没有“不适用”状态；复核 prompt 虽允许无计算时返回 true，但模型仍可能用 false 表示不适用。
- 所有 false 复核字段均直接进入问题列表；工具字段为 false 时，主机进一步给出“工具输入不匹配”的误导修复指令，虽然工具未执行。
- `os_interrupt_deadlock_en` 的复核使用别名字段，缺少 5 个必填字段、额外 6 字段。5 次 API 全成功。native 没有使用 Harness 专用的一次 schema 重评估，故直接 protocol_failure。
- 本地预算预检同样写 provider_error，原始指标分类继承此混淆。完整 JSON 给出冻结代码副本路径、行号、SHA-256 与 manifest 核验结果。

## 下一轮最小修复（本次未改产品）

1. 明确工具检查适用性，处理结构化判断之间的矛盾；不直接将所有 false 改成 true，不绕过实际计算与答案核查。
2. native 共用一次有预算上限的 schema 重评估；保留原始响应、诊断及两次调用记录，不机械把别名映射为通过。
3. 区分本地预算、单任务调用限制、协议错误、上游网络/HTTP 错误；修复提示与实际原因一致。
4. 新策略必须另开冻结实验。保留本轮 24 个已提交任务、23 次检索开始、20 次交付及 189 次调用，不追加结果来改写基线。

## 证据边界

上述“正确”“有来源支持”等 reviewer 值只是模型检查器自述。本诊断确认控制流程、适用性矛盾及响应结构问题，不提供独立正确率或引用蕴含率，不推算修改后一定能交付多少题。`os_lost_wakeup_en` 的 solver/reviewer 分歧、网络 ACK 序号推导中的无工具核验边界，仍应单独做语义审核。

final_gate_findings.json 保存所有 24 个源案例文件的 SHA-256、逐尝试 JSON pointer、模型字段、主机拒绝原因及账本摘要。interim_gate_findings.* 和原始指标保持原样。
