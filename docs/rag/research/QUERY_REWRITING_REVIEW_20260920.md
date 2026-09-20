# 查询改写、融合与歧义澄清：文献及应用参考

检索核验日期：2026-09-20。对应 [R7 分级口语实验](../R7_RESULTS_20260920.md)。本文是研究记录和后续实验建议；没有新增模型调用、实施新策略或改变生产默认值。论文效果、软件功能、本项目实测与下述建议分别表述。

## 1. 与 R7 的关系

R7 中，术语归一化改善强口语输入的首阶段排序，但前五及最终命中率已经饱和；保守改写在歧义识别上更好，归一化还出现答案提示及范围改变。现在要研究的至少是三个独立问题：能否保持原意、生成的查询怎样参与检索、信息不足时是否及怎样追问。口语化程度不能代替歧义标签。

## 2. 优先阅读的近期研究

### 2.1 AnchorQE：把生成方法与融合方法分开

Sun and Surdeanu. **Query Expansion Is More Than Generation: Improving Dense Retrieval through Better Integration**. arXiv，2026-08-26，v1；本次未见会议录用信息。[摘要与版本](https://arxiv.org/abs/2608.25521) · [全文](https://arxiv.org/html/2608.25521v1)

固定同一份扩展文本，分别编码原文及扩展，再加权融合归一化向量。SC 版本用查询流开头八条无标签输入估计一个权重，排除这八条后评价，并非逐题路由。其线性融合等价性限于同一向量空间的点积、完整精确排序，不覆盖稀疏混合或截断列表。

**本项目建议：**复用 R7 已保存的文本和向量，比较交替合并、RRF、向量融合。先只变化融合方式，检查是否保留原文能抑制不良改写。旧数据只作探索，正式结论另用新留出集；不能把向量接近当成语义忠实证明。

### 2.2 Better Together：强基线下，改写何时值得做

Shanian et al. **Better Together: Complementary Query Rewriting Under a Strong RAG Baseline**. 2026-09-04 首发，09-09 v2；arXiv 作者备注称已接收 EMNLP 2026 Industry Track。[版本页](https://arxiv.org/abs/2609.05637) · [全文](https://arxiv.org/html/2609.05637v2)

在固定检索、重排及多样性筛选下比较改写与扩展。没有一种单方法跨数据集占优，合并可能受益，也在 AmbigNQ 上退步。作者的企业基准模拟路由仅对 39% 查询扩展，HIT@10 为 43.55%，原文为 39.22%；这来自合成企业语料和事后模拟，不是线上 A/B 结果。融合分析还需注意种子及事后选择。

**本项目建议：**记录“救回原文失败的题”和“破坏原本正确的题”，同时测成本。若依据重排分数触发改写，阈值只能在开发集校准；不能直接照搬其他模型的 0.65，也不能把相关性分数当成理解用户意图的概率。

### 2.3 Clarify-Then-Search：追问要改善最终任务

Huang et al. **Clarify-Then-Search: A Clarification Benchmark for Deep Search with End-to-End Nugget Restoration**. KDD 2026 Datasets & Benchmarks；作者论文列 DOI `10.1145/3770855.3817586`。[论文](https://arxiv.org/html/2608.20357v1) · [项目与数据](https://clarify-then-search.github.io/)

518 对源自百度查询的明确意图/信息缺失输入。澄清器只看模糊输入，模拟用户依据隐藏意图答复，改写器只看到已发生的问答，再测固定搜索后端的证据要点恢复。资料特意筛选高澄清价值场景，包含模型模拟和自动评分，不能估计一般流量里多少人需要追问。

**本项目建议：**将 L4 从“是否返回澄清标记”扩展为“问一个必要问题→得到回复→检索”。除命中外，测追问可回答率、无信息回复率、误追问率与交互成本。隐藏意图只能供模拟用户或评价器使用，不能出现在改写器输入中。

### 2.4 Think Then Rewrite：从生活化描述识别专业概念

Li et al. **Think Then Rewrite: Reasoning Enhanced Query Rewriting for Domain Specific Retrieval**. AAAI 2026，40(18):15045–15053，2026-03-14。[正式论文页](https://ojs.aaai.org/index.php/AAAI/article/view/38527) · [作者代码](https://github.com/LIANG-star177/TTR/tree/master)

面向法律、医疗领域，以区分混淆文档的奖励和混合策略强化学习训练推理改写器。它针对的是用户表达与专业文档之间的差距，而不只是删语气词。

**本项目建议：**先提取用户已经表达的机制、限制条件及待求目标，再判断能否唯一对应课程术语。加入近邻概念干扰，例如普通平衡树与 AVL、平均情况与最坏情况。通过 DeepSeek 提示词借鉴这个思路，不等于复现论文的训练算法或性能。

### 2.5 Clarify When Necessary：追问本身有代价

Zhang and Choi. **Clarify When Necessary: Resolving Ambiguity Through Interaction with LMs**. Findings of NAACL 2025。[正式论文](https://aclanthology.org/2025.findings-naacl.306/)

IntentSim 用多个潜在意图估计交互价值，在有限预算下决定何时澄清。原研究为隔离“何时问”使用 oracle 澄清问答，不能据其结果宣称已解决实际追问生成。

**本项目建议：**比较限制追问比例下的净收益，不以“追问越多越好”为目标。正式但信息不足、口语但信息完整应成为交叉测试组。

## 3. 论文背景与补充基准

| 参考 | 适合借鉴的部分 | 写作及实验边界 |
|---|---|---|
| Ma et al., **Query Rewriting in Retrieval-Augmented Large Language Models**, EMNLP 2023。[原文](https://aclanthology.org/2023.emnlp-main.322/) | Rewrite–Retrieve–Read 基础框架；利用下游反馈优化查询 | 包括小模型强化学习训练，不能把我们的提示词实验称为完整复现 |
| Zhang et al., **Adaptive Query Rewriting: Aligning Rewriters through Marginal Probability of Conversational Answers**, EMNLP 2024。[原文](https://aclanthology.org/2024.emnlp-main.746/) | AdaQR 用答案概率建立改写偏好，再进行 DPO 训练 | adaptive 指训练适配，并非判断是否改写的产品路由器；训练阶段仍使用答案 |
| Li et al., **DMQR-RAG: Diverse Multi-Query Rewriting for RAG**, arXiv 2024。[原文](https://arxiv.org/abs/2411.13154) | 有限策略池、原文保留、选择不同改写策略 | 含伪答案扩展；原文加四路各取十条的流程不同于我们的总候选二十条；本次未核实会议录用 |
| **CLAMBER**, ACL 2024。[原文](https://aclanthology.org/2024.acl-long.578/) · [数据](https://github.com/SCUNLP/CLAMBER) | 细分歧义类型，分别评估识别与澄清质量 | 包含合成过程，不统一称纯人工真实用户数据；课程中英文仍需单独验证 |
| Zheng et al., **Can Synthetic Query Rewrites Capture User Intent Better than Humans in Retrieval-Augmented Generation?**, arXiv 2025。[原文](https://arxiv.org/abs/2509.22325) | SynRewrite 的合成训练目标及泄漏审计 | 制作训练目标时可看答案，不代表测试改写器可以看答案；标题不能证明 AI 审核等价于教师金标 |

## 4. 已有应用和可复用实现

| 应用或项目 | 当前官方资料支持的功能 | 对我们的价值 |
|---|---|---|
| [LlamaIndex QueryFusionRetriever](https://developers.llamaindex.ai/python/framework/integrations/retrievers/reciprocal_rerank_fusion/) · [源码](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py) | 保留原文，支持多查询及 RRF 等排名融合，最后截取 top-k | 参考真正的排名融合；R7 的交替合并未测到这一策略 |
| [LangChain MultiQueryRetriever 源码](https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain_classic/retrievers/multi_query.py) | 生成多种表达、分别检索、返回去重并集；默认不加入原文 | 适合多查询对照；并集不是 RRF，需要自己限制总候选预算 |
| [Haystack QueryExpander](https://docs.haystack.deepset.ai/docs/queryexpander) · [源码](https://github.com/deepset-ai/haystack/blob/main/haystack/components/query/query_expander.py) | 结构化输出、扩展数量限制、去重和失败回退；可保留原文 | 借鉴可靠性处理；这些检查不能保证意思未变，也未实现我们的歧义澄清流程 |
| [IBM Granite Query Rewrite Intrinsic](https://huggingface.co/ibm-granite/rag-intrinsics-lib/blob/main/query_rewrite/README.md) | 开放改写适配器，把依赖历史的提问转成独立问题；要求必要时才改 | 参考最小改动与语义等价评价。官方在 MT-RAG 的 260 条依赖上下文子集、Elser 检索器上报告 R@5 从 0.263 到 0.445；不是我们的强口语单轮任务结果，且部分训练数据未公开 |
| [Cloudflare AI Search](https://developers.cloudflare.com/ai-search/configuration/retrieval/query-rewriting/) | 官方 2026-06-08 文档：可选改写用于 messages 形式的后续问题，首条直接使用；query 形式不应用 | 证明产品中存在有条件改写的设计；主要处理对话引用，不是现成的单轮口语分流器，增加模型调用 |

另有 [LlamaIndex HyDE](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/indices/query/query_transform/base.py)：生成假想回答/文档用于嵌入。它可以单列为探索臂，但不属于忠实改写；生成事实不能成为答案证据，仍需在真实资料中找到支持。

以上链接核对的是当日文档或默认分支，不是已安装、测试或固定依赖版本。真正引入代码前应记录具体版本与许可。

## 5. 建议的下一轮顺序（尚未执行或冻结）

1. **固定文本的融合消融。** 原文、归一化、交替合并、RRF、向量融合；复用已有向量先研究首阶段，不伪造新候选的重排分数。若新候选未在已记录的共享评分池中，最终重排需重新评分或明确只报首阶段。RRF 与向量融合不是同一个算法。
2. **意图保持的归一化。** 明确保留实体、否定、范围、前提及待求目标。分别统计恢复术语、答案提示、范围强化、无必要修改；仍保留原文回退。
3. **独立的歧义与交互实验。** 用新课程信息需求交叉安排口语程度和信息充分性；分别测“是否该问”“问得是否有用”“回复后是否找对证据”。已知歧义也不等于知道用户本来想表达什么。
4. **开发集选择、全新留出验证。** 选择权重、阈值及提示后再冻结；R7 已看过，不能升级为新策略的独立验证集。优先加入学生原始问法及教师相关性/意图审核；没有真人参与时继续标注 AI 辅助。

各臂保持最终上下文和重排候选预算一致，另报实际检索次数、候选扫描量、模型调用、延迟及费用。相同最终 top-k 不等于相同计算成本。同时报告命中、排序、语义风险、逐题得失与追问负担；预注册主要选择规则，避免事后选“最好看的指标”。

## 6. 对论文的定位

可将后续问题表述为：**在中英文计算机课程检索中，如何在保持用户意图和受限成本的条件下，选择保留原文、术语归一化或澄清，并控制改写信息参与检索的方式？**

这是一项基于现有方法的可检验工程研究方向；尚未建立算法新颖性或普遍性能优势。文献中的提升、R7 的排序收益和未来实验数据应分表记录，不拼成同一条提升曲线。论文正文及 DOCX/PDF 本次未重建。
