# R4 协议补充 2：加入可用的 OpenRouter Qwen8B 专用重排

记录时间：2026-09-12T07:57:44.282371+00:00。本地 dev 重排已完成 166/184；尚未汇总其质量，尚无选择锁和 test 排名。

发现并真实探测 OpenRouter /api/v1/rerank 支持 qwen/qwen3-reranker-8b。首次公共示例请求 HTTP 200；记录见 openrouter-rerank-probe.json。官方参考：https://openrouter.ai/qwen/qwen3-reranker-8b 与 https://openrouter.ai/docs/api/api-reference/rerank/create-rerank （文档搜索可见，正文抓取曾 404，以真实请求验证为准）。

新增 api8b_none、api8b_parent 两组，共用原 dev 选出的 token_hybrid Top20 候选。同一原始 query、标题编码文档、top_n=全部候选；使用服务默认重排提示，接口不提供本地版本的自定义指令参数，因此比较的是完整 API 方案而不是纯参数规模消融。返回 relevance_score 按文档 index 映射；保留实际服务模型、provider、用量与耗时。不把 0–1 分数当校准正确率。

dev 完整运行 184 请求，最多并发 2、单次超时 60 秒；无自动重试。失败的请求保留失败记录，主要操作指标按空证据/0 命中计；不能只在成功子集计算主成绩。若 API 方案最终胜出，才在 test 运行 168 请求。总计最多 352 个数据集请求及 1 个探测请求，额外最多 1 USD；按已公开 0.20 USD/百万 token 估计，单请求预留 0.01 USD，逐次核对真实 usage.cost，未知计费停止批量运行。

仍按原 dev 规则选择：预算 Hit、MRR、无重排、较少上下文、预定顺序。顺序为原 12 组、本地 rerank_none、rerank_parent、api8b_none、api8b_parent。新的 API 候选不能在看到 test 后加入。默认升级门槛、数据、token 预算和 bootstrap 均不改变。

原冻结代码不修改。扩展脚本单独冻结为 remote-extension-code.py，哈希记录于 remote-extension.json；全部原始/补充协议并存。
