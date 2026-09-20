# R7 input audit — query-only AI review

Audit date: 2026-09-20 (Asia/Shanghai). **Final status: accepted for the controlled diagnostic after two required pre-freeze L3 amendments. No remaining mandatory edit.**

## Evidence boundary

This is **AI-assisted auditing, not human annotation or educator validation**. This audit inspected only `benchmarks/rag/query-severity-v1/variants.json` and `canonical-only.json`. Judgments use query wording and the proposed ambiguity descriptions. No `base.json`, textbook, answer span, passage, retrieval output or model rewrite output was consulted. The reviewer did not edit variants; the experiment author applied the two requested changes before freezing.

- Initial variants SHA-256: `12f3f751d415ea2502a881f2487625fd3923cf052aa4eee20f50d4678897f4ac`
- Amended and rechecked variants SHA-256: `b6bbf13f2aea136450d8bf40a66488e56981a12f912412b4c7a31298dcd649d0`
- Canonical-only SHA-256 at final audit: `4680000eeb0d1e70d96656969928b22c9a9af1e6dae38dd386f078b3e3a63cbf`
- Coverage: 120 unique rows; 12 families × 2 languages × 5 levels; 24 rows per level.
- All 24 L0 texts match the supplied canonical-only texts exactly.
- L0–L2: all 72 rows read and accepted for intent continuity.
- L3: all 24 rows read; 22 accepted initially and 2 accepted after mandatory amendments.
- L4: all 24 rows read; each has at least two reasonable readings and is accepted as deliberately ambiguous.

Accepted means suitable for this diagnostic with the limitations below. It does not certify perfect semantic equivalence, real-user naturalness, unique correct answers, or an empirically calibrated severity scale.

## Mandatory findings and completed corrections

| Row ID | Initial finding | Applied correction and recheck |
|---|---|---|
| `avl-factor-en-L3` | Rotations and height balancing alone did not uniquely identify AVL; marking clarification unnecessary was too strong. | Added “the heights on the two sides of every branching point differ by at most one level”; asks for the signed imbalance number without providing a subtraction formula. Re-read and accepted. |
| `avl-factor-zh-L3` | “旋转并保持高度平衡”缺少AVL区别约束。 | 已加“要求每个分叉处两边的高度最多差一层”，仍询问带正负号的数怎样计算，没有给出相减公式。复读后接受。 |

The correction makes the height cue explicit. It restores a defining constraint but is not information-neutral deletion. The audit preserves both input hashes so the initial file is not falsely described as passing without revisions.

## Interpretation limits

1. L3 replaces technical names with mechanism descriptions. A mechanism can increase query length, aid retrieval, or partly imply an answer; this is not a pure removal of information. Do not assume L3 must be harder than L2.
2. BFS L3 gives a **partial answer cue** about the visitation-order part of its two-part canonical question through outward frontier expansion. The supporting data structure is still requested. Report this family separately if interpreting answer-hint effects; do not claim all L3 rows lack answer hints.
3. Stack L3 provides same-end access, from which the removal rule can be inferred, but does not explicitly state LIFO. Binary-log L3 no longer supplies the canonical question's logarithmic conclusion and instead asks for both growth and explanation. AVL L3 now supplies a defining height bound. These are disclosed intervention differences, not conclusions obtained from an answer file.
4. No inspected L3 query directly supplies the complete requested explanation or calculation rule. This query-only observation does not prove absence of overlap with unseen textbook answer wording; that was outside this review.
5. L4 tests uncertainty recognition after constraints are removed. Its original family is one plausible intent, not uniquely correct gold. Do not score recovery of that family as the only successful rewrite or treat its single inherited span as exhaustive relevance.
6. L4 wording is plausible single-message conversational input by AI judgment; no user study validated naturalness or the distribution of ambiguity types.
7. Original question conventions remain: balance-factor sign conventions, the assumed hash deletion scheme, and ordering within a BFS layer are not fully specified. Rewriters should not invent conventions merely to manufacture a unique answer.
8. L0–L4 are construction categories. Monotonic difficulty, equal semantic information, and uniform perturbation strength across families have not been established.

## L0–L2 full sweep

Each table row covers the explicitly named L0, L1 and L2 variants. All 72 query strings were read; this was not sampling.

| Family / language | L0 | L1 | L2 | Finding |
|---|---|---|---|---|
| `binary-order-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `binary-order-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `binary-log-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `binary-log-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `hash-delete-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `hash-delete-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `hash-chain-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `hash-chain-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `avl-factor-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `avl-factor-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `stack-order-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `stack-order-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `bfs-queue-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `bfs-queue-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `dfs-backtrack-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `dfs-backtrack-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `quick-partition-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `quick-partition-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `quick-bad-pivot-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `quick-bad-pivot-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `insertion-near-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `insertion-near-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `merge-selection-en` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |
| `merge-selection-zh` | Exact canonical | Pass | Pass | Target information and defining named concepts/constraints retained; no new answer conclusion identified. |

## L3 individual judgments

| Row ID | Final judgment | Query-only finding |
|---|---|---|
| `binary-order-en-L3` | Pass | 保留检查中点、排除一边的机制及开始前排列条件的目标；未直接写出有序性条件。 |
| `binary-order-zh-L3` | Pass | 保留检查中点、排除一边的机制及开始前排列条件的目标；未直接写出有序性条件。 |
| `binary-log-en-L3` | Pass with scope note | 保留每次排除一半与规模增大的条件；L3问增长速度并解释，而原问题已给出 logarithmic/对数。因此知识需求相近，但已知信息量并不完全相同。 |
| `binary-log-zh-L3` | Pass with scope note | 保留每次排除一半与规模增大的条件；L3问增长速度并解释，而原问题已给出 logarithmic/对数。因此知识需求相近，但已知信息量并不完全相同。 |
| `hash-delete-en-L3` | Pass | 键映射位置、逐格向后尝试和删除标记保留；未说明标记的作用。原问题must/需要的前提仍受所假定删除方案限制。 |
| `hash-delete-zh-L3` | Pass | 键映射位置、逐格向后尝试和删除标记保留；未说明标记的作用。原问题must/需要的前提仍受所假定删除方案限制。 |
| `hash-chain-en-L3` | Pass | 键映射同一位置、链接成串及单串过长均保留；未给出改进结构或复杂度。改善方案本来可能不唯一。 |
| `hash-chain-zh-L3` | Pass | 键映射同一位置、链接成串及单串过长均保留；未给出改进结构或复杂度。改善方案本来可能不唯一。 |
| `avl-factor-en-L3` | Pass after required amendment | 已补充每个分叉处两边高度最多差一层，足以识别AVL约束；未给出平衡因子的减法公式。高度和正负号仍是额外机制线索。 |
| `avl-factor-zh-L3` | Pass after required amendment | 已补充每个分叉处两边高度最多差一层，足以识别AVL约束；未给出平衡因子的减法公式。高度和正负号仍是额外机制线索。 |
| `stack-order-en-L3` | Pass with mechanism cue | 同一端进出足以识别栈语义；没有直接写出LIFO/后进先出，但该机制能推导所问顺序。属于机制释义。 |
| `stack-order-zh-L3` | Pass with mechanism cue | 同一端进出足以识别栈语义；没有直接写出LIFO/后进先出，但该机制能推导所问顺序。属于机制释义。 |
| `bfs-queue-en-L3` | Pass with partial answer cue | 当前front向外铺开、不沿单路深入可指向BFS；没有给出queue/FIFO，但已经提示复合问题的访问顺序部分。须保留这一诊断标签。 |
| `bfs-queue-zh-L3` | Pass with partial answer cue | 当前front向外铺开、不沿单路深入可指向BFS；没有给出queue/FIFO，但已经提示复合问题的访问顺序部分。须保留这一诊断标签。 |
| `dfs-backtrack-en-L3` | Pass | 优先沿单路线深入的机制保留；回溯触发条件和之后继续探索规则仍未给出。 |
| `dfs-backtrack-zh-L3` | Pass | 优先沿单路线深入的机制保留；回溯触发条件和之后继续探索规则仍未给出。 |
| `quick-partition-en-L3` | Pass | 选择参照、按相对关系移动并递归处理各段保留；没有给出分割后各部分满足的性质。 |
| `quick-partition-zh-L3` | Pass | 选择参照、按相对关系移动并递归处理各段保留；没有给出分割后各部分满足的性质。 |
| `quick-bad-pivot-en-L3` | Pass | 参照分段并递归、初始从大到小、每段取首元素三项关键约束保留；未给出性能退化机制或复杂度。 |
| `quick-bad-pivot-zh-L3` | Pass | 参照分段并递归、初始从大到小、每段取首元素三项关键约束保留；未给出性能退化机制或复杂度。 |
| `insertion-near-en-L3` | Pass | 逐项放入已排好部分与整体接近有序保留；未给出减少哪些操作的解释。 |
| `insertion-near-zh-L3` | Pass | 逐项放入已排好部分与整体接近有序保留；未给出减少哪些操作的解释。 |
| `merge-selection-en-L3` | Pass | 两个同方向有序序列及结果仍有序的目标保留；没有给出比较候选并选下一项的规则。 |
| `merge-selection-zh-L3` | Pass | 两个同方向有序序列及结果仍有序的目标保留；没有给出比较候选并选下一项的规则。 |

## L4 individual ambiguity judgments

These rows are accepted as ambiguous inputs, not as guaranteed paraphrases of the canonical family. Each has at least two plausible interpretations.

| Row ID | Plausible interpretations | Why clarification is justified |
|---|---|---|
| `binary-order-en-L4` | 二分查找排序前提；线性扫描是否需要排序。 | 缺少搜索机制，预处理是否必要并不唯一。 |
| `binary-order-zh-L4` | 二分查找排序前提；线性扫描是否需要排序。 | 缺少搜索机制，预处理是否必要并不唯一。 |
| `binary-log-en-L4` | 区间折半查找；树搜索剪枝。 | cutting things down/范围变小未说明是折半、剪枝还是筛选。 |
| `binary-log-zh-L4` | 区间折半查找；树搜索剪枝。 | cutting things down/范围变小未说明是折半、剪枝还是筛选。 |
| `hash-delete-en-L4` | 开放寻址删除标记；数据库软删除或同步删除标记。 | 表和记号是泛称，缺少位置探测条件。 |
| `hash-delete-zh-L4` | 开放寻址删除标记；数据库软删除或同步删除标记。 | 表和记号是泛称，缺少位置探测条件。 |
| `hash-chain-en-L4` | 哈希桶冲突链过长；普通无序容器中记录过多。 | 缺少键映射、链式存储线索，改进方案会随解释变化。 |
| `hash-chain-zh-L4` | 哈希桶冲突链过长；普通无序容器中记录过多。 | 缺少键映射、链式存储线索，改进方案会随解释变化。 |
| `avl-factor-en-L4` | 按子树高度衡量失衡；按子树节点数衡量失衡。 | 没有指定树类型或衡量维度，其他平衡不变量也合理。 |
| `avl-factor-zh-L4` | 按子树高度衡量失衡；按子树节点数衡量失衡。 | 没有指定树类型或衡量维度，其他平衡不变量也合理。 |
| `stack-order-en-L4` | 栈；队列；优先队列。 | 容器访问规则未知，直接选一种会猜测意图。 |
| `stack-order-zh-L4` | 栈；队列；优先队列。 | 容器访问规则未知，直接选一种会猜测意图。 |
| `bfs-queue-en-L4` | 广度优先；深度优先；按优先级搜索。 | 没有扩展顺序或搜索目标，等待容器选择不唯一。 |
| `bfs-queue-zh-L4` | 广度优先；深度优先；按优先级搜索。 | 没有扩展顺序或搜索目标，等待容器选择不唯一。 |
| `dfs-backtrack-en-L4` | DFS遍历回溯；路径搜索遇死路后退。 | 缺少遍历策略、路径或状态条件；约束搜索也是可能解释。 |
| `dfs-backtrack-zh-L4` | DFS遍历回溯；路径搜索遇死路后退。 | 缺少遍历策略、路径或状态条件；约束搜索也是可能解释。 |
| `quick-partition-en-L4` | 围绕pivot划分；归并分治前拆分子列表。 | 未说明pivot或比较关系；挪动可能泛指预处理。第二种读法较弱，但仍需问清排序算法。 |
| `quick-partition-zh-L4` | 围绕pivot划分；归并分治前拆分子列表。 | 未说明pivot或比较关系；挪动可能泛指预处理。第二种读法较弱，但仍需问清排序算法。 |
| `quick-bad-pivot-en-L4` | 快排每段取首元素；插入排序从待处理前端取下一项。 | 反序与取前项不足以唯一确定排序机制。 |
| `quick-bad-pivot-zh-L4` | 快排每段取首元素；插入排序从待处理前端取下一项。 | 反序与取前项不足以唯一确定排序机制。 |
| `insertion-near-en-L4` | 插入排序；利用已有有序段的自适应归并。 | 只保留接近有序的条件，未指定算法；提前终止的冒泡变体也可能。 |
| `insertion-near-zh-L4` | 插入排序；利用已有有序段的自适应归并。 | 只保留接近有序的条件，未指定算法；提前终止的冒泡变体也可能。 |
| `merge-selection-en-L4` | 保持有序合并；来源顺序拼接；交替交织。 | 未说明输入有序及输出排序目标，合理规则不止一种。 |
| `merge-selection-zh-L4` | 保持有序合并；来源顺序拼接；交替交织。 | 未说明输入有序及输出排序目标，合理规则不止一种。 |

## Freeze decision

The amended file with the hash above may be frozen. Keep this audit and both recorded hashes with the run. Later changes motivated by results must create a new dataset version rather than silently repairing the evaluated inputs.
