# Blind accepted-question review packet

Rate each item from its source and student-visible question. Do not use the product gate verdict.

## e0a3dd2cca57

Focus: why retrying only one statement is insufficient

Question: The assigned excerpt describes PostgreSQL's Serializable isolation level.

According to that excerpt:
1. Serializable emulates serial execution for all committed transactions.
2. Applications using this level must be prepared to retry transactions due to serialization failures.
3. The level works exactly the same as Repeatable Read, except that it additionally monitors for conditions that could make concurrent execution inconsistent with all possible serial executions.
4. The monitoring adds overhead but no blocking beyond Repeatable Read, and detecting a serialization anomaly triggers a serialization failure.

A developer argues: "If a serialization failure occurs, I can just retry the single SQL statement that failed; there is no need to repeat the whole transaction." Using only the supplied excerpt, explain why that argument is incorrect.

Answer: The excerpt states that applications using Serializable must be prepared to retry transactions due to serialization failures. A serialization failure signals that the concurrent set of transactions may have behaved inconsistently with every possible serial order. Because the Serializable level provides a guarantee over committed transactions as a group and does not add blocking beyond Repeatable Read, the database cannot let the transaction continue as if nothing happened. Retrying only one statement would leave the rest of the transaction's earlier reads and writes in place and would not re-establish the serializable guarantee for the whole transaction. Therefore, the failure must be handled by retrying the transaction as a unit, not just the single statement.

Explanation: The excerpt states the retry requirement at the transaction level, not the statement level. A serialization failure is triggered when the monitoring detects conditions that could make the concurrent execution inconsistent with all possible serial executions. Since Serializable must emulate serial execution for committed transactions and adds no blocking beyond Repeatable Read, the only way to restore that guarantee after such a failure is to retry the transaction as a unit. Retrying one statement would keep prior reads and writes of the same transaction, so the transaction's result could still be inconsistent with any serial order.

Source scale-db_retry (PostgreSQL 18: Serializable transactions and retry handling):
13.2.3. Serializable Isolation Level #

The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. In fact, this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure.


## 03491827cb1d

Focus: a critical section and its invariant

Question: Excerpt (xv6: Races, critical sections, and atomic lock acquisition):
"Most kernels, including xv6, interleave the execution of multiple activities. One source of interleaving is multiprocessor hardware: computers with multiple CPUs executing independently, such as xv6's RISC-V. These multiple CPUs share physical RAM, and xv6 exploits the sharing to maintain kernel data structures that all CPUs read and write. This sharing raises the possibility of one CPU reading a data structure while another CPU is mid-way through updating it, or even multiple CPUs updating the same data simultaneously; without careful design such parallel access is likely to yield incorrect results or a broken data structure. Even on a uniprocessor, the kernel may switch the CPU among a number of threads, causing their execution to be interleaved. Finally, a device interrupt handler that modifies the same data as some interruptible code could damage the data if the interrupt occurs just as the interrupted code is also modifying the data. The word concurrency refers to situations in which multiple instruction streams are interleaved, due to multiprocessor parallelism, thread switching, or interrupts."

Using only the excerpt, explain what a critical section is in this context and what invariant it must protect. Give one concrete example from the excerpt of code that should be in a critical section, and state what could go wrong in that example if the invariant is not maintained.

Answer in 3–5 sentences.

Answer: A critical section here is the region of kernel code that reads or updates a shared kernel data structure (for example, a lock-protected update that multiple CPUs, threads, or an interrupt handler may access concurrently). The invariant it must protect is that no other instruction stream can observe or modify the shared data structure while it is mid-update, so the structure is always in a consistent state as seen by any reader or writer.

One concrete example from the excerpt: a CPU is mid-way through updating a kernel data structure that another CPU also reads and writes, or an interrupt handler runs while the interrupted code is modifying the same data. If the invariant is not maintained, the excerpt says parallel access is likely to yield incorrect results or a broken data structure.

Explanation: Recognize the critical section: the interleaving described by the excerpt (multiprocessor parallelism, thread switching, or interrupts) means shared kernel data can be read or written concurrently, so code that touches that data must be protected as a critical section.

State the invariant: while one stream is updating the shared structure, no other stream should see or alter it mid-update, so readers and writers always find a consistent state.

Give a concrete example: the excerpt's case of one CPU reading while another is mid-way through updating the same structure, or an interrupt handler modifying data that interruptible code is also modifying.

State the failure: without careful design the excerpt says parallel access is likely to produce incorrect results or a broken data structure.

Source scale-os_races (xv6: Races, critical sections, and atomic lock acquisition):
Most kernels, including xv6, interleave the execution of multiple activities. One source of interleaving is multiprocessor hardware: computers with multiple CPUs executing independently, such as xv6’s RISC-V. These multiple CPUs share physical RAM, and xv6 exploits the sharing to maintain kernel data structures that all CPUs read and write. This sharing raises the possibility of one CPU reading a data structure while another CPU is mid-way through updating it, or even multiple CPUs updating the same data simultaneously; without careful design such parallel access is likely to yield incorrect results or a broken data structure. Even on a uniprocessor, the kernel may switch the CPU among a number of threads, causing their execution to be interleaved. Finally, a device interrupt handler that modifies the same data as some interruptible code could damage the data if the interrupt occurs just as the interrupted code is also modifying the data. The word concurrency refers to situations in which multiple instruction streams are interleaved, due to multiprocessor parallelism, thread switching, or interrupts.


## 1eee6e801ca9

Focus: a critical section and its invariant

Question: Course excerpt (xv6: Races, critical sections, and atomic lock acquisition):
"Most kernels, including xv6, interleave the execution of multiple activities. One source of interleaving is multiprocessor hardware: computers with multiple CPUs executing independently, such as xv6's RISC-V. These multiple CPUs share physical RAM, and xv6 exploits the sharing to maintain kernel data structures that all CPUs read and write. This sharing raises the possibility of one CPU reading a data structure while another CPU is mid-way through updating it, or even multiple CPUs updating the same data simultaneously; without careful design such parallel access is likely to yield incorrect results or a broken data structure. Even on a uniprocessor, the kernel may switch the CPU among a number of threads, causing their execution to be interleaved. Finally, a device interrupt handler that modifies the same data as some interruptible code could damage the data if the interrupt occurs just as the interrupted code is also modifying the data. The word concurrency refers to situations in which multiple instruction streams are interleaved, due to multiprocessor parallelism, thread switching, or interrupts."

A kernel keeps an integer counter in shared RAM. Two CPUs run kernel code at the same time, and each CPU executes the code shown below, where the counter is read into a register, the register is incremented, and the register is written back to memory.

```
load  counter -> r
add   r, 1
store r -> counter
```

1. The counter's initial value is 10.
2. Both CPUs execute this same three-instruction sequence exactly once.
3. Execution may be interleaved at instruction boundaries, and no other code reads or writes the counter.

Question: Explain what a critical section is and what invariant the code above is intended to maintain, then use the interleaving above to explain why the final value of the counter can be 11 instead of 12.

Answer: A critical section is a region of code that accesses shared data (like the counter) and must be executed by at most one instruction stream at a time, so interleaved accesses cannot corrupt the data. The intended invariant of the code above is that each complete execution of the load/add/store sequence increases the counter by exactly 1, so two complete executions must leave the counter at 12. If the two CPUs interleave their accesses, both may load the same old value 10 before either stores. Each then increments its own register to 11 and writes 11 back. The store of one CPU overwrites the store of the other, so one increment is lost and the final value is 11 instead of 12.

Explanation: Reading and updating the counter is a read-modify-write sequence, so the shared counter must be protected as a critical section: only one instruction stream should be inside the sequence at a time. The invariant is that each full sequence adds 1; two full sequences should give 12. But interleaving lets both CPUs load 10, both compute 11, and both store 11, producing an 11 rather than 12 and showing why unprotected concurrent access can yield incorrect results.

Source scale-os_races (xv6: Races, critical sections, and atomic lock acquisition):
Most kernels, including xv6, interleave the execution of multiple activities. One source of interleaving is multiprocessor hardware: computers with multiple CPUs executing independently, such as xv6’s RISC-V. These multiple CPUs share physical RAM, and xv6 exploits the sharing to maintain kernel data structures that all CPUs read and write. This sharing raises the possibility of one CPU reading a data structure while another CPU is mid-way through updating it, or even multiple CPUs updating the same data simultaneously; without careful design such parallel access is likely to yield incorrect results or a broken data structure. Even on a uniprocessor, the kernel may switch the CPU among a number of threads, causing their execution to be interleaved. Finally, a device interrupt handler that modifies the same data as some interruptible code could damage the data if the interrupt occurs just as the interrupted code is also modifying the data. The word concurrency refers to situations in which multiple instruction streams are interleaved, due to multiprocessor parallelism, thread switching, or interrupts.


## 24f305d77af4

Focus: local interrupt handling while holding a lock

Question: A system has two locks, A and B. Two functions run on CPUs C1 and C2. Each function has a point at which it needs to hold both locks, but they acquire them in different orders.

1. C1 acquires A, then tries to acquire B.
2. C2 acquires B, then tries to acquire A.
3. Both CPUs happen to execute their first acquire at exactly the same moment, and both first acquires succeed.

According to the excerpt, what is this situation called, and what is the general rule that locking code must follow to avoid it?

Answer in 2–3 sentences.

Answer: This situation is called deadlock. Both CPUs are waiting for each other, so neither will ever release a lock and both will wait forever. The general rule is that all code paths that hold multiple locks must acquire locks in the same order.

Explanation: Both CPUs acquired their first lock successfully because they asked for different locks, but then each waited on the lock the other held. Since neither can proceed or release, both wait forever — this is deadlock. The excerpt's rule is that all code paths that hold multiple locks must acquire locks in the same order.

Source scale-os_interrupt_locks (xv6: Lock ordering and interrupts):
7.4 Deadlock and lock ordering

Suppose the functions running on CPUs C1 and C2 both have a point at which each needs to hold both lock A and lock B, and they acquire them in different orders:

With a bit of bad luck, C1 and C2 might both execute their first acquire at exactly the same moment; both can succeed, since they are asking for different locks. But then both C1 and C2 will have to wait in their second calls to acquire(), since both locks are already held by the other CPU. Because both CPUs are waiting for each other, neither will ever release a lock, and both will wait forever. This situation is called deadlock.

The key problem in the C1/C2 example is that the two CPUs acquired the locks in different orders. If they had both tried to acquire A first, one would have acquired A and then B and then released them both, and then the other CPU could have proceeded. More generally, locking code must follow this rule to avoid deadlock: all code paths that hold multiple locks must acquire locks in the same order. The need for this global lock acquisition order means that locks are effectively part of each function’s specification: callers must invoke functions in a way that causes locks to be acquired in the agreed-on order.


## 397a6c53a800

Focus: the role of wakeup in producer-consumer coordination

Question: Background: The xv6 kernel needs a way for threads to intentionally interact when one must wait for another. The assigned excerpt says:

"Sleep allows a kernel thread to wait for some condition to be true; another thread or an interrupt handler can cause the condition to be true (typically by modifying some variable(s)) and then call wakeup to indicate that threads waiting for the condition should resume. Sleep and wakeup are often called sequence coordination or conditional synchronization mechanisms."

Scenario: A process is blocked in sleep while reading from a pipe, waiting for a writer to produce data.

Using only the excerpt above, answer the following:
1. After the writer causes the condition (data available) to become true, which mechanism must the writer call, and what does that call indicate?
2. What is the name given to this pair of mechanisms, and why is it needed here?

Answer: 1. The writer calls wakeup, which indicates that threads waiting for the condition (data available) should resume.

2. The pair is called sequence coordination or conditional synchronization. It is needed because sleep alone only lets a thread wait for a condition; another thread (the writer) must modify the variable(s) making the condition true and then call wakeup so the waiting reader can resume.

Explanation: The excerpt states that sleep lets a kernel thread wait for a condition to be true, and that another thread or an interrupt handler can make the condition true and then call wakeup to indicate that waiting threads should resume.

It also names sleep and wakeup as sequence coordination or conditional synchronization mechanisms.

In the pipe scenario, the reader sleeps waiting for data; the writer produces data and calls wakeup so the waiting reader resumes.

Both required answer parts — the call and the term — come directly from the excerpt.

Source scale-os_wakeup (xv6: Condition synchronization and lost wakeups):
Scheduling and locks help conceal the actions of one thread from another, but we also need abstractions that help threads intentionally interact. For example, the reader of a pipe in xv6 may need to wait for a writing process to produce data; a parent’s call to wait may need to wait for a child to exit; and a process reading the disk needs to wait for the disk hardware to finish the read. The xv6 kernel uses a mechanism called sleep and wakeup in these situations (and many others). Sleep allows a kernel thread to wait for some condition to be true; another thread or an interrupt handler can cause the condition to be true (typically by modifying some variable(s)) and then call wakeup to indicate that threads waiting for the condition should resume. Sleep and wakeup are often called sequence coordination or conditional synchronization mechanisms.

9.1 Overview


## 6ac06ca13c5f

Focus: transaction atomicity

Question: The excerpt below describes database transactions and atomicity.

Excerpt (scale-db_atomicity):
"Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all. ... A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all."

Scenario: A bank transfer from Alice to Bob involves several separate updates. Bob must receive $100.00 only if that same $100.00 is debited from Alice.

Using the excerpt, explain what it means for this transaction to be atomic.

In your answer, state:
1. how other transactions see the grouped updates, and
2. what happens to the steps already executed if a failure prevents the transaction from completing.

Answer: A transaction is atomic when it bundles multiple steps into a single, all-or-nothing operation: from the point of view of other transactions, it either happens completely or not at all.

1. Other concurrent transactions cannot see the intermediate states between the steps; they only see the transaction as fully done or not done.

2. If a failure prevents the transaction from completing, none of the steps executed so far take effect on the database.

Explanation: The excerpt defines a transaction as bundling multiple steps into a single, all-or-nothing operation. It states that intermediate states between steps are not visible to other concurrent transactions, and that if a failure prevents completion, none of the steps affect the database. A transaction is therefore atomic: it either happens completely or not at all.

Scoring guidance:
- Award credit for correctly stating the all-or-nothing behaviour or invisibility of intermediate states to other transactions.
- Award credit for correctly stating that on failure, none of the already-executed steps take effect.
- No credit for answers that claim partial updates are visible or that completed steps persist after a failure.

Source scale-db_atomicity (PostgreSQL 18: Transactions and atomicity):
3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.


## fc5b4078893d

Focus: buffer space and advertised window

Question: A student is asked about how TCP keeps a fast sender from overrunning a slow receiver.

Use the following excerpt from the assigned reading.

"It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time."

In one or two sentences, explain what role the receiver's buffer space plays in TCP's flow-control mechanism, and state what the advertised window tells the sender to do.

Base your answer only on the excerpt above.

Answer: The receiver's buffer space holds incoming data that the application has not yet consumed, and it is what limits how much data the sender may transmit at a given time. The advertised window conveys that limit to the sender, telling the sender the amount of data it is currently permitted to send.

Explanation: The excerpt states that TCP includes a flow-control mechanism for each byte stream that allows the receiver to limit how much data the sender can transmit at a given time. The receiver's buffer space is the resource that sets this limit, and the advertised window is how that limit is communicated to the sender. Therefore, buffer space determines the permitted amount of in-flight data, and the advertised window tells the sender to send no more than that amount.

Source scale-net_windows (Computer Networks: A Systems Approach — Flow and congestion control):
In terms of the properties of transport protocols given in the problem statement at the start of this chapter, TCP guarantees the reliable, in-order delivery of a stream of bytes. It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time. Finally, like UDP, TCP supports a demultiplexing mechanism that allows multiple application programs on any given host to simultaneously carry on a conversation with their peers.

In addition to the above features, TCP also implements a highly tuned congestion-control mechanism. The idea of this mechanism is to throttle how fast TCP sends data, not for the sake of keeping the sender from over-running the receiver, but so as to keep the sender from overloading the network. A description of TCP’s congestion-control mechanism is postponed until the next chapter, where we discuss it in the larger context of how network resources are fairly allocated.


## 579efa7bb984

Focus: the effect of COMMIT

Question: A bank transfer bundles several separate updates: $100.00 is debited from Alice's account, then $100.00 is credited to Bob's account. The updates are grouped into one transaction, and the transaction executes COMMIT after both updates succeed.

Required excerpt: "The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all."

Question: Using only the excerpt above, explain what effect the COMMIT has on what other concurrent transactions can observe about the transfer.

Answer: The excerpt states that a transaction bundles its steps into a single all-or-nothing operation, and that the intermediate states between the steps are not visible to other concurrent transactions. COMMIT therefore makes the transaction's effects take effect as a completed unit: other concurrent transactions observe the transfer as a whole (the debit and the credit together), never the partial intermediate state in which Alice has been debited but Bob has not yet been credited.

Explanation: The excerpt gives two linked claims. First, the intermediate states between the steps of a transaction are not visible to other concurrent transactions; second, the operation is all-or-nothing. COMMIT is the point that ends the all-or-nothing grouping, so the completed result becomes the observable outcome for other concurrent transactions.

Source scale-db_atomicity (PostgreSQL 18: Transactions and atomicity):
3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.


## fba55221d483

Focus: the role of timer interrupts in CPU sharing

Question: The excerpt below describes how xv6 multiplexes CPUs among processes.

"Xv6 multiplexes by switching each CPU from one process to another in two situations. First, xv6 switches when a process makes a system call that blocks (has to wait), for example read or wait. Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. The former are called voluntary switches, the latter involuntary."

Using this excerpt, explain what xv6 relies on to make the involuntary switch happen.

In your answer:
1. Name the category (voluntary or involuntary) that applies when a process blocks in a system call like read or wait.
2. Explain why the periodic forced switch exists, based on the excerpt.
3. State what triggers the periodic forced switch.

Answer: 1. A process that blocks in a system call such as read or wait causes a voluntary switch.
2. The periodic forced switch exists to cope with processes that compute for long periods without blocking, so that such a CPU-bound process cannot keep a CPU indefinitely.
3. The periodic forced switch is triggered by a timer interrupt, which is how xv6 "periodically forces a switch" as described in the excerpt.

Explanation: The excerpt distinguishes two switching situations. Blocking calls (read, wait) produce voluntary switches, because the process itself gives up the CPU while it waits. To cope with processes that compute for long periods without blocking, xv6 periodically forces a switch; these forced switches are the involuntary ones, and the mechanism that makes them happen periodically is the timer interrupt.

Scoring points:
1. Correctly label the blocking-call case as voluntary.
2. State that the forced switch targets CPU-bound processes that do not block.
3. Identify the periodic trigger as the timer interrupt.

Source scale-os_context (xv6: CPU multiplexing and context switching):
Any operating system is likely to run with more processes than the computer has CPUs, so a plan is needed to time-share the CPUs among the processes. Ideally the sharing would be transparent to user processes. A common approach is to provide each process with the illusion that it has its own virtual CPU by multiplexing the processes onto the hardware CPUs. This chapter explains how xv6 achieves this multiplexing.

8.1 Multiplexing

Xv6 multiplexes by switching each CPU from one process to another in two situations. First, xv6 switches when a process makes a system call that blocks (has to wait), for example read or wait. Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. The former are called voluntary switches, the latter involuntary.


## 048cf1dd1c86

Focus: the effect of COMMIT

Question: A bank transfers $100 from Alice to Bob. The transfer is grouped into a single database transaction consisting of the two updates: debit Alice's account by $100, then credit Bob's account by $100.

1. The transaction performs the debit of Alice's account and then the credit of Bob's account.
2. Both updates complete, and the transaction is then committed (COMMIT succeeds).
3. A system failure occurs immediately after the COMMIT succeeds.

From the point of view of other concurrent transactions, what is the effect of the committed transaction, and what does the excerpt guarantee if a failure had occurred partway through before the COMMIT?

Answer in 1–3 sentences.

Answer: The committed transaction is treated as atomic: from the point of view of other transactions it happens completely, so both the $100 debit of Alice and the $100 credit of Bob are visible and take effect. If a failure had occurred partway through before the COMMIT, none of the steps executed so far would take effect, so Alice would not be debited and Bob would not be credited.

Explanation: The excerpt states that a transaction bundles multiple steps into a single, all-or-nothing operation.

It states that a transaction is atomic: from the point of view of other transactions, it either happens completely or not at all.

It also states that if a failure prevents the transaction from completing, none of the steps affect the database at all.

Therefore, once COMMIT succeeds, both updates take effect; if a failure occurs before completion, neither update takes effect.

Source scale-db_atomicity (PostgreSQL 18: Transactions and atomicity):
3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.

