# 按需语义复核诊断

本轮复核已有判级理由与样例答案，不重新定级。样例来自已见过的开发题和人工构造的改动，没有教师金标准。

实际调用 12，39418 tokens；有效 11/12。
预设类别检出 4/6；对照中同类标记 0/6，对照中任意明确问题 1/6。这些不是泛化准确率。

| 样例 | 两次状态 | 明确问题类别 |
|---|---|---|
| method_observed | correction_required / correction_required | optional_method_as_required / unsupported_claim |
| method_local_correction | no_issue_found / no_issue_found | 无 / 无 |
| termination_observed | correction_required / correction_required | unsupported_claim, internal_contradiction / unsupported_claim, internal_contradiction |
| termination_local_correction | failed / correction_required | 无 / unsupported_claim |
| causal_original | no_issue_found / no_issue_found | 无 / 无 |
| causal_inserted | correction_required / correction_required | internal_contradiction / internal_contradiction, unsupported_claim, answer_coverage_gap |

## termination_observed_1

- unsupported_claim (definite): The review claims that for a=[1], t=2 the proposed code 'returns 0 instead of the correct boundary.' But with a=[1], t=2: l=0, r=len(a)-1=0, so the while condition l<r is false immediately and the code returns l=0. The correct answer is len(a)=1, so the code does return 0, which is indeed wrong. However, the review's stated mechanism ('l stays 0 and the loop returns 0') is misleading for this input because the loop body never executes; the failure is due to the initial r=len(a)-1 convention, not the l=m non-progress case. The review conflates two distinct failure modes under one explanation.
  - 建议：Either remove the a=[1], t=2 example from R005/R011, or clarify that for a=[1], t=2 the failure is due to r=len(a)-1=0 making the loop body never execute, which is a different failure mode from the l=m non-progress case illustrated by a=[1,2], t=2.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：tasks[0].residual_work: a=[1,2], t=2 (or a=[1], t=2), where l stays 0 and the loop returns 0 instead of the correct boundary. / minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1.
- internal_contradiction (definite): R011 states 'Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0.' This is internally inconsistent: if the loop 'never makes progress' and 'l<r still holds,' the loop would not terminate and would not 'return 0.' In fact, for a=[1,2], t=2, the loop runs forever (l=0, r=1, m=0, a[0]<2, l=m=0, repeat), so the code does not return 0; it fails to terminate. The review's own task description (R003/R005) correctly identifies this as a non-progress case, but the minimum_answer explanation incorrectly says it 'returns 0.'
  - 建议：Correct R011 to state that for a=[1,2], t=2 the loop does not terminate (l stays 0, r stays 1, m stays 0), so the code fails by nontermination rather than by returning an incorrect value. Alternatively, use a=[1], t=2 as the failing input, where the code returns 0 instead of 1 due to the initial r=len(a)-1 convention.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1.

## causal_original_1

本次未发现具体问题；不等于证明判级正确。

## method_local_correction_1

本次未发现具体问题；不等于证明判级正确。

## termination_local_correction_1

- unsupported_claim (definite): The task residual_work claims a=[1], t=2 is a failing input that 'exits immediately and incorrectly returns 0 instead of 1'. But with a=[1], t=2: l=0, r=len(a)-1=0, so the while condition l<r is false immediately and the code returns l=0. The correct answer is len(a)=1, so the code does return 0 incorrectly. However, the claim that it 'exits immediately' is accurate, and the return value 0 is indeed wrong. Re-checking: this is actually correct. The issue is that the residual_work presents this as an alternative failing input, which is valid. No defect here.
  - 建议：No change needed; the alternative failing input is valid.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：tasks[0].residual_work: Must give a concrete failing input: for a=[1,2], t=2 the loop does not terminate; alternatively a=[1], t=2 exits immediately and incorrectly returns 0 instead of 1.

## causal_inserted_1

- internal_contradiction (definite): The minimum_answer directly contradicts the question's explicit requirements and the review's own task analysis. The question (S006) asks to judge whether the records support the causal conclusion, give a specific alternative explanation, and propose a more reliable design; S007 forbids fabricating actual background differences. The review's tasks[1]-tasks[3] correctly require concluding the data are insufficient, offering a hypothetical confound, and proposing random assignment. But the minimum_answer asserts the opposite: that the 30-point difference proves causation, that selection bias/background differences are impossible, that motivation cannot be an alternative explanation, and that random assignment is unnecessary. This is a direct internal contradiction between the declared tasks and the minimum_answer.
  - 建议：Rewrite minimum_answer to align with the declared tasks: state the 30-point observed difference, conclude the records are insufficient to support the causal claim due to self-selection, give a hypothetical confound (e.g., stronger motivation or prior achievement among volunteers) without asserting it as fact, and propose random assignment to treatment/control to balance confounders. Do not change the grade.
  - 题目依据：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。 / 不得编造两组实际背景的差异。
  - 初评依据：minimum_answer: 参加组通过率为90%，未参加组为60%，差30个百分点。 / minimum_answer: 这证明辅导本身造成了30个百分点的提升，因为两组都参加相同考试，所以不可能存在选择偏差或背景差异。 / minimum_answer: 学习动机不可能是替代解释。 / minimum_answer: 随机分配已无必要，继续采用自愿报名就能准确估计因果效果。
- unsupported_claim (definite): The minimum_answer asserts that the 30-point difference 'proves' the tutoring caused the gain and that selection bias or background differences are 'impossible' because both groups took the same exam. This is unsupported and contradicted by the problem facts: S002 states participation was voluntary, and S004 states no background data exist. Taking the same exam does not rule out selection bias. Similarly, claiming motivation 'cannot' be an alternative explanation is unsupported given the voluntary design.
  - 建议：Replace these assertions with the supported conclusion that the observational difference is consistent with but does not establish causation, and that self-selection is a plausible alternative explanation. Do not change the grade.
  - 题目依据：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / ”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 初评依据：minimum_answer: 这证明辅导本身造成了30个百分点的提升，因为两组都参加相同考试，所以不可能存在选择偏差或背景差异。 / minimum_answer: 学习动机不可能是替代解释。
- answer_coverage_gap (definite): The minimum_answer omits mandatory parts of the question. S006 requires (a) judging whether the records support the causal conclusion, (b) giving a specific alternative explanation, and (c) proposing a more reliable research design and explaining what it solves. The minimum_answer instead denies the need for an alternative explanation and for random assignment, so it fails to cover the required alternative-explanation and design components.
  - 建议：Add the required components to minimum_answer: a specific hypothetical alternative explanation and a randomized controlled design with an explanation of how randomization addresses selection bias. Do not change the grade.
  - 题目依据：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 初评依据：minimum_answer: 参加组通过率为90%，未参加组为60%，差30个百分点。 / minimum_answer: 这证明辅导本身造成了30个百分点的提升，因为两组都参加相同考试，所以不可能存在选择偏差或背景差异。 / minimum_answer: 学习动机不可能是替代解释。 / minimum_answer: 随机分配已无必要，继续采用自愿报名就能准确估计因果效果。

## method_local_correction_0

本次未发现具体问题；不等于证明判级正确。

## causal_original_0

本次未发现具体问题；不等于证明判级正确。

## causal_inserted_0

- internal_contradiction (definite): The minimum_answer directly contradicts the question's requirements and the review's own task analysis. The question (S006) asks to judge whether the records support the causal conclusion, give a specific alternative explanation, and propose a more reliable design; S007 forbids fabricating actual background differences. The review's tasks[1]-[3] correctly state the data are insufficient for causation, that a hypothetical confound (e.g., motivation) should be offered, and that random assignment is the better design. But the minimum_answer asserts the opposite: that the 30-point difference proves the tutoring caused the gain, that selection bias/background differences are impossible, that motivation cannot be an alternative explanation, and that random assignment is unnecessary. This is a self-contradiction between the declared tasks and the sample answer, and the sample answer would fail the question's explicit demands.
  - 建议：Rewrite minimum_answer to align with the tasks: report 90% vs 60% and the 30-point difference; state the records are insufficient to support the causal claim because participation was self-selected; offer a hypothetical confound (e.g., stronger motivation or prior preparation among volunteers) without asserting it as an observed fact; and propose random assignment to treatment/control, explaining that randomization balances confounders and removes self-selection bias. Do not change the difficulty grade.
  - 题目依据：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。 / 不得编造两组实际背景的差异。
  - 初评依据：minimum_answer: 参加组通过率为90%，未参加组为60%，差30个百分点。 / minimum_answer: 这证明辅导本身造成了30个百分点的提升，因为两组都参加相同考试，所以不可能存在选择偏差或背景差异。 / minimum_answer: 学习动机不可能是替代解释。 / minimum_answer: 随机分配已无必要，继续采用自愿报名就能准确估计因果效果。

## termination_observed_0

- unsupported_claim (definite): The review's failing-input example a=[1,2], t=2 is incorrect. With l=0, r=1, m=0, a[0]=1<2 sets l=m=0, so l<r still holds and the loop repeats identically forever (nontermination), not 'returns 0'. The review's own text says 'the loop never makes progress and returns 0', which is internally inconsistent: a non-progressing loop does not return. The correct answer for a=[1,2], t=2 is indeed 1, but the code does not return 0; it hangs. The alternative a=[1], t=2 also loops forever (l=0, r=0? no: r=0, l=0, l<r false, returns 0, which is correct for t=2 since no a[i]>=2, so that example is not a failure at all).
  - 建议：Replace the failing-input example with one where the loop terminates but returns a wrong value, e.g. a=[1,2,3], t=2: l=0,r=2,m=1,a[1]=2>=2 so r=1; l=0,r=1,m=0,a[0]=1<2 so l=0; l<r still holds and loops forever. To get a terminating wrong answer, use a case where l=m does not occur, e.g. a=[1,3], t=2: l=0,r=1,m=0,a[0]=1<2 so l=0, loops forever. A genuinely terminating wrong-answer case: a=[1,2], t=3: l=0,r=1,m=0,a[0]=1<3 so l=0, loops forever. The cleanest fix is to state the failure as nontermination (infinite loop) for a=[1,2], t=2, and separately note that when it does terminate it can also return a wrong index, e.g. a=[2,3], t=2: l=0,r=1,m=0,a[0]=2>=2 so r=0, loop ends, returns 0, which is correct; a=[1,2,3], t=2 loops. Use a=[1,2,3,4], t=3: l=0,r=3,m=1,a[1]=2<3 so l=1; l=1,r=3,m=2,a[2]=3>=3 so r=2; l=1,r=2,m=1,a[1]=2<3 so l=1; loops forever. So the review should describe the failure as nontermination, not as returning 0.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：tasks[0].residual_work: a=[1,2], t=2 (or a=[1], t=2), where l stays 0 and the loop returns 0 instead of the correct boundary. / minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1.
- internal_contradiction (definite): R011 asserts both that 'the loop never makes progress' and that it 'returns 0'. These are contradictory: if the loop never makes progress and l<r remains true, the while loop does not exit and the function does not return. The review's own task description (R003/R005) frames this as a 'non-progress case', which is consistent with nontermination, not with returning 0.
  - 建议：Reword R011 to say the loop does not terminate (infinite loop) for a=[1,2], t=2, rather than claiming it returns 0. If a terminating wrong-answer example is desired, supply a distinct input where the loop exits with an incorrect index.
  - 题目依据：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 初评依据：minimum_answer: Initially l=0, r=1, m=0; a[0]=1<2 so l=m=0, and l<r still holds, so the loop never makes progress and returns 0, but the correct answer is 1.

## method_observed_0

- optional_method_as_required (definite): 题目 S003 明确说“可自行选择证明方法，不要求特定方法”，但 decision.reason 开头（R012）写成“该题要求用数学归纳法证明……”，把可选方法表述为题目要求，与 S003 冲突。
  - 建议：将 R012 中“该题要求用数学归纳法证明”改为“该题要求证明奇数和公式（可用数学归纳法等方法）”，保留原难度判断不变。
  - 题目依据：可自行选择证明方法，不要求特定方法。
  - 初评依据：decision.reason: 该题要求用数学归纳法证明一个未做过的奇数和公式，并解释有限验证的不足。

## method_observed_1

- unsupported_claim (definite): R012 断言“该题要求用数学归纳法证明”，但 S003 明确说明“可自行选择证明方法，不要求特定方法”。题目只要求给出对任意 n 成立的证明，并未强制使用数学归纳法；把归纳法说成题目要求，与题面矛盾。
  - 建议：将 R012 改为“该题要求证明一个未做过的奇数和公式，并解释有限验证的不足；方法开放，可用数学归纳法等。”，不改变 medium 判定。
  - 题目依据：可自行选择证明方法，不要求特定方法。
  - 初评依据：decision.reason: 该题要求用数学归纳法证明一个未做过的奇数和公式，并解释有限验证的不足。
