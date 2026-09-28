# 评审汇总与覆盖率

“暂定一致”仅表示所有预定重复有效且等级相同，不是准确性证明。边界候选会归为 uncertain；多弃判不能算作更强判级能力。

| 方法 | 有效评审 | 单一明确等级 | 多候选边界评审 | 候选集合一致题数 |
|---|---:|---:|---:|---:|
| v4 | 24/24 | 19/24 | 5 | 9/12 |

## 逐题合并

失败、缺失或等级分歧不会回退到单次成功判断。两次 uncertain 仅表示弃判；若候选集合不同，集合一致指标不会计为一致。

### odd_sum_intro

- v4: review_required / uncertain；观测 ['uncertain', 'medium']；候选集合 [['easy', 'medium'], ['medium']]。

### odd_sum_practised

- v4: provisional_consensus / easy；观测 ['easy', 'easy']；候选集合 [['easy'], ['easy']]。

### odd_sum_paraphrase

- v4: review_required / uncertain；观测 ['medium', 'uncertain']；候选集合 [['medium'], ['easy', 'medium']]。

### lower_bound_intro

- v4: provisional_consensus / hard；观测 ['hard', 'hard']；候选集合 [['hard'], ['hard']]。

### lower_bound_practised

- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### lower_bound_paraphrase

- v4: provisional_consensus / hard；观测 ['hard', 'hard']；候选集合 [['hard'], ['hard']]。

### training_claim_intro

- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### training_claim_practised

- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### training_claim_paraphrase

- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### station_accounts_intro

- v4: abstained / uncertain；观测 ['uncertain', 'uncertain']；候选集合 [['medium', 'hard'], ['medium', 'hard']]。

### station_accounts_practised

- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### station_accounts_paraphrase

- v4: review_required / uncertain；观测 ['medium', 'uncertain']；候选集合 [['medium', 'hard'], ['medium']]。

## v4 核对示例

以下只展示每题第一次有效评审，供查看依据；不代表另一重复成功，也不替代上面的合并结果。证据由系统按编号还原，角色分类和剩余任务仍是模型判断。

### odd_sum_intro（重复 1）

该题的核心是标准数学归纳法证明，学习者已知道基例与归纳步骤并做过简单归纳证明，因此主要工作是熟悉的归纳框架应用，属于 easy 到 medium 的边界。与 easy 的最近边界：若学习者只需复现已熟悉的归纳模板，则偏 easy；与 medium 的最近边界：需要把求和式与归纳假设正确衔接（加上 2k+1 并化简为 (k+1)²），并独立说明有限验证不足，这需要一定的代数操作与论证组织，故 medium 也合理。由于未练习奇数求和与等差数列公式，学习者不能直接套用现成求和公式，但归纳法本身是已备知识，不构成非例行瓶颈，故不判 hard。

- 作答要求：对每个正整数 n，证明 1+3+5+…+(2n−1)=n²。 / 要求给出对任意 n 成立的证明，并解释为什么只验证 n=1、2、3 不能证明结论。
  - 题目条件：对每个正整数 n，证明 1+3+5+…+(2n−1)=n²。
  - 解法提示：未引用解法提示
  - 剩余工作：需要自行构造对任意 n 的证明。可用数学归纳法：基例 n=1 时左边 1=1²；归纳步骤假设 1+3+…+(2k−1)=k²，则加上 2k+1 得 k²+2k+1=(k+1)²，完成归纳。也可用配对或图形法，但均需独立给出。
- 作答要求：要求给出对任意 n 成立的证明，并解释为什么只验证 n=1、2、3 不能证明结论。
  - 题目条件：无引用
  - 解法提示：未引用解法提示
  - 剩余工作：需要独立论证有限验证不能覆盖无穷多个 n：n=1,2,3 只验证了三个特例，命题对 n≥4 仍未证明；必须给出对所有正整数的推理（如归纳步骤）。

### odd_sum_practised（重复 1）

该题要求证明奇数求和公式并解释有限验证的局限。学习者档案明确记载其已多次独立完成该证明，能不看范例写出基例、归纳步骤，并已能解释有限举例与全称证明的区别，因此最低答案基本是已掌握内容的直接再现，无需新的策略选择或非平凡整合。最近边界为 easy 与 medium：若学习者尚未独立掌握归纳证明或需自行选择并适配方法，则可能为 medium；但此处准备情况明确，故定为 easy。

- 作答要求：对每个正整数 n，证明 1+3+5+…+(2n−1)=n²。 / 要求给出对任意 n 成立的证明，并解释为什么只验证 n=1、2、3 不能证明结论。
  - 题目条件：可自行选择证明方法，不要求特定方法。
  - 解法提示：未引用解法提示
  - 剩余工作：需写出对任意 n 成立的证明（如归纳法：基例 n=1 时左边 1=1²；归纳步骤假设 1+3+…+(2k−1)=k²，则加 (2k+1) 得 k²+2k+1=(k+1)²），并说明仅验证 n=1,2,3 只覆盖有限个例，无法排除 n≥4 时反例，故不构成全称证明。

### odd_sum_paraphrase（重复 1）

该题要求用数学归纳法证明一个未做过的奇数和公式，并解释有限验证的不足。学习者已理解归纳法如何检验基例并完成归纳步骤，也做过简单归纳题，因此主要工作是熟悉方法的直接应用：写出基例、归纳假设、代数化简 k²+(2k+1)=(k+1)²，并说明有限验证不构成证明。没有需要非平凡策略突破的瓶颈，故为 medium；不属于 easy，因为需要独立组织完整证明而非仅复述已给论证；也不属于 hard，因为归纳框架和代数化简均在其准备范围内。

- 作答要求：对每个正整数 n，证明 1+3+5+…+(2n−1)=n²。 / 要求给出对任意 n 成立的证明，并解释为什么只验证 n=1、2、3 不能证明结论。
  - 题目条件：可自行选择证明方法，不要求特定方法。
  - 解法提示：未引用解法提示
  - 剩余工作：需要自行构造对任意 n 成立的证明。可用数学归纳法：基例 n=1 时左边 1=1²；归纳假设 1+3+…+(2k−1)=k²，则加上第 k+1 项 (2k+1) 得 k²+2k+1=(k+1)²，完成归纳。也可用配对或图形法，但均需独立给出。
- 作答要求：要求给出对任意 n 成立的证明，并解释为什么只验证 n=1、2、3 不能证明结论。
  - 题目条件：无引用
  - 解法提示：未引用解法提示
  - 剩余工作：需要解释有限验证 n=1,2,3 只覆盖三个特例，不能排除某个更大的 n 失败；证明必须给出对所有正整数 n 都成立的推理，例如归纳步骤从 k 推到 k+1。

### lower_bound_intro（重复 1）

The learner can trace loops and ordinary exact-match binary search, but has not implemented or proved a first-greater-or-equal boundary search or debugged its non-progress cases. The bottleneck is not recalling binary search but recognizing the l=m non-progress bug and selecting a correct interval convention (half-open with l=m+1) that guarantees progress while preserving the boundary invariant. This is a specific nonroutine strategy/integration step rather than a familiar application, so the nearest boundary is hard rather than medium; the proof and failing-input construction are then routine once the repair is chosen.

- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / l = 0 / r = len(a) - 1 / while l < r: / m = (l + r) // 2 / if a[m] < t: / l = m / else: / r = m / return l / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Must construct a concrete failing input by reasoning about the l=m non-progress case, e.g. a=[1,2], t=2 (or a=[1], t=2), where l stays 0 and the loop returns 0 instead of the correct boundary.
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Must design a corrected boundary search, e.g. half-open [l,r) with r=len(a), m=(l+r)//2, l=m+1 when a[m]<t else r=m, returning l; must ensure progress and O(log n).
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / You may change the interval convention.
  - 解法提示：未引用解法提示
  - 剩余工作：Must prove termination (interval strictly shrinks each iteration) and correctness of the returned boundary for all arrays, including duplicates and t above all entries (return len(a)).

### lower_bound_practised（重复 1）

The learner profile states repeated implementation and proof of exactly this first-greater-or-equal binary search with half-open intervals, duplicates, no-match returns, and progress bugs from reusing the midpoint. The task asks for a counterexample, a repair, and a termination/boundary justification. The bug (l=m stalling, r=len(a)-1 preventing len(a) return) and the standard half-open repair are familiar to this learner, so the work is meaningful familiar application rather than a nonroutine bottleneck. It is above pure reproduction because the learner must construct a concrete failing input and supply the invariant argument, but both draw directly on prior preparation. Nearest boundary: easy would require only reproducing a supplied argument; here no solution is supplied, so medium is appropriate. No hard candidate, so hard_task_index is null.

- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / l = 0 / r = len(a) - 1 / while l < r: / m = (l + r) // 2 / if a[m] < t: / l = m / else: / r = m / return l / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Must construct a concrete failing input by reasoning about the buggy loop: with l=m on a[m]<t and r=m otherwise, when a[m]<t the update l=m can leave l unchanged (e.g., l=0,r=1,m=0), causing an infinite loop; also r=len(a)-1 cannot return len(a) for t above all entries. Learner must exhibit one such input and trace the failure.
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Must design a corrected O(log n) algorithm, e.g., half-open [l,r) with r=len(a), m=(l+r)//2, l=m+1 when a[m]<t and r=m otherwise, returning l. This is a genuine design choice not supplied in the text.
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / l = 0 / r = len(a) - 1 / while l < r: / m = (l + r) // 2 / if a[m] < t: / l = m / else: / r = m / return l / You may change the interval convention.
  - 解法提示：未引用解法提示
  - 剩余工作：Must prove termination (interval strictly shrinks each iteration) and the returned boundary (invariant: all indices < l have a[i]<t, all indices >= r have a[i]>=t; on exit l=r is the smallest index with a[i]>=t, or len(a) if none). No proof is supplied.

### lower_bound_paraphrase（重复 1）

The learner is familiar with exact-match binary search tracing and loop invariants, but has no practice constructing or proving a lower-bound search, especially with non-advancing loops. The bottleneck is not recalling binary search but designing a correct half-open interval update and proving the boundary invariant for all cases, including duplicates and t above all entries. This is a specific nonroutine integration/strategy task relative to the stated preparation, so it is hard rather than a familiar application. The nearest boundary is medium: if the learner had previously constructed lower-bound searches, the repair and proof would be routine application; here the missing construction/proof experience makes it hard.

- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / l = 0 / r = len(a) - 1 / while l < r: / m = (l + r) // 2 / if a[m] < t: / l = m / else: / r = m / return l / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Find a concrete failing input by tracing the supplied code, e.g. a=[1,2], t=2: l=0,r=1,m=0,a[0]<2 so l=0, loop repeats forever. This requires constructing a counterexample, not supplied.
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / You may change the interval convention. / No library search function may be used.
  - 解法提示：未引用解法提示
  - 剩余工作：Design a corrected lower-bound search retaining O(log n). A standard fix uses half-open [l,r) with r=len(a), m=(l+r)//2, if a[m]<t then l=m+1 else r=m, returning l. The learner must choose/adapt an interval convention and ensure progress.
- 作答要求：Give one concrete input where it fails, repair it while retaining O(log n) worst-case running time, and justify both termination and the returned boundary for all allowed arrays, including duplicates and a target above all entries.
  - 题目条件：An array a has at least one element and is sorted in nondecreasing order; duplicates are allowed. / Integers and indexing are exact. / Given target t, return the smallest index i with a[i] >= t, or len(a) if there is no such index. / You may change the interval convention.
  - 解法提示：未引用解法提示
  - 剩余工作：Prove termination and correctness for all allowed arrays, including duplicates and t above all entries. This requires a loop invariant and boundary argument not supplied; the learner must establish that the returned l is the smallest index with a[l]>=t or len(a).

### training_claim_intro（重复 1）

该学习者已掌握百分点差计算、相关不等于因果、混杂因素与随机分配的定义，因此计算与识别自选择混杂属于熟悉的常规应用；但题目要求把“自愿参加”这一具体情境与混杂、替代解释、随机化设计整合起来，并说明随机化解决了什么问题，这需要将已学概念迁移到项目评价情境，属于有意义的熟悉应用而非直接复述，故定为 medium。最近边界：若只需复述随机分配定义而不需针对该情境构造替代解释与设计说明，则更接近 easy；若要求自行推导选择偏倚的量化方向或设计具体随机化方案与效力分析，则更接近 hard。此处两者均未达到，故仅取 medium。

- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 两组参加同一考试，记录无缺失。
  - 解法提示：未引用解法提示
  - 剩余工作：需自行从90/100与60/100算出90%与60%，再作差得30个百分点。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需判断自愿分组下30个百分点差不能直接归因于辅导，因为存在自选择/混杂；并给出一个不编造实际背景差异的具体替代解释（如学习动机强者更可能参加辅导，动机同时提高通过率）。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。
  - 解法提示：未引用解法提示
  - 剩余工作：需提出随机分配（随机对照试验）设计，并说明随机化使两组在可观测与不可观测背景上期望可比，从而消除自选择混杂，使组间通过率差可作因果解释。

### training_claim_practised（重复 1）

该任务对已多次独立分析自愿参加项目选择偏差、能区分假设性混杂与已观察事实、并能设计和解释随机分配对照组作用的学习者而言，属于熟悉的常规应用：计算比例差是直接操作，判断因果不足、给出替代解释和提出随机对照设计均在其已掌握的概念范围内。最近边界是 easy 与 medium：虽然计算部分接近直接再现，但要求整合选择偏差、替代解释与设计说明，超出单纯检索，故定为 medium 而非 easy；未达到 hard，因为不存在需要非例行策略或全新整合的瓶颈。

- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 两组参加同一考试，记录无缺失。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需从S002的90/100与60/100计算两个通过率并求差，得到30个百分点。这是直接的比例计算，无现成结果。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需判断记录是否足以支持因果结论：因是自愿选择，存在选择偏差，不能仅凭观察差值断言因果。需明确说明数据不足以支持负责人的因果主张。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需给出一个具体替代解释，例如学习动机更强或基础更好的学生更可能自愿参加辅导，从而通过率更高；不得编造两组实际背景差异，只能作为假设性混杂提出。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需提出更可靠设计（如随机分配参加辅导与不参加辅导的对照组），并说明它通过随机化平衡可观测与不可观测混杂、消除自愿选择带来的选择偏差，从而更可靠估计因果效果。

### training_claim_paraphrase（重复 1）

该题对已掌握比例、百分点差、相关与因果、随机分配和混杂因素的学习者属于熟悉的综合应用：计算是直接的比例差，因果判断和替代解释是课堂已学概念的直接运用，随机对照设计也是已理解的随机分配含义的应用。没有需要非例行策略或新方法整合的瓶颈，因此不判为hard。与easy的边界在于：题目要求学习者自己组织因果论证、给出具体替代解释并说明设计解决了什么问题，而非仅复述一个已完整给出的论证，故略高于纯再现，定为medium。

- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 两组参加同一考试，记录无缺失。 / 除此之外没有入学成绩、学习时间或其他背景数据。
  - 解法提示：未引用解法提示
  - 剩余工作：需自行计算90/100−60/100=0.30，即30个百分点，并说明这是观察到的组间差异。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需判断自愿选择导致组间不可比，观察差异不能直接支持因果结论；须指出选择偏差/混杂（如学习动机、基础成绩）可能同时影响参加辅导与通过率，且不得编造两组实际背景差异。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。 / 不得编造两组实际背景的差异。
  - 解法提示：未引用解法提示
  - 剩余工作：需给出一个具体替代解释，例如学习动机更强或基础更好的学生更可能参加辅导，从而通过率更高，而非辅导本身起作用。
- 作答要求：”计算观察到的通过率差；判断这些记录是否足以支持该因果结论，给出一个具体的替代解释，并提出一种能更可靠估计辅导因果效果的研究设计，说明它解决了什么问题。
  - 题目条件：200 名学生自愿选择是否参加辅导：参加组 100 人中 90 人通过考试，未参加组 100 人中 60 人通过。 / 除此之外没有入学成绩、学习时间或其他背景数据。
  - 解法提示：未引用解法提示
  - 剩余工作：需提出随机对照设计：将学生随机分配到辅导组与对照组，比较通过率；说明随机分配使两组在可测与不可测背景上期望可比，从而消除选择偏差/混杂，支持因果推断。

### station_accounts_intro（重复 1）

The learner can distinguish observation from inference and quote sources, but has not practised weighing contemporaneous records against retrospective testimony or evaluating an accusation about another person's prior knowledge. Tasks 1, 2, and 4 are familiar applications of those skills: reading two supplied sources, constructing two rival explanations, and stating a calibrated conclusion. Task 3 is the bottleneck: it requires the nonroutine integration of source timing into evidential value and the explicit separation of established facts from hypotheses about the manager's knowledge, a skill the profile says is unpractised. This is not merely naming proof or evaluation; it demands a specific epistemic move (temporal proximity and outcome bias) that the learner has not rehearsed. The nearest boundary is medium: if the learner already fluently weighed contemporaneous against retrospective evidence, the whole task would be a meaningful familiar application. Because that fluency is explicitly absent, hard is also plausible, so both candidates are reported.

- 作答要求：Evaluate the later accusation using both contemporaneous sources.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must independently read both contemporaneous sources against the later accusation, identifying that the diary records the manager's forecast and the diarist's reliance, while the log records uncertainty about delivery and reopening. No supplied evaluation exists.
- 作答要求：Give a plausible explanation consistent with deliberate deception and one consistent with an honest but mistaken forecast.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must construct two rival explanations: deception (manager knew reopening was impossible yet stated a next-week finish) and honest error (manager relied on an unconfirmed delivery date and testing that later failed). Neither explanation is supplied.
- 作答要求：Explain which parts are established and which remain hypotheses, how the time at which each source was written affects its evidential value, and what additional evidence would help distinguish the explanations.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must classify what is established (the forecast, the log's uncertainty, the non-reopening) versus what remains hypothesis (the manager's knowledge and intent), explain that the contemporaneous diary and log are closer to the events while the twenty-year retrospective is memory-shaped and outcome-influenced, and propose additional evidence such as the manager's internal communications or delivery records.
- 作答要求：Conclude with a claim no stronger than the evidence permits.
  - 题目条件：" The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must formulate a calibrated conclusion, e.g. that the evidence cannot establish deliberate deception and that the accusation outruns what the sources support, without asserting either explanation as proven.

### station_accounts_practised（重复 1）

The learner profile describes repeated practice comparing contemporaneous records with retrospective testimony, separating outcome from earlier knowledge, and writing bounded arguments testing deceptive-intent versus honest-error explanations. This task asks for exactly that familiar structure: apply the two contemporaneous sources, generate two competing explanations, classify established versus hypothetical elements, assess temporal evidential value, and calibrate a conclusion. No specific nonroutine bottleneck remains after the familiar comparison and bounded-argument moves are applied. The nearest boundary is easy: the task is not mere retrieval because it requires constructing two coherent explanations and a calibrated conclusion rather than reproducing a supplied argument. It is not hard because the learner has repeatedly performed this exact kind of source-comparison and bounded-argument task.

- 作答要求：Evaluate the later accusation using both contemporaneous sources.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Must independently compare the announcement-day diary and maintenance log against the twenty-year retrospective accusation, using the stated evidentiary gap.
- 作答要求：Give a plausible explanation consistent with deliberate deception and one consistent with an honest but mistaken forecast.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Must construct two internally coherent explanations: one where the manager knowingly deceived, one where the manager honestly forecast based on incomplete information.
- 作答要求：Explain which parts are established and which remain hypotheses, how the time at which each source was written affects its evidential value, and what additional evidence would help distinguish the explanations.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Must classify what is established versus hypothetical, explain how contemporaneity versus retrospective memory affects evidential value, and propose additional evidence that would discriminate between the explanations.
- 作答要求：Conclude with a claim no stronger than the evidence permits.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Must formulate a conclusion calibrated to the evidence, avoiding a stronger claim than the sources support.

### station_accounts_paraphrase（重复 1）

The learner can cite evidence and separate observation from interpretation, but comparing contemporaneous records with a much later recollection and judging what someone previously knew are explicitly new tasks. The minimum answer requires constructing two rival explanations, classifying established facts versus hypotheses, and reasoning about temporal evidential weight and discriminating evidence. This is more than reproducing a supplied argument, since no explanation or analysis is provided, but it is a structured, scaffolded evaluation rather than an open-ended investigation. The nearest boundary is easy versus medium: the task is not mere retrieval or a familiar explanation, because the learner must independently build and weigh rival accounts. The boundary toward hard is whether the unfamiliarity of retrospective knowledge-attribution creates a genuine nonroutine bottleneck; because the prompt supplies the sources and the required structure, a practised learner could handle it as a familiar application, so medium is plausible, while the newness of the comparison and knowledge-judgement tasks supports hard. The concrete remaining bottleneck is task 0: constructing and evidencing the two rival explanations.

- 作答要求：Evaluate the later accusation using both contemporaneous sources. / Give a plausible explanation consistent with deliberate deception and one consistent with an honest but mistaken forecast.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / I bought a weekly ticket because I trusted him. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / Reopening depends on testing after installation. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / " The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must construct two rival explanations from the sources: a deception account (manager asserted a near reopening while the log shows unconfirmed delivery and testing-dependent reopening) and an honest-mistake account (manager relied on the same uncertain forecast and later events, unrecorded, prevented reopening). No explanation is supplied; both must be built and tied to specific evidence.
- 作答要求：Explain which parts are established and which remain hypotheses, how the time at which each source was written affects its evidential value, and what additional evidence would help distinguish the explanations.
  - 题目条件：A diary written on the announcement day says: "The manager said repairs should finish next week. / " A maintenance log dated the same day says: "Parts have been ordered; the delivery date is not confirmed. / " Twenty years later the diarist writes: "He knew the station would never reopen and deliberately deceived us. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must classify what is established (the statement was made, the log recorded uncertainty, the station never reopened) versus what remains hypothesis (the manager's knowledge and intent), and must reason about how the twenty-year gap and the contemporaneous dating affect reliability, plus propose discriminating evidence such as the manager's records or communications. None of this analysis is supplied.
- 作答要求：Conclude with a claim no stronger than the evidence permits.
  - 题目条件：" The station in fact never reopened. / No record shows what information the manager received or what later prevented reopening.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must formulate a calibrated conclusion, e.g. that the accusation is not established and the evidence is consistent with both explanations, avoiding overclaiming in either direction.
