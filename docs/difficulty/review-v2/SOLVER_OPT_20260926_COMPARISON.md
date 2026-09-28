# 分析端配置组合的配对比较

仅比较相同协议、数据和核验配置。解答检查是核验模型报告；教师准确率与独立解答正确率均未知。

| 案例 / 重复 | 配置 | 分析结构 | 核验解答检查 | 内容检查 | 最终判定 / 候选 |
|---|---|---|---|---|---|
| courier_single_failure_corrected / 0 | baseline | validated | fail | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | insufficient_evidence / [] |
| courier_single_failure_corrected / 0 | candidate | validated | not_verified | conditions_complete:not_verified, reference_correct:not_verified, explanation_consistent:not_verified, source_support:not_verified | unavailable / [] |
| courier_single_failure_corrected / 1 | baseline | validated | not_verified | conditions_complete:not_verified, reference_correct:not_verified, explanation_consistent:not_verified, source_support:not_verified | unavailable / [] |
| courier_single_failure_corrected / 1 | candidate | validated | pass | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | assessed / ['medium'] |
| laboratory_slots / 0 | baseline | validated | fail | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | insufficient_evidence / [] |
| laboratory_slots / 0 | candidate | validated | pass | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | insufficient_evidence / [] |
| laboratory_slots / 1 | baseline | validated | fail | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | insufficient_evidence / [] |
| laboratory_slots / 1 | candidate | validated | pass | conditions_complete:pass, reference_correct:pass, explanation_consistent:pass, source_support:pass | boundary / ['medium', 'hard'] |

失败、未尝试及弃判均保留。内容误放按保存的开发预期计算，即使最终弃判也记录；它不是教师金标准准确率。
各阶段耗时、调用归属、token 与费用缺项见同名 JSON；缺项没有按零计费。
