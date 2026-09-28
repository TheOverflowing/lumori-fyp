# 容量修正后的离线原始响应回放

没有新增 API 调用。下方 v4 指 v4.1 校验器对原始 v4 回复的回放；v3 沿用父试验记录。不是一轮新的在线实验。仅引用数量上限由 5/6 提高到 64，等级、原文编号及理由没有编辑。

# 难度评委 v3 / v4 固定题诊断

本轮比较评估流程，两个版本使用同一模型与参数、独立上下文。不是不同模型评委实验，也不是完整 Harness 端到端复现。

实际调用 0；报告 token 0；缺失费用记录 0 条。
没有教师标签和学生实测数据：准确率、加权 κ 均为 null，不能宣称新方法更准确。

| 方法 | 有效/计划 | 稳定题数 | 明确等级且稳定 | 弃判次数 |
|---|---:|---:|---:|---:|
| v3 | 13/16 | 4/8 | 3/8 | 2 |
| v4 | 16/16 | 7/8 | 6/8 | 3 |

稳定题数包含稳定弃判；明确等级且稳定另列。任何一次失败都不能计为稳定。有限次重复是小样本诊断。

| 题目 | v3 | v4 |
|---|---|---|
| h_hint | medium, medium | medium, medium |
| m_missing | uncertain, uncertain | uncertain, uncertain |
| editor_base | medium, failed | medium, medium |
| editor_hint | failed, medium | medium, medium |
| divisibility_base | hard, hard | hard, hard |
| divisibility_hint | medium, medium | medium, medium |
| transfer_base | hard, failed | hard, uncertain |
| transfer_hint | medium, easy | easy, easy |

## 对照检查

仅比较两次都有明确等级的配对；弃判和失败不可算通过。这些是开发者预设的行为假设，不是教师金标准。

- v3: editor_base → editor_hint (nonincrease): 0/0 可比较配对通过，共 2 对。
- v3: divisibility_base → divisibility_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v3: transfer_base → transfer_hint (nonincrease): 1/1 可比较配对通过，共 2 对。
- v4: editor_base → editor_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v4: divisibility_base → divisibility_hint (nonincrease): 2/2 可比较配对通过，共 2 对。
- v4: transfer_base → transfer_hint (nonincrease): 1/1 可比较配对通过，共 2 对。

正式判级流程未切换；下一步需要教师独立标注、仲裁以及与参照题分离的测试集。
