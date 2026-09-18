# R4 文献方案对照协议 v1

状态：在本轮任何排名前冻结。日期：2026-09-12。

目标：选择本轮可运行候选中证据覆盖与排序最好的策略；不声称全球最优。
来源与动机见 research/CHUNKING_RETRIEVAL_REVIEW_20260912.md。

## 数据与隔离

- 既有 R2/R3 MLQA 92 条查询全部划为 dev，因为此前 test 已经看过。
- 新 test 从同一校验过的 MLQA 官方 test 包选择未使用的中英平行人工 QA。
- 仅按预设 CS 文章标题筛选，排除既有 family，以及任一语言原文与既有 corpus 完全重复的 family。
- 追加标题清单在 scripts/r4_experiment.py 中冻结；包含软件历史，属于 CS 相关 Wikipedia，不是课堂人工金标。
- query family 与完整原文不跨 dev/test，文章标题可能跨；没有无答案题，未知相关上下文仍为未标注。
- 每个问题运行 mixed 和 cross 两个任务。cross 只允许另一语言文档，gold 同样限制为另一语言的原人工答案跨度。
- 先保存 dev 选择，再首次运行 test。嵌入/索引可以预计算，不查看测试排名调参。

## 切分与编码

- char1200：当前 recursive_v1，1200 Python 字符、120 字符尾部重叠。
- token256 / token128：用冻结的 Qwen3-Embedding-8B tokenizer 精确计数，递归边界与同节贪心合并，无重叠。
- token 组同时改变长度度量和重叠策略，属于 token 策略组合，不能宣称纯 tokenizer 单因素贡献。
- 所有片段为原文切片，保留父原文 ID、起止字符和标题；已识别短代码/表格保护，超长则显式降级。
- 原文正文与 title_text 分开；标题来自 MLQA 文章元数据，不由模型生成。标题前缀使总编码长度略超正文 token 限额时单独统计，不声称总输入受正文限额约束。
- 原始查询对照固定英文任务指令：Given a question about computer science, retrieve passages that provide evidence to answer the question.
- 编码输入整体 SHA 缓存，同提供商模型身份才允许复用；不向正式课程库写入实验数据。

## 12 个首阶段候选与重排

候选常量以冻结 run/arms.json 为准：现状；单独查询指令；单独标题；标题+指令；字符有界混合；token256；token128；token256+标题+指令；再加有界混合；等权 RRF；有界混合+父级；有界混合+窗口。

Dense / 有界词法加分 / RRF 复用现有算法，candidate_k=20、RRF k=60，有界词法加分最大 0.05。
首阶段保留 Top20，最终以 Top5 叶片段为种子。先在 dev 选最佳首阶段，在其相同 Top20 候选上增加 Qwen3-Reranker-0.6B 的 none / parent 两组。
重排采用官方 yes/no 最后位置 logit 差，固定任务指令，最长 1024 tokenizer token（记录截断数），批量最多 4。
模型权重与 tokenizer commit/hash 记录于 models.json；只使用 Transformers 内置模型实现，不运行远程 Python 代码。
计时在加速设备同步后记录，包含本地 tokenization 与模型推理；模型加载和冷启动单独记录。
若本地推理不可运行或耗时不可接受，记录失败及已完成部分，不使用聊天模型伪造专用重排，不把未测方法判为落后。
Jina、Late Chunking、多向量检索本轮不预设为必须执行；没有兼容接口/资源时保留为未比较候选。

## 固定预算与扩展

主要上下文预算：1024 个冻结 Qwen tokenizer token，只计用双换行连接后的原文证据，不含生成提示词及引用元数据。
这是实验比较单位，不声称与 DeepSeek 的服务端 token 完全一致。
Top5 片段先按顺序纳入；放不下则跳过该片段。合并相同原文重叠跨度去重，再计完整序列的 token 数。
扩展发生在已保留的叶片段之后，不能为扩展丢弃已纳入的证据。
parent：同节全部原文；窗口：同节内向两侧各最多扩 160 字符。扩展超预算则保留叶片段。

## 选择规则与报告

dev 按 mixed/cross、双语等数量的全部行计算均值；优先 budget 完整答案跨度 Hit，再 MRR@5，再无重排，再更少上下文 token，再冻结候选顺序。
MRR 和 Top5 只针对叶片段完整覆盖已知答案，不把父文档标签复制给所有孩子。
保存选择锁后，test 一次比较所有固定首阶段及固定重排候选；不根据 test 换冠军或重调参数。
默认升级门槛：锁定候选在新 test 的 budget Hit 不低于现状、MRR@5 退步不超过 0.02，并且 mixed/cross 各组 budget Hit 不下降；不满足就保留现状，报告开发集选择失败。
所有门槛是本轮工程选择，不构成统计显著性。按 42 个双语 family 做配对 bootstrap 2000 次，种子 20260912，报告 95% 区间。
最终保留全部配置、排名、实际源跨度、单题记录、失败、API 用量、tokenizer 单位、缓存身份与代码快照。
成本同时记录模型下载/加载、嵌入调用与输入、索引大小、缓存复用、本地排名、重排延迟。禁止把缓存排名时间解释为在线端到端 API 延迟。

正式课程人工证据集仍待标注；本轮结果仅用于公开数据上的策略选择和可复现探索。
