# Codex 逐题评分记录

评分已冻结后才显示下方策略、目标及阶段。共42个请求，39道可评题，3个无可用输出的槽位。此为有先前背景的回顾性AI复核，不是教师或学生金标。

[组汇总与解释](REVIEW_REPORT.md) · [固定评分协议](../../CODEX_REVIEW_PROTOCOL_V1.md) · [原资料与学习者背景](sources.json)

## Q001 · D1：六需求对照 · 三档对照

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：需把同一提交时序分别应用到RR与RC：第二次读取为100与150。旧快照与完整重试的说明合理；有具体状态对照，尚无实质方案权衡。

**原题干**

Two sessions run against a table accounts(id, balance) with initial rows (1, 100) and (2, 200). Session A runs under PostgreSQL Repeatable Read. Session B runs under PostgreSQL Read Committed. The schedule is: (1) A begins; (2) A performs its first ordinary SELECT of account 1 and sees balance 100; (3) B begins; (4) B updates account 1 to balance 150 and commits; (5) A performs a second ordinary SELECT of account 1; (6) A commits. Using only the supplied PostgreSQL semantics, state what A's second SELECT is allowed to see and explain why. Then compare this with what a Read Committed transaction in the same position would see, and state one consequence of this difference for an application that decides its writes from its reads.

**原参考答案（保持原样，可能有错）**

A's second ordinary SELECT under Repeatable Read must still see balance 100, because ordinary queries use the snapshot associated with A's first non-transaction-control statement, and B's concurrent commit does not change that view between successive reads. A Read Committed transaction in the same position would see balance 150 on its second ordinary SELECT, because each ordinary SELECT sees rows committed before that statement began. The application consequence is that a transaction whose decisions depend on its reads may be making decisions from an older snapshot under Repeatable Read, so it cannot assume its reads reflect the latest committed state; it should be prepared for concurrency behavior such as serialization failure and retry the complete transaction when required.

**原解释（保持原样）**

The key is to apply the stated snapshot rule rather than a general intuition. Repeatable Read fixes the ordinary-read view at the first non-transaction-control statement, so step 5 cannot see B's commit. Read Committed takes a fresh statement-level view, so step 5 would see balance 150. The application consequence follows from the notes: decisions based on reads may be based on a state that is no longer current, and the application must be prepared for transaction failure and complete retry.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q002 · D1：六需求对照 · 支架与迁移控制

目标：hard；题目级综合分：85.0/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：hard；置信度：high。

正确性 2/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：含响应上限和开销预算的联合可行性判断及参数取舍，属于hard。前两问主要时间线正确，但(3)把零开销平均响应1用于有开销场景；有开销平均响应应2，开销比为5/(10+5)=1/3而非50%。不可行结论仍对，数值依据错。

**原题干**

某单处理器系统按片段中的自拟教学模型运行，采用轮转调度 RR，任务均独立、各只有一个 CPU burst 且无 I/O。切换开销只在切换到另一个任务时计费，首次派发免费；忽略开销时切换耗时为 0，计算开销时每次切换耗时 1 个时间单位，切换期间到达的任务按“新到任务先于被抢占任务入队”处理；任务恰在片尾到达时同样按“新到任务先入队”处理。现有三个任务：A 在 t=0 到达、服务量 5；B 在 t=1 到达、服务量 3；C 在 t=2 到达、服务量 2。请完成以下任务并给出论证：(1) 在时间片 q=2、忽略切换开销的条件下，写出三个任务各自的首次运行时刻与完成时刻，并计算各自的响应时间与周转时间；(2) 在 q=2、计入上述切换开销的条件下，重新给出三个任务的完成时刻，并计算系统总周转时间，与 (1) 中忽略开销的总周转时间比较；(3) 若设计目标改为“所有任务的平均响应时间不超过 1 个时间单位，且切换开销占 CPU 总时间的比例不超过 20%”，请判断 q=2 是否可行，并说明你会如何在片段允许的策略参数范围内调整（可考虑改变 q 或改用 MLFQ），同时指出该调整可能带来的代价。

**原参考答案（保持原样，可能有错）**

以片段模型为准，切换开销只在切换到另一个任务时计费且首次派发免费；片尾或切换期间到达的新任务先入队。(1) q=2、忽略开销：t=0 派发 A，A 运行 [0,2)，剩余 3；t=1 B 到达入队，t=2 C 到达，按“新到任务先入队”C 先于被抢占的 A 入队，队列为 B、C、A。t=2 派发 B，B 运行 [2,4)，剩余 1；t=4 派发 C，C 运行 [4,6) 完成；t=6 派发 A，A 运行 [6,8)，剩余 1；t=8 派发 B，B 运行 [8,9) 完成；t=9 派发 A，A 运行 [9,10) 完成。首次运行时刻：A=0、B=2、C=4；完成时刻：A=10、B=9、C=6。响应时间：A=0-0=0、B=2-1=1、C=4-2=2；周转时间：A=10-0=10、B=9-1=8、C=6-2=4；总周转时间=22。(2) q=2、每次切换计 1：t=0 派发 A（首次免费），A 运行 [0,2)；t=2 切换耗时 [2,3)，期间 C 到达，C 先入队，队列为 B、C、A；t=3 派发 B，B 运行 [3,5)；t=5 切换 [5,6)；t=6 派发 C，C 运行 [6,8) 完成；t=8 切换 [8,9)；t=9 派发 A，A 运行 [9,11)，剩余 1；t=11 切换 [11,12)；t=12 派发 B，B 运行 [12,13) 完成；t=13 切换 [13,14)；t=14 派发 A，A 运行 [14,15) 完成。完成时刻：A=15、B=13、C=8；总周转时间=(15-0)+(13-1)+(8-2)=33，比忽略开销的 22 多 11，差额来自 5 次切换的 5 个时间单位以及由此推迟的完成时刻。(3) q=2 不可行：平均响应时间=(0+1+2)/3=1，恰好不超过 1，但切换开销占比为 5/(5+5)=50%，超过 20% 的预算，因此不满足全部约束。可在片段允许的参数内调整：方案一是增大时间片 q（例如 q=3 或更大），减少切换次数从而降低开销占比，但会延长后到任务首次运行前的等待，可能使平均响应时间超过 1；方案二是改用 MLFQ，让新任务从高优先级开始、同级轮转，并按累计使用量计算配额、周期性提升优先级，从而在不预知运行时间的情况下改善首次响应并兼顾公平，但队列层数、片长、配额和提升间隔等参数需要重新选择，且低优先级任务可能仍经历较长等待，切换与提升本身也会带来开销。结论：不存在仅靠 q=2 就同时满足两个约束的方案，必须在响应上限与开销预算之间做有依据的取舍。

**原解释（保持原样）**

先按片段定义记录每个任务的首次运行与结束时刻，再计算响应时间（首次运行时刻减到达时刻）和周转时间（完成时刻减到达时刻）。忽略开销时只需按 RR 规则轮转；计入开销时，切换只在切换到另一个任务时计费、首次派发免费，切换期间到达的新任务按“新到任务先入队”处理，因此 C 在 t=2 的切换期间到达时排在 A 之前。最后用“平均响应时间”和“切换开销占比”两个约束分别检验 q=2，并说明调整 q 或改用 MLFQ 的收益与代价。

资料键：`fixture_cpu_scheduling_zh`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q003 · D1：六需求对照 · 评分要点先行

目标：hard；题目级综合分：67.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：hard；置信度：medium。

正确性 1/4 · 资料支持 4/4 · 可作答性 2/4 · 清晰度 2/4。

**评分理由**：有响应上限和正切换开销下的取舍，任务意图为hard；但片尾到达与被抢占者入队顺序未规定，数值分支不能唯一确定。答案服务量不足、时间区间自相矛盾，且把首次运行时刻当成响应时间；核心约束判断不可靠。

**原题干**

某单处理器系统采用轮转调度（RR），时间片为 q，切换开销按“仅切换到另一个任务时计费、首次派发免费”计算，切换期间到达的任务按到达顺序先入就绪队列。现有三个独立任务，均无 I/O、各只有一个 CPU burst，到达时间与服务量如下：
A：到达 0，服务 5
B：到达 1，服务 3
C：到达 2，服务 2
（时间单位任意，切换开销记为 s，且 s<q。）

请完成：
(1) 取 q=2、s=0，给出 A、B、C 各自的首次运行时刻与完成时刻，并计算各自的响应时间与周转时间；
(2) 说明若把 q 从 2 减小到 1（仍取 s=0），哪些任务的首次响应会改善、哪些不会，并解释原因；
(3) 在 s>0 的一般情形下，论证“q 越小一定越好”不成立：需结合本题任务集合，指出 q 减小带来的收益与代价，并给出一个使总切换开销占比上升的 q 取值方向；
(4) 若系统额外要求“所有任务响应时间不超过 2 个时间单位”，在 s=0 时判断 q=2 是否满足，并说明若改为 q=1 是否满足；若 s>0，说明该约束还取决于什么。

**原参考答案（保持原样，可能有错）**

(1) q=2、s=0 时，就绪队列演化：t=0 A 运行 [0,2)，t=2 B 已到达，A 回队尾，队列为 B、A；B 运行 [2,4)，t=4 C 已到达，B 回队尾，队列为 A、C、B；A 运行 [4,6)，A 完成（服务 5，已用 2+2=4，本次只需 1 个时间单位），队列为 C、B；C 运行 [6,8)，C 完成；B 运行 [8,9)，B 完成。
结果：A 首次运行 0，完成 6，响应时间 0-0=0，周转时间 6-0=6；B 首次运行 2，完成 9，响应时间 2-1=1，周转时间 9-1=8；C 首次运行 6，完成 8，响应时间 6-2=4，周转时间 8-2=6。
(2) q=1、s=0 时，A 运行 [0,1)，B 到达 1 后 A 回队尾，队列 B、A；B 运行 [1,2)，C 到达 2 后 B 回队尾，队列 A、C、B；A 运行 [2,3)，队列 C、B、A；C 运行 [3,4)，队列 B、A、C；B 运行 [4,5)，队列 A、C、B；A 运行 [5,6)，队列 C、B、A；C 运行 [6,7)，C 完成；B 运行 [7,8)，B 完成；A 运行 [8,9)，A 完成。首次运行时刻：A=0（不变），B=1（由 2 提前到 1），C=3（由 6 提前到 3）。因此 B、C 的首次响应改善，A 不变，因为 A 本来就在 t=0 立即获得 CPU。
(3) q 减小的收益是更早轮转到队尾任务，改善首次响应（如 (2) 中 C 从 6 提前到 3）；代价是切换次数增加，总切换开销上升。在本题中，q=2 时 A、B、C 共需切换若干次；若 q 取更小值（如 q=1 甚至更小），在相同总服务量下就绪队列轮转次数增多，切换次数随之增多，总开销 = 切换次数 × s 上升。当 s 相对于 q 不可忽略时，切换开销可能挤占有效 CPU 时间，使某些任务的完成时间反而推迟，因此“q 越小一定越好”不成立，需要针对响应上限与开销预算折中。
(4) s=0、q=2 时响应时间分别为 A=0、B=1、C=4，C 的响应时间 4>2，不满足“所有任务响应时间不超过 2”。q=1 时响应时间为 A=0、B=1、C=3，C 仍为 3>2，仍不满足。若 s>0，该约束能否满足还取决于 s 的大小与切换计费方式：切换开销会推迟后续任务的首次运行时刻，s 越大越难满足响应上限；此外片尾到达与新到任务入队顺序也会影响首次运行时刻。

**原解释（保持原样）**

本题按“评分要点先行”设计：先确定应展示的能力——按给定模型手工推演 RR 的首次运行与完成时刻、计算响应/周转时间、在具体约束下比较不同 q 并论证权衡。答案中的时刻表可用片段给出的周转时间与响应时间定义核对：周转时间=完成时刻-到达时刻，响应时间=首次运行时刻-到达时刻；RR 每次最多运行一个时间片，未完成者回队尾；切换开销与片尾到达规则按片段中的自拟教学模型处理。

资料键：`fixture_cpu_scheduling_zh`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q004 · D1：六需求对照 · 当前基线

目标：hard；题目级综合分：85.0/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：hard；置信度：medium。

正确性 2/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：要求比较响应与开销并指出设计约束，属于评价型边界hard。q2时A已在队中等待，C到达不能越过A；正确首次运行A/B/C为0/3/9，结束19/14/11，平均响应2、周转38/3。参考把C先运行，相关数值错误。

**原题干**

Using the fixture's explicit scheduling model, consider a single processor with these independent jobs, each having one CPU burst and no I/O. All times are in milliseconds. Job A arrives at t=0 and needs 8 ms of CPU service. Job B arrives at t=2 and needs 4 ms. Job C arrives at t=4 and needs 2 ms. The scheduler is Round Robin with a time slice of 2 ms. Context-switch overhead is 1 ms and applies only when the processor moves between different jobs; there is no initial dispatch charge. A job that finishes before its slice ends does not use the remaining slice. If a job arrives exactly at a slice boundary, assume it is enqueued before the preempted job. Ties are resolved alphabetically by job name. (a) Draw or describe the timeline from t=0 until all jobs finish, showing each dispatch and switch. (b) Compute each job's first-run time, completion time, response time, and turnaround time. (c) Compute the average response time and average turnaround time. (d) The system designer now says the goal is to minimize the maximum response time while keeping switching overhead low. Based only on this scenario, argue whether a 1 ms slice would be a better or worse choice than the 2 ms slice, and state one constraint or measurement that would be needed before recommending a final design.

**原参考答案（保持原样，可能有错）**

A complete answer must follow the fixture's conventions and show the timeline, per-job metrics, averages, and a reasoned design judgment. A correct timeline for the 2 ms slice is: A runs 0–2 (2 ms service); switch 2–3; B runs 3–5 (2 ms service); switch 5–6; C runs 6–8 (2 ms service, finishes at 8); switch 8–9; A runs 9–11 (2 ms service); switch 11–12; B runs 12–14 (2 ms service, finishes at 14); switch 14–15; A runs 15–19 (4 ms service, finishes at 19). Note that B arrived at t=2, which is exactly a slice boundary, so under the stated rule B is enqueued before preempted A; C arrives at t=4 during B's slice and enters the ready queue. First-run times: A=0, B=3, C=6. Completion times: A=19, B=14, C=8. Response times (first run minus arrival): A=0−0=0 ms; B=3−2=1 ms; C=6−4=2 ms. Turnaround times (completion minus arrival): A=19−0=19 ms; B=14−2=12 ms; C=8−4=4 ms. Average response time = (0+1+2)/3 = 1.0 ms. Average turnaround time = (19+12+4)/3 = 35/3 ≈ 11.67 ms. For part (d), a 1 ms slice would tend to let B and C first run sooner, which can reduce the maximum response time, but it also increases the number of context switches and therefore the switching overhead, which can delay completion and raise turnaround time. So a 1 ms slice is not automatically better for the stated goal; it is a tradeoff. A final recommendation needs an explicit objective and constraints, such as a maximum acceptable response time, a switching-overhead budget, or a fairness requirement, and ideally measured workload traces rather than hypothetical bursts.

**原解释（保持原样）**

The fixture defines response time as first-run time minus arrival time and turnaround time as completion time minus arrival time, and it warns that early access does not necessarily imply early completion. It also states that shorter slices can improve initial responsiveness but increase context-switch frequency, and that neither a smaller average response time nor a smaller switching fraction alone proves a policy is best for every objective. The timeline must respect the stated overhead rule, the no-initial-dispatch-charge convention, the exact-boundary enqueue rule, and the alphabetical tie rule. The design argument must connect the 1 ms versus 2 ms choice to the stated objective and acknowledge that a final recommendation requires a stated objective and constraints.

资料键：`fixture_cpu_scheduling_en`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q005 · v2：单需求格式验证 · 评分要点先行

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：先读100、外部随后提交150，RR第二次仍100；失败作为题设条件时，重读及重做决策的完整重试正确。属于熟悉规则的情境应用。

**原题干**

某 PostgreSQL 应用在 Repeatable Read 隔离级别下运行事务 T1。T1 先执行一次普通 SELECT 得到账户余额为 100，随后另一事务 T2 把该余额改为 150 并成功提交；T1 之后又执行一次相同的普通 SELECT，然后基于第二次查询结果决定写入。请回答：(1) T1 第二次普通 SELECT 看到的值应为多少，并说明依据；(2) 若 T1 在提交时因序列化异常被拒绝，应用按资料要求应如何重试，为什么不能只重试最后一条失败语句？

**原参考答案（保持原样，可能有错）**

(1) 第二次普通 SELECT 仍看到 100。依据：Repeatable Read 下普通查询使用本事务第一条非事务控制语句对应的快照，连续查询不会因其他事务的提交而改变这一视图（fixture_transactions_zh）。(2) 应重试整个事务，包括重新执行读取数据以及据此选择写入操作的应用逻辑；因为仅重试最后一条失败语句可能继续使用已经失效的决策（fixture_transactions_zh），重试本身也可能再次失败，不能承诺一次成功。

**原解释（保持原样）**

Repeatable Read 的稳定快照使 T1 的两次普通 SELECT 保持同一视图，因此 T2 提交的 150 不会出现在 T1 的第二次查询中。序列化异常意味着该次执行被拒绝，应用必须重做依赖读取结果的决策，而不是只重发最后一条语句。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q006 · D1：六需求对照 · 支架与迁移控制

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：只需识别资料明确写出的闭区间左边界更新；A唯一正确，解释排除了mid及其左侧。

**原题干**

资料采用闭区间 [left, right] 保存仍可能包含目标的位置，数组升序、元素互异。当中间值小于目标时，应如何更新边界？

A. left = mid + 1
B. left = mid
C. right = mid - 1
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

闭区间约定下，中间值小于目标说明 mid 及其左侧位置都不可能命中，因此把左边界更新为 mid+1，保持区间内都是仍可能命中的位置（fixture_binary_search_zh）。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q007 · v2：单需求格式验证 · 难度维度约束

目标：medium；题目级综合分：80.0/100；严格达标：否；完整材料原校验：通过。

我的难度判断：easy；置信度：medium。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：未给需要追踪的交错、数值或方案约束；所问错误重试及正确范围可直接复述资料中“重试整个事务及读取决策”的规则。有情境包装，easy/medium有边界性，本次归easy。

**原题干**

某 PostgreSQL 应用在 Repeatable Read 隔离级别下运行事务 T。T 先执行一次普通 SELECT 读取账户余额，然后根据该余额决定写入一条调整记录，提交时遇到序列化失败。应用当前的错误处理只重新执行最后一条失败的写入语句。请分析：只重试最后一条失败语句是否可能使 T 的决策基于失效的读取结果；并说明按照资料应如何重试整个事务，以及为什么不能承诺重试一次就一定成功。

**原参考答案（保持原样，可能有错）**

可能。Repeatable Read 让普通查询使用本事务第一条非事务控制语句对应的快照，因此 T 第一次普通 SELECT 看到的余额在 T 的后续普通查询中不会因其他事务提交而改变；但提交时仍可能因序列化异常被拒绝。如果只重新执行最后一条失败的写入语句，应用逻辑中“根据读取余额决定写入什么”的决策没有被重新执行，可能继续使用已经失效的读取结果。按照资料，应重试整个事务，包括读取数据和据此选择写入操作的应用逻辑，使决策在新的事务中基于新的快照重新做出。重试本身也可能再次失败，因为新的执行仍可能遇到序列化异常，所以不能承诺重试一次就一定成功。

**原解释（保持原样）**

先判断 Repeatable Read 下普通查询的快照行为，再说明序列化失败后只重试最后一条语句会保留失效决策，最后给出重试整个事务的要求及其不确定性。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q008 · D1：六需求对照 · 难度维度约束

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：闭区间、中值小于目标的更新是直接资料提取；A正确，其余选项不能正确排除已比较位置。

**原题干**

在资料所述的闭区间 [left, right] 二分查找中（数组升序、元素互异、下标从 0 开始），若某轮中间位置的值小于目标值，应如何更新边界？

A. left = mid + 1
B. left = mid
C. right = mid - 1
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

闭区间 [left, right] 中，mid 位置的值小于目标，说明 mid 及其左侧都不可能是目标，因此把 left 更新为 mid+1，新区间仍保持闭区间约定。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q009 · D1：六需求对照 · 当前基线

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：RC两次读取100、70，RR第二次100，失败后完整重试均正确。有明确提交时间的状态追踪与规则比较，不因三个子问自动升hard。

**原题干**

Two sessions run this schedule against a table accounts(id, balance) with initial rows (1, 100) and (2, 100). Session A: BEGIN; UPDATE accounts SET balance = balance - 30 WHERE id = 1; UPDATE accounts SET balance = balance + 30 WHERE id = 2; (no COMMIT yet). Session B: BEGIN; SELECT balance FROM accounts WHERE id = 1; (ordinary read, under PostgreSQL Read Committed). Then Session A executes COMMIT, and Session B runs the same SELECT again inside its still-open transaction. (a) State what Session B's first SELECT and second SELECT each are allowed to see, and explain the difference using the isolation rule. (b) Suppose instead Session B runs under Repeatable Read with its first SELECT as the first non-transaction-control statement; state what its second SELECT sees and why. (c) If a transaction in this system aborts with a serialization failure, explain what the application must retry and why retrying only the last failed statement is inadequate.

**原参考答案（保持原样，可能有错）**

(a) Under Read Committed, Session B's first SELECT sees only rows committed before that statement began, so it sees balance = 100 for id = 1; it does not see Session A's unfinished writes. After Session A commits, Session B's second SELECT sees rows committed before that new statement began, so it now sees balance = 70 for id = 1. The change is allowed because Read Committed takes a fresh view per statement. (b) Under Repeatable Read, ordinary queries use the snapshot from the transaction's first non-transaction-control statement, so Session B's second SELECT still sees balance = 100 for id = 1; Session A's concurrent commit does not change that view between successive reads. (c) A serialization failure means the application must retry the complete transaction, including the reads and the application decisions that selected the writes. Retrying only the final failed statement is inadequate because it can reuse decisions made from a state that is no longer appropriate. A retry can itself fail, so a considered retry policy is needed rather than assuming one attempt always succeeds.

**原解释（保持原样）**

The item applies the fixture's stated PostgreSQL semantics to a small schedule: Read Committed gives a per-statement view, Repeatable Read gives a transaction-level snapshot from the first non-transaction-control statement, and a serialization failure requires rerunning the whole transaction because the reads and dependent decisions must be re-evaluated. Note that a stable snapshot does not by itself guarantee serializable outcomes. These are the fixture's modeling assumptions, not measured database results.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q010 · D1：六需求对照 · 支架与迁移控制

目标：medium；题目级综合分：92.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 3/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：读取和回滚后的数值均正确；解释“原子性保证扣款与入账要么都提交”套用了题中不存在的入账操作。原子性只覆盖实际纳入该事务的操作；本例回滚后总量200成立。

**原题干**

某 PostgreSQL 数据库初始账户表为：账户 A 余额 100，账户 B 余额 100，总量不变式要求 A+B 始终等于 200。两个会话按下列顺序交错执行，默认使用普通查询：

会话1：BEGIN；UPDATE 账户 SET 余额 = 余额 - 30 WHERE 名称 = 'A'；（尚未 COMMIT）
会话2：BEGIN；SELECT 余额 FROM 账户 WHERE 名称 = 'A'；
会话1：COMMIT；
会话2：再次 SELECT 余额 FROM 账户 WHERE 名称 = 'A'；COMMIT；

请回答：(1) 若会话2 的隔离级别是 Read Committed，两次 SELECT 各允许看到 A 的什么余额？(2) 若会话2 的隔离级别是 Repeatable Read，两次 SELECT 各允许看到什么余额？(3) 会话1 在 COMMIT 前若发生失败并 ROLLBACK，会话2 在 Read Committed 下第一次 SELECT 看到的 A 余额会是什么？请结合原子性说明此时总量不变式是否被破坏。

**原参考答案（保持原样，可能有错）**

(1) Read Committed：第一次 SELECT 在会话1 提交前执行，看不到未提交的扣款，允许看到 A=100；第二次 SELECT 在会话1 提交后执行，允许看到新提交结果 A=70。
(2) Repeatable Read：会话2 的普通查询使用本事务第一条非事务控制语句对应的快照，因此两次 SELECT 都允许看到 A=100，不因会话1 的提交而改变视图。
(3) 会话1 ROLLBACK 会取消未提交修改，A 回到 100；会话2 第一次 SELECT 本就看不到未提交写入，仍看到 A=100。原子性保证扣款与入账要么都提交要么都不提交，这里只发生扣款且被回滚，A+B 仍为 200，总量不变式未被破坏。

**原解释（保持原样）**

解题时先按隔离级别判断每次读取允许看到的状态：Read Committed 下普通 SELECT 看到语句开始前已提交的数据以及本事务此前的修改，所以提交前后两次读取结果不同；Repeatable Read 下普通查询固定在本事务第一条非事务控制语句的快照上，所以两次读取一致。再区分未提交写入与已提交状态：未提交的扣款对其他事务不可见，ROLLBACK 取消该修改，因此原子性未被破坏，A+B=200 的不变式保持成立。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q011 · D1：六需求对照 · 评分要点先行

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：题干已给闭区间约定；更新left=mid+1可从资料直接识别，无需状态追踪或方法选择。

**原题干**

在资料给出的闭区间二分查找中，数组按升序排列、元素互异，初始 left=0、right=n-1，循环条件为 left<=right。若某一轮中中间值小于目标值，应如何更新边界？

A. left = mid + 1
B. right = mid - 1
C. left = mid
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

资料规定：闭区间 [left, right] 保存仍可能包含目标的位置。中间值小于目标时，mid 及其左侧位置都不可能命中，因此把 left 更新为 mid+1，区间缩小为 [mid+1, right]。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q012 · D1：六需求对照 · 当前基线

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：明确的单规则识别题，A正确且解释与有序数组排除逻辑一致。

**原题干**

在资料采用的闭区间 [left, right] 二分查找中，数组按升序排列且元素互异。若某一轮取到 mid 后，发现中间值小于目标值，下一步应如何更新边界？（依据片段 fixture_binary_search_zh）

A. left = mid + 1
B. left = mid
C. right = mid - 1
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

闭区间 [left, right] 保存所有仍可能包含目标的位置。中间值小于目标，说明 mid 及其左侧位置都不可能命中，且 mid 已被排除，因此令 left = mid + 1（fixture_binary_search_zh）。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q013 · D1：六需求对照 · 三档对照

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：S2在两次读取间提交，RC读B=200，RR读B=100；条件性序列化失败的完整重试说明正确。任务是具体交错应用与比较。

**原题干**

两个会话在 PostgreSQL 默认隔离级别（Read Committed）下并发操作，初始表 accounts 内容为：A 余额 100，B 余额 100。

会话 S1：
BEGIN;
SELECT balance FROM accounts WHERE name='A';   -- 语句1
（此时读到 A=100）
SELECT balance FROM accounts WHERE name='B';   -- 语句2

会话 S2 在 S1 的语句1与语句2之间执行并提交：
BEGIN;
UPDATE accounts SET balance=balance-100 WHERE name='A';
UPDATE accounts SET balance=balance+100 WHERE name='B';
COMMIT;

请回答：
(1) S1 的语句2 读到 B 的余额是多少？请依据 Read Committed 的可见性规则说明理由。
(2) 如果 S1 改用 Repeatable Read，语句2 读到 B 的余额会是多少？请说明快照规则如何导致这一差异。
(3) 若 S1 在 Serializable 下因序列化异常被拒绝，应用应如何重试？请说明重试范围并给出理由。

**原参考答案（保持原样，可能有错）**

(1) 语句2 读到 B=200。Read Committed 下普通 SELECT 看到语句开始前已经提交的数据，S2 在语句2开始前已提交，因此 S1 的语句2 能看到 S2 把 B 从 100 改为 200 的结果。
(2) 语句2 读到 B=100。Repeatable Read 让普通查询使用本事务第一条非事务控制语句对应的快照，S1 的语句1 建立快照时 S2 尚未提交，因此后续查询不会因 S2 的提交而改变视图。
(3) 应重试整个事务，包括重新读取数据以及据此选择写入操作的应用逻辑；不能只重试最后一条失败语句，否则可能继续使用失效的决策。重试本身也可能再次失败，不能承诺一次重试必定成功。

**原解释（保持原样）**

本题把 Read Committed 与 Repeatable Read 的可见性规则放到同一段具体交错中比较：Read Committed 以语句开始时刻为界，所以后一条 SELECT 能看到 S2 新提交的结果；Repeatable Read 以事务第一条非事务控制语句的快照为界，所以视图保持不变。第(3)问要求把“序列化失败后重试整个事务”的规则应用到该情境，强调重试必须覆盖依赖读取结果的决策逻辑，而不是只重发失败语句。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q014 · v2：单需求格式验证 · 支架与迁移控制

目标：medium；题目级综合分：0.0/100；严格达标：否；完整材料原校验：未通过。

原回复没有可评分的单题或不能解析，按协议计0分；不生成虚构评语。

## Q015 · D1：六需求对照 · 输出前自检

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：初值与循环条件属于同一闭区间约定的直接复述，A唯一正确，不因同时列三个符号而上调难度。

**原题干**

In the supplied notes, binary search is described for an ascending array with distinct values and zero-based indices. Using the closed interval [left, right], what are the initial values of left and right, and what is the loop condition?

A. left = 0, right = n - 1, and loop while left <= right
B. left = 0, right = n, and loop while left < right
C. left = 0, right = n - 1, and loop while left < right
D. left = 1, right = n, and loop while left <= right

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

The notes state that for the closed interval [left, right], left starts at zero and right starts at n minus one, and the loop runs while left <= right; an empty interval means the target is absent.

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q016 · D1：六需求对照 · 输出前自检

目标：hard；题目级综合分：65.0/100；严格达标：否；完整材料原校验：通过。

我的难度判断：medium；置信度：medium。

正确性 2/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：任务主要是给定两算法的模拟与比较，所有任务完成是这里自动满足的条件；最小平均响应的选择无需处理实质冲突约束，最后泛论其他目标可直接援引资料，因此评medium。RR队列应B,C,A，平均响应1、周转20/3；原RR数值错，STCF部分正确。

**原题干**

Consider three independent CPU-bound jobs on one processor. Each job has a single CPU burst and no I/O. Arrival times and required CPU service are: A arrives at time 0 and needs 6 units; B arrives at time 1 and needs 3 units; C arrives at time 2 and needs 1 unit. Ignore context-switch overhead. Ties are resolved alphabetically. You are choosing between two policies: (1) Round Robin with a time slice of 2 units, where a newly arriving job is enqueued before the preempted job when both occur at the same boundary; and (2) Shortest Time-to-Completion First (STCF), which is preemptive and selects the job with the least remaining processing time. For each policy, give the first-run time and completion time of every job, then compute average response time and average turnaround time. Finally, recommend one policy for a system whose primary objective is minimizing average response time while still completing all jobs, and justify your recommendation using your computed values and the stated constraint. Address whether the policy with the better average response time is necessarily best for every objective.

**原参考答案（保持原样，可能有错）**

Round Robin (slice = 2): A runs 0-2; B arrives at 1 and waits; C arrives at 2. At time 2, A is preempted and C is enqueued before A. Queue order after time 2: C, B, A. C runs 2-3 and finishes (completion 3). B runs 3-5; at time 5 B still needs 1, so A runs 5-7; B runs 7-8 and finishes (completion 8). A runs 8-10 and finishes (completion 10). First-run times: A = 0, B = 3, C = 2. Response times: A = 0, B = 2, C = 0. Average response time = (0 + 2 + 0)/3 = 2/3. Turnaround times: A = 10 - 0 = 10; B = 8 - 1 = 7; C = 3 - 2 = 1. Average turnaround time = (10 + 7 + 1)/3 = 6. STCF: at time 0 only A is available, so A runs 0-1. At time 1, B arrives with remaining 3 while A has remaining 5, so B runs 1-2. At time 2, C arrives with remaining 1, so C runs 2-3 and finishes (completion 3). Then B has remaining 2 and A has remaining 5, so B runs 3-5 and finishes (completion 5). A runs 5-10 and finishes (completion 10). First-run times: A = 0, B = 1, C = 2. Response times: A = 0, B = 0, C = 0. Average response time = 0. Turnaround times: A = 10, B = 4, C = 1. Average turnaround time = (10 + 4 + 1)/3 = 5. Recommendation: STCF, because it gives a lower average response time (0 versus 2/3) and also a lower average turnaround time (5 versus 6) under the stated workload, so it better satisfies the primary objective. However, the better average response time does not by itself establish that a policy is best for every objective: the same fixture notes that neither a smaller average response time nor a smaller switching fraction alone establishes that a policy is best for every objective. For example, a different objective such as fairness, a maximum response-time bound, or switching overhead could favor another policy, and the recommendation depends on the stated workload and requirements.

**原解释（保持原样）**

The key steps are to build a reproducible timeline for each policy, compute first-run and completion times, derive response and turnaround times, and then compare against the stated objective. Round Robin must follow the stated boundary rule: at time 2, C is enqueued before the preempted A. STCF must be preemptive and choose the least remaining time at each decision point. The final judgment must connect the computed averages to the objective and acknowledge that one metric does not settle all objectives.

资料键：`fixture_cpu_scheduling_en`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q017 · D1：六需求对照 · 支架与迁移控制

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：闭区间循环条件与右边界更新均在资料中明确列出；题干没有需要实际追踪的数组，属于识别规则而非具体情境应用。

**原题干**

Using the closed-interval convention [left, right] described in the notes, which statement correctly pairs the loop condition with the update applied when the middle value is larger than the target? (fixture_binary_search_en)

A. Loop while left <= right; set right = mid - 1
B. Loop while left < right; set right = mid
C. Loop while left <= right; set left = mid + 1
D. Loop while left < right; set right = mid - 1

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

In the closed convention the interval [left, right] is nonempty while left <= right, and when the middle value is larger than the target, positions from mid onward are too large, so right = mid - 1 (fixture_binary_search_en).

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q018 · D1：六需求对照 · 当前基线

目标：medium；题目级综合分：17.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：uncertain；置信度：high。

正确性 1/4 · 资料支持 2/4 · 可作答性 1/4 · 清晰度 1/4。

**评分理由**：题干同时给出T首次读取100和U在首次读取前已提交200，两者在所述规则下矛盾；答案又把U提交说成在快照之后。若按提交顺序应读200。重试及原子性部分可用，但不能可靠给矛盾任务分档。

**原题干**

某应用在 PostgreSQL 的 Repeatable Read 隔离级别下运行一个事务 T：T 首先执行普通 SELECT 读取账户 A 的余额为 100，据此决定向账户 B 转入 30，并执行相应写入，最后提交。与此同时，另一个事务 U 在 T 开始后、T 的第一次 SELECT 之前已经把 A 的余额改为 200 并提交。请回答：(1) T 的第一次 SELECT 会看到 A 的余额是多少？为什么？(2) 如果 T 因序列化异常而失败，应用只重试最后一条失败的写入语句，而不重新读取 A 的余额，可能产生什么问题？(3) 结合原子性，说明 T 的扣款与入账为什么必须作为一个单元提交或回滚。

**原参考答案（保持原样，可能有错）**

(1) T 的第一次 SELECT 看到 100。因为 Repeatable Read 下普通查询使用本事务第一条非事务控制语句对应的快照，U 虽然已经提交，但该提交发生在快照建立之后，所以 T 的连续查询不会因 U 的提交而改变视图。(2) 只重试最后一条失败语句可能继续使用失效的决策：T 原本基于余额 100 决定转 30，而 U 已把余额改为 200；不重新读取 A 的余额就重试写入，可能在不正确的旧决策上继续执行。正确做法是重试整个事务，包括读取数据和据此选择写入操作的应用逻辑。(3) 原子性要求扣款与入账要么都提交、要么都回滚，不能只留下其中一笔已提交；否则会出现资金凭空消失或凭空出现的状态。

**原解释（保持原样）**

本题要求在具体交错情境中应用快照隔离和重试原则。Repeatable Read 的稳定快照来自本事务第一条非事务控制语句；重试必须覆盖依赖读取结果的决策逻辑；原子性则保证转账的两笔修改不可分割。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q019 · D1：六需求对照 · 难度维度约束

目标：medium；题目级综合分：32.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：uncertain；置信度：high。

正确性 2/4 · 资料支持 2/4 · 可作答性 2/4 · 清晰度 3/4。

**评分理由**：RR下A读取旧快照后，B更新同一行并提交，A3再更新该行会序列化失败；不能把最终余额算80，无重试仅B的70保留。该RR写冲突规则未在题内资料给出，限制了(b)的可答性；(a)与完整重试说明正确。

**原题干**

Consider the following educational-fixture schedule. The isolation level is PostgreSQL Repeatable Read for both sessions. Initial table accounts: (id=1, balance=100), (id=2, balance=50). There are no hidden triggers, constraints, background transactions, or external side effects.

Session A: BEGIN; SELECT balance FROM accounts WHERE id=1;  -- statement A1
Session B: BEGIN; UPDATE accounts SET balance = balance - 30 WHERE id=1; COMMIT;  -- statement B1
Session A: SELECT balance FROM accounts WHERE id=1;  -- statement A2
Session A: UPDATE accounts SET balance = balance + 10 WHERE id=1; COMMIT;  -- statement A3

(a) State the value returned by A1 and the value returned by A2, and justify each using the Repeatable Read snapshot rule stated in the notes.
(b) After the schedule completes, what is the committed balance of account id=1? Show how you combine Session A's own change with Session B's committed change, and explain why treating A3's write as committed before A's COMMIT would be incorrect.
(c) Suppose the isolation level were changed to PostgreSQL Serializable and A3 were rejected with a serialization failure. Explain what the application must retry and why retrying only A3 would be insufficient, referring to the role of the reads and decisions in this schedule.

**原参考答案（保持原样，可能有错）**

(a) A1 returns 100. A2 also returns 100. Under Repeatable Read, ordinary queries use the snapshot associated with the transaction's first non-transaction-control statement (here A1), so B1's concurrent commit does not change A's view between A1 and A2.

(b) The committed balance is 100 - 30 + 10 = 80. Session B's committed change (-30) and Session A's own committed change (+10) both apply to the initial 100. A3's write is uncommitted until A's COMMIT, so it must not be counted as a committed state change before then; if A had rolled back instead, only B's -30 would remain committed (balance 70).

(c) The application must retry the complete transaction, including the reads and the application decisions that selected the writes (A1/A2 and the decision leading to A3). Retrying only A3 would reuse a decision made from a state that is no longer appropriate, because the snapshot and the concurrent commits may have changed; the notes state that retrying only the final failed statement can reuse decisions made from a state that is no longer appropriate. A retry can also fail, so a considered retry policy is needed rather than assuming one attempt always succeeds.

**原解释（保持原样）**

This item applies the fixture's stated rules to a concrete two-session schedule. Part (a) tests the Repeatable Read snapshot rule: the snapshot is tied to the first non-transaction-control statement, so A2 keeps seeing 100 even after B1 commits. Part (b) separates an uncommitted write from a committed state change: A3's +10 counts only because A commits, and B's -30 counts because B committed, giving 80; had A rolled back, the balance would be 70. Part (c) tests the retry requirement: a serialization failure means rerunning the whole transaction, including the reads and decisions that selected the writes, because retrying only the failed statement can reuse decisions based on a state that is no longer appropriate, and a retry can itself fail.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q020 · v2：单需求格式验证 · 输出前自检

目标：medium；题目级综合分：72.5/100；严格达标：否；完整材料原校验：通过。

我的难度判断：medium；置信度：medium。

正确性 2/4 · 资料支持 3/4 · 可作答性 2/4 · 清晰度 2/4。

**评分理由**：第一次读取5正确；“后续SELECT仍5”忽略资料中本事务看见自身写入的例外，且未指定后续读取在UPDATE之前还是之后。若自身UPDATE成功后读应见自己的修改，若已失败则不能继续普通读取。重试原则正确，题干需明确事件顺序。

**原题干**

某应用在 PostgreSQL 中使用 Repeatable Read 事务 T 完成一次“先读后写”的库存扣减：T 先执行普通 SELECT 读出库存为 5，据此判断“库存足够”并执行 UPDATE 将库存减 1 后提交。与 T 并发的另一事务已在 T 的第一条非事务控制语句之后提交了一次库存修改，使实际库存变为 4。T 提交时数据库报告序列化失败。请分析：(1) T 中第一次 SELECT 与后续 SELECT 在 Repeatable Read 下分别能看到什么，为什么稳定快照不等于并发结果一定等价于逐个执行；(2) 应用应如何重试，只重试最后失败的 UPDATE 是否可行，并说明理由。

**原参考答案（保持原样，可能有错）**

参考答案：(1) 在 Repeatable Read 下，T 的普通查询使用本事务第一条非事务控制语句对应的快照，因此 T 中第一次 SELECT 与后续普通 SELECT 看到的是同一快照中的库存视图（本例读出 5），不会因另一事务在快照之后提交的修改而改变；但稳定快照不代表并发事务的全部结果一定等价于逐个执行，因为 T 基于旧快照做出的“库存足够”判断可能与并发已提交的修改冲突，Serializable 语义下这种冲突会以序列化异常的形式被拒绝，而不是允许提交。(2) 应用应重试整个事务，包括重新执行读取库存并据此判断是否扣减的应用逻辑，而不是只重试最后失败的 UPDATE；因为仅重试最后一条语句会继续使用基于旧快照的失效决策（仍按库存 5 判断），可能再次失败或产生错误结果。重试本身也可能再次失败，不能承诺重试一次就一定成功。

**原解释（保持原样）**

本题要求把 Repeatable Read 的快照可见性规则应用到具体“先读后写”情境，并据此判断重试范围。资料指出 Repeatable Read 下普通查询使用本事务第一条非事务控制语句对应的快照，连续查询不会因其他事务提交而改变视图；同时指出稳定快照不代表并发结果等价于逐个执行，Serializable 会拒绝必要时的那次执行。资料还明确：出现序列化失败时应重试整个事务，包括读取数据和据此选择写入操作的应用逻辑，仅重试最后一条失败语句可能继续使用失效的决策。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q021 · D1：六需求对照 · 当前基线

目标：hard；题目级综合分：47.5/100；严格达标：否；完整材料原校验：通过。

我的难度判断：medium；置信度：medium。

正确性 1/4 · 资料支持 4/4 · 可作答性 2/4 · 清晰度 2/4。

**评分理由**：主体是两种q的模拟比较和时间片权衡解释，未给需实际求解的额外预算/设计边界，评medium。按原到达时间优先的文字又可能与RR队列先后冲突。答案q1为A分配过多服务，q2给B不足服务，不能据其时刻表作出有效比较。

**原题干**

在片段 fixture_cpu_scheduling_zh 给出的教学模型下，考虑单处理器、独立任务、每个任务只有一个 CPU burst 且无 I/O。现有三个任务，到达时间与服务量如下：
A 到达 0，服务量 3；
B 到达 1，服务量 2；
C 到达 2，服务量 1。
时间单位相同。忽略切换开销。任务恰在片尾到达时，规定新到任务先入就绪队列，被抢占任务后入队；若同时有多个任务可用，按到达时间早者优先，到达时间相同按任务名 A、B、C 顺序。
请回答：
（1）采用 RR，时间片 q=1。列出从时刻 0 到全部完成期间每个时间区间运行的任务，并计算 A、B、C 各自的响应时间和周转时间。
（2）采用 RR，时间片 q=2，其他规则相同。列出每个时间区间运行的任务，并计算 A、B、C 各自的响应时间和周转时间。
（3）根据（1）和（2）的结果，结合片段中关于时间片权衡的说明，分析较小时间片是否一定更好。你的回答必须至少讨论首次响应、切换频率或切换开销、以及公平性中的一个具体约束，并给出有依据的判断。

**原参考答案（保持原样，可能有错）**

（1）RR，q=1，忽略切换开销，新到任务先入队。
时间区间：0–1 运行 A；1–2 运行 B（B 到达 1，新到先入队，A 剩余 2 入队）；2–3 运行 C（C 到达 2，新到先入队，B 剩余 1 入队）；3–4 运行 A（A 剩余 2）；4–5 运行 B（B 剩余 1）；5–6 运行 A（A 剩余 1）；6–7 运行 A 完成。
首次运行时刻：A=0，B=1，C=2。
完成时刻：A=7，B=5，C=3。
响应时间：A=0−0=0；B=1−1=0；C=2−2=0。
周转时间：A=7−0=7；B=5−1=4；C=3−2=1。

（2）RR，q=2，忽略切换开销，新到任务先入队。
时间区间：0–2 运行 A；2–3 运行 B（B 到达 1 已在就绪队列，C 到达 2 新到先入队，A 剩余 1 入队；按到达时间 B 先于 C，所以 B 先运行）；3–4 运行 C；4–5 运行 A 完成。
首次运行时刻：A=0，B=2，C=3。
完成时刻：A=5，B=3，C=4。
响应时间：A=0−0=0；B=2−1=1；C=3−2=1。
周转时间：A=5−0=5；B=3−1=2；C=4−2=2。

（3）较小时间片不一定更好。q=1 时所有任务响应时间都为 0，首次响应更早；但 q=1 在 0–7 期间发生了更多次任务切换，若切换需要开销，则切换频率更高、开销占比更大，可能延长完成时刻并降低有效吞吐。q=2 时 A 的周转时间从 7 降到 5，B 的周转时间从 4 降到 2，但 C 的响应时间从 0 变为 1，且 C 的周转时间从 1 变为 2。因此，若目标是最小化所有任务首次响应，q=1 更好；若目标是降低切换频率或改善平均周转时间，q=2 可能更好。一个方案可能满足一个约束，却在另一个指标上更差，所以需要结合具体响应上限、开销预算或公平性约束来判断，不能仅凭平均响应更小或切换占比更低就断言某策略适合所有目标。

**原解释（保持原样）**

先按 RR 规则逐步维护就绪队列，记录每个任务的首次运行时刻和完成时刻，再套用响应时间与周转时间定义。q=1 与 q=2 的差异说明时间片大小会改变首次响应和完成时刻；片段 fixture_cpu_scheduling_zh 明确指出较小时间片可改善首次响应却增加切换频率，较大时间片可分摊切换开销却可能延长等待，且平均响应更小或切换占比更低都不能单独证明策略适合所有目标。

资料键：`fixture_cpu_scheduling_zh`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q022 · D1：六需求对照 · 当前基线

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：直接识别中值小于目标时的更新规则，A唯一正确，解释有资料支持。

**原题干**

Using the closed interval [left, right] convention for binary search on an ascending array with distinct values, suppose the middle value is smaller than the target. Which boundary update is correct?

A. left = mid + 1
B. left = mid
C. right = mid - 1
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

In the closed-interval convention, if the middle value is smaller than the target, every position through mid is too small, so the eligible interval becomes [mid + 1, right].

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q023 · D1：六需求对照 · 三档对照

目标：hard；题目级综合分：65.0/100；严格达标：否；完整材料原校验：通过。

我的难度判断：hard；置信度：medium。

正确性 1/4 · 资料支持 3/4 · 可作答性 2/4 · 清晰度 2/4。

**评分理由**：要求在响应上限下最小化切换次数，任务意图为hard。未给切换耗时且未说忽略，首次运行和可行q不可唯一确定；即使额外假设耗时0，正确不同任务切换次数为10/5/3，原13/7/4还混入多余服务与同任务续跑。

**原题干**

Using the supplied scheduling model, consider three independent jobs that all arrive at time 0 and each require one CPU burst with no I/O: A requires 8 units, B requires 4 units, and C requires 2 units. The processor is single and never serves two jobs simultaneously. Switching overhead applies only when moving between different jobs and has no initial dispatch charge; arrivals cannot occur while switching. The scheduler is Round Robin with a fixed time slice q. A job that finishes before its slice ends does not use the remaining slice. Ties are resolved alphabetically. You must recommend a time slice q from the options q = 1, q = 2, or q = 4 that keeps the maximum response time at or below 2 units while using the fewest context switches. Show the first-run times and the number of context switches for each candidate, then justify your recommendation. Explain how your recommendation would change if the maximum response-time constraint were removed and the only objective were minimizing context switches.

**原参考答案（保持原样，可能有错）**

For q = 1: order A, B, C, A, B, C, A, B, A, B, A, B, A, A. First-run times: A = 0, B = 1, C = 2. Maximum response time = 2. Context switches: 13. For q = 2: order A, B, C, A, B, A, B, A. First-run times: A = 0, B = 2, C = 4. Maximum response time = 4. Context switches: 7. For q = 4: order A, B, C, A, A. First-run times: A = 0, B = 4, C = 8. Maximum response time = 8. Context switches: 4. Only q = 1 satisfies the maximum response-time constraint of 2 units. Therefore recommend q = 1. If the response-time constraint were removed and the only objective were minimizing context switches, q = 4 would be preferred because it uses the fewest context switches among the candidates. This shows that the time-slice choice depends on the stated objective and constraints.

**原解释（保持原样）**

Compute first-run times by tracking the Round Robin order and the first time each job is selected. Response time is first-run time minus arrival time; since all jobs arrive at 0, it is the first-run time. Count context switches as transitions between different jobs. Compare candidates against the stated constraint and objective, then state how the recommendation changes when the constraint is removed.

资料键：`fixture_cpu_scheduling_en`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q024 · D1：六需求对照 · 评分要点先行

目标：easy；题目级综合分：92.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 3/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：正确选项A完整匹配闭区间算法，难度仍为识别资料。解释将B和C概称为half-open behavior不准确：B的left=mid和C的left<=right均不是资料给出的正确半开区间算法，应说明它们混用了或破坏了规则。主要选择答案不受影响。

**原题干**

According to the supplied notes, in the closed-interval binary search on an ascending array with distinct values and zero-based indexing, which statement correctly describes the interval convention and its boundary updates?

A. The interval [left, right] is initially [0, n - 1]; the loop runs while left <= right; a middle value smaller than the target sets left = mid + 1, and a larger one sets right = mid - 1.
B. The interval [left, right] is initially [0, n]; the loop runs while left < right; a middle value smaller than the target sets left = mid, and a larger one sets right = mid.
C. The interval [left, right) is initially [0, n]; the loop runs while left <= right; a middle value smaller than the target sets left = mid + 1, and a larger one sets right = mid.
D. The interval [left, right] is initially [0, n - 1]; the loop runs while left < right; a middle value smaller than the target sets left = mid + 1, and a larger one sets right = mid.

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

The notes state that a closed search interval [left, right] contains every eligible position, starts with left = 0 and right = n - 1, loops while left <= right, and updates left = mid + 1 when the middle value is smaller and right = mid - 1 when it is larger. Option B and C describe half-open behavior, and option D mixes the closed initial boundaries with the half-open loop condition.

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q025 · D1：六需求对照 · 难度维度约束

目标：hard；题目级综合分：85.0/100；严格达标：否；完整材料原校验：通过。

我的难度判断：hard；置信度：high。

正确性 2/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：需在响应主目标、开销次目标之间评价两方案；规则虽特殊但提前完成免切换费已明确。答案未遵守这条例外：R2 B结束后不应再加1，R4 B/C提前结束后均应免费。响应/周转/开销比较必须据正确时间线重算。

**原题干**

Consider a single-processor system with three independent CPU-bound jobs, each consisting of one CPU burst with no I/O. Arrival times and required CPU service are:

- Job A: arrives at time 0, requires 6 units of CPU service.
- Job B: arrives at time 1, requires 3 units of CPU service.
- Job C: arrives at time 2, requires 2 units of CPU service.

You must choose between two policies:

- Policy R2: Round Robin with a time slice of 2 units.
- Policy R4: Round Robin with a time slice of 4 units.

For both policies, assume switching overhead is 1 unit and applies only when the processor moves between different jobs; there is no initial dispatch charge. Arrivals can occur during switching and enter the ready queue immediately. If a job finishes before its slice ends, the next job starts immediately with no switching overhead for that transition. If a job arrives exactly at a slice boundary, it is enqueued before the preempted job. Resolve ties by alphabetical job name.

Your task: Compute each job's first-run time and completion time under both policies, then compute the average response time and average turnaround time for each policy. Finally, recommend one policy for a workload where the primary objective is minimizing average response time and the secondary objective is minimizing switching overhead. Justify your recommendation by referencing the computed metrics and the constraints. State any assumption you need to make about how switching overhead interacts with the scheduling model.

**原参考答案（保持原样，可能有错）**

A correct answer should include the following computations and reasoning.

Policy R2 (time slice = 2, switching overhead = 1 between different jobs):

Timeline:
- t=0: A runs (slice 0-2). A remaining = 4.
- t=2: switch to B (overhead 1). B first runs at t=3.
- t=3-5: B runs (slice 3-5). B remaining = 1.
- t=5: switch to C (overhead 1). C first runs at t=6.
- t=6-8: C runs (slice 6-8). C finishes at t=8.
- t=8: switch to A (overhead 1). A runs at t=9.
- t=9-11: A runs (slice 9-11). A remaining = 2.
- t=11: switch to B (overhead 1). B runs at t=12.
- t=12-13: B runs (slice 12-13). B finishes at t=13.
- t=13: switch to A (overhead 1). A runs at t=14.
- t=14-16: A runs (slice 14-16). A finishes at t=16.

First-run times: A=0, B=3, C=6.
Completion times: A=16, B=13, C=8.
Response times: A=0-0=0, B=3-1=2, C=6-2=4. Average response time = (0+2+4)/3 = 2.
Turnaround times: A=16-0=16, B=13-1=12, C=8-2=6. Average turnaround time = (16+12+6)/3 = 34/3 ≈ 11.33.

Policy R4 (time slice = 4, switching overhead = 1 between different jobs):

Timeline:
- t=0: A runs (slice 0-4). A remaining = 2.
- t=4: switch to B (overhead 1). B first runs at t=5.
- t=5-8: B runs (slice 5-8). B finishes at t=8.
- t=8: switch to C (overhead 1). C first runs at t=9.
- t=9-11: C runs (slice 9-11). C finishes at t=11.
- t=11: switch to A (overhead 1). A runs at t=12.
- t=12-14: A runs (slice 12-14). A finishes at t=14.

First-run times: A=0, B=5, C=9.
Completion times: A=14, B=8, C=11.
Response times: A=0-0=0, B=5-1=4, C=9-2=7. Average response time = (0+4+7)/3 = 11/3 ≈ 3.67.
Turnaround times: A=14-0=14, B=8-1=7, C=11-2=9. Average turnaround time = (14+7+9)/3 = 30/3 = 10.

Recommendation: Policy R2 is preferable for the primary objective of minimizing average response time, because its average response time (2) is lower than Policy R4's (3.67). However, Policy R4 has lower average turnaround time (10 vs. 11.33) and fewer context switches (3 switches vs. 5 switches in R2), so it better satisfies the secondary objective of minimizing switching overhead. A complete recommendation should acknowledge this tradeoff and state which objective is prioritized. If the primary objective is strictly average response time, choose R2; if switching overhead is weighted more heavily, R4 may be preferred despite worse response time.

Assumption: Switching overhead is charged only when the processor moves between different jobs, and arrivals during switching enter the ready queue immediately. If a job finishes before its slice ends, no switching overhead is charged for that transition.

**原解释（保持原样）**

This question requires integrating several scheduling concepts: Round Robin time-slice effects, response time vs. turnaround time, switching overhead, and multi-objective policy evaluation. Students must compute timelines under two policies, derive both metrics, and then justify a recommendation under stated constraints. The answer cannot be obtained by recalling a definition; it requires applying the scheduling model, analyzing tradeoffs, and evaluating which policy best meets the stated objectives.

资料键：`fixture_cpu_scheduling_en`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q026 · D1：六需求对照 · 难度维度约束

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：初始化与循环条件均可从资料直接取得，A唯一正确；没有迁移或策略选择要求。

**原题干**

According to the supplied notes (fixture_binary_search_en), in the closed-interval exact-match binary search on an ascending array of n distinct values, which description correctly states the initial boundaries and the loop condition?

A. left = 0, right = n - 1, and the loop runs while left <= right
B. left = 0, right = n, and the loop runs while left < right
C. left = 0, right = n - 1, and the loop runs while left < right
D. left = 0, right = n, and the loop runs while left <= right

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

The notes state that for the closed interval [left, right], left starts at zero and right starts at n minus one, and the loop runs while left <= right; an empty interval means the target is absent.

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q027 · D1：六需求对照 · 评分要点先行

目标：medium；题目级综合分：92.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 3/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：A=70来自S1自己尚未提交的写入，B在RC为130、RR为100，数值正确。但答案又说该行在语句前已提交，容易把新版本可见性与自身写例外混淆；应明确70尚未提交也对自身可见。

**原题干**

Two sessions run against the same table, which initially holds account rows A = 100 and B = 100. Both sessions use ordinary reads (not locking reads), there are no hidden triggers, constraints, background transactions, or external side effects, and the only relevant changes are the ones listed below.

Session 1:
1. BEGIN
2. UPDATE accounts SET balance = balance - 30 WHERE name = 'A'
3. SELECT balance FROM accounts WHERE name = 'A'

Session 2:
1. BEGIN
2. UPDATE accounts SET balance = balance + 30 WHERE name = 'B'
3. COMMIT

Session 1 then runs:
4. SELECT balance FROM accounts WHERE name = 'B'
5. COMMIT

Assume the interleaving is: Session 1 statements 1-3 all begin and finish before Session 2 statement 2 begins, and Session 2 statement 3 (COMMIT) finishes before Session 1 statement 4 begins.

(a) Under PostgreSQL Read Committed, what does Session 1 statement 3 read for A, and what does Session 1 statement 4 read for B? Justify each value using the snapshot rule for that isolation level.
(b) Under PostgreSQL Repeatable Read instead, what does Session 1 statement 4 read for B? Justify using the snapshot rule for that isolation level.
(c) Suppose the same application instead runs under PostgreSQL Serializable and the commit of Session 1 is rejected with a serialization failure. Describe what the application should retry, and justify why retrying only the final failed statement is not enough.

**原参考答案（保持原样，可能有错）**

(a) Read Committed: statement 3 reads A = 70. Session 1's own earlier change (the debit of 30) is visible to it, and the row was committed before the statement began. Statement 4 reads B = 130, because under Read Committed an ordinary SELECT sees rows committed before that statement began, and Session 2 committed B = 130 before Session 1 statement 4 began. (b) Repeatable Read: statement 4 reads B = 100. Session 1's ordinary queries use the snapshot associated with its first non-transaction-control statement, so Session 2's concurrent commit does not change Session 1's view between successive reads. (c) The application should retry the complete transaction, including the reads and the application decisions that selected the writes. Retrying only the final failed statement can reuse decisions made from a state that is no longer appropriate, so the reads and decisions must be rerun together with the writes. A retry can itself fail, so the application also needs a considered retry policy rather than assuming one attempt always succeeds.

**原解释（保持原样）**

Mark the transaction boundaries first: Session 1's BEGIN and statements 1-3 happen before Session 2's UPDATE, and Session 2's COMMIT happens before Session 1 statement 4. Under Read Committed, each ordinary SELECT sees rows committed before that statement began plus the transaction's own earlier changes, so statement 3 sees Session 1's own debit (A = 70) and statement 4 sees Session 2's committed credit (B = 130). Under Repeatable Read, ordinary queries use the snapshot from Session 1's first non-transaction-control statement, so Session 1's later read of B does not pick up Session 2's concurrent commit and still reads B = 100. Under Serializable, a rejected commit is a serialization failure, and the required response is to retry the whole transaction, because the reads and the application decisions built on them must be recomputed against an appropriate state; retrying just the last statement can reuse stale decisions, and a retry may fail again, so a retry policy is needed.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q028 · D1：六需求对照 · 三档对照

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：只问闭区间right初值，B=n-1有直接依据，定义清楚。

**原题干**

在资料采用的闭区间 [left, right] 二分查找中，初始 right 的值是什么？

A. n
B. n-1
C. 0
D. mid

**原参考答案（保持原样，可能有错）**

B

**原解释（保持原样）**

资料写明闭区间 [left, right] 初始 left=0、right=n-1，因此选 n-1。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q029 · D1：六需求对照 · 输出前自检

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：单一更新规则的直接辨认，A正确；解释足以说明mid已排除。

**原题干**

本资料采用闭区间 [left, right] 保存所有仍可能包含目标的位置，数组按升序排列且元素互异。若某轮中 mid 位置的元素小于目标值，按资料应如何更新边界？

A. left = mid + 1
B. left = mid
C. right = mid - 1
D. right = mid

**原参考答案（保持原样，可能有错）**

A

**原解释（保持原样）**

资料规定：闭区间下，若中间值小于目标，将 left 更新为 mid+1，因为 mid 位置的元素已被比较并排除。

资料键：`fixture_binary_search_zh`；核查依据：[sources.json](sources.json)。

## Q030 · D1：六需求对照 · 支架与迁移控制

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：R1/R2均100；会话写不同账户且无其他写，最终A=150、B=110。对普通读取快照和自身写入分开说明，重试规则正确；无需设计新的方案。

**原题干**

Two sessions run the schedule below against a table `accounts(name, balance)` whose initial rows are exactly: ('A', 100), ('B', 100). Each session executes its statements in the listed order, and the interleaving is given by the step numbers. All reads are ordinary reads (not locking reads). There are no hidden triggers, constraints, background transactions, or external side effects.

1. Session 1: BEGIN (isolation level Repeatable Read).
2. Session 2: BEGIN (isolation level Repeatable Read).
3. Session 1: SELECT balance FROM accounts WHERE name = 'A';  -- read R1
4. Session 2: UPDATE accounts SET balance = balance + 50 WHERE name = 'A';
5. Session 2: COMMIT;
6. Session 1: SELECT balance FROM accounts WHERE name = 'A';  -- read R2
7. Session 1: UPDATE accounts SET balance = balance + 10 WHERE name = 'B';
8. Session 1: COMMIT;

Using only the PostgreSQL semantics stated in the notes (fixture_transactions_en):
(a) State the value returned by R1 and the value returned by R2, and justify each value by referring to the snapshot rule for Repeatable Read.
(b) State the final committed balance of 'A' and of 'B', and explain how the update in step 7 relates to the snapshot observed by Session 1.
(c) Suppose a later run of this same schedule is rejected with a serialization failure. Explain what the application must retry, and why retrying only the final failed statement would be incorrect.

**原参考答案（保持原样，可能有错）**

(a) R1 returns 100 and R2 returns 100. Under PostgreSQL Repeatable Read, ordinary queries use a snapshot associated with the transaction's first non-transaction-control statement (step 3 for Session 1), so Session 2's commit of the +50 update in steps 4–5 does not change Session 1's view between R1 and R2 (fixture_transactions_en).

(b) Final committed balance of 'A' is 150 and of 'B' is 110. Session 2's update committed at step 5, so 'A' becomes 150. Session 1's step 7 update writes +10 to 'B' relative to the current committed row and commits at step 8, giving 'B' = 110; the stable Repeatable Read snapshot governs what Session 1's ordinary reads observe, and it does not prevent Session 1's own write from being applied and committed (fixture_transactions_en).

(c) The application must retry the complete transaction, including the reads and the application decisions that selected the writes. A serialization failure means the required guarantee could not be maintained and the execution may be rejected rather than committed (fixture_transactions_en). Retrying only the final failed statement would reuse decisions made from a state that is no longer appropriate, so the retried work would not correspond to a fresh, consistent set of reads and decisions (fixture_transactions_en). The retry itself can also fail, so a considered retry policy is needed rather than assuming one attempt always succeeds (fixture_transactions_en).

**原解释（保持原样）**

This item applies the notes' snapshot and retry rules to a concrete two-session schedule. Part (a) tests the Repeatable Read snapshot rule: Session 1's view is fixed by its first non-transaction-control statement, so R2 still shows 100 even though Session 2 committed +50. Part (b) separates snapshot visibility from committed state changes: 'A' is 150 because Session 2 committed, and 'B' is 110 because Session 1's own write is applied and committed. Part (c) tests the retry requirement: because a serialization failure may reject the execution, the whole transaction — reads, decisions, and writes — must be rerun, not just the last statement.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q031 · D1：六需求对照 · 评分要点先行

目标：hard；题目级综合分：47.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：medium；置信度：medium。

正确性 1/4 · 资料支持 4/4 · 可作答性 2/4 · 清晰度 2/4。

**评分理由**：主要要求用固定规则计算并比较q，未给具体需共同满足的设计预算，判medium；片尾到达与回队的先后未明确，字母平局是否涵盖事件排序也不清。答案给B过量服务、A不足服务，给A到A计费，并未从首次/结束时刻减到达时间，存在多处独立实质错误。

**原题干**

Model: one processor; jobs are independent, each a single CPU burst with no I/O; the processor never serves two jobs at once. Jobs (name, arrival time, required CPU service): A(0, 6), B(1, 3), C(2, 1). Use Round Robin with a time slice of 2 time units. Switching overhead is charged only when the processor moves between two different jobs, costs 1 time unit, and no initial dispatch charge applies; arrivals during switching enter the ready queue in arrival order. If a job finishes before its slice ends, it does not use the remaining slice. Ties are broken alphabetically. Overhead time delivers no CPU service to any job.

(a) Build the timeline and report each job's first-run time and completion time, then compute the average response time and average turnaround time.
(b) A designer wants to reduce the average response time and proposes shortening the time slice to 1 time unit. Using the same jobs, arrivals, and overhead rule, compute the new average response time and average turnaround time, and state whether the proposal meets its stated objective.
(c) Recommend a slice length for this workload and objective, and justify your recommendation with reference to the tradeoff between initial responsiveness and switching frequency, naming at least one constraint a recommendation must respect.

**原参考答案（保持原样，可能有错）**

(a) Slice = 2, overhead = 1 per switch between different jobs, no initial dispatch charge. Timeline: A runs 0-2 (first run A=0); switch 2-3; B runs 3-5 (first run B=3); switch 5-6; C runs 6-7 and finishes (first run C=6, completion C=7); switch 7-8; A runs 8-10; switch 10-11; B runs 11-13 and finishes (completion B=13); switch 13-14; A runs 14-16 and finishes (completion A=16). First-run times: A=0, B=3, C=6. Completion times: A=16, B=13, C=7. Average response time = (0+3+6)/3 = 3. Average turnaround time = (16+13+7)/3 = 36/3 = 12.

(b) Slice = 1, same overhead rule. Timeline: A 0-1 (A first run 0); switch 1-2; B 2-3 (B first run 2); switch 3-4; C 4-5 and finishes (C first run 4, completion C=5); switch 5-6; A 6-7; switch 7-8; B 8-9; switch 9-10; A 10-11; switch 11-12; B 12-13 and finishes (completion B=13); switch 13-14; A 14-15; switch 15-16; A 16-17 and finishes (completion A=17). First-run times: A=0, B=2, C=4. Completion times: A=17, B=13, C=5. Average response time = (0+2+4)/3 = 2, which is lower than 3, so the stated objective (reducing average response time) is met. Average turnaround time = (17+13+5)/3 = 35/3 ≈ 11.67, slightly better here, but the gain is small because more switches occur.

(c) A defensible recommendation states the objective and constraints, e.g., "choose the slice to lower average response time while keeping switching overhead within a stated budget." For this workload, slice = 1 gives the lower average response time (2 vs 3) but requires more switches (8 vs 4), so it spends more time on overhead; slice = 2 amortizes switching better and still gives reasonable first access. A recommendation is only justified relative to the stated objective and constraints (maximum response time, switching budget, or fairness), because a policy can satisfy one constraint while losing on another metric; shorter slices can improve initial responsiveness but increase context-switch frequency, and larger slices amortize switching costs but can lengthen waits before a different job first runs.

**原解释（保持原样）**

Turnaround time is completion minus arrival; response time is first run minus arrival, so a job can start early yet finish late (fixture_cpu_scheduling_en). The timelines above follow the fixture's modeling conventions: one processor, one burst per job, no service during switching, no initial dispatch charge, overhead only between different jobs, arrivals during switching enqueued in arrival order, and alphabetical tie-breaking. The comparison shows the stated objective (average response time) improving with a shorter slice while switching frequency rises, so the recommendation must name the objective and the constraint it respects.

资料键：`fixture_cpu_scheduling_en`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q032 · D1：六需求对照 · 三档对照

目标：hard；题目级综合分：77.5/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：hard；置信度：high。

正确性 1/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：响应和总开销双约束加MLFQ调整，属于hard。q1给出的结束时刻与总服务12加开销10矛盾；q3把已等待的A放到了更晚到达的C之后，导致错误宣称q3满足上限。核心可行方案选择不成立，不能靠泛化MLFQ建议弥补。

**原题干**

本课程采用如下自拟教学模型（依据片段 fixture_cpu_scheduling_zh）：单处理器、独立任务、每个任务只有一个 CPU burst 且无 I/O；切换只在切换到另一个任务时计费 1 个时间单位，首次派发免费；切换期间到达的任务在切换结束后入队；任务恰在片尾到达时，新到任务先于被抢占任务入队；平局按任务名升序。现有三个任务：A 在 t=0 到达、服务量 6；B 在 t=2 到达、服务量 3；C 在 t=4 到达、服务量 3。

请设计一个轮转调度（RR）时间片 q 的取值方案，并论证它相对 q=1 和 q=6 的取舍。要求：(1) 对 q=1、q=3、q=6 三种取值，分别写出各任务的首次运行时刻与完成时刻（按上述模型计费），并计算各自的响应时间与周转时间；(2) 在“所有任务响应时间不超过 4 个时间单位”和“总切换开销不超过 4 个时间单位”这两个约束下，判断哪种 q 可行，并说明理由；(3) 若把 RR 换成 MLFQ（依据片段：新任务从高优先级开始，用完 CPU 配额后降级；按累计使用量计算配额；周期性提升优先级），在不需要预知运行时间的前提下，说明应如何设置配额与提升间隔才能同时照顾响应上限与长期等待的低优先级任务，并指出该设计仍需权衡的一个指标。

**原参考答案（保持原样，可能有错）**

按题目模型计算（切换只在切换到另一任务时计费 1，首次派发免费；片尾到达的新任务先入队；平局按名字升序）：

q=1：
- t=0 A 首次运行（A 首次运行=0），t=1 切换 1 单位，t=2 B 到达并入队，t=2 派发 B（B 首次运行=2）。
- 之后按 A、B、C 轮转，C 在 t=4 到达，C 首次运行=4。
- 完成时刻：A 在 t=11 完成，B 在 t=9 完成，C 在 t=13 完成。
- 响应时间：A=0、B=0、C=0；周转时间：A=11、B=7、C=9。
- 切换次数：每次换任务计 1，共 10 次，总切换开销=10。

q=3：
- t=0 A 首次运行=0，运行 3 单位到 t=3，切换 1 单位到 t=4；t=2 B 到达、t=4 C 到达，均在切换期间或之前入队，按到达顺序 B 先于 C。
- t=4 派发 B（B 首次运行=4），运行 3 单位到 t=7 完成，切换 1 单位到 t=8。
- t=8 派发 C（C 首次运行=8），运行 3 单位到 t=11 完成，切换 1 单位到 t=12。
- t=12 派发 A 剩余 3 单位，运行到 t=15 完成。
- 响应时间：A=0、B=2、C=4；周转时间：A=15、B=5、C=7。
- 切换次数：A→B、B→C、C→A 共 3 次，总切换开销=3。

q=6：
- t=0 A 首次运行=0，运行 6 单位到 t=6 完成，切换 1 单位到 t=7。
- t=2 B 到达，t=4 C 到达，均在就绪队列中等待。
- t=7 派发 B（B 首次运行=7），运行 3 单位到 t=10 完成，切换 1 单位到 t=11。
- t=11 派发 C（C 首次运行=11），运行 3 单位到 t=14 完成。
- 响应时间：A=0、B=5、C=7；周转时间：A=6、B=8、C=10。
- 切换次数：A→B、B→C 共 2 次，总切换开销=2。

约束判断：
- 响应上限“所有任务响应时间不超过 4”：q=1 满足（0,0,0）；q=3 满足（0,2,4）；q=6 不满足（B=5、C=7 均超过 4）。
- 总切换开销“不超过 4”：q=1 为 10，不满足；q=3 为 3，满足；q=6 为 2，满足。
- 因此只有 q=3 同时满足两个约束，是可行方案。

MLFQ 设计（依据片段）：由于 MLFQ 不要求预知运行时间，可用“新任务从高优先级开始、同级轮转、用完 CPU 配额后降级”的机制逼近短任务优先的效果。要照顾响应上限，可把高优先级队列的配额设得较小、同级时间片也设得较小，使新任务和短任务尽快获得首次运行；要照顾长期等待的低优先级任务，可设置周期性提升优先级，把长时间未运行的任务重新提升到高优先级，避免饥饿。按累计使用量计算配额，可防止任务通过每次在时间片结束前主动让出 CPU 来永久保留高优先级。仍需权衡的一个指标是：较小配额与较短时间片会增加切换频率和开销，可能降低吞吐量或使总切换开销上升；提升间隔过短会削弱优先级区分，过长则低优先级任务等待仍可能超过响应上限。

**原解释（保持原样）**

本题按片段给出的自拟模型逐步计算：先记录每个任务首次运行和完成时刻，再算响应时间与周转时间；随后用两个约束筛选 q，最后把 RR 的时间片权衡迁移到 MLFQ 的配额与提升间隔设计上。

资料键：`fixture_cpu_scheduling_zh`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q033 · D1：六需求对照 · 输出前自检

目标：hard；题目级综合分：0.0/100；严格达标：否；完整材料原校验：未通过。

原回复没有可评分的单题或不能解析，按协议计0分；不生成虚构评语。

## Q034 · D1：六需求对照 · 支架与迁移控制

目标：hard；题目级综合分：0.0/100；严格达标：否；完整材料原校验：未通过。

原回复没有可评分的单题或不能解析，按协议计0分；不生成虚构评语。

## Q035 · D1：六需求对照 · 评分要点先行

目标：medium；题目级综合分：95.0/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：medium；置信度：medium。

正确性 4/4 · 资料支持 4/4 · 可作答性 3/4 · 清晰度 3/4。

**评分理由**：按题干原始RC场景，(a)70、(c)最终A50/总150正确，(b)局部RR反事实读100也正确。但(c)在(b)之后未明确回到RC，若沿用RR则后续同一行写入会失败；应明确每问适用的隔离级别。

**原题干**

某表 accounts(name, balance) 初始为 ('A', 100) 和 ('B', 100)，总量不变量为 200。两个会话使用 PostgreSQL 默认的 Read Committed 隔离级别，按以下顺序交错执行（默认普通查询，无加锁读取）：

1) 会话 S1：BEGIN；
2) S1：SELECT balance FROM accounts WHERE name='A'； 得到 100
3) 会话 S2：BEGIN；
4) S2：UPDATE accounts SET balance=balance-30 WHERE name='A'；
5) S2：COMMIT；
6) S1：SELECT balance FROM accounts WHERE name='A'；
7) S1：UPDATE accounts SET balance=balance-20 WHERE name='A'；
8) S1：COMMIT；

请回答：(a) 第 6 步 S1 的查询会看到 A 的余额是多少？请依据 Read Committed 的可见性规则说明理由。(b) 若把 S1 的隔离级别改为 Repeatable Read，第 6 步结果会变成多少？说明与 (a) 的差异来源。(c) 两步结束后 A 的最终余额是多少，总量不变量是否被保持？请结合原子性说明。

**原参考答案（保持原样，可能有错）**

(a) 第 6 步看到 70。Read Committed 下普通 SELECT 看到语句开始前已经提交的数据以及本事务此前的修改；S2 在第 5 步已提交 balance=100-30=70，所以 S1 的第 6 步能读到 70。(b) 改为 Repeatable Read 后第 6 步仍看到 100。Repeatable Read 让普通查询使用本事务第一条非事务控制语句对应的快照，S1 的第一条非事务控制语句是第 2 步的 SELECT，其快照中 A 为 100，后续 S2 的提交不会改变这一视图。(c) A 的最终余额为 70-20=50，B 仍为 100，总量为 150，不等于不变量 200，因此总量不变量未被保持。原子性只保证 S1 的扣款与提交作为单元要么全部生效要么全部回滚，它不阻止两个各自成功提交的事务叠加扣款；本例中 S1 与 S2 都成功提交，所以原子性成立而总量不变量仍被破坏。

**原解释（保持原样）**

本题考查把隔离级别规则应用到具体交错上：先判断每次读取允许看到什么，再讨论事务是否提交以及不变量是否保持。Read Committed 的普通 SELECT 以语句开始前已提交数据为基准，所以能读到 S2 已提交的 70；Repeatable Read 以事务第一条非事务控制语句的快照为基准，所以仍读 100。最终余额由两次已提交的扣款叠加得到 50，说明原子性只约束单个事务单元的提交/回滚，并不自动维护跨事务的业务不变量。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q036 · v2：单需求格式验证 · 三档对照

目标：medium；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：外部提交在首次读取之后，RR第二次100；以题设失败为条件重新执行读取和决策正确。主要是具体快照应用和重试依赖分析。

**原题干**

某应用在 PostgreSQL 的 Repeatable Read 隔离级别下运行事务 T。T 先执行一条普通 SELECT，读到账户 A 的余额为 100；随后另一事务把 A 的余额改为 80 并提交；T 再次执行同样的普通 SELECT。请回答：(1) T 第二次读取看到的值是多少，依据是什么；(2) 如果 T 在第二次读取后打算根据该值写入一笔扣款，而提交时因序列化异常被拒绝，应用应当重试什么、为什么不能只重试最后一条失败语句。请结合资料中的快照与重试语义说明。

**原参考答案（保持原样，可能有错）**

参考答案：(1) T 第二次普通 SELECT 仍看到 100。依据是 Repeatable Read 下普通查询使用本事务第一条非事务控制语句对应的快照，连续查询不会因其他事务的提交而改变这一视图，所以另一事务提交的 80 对 T 不可见。(2) 应用应当重试整个事务，包括重新执行读取 A 余额的查询以及据此选择写入操作的应用逻辑。因为仅重试最后一条失败语句会继续使用基于旧快照（100）做出的决策，而该决策在并发修改后可能已经失效；重试整个事务才能基于新快照重新读取并重新决定写入。重试本身也可能再次失败，不能承诺一次成功。

**原解释（保持原样）**

先按 Repeatable Read 的快照规则判断第二次读取的可见性，再根据资料中“重试整个事务，包括读取数据和据此选择写入操作的应用逻辑”的要求，说明只重试失败语句会沿用失效决策。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q037 · D1：六需求对照 · 三档对照

目标：easy；题目级综合分：100.0/100；严格达标：是；完整材料原校验：通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：直接辨认闭区间非空条件，B正确；半开区间对照解释准确。

**原题干**

According to the supplied notes, for a closed search interval [left, right] over an ascending array with distinct values, which loop condition matches this convention?

A. while left < right
B. while left <= right
C. while left != right
D. while left + 1 < right

**原参考答案（保持原样，可能有错）**

B

**原解释（保持原样）**

The notes state that for a closed interval [left, right], the loop runs while left <= right, and an empty interval means the target is absent. The half-open convention [left, right) instead loops while left < right.

资料键：`fixture_binary_search_en`；核查依据：[sources.json](sources.json)。

## Q038 · D1：六需求对照 · 难度维度约束

目标：medium；题目级综合分：87.5/100；严格达标：否；完整材料原校验：通过。

我的难度判断：medium；置信度：medium。

正确性 3/4 · 资料支持 4/4 · 可作答性 3/4 · 清晰度 3/4。

**评分理由**：在其他语句不修改该账户的通常解释下，第二次100与完整重试正确。但题干写“若干其他语句”未限定范围；资料允许看见自身写入，应补明这些语句不修改A，避免把稳定快照误解为看不见自身修改。

**原题干**

某应用在 PostgreSQL 中使用 Repeatable Read 隔离级别运行事务 T1。T1 的第一条非事务控制语句读取账户余额为 100，之后 T1 执行若干其他语句；在此期间，另一个事务 T2 将同一账户余额改为 150 并成功提交。随后 T1 再次读取该账户余额。请回答：(1) T1 第二次读取会看到什么值？请依据本资料中的快照语义说明理由。(2) 如果数据库返回序列化失败，应用只重试 T1 中最后一条失败的写语句而不是整个事务，可能带来什么后果？请结合“依据读取结果选择写入”的逻辑分析。

**原参考答案（保持原样，可能有错）**

(1) T1 第二次读取仍看到 100。因为 Repeatable Read 让普通查询使用本事务第一条非事务控制语句对应的快照，T2 的提交不会改变 T1 的这一视图（fixture_transactions_zh）。(2) 只重试最后一条失败语句可能继续使用失效的决策：T1 此前读取到的 100 是旧快照，据此选择的写入操作可能已经不再适用；应重试整个事务，包括读取数据和据此选择写入的应用逻辑（fixture_transactions_zh）。

**原解释（保持原样）**

先判断每次读取允许看到什么：Repeatable Read 下快照固定在第一条非事务控制语句，因此 T2 提交后 T1 的第二次读取不变。再分析重试：失败后若只重发最后一条语句，应用逻辑仍基于旧读取结果，决策可能失效，所以必须重做整个事务逻辑。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q039 · D1：六需求对照 · 输出前自检

目标：medium；题目级综合分：80.0/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 2/4 · 资料支持 2/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：T2在T首次读取前已提交，因此新值应进入首次非事务控制语句的快照，两次读取都可见该新值。答案反称T先完成首次读取，颠倒了明确时序；完整重试部分正确。任务本身是可判定的规则应用。

**原题干**

某应用在 PostgreSQL 的 Repeatable Read 隔离级别下运行事务 T，逻辑为：先读取账户 A 的余额，再根据该余额决定向 B 写入的金额，最后提交。并发事务 T2 在 T 开始后、T 第一次读取 A 之前提交了对 A 的修改。请回答：（1）T 中连续两次普通 SELECT 读取 A，会看到 T2 提交后的新值吗？请依据快照语义说明。（2）如果 T 在提交时因序列化异常被拒绝，应用只重试最后一条失败的写入语句是否合适？请说明理由，并指出正确的重试范围。

**原参考答案（保持原样，可能有错）**

（1）不会。Repeatable Read 下普通查询使用本事务第一条非事务控制语句对应的快照，T 在 T2 提交前已开始并完成首次读取，因此后续 SELECT 仍看到该快照中的旧值，不会因 T2 提交而改变视图（fixture_transactions_zh）。（2）不合适。序列化失败时应重试整个事务，包括读取 A 余额并据此选择写入金额的应用逻辑；只重试最后一条写入语句可能继续使用已经失效的决策（fixture_transactions_zh）。正确做法是从事务开始处重新执行读取与决策，再重新提交；重试本身也可能再次失败，不能承诺一次重试必然成功（fixture_transactions_zh）。

**原解释（保持原样）**

本题考查把快照隔离语义和重试范围应用到具体交错情境。第（1）问的关键是区分 Read Committed 与 Repeatable Read：前者后续 SELECT 可看到新提交结果，后者使用本事务第一条非事务控制语句的快照，因此连续读取保持稳定（fixture_transactions_zh）。第（2）问的关键是识别“读取—决策—写入”的依赖链，重试必须覆盖整条链，而不是只覆盖最后一条语句（fixture_transactions_zh）。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q040 · D1：六需求对照 · 难度维度约束

目标：hard；题目级综合分：85.0/100；严格达标：否；完整材料原校验：未通过。

我的难度判断：hard；置信度：high。

正确性 2/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：明确的双性能目标和20%预算需要约束权衡，属于hard。特殊切换期间到达入队规则应遵守；q1在C结束后应先运行已等待的A，原后半段顺序与完成时刻错误，切换次数叙述也自相矛盾。q3数值正确；两候选均超预算的结论仍成立。

**原题干**

某单处理器教学系统采用轮转调度（RR）。任务独立、每个任务只有一个 CPU burst 且无 I/O。切换开销只在从一个任务切换到另一个任务时计费，首次派发免费；切换期间到达的任务按到达时刻进入就绪队列，并排在因时间片用完而回到队尾的任务之前。任务恰在片尾到达时，新到任务先于被抢占任务入队。提前完成的任务不消耗剩余时间片。现有三个任务：A 在时刻 0 到达，服务量 6；B 在时刻 1 到达，服务量 3；C 在时刻 2 到达，服务量 1。切换开销为 1 个时间单位。

系统目标同时包括：平均响应时间尽量小、平均周转时间尽量小，并且切换开销占比不超过 20%。请分别计算时间片 q=1 和 q=3 时的平均响应时间、平均周转时间与切换开销占比，然后论证哪一个时间片更符合上述目标；如果两者都不能同时满足全部目标，请指出冲突并给出一个在资料范围内可调整的策略参数或方案，并说明其依据和局限。

**原参考答案（保持原样，可能有错）**

按题设规则计算（切换只在切换到另一个任务时计费，首次派发免费；切换期间到达任务先入队；片尾到达的新任务先于被抢占任务入队；提前完成不消耗剩余时间片）。

q=1 时：
- 时刻 0：A 首次运行（响应 A=0），运行 1 后剩 5；时刻 1 发生切换，B 在时刻 1 到达并入队，切换期间到达的 B 排在 A 之前。
- 时刻 2：B 首次运行（响应 B=1），运行 1 后剩 2；时刻 3 发生切换，C 在时刻 2 已到达并入队，排在 B 之前。
- 时刻 4：C 首次运行（响应 C=2），服务量 1，运行 1 后完成，完成时刻 5，周转 C=3。
- 之后按队列顺序运行 B、A：B 剩 2 分两次运行，完成时刻 9，周转 B=8；A 剩 5 分五次运行，完成时刻 16，周转 A=16。
- 平均响应时间 = (0+1+2)/3 = 1；平均周转时间 = (16+8+3)/3 = 9；切换次数 = 7 次（A→B、B→C、C→B、B→A、A→B、B→A、A→A 不计，实际为 6 次切换到不同任务，需按题设“切换到另一个任务”计费，故为 6），开销 = 6，总时间 = 16，开销占比 = 6/16 = 37.5%。

q=3 时：
- 时刻 0：A 首次运行（响应 A=0），运行 3 后剩 3；时刻 3 发生切换，B 在时刻 1 到达、C 在时刻 2 到达，均已在就绪队列，按到达顺序 B 先入队，故 B 先运行。
- 时刻 4：B 首次运行（响应 B=3），服务量 3，运行 3 后完成，完成时刻 7，周转 B=6；时刻 7 发生切换。
- 时刻 8：C 首次运行（响应 C=6），服务量 1，运行 1 后完成，完成时刻 9，周转 C=7；时刻 9 发生切换。
- 时刻 10：A 继续运行，剩 3，运行 3 后完成，完成时刻 13，周转 A=13。
- 平均响应时间 = (0+3+6)/3 = 3；平均周转时间 = (13+6+7)/3 = 26/3 ≈ 8.67；切换次数 = 3 次（A→B、B→C、C→A），开销 = 3，总时间 = 13，开销占比 = 3/13 ≈ 23.1%。

比较与论证：q=1 的平均响应时间（1）明显小于 q=3（3），但平均周转时间（9）略大于 q=3（≈8.67），且切换开销占比 37.5% 超过 20% 预算；q=3 的切换开销占比约 23.1%，仍略高于 20%，但比 q=1 更接近预算，且平均周转时间更小。因此两者都不能同时满足“响应最小、周转最小、开销占比≤20%”的全部目标：q=1 在响应上更优但开销超标，q=3 在周转和开销上更优但响应变差且开销仍略超。

可调整方案：在资料范围内，可增大时间片（如取 q=4 或更大）以降低切换频率，从而可能把开销占比压到 20% 以内；但增大时间片会延长其他任务首次运行前的等待，使平均响应时间变差。也可考虑采用多级反馈队列（MLFQ），根据已观察到的执行行为调整优先级，不要求预知准确运行时间，并可通过周期性提升优先级帮助长期等待的低优先级任务；但 MLFQ 的队列层数、片长、配额和提升间隔都是策略参数，需要针对具体目标调参，且一个方案可能满足一个约束却在另一个指标上更差。

**原解释（保持原样）**

本题要求在给定 RR 模型和切换开销规则下，先按时间片计算首次运行时刻与完成时刻，再求平均响应时间、平均周转时间和切换开销占比，最后在多个目标冲突时进行论证。关键不是背定义，而是处理“切换何时计费”“切换期间到达如何入队”“片尾到达谁先入队”等情境约束，并说明时间片选择在响应、周转和开销之间的权衡。

资料键：`fixture_cpu_scheduling_zh`；核查依据：[cpu_checks.json](cpu_checks.json)。

## Q041 · D1：六需求对照 · 输出前自检

目标：medium；题目级综合分：97.5/100；严格达标：是；完整材料原校验：未通过。

我的难度判断：medium；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 3/4。

**评分理由**：RC前后100/70、缺少同一事务内入账会破坏转账不变量、失败后完整重试均正确。是在具体交错上检验显式不变量与规则；(b)“as if complete transfer”措辞不够精确，但答案已区分可见扣款与完整转账。

**原题干**

Consider this educational-fixture schedule. Initial table accounts has row id=1 with balance=100. Session S1 and session S2 each run one explicit transaction, using PostgreSQL Read Committed and ordinary SELECT statements; there are no hidden triggers, constraints, background transactions, or external side effects.

S1: BEGIN; UPDATE accounts SET balance = balance - 30 WHERE id = 1; (S1 has not committed)
S2: BEGIN; SELECT balance FROM accounts WHERE id = 1; (this statement begins now)
S1: COMMIT;
S2: SELECT balance FROM accounts WHERE id = 1; (this statement begins now)
S2: COMMIT;

The application's stated invariant is: a committed transfer must never leave the debit applied without the corresponding credit. Suppose the application, upon receiving a serialization failure from the database, plans to retry only the final failed statement inside the same still-open transaction rather than the whole transaction.

(a) For each of S2's two SELECT statements, state the balance value it is allowed to see and identify the rule that determines that value. (b) Using the invariant, analyze whether S2's second SELECT could observe S1's committed debit as if it were a complete transfer, and explain what additional operation would be needed for the transfer to satisfy the invariant. (c) Evaluate the proposed retry plan against the notes' requirement for retrying serialization failures, and state whether it is acceptable.

**原参考答案（保持原样，可能有错）**

(a) S2's first SELECT must see balance=100: under Read Committed, an ordinary SELECT sees rows committed before that statement began, and S1's UPDATE is still uncommitted, so it is not visible. S2's second SELECT must see balance=70: that statement begins after S1's COMMIT, so Read Committed allows it to observe S1's newly committed change. (b) S2's second SELECT may observe balance=70, but that is only the debit side of S1's transaction. The invariant requires that a committed transfer never leave the debit applied without the corresponding credit, so a credit operation (for example, adding the corresponding amount to the destination row) must also be committed as part of the same unit; observing the debit alone does not satisfy the invariant. (c) The plan is not acceptable: a serialization failure means retrying the complete transaction, including the reads and application decisions that selected the writes. Retrying only the final failed statement can reuse decisions made from a state that is no longer appropriate, and a retry can itself fail, so a considered retry policy is needed rather than assuming one attempt always succeeds.

**原解释（保持原样）**

The item applies the Read Committed visibility rule to a two-statement interleaving and then uses the all-or-nothing invariant to analyze the observed state. The first SELECT is blocked from seeing the uncommitted debit; the second SELECT begins after COMMIT and may see it. The invariant is about committed state changes, not about a single visible row value, so the debit alone is not a complete transfer. The retry evaluation follows the notes: serialization failure requires rerunning the whole transaction, including the reads and decisions, not just the last statement.

资料键：`fixture_transactions_en`；核查依据：[transactions_checks.json](transactions_checks.json)。

## Q042 · v2：单需求格式验证 · 当前基线

目标：medium；题目级综合分：80.0/100；严格达标：否；完整材料原校验：通过。

我的难度判断：easy；置信度：high。

正确性 4/4 · 资料支持 4/4 · 可作答性 4/4 · 清晰度 4/4。

**评分理由**：只问序列化失败后的重试范围及原因，资料已直接给出相同规则；没有具体交错、计算或需选择的条件，属于直接解释，不能仅因使用数据库术语认定为medium。

**原题干**

某应用在 PostgreSQL 中使用 Repeatable Read 隔离级别执行一个事务：先读取账户 A 的余额，再根据该余额决定是否向账户 B 写入一笔转账。若提交时发生序列化失败，应用应如何重试？请说明重试范围，并解释为什么不能只重试最后一条失败语句。

**原参考答案（保持原样，可能有错）**

应重试整个事务，包括重新读取账户 A 的余额以及根据该余额重新决定是否写入转账。不能只重试最后一条失败语句，因为原决策可能基于已经失效的读取结果；只重试写入会继续使用旧决策，无法保证正确性。重试本身也可能再次失败，不能承诺一次重试必然成功。

**原解释（保持原样）**

序列化失败意味着当前事务的执行不能安全提交。重试范围必须覆盖读取数据和据此选择写入操作的应用逻辑，否则可能继续使用失效的决策。

资料键：`fixture_transactions_zh`；核查依据：[transactions_checks.json](transactions_checks.json)。
