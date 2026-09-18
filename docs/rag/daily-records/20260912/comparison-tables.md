# 2026-09-12 原始汇总值对照表

由各轮已保存的数值文件直接导出。本表没有新调用、重新评分或改变选型。不同轮次、数据、预算的成绩不构成可直接相减的时间序列。
CSV 保存原始小数；百分比表仅做显示舍入。R4 本地 0.6B 未运行保留集，空白不填成零。

## R1

| 划分 | 方法 | 可答题数 | Recall@5 | Hit@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|---:|---:|
| dev | dense_v1 | 14 | 98.21% | 100.00% | 0.9643 | 0.9486 |
| dev | bm25_v1 | 14 | 46.43% | 78.57% | 0.7500 | 0.5807 |
| dev | hybrid_rrf_v1 | 14 | 46.43% | 78.57% | 0.7500 | 0.5785 |
| dev | hybrid_mmr_v1 | 14 | 46.43% | 78.57% | 0.7500 | 0.5785 |
| test | dense_v1 | 14 | 90.48% | 100.00% | 0.9643 | 0.9330 |
| test | bm25_v1 | 14 | 46.43% | 78.57% | 0.7857 | 0.6122 |
| test | hybrid_rrf_v1 | 14 | 46.43% | 78.57% | 0.7857 | 0.6140 |
| test | hybrid_mmr_v1 | 14 | 46.43% | 78.57% | 0.7857 | 0.5992 |

原始来源：[R1 数值](../../../rag/experiments/20260912T053716373758Z/metrics.json)

## R2_MLQA

| 划分 | 方法 | 可答题数 | Recall@5 | Hit@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|---:|---:|
| dev | dense_v1 | 12 | 70.83% | 75.00% | 0.6944 | 0.6922 |
| dev | bm25_v1 | 12 | 50.00% | 100.00% | 0.7778 | 0.5122 |
| dev | hybrid_rrf_v1 | 12 | 50.00% | 100.00% | 0.8611 | 0.5499 |
| dev | hybrid_mmr_v1 | 12 | 50.00% | 100.00% | 0.8361 | 0.5374 |
| dev | hybrid_dense_lexical_v1 | 12 | 79.17% | 91.67% | 0.7500 | 0.7366 |
| test | dense_v1 | 80 | 91.25% | 96.25% | 0.8858 | 0.8737 |
| test | bm25_v1 | 80 | 47.50% | 90.00% | 0.7775 | 0.5100 |
| test | hybrid_rrf_v1 | 80 | 61.25% | 95.00% | 0.8875 | 0.6365 |
| test | hybrid_mmr_v1 | 80 | 50.00% | 93.75% | 0.8723 | 0.5599 |
| test | hybrid_dense_lexical_v1 | 80 | 91.88% | 100.00% | 0.9390 | 0.8907 |

原始来源：[R2_MLQA 数值](../../../rag/experiments/20260912T055718752885Z/metrics.json)

## R2_T2

| 划分 | 方法 | 可答题数 | Recall@5 | Hit@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|---:|---:|
| dev | dense_v1 | 10 | 43.76% | 90.00% | 0.7333 | 0.6155 |
| dev | bm25_v1 | 10 | 38.80% | 90.00% | 0.7333 | 0.5643 |
| dev | hybrid_rrf_v1 | 10 | 45.43% | 90.00% | 0.7833 | 0.6491 |
| dev | hybrid_mmr_v1 | 10 | 40.46% | 90.00% | 0.8000 | 0.5753 |
| dev | hybrid_dense_lexical_v1 | 10 | 46.46% | 90.00% | 0.6833 | 0.6157 |
| test | dense_v1 | 10 | 40.58% | 100.00% | 0.7333 | 0.6488 |
| test | bm25_v1 | 10 | 37.31% | 100.00% | 0.6450 | 0.5662 |
| test | hybrid_rrf_v1 | 10 | 47.02% | 100.00% | 0.7450 | 0.6960 |
| test | hybrid_mmr_v1 | 10 | 28.29% | 90.00% | 0.7083 | 0.5329 |
| test | hybrid_dense_lexical_v1 | 10 | 44.74% | 100.00% | 0.7167 | 0.6756 |

原始来源：[R2_T2 数值](../../../rag/experiments/20260912T055800717636Z/metrics.json)

## R3

| 方法 | 约束 | 划分 | n | 答案跨度 Hit | 平均返回片段 | 平均正文字符 |
|---|---|---|---:|---:|---:|---:|
| legacy1200_dense | top5 | all | 92 | 93.48% | 5.00 | 2228.1 |
| legacy1200_dense | top5 | dev | 12 | 75.00% | 5.00 | 2592.0 |
| legacy1200_dense | chars6000 | all | 92 | 98.91% | 13.14 | 5695.8 |
| legacy1200_dense | chars6000 | dev | 12 | 91.67% | 11.75 | 5658.6 |
| legacy1200_dense | top5 | test | 80 | 96.25% | 5.00 | 2173.5 |
| legacy1200_dense | chars6000 | test | 80 | 100.00% | 13.35 | 5701.4 |
| recursive1200_dense | top5 | all | 92 | 93.48% | 5.00 | 2242.5 |
| recursive1200_dense | top5 | dev | 12 | 75.00% | 5.00 | 2560.8 |
| recursive1200_dense | chars6000 | all | 92 | 98.91% | 13.33 | 5732.0 |
| recursive1200_dense | chars6000 | dev | 12 | 91.67% | 12.08 | 5800.4 |
| recursive1200_dense | top5 | test | 80 | 96.25% | 5.00 | 2194.8 |
| recursive1200_dense | chars6000 | test | 80 | 100.00% | 13.51 | 5721.8 |
| recursive800_dense | top5 | all | 92 | 94.57% | 5.00 | 1977.4 |
| recursive800_dense | top5 | dev | 12 | 91.67% | 5.00 | 2100.5 |
| recursive800_dense | chars6000 | all | 92 | 97.83% | 14.77 | 5741.0 |
| recursive800_dense | chars6000 | dev | 12 | 100.00% | 14.25 | 5780.6 |
| recursive800_dense | top5 | test | 80 | 95.00% | 5.00 | 1958.9 |
| recursive800_dense | chars6000 | test | 80 | 97.50% | 14.85 | 5735.1 |
| recursive1200_hybrid | top5 | all | 92 | 98.91% | 5.00 | 2236.9 |
| recursive1200_hybrid | top5 | dev | 12 | 91.67% | 5.00 | 2554.6 |
| recursive1200_hybrid | chars6000 | all | 92 | 100.00% | 13.55 | 5698.1 |
| recursive1200_hybrid | chars6000 | dev | 12 | 100.00% | 12.58 | 5825.2 |
| recursive1200_hybrid | top5 | test | 80 | 100.00% | 5.00 | 2189.3 |
| recursive1200_hybrid | chars6000 | test | 80 | 100.00% | 13.70 | 5679.0 |
| recursive1200_metadata | top5 | all | 92 | 98.91% | 5.00 | 2224.5 |
| recursive1200_metadata | top5 | dev | 12 | 91.67% | 5.00 | 2554.6 |
| recursive1200_metadata | chars6000 | all | 92 | 100.00% | 13.58 | 5723.2 |
| recursive1200_metadata | chars6000 | dev | 12 | 100.00% | 12.58 | 5825.2 |
| recursive1200_metadata | top5 | test | 80 | 100.00% | 5.00 | 2174.9 |
| recursive1200_metadata | chars6000 | test | 80 | 100.00% | 13.72 | 5707.9 |

## R4：全部 16 个开发集配置

每个 dev 配置为 184 个场景；已运行的 test 配置各 168 个场景。MRR 使用叶片段排名。
R4 API 行的 candidate_hit20 含接口失败，不能当作纯首阶段覆盖；纯首阶段查看 token_hybrid。

| 方法 | dev Hit | dev MRR | test Hit | test MRR | test 平均原文 token |
|---|---:|---:|---:|---:|---:|
| baseline | 88.04% | 0.8053 | 97.02% | 0.8868 | 493.4 |
| query_instruction | 95.65% | 0.8463 | 97.02% | 0.9484 | 598.7 |
| title | 90.22% | 0.8207 | 95.24% | 0.9008 | 527.4 |
| title_instruction | 95.65% | 0.8633 | 96.43% | 0.9233 | 612.5 |
| char_hybrid | 92.39% | 0.8303 | 97.62% | 0.9035 | 503.2 |
| token256 | 87.50% | 0.8006 | 96.43% | 0.8826 | 490.7 |
| token128 | 86.96% | 0.8020 | 98.21% | 0.8949 | 369.1 |
| token_title_instruction | 96.20% | 0.8576 | 96.43% | 0.9243 | 612.8 |
| token_hybrid | 96.20% | 0.8678 | 96.43% | 0.9334 | 608.3 |
| rerank_none | 96.74% | 0.9248 | 未运行 | 未运行 | 未运行 |
| rerank_parent | 96.74% | 0.9248 | 未运行 | 未运行 | 未运行 |
| token_rrf | 95.11% | 0.8082 | 96.43% | 0.8504 | 602.4 |
| token_parent | 96.20% | 0.8678 | 96.43% | 0.9334 | 631.1 |
| token_window | 96.20% | 0.8678 | 96.43% | 0.9334 | 618.2 |
| api8b_none | 98.37% | 0.9570 | 97.02% | 0.9524 | 553.4 |
| api8b_parent | 98.37% | 0.9570 | 97.02% | 0.9524 | 591.8 |

## R4：配置含义

| 方法 | 切分 | 标题编码 | 查询指令 | 首阶段 | 扩展 |
|---|---|---|---|---|---|
| baseline | char1200 | False | False | dense_v1 | none |
| query_instruction | char1200 | False | True | dense_v1 | none |
| title | char1200 | True | False | dense_v1 | none |
| title_instruction | char1200 | True | True | dense_v1 | none |
| char_hybrid | char1200 | False | False | hybrid_dense_lexical_v1 | none |
| token256 | token256 | False | False | dense_v1 | none |
| token128 | token128 | False | False | dense_v1 | none |
| token_title_instruction | token256 | True | True | dense_v1 | none |
| token_hybrid | token256 | True | True | hybrid_dense_lexical_v1 | none |
| token_rrf | token256 | True | True | hybrid_rrf_v1 | none |
| token_parent | token256 | True | True | hybrid_dense_lexical_v1 | parent |
| token_window | token256 | True | True | hybrid_dense_lexical_v1 | window |

rerank_none / rerank_parent 在 token_hybrid 的相同 Top20 上加入本地 Qwen3-Reranker-0.6B；api8b_none / api8b_parent 加入云端 Qwen3-Reranker-8B。后两组由保留集曝光前的补充协议加入。

## R5

| 划分 | 方法 | n | 预算 Hit | MRR@5 | 重排前 Hit@20 | 失败场景 | 阶段合成平均 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | original | 96 | 98.96% | 0.9844 | 98.96% | 0 | 1973.2 |
| dev | translated | 96 | 98.96% | 0.9844 | 98.96% | 0 | 2721.4 |
| dev | dual | 96 | 97.92% | 0.9740 | 98.96% | 1 | 2883.2 |
| test | original | 124 | 87.90% | 0.8602 | 92.74% | 6 | 3551.8 |
| test | translated | 124 | 89.52% | 0.8777 | 94.35% | 6 | 3838.2 |
| test | dual | 124 | 88.71% | 0.8696 | 94.35% | 8 | 4850.5 |

## 研究运行调用账目

仅下列固定研究运行；R4 含 1 次重排探测。排除 CA1、难度验收、应用索引迁移、模型下载及离线重放。cost 为已返回金额合计，缺失不代表免费。

| 运行 | 嵌入 | 翻译/文字 | 重排 | 请求失败 | 已返回 cost | cost 缺失次数 |
|---|---:|---:|---:|---:|---:|---:|
| R1 | 5 | 0 | 0 | 0 | 0.00006321 | 0 |
| R2_MLQA | 12 | 0 | 0 | 0 | 0.00012236 | 0 |
| R2_T2 | 24 | 0 | 0 | 0 | 0.00226145 | 0 |
| R3 | 4 | 0 | 0 | 0 | 0.00007121 | 0 |
| R4 | 42 | 0 | 353 | 7 | 0.29398760 | 7 |
| R5 | 222 | 110 | 660 | 21 | 0.56427819 | 131 |

合计 1432 次 API 尝试；已返回 cost 合计 0.86078402，不代表账号全天或合并完整账单。

