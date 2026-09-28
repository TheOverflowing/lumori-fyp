# 旁路分歧复核

此表应在独立评审完成后查看。草稿保留等级是题目资产中的设计目标，审核页另列模型判断，学生导出不显示内部难度标签。模型判断仅是待核查线索；“一致”不等于准确，语义复核无发现不等于答案正确。

| 样本 | 原判 | 草稿保留的目标 | 旁路候选 | 原判对比 | 目标对比 | 语义复核 | 耗时 |
|---|---|---|---|---|---|---|---:|
| REAL_TASKS_20260925_R3_task_2_q1 | hard | hard | medium | disagrees | outside_candidates | correction_required | 9537 ms |
| REAL_TASKS_20260925_R4_task_1_q1 | easy | easy | easy | agrees | agrees | no_issue_found | 3662 ms |

## 分歧依据

### REAL_TASKS_20260925_R3_task_2_q1

- 原判：hard；请求目标：hard；草稿保留的目标：hard；旧门槛：strict／strict_passed=True；旁路候选：['medium']。
- 旁路依据：任务覆盖识别、因果链分析、次序约束、嵌套簿记、单/多 CPU 对比与两种防护区分。课程资料已给出关键约束（S010、S011、S012、S015）与并发来源（S014），学习者只需将这些已学概念应用到具体场景并组织论证，属于熟悉的实质性应用与证据整合，而非需要非例行策略突破的瓶颈。任务 2、3、5、6 的因果链与对比虽需独立组织，但每一步都可由已给约束直接推出，未超出已学范围。最近边界：若要求自行发现 push_off/pop_off 机制或自行推导次序约束，则偏 hard；此处均已提供，故定为 medium。
- 语义复核：[{"category": "internal_contradiction", "certainty": "definite", "question_ids": ["S033", "S030", "S031", "S032"], "review_ids": ["R006", "R022"], "explanation": "R006 states for scenario S that assertion A holds (中断处理程序等待会自死锁，故不能一直等待), but the minimum answer R022 says assertion A 不成立. The two review sections contradict each other on the same judgement.", "suggested_correction": "Align R006 with R022: in scenario S, assertion A 不成立 (本 CPU 中断处理程序若一直等待本 CPU 线程释放锁会自死锁)."}, {"category": "unsupported_claim", "certainty": "definite", "question_ids": ["S033", "S034", "S030"], "review_ids": ["R006", "R022", "R023"], "explanation": "Assertion A/B are phrased as '可以一直等待' (can wait indefinitely). The review answers '成立/不成立' without noting that '一直等待' is precisely what causes deadlock, so the assertion is false in both scenarios; the answer conflates 'can wait' with 'can wait forever'.", "suggested_correction": "Clarify that '一直等待' is false in both S and P for assertion A; only a bounded wait by another CPU's handler is possible, matching the intended deadlock analysis."}]
