# R6: 同语言查询改写预注册协议 v1

冻结日期：2026-09-19。范围：独立诊断实验，不变更生产检索默认值。

## 问题与设计

检验轻度口语化输入是否损害检索，以及仅在第一阶段使用同语言改写是否改善证据命中。固定四个条件：

1. canonical：原始基准问句参照，不是人工纠错金标准，也不参与策略选择。
2. original：合成口语输入直接检索。
3. rewritten：同语言改写用于向量和词汇检索；重排仍使用口语原文。
4. dual：原文与改写各取最多20候选，原文优先交替合并去重，总候选仍最多20；重排使用口语原文。

三种口语策略的重排输入相同。canonical 的重排输入为其原始基准问句。这是第一阶段查询策略消融，不是所有环节都替换查询的比较。dual改变候选组成，也增加首次召回计算，不保证原文20候选全部保留。

## 数据与冻结

使用 benchmarks/rag/query-rewrite-v1/queries.json 中按预定哈希抽取的20个双语问题族、40条问句。作者和第二位核验者仅看查询，不看资料、答案、相关性或检索结果。口语变体为AI撰写和AI核验，非人工口语标注、非真实用户日志。包含原始含糊指代和疑似原问句错误，不事后删题。

资料沿用R5公开软件主题语料：207篇、236个256-token递归切片，无重叠，标题路径编码。沿用原答案span作为暂定证据标签，不能把不完全span标注称为穷尽相关性，也不能把Hit率称为严格Recall。并非代表性本科课程语料。

20个问题族依据已知相关来源建立连通分量；按 SHA256('r6-split:'+component) 排序，前 max(1,floor(component_count/3)) 个分量为dev，其余为test。同一分量不得跨划分。R5材料已在历史实验中使用，本轮局部留出集不是整个项目从未接触的最终测试集。

保存查询、标签、切片、分量、tokenizer、接口标识、代码及协议哈希；网络调用前冻结。文档向量仅在模型签名、NPZ哈希、完整标题输入SHA-256键和4096维度均匹配时复用，不重新编码文档。本轮查询向量与重排重新请求，完全相同请求在本轮内去重。模型ID相同不等于服务商权重和实现从未改变。

## 改写约束与失败处理

使用 deepseek-flash，temperature=0、thinking disabled、max_tokens=256，JSON字段仅 query 与 needs_clarification。仅输入口语文本及语言；不输入原基准问句、另一语言问题、语料或答案。要求同语言简洁检索问句，保留实体、数字、否定、比较、代码和技术缩写，不回答，不增加事实；删除聊天套话/输出格式要求但保留主题约束。缺失实体、指代无法消解则 needs_clarification=true 并原样返回。

程序检查JSON字段、布尔类型、长度、基本语言字符、数字/代码/缩写保留；这是有限防护，并非完整语义一致性证明。HTTP/结构/校验失败、需要澄清或改写向量失败时，rewritten及dual回退原文候选；明确记录原因。原文向量失败时dual可使用改写分支，canonical/original没有猜测向量。无候选或重排失败按零证据命中纳入主分母，不静默重试。另报成功配对诊断，不取代主分析。

## 固定检索与度量

qwen/qwen3-embedding-8b、qwen/qwen3-reranker-8b，固定CS查询指令，hybrid_dense_lexical_v1，20候选、重排top5、1024源上下文token预算、无parent扩展。mixed使用全语料；cross仅保留与查询语言不同的资料。两个条件分别报告，也给等权总体，不把两种条件当独立问题。

主指标：预算内已知答案span命中率 budget_hit；次指标 candidate_hit20、top5_hit、MRR@5、上下文token、各阶段调用延迟。按来源连通分量进行配对bootstrap，2000次、种子20260919；中英文与两条件留在同一分量重采样。展示gain/loss、接口失败和已知措辞问题。延迟是各API调用耗时与本地计算组合的阶段估计，不是在线端到端并发压测。

candidate_hit20 使用20个候选的联合span覆盖，与预算内命中采用相同覆盖定义；另存 candidate_single_chunk_hit20 作为单个候选独立命中诊断。MRR@5沿用单片段完整span命中定义。字面量防护补充C++/C#与APIs等复数缩写，仍不构成完整实体识别或语义保证。

dev在 original、rewritten、dual 中按 budget_hit、MRR@5降序，完全相同时按上述顺序选。先落盘锁定，再运行test排名。test不反向调prompt、候选预算、阈值或删题。真实改写输出做查询对查询的AI语义审阅，独立于答案与检索结果，只诊断、不修复本轮输出。

## 调用与成本边界

最多40次text、120次单查询embedding、320次rerank请求；并发分别2/4/2，60秒超时，不自动重试。不使用用户私有资料。OpenRouter已报告累计费用控制阈值2美元，每个在途请求预留0.01美元；这是预请求检查而非服务端硬限额，不保证异常单次计费不会超出。HTTP200的OpenRouter响应缺少cost则停止后续批次，重新启动也不得绕过（最多已有在途请求可完成）。DeepSeek若无金额只列token，不把未知费用写成零。保留实际返回模型/服务商、usage、状态、时间和可公开的查询响应；不记录凭据。

## 相关工作

- Ma, X., Gong, Y., He, P., Zhao, H., and Duan, N. (2023). Query Rewriting in Retrieval-Augmented Large Language Models. EMNLP, 5303–5315. https://aclanthology.org/2023.emnlp-main.322/ DOI:10.18653/v1/2023.emnlp-main.322. 为先改写再检索提供研究动机；其web检索、强化学习训练与下游QA结果不能直接视为本项目效果。
- Jang et al. (2024). IterCQR: Iterative Conversational Query Reformulation with Retrieval Guidance. NAACL. https://aclanthology.org/2024.naacl-long.449/ DOI:10.18653/v1/2024.naacl-long.449. 多轮会话检索改写研究；本轮只有单条输入，没有对话历史消解或相同训练过程。

文献访问日期：2026-09-19。无论结果正负均保存，不能与R1–R5异构数据结果拼接成单一提升曲线。当前试验不足以独立支持生产默认开启或正式学习效果结论。
