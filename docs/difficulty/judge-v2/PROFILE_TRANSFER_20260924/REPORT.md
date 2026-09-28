# 难度评委 v4 固定题诊断

本轮为单一冻结评委的新题诊断，使用独立上下文。不是完整 Harness 端到端复现。

实际调用 24；报告 token 69093；缺失费用记录 24 条。
没有教师标签和学生实测数据：准确率、加权 κ 均为 null，不能宣称新方法更准确。

| 方法 | 有效/计划 | 稳定题数 | 明确等级且稳定 | 弃判次数 |
|---|---:|---:|---:|---:|
| v4 | 24/24 | 9/12 | 8/12 | 5 |

稳定题数包含稳定弃判；明确等级且稳定另列。任何一次失败都不能计为稳定。有限次重复是小样本诊断。

| 题目 | v4 |
|---|---|
| odd_sum_intro | uncertain, medium |
| odd_sum_practised | easy, easy |
| odd_sum_paraphrase | medium, uncertain |
| lower_bound_intro | hard, hard |
| lower_bound_practised | medium, medium |
| lower_bound_paraphrase | hard, hard |
| training_claim_intro | medium, medium |
| training_claim_practised | medium, medium |
| training_claim_paraphrase | medium, medium |
| station_accounts_intro | uncertain, uncertain |
| station_accounts_practised | medium, medium |
| station_accounts_paraphrase | medium, uncertain |

## 对照检查

仅比较两次都有明确等级的配对；弃判和失败不可算通过。这些是开发者预设的行为假设，不是教师金标准。

- v4: odd_sum_intro → odd_sum_practised (nonincrease): 1/1 可比较配对通过，共 2 对。
- v4: odd_sum_intro → odd_sum_paraphrase (equal): 0/0 可比较配对通过，共 2 对。
- v4: lower_bound_intro → lower_bound_practised (nonincrease): 2/2 可比较配对通过，共 2 对。
- v4: lower_bound_intro → lower_bound_paraphrase (equal): 2/2 可比较配对通过，共 2 对。
- v4: training_claim_intro → training_claim_practised (nonincrease): 2/2 可比较配对通过，共 2 对。
- v4: training_claim_intro → training_claim_paraphrase (equal): 2/2 可比较配对通过，共 2 对。
- v4: station_accounts_intro → station_accounts_practised (nonincrease): 0/0 可比较配对通过，共 2 对。
- v4: station_accounts_intro → station_accounts_paraphrase (equal): 0/0 可比较配对通过，共 2 对。

正式判级流程未切换；下一步需要教师独立标注、仲裁以及与参照题分离的测试集。
