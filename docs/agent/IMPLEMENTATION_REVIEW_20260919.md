# 教育生成 Agent 实现审查记录

日期：2026-09-19。范围：`app/generation_agent.py`，以及 `config.py`、`pipeline.py`、`store.py`、`main.py` 的接入路径；辅助阅读 `answer_tools.py`、模型 schema 和资料生命周期实现。

本轮只读应用代码，仅新增此审查记录。没有真实模型/API 调用，也没有修改应用。下面区分静态观察、离线复现和已看到的修复；不作为完整集成验收结果。

## 已发现并修复的事项

| 问题 | 原始影响 | 当前状态 |
| --- | --- | --- |
| 每任务调用上限只计 author/solve/review | 检索及其跨日恢复不受该上限限制；进度的 calls 不等于真实总调用数 | 已读到 `Store.reserve_call` 在事务内按 job 总 ledger 计数限制；progress 区分 text_call_attempts 与实际 calls |
| 恢复后按当前工作流设置重新路由 | 原 agent 任务若改为 legacy_v3，可能覆盖检查点并重做整批 | 已读到 pipeline 和 resume API 拒绝降级 |
| 完整工具 timeline 直接进入评审或修复 prompt | 支持范围内的合法输入也会超过上下文上限，无法进入复核或修复 | 已确认 review 与 repair 均使用精简视图，完整结果保存在 attempt.tool_results；800 区间离线回归通过，详见最终复查 |
| 非空 Review.issues 不影响通过 | 所有布尔值为 true 但 issues 指出错误的矛盾响应可能被接受 | 已读到非空 issues 产生 review_reported_issues 并拒绝 |
| author 作用域错误被当作题目结构错误 | 停用来源会消耗修复次数，误报 quality_failed | 已读到 call() 捕获作用域错误后写 scope_changed，从作者修复 catch 重新抛出 |

### 大型工具结果的离线复现

调用本项目已有的纯计算工具，无网络：RR，8 个进程同时到达，每个 burst=100，quantum=1，switch_cost=1，boundary=before，during_switch=tail，early_finish_free=false。

实际结果：**1599 个 timeline 区间，完整 result 序列化为 125,011 字符**。默认上下文上限 48,000，环境配置最高 100,000，所以原实现必然在 review 前停止。这是上下文契约不匹配的复现，不是模型质量实验。

## 修复反馈路径：已确认修复

原问题是下一次 author 从 `attempt.feedback` 原样组装 `repair_feedback`，只有 review_contract 精简了结果，导致大 timeline 可能重新进入修复 prompt。最终实现先将完整结果保存在 `attempt.tool_results`；`reject()` 复制 details 并为反馈构造 `tool_prompt_view`，因此不会覆盖完整原始结果。审查时的待确认项现已关闭。

两个拒绝入口复用这一 `reject()` 路径；此次回归实际运行并覆盖了 review 拒绝后的修复，不据此声称所有可能输入都完成了穷尽测试。

## 本次未发现明显绕过的边界

- resume API 复用现有 job owner 查询；恢复状态更新在事务内，只有失败任务能重新入队。
- worker 执行前检查任务与课程账号；每次新的模型调用前检查来源课程及启用/删除状态；发布事务再次检查来源有效性。
- 已持久化的模型响应会复用；未知的在途调用需要显式恢复，不在同一恢复轮次静默重试。结构错误允许的作者修复次数有限；solver/reviewer 协议错误会停止。
- 计算工具只有允许名单及严格、有限的输入，没有任意代码、网络或文件执行。

这些是源码审查结论，不是并发压测、崩溃注入或所有账号攻击场景的通过证明。工具输入与题干、答案与计算结果的对应关系仍由模型复核；当前 NOTE 已披露这个边界，不能把整题称为确定性正确性证明。

## 后续验证建议（不属于新发现的阻塞问题）

优先保留三种端到端离线测试：在作者/解题/复核各阶段中断后恢复且不重做已完成调用；停用来源后不调用供应商、不发布；同账号并发任务和跨日恢复都不能绕过 job/day 两级额度。对超长题干、答案、最近题目以及反馈分别测量 prompt 大小。当前近义重复检查主要覆盖最近 8 题，应将其视为覆盖限制，而不是已证明整套 50 题语义互异。

## 最终复查（2026-09-19）

已阅读最终 `tool_prompt_view`、`reject()` 及 `tests/test_generation_agent.py` 中的 `test_large_tool_timelines_stay_in_evidence_but_not_review_or_repair_prompts`，并实际运行该项：**1 passed in 0.21s**。这是纯离线 mock provider 测试，没有新增真实 API 调用。

该回归使用 8 个 burst=100 的 RR 进程、quantum=1、零切换开销，产生 **800 个运行区间**。断言覆盖：完整 timeline 在两次 attempt 的证据中保留；review、repair 与反馈视图明确省略 timeline、保留完整 per-process 指标并注明逐区间判断限制；第一次拒绝、第二次通过；共 6 次模拟文字调用；所有发给模型的序列化消息均小于 48,000 字符。它与前述非零切换开销产生 1599 个区间的缺陷复现属于不同 fixture，不能混写为同一个实验。

A1/A2 的真实调用账本另见 [A1_A2_LEDGER_20260919.json](A1_A2_LEDGER_20260919.json)。该账本核对原始 SQLite、各 case 导出、summary 和源文件快照，并记录各归档文件的 SHA-256；调用成功与内部题目质量门通过分开统计。
