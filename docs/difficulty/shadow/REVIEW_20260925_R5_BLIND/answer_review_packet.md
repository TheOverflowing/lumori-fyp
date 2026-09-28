# 独立答案与来源复核材料

先完成 teacher_review_template.csv 中的难度判断，再打开本页。先核对题目条件、参考答案和来源，再查看 comparison.md 中的模型判级。

## REAL_TASKS_20260925_R5_task_1_q1

**学生可见内容**

Learning objectives:
把 TCP 的字节序号应用到具体到达序列，标出已按序到达与缺失的字节区间。
依据累积确认规则判断接收方应发的确认值所指向的字节位置。
比较 LastByteRcvd 与 NextByteExpected 的相对位置，定位缺失区间起点。

字节序号与段
TCP 是面向字节的协议：发送进程写入字节流，接收进程读出字节流，而网络上传输的是包含一段字节流的报文段。因为面向字节，每个字节都有序号；SequenceNum 字段给出该段所携带数据的第一个字节的序号。确认（Acknowledgement）与通告窗口字段承载的是反方向数据流的信息；本情境只讨论单向数据流。约定本情境中起始序号为 1，序号连续递增、不回收。

接收缓冲与缺失区间
接收方维护接收缓冲，可暂存乱序到达的数据。NextByteExpected 指向最新的“已收到且其前所有字节都已收到”的字节之后的那个字节：若数据按序到达，它指向 LastByteRcvd 之后；若出现乱序，则它指向数据中第一个缺失字节，即缺失区间的起点。一个字节只有在被收到、且其前面所有字节也都已收到之后，才可被应用读取。

某 TCP 连接的接收方正在处理一个反向流量的单向数据流，字节序号从 1 开始连续编号。接收方已收到的若干字节如下（均为有效载荷，不含首部）：
1) 第 1～200 字节已按序收到。
2) 第 201～500 字节尚未到达。
3) 第 501～700 字节已到达，但它们前面存在缺口。
4) 第 701～900 字节尚未到达。
5) 第 901～1000 字节已到达。
6) 此情境假设接收方不发送延迟确认、不重传，接收缓冲足够大，且发送方不重传第 201～500 字节。

请依据“面向字节序号 + 累积确认”规则，判断接收方此刻应发送的累积确认值指向哪个字节位置，并定位数据中最先出现的缺失区间。

请选择最符合上述规则的一项。

A. 确认值指向第 501 字节（即已连续收到 1～500，缺口从第 501 字节开始）。

B. 确认值指向第 201 字节，且最先缺失区间为第 201～500 字节。

C. 确认值指向第 1001 字节，接收方已允许应用读取全部 1～1000 字节。

D. 确认值指向第 901 字节，最先缺失区间为第 701～901 字节。

**参考答案**

B

**答案解释**

TCP 面向字节，每个字节都有序号，接收方用累积确认表示“该序号之前的字节都已连续收到”。第 1～200 字节连续到达，第 201 字节缺失，于是 NextByteExpected 指向第一个缺失字节，即第 201 字节。

虽然第 501～700、901～1000 字节已到达，但它们前面的 201～500 存在缺口，因此这些乱序字节不能被越过缺口确认；接收缓冲即便暂存了它们，应用也不能读取连续状态下的第 201 字节及之后数据。

所以正确结论是：累积确认指向第 201 字节，最先缺失区间为 201～500。

A 错在把缺口起点误当成 501，并把已到达的 501～700 视为已连续。C 错在假设缺口不影响可确认范围，把 1001 当成可确认位置。D 错在缺口起点与累积确认位置均被错误定位。

**题目引用的来源**

### net_byte_stream.md · context_64dd618ddaee33910f654543e3749168

TCP is a byte-oriented protocol, which means that the sender writes bytes into a TCP connection and the receiver reads bytes out of the TCP connection. Although “byte stream” describes the service TCP offers to application processes, TCP does not, itself, transmit individual bytes over the Internet. Instead, TCP on the source host buffers enough bytes from the sending process to fill a reasonably sized packet and then sends this packet to its peer on the destination host. TCP on the destination host then empties the contents of the packet into a receive buffer, and the receiving process reads from this buffer at its leisure. This situation is illustrated in Figure 127, which, for simplicity, shows data flowing in only one direction. Remember that, in general, a single TCP connection supports byte streams flowing in both directions.

The packets exchanged between TCP peers in Figure 127 are called segments, since each one carries a segment of the byte stream. Each TCP segment contains the header schematically depicted in Figure 128. The relevance of most of these fields will become apparent throughout this section. For now, we simply introduce them.

### net_byte_stream.md · context_199c09ce877546cc6641001e1dd6ead4

The Acknowledgement, SequenceNum, and AdvertisedWindow fields are all involved in TCP’s sliding window algorithm. Because TCP is a byte-oriented protocol, each byte of data has a sequence number. The SequenceNum field contains the sequence number for the first byte of data carried in that segment, and the Acknowledgement and AdvertisedWindow fields carry information about the flow of data going in the other direction. To simplify our discussion, we ignore the fact that data can flow in both directions, and we concentrate on data that has a particular SequenceNum flowing in one direction and Acknowledgement and AdvertisedWindow values flowing in the opposite direction, as illustrated in Figure 129. The use of these three fields is described more fully later in this chapter.

### net_ack.md · context_4d79e8b0335c674e0ef7061b94ee3471

To see how the sending and receiving sides of TCP interact with each other to implement reliable and ordered delivery, consider the situation illustrated in Figure 132. TCP on the sending side maintains a send buffer. This buffer is used to store data that has been sent but not yet acknowledged, as well as data that has been written by the sending application but not transmitted. On the receiving side, TCP maintains a receive buffer. This buffer holds data that arrives out of order, as well as data that is in the correct order (i.e., there are no missing bytes earlier in the stream) but that the application process has not yet had the chance to read.

To make the following discussion simpler to follow, we initially ignore the fact that both the buffers and the sequence numbers are of some finite size and hence will eventually wrap around. Also, we do not distinguish between a pointer into a buffer where a particular byte of data is stored and the sequence number for that byte.

is true because a byte cannot be read by the application until it is received and all preceding bytes have also been received. NextByteExpected points to the byte immediately after the latest byte to meet this criterion. Second,

### net_ack.md · context_4880e8f2cd6feb858236c20181921f5c

since, if data has arrived in order, NextByteExpected points to the byte after LastByteRcvd, whereas if data has arrived out of order, then NextByteExpected points to the start of the first gap in the data, as in Figure 132. Note that bytes to the left of LastByteRead need not be buffered because they have already been read by the local application process, and bytes to the right of LastByteRcvd need not be buffered because they have not yet arrived.
