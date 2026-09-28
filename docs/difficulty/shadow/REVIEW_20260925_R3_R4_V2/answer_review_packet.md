# 独立答案与来源复核材料

先完成 teacher_review_template.csv 中的难度判断，再打开本页。先核对题目条件、参考答案和来源，再查看 comparison.md 中的模型判级。

## REAL_TASKS_20260925_R3_task_2_q1

**学生可见内容**

Learning objectives:
识别共享自旋锁所保护的线程与中断处理程序并发访问，并列举并发的来源。
分析持锁且中断开启时被中断处理程序再次请求同一锁所形成的自等待死锁因果链。
给出取锁、释放锁与中断使能之间的次序约束及嵌套临界区簿记要求。
比较同一共享锁在单 CPU 与多处理器下的后果差异，并界定禁用中断的作用范围。
区分禁止同 CPU 重复取锁与持锁关中断两种防护，说明其针对的故障模式不同。

共享自旋锁与中断交互的基本约束
自旋锁用 locked 字段表示可用或被持有；仅靠“先读再写”不能保证互斥，因为多个 CPU 可能同时读到可用，因此对 locked 的检查与置位必须作为一个原子步骤完成。

有些自旋锁保护的数据同时被内核线程和中断处理程序使用，锁定用于把这两类访问串行化。

由此产生一条关键约束：若某自旋锁会被中断处理程序使用，CPU 就绝不能在中断开启时持有该锁。取锁与开/关中断的相对次序因此很重要：acquire 必须先把本 CPU 的中断关掉，再置位 locked；release 必须先释放锁，之后才恢复中断。嵌套临界区通过 push_off/pop_off 记录本 CPU 上的持锁层数，只有层数归零时才恢复到最外层进入前的中断使能状态。

并发的来源与禁用中断的作用范围
并发指多个指令流交错执行，其来源有三类：多处理器并行、线程切换、以及中断处理程序与可被中断的代码同时修改同一数据。

因此，同一个共享锁在不同来源下防的是不同交错；而“关中断”这一类手段只作用于执行它的那个 CPU：它阻止本 CPU 上会使用该锁的中断在临界区内被递交，却不影响其他 CPU 上的执行者取同一把锁。

内核中有一把自旋锁 tickslock，保护一个计数器变量。内核线程 A 在函数 f() 中取 tickslock、读改写该计数器、再释放锁；时钟中断处理程序 clockintr 也会取同一把锁并在临界区内更新该计数器。锁的 acquire 与 release 采用“取锁时关本 CPU 中断、释放锁时恢复中断”的策略。

请按任务逐条回答，并对每个结论说明依据。

1. 说明为什么该计数器需要 tickslock 保护，并列出可能使 A 与 clockintr 的访问交错的并发来源。
2. 设 A 在 f() 中已取到 tickslock，但此临界区内中断处于开启状态；此时一个时钟中断在本 CPU 上被递交，clockintr 开始执行。逐步分析锁最终是否可能被释放、该 CPU 会处于什么状态、是否会波及系统其他部分。
3. 给出避免任务 2 后果的设计约束，并说明 acquire 与 release 中“取锁/释放锁”与“关中断/恢复中断”两组操作的相对先后次序要求；解释次序颠倒为什么会打开一个危险的时间窗口。
4. 说明嵌套临界区中如何决定何时才真正恢复中断，以及为什么不能在每次释放锁时无条件开中断。
5. 分别在下列两种硬件场景下，判断断言 A 与断言 B 是否成立，并结合“禁用（或开启）中断的作用范围”论证：
场景 S：系统只有一个 CPU。
场景 P：系统有多个 CPU，A 与 clockintr 都可能运行在其中任一 CPU 上，且 tickslock 可能被不同 CPU 上的代码同时请求。
断言 A：本 CPU 上的中断处理程序可以一直等待某个线程释放自旋锁。
断言 B：另一个 CPU 上的中断处理程序可以等待某个线程释放自旋锁。
6. 对“CPU 重复取得自己已持有的锁”存在两种立场。请说明禁止同 CPU 重复取锁是否可以替代在持锁期间关中断，并论证。

**参考答案**

任务 1：该计数器被内核线程 A 与中断处理程序 clockintr 共同访问，两者可能交错，因此需要锁把两类访问串行化。并发来源有三类：多处理器并行、本 CPU 上的线程切换、以及中断处理程序打断可被中断的代码。任一来源都可能让“读—改—写”交错，造成丢失更新或读到中间状态。
任务 2：clockintr 会尝试取 tickslock，发现已被 A 持有，于是在本 CPU 上自旋等待。此时只有 A 能释放该锁，而 A 已在本 CPU 上被中断打断，只有等 clockintr 返回后才可能继续运行；于是 clockintr 永远等不到锁被释放，A 也永远等不到中断返回，形成本 CPU 上的自等待死锁。锁始终不被释放，其他需要 tickslock 的代码也会被阻塞，可能使系统其他部分冻结。
任务 3：约束是——只要某自旋锁会被中断处理程序使用，本 CPU 就绝不能在中断开启时持有该锁。次序要求：acquire 必须先关本 CPU 中断，再置位 locked；release 必须先释放锁，之后才恢复中断。若先置位 locked 再关中断，便存在一个“锁已被持有而中断仍开”的短暂窗口；若先恢复中断再释放锁，则存在“锁尚未释放而中断已开”的窗口。恰好在这类窗口内发生会使用该锁的中断，就会触发任务 2 的死锁。
任务 4：用 push_off/pop_off 记录本 CPU 当前的持锁嵌套层数：acquire 时递增，release 时递减，只有层数减到零（即本 CPU 不再持有任何自旋锁）才恢复中断。若每次释放锁都无条件开中断，那么在外层临界区仍持锁时中断就会被提前打开，外层临界区重新暴露在任务 2 的死锁风险之下；同时也会破坏“恢复到最外层进入前的中断使能状态”这一要求。
任务 5：断言 A——场景 S 不成立，场景 P 同样不成立。本 CPU 上的中断处理程序一旦自旋等待自己打断的那个持锁线程，该线程就无法继续运行来释放锁，等待只能是死锁而非正常等待；在场景 P 中，被本 CPU 中断打断的线程仍只能等待该中断返回，因此结论与场景 S 相同。断言 B——场景 S 中不存在其他 CPU，该情形不可发生；场景 P 中成立。另一个 CPU 上的中断处理程序可以自旋等待某线程释放自旋锁，因为持锁线程在别的 CPU 上仍能继续执行并最终释放锁。关键范围差异是：关中断只影响执行它的那个 CPU，不能阻止其他 CPU 上的中断处理程序取同一把锁并等待；它也只能阻止“本 CPU 上会使用该锁的中断在临界区内被递交”，不能覆盖已在本 CPU 上、在临界区之外开始等待同一把锁的中断。
任务 6：不能替代。禁止同 CPU 重复取锁针对的是同一执行上下文再次请求自己已持有的锁，即把这类重入当成错误；而任务 2 的问题是异步中断在持锁期间打断执行并请求同一把锁，并不是同一上下文的重入，禁止重复取锁无法阻止这种交错。两种立场对“允许重复取锁（re-entrant/recursive）”还是“禁止”本可各自自洽，但无论选哪一种，只要该锁会被中断处理程序使用，就必须保持“不在中断开启时持有该锁”的约束；换言之，二者防护的是不同故障模式，不可相互替代。

**答案解释**

本题要求把自旋锁的互斥原理、共享锁的线程/中断访问、中断使能与取锁次序、嵌套簿记、并发来源以及单/多处理器差异整合到同一情境中，并对两个断言分别给出条件化判断。

任务 1 检查是否指出共享访问与三类并发来源，而不是只复述“需要锁”。
任务 2 检查死锁因果链是否完整：中断处理程序自旋等待、持锁线程被压在中断帧下无法运行、锁永不释放、并波及需要该锁的代码。
任务 3、4 检查次序约束与嵌套计数：先关中断后置位、先释放锁后恢复中断，且只在层数归零时恢复，而不是无条件开中断。
任务 5 是最容易出错处：断言 A 在两种场景中都只能得到“不能一直等待”，因为等待者与被等待者在同一 CPU 上；断言 B 只在多处理器场景成立，因为持锁线程在别的 CPU 上仍可推进。作答必须把“关中断只作用于本 CPU”这一范围说清楚，并且不要把断言 A 与断言 B 混为一谈。
任务 6 检查是否把“禁止重复取锁”与“持锁关中断”视为针对不同故障模式的两种措施。

**题目引用的来源**

### os_interrupt_locks.md · context_6e969ab61218a462f2abc58f726040a4

A question that sometimes arises is what should happen if a CPU tries to acquire a lock that the same CPU already holds. One line of reasoning is that this should be allowed: no other CPU can hold the lock, so there’s no need to worry about CPUs interfering with each others’ use of the protected data. Locking systems that allow a CPU to re-acquire a lock it already holds are called a re-entrant or recursive. On the other hand, if a lock is already held, even on the same CPU, that means an operation may have temporarily violated and not yet restored some invariants; to allow a new operation to commence while the invariants don’t hold seems like an invitation to bugs. Xv6 takes this latter view, and forbids a CPU that currently holds a lock from re-acquiring it. Detecting this situation is the purpose of the call to holding in acquire.

7.5 Locks and interrupts

Some xv6 spinlocks protect data that is used by both threads and interrupt handlers. For example, the clockintr timer interrupt handler might increment ticks at about the same time that a kernel thread reads ticks in sys_pause. The lock tickslock serializes the two accesses.

### os_interrupt_locks.md · context_cb9db0d5737606abbb40cb3532c7e1f8

The interaction of spinlocks and interrupts raises a potential danger. Suppose sys_pause holds tickslock, and its CPU is interrupted by a timer interrupt. clockintr would try to acquire tickslock, see it was held, and wait for it to be released. In this situation, tickslock will never be released: only sys_pause can release it, but sys_pause will not continue running until clockintr returns. So the CPU will deadlock, and any code that needs either lock will also freeze.

To avoid this situation, if a spinlock is used by an interrupt handler, a CPU must never hold that lock with interrupts enabled. Xv6 is more conservative: when a CPU acquires any lock, xv6 always disables interrupts on that CPU. Interrupts may still occur on other CPUs, so an interrupt’s acquire can wait for a thread to release a spinlock; just not on the same CPU.

### os_interrupt_locks.md · context_788a42237a3fb0dd9dc62368670d58e4

Xv6 re-enables interrupts when a CPU holds no spinlocks; it must do a little book-keeping to cope with nested critical sections. acquire calls push_off and release calls pop_off to track the nesting level of locks on the current CPU. When that count reaches zero, pop_off restores the interrupt enable state that existed at the start of the outermost critical section. push_off and pop_off tell the CPU to enable and disable interrupts by changing the SIE (Supervisor Interrupt Enable) bit in the sstatus (Supervisor Status) register, using intr_on and rc_sstatus(SSTATUS_SIE); the latter clears the SIE bit.

It is important that acquire call push_off strictly before setting lk->locked. If the two were reversed, there would be a brief window when the lock was held with interrupts enabled, and an unfortunately timed interrupt would deadlock the system. Similarly, it is important that release call pop_off only after releasing the lock (spinlock.c:73).

### os_races.md · context_253cf66a589aa0d41532d4d6533fc9fe

Most kernels, including xv6, interleave the execution of multiple activities. One source of interleaving is multiprocessor hardware: computers with multiple CPUs executing independently, such as xv6’s RISC-V. These multiple CPUs share physical RAM, and xv6 exploits the sharing to maintain kernel data structures that all CPUs read and write. This sharing raises the possibility of one CPU reading a data structure while another CPU is mid-way through updating it, or even multiple CPUs updating the same data simultaneously; without careful design such parallel access is likely to yield incorrect results or a broken data structure. Even on a uniprocessor, the kernel may switch the CPU among a number of threads, causing their execution to be interleaved. Finally, a device interrupt handler that modifies the same data as some interruptible code could damage the data if the interrupt occurs just as the interrupted code is also modifying the data. The word concurrency refers to situations in which multiple instruction streams are interleaved, due to multiprocessor parallelism, thread switching, or interrupts.

### os_races.md · context_b2c7b4005f3ab8914040f2eead7f5186

Xv6 has two types of locks: spinlocks and sleep-locks. We’ll start with spinlocks. Xv6 represents a spinlock as a struct spinlock. The important field in the structure is locked, a word that is zero when the lock is available and non-zero when it is held. Were there no concurrency, xv6 could acquire a lock with code like

Unfortunately, this implementation does not guarantee mutual exclusion in the face of concurrency. Two CPUs could simultaneously reach line 25, see that lk->locked is zero, and then both grab the lock by executing line 26. At this point, two different CPUs hold the lock, which violates the mutual exclusion property. What we need is a way to make lines 25 and 26 execute as an atomic (indivisible) step.

## REAL_TASKS_20260925_R4_task_1_q1

**学生可见内容**

Learning objectives:
说出事务原子性“全有或全无”的含义。
判断转账中途失败时，已执行但未提交的更新是否应生效。
区分 PostgreSQL 中 COMMIT 与 ROLLBACK 对事务内更新的不同结果。

事务的原子性
事务把多个步骤捆绑成一个单一的全有或全无操作。
中间状态对其他并发事务不可见：若某次故障使事务无法完成，那么已执行的任何步骤都不影响数据库。
资料中的银行例子：不能出现 Bob 收到 100 美元却没有从 Alice 账户扣款，也不能出现扣了 Alice 却没有贷记 Bob。
从其他事务的角度看，事务要么完全发生，要么根本不发生。

PostgreSQL 中的 BEGIN、COMMIT 与 ROLLBACK
在 PostgreSQL 中，用 BEGIN 和 COMMIT 把事务的 SQL 命令包起来，形成事务块。
若事务进行到一半决定不提交（例如刚发现 Alice 的余额变成负数），可以改为发出 ROLLBACK，此前所有更新都会被取消。
未提交的更新对其他事务不可见；提交时，已提交的更改作为一个整体对其它会话可见，被回滚的更改则完全不会变得可见。
若不发出 BEGIN，每条单独的语句都有隐式的 BEGIN，并在成功时被 COMMIT 包裹。

Alice 向 Bob 转账 100 美元，其 PostgreSQL 事务用 BEGIN 开始，包含“从 Alice 账户扣款 100”和“向 Bob 账户贷记 100”两条更新。

条件：
1. 事务尚未发出 COMMIT。
2. 在写入两条更新期间发生故障，事务无法完成。
3. 资料中的银行例子要求：不应出现 Bob 收到 100 美元却没有从 Alice 账户扣款，也不应出现扣了 Alice 却未贷记 Bob。

下面哪一项描述符合资料对原子性以及 COMMIT/ROLLBACK 作用的说明？

A. 该事务是原子的：在没有 COMMIT 的情况下，任何已执行的更新都不会生效；若改为发出 ROLLBACK，此前所有更新也会被取消。

B. 只有“向 Bob 账户贷记 100”会保留下来，因为它是事务中最后执行的一句。

C. 两条更新会立即生效并永久保存，因为 PostgreSQL 会把每条 SQL 语句各自当作一个事务并自动 COMMIT。

D. 由于已经执行了至少一条更新，事务完成后必然把两条更新都写入磁盘，只有 ROLLBACK 才能阻止第二条生效。

**参考答案**

A

**答案解释**

资料把事务描述为把多个步骤捆绑成单一的全有或全无操作，中途失败时已执行的步骤都不影响数据库，这正是选项 A 的表述。
B 错在“最后一条语句保留”：原子性不允许只保留部分更新，故障时已执行的更新都不生效。
C 错在把 BEGIN 事务块的整组语句说成每条都立即生效并自动提交；资料说的是未发出 BEGIN 时，每条单独语句才被隐式 BEGIN 与 COMMIT 包裹，而此处事务由 BEGIN 开始且尚未提交。
D 错在“必然写入磁盘”：资料说明只有事务完成并被确认后才保证永久记录，且 ROLLBACK 会取消此前所有更新，而不是只阻止第二条生效。

**题目引用的来源**

### db_atomicity.md · context_5272194b24cbab69fac1132aab4c49e3

3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.

### db_atomicity.md · context_061768d877b186a640e491e8ef69d909

In PostgreSQL, a transaction is set up by surrounding the SQL commands of the transaction with BEGIN and COMMIT commands. So our banking transaction would actually look like:

If, partway through the transaction, we decide we do not want to commit (perhaps we just noticed that Alice's balance went negative), we can issue the command ROLLBACK instead of COMMIT, and all our updates so far will be canceled.

PostgreSQL actually treats every SQL statement as being executed within a transaction. If you do not issue a BEGIN command, then each individual statement has an implicit BEGIN and (if successful) COMMIT wrapped around it. A group of statements surrounded by BEGIN and COMMIT is sometimes called a transaction block.

It's possible to control the statements in a transaction in a more granular fashion through the use of savepoints. Savepoints allow you to selectively discard parts of the transaction, while committing the rest. After defining a savepoint with SAVEPOINT, you can if needed roll back to the savepoint with ROLLBACK TO. All the transaction's database changes between defining the savepoint and rolling back to it are discarded, but changes earlier than the savepoint are kept.

### db_atomicity.md · context_92433ce91f957a3ac489c075dad91e1f

We also want a guarantee that once a transaction is completed and acknowledged by the database system, it has indeed been permanently recorded and won't be lost even if a crash ensues shortly thereafter. For example, if we are recording a cash withdrawal by Bob, we do not want any chance that the debit to his account will disappear in a crash just after he walks out the bank door. A transactional database guarantees that all the updates made by a transaction are logged in permanent storage (i.e., on disk) before the transaction is reported complete.

Another important property of transactional databases is closely related to the notion of atomic updates: when multiple transactions are running concurrently, each one should not be able to see the incomplete changes made by others. For example, if one transaction is busy totalling all the branch balances, it would not do for it to include the debit from Alice's branch but not the credit to Bob's branch, nor vice versa. So transactions must be all-or-nothing not only in terms of their permanent effect on the database, but also in terms of their visibility as they happen. The updates made so far by an open transaction are invisible to other transactions until the transaction completes, whereupon all the updates become visible simultaneously.

### db_atomicity.md · context_6f8d6b6c0cf24e5f381c70638f7570a3

After rolling back to a savepoint, it continues to be defined, so you can roll back to it several times. Conversely, if you are sure you won't need to roll back to a particular savepoint again, it can be released, so the system can free some resources. Keep in mind that either releasing or rolling back to a savepoint will automatically release all savepoints that were defined after it.

All this is happening within the transaction block, so none of it is visible to other database sessions. When and if you commit the transaction block, the committed actions become visible as a unit to other sessions, while the rolled-back actions never become visible at all.
