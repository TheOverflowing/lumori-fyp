# 难度评委 v2 / v3 固定题诊断

本轮比较评估流程，两个版本使用同一模型与参数、独立上下文。不是不同模型评委实验，也不是完整 Harness 端到端复现。

实际调用 32；报告 token 100674；缺失费用记录 32 条。
没有教师标签和学生实测数据：准确率、加权 κ 均为 null，不能宣称新方法更准确。

| 方法 | 有效/计划 | 稳定题数 | 明确等级且稳定 | 弃判次数 |
|---|---:|---:|---:|---:|
| v2 | 15/16 | 6/8 | 5/8 | 2 |
| v3 | 14/16 | 5/8 | 4/8 | 2 |

稳定题数包含稳定弃判；明确等级且稳定另列。任何一次失败都不能计为稳定。有限次重复是小样本诊断。

| 题目 | v2 | v3 |
|---|---|---|
| h_hint | medium, medium | failed, medium |
| m_missing | uncertain, uncertain | uncertain, uncertain |
| editor_base | medium, medium | medium, medium |
| editor_hint | medium, failed | medium, medium |
| divisibility_base | hard, hard | hard, hard |
| divisibility_hint | medium, medium | medium, medium |
| transfer_base | hard, hard | hard, failed |
| transfer_hint | medium, easy | medium, easy |

## 对照检查

仅比较两次都有明确等级的配对；弃判和失败不可算通过。这些是开发者预设的行为假设，不是教师金标准。

- v2: editor_base → editor_hint (nonincrease): 1/1 可比较配对通过，共 2 对。
- v2: divisibility_base → divisibility_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v2: transfer_base → transfer_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v3: editor_base → editor_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v3: divisibility_base → divisibility_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v3: transfer_base → transfer_hint (nonincrease): 1/1 可比较配对通过，共 2 对。

正式判级流程未切换；下一步需要教师独立标注、仲裁以及与参照题分离的测试集。

## 结果解释与当前决定

**本轮没有证明 v3 比 v2 更稳定。** v3 有效输出 14/16，低于 v2 的 15/16；完整重复一致的题数为 5/8，也低于 v2 的 6/8。因此不将 v3 自动替换到正式判级门槛。

有用进展：

- 两种方法均将无提示整除证明判 hard，给出完整证明路线后判 medium；新版没有把全部题目降成中等。
- v3 对原人文题的有效回答，明确将现成解释方向与学生仍需完成的证据组织分开，判 medium；新编辑题也能将已给出的解释与剩余应用分开。但同一题另一次 v3 调用不完整，不能按两次成功来计数。
- 未提示的转账设计在有效评审中为 hard；完整方案提示后出现 easy/medium 分歧。两次解释都识别出提示已给方法，分歧集中于“把给定证明写完整”对初学者是否仍算实质性应用。这是相邻档边界，不能用平均数或任选一次掩盖。

具体失败：

1. h_hint_v3_1 漏掉 hard_basis_quote 和 learner_relative_basis 两个必填字段。
2. transfer_base_v3_0 在标 not_supplied 的同时填入 support_quotes，违反协议；数据/约束和解法提示的区分仍可能被模型混淆。
3. editor_hint_v2_0 的引用不是题干中的精确连续原文。

三次失败都保留原始返回和验证诊断，不自动补字段、改标签或扣除分母。FAILURE_DIAGNOSTICS.json 可复核。

## 跨轮不稳定证据

原 h_hint 的 **v2 提示、模型别名、请求参数与上一轮完全相同**，上一轮 hard/hard，本轮 medium/medium。可见输入相同不保证供应商内部状态相同，原因未知；不能将该变化归功于 v3。CROSS_RUN_CHECK.json 记录比较结果。两次重复相同也不足以证明跨轮稳定。

## 新增保守汇总

本轮后加入独立汇总模块（未改变本轮请求或原始结果）：

- 全部预定重复有效、可评且等级一致，才输出“AI 暂定一致”；这仍不是准确性证明。
- 漏字段、引用无效、重复缺失、同题等级分歧都输出“待复核”，不取平均、不回退到单次成功结果。
- 两次均弃判，保留弃判及原始原因。

结果：v2 有 5 题暂定一致、1 题弃判、2 题待复核；v3 有 4 题暂定一致、1 题弃判、3 题待复核。机器可读文件为 CONSENSUS.json。新汇总规则及原协议合计 23 项本地测试通过。它提供了处理不稳定输出的明确方法，未把 AI 结果改写成教师金标准。

下一轮具体改进方向：减少重复字段、分别记录“问题给定事实”和“解法提示”，用更多预先声明学生练习经验的题检验 easy/medium 边界。继续保留本轮负面结果，不在看过标签后修改本轮测试集。当前正式 Agent、.env 和旧报告未被覆盖。
