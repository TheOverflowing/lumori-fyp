# Blind accepted-question review packet

Rate each item from its source and student-visible question. Do not use the product gate verdict.

## dd3f87c94aac

Focus: TCP as a byte stream

Question: A student says that TCP delivers data to the receiving application as a sequence of distinct messages, much like a datagram service, and that therefore message boundaries are preserved.

Using the excerpt below, explain why this claim is incorrect, and state two additional properties that TCP provides beyond reliability.

Excerpt (source scale-net_byte_stream):
"In contrast to a simple demultiplexing protocol like UDP, a more sophisticated transport protocol is one that offers a reliable, connection-oriented, byte-stream service... TCP guarantees the reliable, in-order delivery of a stream of bytes. It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time."

Address both parts of the prompt in your response.

Answer: TCP is a byte-stream service: it guarantees reliable, in-order delivery of a stream of bytes, not of discrete messages, so the receiver sees no message boundaries imposed by TCP itself.

Two additional properties from the excerpt:
- Full-duplex operation: each connection carries a pair of byte streams, one in each direction.
- Per-stream flow control: the receiver can limit how much data the sender transmits at a given time.
- Demultiplexing: like UDP, TCP lets multiple application programs on a host carry on simultaneous conversations with their peers.

Explanation: TCP is described as a byte-stream service providing reliable, in-order delivery of a stream of bytes rather than a sequence of distinct messages. Because the abstraction is a stream, message boundaries are not part of what TCP preserves. Beyond reliability, the excerpt states that TCP is full-duplex, supporting a byte stream in each direction, and that it includes flow control so the receiver can limit how much data the sender transmits at a given time. It also supports demultiplexing, allowing multiple applications on a host to communicate simultaneously.

Source scale-net_byte_stream (Computer Networks: A Systems Approach — TCP byte-stream service):
5.2 Reliable Byte Stream (TCP)

In contrast to a simple demultiplexing protocol like UDP, a more sophisticated transport protocol is one that offers a reliable, connection-oriented, byte-stream service. Such a service has proven useful to a wide assortment of applications because it frees the application from having to worry about missing or reordered data. The Internet’s Transmission Control Protocol is probably the most widely used protocol of this type; it is also the most carefully tuned. It is for these two reasons that this section studies TCP in detail, although we identify and discuss alternative design choices at the end of the section.

In terms of the properties of transport protocols given in the problem statement at the start of this chapter, TCP guarantees the reliable, in-order delivery of a stream of bytes. It is a full-duplex protocol, meaning that each TCP connection supports a pair of byte streams, one flowing in each direction. It also includes a flow-control mechanism for each of these byte streams that allows the receiver to limit how much data the sender can transmit at a given time. Finally, like UDP, TCP supports a demultiplexing mechanism that allows multiple application programs on any given host to simultaneously carry on a conversation with their peers.


## 4e5c39e6d32e

Focus: interrupt-related lock ordering

Question: The excerpt below explains how acquiring multiple locks in different orders can cause deadlock.

Excerpt (source scale-os_interrupt_locks):
"Suppose the functions running on CPUs C1 and C2 both have a point at which each needs to hold both lock A and lock B, and they acquire them in different orders:
... With a bit of bad luck, C1 and C2 might both execute their first acquire at exactly the same moment; both can succeed, since they are asking for different locks. But then both C1 and C2 will have to wait in their second calls to acquire(), since both locks are already held by the other CPU. Because both CPUs are waiting for each other, neither will ever release a lock, and both will wait forever. This situation is called deadlock.
... locking code must follow this rule to avoid deadlock: all code paths that hold multiple locks must acquire locks in the same order."

Scenario: CPU C1 acquires lock A, then lock B. At the same moment, CPU C2 acquires lock B, then lock A.

1. Why can both CPUs succeed on their first acquire call?
2. Why does each CPU then block on its second acquire call?
3. State the general rule from the excerpt that would prevent this deadlock.

Answer as three short numbered items.

Answer: 1. Both CPUs succeed on their first acquire call because each is asking for a different lock (C1 asks for A, C2 asks for B), and the lock the other CPU holds is not the one being requested.

2. Each CPU blocks on its second acquire call because the second lock it needs is already held by the other CPU: C1 wants B (held by C2), and C2 wants A (held by C1). Neither can proceed until the other releases, but neither will release while waiting.

3. The rule: all code paths that hold multiple locks must acquire locks in the same order.

Explanation: The excerpt states that both first acquires succeed because each CPU requests a different lock, so there is no conflict at that step.

The deadlock arises at the second acquire: each CPU already holds one lock and now requests the lock the other CPU is holding, so both wait forever.

The excerpt's stated prevention rule is that all code paths that hold multiple locks must acquire locks in the same order, which would prevent the circular waiting in this scenario.

Source scale-os_interrupt_locks (xv6: Lock ordering and interrupts):
7.4 Deadlock and lock ordering

Suppose the functions running on CPUs C1 and C2 both have a point at which each needs to hold both lock A and lock B, and they acquire them in different orders:

With a bit of bad luck, C1 and C2 might both execute their first acquire at exactly the same moment; both can succeed, since they are asking for different locks. But then both C1 and C2 will have to wait in their second calls to acquire(), since both locks are already held by the other CPU. Because both CPUs are waiting for each other, neither will ever release a lock, and both will wait forever. This situation is called deadlock.

The key problem in the C1/C2 example is that the two CPUs acquired the locks in different orders. If they had both tried to acquire A first, one would have acquired A and then B and then released them both, and then the other CPU could have proceeded. More generally, locking code must follow this rule to avoid deadlock: all code paths that hold multiple locks must acquire locks in the same order. The need for this global lock acquisition order means that locks are effectively part of each function’s specification: callers must invoke functions in a way that causes locks to be acquired in the agreed-on order.


## e3608525982d

Focus: two SELECT statements in one Read Committed transaction

Question: The excerpt below describes PostgreSQL's Read Committed isolation level.

Excerpt (source scale-db_read_committed):
"Read Committed is the default isolation level in PostgreSQL. When a transaction uses this isolation level, a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution. In effect, a SELECT query sees a snapshot of the database as of the instant the query begins to run. However, SELECT does see the effects of previous updates executed within its own transaction, even though they are not yet committed. Also note that two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts."

Scenario:
- Transaction T runs at Read Committed with no FOR UPDATE/SHARE clause.
- At time 1, T executes its first SELECT on row R and reads the committed value 10; this SELECT finishes at time 2.
- At time 3, a different transaction U commits an update that changes R from 10 to 20.
- At time 4, T executes its second SELECT on R and finishes at time 5.
- T has not itself updated row R.

1. State the committed value of R returned by T's first SELECT.
2. State the committed value of R returned by T's second SELECT.
3. Explain how the excerpt's snapshot rule accounts for each result.

Answer as three short numbered items.

Answer: 1. 10
2. 20
3. The first SELECT starts at time 1 and sees a snapshot of committed data as of that instant, so it reads 10. The second SELECT starts at time 4, after U committed at time 3, so its new snapshot includes 20. Because each Read Committed command begins a fresh snapshot, two successive SELECTs in the same transaction can see different data.

Explanation: Each SELECT in Read Committed takes its snapshot when the query begins. T's first SELECT begins at time 1 and finishes at time 2, so during its execution it cannot see U's later commit at time 3; it returns 10. T's second SELECT begins at time 4, after U committed, so its snapshot includes R = 20. The excerpt explicitly notes that two successive SELECTs in one transaction can see different data if another transaction commits between them.

Source scale-db_read_committed (PostgreSQL 18: Read Committed statement snapshots):
13.2.1. Read Committed Isolation Level #

Read Committed is the default isolation level in PostgreSQL. When a transaction uses this isolation level, a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began; it never sees either uncommitted data or changes committed by concurrent transactions during the query's execution. In effect, a SELECT query sees a snapshot of the database as of the instant the query begins to run. However, SELECT does see the effects of previous updates executed within its own transaction, even though they are not yet committed. Also note that two successive SELECT commands can see different data, even though they are within a single transaction, if other transactions commit changes after the first SELECT starts and before the second SELECT starts.

Because Read Committed mode starts each command with a new snapshot that includes all transactions committed up to that instant, subsequent commands in the same transaction will see the effects of the committed concurrent transaction in any case. The point at issue above is whether or not a single command sees an absolutely consistent view of the database.


## 69a1a0f64050

Focus: consistent repeated reads

Question: The excerpt below describes PostgreSQL's Repeatable Read isolation level.

Excerpt (source scale-db_repeatable_read):
"This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started."

Scenario: Transaction T begins at time 0. Its first non-transaction-control statement executes at time 2 and issues a SELECT that reads a row whose committed value is 100. At time 4, another transaction U commits an update that changes that row to 200. At time 6, T's second SELECT reads the same row. T has not updated this row itself.

1) At what point is T's snapshot established?
2) Which committed value does T's second SELECT return at time 6?

Answer each part using the excerpt.

Answer: 1) T's snapshot is established at the start of the first non-transaction-control statement, i.e., at time 2, not at the start of the second statement.
2) The second SELECT returns 100, the value from T's snapshot, because Repeatable Read says successive SELECT commands within a single transaction see the same data and do not see changes committed by other transactions after their own transaction started. U's update committed at time 4, after T's snapshot at time 2, so it is not visible to T.

Explanation: Option-free short answer. r1 fulfilled: the excerpt explicitly states the snapshot is taken as of the start of the first non-transaction-control statement (time 2), not as of the current statement. It also states successive SELECT commands within one transaction see the same data and do not see other transactions' commits made after the transaction started, so U's commit at time 4 is invisible and the second SELECT still returns 100.

Source scale-db_repeatable_read (PostgreSQL 18: Repeatable Read and snapshot isolation):
13.2.2. Repeatable Read Isolation Level #

The Repeatable Read isolation level only sees data committed before the transaction began; it never sees either uncommitted data or changes committed by concurrent transactions during the transaction's execution. (However, each query does see the effects of previous updates executed within its own transaction, even though they are not yet committed.) This is a stronger guarantee than is required by the SQL standard for this isolation level, and prevents all of the phenomena described in Table 13.1 except for serialization anomalies. As mentioned above, this is specifically allowed by the standard, which only describes the minimum protections each isolation level must provide.

This level is different from Read Committed in that a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement in the transaction, not as of the start of the current statement within the transaction. Thus, successive SELECT commands within a single transaction see the same data, i.e., they do not see changes made by other transactions that committed after their own transaction started.

Applications using this level must be prepared to retry transactions due to serialization failures.


## 536d9386872b

Focus: the effect of COMMIT

Question: The excerpt below describes how a transaction bundles several separate updates into one operation.

Excerpt (scale-db_atomicity): "The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all... A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all."

Scenario: A transaction performs several separate updates; these updates execute successfully with no failure, and the application then issues COMMIT.

1. According to the excerpt, before COMMIT are the intermediate states between the separate updates visible to other concurrent transactions?
2. After COMMIT, what happens to the effects of all the steps, and how does this match the idea that a transaction either happens completely or not at all?

Answer both parts in one or two sentences.

Answer: 1. No. The excerpt states the intermediate states between the steps are not visible to other concurrent transactions, so other transactions cannot see the partial updates before COMMIT.
2. After COMMIT the transaction has completed without failure, so all of its steps take effect together; this matches the excerpt's all-or-nothing atomicity, where the transaction either happens completely or not at all.

Explanation: The excerpt directly supports part 1: intermediate states between steps are hidden from other concurrent transactions, so a partially updated state cannot be observed before COMMIT (scale-db_atomicity).
Part 2 follows from the all-or-nothing condition: a successful completion means every step's effect is applied, which is the "completely" side of the excerpt's either/or rule; the "not at all" side applies only when a failure prevents completion.

Source scale-db_atomicity (PostgreSQL 18: Transactions and atomicity):
3.4. Transactions #

Transactions are a fundamental concept of all database systems. The essential point of a transaction is that it bundles multiple steps into a single, all-or-nothing operation. The intermediate states between the steps are not visible to other concurrent transactions, and if some failure occurs that prevents the transaction from completing, then none of the steps affect the database at all.

The details of these commands are not important here; the important point is that there are several separate updates involved to accomplish this rather simple operation. Our bank's officers will want to be assured that either all these updates happen, or none of them happen. It would certainly not do for a system failure to result in Bob receiving $100.00 that was not debited from Alice. Nor would Alice long remain a happy customer if she was debited without Bob being credited. We need a guarantee that if something goes wrong partway through the operation, none of the steps executed so far will take effect. Grouping the updates into a transaction gives us this guarantee. A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.

