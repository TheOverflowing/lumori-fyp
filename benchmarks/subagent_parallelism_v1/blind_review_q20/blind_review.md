# Blind accepted-question review packet

Rate each item from its source and student-visible question. Do not use the product gate verdict.

## 783df20cd683

Focus: the Repeatable Read transaction snapshot

Question: Consider a database using the Repeatable Read isolation level, as described in the excerpt below.

Excerpt (scale-db_repeatable_read): "The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.)" The excerpt also states that a query sees "a snapshot as of the start of the first non-transaction-control statement in the transaction" and that "successive SELECT commands within a single transaction see the same data."

Using only this excerpt, explain what data a transaction running at Repeatable Read can and cannot see during its execution, and state what the snapshot is taken relative to.

Answer: A Repeatable Read transaction sees only data committed before the transaction began.
It never sees uncommitted data or changes committed by concurrent transactions during its execution.
Each query does see effects of previous updates made within its own transaction, even if those updates are not yet committed.
The snapshot is taken as of the start of the first non-transaction-control statement in the transaction, so successive SELECT commands see the same data.

Explanation: The reference answer restates the excerpt's definition of the Repeatable Read snapshot: it sees pre-transaction committed data only, ignores other transactions' concurrent changes and uncommitted data, reflects its own transaction's earlier updates, and takes its snapshot at the first non-transaction-control statement so consecutive SELECTs are consistent.

Source scale-db_repeatable_read (PostgreSQL 18: Repeatable Read and snapshot isolation):
13.2.2. Repeatable Read Isolation Level #

The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) This is a stronger guarantee than is required by the SQL standard for this isolation level, and prevents all of the phenomena described in Table 13.1 except for serialization anomalies. As mentioned above, this is specifically allowed by the standard, which only describes the minimum protections each isolation level must provide.

This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started.

Applications using this level must be prepared to retry transactions due to serialization failures.


## 9802e6564bba

Focus: voluntary versus timer-driven process switches

Question: Consider the xv6 excerpt on CPU multiplexing: xv6 switches each CPU from one process to another in two situations. First, a process makes a system call that blocks (for example, read or wait). Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. The first type is called a voluntary switch, the second an involuntary switch.

A running process, P, executes on a single CPU. It is currently doing a long computation with no system calls.

1. Name the type of switch (voluntary or involuntary) that matches each of the two situations described in the excerpt.
2. For each situation, describe when the switch occurs.
3. For a process like P that never blocks, which of the two switches must the operating system rely on, and why does the other type never occur?

Explain in terms of the excerpt.

Answer: 1. A switch caused by a process making a blocking system call (for example, read or wait) is a voluntary switch. A switch forced periodically to cope with a process that computes for a long time without blocking is an involuntary switch.

2. The voluntary switch occurs when the process itself requests an operation that must wait, such as a blocking read or wait. The involuntary switch occurs periodically, forced by xv6 on a timer-like basis, not requested by the process.

3. For a process like P that never blocks, the operating system must rely on the involuntary (periodic, forced) switch, because P never makes a blocking system call, so the voluntary condition never arises.

Explanation: The excerpt distinguishes the two cases by cause: voluntary switches happen when a process blocks inside a system call such as read or wait, while involuntary ones are forced periodically for processes that compute without blocking.

Applied to the scenario: P makes no blocking calls, so the voluntary trigger is never present. Only the periodic forced switch can take the CPU away from P.

Source scale-os_context (xv6: CPU multiplexing and context switching):
Any operating system is likely to run with more processes than the computer has CPUs, so a plan is needed to time-share the CPUs among the processes. Ideally the sharing would be transparent to user processes. A common approach is to provide each process with the illusion that it has its own virtual CPU by multiplexing the processes onto the hardware CPUs. This chapter explains how xv6 achieves this multiplexing.

8.1 Multiplexing

Xv6 multiplexes by switching each CPU from one process to another in two situations. First, xv6 switches when a process makes a system call that blocks (has to wait), for example read or wait. Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. The former are called voluntary switches, the latter involuntary.


## f514b938ca62

Focus: voluntary versus timer-driven process switches

Question: A student is learning how xv6 multiplexes processes onto CPUs.

Consider only these two processes on a single CPU:
1. Process P calls read and blocks because it must wait for data.
2. Process Q computes for a long period without blocking or making any system call.

xv6 uses two situations to switch each CPU from one process to another: one switch type is caused by a process making a system call that blocks, and the other is forced periodically to cope with processes that compute for long periods without blocking.

Based on the excerpt, name the two types of process switches, and match each type to either P or Q.

Answer: Voluntary switch: xv6 switches when a process makes a system call that blocks (has to wait), such as read or wait. This applies to P, because P calls read and blocks.

Involuntary switch: xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. This applies to Q, because Q computes for a long period without blocking or making a system call.

Explanation: The excerpt states xv6 multiplexes by switching each CPU from one process to another in two situations.

First, xv6 switches when a process makes a system call that blocks (has to wait), for example read or wait; these are voluntary switches.

Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking; these are involuntary switches.

P blocks in read, so its switch is voluntary. Q computes for a long period without blocking, so the periodic forced switch applies to Q.

Source scale-os_context (xv6: CPU multiplexing and context switching):
Any operating system is likely to run with more processes than the computer has CPUs, so a plan is needed to time-share the CPUs among the processes. Ideally the sharing would be transparent to user processes. A common approach is to provide each process with the illusion that it has its own virtual CPU by multiplexing the processes onto the hardware CPUs. This chapter explains how xv6 achieves this multiplexing.

8.1 Multiplexing

Xv6 multiplexes by switching each CPU from one process to another in two situations. First, xv6 switches when a process makes a system call that blocks (has to wait), for example read or wait. Second, xv6 periodically forces a switch to cope with processes that compute for long periods without blocking. The former are called voluntary switches, the latter involuntary.


## fb4dde2546fa

Focus: a complete transaction retry

Question: A developer team runs its transactions at the Serializable isolation level because the application must behave as if transactions executed serially.

Source excerpt (PostgreSQL 18):

"The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. In fact, this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure."

Question: According to this excerpt, what must an application using the Serializable isolation level be prepared to do, and what triggers the need for that action?

Answer: The application must be prepared to retry transactions due to serialization failures. The trigger is detection of conditions that could make a concurrent set of serializable transactions behave inconsistently with all possible serial executions of those transactions, which produces a serialization failure.

Explanation: The excerpt states applications using Serializable must be prepared to retry transactions due to serialization failures. It also explains why: the level monitors for conditions that could make concurrent execution inconsistent with every possible serial execution. When such conditions are detected — a potential serialization anomaly — a serialization failure is triggered, and the application should retry.

Source scale-db_retry (PostgreSQL 18: Serializable transactions and retry handling):
13.2.3. Serializable Isolation Level #

The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. In fact, this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure.


## 89af85329134

Focus: the condition checked before sleeping

Question: Read the following excerpt from the course material on xv6 condition synchronization:

"The xv6 kernel uses a mechanism called sleep and wakeup in these situations (and many others). Sleep allows a kernel thread to wait for some condition to be true; another thread or an interrupt handler can cause the condition to be true (typically by modifying some variable(s)) and then call wakeup to indicate that threads waiting for the condition should resume."

Background: A student is writing a kernel routine in which a thread must wait until a shared buffer contains data before it may proceed.

Based on the excerpt, answer the following in 1–2 sentences.

1. Before calling sleep, what must the thread verify about the condition it is waiting for?
2. Why is this check necessary before sleeping rather than after waking up?

Answer: Before calling sleep, the thread must verify that the condition it is waiting for is not already true (for example, that the shared buffer does not already contain data). The condition is a predicate on shared variables that another thread or an interrupt handler makes true, so if it were already true when the thread decided to sleep, the thread would wait unnecessarily; sleep is only appropriate when the condition is currently false and must be made true by another thread or an interrupt handler calling wakeup.

Explanation: The excerpt states that sleep allows a kernel thread to wait for some condition to be true, and that another thread or an interrupt handler causes the condition to be true (typically by modifying variables) and then calls wakeup. Therefore, the thread must test the condition before sleeping to confirm it is not already satisfied; otherwise, the pending wakeup event may already have occurred, and the thread would block even though no future wakeup is guaranteed. This check ties the decision to sleep to the actual state of the shared variables described in the excerpt.

Source scale-os_wakeup (xv6: Condition synchronization and lost wakeups):
Scheduling and locks help conceal the actions of one thread from another, but we also need abstractions that help threads intentionally interact. For example, the reader of a pipe in xv6 may need to wait for a writing process to produce data; a parent’s call to wait may need to wait for a child to exit; and a process reading the disk needs to wait for the disk hardware to finish the read. The xv6 kernel uses a mechanism called sleep and wakeup in these situations (and many others). Sleep allows a kernel thread to wait for some condition to be true; another thread or an interrupt handler can cause the condition to be true (typically by modifying some variable(s)) and then call wakeup to indicate that threads waiting for the condition should resume. Sleep and wakeup are often called sequence coordination or conditional synchronization mechanisms.

9.1 Overview


## c67bb28e74f9

Focus: the Repeatable Read transaction snapshot

Question: Consider the following excerpt from the PostgreSQL documentation on the Repeatable Read isolation level:

"The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) ... This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction."

1. According to the excerpt, what snapshot does a query in a Repeatable Read transaction see?
2. Why do successive SELECT commands within the same Repeatable Read transaction see the same data?

Answer: 1. A query in a Repeatable Read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction.
2. Because the snapshot is taken at the start of the first non-transaction-control statement, successive SELECT commands see the same data: they do not see changes made by other transactions that committed after their own transaction started.

Explanation: The excerpt states that Repeatable Read sees only data committed before the transaction began and cannot see uncommitted data or changes committed by concurrent transactions during execution.

Although each query sees its own transaction's uncommitted updates, the snapshot for query visibility is fixed at the start of the first non-transaction-control statement.

Therefore successive SELECT commands within the same transaction see the same data, because they all use that same snapshot and do not reflect changes committed by other transactions after the transaction started.

Source scale-db_repeatable_read (PostgreSQL 18: Repeatable Read and snapshot isolation):
13.2.2. Repeatable Read Isolation Level #

The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) This is a stronger guarantee than is required by the SQL standard for this isolation level, and prevents all of the phenomena described in Table 13.1 except for serialization anomalies. As mentioned above, this is specifically allowed by the standard, which only describes the minimum protections each isolation level must provide.

This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started.

Applications using this level must be prepared to retry transactions due to serialization failures.


## 0c3f9e9c2425

Focus: a serialization failure

Question: A database application sets the Serializable isolation level for a transaction. While the transaction runs, the database detects conditions that could make concurrent execution behave inconsistently with any possible one-at-a-time (serial) execution of the transactions.

According to the course excerpt, what will happen to the transaction, and what must the application be prepared to do as a result?

Answer: The detection of conditions that could make a concurrent set of serializable transactions behave inconsistently with all possible serial executions will trigger a serialization failure. Because of this, the application must be prepared to retry the transaction.

Explanation: The excerpt states that the Serializable level emulates serial execution for all committed transactions, as if they had run one after another rather than concurrently.
It monitors for conditions that could make concurrent serializable transactions behave inconsistently with all possible serial executions.
When such conditions are detected, a serialization failure is triggered.
The excerpt also says applications using this level must be prepared to retry transactions due to serialization failures.
So the correct response has two parts: a serialization failure is triggered, and the application must be ready to retry the transaction.

Source scale-db_retry (PostgreSQL 18: Serializable transactions and retry handling):
13.2.3. Serializable Isolation Level #

The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. In fact, this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure.


## fe04a574cf6c

Focus: the Repeatable Read transaction snapshot

Question: The following is from the assigned PostgreSQL 18 course excerpt on the Repeatable Read isolation level:

"The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) ... A query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started."

Question:
A transaction T1 running at Repeatable Read begins and then executes SELECT twice, with a large gap between the two SELECTs. During the gap, a different transaction T2 commits a change to a row. Explain what each SELECT of T1 sees and identify the exact point that fixes the snapshot.

Answer: Both SELECTs of T1 see the same snapshot, which is taken at the start of the first non-transaction-control statement in T1 (i.e., at the first SELECT), not at the start of each individual statement. Because T2 commits during the gap after T1's snapshot was fixed, T1 does not see T2's change in the second SELECT. T1 also does not see any uncommitted data, but it does see the effects of updates it previously performed within T1 itself, even though those are not yet committed.

Explanation: Under Repeatable Read, the snapshot is fixed at the start of the first non-transaction-control statement, so subsequent statements in the same transaction reuse that snapshot instead of refreshing it. This makes successive SELECT commands in T1 return the same data even though T2 committed a change between them. The key distinctions are: data committed before T1 began is visible; uncommitted or concurrently committed data outside T1's snapshot is not; and T1's own previous updates are visible to its own later queries even before T1 commits.

Source scale-db_repeatable_read (PostgreSQL 18: Repeatable Read and snapshot isolation):
13.2.2. Repeatable Read Isolation Level #

The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) This is a stronger guarantee than is required by the SQL standard for this isolation level, and prevents all of the phenomena described in Table 13.1 except for serialization anomalies. As mentioned above, this is specifically allowed by the standard, which only describes the minimum protections each isolation level must provide.

This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started.

Applications using this level must be prepared to retry transactions due to serialization failures.


## c01269e9fe41

Focus: visibility of a concurrent committed update

Question: The following excerpt from the course material (scale-db_read_committed) describes PostgreSQL's Read Committed isolation level:

"Read Committed is the default isolation level in PostgreSQL. When a transaction uses this isolation level, a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution. In effect, a SELECT query sees a snapshot of the database as of the instant the query begins to run. However, SELECT does see the effects of previous updates executed within its own transaction, even though they are not yet committed. Also note that two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts."

Scenario: Transaction T1 begins at time t0 using Read Committed. At time t1 (with t1 > t0), T1 issues its first SELECT query. While T1's first SELECT is still executing, another transaction T2 commits an update to a row that T1's first SELECT will examine.

1. Does T1's first SELECT see T2's committed update? Explain why, citing the snapshot rule from the excerpt.
2. Suppose T1 later issues a second SELECT in the same transaction, after T2 has committed. Does this second SELECT see T2's committed update? Explain using the excerpt's statement about successive SELECT commands.

Answer: 1. No, T1's first SELECT does not see T2's committed update. Per the excerpt, a SELECT under Read Committed "sees only data committed before the query began" and "never sees either uncommitted data or changes committed by concurrent transactions during the query's execution." Since T2 committed while T1's first SELECT was still executing, the update is not part of the snapshot taken at the instant the query began.

2. Yes, T1's second SELECT can see T2's committed update. The excerpt states that "two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts." T2's commit occurred before the second SELECT started, so it is included in the new snapshot taken when the second SELECT began.

Explanation: Read Committed takes a new snapshot at the start of each SELECT query. The first SELECT's snapshot was taken at t1, before T2 committed, so T2's update is invisible to it. The second SELECT starts after T2 committed, so its snapshot includes T2's update, which is why successive SELECTs in the same transaction can see different data.

Source scale-db_read_committed (PostgreSQL 18: Read Committed statement snapshots):
13.2.1. Read Committed Isolation Level #

Read Committed is the default isolation level in PostgreSQL. When a transaction uses this isolation level, a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution. In effect, a SELECT query sees a snapshot of the database as of the instant the query begins to run. However, SELECT does see the effects of previous updates executed within its own transaction, even though they are not yet committed. Also note that two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts.

Because Read Committed mode starts each command with a new snapshot that includes all transactions committed up to that instant, subsequent commands in the same transaction will see the effects of the committed concurrent transaction in any case. The point at issue above is whether or not a single command sees an absolutely consistent view of the database.


## d42268e26db8

Focus: the effect of COMMIT

Question: The excerpt below describes transactions in a database system.

"Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all."

A bank transfer bundles a debit of Alice's account and a credit of Bob's account into one transaction.

1. The transaction executes the debit from Alice and then the credit to Bob without any failure.
2. The transaction then executes COMMIT.

Using the excerpt, explain what effect the COMMIT has on the transaction's updates.

Answer: COMMIT makes the transaction's updates permanent. Because the transfer bundles the debit and credit into a single all-or-nothing operation, after the COMMIT the whole transfer takes effect: Alice's account is debited, Bob's account is credited, and the intermediate states are not visible to other concurrent transactions. The excerpt states a transaction is atomic: it either happens completely or not at all.

Explanation: The excerpt says a transaction bundles multiple steps into one all-or-nothing operation. Once the transfer has executed both the debit and the credit without failure, COMMIT ends the transaction so the whole operation takes effect: the debit and the credit both become part of the database. If the transaction had failed before completing, none of its steps would affect the database.

Source scale-db_atomicity (PostgreSQL 18: Transactions and atomicity):
3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.


## 9beb1e10539d

Focus: receiver-advertised flow control

Question: The excerpt below describes TCP's flow-control mechanism.

"It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time. Finally, like UDP, TCP supports a demultiplexing mechanism that allows multiple application programs on any given host to simultaneously carry on a conversation with their peers.

In addition to the above features, TCP also implements a highly tuned congestion-control mechanism. The idea of this mechanism is to throttle how fast TCP sends data, not for the sake of keeping the sender from over-running the receiver, but so as to keep the sender from overloading the network. A description of TCP's congestion-control mechanism is postponed until the next chapter, where we discuss it in the larger context of how network resources are fairly allocated."

Using only this excerpt, explain the purpose of TCP's flow-control mechanism and state how its goal differs from that of TCP's congestion-control mechanism.

Answer: TCP's flow-control mechanism lets the receiver limit how much data the sender can transmit at a given time, so the sender will not over-run the receiver.

TCP's congestion-control mechanism throttles how fast the sender sends data, but for a different reason: to keep the sender from overloading the network, rather than to protect the receiver from being over-run.

Explanation: The excerpt states that TCP's flow-control mechanism allows the receiver to limit how much data the sender can transmit at a given time.
It contrasts this with TCP's congestion-control mechanism, which throttles sending not for the sake of keeping the sender from over-running the receiver, but so as to keep the sender from overloading the network.
So flow control is about the receiver's ability to bound in-flight data, while congestion control is about protecting the shared network.

Source scale-net_windows (Computer Networks: A Systems Approach — Flow and congestion control):
In terms of the properties of transport protocols given in the problem statement at the start of this chapter, TCP guarantees the reliable, in-order delivery of a stream of bytes. It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time. Finally, like UDP, TCP supports a demultiplexing mechanism that allows multiple application programs on any given host to simultaneously carry on a conversation with their peers.

In addition to the above features, TCP also implements a highly tuned congestion-control mechanism. The idea of this mechanism is to throttle how fast TCP sends data, not for the sake of keeping the sender from over-running the receiver, but so as to keep the sender from overloading the network. A description of TCP’s congestion-control mechanism is postponed until the next chapter, where we discuss it in the larger context of how network resources are fairly allocated.


## de6fc2d3219b

Focus: TCP as a byte stream

Question: The assigned excerpt compares a reliable, connection-oriented, byte-stream transport protocol with a simpler demultiplexing protocol like UDP. It states that TCP guarantees the reliable, in-order delivery of a stream of bytes and frees the application from worrying about missing or reordered data.

1. What does it mean to say that TCP offers a byte-stream service rather than a message-based service?
2. List the two byte streams that a single TCP connection supports and explain why the protocol is described as full-duplex.
3. Name the mechanism that allows the receiver to limit how much data the sender can transmit at a given time, and name the mechanism that allows multiple application programs on one host to carry on simultaneous conversations with their peers.

Answer: 1. A byte-stream service means TCP guarantees the reliable, in-order delivery of a stream of bytes. The application is freed from handling missing or reordered data; there are no preserved message boundaries or per-message deliveries to the application.
2. A TCP connection supports a pair of byte streams, one flowing in each direction. It is full-duplex because both of those byte streams are carried on the same connection at the same time, in opposite directions.
3. The receiver limits the sender's data using the flow-control mechanism. Multiple applications on one host hold simultaneous conversations through TCP's demultiplexing mechanism, just as UDP also supports demultiplexing.

Explanation: The excerpt states TCP guarantees reliable, in-order delivery of a stream of bytes and frees the application from worry about missing or reordered data, which is what distinguishes a byte-stream service from one that preserves message boundaries.
It also states that each TCP connection supports a pair of byte streams, one flowing in each direction, and that this makes the protocol full-duplex.
Finally, the excerpt says each byte stream has a flow-control mechanism that lets the receiver limit how much data the sender can transmit, and that TCP supports a demultiplexing mechanism allowing multiple application programs on a host to converse simultaneously with their peers. The same demultiplexing statement also applies to UDP.

Source scale-net_byte_stream (Computer Networks: A Systems Approach — TCP byte-stream service):
5.2 Reliable Byte Stream (TCP)

In contrast to a simple demultiplexing protocol like UDP, a more sophisticated transport protocol is one that offers a reliable, connection-oriented, byte-stream service. Such a service has proven useful to a wide assortment of applications because it frees the application from having to worry about missing or reordered data. The Internet’s Transmission Control Protocol is probably the most widely used protocol of this type; it is also the most carefully tuned. It is for these two reasons that this section studies TCP in detail, although we identify and discuss alternative design choices at the end of the section.

In terms of the properties of transport protocols given in the problem statement at the start of this chapter, TCP guarantees the reliable, in-order delivery of a stream of bytes. It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time. Finally, like UDP, TCP supports a demultiplexing mechanism that allows multiple application programs on any given host to simultaneously carry on a conversation with their peers.


## f4cf749e1b7f

Focus: visibility of a concurrent committed update

Question: A transaction T1 is running under PostgreSQL's Read Committed isolation level, which is the default level described in the supplied excerpt.

1. T1 executes SELECT A and finishes; during that query, another transaction T2 commits a change to row X.
2. T1 then executes a second SELECT B, with no changes by T1 to X and no FOR UPDATE/SHARE clause, and no further concurrent commits occur before SELECT B finishes.

According to the excerpt, does SELECT B see T2's committed change to X?

Explain your answer by stating which snapshot SELECT B uses relative to when SELECT A started and when T2 committed.

Answer: Yes. SELECT B sees T2's committed change to X, provided that T2 committed before SELECT B began. In Read Committed, each SELECT query starts with a new snapshot that includes all transactions committed up to that instant. SELECT A only saw data committed before SELECT A began, so it would not see T2's change if T2 committed after SELECT A began; SELECT B can see it because T2's commit occurred before SELECT B began.

Explanation: The excerpt states that under Read Committed, a SELECT query sees only data committed before the query began and never sees uncommitted data or changes committed by concurrent transactions during the query's execution. It also states that two successive SELECT commands within one transaction can see different data if other transactions commit between the start of the first SELECT and the start of the second SELECT. Since T2 committed after SELECT A started but before SELECT B started (as implied by the sequence), SELECT B uses a new snapshot that includes T2's commit, while SELECT A used a snapshot that excluded it.

Source scale-db_read_committed (PostgreSQL 18: Read Committed statement snapshots):
13.2.1. Read Committed Isolation Level #

Read Committed is the default isolation level in PostgreSQL. When a transaction uses this isolation level, a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution. In effect, a SELECT query sees a snapshot of the database as of the instant the query begins to run. However, SELECT does see the effects of previous updates executed within its own transaction, even though they are not yet committed. Also note that two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts.

Because Read Committed mode starts each command with a new snapshot that includes all transactions committed up to that instant, subsequent commands in the same transaction will see the effects of the committed concurrent transaction in any case. The point at issue above is whether or not a single command sees an absolutely consistent view of the database.


## 5713023f0d02

Focus: a serialization failure

Question: The following is a short excerpt from the assigned PostgreSQL 18 course reading on transaction isolation:

"The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. ... this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure."

Question: According to the excerpt, what does the Serializable level monitor for, and what happens when it detects the relevant condition?

Answer in one or two sentences.

Answer: Serializable monitors for conditions that could make a concurrent set of serializable transactions behave inconsistently with any possible serial (one-at-a-time) execution of those transactions. When such conditions are detected, a serialization failure is triggered.

Explanation: The textbook states that Serializable monitors for conditions which could make concurrent serializable transactions inconsistent with any serial execution. It further says that detection of conditions that could cause a serialization anomaly will trigger a serialization failure. Therefore, the monitor checks for possible serialization anomalies, and the response is to trigger a serialization failure, which applications must be prepared to handle by retrying.

Source scale-db_retry (PostgreSQL 18: Serializable transactions and retry handling):
13.2.3. Serializable Isolation Level #

The Serializable isolation level provides the strictest transaction isolation. This level emulates serial transaction execution for all committed transactions; as if transactions had been executed one after another, serially, rather than concurrently. However, like the Repeatable Read level, applications using this level must be prepared to retry transactions due to serialization failures. In fact, this isolation level works exactly the same as Repeatable Read except that it also monitors for conditions which could make execution of a concurrent set of serializable transactions behave in a manner inconsistent with all possible serial (one at a time) executions of those transactions. This monitoring does not introduce any blocking beyond that present in repeatable read, but there is some overhead to the monitoring, and detection of the conditions which could cause a serialization anomaly will trigger a serialization failure.


## 3a7b38da5efc

Focus: retransmission after missing acknowledgment

Question: According to the excerpt, a link-level protocol that wants to deliver frames reliably must recover from corrupt frames that have been discarded (lost).

1. Explain why some corrupt frames must be discarded rather than always being corrected by an error code such as CRC.
2. Suppose a receiver never sends an acknowledgment for a frame that was lost in transit. Explain, using the excerpt's reliability reasoning, what the sender must do so the frame is eventually delivered.

Answer in two or three sentences.

Answer: 1. Error-correcting codes typically add too much overhead to handle the full range of bit and burst errors that can occur on a link; even when error-correcting codes are used, some errors are too severe to be corrected, so corrupt frames must be discarded.
2. Because a discarded or lost frame will not be acknowledged, the sender must retransmit the lost frame so that reliable delivery can be achieved.

Explanation: The excerpt states that using error codes strong enough to correct errors usually has overhead too large for the range of bit and burst errors on a link, and that even error-correcting codes on wireless links cannot handle some severe errors. Therefore some corrupt frames are discarded and become lost.

A reliable link-level protocol must then recover from these lost frames. Since the receiver never acknowledges a frame it never successfully received, the sender must retransmit that frame until delivery is confirmed.

Source scale-net_reliability (Computer Networks: A Systems Approach — Reliable transmission):
2.5 Reliable Transmission

As we saw in the previous section, frames are sometimes corrupted while in transit, with an error code like CRC used to detect such errors. While some error codes are strong enough also to correct errors, in practice the overhead is typically too large to handle the range of bit and burst errors that can be introduced on a network link. Even when error-correcting codes are used (e.g., on wireless links) some errors will be too severe to be corrected. As a result, some corrupt frames must be discarded. A link-level protocol that wants to deliver frames reliably must somehow recover from these discarded (lost) frames.

It’s worth noting that reliability is a function that may be provided at the link level, but many modern link technologies omit this function. Furthermore, reliable delivery is frequently provided at higher levels, including both transport and sometimes, the application layer. Exactly where it should be provided is a matter of some debate and depends on many factors. We describe the basics of reliable delivery here, since the principles are common across layers, but you should be aware that we’re not just talking about a link-layer function.

