# 按需语义复核诊断

本轮复核已有判级理由与样例答案，不重新定级。样例来自已见过的开发题和人工构造的改动，没有教师金标准。

实际调用 4，16049 tokens；有效 4/4。
预设类别检出 2/2；对照中同类标记 0/2，对照中任意明确问题 0/2。这些不是泛化准确率。

| 样例 | 两次状态 | 明确问题类别 |
|---|---|---|
| termination_observed | correction_required / correction_required | internal_contradiction / internal_contradiction |
| termination_local_correction | no_issue_found / no_issue_found | 无 / 无 |

## termination_local_correction_0

本次未发现具体问题；不等于证明判级正确。

## termination_observed_1

- internal_contradiction (definite): The minimum answer and task[0] claim a=[1,2], t=2 makes the loop 'never make progress' and 'returns 0'. The host witness shows this input actually causes nontermination (repeated state l=0,r=1,m=0), not a return of 0. The stated failing input does not match the asserted failure mode.
  - 建议：Either use a=[1], t=2 (witness: returns 0, correct 1) as the concrete failing input, or describe a=[1,2], t=2 as nonterminating rather than returning 0.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1. / tasks[0].residual_work: a=[1,2], t=2 (or a=[1], t=2), where l stays 0 and the loop returns 0 instead of the correct boundary.

## termination_local_correction_1

本次未发现具体问题；不等于证明判级正确。

## termination_observed_0

- internal_contradiction (definite): The minimum_answer claims for a=[1,2], t=2 that 'the loop never makes progress and returns 0'. Host witness shows this input causes nontermination (repeated state l=0,r=1,m=0), not a return of 0. The answer conflates nontermination with returning an incorrect value.
  - 建议：State that a=[1,2], t=2 causes the loop to repeat state l=0,r=1,m=0 forever (nontermination), not that it returns 0. Use a=[1], t=2 as the example that returns 0 incorrectly.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1. / minimum_answer: Failing input: a=[1,2], t=2.
