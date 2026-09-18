# Chunk 切分与召回策略：论文和项目参考

检索核验日期：2026-09-12。场景：中英文计算机本科课程的学习内容与出题证据检索。本文是文献筛选与实验建议，未实施新算法、未运行新的模型对照，也不将外部论文的提升记为本项目成果。

**建议优先验证：结构与 token 预算控制 → 标题上下文编码 → 小片段召回与专用重排 → 有预算的父级原文补全。** 这是根据现有实现、R1–R3 结果和下列资料作出的工程判断；目前没有证据支持某一种方法在所有课程、语言和成本预算下同时最优。

## 1. 当前系统与真正需要补的环节

本次核对了 `app/chunking.py`、`app/pipeline.py`、`app/providers.py`、`app/retrieval.py` 和 R2/R3 报告。

- 已有递归切分、Markdown 标题边界、部分代码/表格保护、原文字符坐标、标题路径和关键词元数据。默认 1200 字符、最多 120 字符重叠；**字符数不是模型 token 数**。
- 嵌入模型为 Qwen3-Embedding-8B。入库时编码片段正文，查询时编码原始 topic；标题和关键词尚未加入文档嵌入文本，查询尚无任务指令。
- 已有 dense、BM25、RRF、MMR 和有界词法加分候选；默认仍是 dense。当前没有专用 reranker、父子片段补全或最终 token 预算装配。
- [R3](../CHUNKING_RESULTS_20260912.md) 中，1200 递归切分相对旧切分的已知答案命中持平；12 篇教材重复字符比例从 9.20% 降至 3.41%，但片段数从 75 增至 115。不能把减少重复等同于降低总索引成本。
- [R2](../EXTERNAL_DATA_RESULTS_20260912.md) 中不同数据集对融合方法的偏好不同。等权 RRF 在早期双语试点退步，但在 T2Ranking 的 Recall 上表现更好，不能永久排除，也不能直接设为默认。

## 2. 值得优先读的研究与实现

证据类型分开记录：正式会议论文用于已有研究证据；预印本用于近期研究线索；作者/厂商评测需保留其协议限制；项目文档用于确认实现机制，不能单独证明效果更强。以下为针对本项目的筛选，并非系统性综述或完整排行榜。持续更新的仓库没有被当作某一天发布的论文。

| 编号 | 资料与日期 | 核心参考价值 | 主要限制及项目优先级 |
|---|---|---|---|
| S01 | [Is Semantic Chunking Worth the Computational Cost?](https://aclanthology.org/2025.findings-naacl.114/)，Findings of NAACL，2025-04 | 对比语义与固定切分在检索及生成任务中的效果与开销；未发现语义切分稳定抵偿额外成本 | 正式论文；支持保留简单强基线，不等于语义切分从不有效。优先读 |
| S02 | [Chunking Methods on RAG: Effectiveness Evaluation Against Computational Cost and Limitations](https://arxiv.org/abs/2606.00881)，2026-05-30 | 比较多类切分器，同时记录运行失败、耗时与质量；部分复杂方法在成功运行的子集上表现好 | 预印本；排除失败运行后的均值存在选择偏差，不能只看最高平均分。其[代码](https://github.com/ApriiM/Chunking-Research)由论文链接提供，本次未执行 |
| S03 | [Evaluating Chunking Strategies for RAG on Academic Texts](https://arxiv.org/abs/2607.01852)，2026-07-02 | 在有结构的学术长文本上，所测聚类切分未胜过固定/递归切分，并讨论自动评审的可靠性 | 预印本；使用 MiniLM 和较小的本地生成/评审模型，结果不能直接外推至 Qwen 8B 中英课程 |
| S04 | [Structure-Aware Semantic Chunking with Title-Chain Prefixes](https://arxiv.org/abs/2608.00824)，2026-08-01 | 标题层级切分、语义合并、标题链前缀组合；也展示文本变换会影响自动标注 | 预印本；私有语料、组合变量、双 LLM 评审。适合提出标题消融，不能作为单独标题增益的强证据 |
| S05 | [Docling HybridChunker](https://docling-project.github.io/docling/_generated/examples/hybrid_chunking/)，当前官方文档 | 先识别文档结构，再按 tokenizer 拆分过长单元、合并适宜短单元；可序列化标题上下文 | 工程参考，优先级高。它的 hybrid 指结构与 token 约束，不是向量与 BM25 融合 |
| S06 | [LlamaIndex AutoMergingRetriever](https://developers.llamaindex.ai/python/framework/integrations/retrievers/auto_merging_retriever/)，当前官方文档 | 叶节点向量检索，父节点留在文档存储中，命中相关子节点后可向父级合并 | 成熟实现思路，优先级高；示例不是课程评测，不能照搬其层级大小或旧模型配置 |
| S07 | [Late Chunking](https://arxiv.org/abs/2409.04701)，2024-09 起的研究；本次参考 v3 | 先用长上下文编码 token，再按片段聚合向量，使片段表示带有上文信息 | 需要兼容的 token 表示和 pooling 流程。作为独立研究支线，不能仅改当前切分函数实现 |
| S08 | [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)，2024-09-19 | 索引阶段给片段生成上下文描述，再用于向量和 BM25；结合重排测试 | 厂商研究；有额外索引生成成本。先对比可从原文直接取得的标题路径，再决定是否生成描述 |
| S09 | [Qwen3 Embedding / Reranker](https://github.com/QwenLM/Qwen3-Embedding)，2025-06 系列 | 查询任务指令、多语言 embedding，以及 0.6B/4B/8B 专用重排模型 | 优先级高。先比较查询指令与 0.6B 重排；4B 是后续质量候选。嵌入接口可用不代表重排接口已可用 |
| S10 | [jina-reranker-v3.5](https://huggingface.co/blog/jinaai/jina-reranker-v3-5-faster-listwise-reranking)，2026-08-05 发布介绍 | 0.6B 多语言 listwise 重排，以混合注意力降低长候选列表计算开销 | 最新候选之一；主要依据作者评测，需要在相同候选集上与 Qwen 对照 |
| S11 | [DenseOn with the LateOn](https://arxiv.org/abs/2607.27178)，2026-07-29，v2 为 07-31 | 开放训练方案、数据与模型；mLateOn 是 307M 多语言 ColBERT 式多向量检索模型 | 预印本及[官方模型卡](https://huggingface.co/lightonai/mLateOn)；适合第二阶段研究，不是现有 4096 维向量的替换配置 |
| S12 | [NextPlaid](https://github.com/lightonai/next-plaid)，当前官方仓库 | 多向量搜索服务，包含量化、增量更新、元数据预过滤及 CPU 路线 | 可作为 S11 的服务实现候选；须验证模型导出兼容性。工程特性不代表本机性能已验证 |

## 3. 论文数字应该怎样解释

**复杂切分的收益并不稳定。** S01 的正式研究和 S03 的近期学术文本实验都要求我们保留固定/递归基线。S02 还报告了超时和实现失败；某个方法只在成功的任务上均分更高，不足以证明它整体更强。[S01](https://aclanthology.org/2025.findings-naacl.114/)、[S02](https://arxiv.org/html/2606.00881v1)、[S03](https://arxiv.org/html/2607.01852v1)

**最新小模型也不是全场景第一。** Jina 作者用同一个首阶段模型生成 Top 100 候选后，报告 v3.5 与 Qwen3-Reranker-4B 的 BEIR nDCG@10 分别为 63.20、62.28；MIRACL 则为 74.11、76.56。其最高 1.56 倍加速是相对 Jina v3、单张 A100、长文档列表的特定测试，平均耗时仍为 10.3 秒。不能把参数更少直接解释为本机/API 更快。[S10](https://huggingface.co/blog/jinaai/jina-reranker-v3-5-faster-listwise-reranking)

**不要混淆错误率与召回率。** Anthropic 的 67% 是其设定下 Top 20 检索失败率从 5.7% 降至 1.9% 的相对下降，且包含上下文处理与重排；不是 Recall 增加 67 个百分点，也不是本项目 Top 5 的实验。[S08](https://www.anthropic.com/engineering/contextual-retrieval)

**不要把双 LLM 评审称为双人标注。** S04 的评审者为 DeepSeek 模型，且不同文本变换下评审一致性明显变化；三阶段组合结果无法证明标题前缀本身的独立贡献。我们应借用其消融警示，在固定原文证据标签上比较新旧表示。[S04](https://arxiv.org/html/2608.00824v1)

## 4. 最适合下一轮验证的方案

以下是本项目的设计建议，不是引用资料已证明的效果。

### 4.1 结构识别、token 预算与标题编码

以当前递归切分为基线，独立比较：格式识别修复；字符预算改为准确 tokenizer 预算；同一章节内相邻短单元合并。长代码/表格需要明确的降级规则、重复表头和源位置映射。PDF 还要区分解析时丢失标题/阅读顺序与切分算法造成的信息断裂。

参考 Docling 的结构加 token 约束实现，而不是为了使用库而整体迁移。切片时按嵌入模型 tokenizer 计数，并把标题前缀占用算进去；最终生成证据预算按生成模型 tokenizer 单独核算。若无法取得服务端一致的 tokenizer，必须标明估算方式，不能把字符预算重命名为精确 token 预算。[S05](https://github.com/docling-project/docling/blob/main/docs/concepts/chunking.md)

为每个片段保留两份用途明确的文本：`source_text` 对应原文与引用；`embedding_text` 可增加“课程 → 章节 → 小节”路径。例如为“平均查找时间为 O(1)”加入“数据结构 / 散列表 / 时间复杂度”。先测真实标题，关键词扩展另设开关，避免一次改变多个因素。

修改标题前缀需要重新编码受影响的文档，并版本化索引输入格式。生成的 contextual description 如以后加入，也必须与原文分开保存，不能作为原文引用。

### 4.2 查询任务指令与两阶段检索

Qwen 官方提供查询任务指令格式，并建议多语言任务使用英文指令；检索文档不要求相同指令。我们可以冻结一句贴合课程证据检索的描述，先做“原始 query / 指令 query”的独立对照，保持文档向量不变，但刷新并记录查询编码缓存版本。[S09](https://github.com/QwenLM/Qwen3-Embedding)

先分别观察候选 Recall@20/50，再比较同候选集上的无重排、Qwen 0.6B、Jina v3.5；预算允许时再加 Qwen 4B。重排不能凭空找回首阶段从未召回的证据，所以候选覆盖与最终排序必须分别报告。API 可用性、模型版本、截断、超时和网络延迟都要记录；普通聊天输出“是/否”不等同于按专用模型规定读取重排分数。

Dense 与 BM25 保留为可独立评估的候选来源；融合在 dev 上定规则，分开观察精确代码术语和中英跨语言查询，避免词法重合把真正相关的跨语言结果挤出候选。

### 4.3 小片段定位，父级原文补全

小片段帮助定位知识点，生成题目可能还需要同节的定义、前提和例子。参考 AutoMergingRetriever 的父子结构，在选定片段后按规则补回父节或相邻窗口，合并重复源跨度，再装入固定生成 token 预算。[S06](https://developers.llamaindex.ai/python/framework/integrations/retrievers/auto_merging_retriever/)

例如检索命中二分查找的 `mid` 更新规则后，补回同节的“数组有序”前提与终止条件。父级来源采用原文，无需额外生成摘要；但上下文变长会增加生成输入成本。不能无限扩大父节，更不能仅凭最终 Recall 提高就忽略输入预算增长。

### 4.4 Late Chunking 与多向量检索：只选择一条研究支线

| 方法 | 改变什么 | 当前接口适配情况 |
|---|---|---|
| 标题前缀/上下文描述 | 改变送入 embedding 的文本，仍输出一个片段向量 | 现有接口可以编码，但要重建相关向量及输入格式版本 |
| 父级补全 | 检索后增加有来源的原文上下文 | 可复用已有叶片段向量，增加父子映射和预算装配 |
| Late Chunking | 长文本先得到 token 表示，再按片段池化 | 当前接口仅返回汇总向量，不暴露所需中间表示；Qwen 官方示例使用末 token 池化，不能直接照搬均值池化方案 |
| ColBERT / mLateOn | 每个片段保留多个 token 向量，查询时细粒度匹配 | 需要兼容编码器和多向量索引；增加存储与检索工程投入 |

Late Chunking 的参考是 [Jina 论文](https://arxiv.org/html/2409.04701v3)；它与 ColBERT 的 late interaction 是两种不同机制。mLateOn 与 NextPlaid 可以构成后一条路线的候选。mLateOn 的多语言训练扩展主要覆盖英语及八种翻译语言，中文不在这八种之内；中文和中英跨语言效果仍须单独验证。其模型卡的主要基线也不等于已经战胜我们使用的 Qwen 8B。[S11](https://huggingface.co/lightonai/mLateOn)、[S12](https://github.com/lightonai/next-plaid)

## 5. 建议的实验顺序与停止条件

这些编号是待讨论的实验草案，**不是已预登记或已完成的 R4**。先限制候选数量，不执行全组合网格。

| 阶段 | 独立问题 | 首批对照与条件 |
|---|---|---|
| A | 结构、token 和编码上下文是否有效？ | 当前基线；每次只增加格式修复、token 预算、短单元合并或标题路径之一。查询指令另做对照 |
| B | 命中片段是否缺少生成所需前提？ | 固定 A 的开发集选择，比较不扩展 / 邻接窗口 / 有界父节；相同最终 token 预算 |
| C | 候选齐全但排名不理想吗？ | 固定候选集，比较无重排与两种小 reranker；仅在收益不足且延迟预算允许时增加 4B |
| D | 单向量表示是否仍是主要瓶颈？ | 只有 A–C 后仍存在对应失败案例时，比较兼容模型的 Late Chunking 或 mLateOn；更换模型本身须设匹配基线 |

阶段 C 可以在现有切片上先做小规模试验以确认瓶颈；最终论文报告仍要区分单因素消融与组合流水线，不把组合提升全部归因于某一个模块。

停止条件：某候选增加调用/存储/延迟但收益不稳定，保留负结果并停止扩大；只有某种题型受益时，考虑按明确规则使用，而非全量默认开启。规则和阈值在 dev 上决定，冻结后评一次新的保留测试集。

## 6. 为论文保留的评估证据

1. **新测试集。** 已见的 MLQA/T2Ranking 和 R3 数据继续用于开发与回归，不能反复调参后仍称为独立 test。新增真实课程人工审核数据；中英同义题按 query family 分组，优先课程/文档隔离，避免翻译题或相邻片段跨集合泄漏。
2. **片段无关的真值。** 人工标注原文中的相关证据跨度与必要事实组。切分变化后从原文映射，不能把父 passage 的正例标签复制给每一个子片段。公开 QA 答案跨度与完整教学证据标签继续分开。
3. **分层指标。** 首阶段候选覆盖；重排后的 MRR/nDCG；固定 token 预算下的证据跨度及必要事实覆盖；随后才是生成内容的事实支持、可出题性与难度控制。命中知识点不等于生成质量或学习效果提升。
4. **语言与难题分组。** 中文、英文、强制跨语言、精确术语、代码、表格、跨段证据、无答案；报告分母与失败类型，不能只展示总体均分。
5. **完整成本。** 解析/切分/嵌入建库耗时、片段数、重复量、索引体积、在线 p50/p95、网络时间、模型输入量与实际账单字段；冷/热缓存、并发与硬件一致。不能仅比较本地排序时间。
6. **可信差异。** 保存版本、代码/语料/配置哈希、逐题排名、实际上下文、随机种子与原始输出；配对统计按双语 query family 聚合 bootstrap。自动 LLM 评分作为补充，不代替人工真值；预先固定评审协议。

建议论文研究问题：**在固定上下文与在线成本预算下，结构和标题信息、父级补全以及专用重排，分别对双语计算机课程的证据完整性带来多大收益？** 这是可以用现有系统逐步回答的问题，结论允许正向、持平和负向结果。

来源登记表：[chunking_retrieval_sources_20260912.json](chunking_retrieval_sources_20260912.json)。本文件记录本次阅读网页后的摘要与判断，未保存第三方全文，也未对上述开源仓库进行安装或复现。
