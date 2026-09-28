# 思考强度与输出 token 上限验证

## 当前本机配置与问题

2026-09-24 本次读取 `Settings.from_env()`：模型为 `deepseek-flash`、运行时为 `deepseek_harness`，`thinking=disabled`、`HARNESS_REASONING_EFFORT=off`。`TEXT_EXTRA_JSON.max_tokens=6000`，Harness 保护上限为 8192；提供商适配器最后合并文字接口配置，因此当前请求的实际输出上限为 6000。以上是当前配置，不是对既有服务进程已经重载的声明。

官方将思考开关/强度和输出 token 上限分为不同参数；当前文档列出 low/high/max。项目固定 Harness 适配器目前只验证了 off/high，不直接启用 max。[官方思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)、[官方 Chat Completions 参数](https://api-docs.deepseek.com/api/create-chat-completion/)

本项目把思考和最终 JSON 放在同一个输出预算内。R6 的 high + 8192 作者响应实际用满 8192 completion tokens，其中 7351 是 reasoning tokens，`finish_reason=length`，最终 JSON 被截断。它不证明 high 质量差，而是证明该响应的单次预算不够。

## 本轮验证

保留原英文虚构材料、目标 hard、同一应用代码与 high；每次输出上限从 8192 提到 **16384**，同时对齐文字接口和 Harness 两处上限。任务仍在隔离数据库中，正式 `.env` 未改。

| 轮次 | 单任务调用上限 | 实际调用 | 总 tokens | 截断 | 结果 |
| --- | ---: | ---: | ---: | --- | --- |
| [R7](R7_HIGH16K_20260924/results.json) | 6 | 6 | 66,608 | 无 | 首稿判 medium；第二稿解题判 hard，但最终复核前额度耗尽，无完整草稿 |
| [R8](R8_HIGH16K_20260924/results.json) | 12 | 10 | 114,964 | 无 | 生成完整草稿，实际接受为 medium，标记难度调整 |

R7 作者曾使用 **9521** completion tokens，其中 **7744** reasoning tokens；R8 最长响应使用 **10913** completion tokens，其中 **8736** reasoning tokens。这两条完整响应都超过原先 8192 总预算。16 次请求都返回完整响应，没有观察到 token 截断；不能据此保证所有任务用 16384 都足够。

本轮合计 **16 次调用、181,572 tokens**，低于 18 次计划上限；费用字段均缺失。R7 墙钟时间 166.2 秒，R8 246.7 秒，包含其实际规划、写作、解题、复核和修订。不同任务停止点与随机候选不同，不能拿它们直接作准确率或速度排名。

## 结论及配置处理

1. **增加单次上限有用：**它解决了这批 high 响应的截断；多给调用次数不能补全已经截断的同一响应。
2. **调用额度是另一层限制：**R7 的第二稿还需最终复核时触及 6 次额度；R8 保留 12 次上限，才有空间完成多轮修订。
3. **思考更多仍未解决困难题稳定性：**R8 交付为 medium，不能写成 hard 成功。参考答案还把内容未知的信件称为 family-related，属于需要教师核对的推断；模型通过不等于事实完全可靠。[可读草稿](R8_HIGH16K_20260924/DRAFT_EN_ADJUSTED.md)
4. **后续实验默认：**`runtime_paired_comparison.py` 的 high 默认输出上限改为 16384，off 仍为 8192，显式参数可覆盖以保留旧条件。若再次出现 `finish_reason=length`，可单独研究 32768；当前没有证据要求立即扩大到该值。

本机正式生成配置仍保持 off/6000，未把本轮局部实验当作 high 总体优于 off 的证明。若后续切换本机 high，必须同时对齐 `HARNESS_REASONING_EFFORT`、文字接口的 thinking/reasoning_effort，以及两处 max_tokens；仅提高 Harness 保护上限仍可能被文字接口的较低值限制。
