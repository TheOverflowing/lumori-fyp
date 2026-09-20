# R8 融合与追问实验复现

R8A 和 R8B 是两项独立实验，不合并成一个改进百分比。A 重用 R7 的已见数据研究融合；B 使用已见教材中的新问题研究单次模拟追问。

## R8A：无需网络或新增模型调用

归档目录：`docs/rag/r8a-experiments/20260920T015309811007Z/`。

```sh
.venv/bin/python scripts/r8_fusion.py
```

脚本在新时间戳目录记录新一次本地计算，先核验 R7 基线一致性，禁止网络。源文本、改写、向量相同，不代表新增独立模型实验。图可由 `scripts/r8_fusion_plot.py` 根据已存 CSV/JSON 重建；绘图需要 matplotlib，实验本身不依赖该包。

## R8B：现有 API 输出的离线重放

有效归档目录：`docs/rag/r8b-experiments/20260920T020637637502Z/`。

```sh
.venv/bin/python scripts/r8_clarification_verify.py \
  --run docs/rag/r8b-experiments/20260920T020637637502Z
```

校验器在临时副本内禁用网络、禁止构造远程客户端，重新生成三臂候选、首阶段指标、分层统计、配对区间和成本汇总，与归档逐项比较。只排除本地重新计算的 `ranking_ms`；原始账本与实验文件不变，仅写新的验证记录。应先确认归档已完成 `per-query.json`、`summary.json` 及 `report.md`。

冻结校验包含代码。如果以后修改过脚本，应在隔离目录中使用归档 `code/` 的版本，补齐匹配版本的依赖及原始来源路径；不要关闭校验或把新代码算出的结果覆盖旧记录。该档案保存可复核代码与证据，但不是无需配置的独立部署包。

角色数据边界：`query-inputs.json` 只有可见文本和语言；`profiles.json` 只供模拟用户。`role-inputs.json` 记录实际发送的角色投影，`interactions.json` 保存响应及状态。`effective-queries.json` 记录追问解决、未解决及回退。嵌入批次按完整输入哈希与响应文件哈希绑定；排名只使用各臂合法获得的查询。

人工充分性/风格标签、隐藏 profile、标准问题及证据 span 都不能传给决策器或改写器。语义审阅单独读取不含排名的投影，不能把 AI 审阅改称人工金标。

## 主动重新调用模型属于新实验

`freeze` / `interact` / `embed` 是创建或执行在线实验的阶段，可能产生费用。离线复现不需要执行它们。新的模型响应可能改变；不得将旧账本删掉、对失败反复生成后挑选成功结果，或者将新数据作为原实验的补丁。

原研究设计见 [R8B V1 协议](R8B_PROTOCOL_V1.md)，有效运行使用 [V2 请求契约修订](R8B_PROTOCOL_V2.md)。首次尝试 `20260920T020110436365Z` 因 JSON 模式请求格式错误全部 HTTP 400，连同一次诊断共 129 次失败尝试，单独保留 [中止记录](r8b-experiments/20260920T020110436365Z/ABORTED.md)。该目录没有有效排名，不是待重放的实验结果。修订只补齐 JSON 提示字样和永久错误停止逻辑，未改变数据、策略内容或评分规则。

未知金额保留未知；模拟用户的 token/费用与潜在产品模型开销分列。没有重排或最终内容生成，不能用该实验报告后两阶段的质量或在线时延。

## 图表复现

安装 matplotlib 后，根据现有统计输出绘图，不调用模型：

```sh
.venv/bin/python scripts/r8_clarification_plot.py \
  --run docs/rag/r8b-experiments/20260920T020637637502Z
```

生成白底 PNG/PDF/SVG 及输入、绘图脚本和图片的哈希清单。图中 `resolved` 是模型自报状态，必须结合 [回复审阅](R8B_REPLY_AUDIT_20260920.md)，不能等同于真正解决用户问题。图表是原数据的展示，不是新增实验。汇总结论见 [R8B 结果](R8B_RESULTS_20260920.md)。
