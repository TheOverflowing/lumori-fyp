# R7 rewrite semantic audit — query-only AI assessment

Date: 2026-09-20 (Asia/Shanghai). Scope: all **240** responses, including all normalization levels and all L3/L4 responses from both policies.

## Evidence and limits

This is **AI-assisted qualitative auditing, not human annotation, instructor evaluation, or an independent factuality benchmark**. The sole input read for this output audit was `rewrite-audit-inputs.json` from the R7 run. Decisions compare its original query, response query, clarification decision, explanation and validation status. No textbook, answer span, relevance label, ranking or metric was consulted. Saved ambiguity-interpretation lists were not read for this audit.

- Run: `docs/rag/r7-experiments/20260919T161914951306Z`
- Audit input SHA-256: `4205fa7d19e3a1377ce24f8b34324fec3884a8776475f9bc24299ea452ca2ba1`
- Row artifact: `rewrite-semantic-audit.json`, a list of 240 `{key, disposition, notes}` objects.
- Original outputs, labels, prompt, candidate lists and scores were not modified. These are post hoc diagnostic judgments, not exclusions or replacement grades.
- Counts describe these outputs under this rubric; they are not population error rates or human agreement statistics.

## Dispositions

- `faithful`: active query preserves the information need and material constraints without inserting a requested answer; supported terminology normalization is allowed only in the normalize condition.
- `clarification`: a reasonable clarification decision. Under the frozen contract its query field is ignored; even a guessed term in that unused field is not counted as an executed retrieval query.
- `possible_scope_shift`: omitted/narrowed constraints, an unsupported specific interpretation, or strengthened certainty. This label includes plausible risks rather than proven factual errors.
- `answer_injection`: an active query adds a candidate answer/rule/complexity conclusion that the user was asking to obtain. Partial hints and answer hypotheses phrased as questions count; the label does not require a complete prose answer.
- `other_warning`: a policy-separation violation or missed clarification without a newly specific invented intent.
- `invalid`: frozen program validation rejected the response. This is distinct from semantic unfaithfulness or HTTP failure.

Where problems overlap, invalid status takes precedence, then answer injection, scope shift and other warnings. Reason text is inspected to explain an inference but is not itself treated as a retrieval query.

## Counts

| Disposition | Conservative | Normalize | Total |
|---|---:|---:|---:|
| faithful | 95 | 81 | 176 |
| clarification | 21 | 17 | 38 |
| possible_scope_shift | 0 | 11 | 11 |
| answer_injection | 0 | 9 | 9 |
| other_warning | 4 | 0 | 4 |
| invalid | 0 | 2 | 2 |

## Main findings

1. Terminology normalization sometimes answers the question while rewriting it. Five stack variants explicitly add LIFO/后进先出, although the original input asks for removal order. Two insertion variants add a near-linear complexity conclusion. One vague search query gains both binary-search identity and logarithmic complexity. One ordering query gains sorted as a proposed answer in a yes/no formulation. These additions may change retrieval behavior; they must not automatically be interpreted as faithful terminology recovery.
2. Several ambiguous L4 inputs are confidently narrowed to a specific algorithm or data structure. Examples include a generic crowded location becoming a hash bucket, and an unspecified tree balance number becoming the binary-tree balance factor.
3. The conservative output for `insertion-near-en-L3` introduces the absent algorithm name insertion sort, breaching its own policy. This matters for interpreting the contrast between the two arms even though the inferred algorithm fits the described mechanism.
4. The two invalid normalization outputs expand DFS into its full English/Chinese name without preserving the literal acronym. Their visible wording is semantically close to the input; the rejection demonstrates the strict literal-preservation rule, not a demonstrated hallucination. They remain invalid/fallback records in the frozen evaluation.
5. Some clarification responses contain a guessed algorithm or answer-like word in their ignored query field. The executed action is clarification, so these are kept separate from active-query answer injection. Future integrations must continue honoring the clarification flag.

## Flagged rows

The machine-readable artifact contains every row. This table lists non-faithful, non-clarification cases so the concrete concerns can be inspected without confusing them with retrieval scores.

| Key | Disposition | Query-only judgment |
|---|---|---|
| `avl-factor-en-L4:normalize` | possible_scope_shift | 原句只说树上的平衡数；query指定binary tree balance factor，reason错误断言唯一对应。输入未排除其他树类型或平衡度量。 |
| `bfs-queue-en-L4:conservative` | other_warning | 基本保留了原句的模糊范围，没有明显猜出具体算法；但needs_clarification=false，把缺少遍历策略/表类型/排序机制的多义输入当作足够明确，漏掉应有澄清。 |
| `bfs-queue-zh-L2:normalize` | possible_scope_shift | 原句问整个等待访问集合；query改为待访问“相邻”顶点，可能被读作当前节点的邻居而非整个frontier。属较弱范围风险，不是已确认错误答案。 |
| `binary-log-en-L4:normalize` | answer_injection | 原句只说搜索范围逐步缩小；query自行指定binary search并加入logarithmic time complexity。reason还把输入误述成repeatedly halving；既猜测意图又加入复杂度答案。 |
| `binary-order-en-L2:normalize` | answer_injection | 原句开放询问排列必须遵守的规则；query新增“must the elements be sorted”，把候选答案sorted置入检索词。属于部分答案提示，即使保留疑问形式也不只是同义改写。 |
| `dfs-backtrack-en-L1:normalize` | invalid | 程序以r7_rewrite_missing_literal拒绝：输出用depth-first search/深度优先搜索替换DFS而未保留字面缩写。可见文本语义基本忠实，属于预设字面保留规则触发，不是HTTP失败，也不能据此称为幻觉；实际按runner回退，未修复输出。 |
| `dfs-backtrack-zh-L1:normalize` | invalid | 程序以r7_rewrite_missing_literal拒绝：输出用depth-first search/深度优先搜索替换DFS而未保留字面缩写。可见文本语义基本忠实，属于预设字面保留规则触发，不是HTTP失败，也不能据此称为幻觉；实际按runner回退，未修复输出。 |
| `hash-chain-en-L4:normalize` | possible_scope_shift | 原句只说许多记录挤在一处、查询慢；query猜测hash table bucket collisions，缩窄到未由输入确定的数据结构。 |
| `hash-chain-zh-L4:normalize` | possible_scope_shift | 原句没有键映射或哈希线索；query猜测哈希冲突且改成泛问冲突解决方法，reason把未出现的映射机制当作已知。 |
| `hash-delete-en-L4:conservative` | other_warning | 基本保留了原句的模糊范围，没有明显猜出具体算法；但needs_clarification=false，把缺少遍历策略/表类型/排序机制的多义输入当作足够明确，漏掉应有澄清。 |
| `hash-delete-en-L4:normalize` | possible_scope_shift | 原句只有table与删除标记；query指定hash table tombstone，排除了同样合理的其他表删除/软删除场景。 |
| `hash-delete-zh-L2:normalize` | possible_scope_shift | 输入明确逐格向后探测；query只保留开放寻址，遗漏线性探测区别条件。删除问题仍相关，但检索范围被扩大。 |
| `hash-delete-zh-L3:normalize` | possible_scope_shift | 输入明确逐格向后探测；query只保留开放寻址，遗漏线性探测区别条件。删除问题仍相关，但检索范围被扩大。 |
| `insertion-near-en-L3:conservative` | other_warning | 意图大致保持，但query主动引入输入没有的insertion sort算法名称，违反conservative禁止新增技术名称的策略。不是答案注入，却意味着两种改写条件没有严格分离。 |
| `insertion-near-zh-L2:normalize` | answer_injection | 原句只问基本有序时为何工作量少；query新增“时间复杂度接近线性”，引入未由输入给出的复杂度结论。 |
| `insertion-near-zh-L4:normalize` | answer_injection | 原句未说明排序方法；query自行指定插入排序并加入“时间复杂度接近线性”。同时存在猜测算法和新增答案结论；按答案注入优先分类。 |
| `quick-bad-pivot-en-L1:normalize` | possible_scope_shift | 保留首元素pivot与降序输入，但将“can become slow/perform badly”强化为“does ... worst-case”。新增确定性与最坏情况判断，未直接给出退化机制，故与直接答案规则注入分开。 |
| `quick-bad-pivot-en-L2:normalize` | possible_scope_shift | 保留首元素pivot与降序输入，但将“can become slow/perform badly”强化为“does ... worst-case”。新增确定性与最坏情况判断，未直接给出退化机制，故与直接答案规则注入分开。 |
| `quick-bad-pivot-en-L3:normalize` | possible_scope_shift | 保留首元素pivot与降序输入，但将“can become slow/perform badly”强化为“does ... worst-case”。新增确定性与最坏情况判断，未直接给出退化机制，故与直接答案规则注入分开。 |
| `quick-bad-pivot-en-L4:conservative` | other_warning | 基本保留了原句的模糊范围，没有明显猜出具体算法；但needs_clarification=false，把缺少遍历策略/表类型/排序机制的多义输入当作足够明确，漏掉应有澄清。 |
| `quick-partition-zh-L4:normalize` | possible_scope_shift | 原句未确定算法或操作机制；query指定递归分区前partition，reason的唯一识别断言超出输入支持。 |
| `stack-order-en-L1:normalize` | answer_injection | 检索query新增LIFO，直接提供用户正在询问的出入顺序规则；恢复stack名称可以，但补上该答案不属于只规范术语。 |
| `stack-order-en-L2:normalize` | answer_injection | 检索query新增LIFO，直接提供用户正在询问的出入顺序规则；恢复stack名称可以，但补上该答案不属于只规范术语。 |
| `stack-order-en-L3:normalize` | answer_injection | 检索query新增LIFO，直接提供用户正在询问的出入顺序规则；恢复stack名称可以，但补上该答案不属于只规范术语。 |
| `stack-order-zh-L2:normalize` | answer_injection | 检索query新增“后进先出”，直接写入所问顺序规则。属于答案提示注入，不是仅把容器机制命名为栈。 |
| `stack-order-zh-L3:normalize` | answer_injection | 检索query新增“后进先出”，直接写入所问顺序规则。属于答案提示注入，不是仅把容器机制命名为栈。 |

## Interpretation and follow-up

Use these labels to describe mechanisms and inspect paired examples after the frozen primary analysis. Do not silently remove flagged rows, replace their rewrite text, retry failed outputs, or present a filtered subset as a prespecified main result. Any prompt revision needs a newly versioned experiment. Independent human review and agreement measurement would still be needed before treating this audit as validated semantic labels.
