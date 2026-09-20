# R8B 自动统计：选择性追问与首阶段检索

64条AI构造查询、8个新需求，已见教材；没有真实学习者、教师金标、重排或答案生成。
所有追问、unknown、未解决和回退均保留分母。下面两类指标分开，不能合成一个正确率。

## dev

| 输入 | 策略 | n | Hit@5 | MRR@20 | 追问 | resolved | unknown | 回退 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sufficient | original | 8 | 0.8750 | 0.6012 | 0 | 0 | 0 | 0 |
| sufficient | normalize | 8 | 1.0000 | 0.5833 | 0 | 0 | 0 | 0 |
| sufficient | selective | 8 | 1.0000 | 0.6458 | 0 | 0 | 0 | 0 |
| underspecified | original | 8 | 1.0000 | 0.6875 | 0 | 0 | 0 | 0 |
| underspecified | normalize | 8 | 1.0000 | 0.7708 | 0 | 0 | 0 | 0 |
| underspecified | selective | 8 | 1.0000 | 0.7083 | 1 | 1 | 0 | 0 |

underspecified 表示指定模拟用户意图下的证据匹配，不把其他合理解释判成错误。

## test

| 输入 | 策略 | n | Hit@5 | MRR@20 | 追问 | resolved | unknown | 回退 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sufficient | original | 24 | 0.8750 | 0.7662 | 0 | 0 | 0 | 0 |
| sufficient | normalize | 24 | 0.9167 | 0.7836 | 0 | 0 | 0 | 0 |
| sufficient | selective | 24 | 0.8750 | 0.7662 | 0 | 0 | 0 | 0 |
| underspecified | original | 24 | 0.8333 | 0.6363 | 0 | 0 | 0 | 0 |
| underspecified | normalize | 24 | 0.8333 | 0.5809 | 0 | 0 | 0 | 0 |
| underspecified | selective | 24 | 0.8333 | 0.6363 | 1 | 1 | 0 | 0 |

underspecified 表示指定模拟用户意图下的证据匹配，不把其他合理解释判成错误。

## test 配对差值

| 输入 | 比较 | 指标 | 差值 | 95%区间 | 改善/退步/持平 |
|---|---|---|---:|---|---|
| sufficient | normalize − original | pre_hit5 | +0.0417 | [+0.0000, +0.1250] | 1/0/23 |
| sufficient | normalize − original | pre_mrr20 | +0.0174 | [-0.0139, +0.0521] | 3/1/20 |
| sufficient | selective − original | pre_hit5 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| sufficient | selective − original | pre_mrr20 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| sufficient | selective − normalize | pre_hit5 | -0.0417 | [-0.1250, +0.0000] | 0/1/23 |
| sufficient | selective − normalize | pre_mrr20 | -0.0174 | [-0.0521, +0.0139] | 1/3/20 |
| underspecified | normalize − original | pre_hit5 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| underspecified | normalize − original | pre_mrr20 | -0.0554 | [-0.1179, -0.0011] | 1/3/20 |
| underspecified | selective − original | pre_hit5 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| underspecified | selective − original | pre_mrr20 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| underspecified | selective − normalize | pre_hit5 | +0.0000 | [+0.0000, +0.0000] | 0/0/24 |
| underspecified | selective − normalize | pre_mrr20 | +0.0554 | [+0.0011, +0.1179] | 3/1/20 |

按文档分量聚类，2000次bootstrap，种子20260920。小样本探索，没有多重校正。

## 调用与计费

| 能力 | 逻辑请求 | HTTP尝试 | 已知美元 | 金额未知尝试 | tokens |
|---|---:|---:|---:|---:|---:|
| text | 132 | 132 | 0.00000000 | 132 | 45565 |
| embedding | 9 | 9 | 0.00006857 | 0 | 6857 |
| rerank | 0 | 0 | 0.00000000 | 0 | 0 |

模拟用户reply角色的调用单列于costs.json；它是实验开销，不是产品中真人回答的模型成本。未知金额不等于零费用。

语义、回复支持与追问必要性须结合独立AI审阅；本自动统计不宣布上线或普遍最优。
