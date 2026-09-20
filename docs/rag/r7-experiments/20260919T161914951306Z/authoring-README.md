# R7：分级口语化检索实验基础数据

本目录提供 **真实教材原文 + AI 辅助拟定信息需求与证据**，用于检验输入从规范表达到严重口语化时的检索变化。它不是人工金标准，也不是真实用户日志；本阶段没有运行检索、模型 API 或查看检索结果。

`base.json` 包含 12 份冻结的完整教材文件、12 个信息需求 family、24 条中英文规范问句，以及 20 个精确证据片段。所有正文均从现有 `course_sources/manifest.json` 指定的本地文件读取，逐个验证 SHA-256。原始人工查询和判断 CSV 未读取、未更改。

## 来源与授权

- Hello Algo 中文教材，冻结版本 `28c1e74c1d3594fca7cc41b78a6bd18b700c5ce9`，CC BY-NC-SA 4.0，作者 krahets 与贡献者。保留原文、出处、作者和许可；许可文件位于 `benchmarks/rag/course_sources/hello_algo_zh/LICENSE`。
- OpenDSA 英文教材，冻结版本 `347b2872a70eb4b10e20f2a91ffd131656de8266`，MIT，作者 Ville Karavirta、Clifford A. Shaffer 与贡献者。许可文件位于 `benchmarks/rag/course_sources/opendsa_en/MIT-license.txt`。

每份 document 保留具体 `source_url`、`source_revision`、`source_sha256`、`license`、`authors` 与完整相对路径。这里沿用此前已下载的课程原文，没有重新下载或补充未冻结的网页内容。

## 信息需求覆盖

| family | 信息需求 | 已定位的证据语言 |
|---|---|---|
| binary-order | 二分查找要求的数组有序性 | 中、英 |
| binary-log | 搜索区间减半与对数复杂度 | 中、英 |
| hash-delete | 线性探测删除中的墓碑标记 | 中 |
| hash-chain | 冲突链过长时改用平衡树 | 中 |
| avl-factor | AVL 节点平衡因子的计算 | 中 |
| stack-order | 栈的出入顺序关系 | 中、英 |
| bfs-queue | BFS 的队列和访问顺序 | 中、英 |
| dfs-backtrack | DFS 的回溯和继续探索 | 中、英 |
| quick-partition | 快排基准数划分的作用 | 中、英 |
| quick-bad-pivot | 倒序输入中首元素基准的坏划分 | 中、英 |
| insertion-near | 接近有序时插入排序的开销 | 英 |
| merge-selection | 合并两个有序序列时的选择 | 英 |

规范问句只询问下载文本可直接支持的事实；没有依赖图片、交互动画或外部代码引用。中英文表达指向相同信息需求，但不会为了制造双语证据而翻译教材正文。所有 24 条规范问句可用于混合语言全文库。跨语言条件必须依据 `eligible_cross_query_languages` 过滤：7 个 family 双向可用、5 个 family 单向可用，共 19 个规范查询方向。另一方向的证据缺失不是检索失败。

## 证据与评测边界

- `evidence.start/end` 是 `document.text` 中的 Unicode 字符偏移，左闭右开；必须满足 `document.text[start:end] == evidence.text`。
- 正文保留原始 Markdown/reStructuredText、版权说明、代码和未展开的引用。证据均选自已下载的事实性叙述，不将外部宏内容视为已下载文本。
- 片段是已知支持文本，并非穷尽式相关性标注。不能将“命中任一已知片段”直接称为文档 Recall 或完整答案正确率。
- `hash-delete` 的两个中文片段分别解释直接置空的问题与墓碑的解决方式；命中单个片段不一定支持完整解释。需区分 any-span hit 与完整证据覆盖。
- QuickSort 两种教材对等于基准值的分区约定细节不同，因此规范问题询问划分的一般作用，不强制特定等值处理规则。
- 同一文件的多个问题不能作为独立来源。基于 `source_ids` 的连通分组有 8 个：binary、hash、AVL、stack、graph、quick、insertion、merge。划分开发/测试集与重采样时必须按来源连通组；同一 family 的两种语言和全部口语等级不可拆分。
- 12 个信息需求与 8 个来源组规模较小，足以支持局部压力测试，不支持宣称跨课程普适最优。

## 后续变体作者的信息隔离

应向变体作者仅提供 `family_id`、`queries`、`query_ids`（可选 `concepts`），不得提供证据、正文或任何检索排名。L0–L4 的定义、是否仍可唯一识别意图，以及歧义输入的期望行为，应在运行模型前固定。不能把歧义输入强行继承为唯一正确查询；应单独评估澄清或避免擅自补全的行为。

本阶段未构造任何口语变体，也未为策略选择查看模型输出。后续协议、变体和实验结果需分别冻结并标注 AI 辅助属性。
