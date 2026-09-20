# H5：思考模式与 JSON 输出兼容性核查

核查日期：2026-09-19。范围：官方文档、当前安装的 Harness 0.1.5-rc.1 适配器源码。此核查没有调用付费模型，不构成线上兼容性或正确率实验结果。

## 官方 API 的当前约定

- `thinking.type=enabled` 配合 `reasoning_effort=high` 可开启思考。思考支持工具调用；携带 `tools` 的后续请求必须完整回传之前所有 assistant 的 `reasoning_content`，包括没有调用工具的轮次，缺失可能导致 400。思考模式下 `temperature` 不生效。[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- Chat Completions 的 `response_format` 支持 `text` 和 `json_object`；该接口未列出最终消息使用的 `json_schema`。思考时不能强制 `tool_choice=required` 或指定函数；`auto`/`none` 不受这条限制。工具参数的 Beta `strict` 与最终消息 JSON 格式是不同能力。[Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
- JSON 模式仍需在 system/user 提示中明确要求 JSON 并提供预期格式示例；官方也提醒空 content 与长度截断的问题。合法 JSON 不能代替字段校验、题目条件核查或答案验证。[JSON Output](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)

上述文档同时列出思考、工具、JSON 能力，但本次核查未找到展示三者联合请求的官方完整示例。因此只能先认定参数定义不冲突；当前模型的联合请求及工具后的 JSON 最终输出必须由有界真实探针验证，不能用文档或假服务测试代替。

## 已安装适配器的源码证据

检查的是 H4B 运行时提取出的官方包，未修改该包：

```
docs/agent/harness-experiments/H4B_20260919/runtime/harness/native-cache/pkg/9534cde445a865250eb7bc8cfe5e231f3f91d0fda3f4aaa694e81f3531ad1130/@deepseek-ai/dsh-llm-deepseek/
```

`package.json` 的版本为 `0.1.5-rc.1`。`lib/index.js` 共 92,373 字节，SHA-256：

```
b626da3d27cca74336f4980b5d99e1baf1e970c8f06c578b38d0494829641065
```

下表行号均相对于上述 `lib/index.js`：

| 位置 | 实际行为 | 对本项目的含义 |
| --- | --- | --- |
| 26–40 `reasoningEffort` / `resolveThinking` | 接受 `off/low/high/max`；`off` 转为 disabled；`high` 转为 enabled 与同名 effort | profile 应显式使用 `thinking: enabled`、`reasoningEffort: high`，而不是只修改应用提示词 |
| 108–124 `serializeAssistant` | 拼接该 assistant 的 reasoning blocks，非空时写入 `reasoning_content` | 已有回传能力，无需伪造思考文本 |
| 134–147 `serializeMessages` | 对每条 assistant 使用上述序列化 | 并非只回传最近一个工具调用轮次 |
| 227–248 `requestWithMessages` | 写入 thinking/effort/tools/max_tokens；工具只序列化 name、description、parameters | 未映射 `response_format`、`tool_choice`、工具 `strict`；JSON 模式需要在受控转发层显式加入 |
| 1255–1272 SSE 解析 | `delta.reasoning_content` 转为 reasoning block 与 reasoning delta | 转发层必须保留这个字段，不能只发送 content/tool_calls |
| 1884–1894 配置 schema | 包含 thinking、reasoningEffort、maxTokens | 可以直接使用正式配置，不需修改官方包 |
| 1962–1963 配置约束 | disabled 与非 off effort 冲突会报错 | 配置校验与测试应覆盖冲突组合 |

最新版 [官方包说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-deepseek/README.md) 也说明回传 reasoning 和 effort 配置，但其 `master` 已包含额外协议实现。不能把最新 `master` 的能力全部算作本机 0.1.5-rc.1 已安装能力；本表以本机文件为准。

## 建议实现边界

1. 同步设置 Harness profile 与转发层允许的 thinking/effort；禁止子进程绕过设定的模型、令牌上限与调用预算。
2. 转发层传递 `response_format={"type":"json_object"}`，阶段提示明确展示允许字段。继续进行严格 JSON 对象解析和业务 schema 校验；不给语法正确的空对象或多余字段自动放行。
3. 在工具循环中原样保留模型返回的 reasoning 字段供下一轮使用；不要将它拼入最终 JSON，也不要作为公开质量证明展示。单轮最终响应只解析 `content`。
4. 把空输出、截断、JSON 语法错误、字段错误、工具错误和答案错误分别记录。思考会消耗输出预算，因此保留 reasoning token 统计与结束原因，不能把 `finish_reason=length` 的残缺 JSON 当成普通格式失败。
5. 若以后需要格式修复，单独计费、限制次数并重新验证语义；本次不能通过随意截取大括号、丢弃额外文本来掩盖协议不合格。

## 最小验证清单

- 假上游 + 真实 Harness：第一次返回 reasoning 与工具调用，第二次确认同一 reasoning 被完整回传，再返回合法 JSON。
- 多轮 assistant reasoning 保留；最终 JSON 解析不混入 reasoning 文本。
- profile enabled/high 在实际 wire 中一致；off 不写非法的 `reasoning_effort=off`；disabled/high 提前拒绝。
- 转发后的每个受控请求具有预期 JSON 模式；未授权字段、模型、工具和超预算请求仍然拒绝。
- 空 content、length、多个 JSON 值、非对象、额外说明、缺失字段/多余字段均留下失败证据，不能发布题目。
- 有界真实探针：核实 high + 工具 + JSON 的联合请求；必须同时记录是否真的发生工具调用，HTTP 200 本身不足以证明完整循环成功。

本记录只给出已核实的协议和源码结论。H5 实际修改、测试数量与真实调用结果由本轮验收记录另行提供。
