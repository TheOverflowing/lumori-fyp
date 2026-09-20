"""Build frozen, AI-curated question-authoring tasks; this creates no gold labels.

Run from the repository root: .venv/bin/python benchmarks/difficulty/build_cases.py
The course-source manifest supplies pinned URLs and license attribution. Notes
below are newly written study fixtures, not quotations or human translations.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "benchmarks/rag/course_sources/manifest.json"

TOPICS = [
    {
        "id": "binary_search", "split": "dev", "pilot_level": "easy",
        "course_file": "chapter_searching/binary_search.md",
        "name": {"zh": "二分查找：区间约定、边界更新与适用条件", "en": "Binary search: interval conventions, boundary updates, and applicability"},
        "notes": {
            "en": """Binary search uses the ordering of a sequence to discard positions that cannot hold the target. Consider an ascending array with distinct values and constant-time indexed access. A closed search interval [left, right] contains every position still eligible to hold the target. Initially left is zero and right is n minus one. At each iteration, choose mid = left + floor((right - left) / 2). Equality ends the search. If the middle value is smaller than the target, all positions through mid are too small, so set left = mid + 1. If it is larger, positions from mid onward are too large, so set right = mid - 1. The loop runs while left <= right; an empty interval means the target is absent.

The expression for mid avoids adding two potentially large indices. The interval convention determines the termination condition. A half-open interval [left, right) instead starts with right = n, contains no positions when left = right, and loops while left < right. For an exact-match implementation, equality still returns immediately. A smaller middle value sets left = mid + 1, while a larger middle value sets right = mid. Mixing the closed-interval test with the half-open right boundary can inspect a position outside the array. Retaining mid after already rejecting it can prevent progress on a one-element interval.

Each unsuccessful comparison removes approximately half the remaining positions. The worst-case number of iterations grows logarithmically with n, and the iterative implementation stores only a constant number of indices. Empty arrays require no element access. A single-element array may either succeed or become empty after one comparison. The distinct-value assumption avoids a separate requirement to return the first or last occurrence; exact-match search on an array with duplicates may return any matching occurrence unless the specification adds another condition.

The algorithm depends on an ordered search space and cheap access to its middle. Sorting an unsorted array solely for one lookup adds preprocessing work; a scan can be the better choice for that workload. A sorted array serving many lookups can amortize preprocessing, whereas frequent insertions may require movement of array entries. Knowing the midpoint index does not make access to that position constant-time in a singly linked list. A logarithmic number of comparisons is therefore not by itself a claim of logarithmic total running time for every representation.

For exercises in this fixture, indices are zero-based, integer division rounds downward, and -1 denotes an absent target. If an exercise gives pseudocode, its stated interval convention takes precedence. Arrays, targets, and any workload counts introduced by a question must be shown explicitly; they are hypothetical exercise data, not measurements from the source textbook. Reasoning may track the interval after a comparison, explain why discarded positions are impossible, or compare workloads under the supplied cost assumptions. No implementation-language overflow behavior is required beyond the midpoint observation above. The same notes support direct concept questions and constrained reasoning without introducing a different body of reference material for each requested difficulty.""",
            "zh": """二分查找利用有序性排除不可能包含目标的位置。本资料假定数组按升序排列、元素互异，并且按下标访问需要常数时间。闭区间 [left, right] 保存所有仍可能包含目标的位置，初始 left=0、right=n-1。每轮取 mid=left+向下取整((right-left)/2)。若中间值等于目标，返回 mid；若中间值小于目标，将 left 更新为 mid+1；若中间值大于目标，将 right 更新为 mid-1。循环条件是 left<=right，区间为空时返回 -1。

中点公式避免先相加两个可能很大的下标。区间约定决定初始化、循环条件与更新方式：左闭右开区间 [left,right) 从 right=n 开始，left=right 时为空，循环条件是 left<right。精确匹配时，相等仍立即返回；中间值较小则 left=mid+1，较大则 right=mid。不能混用闭区间的循环条件和开区间的右边界，否则可能访问数组之外；也不能在已经排除 mid 后仍保留它而导致区间不缩小。

每轮未命中的比较排除约一半位置，因此最坏循环次数为对数级，迭代版本只使用常数额外空间。空数组不应访问元素；单元素数组在一次比较后即可命中或成为空区间。本资料采用互异元素，避免额外引入查找第一个或最后一个相等元素的要求；有重复元素时，普通精确查找只保证返回某个匹配位置。

二分查找依赖有序数据与便宜的中点访问。为了只查询一次而先排序，会增加预处理工作，线性扫描可能更合适；查询很多次时，可以分摊排序成本。频繁插入又可能要求移动数组元素。链表即使知道中点下标，也不能据此常数时间访问中点，所以对数次比较不等于所有存储形式下都有对数总时间。

本练习统一采用从零开始的下标、向下取整的整数除法和未找到时的 -1；若题目提供伪代码，以明确写出的区间约定为准。出题时须完整列出假设数组、目标与相关工作量，不把自拟数值称为教材实测数据。可讨论区间追踪、被排除位置为何不可能命中，以及给定成本下的适用场景；不要求资料之外的语言细节。同一份资料供所有难度使用。""",
        },
    },
    {
        "id": "quick_sort", "split": "dev", "pilot_level": None,
        "course_file": "chapter_sorting/quick_sort.md",
        "name": {"zh": "快速排序：划分、递归结构与退化条件", "en": "Quicksort: partitioning, recursion structure, and degeneration"},
        "notes": {
            "en": """Quicksort organizes sorting around a pivot and a partition operation. In a two-way partition, elements smaller than the pivot are placed toward one side and larger elements toward the other, after which the remaining subarrays are sorted recursively. A particular implementation must specify how equal values are handled and whether the pivot ends in its final position. The term partition alone does not define the exact sequence of swaps. An exercise asking for a trace therefore needs to supply the pivot rule and partition pseudocode instead of assuming all valid implementations make identical intermediate arrays.

A partition scans a subarray and performs work proportional to its length. When partitions repeatedly split the elements into similarly sized groups, the recursion has logarithmic depth, with linear total partition work across a level. This gives O(n log n) time. When one side repeatedly contains almost every element, the work instead resembles n + (n - 1) + ... + 1 and becomes O(n squared). Choosing the first element as pivot on already sorted distinct input is one way to obtain highly unbalanced splits in an implementation that puts that pivot in its final position.

Changing the pivot rule can reduce exposure to patterned inputs. A randomly selected pivot makes the partition sequence depend on random choices rather than only on the original arrangement, but it does not make a balanced split certain on every call. Median-of-three selection uses a small sample to seek a more representative pivot; it also provides no universal worst-case guarantee by itself. A claim about expected running time and a claim about a worst-case guarantee answer different questions. Neither should be inferred merely from the word randomized or improved.

Recursive calls consume stack space even when partitioning rearranges the original array. Balanced recursion usually has logarithmic depth, while a naive implementation with highly unbalanced partitions can have linear depth. An implementation can recursively process the smaller partition and continue with the larger partition in a loop. Under this strategy, successive nested recursive calls reduce the subproblem size by at least half, bounding the call stack depth even when total partition work remains quadratic. Reducing stack usage does not by itself improve the time complexity of an unlucky pivot sequence.

Quicksort implementations based on distant swaps are generally unstable: two equal-key records may change relative order. Stability is a separate requirement from ascending output and should be stated when records contain associated data. Equal-key handling also matters when many values repeat; a concrete trace or performance claim must be tied to the stated partition scheme.

In this fixture, comparison counts, asymptotic work, stability, and extra stack storage are separate properties. A question may introduce a small array or a specified sequence of split sizes, but must state all assumptions needed to analyze it. If it asks a learner to compare two designs, it must identify the workload and the resource being constrained. There is no requirement to reproduce an external code listing or know a programming library's hidden pivot strategy. Hypothetical arrays and design constraints are exercise inputs, not experimental results or human-annotated examples.""",
            "zh": """快速排序先选择基准值并进行划分，再递归处理子数组。双路划分将较小与较大元素分别放到两侧，但相等元素如何处理、基准最终是否处于正确位置，必须由具体实现规定。仅写“进行一次划分”不足以唯一决定交换顺序，因此追踪题应给出基准规则与伪代码。

一次划分的工作量与子数组长度成正比。如果反复划分成大小相近的两组，递归深度为对数级，每一层合计处理线性数量的元素，总时间为 O(n log n)。如果每次一侧几乎包含全部剩余元素，工作量成为 n+(n-1)+…+1，退化为 O(n²)。对于把基准放到最终位置的常见实现，在已排序且互异的数组上总选首元素，就可能出现这样的失衡。

随机选择基准能降低对特定输入排列的依赖，却不能保证每次都均匀划分。三数取中通过少量样本寻找较合适的基准，本身也不是最坏时间保证。“期望时间”和“最坏情况下保证”是不同结论，不能看到随机化就认定每次运行都达到同一性能。

即便在原数组中完成划分，递归调用仍使用栈空间。较均衡时栈深度通常为 O(log n)，朴素实现在连续失衡时可能达到 O(n)。一种改进是只递归较小的子数组，再用循环处理较大的子数组；连续嵌套的递归问题大小至少减半，因此可限制栈深度，但坏基准造成的划分总工作量仍可能为二次级。节省栈空间不等于修复最坏时间。

通过远距离交换完成划分的快速排序通常不稳定，同键记录的原相对顺序可能改变。稳定性、排序正确性、比较次数与额外空间是不同性质。包含大量重复值时，相等键处理规则也影响推导，不能脱离具体划分方式计算轨迹。

本资料允许题目自拟小数组、明确的划分规模序列或资源约束，但须写清输入、实现假设与比较目标。不要要求学生猜某个语言库未说明的基准策略，也不要把自拟场景当成实测性能。直接概念、应用轨迹与设计权衡都使用同一参考资料。""",
        },
    },
    {
        "id": "graph_traversal", "split": "dev", "pilot_level": None,
        "course_file": "chapter_graph/graph_traversal.md",
        "name": {"zh": "图遍历：BFS、DFS、访问标记与路径保证", "en": "Graph traversal: BFS, DFS, visited state, and path guarantees"},
        "notes": {
            "en": """A graph consists of vertices and edges. Traversing from a start vertex discovers vertices reachable from that start. In an undirected disconnected graph, one traversal does not necessarily visit every component. A complete traversal can iterate over all vertices and start a new search whenever an unvisited vertex is encountered. In a directed graph, following an edge means following its stated direction; reachability need not be symmetric. Exercises must identify whether the graph is directed and specify the start vertex when asking for a traversal.

Breadth-first search uses a first-in, first-out queue. Mark the start as discovered and enqueue it. Repeatedly remove the front vertex and examine its neighbors; an undiscovered neighbor is marked when it is enqueued. This convention prevents multiple queued copies of a vertex reached through different edges. BFS discovers vertices in layers measured by the number of edges from the start. Recording a predecessor when a vertex is first discovered permits reconstruction of one path by following predecessor links backward.

For an unweighted graph, or one where every edge has the same positive cost, the first BFS discovery of a vertex gives a path with the minimum number of edges. The rule does not in general minimize total cost when edges have different weights. A traversal can still enumerate reachable vertices in a weighted graph, but its order alone does not establish a minimum-cost route. The distinction between number of edges and sum of edge weights is necessary when interpreting the word shortest.

Depth-first search follows one branch as far as possible before returning to unexplored alternatives. It may be implemented with recursive calls or an explicit stack. A visited set prevents revisiting vertices indefinitely in a cycle. DFS finds reachable vertices and can record a predecessor tree, but an arbitrary first DFS path need not use the fewest edges. A recursive call returns after its reachable unexplored descendants have been processed, which differs from removing a vertex from the front of a BFS queue.

When the graph is stored in adjacency lists, each vertex and each stored adjacency entry is examined a bounded number of times, giving O(V + E) work for a complete traversal. In an undirected adjacency list, an edge normally appears in both endpoint lists; this does not change the asymptotic bound. An adjacency matrix may require scanning V entries to find the neighbors of each processed vertex, resulting in O(V squared) work for a full traversal. Queue, stack, predecessor, and visited storage are additional resources; they should not be confused with the graph's own representation.

Several valid orders may exist when a vertex has multiple neighbors. For a unique trace, a question must state a neighbor order, such as ascending vertex labels, and distinguish discovery from completion. Hypothetical graphs must list every relevant edge and edge direction. Unless weights are explicitly introduced, edges are unweighted. Path requests must distinguish one valid path, one minimum-edge path, and all possible paths, because these are different tasks. No unseen diagram or external visualization is required to solve a question grounded in this fixture.""",
            "zh": """图由顶点与边组成。从起点遍历，只保证发现从该点可达的顶点；无向图若不连通，一次搜索不一定覆盖全部分量。完整遍历可依次检查所有顶点，对仍未访问的顶点重新发起搜索。有向图必须沿边的方向移动，可达性不一定对称，因此题目要说明图的类型与起点。

广度优先搜索 BFS 使用先进先出的队列：标记起点并入队，反复移除队首并检查邻居，将未发现的邻居在入队时标记。入队即标记可防止同一顶点通过不同边重复进入队列。BFS 按距起点的边数逐层发现顶点；首次发现时保存前驱，可以沿前驱反向恢复一条路径。

在无权图，或所有边具有相同正代价时，BFS 首次发现顶点得到最少边数路径。不同边权的情况下，最少边数并不保证总代价最小。BFS 仍可遍历带权图的可达顶点，但遍历顺序本身不能证明找到最小权重路径。题目中的“最短”应明确指边数还是权重之和。

深度优先搜索 DFS 尽可能沿一条分支深入，再回到尚未探索的分支，可使用递归或显式栈。访问标记防止在环中反复访问。DFS 能发现可达顶点并形成前驱树，但首次找到的路径不一定边数最少。递归返回发生在后继分支处理结束之后，与 BFS 取出队首的时机不同。

邻接表中，完整遍历对各顶点和邻接项进行有界次数处理，时间为 O(V+E)。无向边通常在两个端点的邻接表各出现一次，但不改变渐进复杂度。邻接矩阵可能为每个顶点扫描 V 个位置，完整遍历为 O(V²)。访问集合、前驱、队列或递归栈属于额外空间，不应与图本身的存储混淆。

当邻居不止一个时，可存在多种正确顺序。若要求唯一轨迹，题目须指定邻居顺序，例如按顶点标签升序，并区分发现与完成时刻。自拟图要列出所有相关边及方向；未声明边权时采用无权图。寻找任意路径、最少边数路径和所有路径是不同任务，不得依赖未提供的配图或外部动态演示。""",
        },
    },
    {
        "id": "stack", "split": "dev", "pilot_level": None,
        "course_file": "chapter_stack_and_queue/stack.md",
        "name": {"zh": "栈：后进先出、不变量与受限操作序列", "en": "Stacks: last-in-first-out behavior, invariants, and constrained operation sequences"},
        "notes": {
            "en": """A stack is an abstract data type whose insertion and removal operations act at one end, called the top. Push adds an element at the top, pop removes and returns the top element, and peek reads the top without removing it. The most recently pushed element still present is therefore the next element removed. This last-in-first-out rule defines behavior independently of whether storage uses an array or linked nodes. A queue has a different removal rule and cannot be substituted without checking the required order of operations.

An array implementation can keep a size counter and store occupied elements in positions zero through size minus one. For a nonempty stack, the top element is at size minus one. Push writes at position size before increasing size; pop decreases size before returning the element at the new top boundary. Equivalent implementations may store a top index instead, but the two meanings of the counter must not be mixed. With fixed capacity C, size must remain between zero and C inclusive. A push when size equals C is an overflow attempt; a pop or peek when size is zero is an underflow attempt.

A linked stack can use the head node as the top. Adding or removing that head requires updating a constant number of links. Both representations support constant-time basic operations under their stated storage assumptions. A resizable array may occasionally allocate a larger backing array and copy its elements; the cost of such a resize should not be silently treated as one ordinary fixed-capacity write. Likewise, a linked representation needs storage for links in addition to stored values. The abstract order guarantee does not itself settle which representation best fits a memory constraint.

Stack traces can be analyzed by recording the current ordered contents after each legal operation. If values are pushed in a specified order, a later value above an earlier one must be popped first before the earlier value can be removed. Interleaving pushes and pops changes the possible output sequences. Feasibility depends on both this order rule and any stated capacity bound. An attempted invalid operation must be treated according to a declared policy, such as stopping with an error; silently inventing a returned element changes the problem.

Nested activities are a natural application. A program can remember a suspended operation, process a nested operation, and then resume the most recently suspended one. A stack of opening brackets can similarly record which opening symbol must be matched next. A correct bracket checker must reject a mismatched closing symbol or a closing symbol encountered with an empty stack, and must also check that no unmatched openings remain after all input has been processed. Merely checking the final count of openings and closings is insufficient to establish correct nesting.

For this fixture, a stack is displayed from bottom to top, and its initial contents, capacity, and invalid-operation policy must be explicit whenever they affect the answer. Operations do not happen concurrently. Introduced symbol strings are hypothetical examples and do not carry a preassigned difficulty label. A question can inspect an operation, apply a short trace, or justify a constrained design, while relying on the same stated stack semantics.""",
            "zh": """栈只在称为栈顶的一端插入和删除。push 将元素压入栈顶，pop 删除并返回栈顶元素，peek 读取但不删除栈顶。当前仍在栈中的元素里，最后压入的最先弹出，这就是后进先出。该行为与底层采用数组还是链表无关；队列的移除顺序不同，不能不检查需求就替代栈。

数组实现可用 size 表示元素个数，有效元素位于 0 到 size-1。非空时栈顶下标为 size-1；入栈先写入 size 位置再递增，出栈先递减再读取对应位置。也可以用另一变量记录栈顶下标，但不能混用“元素个数”和“栈顶下标”的含义。固定容量 C 时应保持 0<=size<=C；满栈入栈是溢出尝试，空栈出栈或查看栈顶是下溢尝试。

链式栈可把链表头作为栈顶，添加和移除头结点只需修改常数个连接。在相应存储假设下，两者基本操作都可为常数时间。可扩容数组偶尔需要重新分配并复制元素，不能把这种实际复制当作一次普通写入；链式实现则需要额外连接字段。抽象操作顺序不能单独决定哪种表示更满足空间约束。

分析操作序列时，可在每次合法操作后记录从栈底到栈顶的内容。后入的元素若仍压在先入元素上方，必须先移除它，才能移除下方元素。交替进行压入和弹出，会改变可能的输出序列；序列可行性同时受顺序规则与容量限制。遇到非法操作，应按题目明确给出的策略处理，例如报错停止，不能凭空生成返回值。

嵌套操作适合使用栈：先保存暂停的操作，处理内部操作，再恢复最近暂停的操作。括号匹配可以记录尚待匹配的左括号。正确检查须拒绝类型不符的右括号、空栈时的右括号，还须在输入结束时检查是否仍有未匹配左括号。仅比较左右括号总数不能保证嵌套正确。

本资料按栈底到栈顶展示内容；若初始值、容量或非法操作策略影响答案，题目必须给出。操作不并发。自拟字符串和序列只作练习数据，不附带已经验证的难度。所有档位共用这些操作语义。""",
        },
    },
    {
        "id": "transactions", "split": "dev", "pilot_level": "medium",
        "references": [
            {"url": "https://www.postgresql.org/docs/17/tutorial-transactions.html", "title": "PostgreSQL 17: Transactions"},
            {"url": "https://www.postgresql.org/docs/17/transaction-iso.html", "title": "PostgreSQL 17: Transaction Isolation"},
            {"url": "https://www.postgresql.org/docs/17/mvcc-serialization-failure-handling.html", "title": "PostgreSQL 17: Serialization Failure Handling"},
        ],
        "name": {"zh": "数据库事务：原子性、快照隔离语义与重试", "en": "Database transactions: atomicity, snapshot visibility, and retries"},
        "notes": {
            "en": """A database transaction groups operations into one unit. In PostgreSQL, BEGIN starts an explicit transaction, COMMIT makes its successful changes permanent, and ROLLBACK cancels its uncommitted changes. Other transactions do not observe the group's unfinished changes as if they had already committed. A transfer involving a debit and a credit illustrates why treating two writes as a unit matters: a failed operation should not leave just one of the intended writes committed. Transactions also provide a boundary within which a session sees its own preceding writes.

Isolation determines how overlapping transactions observe database state. Under PostgreSQL Read Committed, an ordinary SELECT sees rows committed before that statement began, along with the transaction's own earlier changes. A later SELECT in the same transaction can therefore observe another transaction's newly committed changes. Under PostgreSQL Repeatable Read, ordinary queries use a snapshot associated with the transaction's first non-transaction-control statement, so concurrent commits do not change that view between successive reads. A stable snapshot does not establish that every collection of concurrent transactions has an outcome equivalent to running them one after another. PostgreSQL Serializable adds checking for serialization anomalies; an execution may be rejected rather than committed when the required guarantee cannot be maintained.

The application must be prepared for transaction failure. A serialization failure means retrying the complete transaction, including the reads and application decisions that selected the writes. Retrying only the final failed statement can reuse decisions made from a state that is no longer appropriate. A retry can also fail; applications need a considered retry policy rather than assuming one attempt always succeeds. The requirement to retry follows from the chosen concurrency behavior, not from a promise that all interleavings will transparently complete.

The following conventions belong to this educational fixture. They are explicit modeling assumptions for generated exercises, not quotations or claims about a measured database workload. Two named sessions each execute statements in their stated order. An interleaving lists when each statement begins and when each transaction commits. An ordinary read is distinguished from a write or a locking read; unless otherwise specified, questions use ordinary reads. Initial table values and every relevant change are supplied in the question. There are no hidden triggers, constraints, background transactions, or external side effects. If a question requires one of those features, it must explain the relevant rule in its own premises.

For visibility analysis, record what each read is allowed to see before considering whether the transaction eventually commits. For all-or-nothing analysis, distinguish an uncommitted write from a committed state change. For a proposed retry design, check whether it reruns the decisions that depend on database reads and whether its stated objective concerns correctness, availability, or both. These are different evaluation criteria. A task must not silently substitute the behavior of another database system for the PostgreSQL semantics stated here.

The notes supply the same facts to every difficulty level. A generated question may use small hypothetical tables or a short schedule, but it must include enough information to identify the relevant transaction boundaries and isolation level. Ambiguous terms such as safe or consistent need a specific invariant, such as preserving an explicitly given total or preventing an explicitly described concurrent outcome. Numeric examples are exercise inputs and are not observed experimental results.""",
            "zh": """数据库事务将多个操作组成一个单元。在 PostgreSQL 中，BEGIN 开始显式事务，COMMIT 提交成功修改，ROLLBACK 取消未提交修改。其他事务不会把这个单元尚未完成的修改当成已经提交的结果。转账的扣款与入账说明了原子性的作用：失败不能只留下其中一笔已提交。事务也能看到自己此前执行的修改。

隔离级别规定并发事务观察状态的方式。PostgreSQL 的 Read Committed 下，普通 SELECT 看到语句开始前已经提交的数据，以及本事务此前的修改；同一事务后续 SELECT 可以看到其他事务新提交的结果。Repeatable Read 则让普通查询使用本事务第一条非事务控制语句对应的快照，连续查询不会因其他事务的提交而改变这一视图。但稳定快照不代表并发事务的全部结果一定等价于逐个执行。Serializable 增加对序列化异常的检查，必要时拒绝某次执行，而不是允许它提交。

应用必须处理事务失败。出现序列化失败时，应重试整个事务，包括读取数据和据此选择写入操作的应用逻辑；仅重试最后一条失败语句可能继续使用失效的决策。重试本身也可能再次失败，不能承诺重试一次就一定成功。选择隔离语义并不意味着所有并发交错都能自动完成。

以下是本教学练习自定的建模约定，不是原文引用或实测工作量：两个具名会话分别按顺序执行语句；交错表明确标出语句开始与提交时刻；默认使用普通查询，若涉及加锁读取须特别说明。题目提供初始表内容与所有相关修改，不隐含触发器、其他约束、后台事务或外部副作用；若需要这些特性，必须说明规则。

分析可见性时，先判断每次读取允许看到什么，再讨论事务最终是否提交；分析原子性时，区分未提交写入与已提交状态。评价重试方案时，要检查是否重新执行了依赖读取结果的决策，并说明目标是正确性、可用性还是两者兼顾。不能把其他数据库的行为默认套到本资料的 PostgreSQL 语义。

所有难度使用同一知识范围。题目可以自拟小表和简短交错，但须明确事务边界与隔离级别。“安全”“一致”等词应落实为具体不变量，如保持明确给出的总量或禁止特定并发结果。题内数值属于练习输入，不是实验观测值。""",
        },
    },
    {
        "id": "cpu_scheduling", "split": "dev", "pilot_level": "hard",
        "references": [
            {"url": "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf", "title": "OSTEP chapter 7: Scheduling: Introduction"},
            {"url": "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf", "title": "OSTEP chapter 8: Scheduling: The Multi-Level Feedback Queue"},
        ],
        "name": {"zh": "CPU调度：响应时间、周转时间与时间片权衡", "en": "CPU scheduling: response time, turnaround time, and time-slice tradeoffs"},
        "notes": {
            "en": """A scheduler chooses which ready job receives the processor. Turnaround time equals completion time minus arrival time. Response time equals the first time a job runs minus its arrival time. These metrics measure different things: early access to a processor does not necessarily imply early completion. First-come, first-served runs jobs in arrival order without preempting them. Shortest Job First selects the shortest available job and is non-preemptive. Shortest Time-to-Completion First is preemptive and selects the job with the least remaining processing time. Comparisons involving these shortest-job policies must state how execution lengths are known.

Round Robin rotates through a ready queue, running each selected job for at most one time slice before moving an unfinished job to the back. Shorter slices can improve initial responsiveness but increase the frequency of context switches. Larger slices amortize switching costs but can lengthen waits before a different job first runs. Neither a smaller average response time nor a smaller switching fraction alone establishes that a policy is best for every objective.

A multi-level feedback queue, or MLFQ, uses observed execution behavior instead of requiring exact future job lengths. Jobs in higher-priority queues run before lower-priority jobs; equal-priority jobs can share service by Round Robin. New jobs begin at high priority, and consuming the allowed CPU allotment causes demotion. Accounting for total consumed allotment prevents a job from retaining high priority indefinitely merely by yielding just before each slice ends. Periodic priority boosts can help jobs otherwise left waiting at low priority. Queue levels, slice lengths, allotments, and boost intervals are policy parameters, not universal constants.

This fixture adds an explicit scheduling model for exercises. It is authored example scaffolding rather than text copied from a textbook. Unless a question states otherwise, there is one processor, jobs are independent, and each job consists of one CPU burst with no I/O. Arrival times and required CPU service are provided. The processor never serves two jobs simultaneously. Time spent switching is not CPU service delivered to any job. A job that finishes before its slice ends does not use the remaining slice. If a job arrives at exactly a slice boundary, the question must say whether that arrival is enqueued before or after the preempted job. Ties must be resolved by an explicit rule, such as alphabetical job names.

A question that includes switching overhead must define when that overhead applies: for example, only when moving between different jobs, with no initial dispatch charge. It must also state whether arrivals can occur while switching and how they enter the queue. Questions that ignore overhead must say so. These conventions make a timeline reproducible and prevent a numeric answer from depending on unstated simulator behavior.

A comparison can report each job's first-run and completion times, then compute the requested averages. A design recommendation also needs an objective and constraints, such as a maximum response time, a switching budget, or a fairness requirement. A policy can satisfy one constraint while losing on another metric. Choosing a scheduler should therefore follow the stated workload and requirements. Hypothetical burst lengths and budgets introduced in an exercise are not measured workload traces, and labels assigned by the generator are not empirical student difficulty measurements.""",
            "zh": """调度器决定哪个就绪任务获得 CPU。周转时间等于完成时刻减到达时刻，响应时间等于首次运行时刻减到达时刻；更早开始不一定意味着更早结束。先来先服务按到达顺序非抢占运行。最短任务优先 SJF 选择当前可用任务中运行时间最短的，并且不抢占；最短剩余时间优先 STCF 允许抢占，总是选择剩余服务时间最短的任务。使用这类策略比较时，要说明如何知道所需运行时间。

轮转调度 RR 让就绪队列中的任务轮流运行，每次最多一个时间片，尚未完成的任务回到队尾。较小时间片可改善首次响应，却增加切换频率；较大时间片可分摊切换开销，却可能延长其他任务首次运行前的等待。平均响应更小或切换占比更低，都不能单独证明某策略适合所有目标。

多级反馈队列 MLFQ 根据已经观察到的执行行为调整优先级，不要求预知准确运行时间。高优先级任务先于低优先级任务执行，同级可轮转；新任务从高优先级开始，用完 CPU 配额后降级。按累计使用量计算配额，可防止任务通过每次在时间片结束前主动让出 CPU 来永久保留高优先级。周期性提升优先级可帮助长期等待的低优先级任务。队列层数、片长、配额和提升间隔都是策略参数。

本练习另行规定一套明确模型，属于自拟教学条件：默认单处理器、独立任务、每个任务只有一个 CPU burst 且无 I/O；题目提供到达时间与服务量。切换消耗的时间不算给任何任务的 CPU 服务。提前完成的任务不消耗剩余时间片。任务恰在片尾到达时，要说明新到任务与被抢占任务谁先入队，平局也要指定顺序。

如果计算切换开销，应写明何时计费，例如只在切换到另一个任务时计费且首次派发免费，并说明切换期间到达任务如何入队；忽略开销时也须明确。可先记录每个任务首次运行与结束时刻，再计算所需指标。设计建议还需要具体目标与约束，如响应上限、开销预算或公平性。一个方案可能满足一个约束，却在另一个指标上更差。题内任务长度和预算是自拟输入，不是实测工作量，生成器标注也不是学生实测难度。""",
        },
    },
    {
        "id": "hash_collision", "split": "holdout", "pilot_level": None,
        "course_file": "chapter_hashing/hash_collision.md",
        "name": {"zh": "哈希冲突：链式存储、线性探测与删除语义", "en": "Hash collisions: chaining, linear probing, and deletion semantics"},
        "notes": {
            "en": """A hash table maps a key to an initial position using a hash function. Distinct keys may produce the same initial position; this is a collision, not evidence that the keys are equal. A lookup must still compare the actual key with the key stored in a candidate entry. A table's load factor is the number of stored key-value entries divided by the number of buckets or slots, using the capacity definition of its representation. The meaning of an occupied location differs between separate chaining and open addressing.

Separate chaining stores a collection of entries at each bucket. Keys with the same hash index can coexist in that collection. A lookup first selects a bucket, then searches its entries for the requested key. Inserting or removing an entry must preserve access to the other entries in that bucket. A chained table can hold more entries than buckets because a bucket can contain several entries. Longer bucket collections increase the work of operations that search through them; a favorable expected cost depends on distributing keys reasonably well rather than merely having a hash function.

Open addressing stores entries directly in table slots. With linear probing, a collision causes the algorithm to examine subsequent slots cyclically until it reaches a matching key or an appropriate place to stop. For a table of capacity m, a probe sequence starting at h can visit h, (h + 1) modulo m, and so on. Adjacent runs of occupied positions can grow and merge, a phenomenon called primary clustering. A search may inspect many entries even when its initial hash index is computed in constant time. Capacity and termination rules are necessary when the table becomes full.

Deletion requires particular care in an open-addressed table. If an entry in the middle of a probe sequence is changed to an ordinary never-used empty slot, a future lookup may stop there and incorrectly report that a later key is absent. A deleted marker, often called a tombstone, distinguishes a reusable location from a location that ends a lookup. Search continues past a tombstone. Insertion may reuse one, but a map that updates an existing key must still avoid creating another entry for that key farther along the probe sequence.

Rehashing allocates a table with a different capacity and reinserts existing entries according to the new positions. Copying each entry to the same numeric slot without reconsidering its hash index is not equivalent. Expansion can reduce the load factor but has a cost because existing entries must be processed. Under the assumptions used for expected analysis, controlling load helps maintain efficient operations; it is not a proof that an adversarial set of keys can never produce a long search.

For exercises in this fixture, a question must state the table capacity, hash function, collision policy, initial entries, and deletion convention whenever they affect the result. Probe counts must say whether the final empty slot or matching slot is counted. Assume a map has at most one entry per key, and distinguish replacing an existing value from adding a new key. Small tables and key sequences are hypothetical examples. No cryptographic properties, unspecified resizing threshold, or implementation-specific library behavior is assumed.""",
            "zh": """哈希表通过哈希函数把键映射到初始位置。不同键可能得到同一位置，这叫冲突，并不表示两个键相等。查找仍须比较实际键值。负载因子为条目数除以容量，但链式存储的桶与开放寻址的槽位含义不同，不能把两种表示的限制直接混用。

链式存储在每个桶中保存一组条目，哈希到同一桶的不同键可以共存。查找先选桶，再寻找目标键；删除某条目不能破坏同桶其他条目的可达性。一个桶可以容纳多个条目，因此条目总数可以大于桶数。桶内集合越长，需要逐项搜索的工作越多；较好的期望效率依赖键分布，而不是只要有哈希函数就自动成立。

开放寻址把条目直接放在槽位。线性探测发生冲突后依次检查后续位置并循环回到开头。容量 m、初始位置 h 时，探测可为 h、(h+1) mod m 等。相邻占用区间会增长和合并，形成聚集；即使计算初始位置只需常数时间，查找仍可能检查很多槽位。满表情况下必须明确终止规则。

删除时，不能随意把探测链中间的条目变为从未使用的空槽，否则后续查找可能过早停止，错误判断后方键不存在。墓碑标记表示这里曾经有条目、可以复用，但不会终止搜索。插入可复用墓碑；若映射允许更新现有键，还须检查后续是否已有该键，避免制造重复条目。

重哈希会分配不同容量的表，并按新规则重新插入现有条目；只把条目复制到相同数值下标不等价。扩容可以降低负载，却需要处理已有条目。控制负载有利于期望效率，但不能证明任何对抗键集合都不会产生长探测。

本资料要求题目写明容量、哈希函数、冲突处理、初始状态和删除规则；若计算探测次数，还须说明最终命中或空槽是否计数。映射每个键最多一个条目，替换值与添加新键要区分。自拟小表与键序列不是实测工作量，不假设密码学性质、未给出的扩容阈值或某语言库的隐藏实现。""",
        },
    },
    {
        "id": "avl_tree", "split": "holdout", "pilot_level": None,
        "course_file": "chapter_tree/avl_tree.md",
        "name": {"zh": "AVL树：高度、旋转与搜索顺序不变量", "en": "AVL trees: heights, rotations, and the search-order invariant"},
        "notes": {
            "en": """A binary search tree with distinct keys stores smaller keys in a node's left subtree and larger keys in its right subtree. This ordering supports search by choosing one subtree after a comparison, but the search cost also depends on tree height. Inserting keys into an ordinary unbalanced search tree can produce a long chain. An AVL tree adds a height-balance rule to the search-order rule, maintaining the condition that the heights of a node's left and right subtrees differ by at most one at every node.

This fixture uses height minus one for an empty subtree and height zero for a leaf. A nonempty node's height is one plus the maximum height of its children. Its balance factor is left height minus right height. Balance factors of minus one, zero, and one satisfy the AVL condition. A stored height must be recomputed after changing a child link; an outdated height can make a later balance decision incorrect even when the pointer structure currently looks plausible. Other texts may count levels differently, so an exercise must not mix height conventions.

A right rotation can repair an imbalance leaning to the left. Let y be the unbalanced subtree root, x its left child, and B the right subtree of x. The rotation makes x the new subtree root, y the right child of x, and B the left subtree of y. The keys in B remain between x and y in sorted order, which explains why they cannot simply be discarded or attached on the outside. A left rotation is the symmetric operation. Rotation changes local shape while preserving the in-order sequence of keys.

When a left-heavy imbalance is caused along the left child's left side, a single right rotation is appropriate. When the growth is on the left child's right side, first rotate that child left and then rotate the unbalanced root right. The two right-heavy cases are symmetric. These cases are commonly described as left-left, left-right, right-right, and right-left. A case name must refer to the actual path or child balance; it is not determined only by whether the newly inserted key is numerically large or small relative to the root.

Insertion first follows ordinary binary-search-tree order, then updates heights and repairs affected ancestors. Deletion can reduce subtree height and may require checking additional ancestors after a local repair. A rotation alone is not a substitute for removing the correct key or preserving links to unaffected subtrees. Maintaining the balance condition bounds tree height logarithmically, supporting logarithmic search and updates, while each individual local rotation changes only a constant number of links.

Exercises must give every relevant child relationship, the distinct keys, and the operation being performed. Trees may be described as parent-to-child relationships rather than requiring a drawing. If an exercise supplies stored heights, it should state whether those heights are inputs to verify or guaranteed current values. Students may reason about a local repair, the sorted-order invariant, and which ancestors need new heights. They are not expected to assume a particular library's node layout, memory allocator, or duplicate-key policy. All introduced trees are hypothetical fixtures, with no empirical difficulty annotation attached.""",
            "zh": """互异键的二叉搜索树要求左子树键小于根、右子树键大于根。该顺序支持比较后选择一个子树，但实际搜索代价还取决于树高。普通搜索树可能因插入顺序退化成长链。AVL 树在搜索顺序之外，要求每个结点左右子树的高度差不超过一。

本资料规定空子树高度为 -1，叶子为 0；非空结点高度为两子树最大高度加一。平衡因子取左高减右高，允许 -1、0、1。修改子链接后须更新存储的高度，否则即使当前结构看似合理，后续平衡判断也可能出错。其他资料可能采用不同层数约定，解题时不能混用。

右旋可修复向左倾斜的失衡：设原根为 y，左孩子为 x，x 的右子树为 B。右旋后 x 成为新根，y 成为 x 的右孩子，B 成为 y 的左子树。B 中的键仍位于 x 与 y 之间，因此不能丢弃 B 或把它接到外侧。左旋是对称操作。旋转改变局部形状，但保持中序键序列不变。

左重失衡若沿左孩子的左侧产生，可对失衡根单次右旋；若增长发生在左孩子的右侧，则先对左孩子左旋，再对失衡根右旋。右重情况对称，对应左左、左右、右右、右左四类。类别应由真实路径或孩子平衡状态判断，不能只看新键相对根的大或小。

插入先遵守普通搜索树顺序，再更新高度并修复祖先。删除可能让子树变矮，完成一次局部修复后仍须继续检查其他祖先。旋转不能代替删除正确的键，也不能破坏未参与子树的链接。维持平衡将高度限制在对数级，支持对数级查找和更新；一次局部旋转只修改常数条链接。

题目须提供相关子结点关系、互异键与待执行操作，可以用父子关系文字表代替图。如果给出存储高度，须说明它们是待检查输入还是保证正确的现值。可讨论局部修复、搜索顺序不变量与需要更新的祖先，不假定某库的内存分配、结点布局或重复键策略。自拟树仅是练习输入，不带经过实测的难度标签。""",
        },
    },
    {
        "id": "paging", "split": "holdout", "pilot_level": None,
        "references": [
            {"url": "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf", "title": "OSTEP chapter 18: Paging: Introduction"},
        ],
        "name": {"zh": "分页：地址分解、映射与线性页表成本", "en": "Paging: address decomposition, mappings, and linear page-table cost"},
        "notes": {
            "en": """Paging divides a virtual address space into fixed-size pages and physical memory into frames of the same size. A virtual address consists of a virtual page number and an offset within that page. A page-table entry maps the virtual page number to a physical frame number, while the offset remains unchanged during translation. Consequently, consecutive virtual pages do not have to occupy consecutive physical frames. An entry can also record whether a translation is valid and what operations are permitted on the page.

For a byte-addressed system with page size 2 to the power b bytes, the offset uses b bits. A v-bit virtual address therefore has v minus b page-number bits. A simple linear page table has one entry for each virtual page; its storage is the number of virtual pages multiplied by the entry size. This table can be large even when a process uses only a small part of its virtual address space. Address translation and page-table storage are separate costs.

The rest of this note defines a deliberately small hypothetical machine for educational exercises. These definitions are part of the fixture, not values measured from the textbook or a real computer. The machine is byte-addressed. A question must supply its virtual address width, physical address width, page size, and page-table entry size if those quantities are needed. Powers of two use binary units: one KiB is 1024 bytes. Unless specified otherwise, address values are nonnegative integers and a displayed page table covers only the entries shown. Missing entries cannot be assumed to map to physical frame zero.

Given a page size P and virtual address A, compute the page number as the integer quotient floor(A / P), and the offset as the remainder A modulo P. If that page has a valid mapping to frame F and the requested access is allowed, the physical address is F times P plus the offset. A valid mapping does not imply that every operation is allowed: a read permission does not grant a write permission. If the translation is invalid or permission is absent, the exercise should report the specified fault instead of inventing a physical address. No demand-loading policy is assumed unless the question explains one.

Separate processes in the fixture have separate page tables. The same virtual address can therefore translate to different physical addresses in different processes. Two entries may deliberately point to one shared frame if the question provides such mappings. A question about sharing must state the relevant permissions and whether writes are intended to be visible through both mappings; it must not assume isolation merely because the virtual page numbers differ.

For storage comparisons, distinguish the virtual address range, the physical frames currently assigned, and the space occupied by the linear page table. If page size changes, both the number of entries and the number of offset bits change. A reasoning exercise may ask for these quantities or require a design to meet an explicit table-space budget. It must provide the needed numerical premises and identify which costs are ignored. These notes do not assume translation caches, multiple page-table levels, replacement algorithms, or an undocumented operating-system implementation. All difficulty levels use this same limited machine model.""",
            "zh": """分页把虚拟地址空间分成固定大小的页，把物理内存分成同样大小的页框。虚拟地址由虚拟页号与页内偏移组成。页表项将虚拟页号映射到物理页框号，地址转换保持偏移不变。因此，相邻虚拟页不必放在相邻物理页框。页表项还可包含映射是否有效以及允许的访问操作。

按字节编址、页大小为 2 的 b 次方字节时，偏移占 b 位，v 位虚拟地址的页号占 v-b 位。简单线性页表为每个虚拟页保留一个项，空间为虚拟页数乘每项字节数。即使进程只实际使用地址空间的一小部分，这种表也可能很大。地址转换的工作与页表本身的存储是两个成本。

以下规定一个自拟教学机器，不是教材实测值或真实硬件配置：按字节编址；计算需要时，由题目给出虚拟和物理地址宽度、页大小、页表项大小。KiB 表示 1024 字节。地址为非负整数，展示的表只保证列出的映射；没有列出的条目不能默认为映射到页框零。

页大小 P、虚拟地址 A 时，虚拟页号为 floor(A/P)，偏移为 A mod P。如果该页有效映射到页框 F 且允许所请求的访问，则物理地址为 F×P+偏移。映射有效不意味着所有操作都获准，例如可读不自动意味着可写。映射无效或权限不足时，按题目要求报告故障，不能编造物理地址；除非给出规则，否则不假设操作系统会自动装入缺页。

本机器的不同进程各有页表，因此同一虚拟地址可对应不同物理地址；若题目明确给出，两项也可指向共享页框。讨论共享时，应写出访问权限和写入是否通过另一映射可见，不能仅因虚拟页号不同就认定物理内容隔离。

比较空间时，要区分虚拟地址范围、当前分配的物理页框与线性页表占用。页大小变化同时影响偏移位数和表项数。题目可以要求计算数量或满足明确的表空间预算，但须提供数值与被忽略的成本。本资料不预设地址转换缓存、多级页表、置换算法或未说明的操作系统实现。各难度使用同一受限机器模型。""",
        },
    },
]


def references(topic):
    if "references" in topic:
        return topic["references"]
    manifest = json.loads(MANIFEST.read_text())
    for source in manifest["sources"]:
        for download in source["downloads"]:
            if download.get("repository_path", "").endswith(topic["course_file"]):
                actual = hashlib.sha256((ROOT / download["local_path"]).read_bytes()).hexdigest()
                assert actual == download["sha256"], f"source hash mismatch: {download['local_path']}"
                return [{"url": download["url"], "title": f"Hello Algo: {topic['id']}",
                         "local_path": download["local_path"], "sha256": download["sha256"],
                         "authors": source["authors"], "license": source["license"],
                         "license_path": "benchmarks/rag/course_sources/hello_algo_zh/LICENSE"}]
    raise ValueError(topic["id"])


def build():
    cases = []
    profiles = {
        "zh": "计算机本科生，已学习所给资料、基本程序控制结构与本课程入门概念；可查阅本题资料，不假定进阶课程、特定语言库或其他数据库的知识。",
        "en": "An undergraduate computer science student who has studied the supplied notes, basic program control flow, and introductory course concepts; the notes are available during the task. Do not assume advanced courses, a particular language library, or another database system's behavior.",
    }
    for topic in TOPICS:
        refs = references(topic)
        for language in ("zh", "en"):
            context = topic["notes"][language].strip()
            for difficulty in ("easy", "medium", "hard"):
                case_id = f"{topic['id']}_{language}_{difficulty}"
                cases.append({
                    "id": case_id, "topic_id": topic["id"], "split": topic["split"],
                    "pilot": difficulty == topic["pilot_level"], "language": language,
                    "target_difficulty": difficulty,
                    "question_type": "mcq" if difficulty == "easy" or topic["id"] in {"graph_traversal", "stack"} else "short_answer",
                    "topic": topic["name"][language], "learner_profile": profiles[language],
                    "sources": [{"id": f"fixture_{topic['id']}_{language}", "text": context,
                                 "document_name": f"AI-curated study fixture: {topic['name'][language]}",
                                 "page": None, "url": refs[0]["url"]}],
                    "provenance": {
                        "kind": "ai_curated_educational_fixture", "author_type": "AI assistant",
                        "original_source_excerpt": False, "human_authored_question": False,
                        "human_difficulty_annotation": False, "human_translation_verified": False,
                        "factual_review_status": "pending_independent_review",
                        "source_references": refs,
                        "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                        "note": "Newly written bilingual study notes grounded in the references and explicit hypothetical exercise conventions. Not original course text, a human translation, a question, a gold difficulty label, or empirical learner data. URLs identify background references; page is null because these are curated notes, not page-aligned excerpts.",
                    },
                })
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for topic in TOPICS:
        group = [case for case in cases if case["topic_id"] == topic["id"]]
        assert len(group) == 6
        assert len({case["split"] for case in group}) == 1
        for language in ("zh", "en"):
            assert len({case["provenance"]["context_sha256"] for case in group if case["language"] == language}) == 1
    pilot = [case for case in cases if case["pilot"]]
    assert len(pilot) == 6 and all(case["split"] == "dev" for case in pilot)
    assert Counter(case["language"] for case in pilot) == {"zh": 3, "en": 3}
    assert Counter(case["target_difficulty"] for case in pilot) == {"easy": 2, "medium": 2, "hard": 2}
    payload = {
        "schema_version": "difficulty-authoring-cases-v1", "created_at": "2026-09-19",
        "label_status": "no_human_difficulty_labels", "cases": cases,
    }
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    (OUT / "cases.json").write_bytes(data)
    checks = {
        "schema_version": payload["schema_version"], "case_count": len(cases),
        "pilot_case_count": len(pilot), "topic_count": len(TOPICS),
        "split_counts": dict(Counter(case["split"] for case in cases)),
        "cases_sha256": hashlib.sha256(data).hexdigest(),
        "question_type_counts": dict(Counter(case["question_type"] for case in cases)),
        "context_sizes": {
            topic["id"]: {"zh_characters": len(topic["notes"]["zh"].strip()),
                          "en_whitespace_words": len(topic["notes"]["en"].split())}
            for topic in TOPICS
        },
        "checks": ["unique case IDs", "one split per topic family", "paired languages at every difficulty", "unchanged per-language context across difficulties", "pilot exclusively dev with both languages and all difficulties", "local course source hashes match pinned manifest"],
        "human_review_performed": False,
    }
    (OUT / "validation.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    build()
