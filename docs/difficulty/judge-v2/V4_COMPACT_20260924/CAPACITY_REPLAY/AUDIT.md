# 评审汇总与覆盖率

“暂定一致”仅表示所有预定重复有效且等级相同，不是准确性证明。边界候选会归为 uncertain；多弃判不能算作更强判级能力。

| 方法 | 有效评审 | 单一明确等级 | 多候选边界评审 | 候选集合一致题数 |
|---|---:|---:|---:|---:|
| v3 | 13/16 | 11/16 | 0 | 4/8 |
| v4 | 16/16 | 13/16 | 1 | 7/8 |

## 逐题合并

失败、缺失或等级分歧不会回退到单次成功判断。两次 uncertain 仅表示弃判；若候选集合不同，集合一致指标不会计为一致。

### h_hint

- v3: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [None, None]。
- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### m_missing

- v3: abstained / uncertain；观测 ['uncertain', 'uncertain']；候选集合 [None, None]。
- v4: abstained / uncertain；观测 ['uncertain', 'uncertain']；候选集合 [[], []]。

### editor_base

- v3: review_required / uncertain；观测 ['medium', None]；候选集合 [None, None]。
- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### editor_hint

- v3: review_required / uncertain；观测 [None, 'medium']；候选集合 [None, None]。
- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### divisibility_base

- v3: provisional_consensus / hard；观测 ['hard', 'hard']；候选集合 [None, None]。
- v4: provisional_consensus / hard；观测 ['hard', 'hard']；候选集合 [['hard'], ['hard']]。

### divisibility_hint

- v3: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [None, None]。
- v4: provisional_consensus / medium；观测 ['medium', 'medium']；候选集合 [['medium'], ['medium']]。

### transfer_base

- v3: review_required / uncertain；观测 ['hard', None]；候选集合 [None, None]。
- v4: review_required / uncertain；观测 ['hard', 'uncertain']；候选集合 [['medium', 'hard'], ['hard']]。

### transfer_hint

- v3: review_required / uncertain；观测 ['medium', 'easy']；候选集合 [None, None]。
- v4: provisional_consensus / easy；观测 ['easy', 'easy']；候选集合 [['easy'], ['easy']]。

## v4 核对示例

以下只展示每题第一次有效评审，供查看依据；不代表另一重复成功，也不替代上面的合并结果。证据由系统按编号还原，角色分类和剩余任务仍是模型判断。

### h_hint（重复 1）

The task is a meaningful familiar application for introductory humanities students who can closely read passages and compare viewpoints. The supplied note provides the interpretive framework, standards, and even the key options (shared ownership vs. unstated difference; tentative belonging vs. unresolved exclusion), so the learner must apply those ideas to specific textual details rather than invent a nonroutine strategy. The nearest boundary is easy: the task is not mere reproduction because the learner must select evidence, construct a qualified interpretation, and revise a claim, which goes beyond retrieving a supplied argument. It is not hard because the note already supplies the interpretive alternatives and the constraint that censorship is not established, leaving no specific unfamiliar bottleneck.

- 作答要求：Evaluate both claims and construct your own interpretation under these constraints: / Distinguish what each passage explicitly states from inferences about motives, selection, rejection, or withheld information. / Use at least one concrete detail from each account as textual support. / Compare how the curator's collective language and the volunteer's applause coexist with hesitation or unstated difference. / Address a plausible competing reading drawn from the same passages. / Limit claims to what the passages establish; do not assert censorship, the letter's contents, or unstated visitor reactions. / Explain how a specific omission or ambiguity shapes your interpretation and state the uncertainty that remains.
  - 题目条件：Use only the three supplied excerpts. / The curator of the imagined North Quay community archive writes: We finally opened the exhibition together. / Volunteers carried boxes from their homes, and children stopped before the wall of photographs. / We chose captions short enough to read in a crowded room. / The opening felt like a beginning, not a finished history. / It does not identify who selected the photographs, list rejected contributions, or report every visitor's reaction. / A volunteer from the same imagined exhibition writes: I recognized my father's coat in a photograph, though the caption named only the factory. / I was glad that someone had kept the picture. / When the curator thanked us, I applauded, but I kept the letter I had brought inside my bag. / Perhaps there would be another occasion to show it. / The narrator reports gratitude and hesitation but does not state why the letter was withheld, whether anybody rejected it, or what it contained. / A first-person account gives access to a situated viewpoint, not automatic knowledge of every participant's motives. / Distinguish a narrator's explicit statement from an inference based on an image, omission or contrast. / The curator's collective we can be read as an aspiration to shared ownership or as a phrase that leaves differences within the group unstated. / The volunteer's applause and unopened letter can support readings of tentative belonging, unresolved exclusion, or a mixture, but the text does not establish censorship or identify the letter's contents. / A defensible interpretation compares details from both passages, acknowledges a plausible competing reading, and explains the limits of its claim. / Different interpretations can meet these standards without using identical wording or agreeing on a single hidden intention. / Do not invent details about the letter, the selection process, or visitors' reactions.
  - 解法提示：The curator's collective we can be read as an aspiration to shared ownership or as a phrase that leaves differences within the group unstated. / The volunteer's applause and unopened letter can support readings of tentative belonging, unresolved exclusion, or a mixture, but the text does not establish censorship or identify the letter's contents. / A defensible interpretation compares details from both passages, acknowledges a plausible competing reading, and explains the limits of its claim.
  - 剩余工作：Learner must select concrete details from each passage, distinguish explicit statements from inferences, compare collective language with hesitation, address a competing reading, and explain how an omission shapes the interpretation while stating remaining uncertainty. The note supplies interpretive options and standards but does not perform the comparison or produce the interpretation.
- 作答要求：- Decide which claim, if either, better fits the evidence and the constraints, and justify your judgment.
  - 题目条件：Claim 1: The curator's 'we' and the volunteer's applause show that the exhibition created shared ownership that everyone experienced as belonging. / Claim 2: The volunteer's unopened letter proves the exhibition censored or excluded her family history. / Limit claims to what the passages establish; do not assert censorship, the letter's contents, or unstated visitor reactions.
  - 解法提示：The volunteer's applause and unopened letter can support readings of tentative belonging, unresolved exclusion, or a mixture, but the text does not establish censorship or identify the letter's contents.
  - 剩余工作：Learner must judge which claim better fits the evidence and constraints, using the note's warning that the text does not establish censorship or identify the letter's contents.
- 作答要求：- If neither claim is fully defensible, revise one claim into a qualified sentence that could satisfy the constraints.
  - 题目条件：Claim 1: The curator's 'we' and the volunteer's applause show that the exhibition created shared ownership that everyone experienced as belonging. / Claim 2: The volunteer's unopened letter proves the exhibition censored or excluded her family history. / Limit claims to what the passages establish; do not assert censorship, the letter's contents, or unstated visitor reactions.
  - 解法提示：The volunteer's applause and unopened letter can support readings of tentative belonging, unresolved exclusion, or a mixture, but the text does not establish censorship or identify the letter's contents.
  - 剩余工作：Learner must revise one claim into a qualified sentence that satisfies the constraints, avoiding unsupported assertions about shared belonging or censorship.
- 作答要求：- Explain what additional evidence would be needed to support the stronger original claim you reject.
  - 题目条件：It does not identify who selected the photographs, list rejected contributions, or report every visitor's reaction. / The narrator reports gratitude and hesitation but does not state why the letter was withheld, whether anybody rejected it, or what it contained. / Limit claims to what the passages establish; do not assert censorship, the letter's contents, or unstated visitor reactions. / Do not invent details about the letter, the selection process, or visitors' reactions.
  - 解法提示：未引用解法提示
  - 剩余工作：Learner must specify what additional evidence would be needed to support the stronger rejected claim, such as records of selection decisions, the letter's contents, or visitor reactions, without inventing those details.

### m_missing（重复 1）

题目缺少确定 xy 所必需的条件，且要求“唯一确定的数值”与已知信息矛盾，故为 invalid_question，不进行难度分级。若补充如 x+y 或 x²+y² 等条件，才可能成为可解问题。

- 作答要求：请给出 xy 唯一确定的数值。
  - 题目条件：设 x、y 为非负实数。
  - 解法提示：未引用解法提示
  - 剩余工作：需要额外条件才能确定 xy；在现有条件下无法完成求值。

### editor_base（重复 1）

The task requires applying familiar skills (distinguishing observation from interpretation, supporting claims with textual details) to a new fictional case. The learner must select relevant details, evaluate an inference, generate alternative explanations, and state a qualified conclusion. This is meaningful familiar application and evidence integration rather than direct reproduction, but it does not require a nonroutine strategy or unfamiliar integration bottleneck. The nearest boundary is easy: the task would be easy if the answer merely reproduced a supplied evaluation, but here the evaluation, alternatives, and qualified conclusion must be constructed independently. It is not hard because the reasoning moves are ones the profile has practised and the case is short and self-contained.

- 作答要求：Evaluate the editor's claim using a detail from each account.
  - 题目条件：A student editor writes: "We printed every submission received before Friday. / The printed issue proves that everyone could speak freely. / " A student contributor writes: "My essay appeared unchanged. / I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " The published submission policy says: "All submissions received before Friday are printed without editorial changes. / " There are no other records.
  - 解法提示：未引用解法提示
  - 剩余工作：Select a relevant detail from each account and use it to assess whether the editor's inference follows; the records do not supply this evaluation.
- 作答要求：Explain whether the policy resolves the contributor's concern.
  - 题目条件：I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " The published submission policy says: "All submissions received before Friday are printed without editorial changes.
  - 解法提示：未引用解法提示
  - 剩余工作：Determine whether a no-editorial-changes policy addresses a self-imposed deletion; the answer requires reasoning about what the policy does and does not govern.
- 作答要求：Give two plausible explanations for the contributor's deletion, distinguish what is established from what is only possible, and state what additional evidence could distinguish those explanations.
  - 题目条件：I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " There are no other records.
  - 解法提示：未引用解法提示
  - 剩余工作：Generate two plausible explanations, sort established facts from mere possibilities, and identify discriminating evidence; none of this is supplied.
- 作答要求：Propose one qualified conclusion supported by the records. / Multiple supported conclusions are allowed; do not invent facts.
  - 题目条件：A student editor writes: "We printed every submission received before Friday. / The printed issue proves that everyone could speak freely. / " A student contributor writes: "My essay appeared unchanged. / I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " The published submission policy says: "All submissions received before Friday are printed without editorial changes. / " There are no other records.
  - 解法提示：未引用解法提示
  - 剩余工作：Formulate a qualified conclusion that stays within the records and avoids invented facts.

### editor_hint（重复 1）

The task is a short seminar response for undergraduates already practised in distinguishing observations from interpretations and supporting comparisons with quotations. The teaching note supplies the key interpretive moves (stage-specific freedom, two explanations, evidence to discriminate, qualified conclusion), so the learner is not discovering a nonroutine strategy; the work is meaningful familiar application: selecting textual details, applying the supplied distinction between established and possible, and assembling a qualified conclusion. This sits above easy because it requires integrating several supplied ideas into a coherent argument with evidence, but below hard because no unfamiliar bottleneck or independent proof/design is required. Nearest boundary: easy would be mere retrieval of the policy or restating the teaching note; the learner must instead apply the distinction to specific details and construct the two-explanation analysis, which is routine application rather than reproduction.

- 作答要求：Evaluate the editor's claim using a detail from each account.
  - 题目条件：A student editor writes: "We printed every submission received before Friday. / The printed issue proves that everyone could speak freely. / " A student contributor writes: "My essay appeared unchanged. / I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " The published submission policy says: "All submissions received before Friday are printed without editorial changes.
  - 解法提示：Teaching note: Printing received submissions unchanged establishes freedom from editorial alteration at that stage; it does not establish freedom from anticipated social consequences before submission.
  - 剩余工作：Learner must select one detail from each account (e.g., editor's 'printed every submission received before Friday' and contributor's 'essay appeared unchanged') and connect them to the claim, rather than merely restating the teaching note.
- 作答要求：Explain whether the policy resolves the contributor's concern.
  - 题目条件：" The published submission policy says: "All submissions received before Friday are printed without editorial changes. / I deleted a paragraph before I sent it because I worried about losing my club role.
  - 解法提示：Teaching note: Printing received submissions unchanged establishes freedom from editorial alteration at that stage; it does not establish freedom from anticipated social consequences before submission. / Nobody requesting deletion rules out that particular explicit request but does not establish whether informal pressure existed.
  - 剩余工作：Learner must explain that the policy governs editorial alteration after receipt, not pre-submission social pressure, so it does not resolve the contributor's worry; this requires articulating the scope limit, not just citing the policy.
- 作答要求：Give two plausible explanations for the contributor's deletion, distinguish what is established from what is only possible, and state what additional evidence could distinguish those explanations.
  - 题目条件：I deleted a paragraph before I sent it because I worried about losing my club role. / Nobody asked me to delete it. / " There are no other records.
  - 解法提示：The contributor's worry might reflect a credible informal threat or an unsupported personal expectation. / Nobody requesting deletion rules out that particular explicit request but does not establish whether informal pressure existed. / Independent accounts of club reactions could help distinguish the explanations.
  - 剩余工作：Learner must generate two distinct plausible explanations (credible informal threat vs. unsupported personal expectation), sort established facts (deletion occurred, no explicit request) from possibilities, and name evidence (independent club accounts) that would discriminate them.
- 作答要求：Propose one qualified conclusion supported by the records. / Multiple supported conclusions are allowed; do not invent facts.
  - 题目条件：A student editor writes: "We printed every submission received before Friday. / " A student contributor writes: "My essay appeared unchanged. / " The published submission policy says: "All submissions received before Friday are printed without editorial changes. / " There are no other records.
  - 解法提示：A qualified conclusion may affirm unchanged publication while leaving pre-submission freedom unresolved.
  - 剩余工作：Learner must formulate a qualified conclusion that affirms unchanged publication while leaving pre-submission freedom unresolved, grounded in the records and avoiding invented facts.

### divisibility_base（重复 1）

该题的核心瓶颈是构造一个非显然的分组：按奇数部分把 1 到 2n 分成 n 组，再用抽屉原理。学习者已会抽屉原理和整除、奇偶性，但未学过按奇数部分分组的技巧；题目也没有提供任何分组方法或中间结论，因此不是对已给方法的熟悉套用，而是需要独立发现并验证构造。最近边界是 medium：若学生已熟悉“写成 2^k 乘奇数”的分组技巧，则本题会退化为常规应用；但按给定画像，该技巧未学，故判为 hard。

- 作答要求：证明其中一定存在两个不同数，使一个整除另一个。 / 你需要说明构造或分组方法为何适用于任意 n，并解释由它得到整除关系的原因，不能只检验几个例子。
  - 题目条件：设 n 为任意正整数。 / 从 1,2,…,2n 中任取 n+1 个不同整数。
  - 解法提示：未引用解法提示
  - 剩余工作：需要独立构造分组：把每个整数写成 2^k·m（m 为奇数），按奇数部分 m 分组；证明每组内任意两数成倍数关系；说明 1 到 2n 中奇数部分只有 n 种可能，从而 n+1 个数落入 n 组，由抽屉原理得两数同组，进而一个整除另一个。还需解释该构造对任意 n 成立。

### divisibility_hint（重复 1）

题目本身是经典抽屉原理证明，但提示已把关键非平凡步骤（唯一分解、奇数部分只有 n 种、按 u 分组、同组两数成倍数）全部给出，学生只需理解并把这些片段组织成完整论证。对已学抽屉原理和整除、但未学过按奇数部分分组技巧的高中生而言，这属于在熟悉框架下应用给定方法并作解释，而非独立发现非平凡策略，故定为 medium。最近边界：若提示只给唯一分解而不给分组与组数，则需学生自行选择分组方式，会偏向 hard；若仅要求复述提示结论，则偏向 easy。此处提示完整，故取 medium。

- 作答要求：证明其中一定存在两个不同数，使一个整除另一个。 / 你需要说明构造或分组方法为何适用于任意 n，并解释由它得到整除关系的原因，不能只检验几个例子。 / 请解释这些步骤为何覆盖所有 n 及所有选取方式。
  - 题目条件：设 n 为任意正整数。 / 从 1,2,…,2n 中任取 n+1 个不同整数。 / 提示：每个正整数唯一写成 2^k·u，其中 k≥0，u 为奇数。 / 1 到 2n 中只有 n 种可能的奇数部分 u（1,3,…,2n−1）。
  - 解法提示：将选出的 n+1 个数按 u 分组，必有两个属于同组；它们分别为 2^a·u 和 2^b·u，设 a<b，则前者整除后者。
  - 剩余工作：提示已给出分组对象（奇数部分 u）、组数 n、抽屉原理推出同组、以及同组两数写成 2^a·u 与 2^b·u 后较小者整除较大者。学生仍需把这些片段组织成完整证明：说明 1 到 2n 中奇数部分恰为 1,3,…,2n−1 共 n 种，因此 n+1 个数落入 n 组必有两数同组；说明同组两数指数不同故为不同数；说明 a<b 时 2^a·u 整除 2^b·u；并说明该论证对任意 n 和任意选取都成立。

### transfer_base（重复 1）

学习者已掌握单锁保护计数器的分析，但尚未练习多对象加锁顺序及其正确性证明。本题核心瓶颈是自行设计按 ID 全序加锁的转账方案并论证其无死锁，这属于相对既有准备的非例行策略选择，而非单纯复述已知论证，故存在 hard 候选。另一方面，若学习者能把单锁临界区经验直接迁移到两把锁并按固定顺序获取，则任务接近熟悉的互斥应用，故 medium 亦合理。边界在于：题目未提供任何加锁顺序方案或正确性证明，需独立构造，因此不能仅判为 easy；但所需概念（互斥、临界区、循环等待）均为已学内容，故不排除 medium。hard_task_index=0 指向伪代码设计这一具体瓶颈。

- 作答要求：设计转账伪代码，使没有任何转账执行到一半时总余额与初始总额相同、任何时刻账户都不透支，并使任意并发转账不会造成死锁。
  - 题目条件：系统有有限个账户，每个账户有不同且固定的整数 ID、初始非负整数余额和一把互斥锁。 / 可同时执行有限次 transfer(source, destination, amount)，source 与 destination 不同，amount 为正整数。 / 余额足够时转账恰好一次，否则返回失败且不改余额。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。 / 不允许使用覆盖整个系统的全局锁。
  - 解法提示：未引用解法提示
  - 剩余工作：需自行设计按账户 ID 排序加锁的转账伪代码：先比较 source/destination 的 ID，按固定全序依次获取两把锁，再在锁内读余额、检查、更新或返回失败，最后逆序释放。题目未提供任何伪代码或加锁顺序方案。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：系统有有限个账户，每个账户有不同且固定的整数 ID、初始非负整数余额和一把互斥锁。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。
  - 解法提示：未引用解法提示
  - 剩余工作：需说明读余额、检查与更新都在同一临界区内、由两把账户锁共同保护，并解释为何不能只锁一个账户或先读后锁。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：余额足够时转账恰好一次，否则返回失败且不改余额。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。
  - 解法提示：未引用解法提示
  - 剩余工作：需给出正确性论证：总余额守恒（转账是同一临界区内一减一加）、不透支（检查与更新原子）、无死锁（全序加锁破坏循环等待）。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。
  - 解法提示：未引用解法提示
  - 剩余工作：需构造具体并发反例：两个线程分别以相反顺序获取 A、B 两把锁，各自持有第一把并等待第二把，形成循环等待而死锁。

### transfer_hint（重复 1）

题目已给出完整方案（按 ID 升序加两锁、持锁检查与扣加、成败均释放）以及正确性理由（扣加相等、失败不改、等待只从小 ID 指向大 ID）和死锁反例（A→B 与 B→A 各持一锁互等）。学习者已掌握互斥锁、竞态、死锁含义并能分析单计数器加锁代码，因此最低要求是把方案转写为伪代码、把已给理由对应到具体语句并展开为覆盖所有交错的说明、把反例具体化——属于对已提供论证的复述与整理，而非发现新策略或新证明。最近边界：若要求自行发现加锁顺序方案或独立构造无死锁证明，则需非平凡策略整合，会升为 medium/hard；但本题明确“无需发现另一种方案”，故判为 easy。

- 作答要求：设计转账伪代码，使没有任何转账执行到一半时总余额与初始总额相同、任何时刻账户都不透支，并使任意并发转账不会造成死锁。 / 请把该方案写成伪代码，并解释上述理由如何覆盖所有允许的交错；无需发现另一种方案。
  - 题目条件：系统有有限个账户，每个账户有不同且固定的整数 ID、初始非负整数余额和一把互斥锁。 / 可同时执行有限次 transfer(source, destination, amount)，source 与 destination 不同，amount 为正整数。 / 余额足够时转账恰好一次，否则返回失败且不改余额。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。 / 不允许使用覆盖整个系统的全局锁。
  - 解法提示：可采用以下完整方案：对两个账户按 ID 从小到大获取两把锁；拿齐两锁后检查 source. / balance≥amount，成立则在仍持有两锁时执行 source. / balance-=amount 与 destination. / balance+=amount，否则不修改；无论成败都释放两把锁。
  - 剩余工作：把已给出的按 ID 升序加两锁、持锁检查与扣加、成败均释放的步骤转写为规范伪代码（含加锁顺序、失败返回、释放路径），无需自行设计新方案。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：系统有有限个账户，每个账户有不同且固定的整数 ID、初始非负整数余额和一把互斥锁。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。
  - 解法提示：读、检查、扣款、加款均在两锁保护内，检查不会被其他转账抢先破坏；每次成功操作扣加相等，失败不改余额。
  - 剩余工作：将已给出的“读、检查、扣款、加款均在两锁保护内”对应到具体语句，说明各操作分别由哪把/哪些锁保护，并指出检查与更新不可被其他转账插入。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：可同时执行有限次 transfer(source, destination, amount)，source 与 destination 不同，amount 为正整数。 / 余额足够时转账恰好一次，否则返回失败且不改余额。 / 只有这些转账操作会读写余额；调用之间可任意交错，线程不崩溃，算术不溢出。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。
  - 解法提示：读、检查、扣款、加款均在两锁保护内，检查不会被其他转账抢先破坏；每次成功操作扣加相等，失败不改余额。 / 所有等待只从较小 ID 指向较大 ID，不能形成等待环。
  - 剩余工作：把已给出的两条理由（成功时扣加相等、失败不改余额；等待只从较小 ID 指向较大 ID 故无等待环）展开为覆盖任意交错的不变量论证，需自行组织“总余额不变、不透支、无死锁”三部分的推理链条。
- 作答要求：解释读余额、检查与更新分别受哪些锁保护；论证正确性并给出一个具体并发例子说明错误的加锁方式为什么可能死锁。
  - 题目条件：可同时执行有限次 transfer(source, destination, amount)，source 与 destination 不同，amount 为正整数。 / 锁获取是原子的；锁竞争采用公平排队，已获得锁的线程最终得到调度并执行有限步后释放锁。
  - 解法提示：反例：若总先锁 source，A→B 与 B→A 可各持一锁再等待另一锁。
  - 剩余工作：把已给出的 A→B 与 B→A 各持一锁再互等的反例具体化为可执行的并发交错序列，说明为何形成等待环而无法推进。
