# 独立答案与来源复核材料

先完成 teacher_review_template.csv 中的难度判断，再打开本页。先核对题目条件、参考答案和来源，再查看 comparison.md 中的模型判级。

## REAL_TASKS_20260925_R6_task_1_q1

**学生可见内容**

Learning objectives:
能依据段首序号与段长写出各到达段覆盖的字节区间，并识别缺失区间。
能用累积确认规则判断存在缺失字节时接收端可回送的有效确认号，并说明依据。

TCP 面向字节流与序号
TCP 是面向字节的协议：发送方把字节写入连接，接收方从连接读出字节，每个数据字节都有一个序号。
段的 SequenceNum 字段给出该段所载数据的第一个字节的序号，因此一个到达段覆盖从该序号开始的连续若干字节。
Acknowledgement 与 AdvertisedWindow 描述反方向的数据流，本情境只看单向数据。

累积确认与空缺区间
接收端的 NextByteExpected 指向第一个空缺（尚未收到的连续字节）的起点；若数据按序到达，它指向 LastByteRcvd 之后的字节。
累积确认只反映到第一个空缺之前连续收到的字节；乱序到达但不与已收前缀连续的数据不能抬高确认号。
因此在存在缺失字节区间时，有效累积确认号停在缺失区间的起点前。

某单向 TCP 连接的数据流：初始 NextByteExpected = 1000，接收端尚未收到任何数据字节；每个数据段携带连续的整数个数据字节，段长由“长度”给出，且各段互不重叠。

到达序列（按到达顺序）：
1) 段 P：SequenceNum = 1200，长度 = 200
2) 段 Q：SequenceNum = 1000，长度 = 100
3) 段 R：SequenceNum = 1400，长度 = 300

问题：按 TCP 的字节序号与累积确认规则，此时接收端可回送的有效累积确认号（Acknowledgement 值）应为多少？

A. 1400

B. 1300

C. 1100

D. 1700

**参考答案**

C

**答案解释**

A 选项 1400：该值对应段 P 覆盖区间的末尾（1200+200），但 P 之前仍有缺失字节 1100，累积确认只能停在第一个空缺处，不能越过缺失区间。
B 选项 1300：1300 落在段 P 的内部，没有对应的连续已收前缀边界，累积确认不会指向这种中间序号。
C 选项 1100：段 Q 已按序到达并覆盖 1000–1099，之后 1100–1199 缺失，因此第一个空缺起点是 1100，累积确认号停在 1100，正确。
D 选项 1700：1700 是段 R 覆盖区间 1400–1699 之后的一个序号，越过缺失字节 1100–1199，不能作为有效累积确认号。
结论：接收端只能确认到 1100 之前连续收到的字节，故选 C。

**题目引用的来源**

### net_byte_stream.md · context_6ea7dfbab6e02ade2a3804046df2f99d

TCP is a byte-oriented protocol, which means that the sender writes bytes into a TCP connection and the receiver reads bytes out of the TCP connection. Although “byte stream” describes the service TCP offers to application processes, TCP does not, itself, transmit individual bytes over the Internet. Instead, TCP on the source host buffers enough bytes from the sending process to fill a reasonably sized packet and then sends this packet to its peer on the destination host. TCP on the destination host then empties the contents of the packet into a receive buffer, and the receiving process reads from this buffer at its leisure. This situation is illustrated in Figure 127, which, for simplicity, shows data flowing in only one direction. Remember that, in general, a single TCP connection supports byte streams flowing in both directions.

The packets exchanged between TCP peers in Figure 127 are called segments, since each one carries a segment of the byte stream. Each TCP segment contains the header schematically depicted in Figure 128. The relevance of most of these fields will become apparent throughout this section. For now, we simply introduce them.

### net_byte_stream.md · context_50cce0b14f8a0a967a4fa7d49fd473c6

The Acknowledgement, SequenceNum, and AdvertisedWindow fields are all involved in TCP’s sliding window algorithm. Because TCP is a byte-oriented protocol, each byte of data has a sequence number. The SequenceNum field contains the sequence number for the first byte of data carried in that segment, and the Acknowledgement and AdvertisedWindow fields carry information about the flow of data going in the other direction. To simplify our discussion, we ignore the fact that data can flow in both directions, and we concentrate on data that has a particular SequenceNum flowing in one direction and Acknowledgement and AdvertisedWindow values flowing in the opposite direction, as illustrated in Figure 129. The use of these three fields is described more fully later in this chapter.

### net_ack.md · context_26a46e6d64f093e5348d6e437e270f4a

The Acknowledgement, SequenceNum, and AdvertisedWindow fields are all involved in TCP’s sliding window algorithm. Because TCP is a byte-oriented protocol, each byte of data has a sequence number. The SequenceNum field contains the sequence number for the first byte of data carried in that segment, and the Acknowledgement and AdvertisedWindow fields carry information about the flow of data going in the other direction. To simplify our discussion, we ignore the fact that data can flow in both directions, and we concentrate on data that has a particular SequenceNum flowing in one direction and Acknowledgement and AdvertisedWindow values flowing in the opposite direction, as illustrated in Figure 129. The use of these three fields is described more fully later in this chapter.

The idea is that two parties want to agree on a set of parameters, which, in the case of opening a TCP connection, are the starting sequence numbers the two sides plan to use for their respective byte streams. In general, the parameters might be any facts that each side wants the other to know about.

### net_ack.md · context_ec2329e722ac9bb3246149e60b883d27

To see how the sending and receiving sides of TCP interact with each other to implement reliable and ordered delivery, consider the situation illustrated in Figure 132. TCP on the sending side maintains a send buffer. This buffer is used to store data that has been sent but not yet acknowledged, as well as data that has been written by the sending application but not transmitted. On the receiving side, TCP maintains a receive buffer. This buffer holds data that arrives out of order, as well as data that is in the correct order (i.e., there are no missing bytes earlier in the stream) but that the application process has not yet had the chance to read.

To make the following discussion simpler to follow, we initially ignore the fact that both the buffers and the sequence numbers are of some finite size and hence will eventually wrap around. Also, we do not distinguish between a pointer into a buffer where a particular byte of data is stored and the sequence number for that byte.

is true because a byte cannot be read by the application until it is received and all preceding bytes have also been received. NextByteExpected points to the byte immediately after the latest byte to meet this criterion. Second,

### net_ack.md · context_9a0e0a8fe960219d9262b9eb78135d3f

since, if data has arrived in order, NextByteExpected points to the byte after LastByteRcvd, whereas if data has arrived out of order, then NextByteExpected points to the start of the first gap in the data, as in Figure 132. Note that bytes to the left of LastByteRead need not be buffered because they have already been read by the local application process, and bytes to the right of LastByteRcvd need not be buffered because they have not yet arrived.
