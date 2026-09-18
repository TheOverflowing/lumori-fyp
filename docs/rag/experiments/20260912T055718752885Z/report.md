# RAG 检索实验记录

运行：20260912T055718752885Z

本轮仅比较检索排序。嵌入模型、查询文本、固定片段、候选语料与评测标注相同。
标注状态：public_human_qa_derived。相关性与证据组由公开人工问答数据的支持关系转换得到；这不是穷尽的人工检索 qrels，也不表示教师逐一复核了候选片段。
评价范围：Known human answer-bearing source coverage in a small mixed-language Wikipedia CS slice; not exhaustive passage relevance, not university-course gold, not official MLQA answer-span F1. Each query has two known sources in one alternative evidence group; all_evidence@k equals hit@k here. Translated question pairs are dependent families; query-level bootstrap is descriptive only. No query-language restriction forces cross-language retrieval and no unanswerable instances are included.

资料片段 81；查询 92；嵌入模型 qwen/qwen3-embedding-8b；维度 4096。
本次新增 API 尝试：12。各策略复用完全相同的已缓存向量；排序耗时不包含嵌入网络耗时。

Recall 按已标注为相关的片段计算；完整证据率按数据声明的证据组计算。公开 QA 或相关性派生组未必代表所有必要答案部分，应结合评价范围解释。不可答查询单独统计，不进入召回均值。

## dev 固定划分

| 策略 | Recall@5 | 完整证据率@5 | nDCG@5 | MRR@5 | 成功查询本地排序中位数 ms |
|---|---:|---:|---:|---:|---:|
| dense_v1 | 70.83% | 75.00% | 69.22% | 69.44% | 21.160 |
| bm25_v1 | 50.00% | 100.00% | 51.22% | 77.78% | 27.489 |
| hybrid_rrf_v1 | 50.00% | 100.00% | 54.99% | 86.11% | 27.588 |
| hybrid_mmr_v1 | 50.00% | 100.00% | 53.74% | 83.61% | 28.918 |
| hybrid_dense_lexical_v1 | 79.17% | 91.67% | 73.66% | 75.00% | 27.518 |

- bm25_v1 对比 dense_v1：Recall@5 差 -20.83 个百分点；配对 bootstrap 95% 区间（百分点）：[-41.66666666666667, 4.166666666666666]。
- hybrid_rrf_v1 对比 dense_v1：Recall@5 差 -20.83 个百分点；配对 bootstrap 95% 区间（百分点）：[-41.66666666666667, 4.166666666666666]。
- hybrid_mmr_v1 对比 dense_v1：Recall@5 差 -20.83 个百分点；配对 bootstrap 95% 区间（百分点）：[-41.66666666666667, 4.166666666666666]。
- hybrid_dense_lexical_v1 对比 dense_v1：Recall@5 差 +8.33 个百分点；配对 bootstrap 95% 区间（百分点）：[0.0, 20.833333333333336]。

## test 固定划分

| 策略 | Recall@5 | 完整证据率@5 | nDCG@5 | MRR@5 | 成功查询本地排序中位数 ms |
|---|---:|---:|---:|---:|---:|
| dense_v1 | 91.25% | 96.25% | 87.37% | 88.58% | 21.160 |
| bm25_v1 | 47.50% | 90.00% | 51.00% | 77.75% | 27.489 |
| hybrid_rrf_v1 | 61.25% | 95.00% | 63.65% | 88.75% | 27.588 |
| hybrid_mmr_v1 | 50.00% | 93.75% | 55.99% | 87.23% | 28.918 |
| hybrid_dense_lexical_v1 | 91.88% | 100.00% | 89.07% | 93.90% | 27.518 |

- bm25_v1 对比 dense_v1：Recall@5 差 -43.75 个百分点；配对 bootstrap 95% 区间（百分点）：[-49.375, -37.5]。
- hybrid_rrf_v1 对比 dense_v1：Recall@5 差 -30.00 个百分点；配对 bootstrap 95% 区间（百分点）：[-36.875, -23.75]。
- hybrid_mmr_v1 对比 dense_v1：Recall@5 差 -41.25 个百分点；配对 bootstrap 95% 区间（百分点）：[-46.875, -35.625]。
- hybrid_dense_lexical_v1 对比 dense_v1：Recall@5 差 +0.62 个百分点；配对 bootstrap 95% 区间（百分点）：[-2.5, 3.75]。

## 解释与边界

- dev 与 test 使用数据文件声明的划分；本运行不重新划分、修改标注或调参。是否构成独立保留测试集需结合评价范围与冻结协议判断。
- 标注来源及覆盖边界见上文；本运行没有实施新的人工或教师审核，公开来源也不自动保证样本代表性或 qrels 穷尽性。
- 所有预先声明的策略和退步查询均保留；没有只导出提升案例。相对提升与绝对百分点在 comparisons.json 中分开保存。
- 未实现检索级拒答阈值。不可答查询的空返回率见 metrics.json；返回片段不代表生成模型一定会编造答案。
- 排序时间包含本次本地算法、词法统计与归一化开销；不等于用户请求总延迟，纯 BM25 的算法比较也复用缓存向量以保留余弦诊断。
- 外部 benchmark 的结果限于其声明的任务与候选池；面向真实课程的结论还需要课程评测、适当标注及独立测试设计。这些结果不证明学习效果。

## 文件

- dataset.json / protocol.md：本次冻结的数据与协议。
- embedding-cache.json：提供商实际返回的向量，支持无需 API 的离线复现。
- metrics.json / rankings.json / comparisons.json：各方法、分组、逐题指标及本次保存的最终排名。
- metrics.csv / per-query.csv / changes.csv：可用于作图、统计和失败分析的表格。
- annotation-review.csv：空白人工审阅表，没有自动填写人工评分。
- manifest.json / code/：调用、版本、参数、代码与数据校验值。
