# 冻结 v4.1：新题与学习经历对照

四个新题目家族，每题三种明确学生背景，每个场景评两次。12 个背景场景不是 12 道独立新题；24 次评审也不是 24 个独立教育样本。

实际调用 24 次，69093 tokens。没有教师标签或学生作答数据，准确率为空。

有效评审 24/24；明确单一等级 19/24；候选集合重复一致 9/12。

| 题目家族 | 入门经历 | 熟练经历 | 入门经历同义表述 |
|---|---|---|---|
| odd_sum | easy/medium；medium | easy；easy | medium；easy/medium |
| lower_bound | hard；hard | medium；medium | hard；hard |
| training_claim | medium；medium | medium；medium | medium；medium |
| station_accounts | medium/hard；medium/hard | medium；medium | medium/hard；medium |

## 预先规定的对照结果

熟练经历不应升高预估难度；宽档标签相同允许。候选范围有重叠但不能保证不升高时记 unresolved_overlap，不算通过。两边都为单一等级时严格降低记 strictly_lower，否则边界不强转数字。

{
  "nonincrease": {
    "nonincrease": 5,
    "strictly_lower": 3
  },
  "equal": {
    "changed_candidates": 3,
    "equal_candidates": 5
  }
}

同义表述比较完整候选集合：两个结果虽然都显示“不确定”，候选集合不同也不算一致。失败或缺结果不会从分母消失。

## 证据边界

这是冻结协议在新材料上的前瞻开发诊断：没有把本轮题目的预期标签传入模型，没有修改评委后重跑挑选结果。新题仍由 AI 编写，表述等价也是开发假设。反应符合预期只能支持流程对这些信息有合理敏感性，不能证明实际学生难度或跨学科准确性。
