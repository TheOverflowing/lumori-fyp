# 自动探索实现验证 · 2026-09-20

## 自动化回归

最终一次相关后端回归：**501 passed, 2 warnings in 61.53s**。警告来自现有 Starlette/httpx 和 anyio 接口弃用提示。以下测试使用隔离数据及模拟响应，不调用真实模型或搜索接口。

```sh
.venv/bin/python -m pytest -q tests/test_exploration_sources.py tests/test_auto_exploration.py tests/test_exploration_contract.py tests/test_exploration_resume.py tests/test_generation_agent.py tests/test_query_fusion_runtime.py tests/test_generation_preparation.py tests/test_job_progress.py tests/test_document_ingestion.py tests/test_document_lifecycle.py tests/test_account_isolation.py tests/test_agent_resume_api.py tests/test_workflow.py tests/test_figure_pipeline.py tests/test_cpu_spec_agent.py tests/test_flexible_agent.py tests/test_supervisor_agent.py
```

覆盖下载地址和重定向校验、下载大小及超时、许可识别、256 层 HTML 许可解析上限、缺口清单冻结、原文引文匹配、候选筛选、预算、重复及禁用资料、中断恢复、账号隔离、来源在重新解析与重建索引后的延续、JSON/Markdown 导出，以及已有问答生成、融合和进度流程。19 项根接口专项已包含在 501 项内；此前各次运行不重复计数。

前端整套检查：**125 passed, 0 failed**，包含 9 项探索专项。

```sh
node --test tests/frontend_*.test.mjs
```

Python 语法编译与 `git diff --check` 同时通过。以上只描述本轮实际执行的检查范围，不声称全部项目测试或模型质量评估已经完成。

最终代码散列见 [implementation-manifest-20260920.json](implementation-manifest-20260920.json)，覆盖 21 个主要实现文件；该清单标记收尾后的版本，不冒充前面真实试跑时的完整代码快照。两份试跑 JSON 已通过 JSON 解析及凭据模式检查。

## 浏览器与本地服务

独立模拟服务验证详情及浅色截图见[界面记录](../../ui/auto-exploration-20260920/README.md)。模拟账号与资料在临时数据目录中，未写入正常账号。

确认正常课程数据库没有排队或运行中的任务后，使用 `run.command` 启动更新后的 8765 服务。首页与新增前端模块响应 200；未登录访问 `/api/status` 响应 401，保持认证边界。服务启动完成不代表外部提供方永远可用。

随后在浏览器已有登录会话中打开真实项目的生成页，确认原有课程可见，设置显示自动探索开关默认关闭、资料搜索为“Public course directory / Available”。此检查只读取真实账号页面，未发起生成或改变开关。临时 8767 模拟服务在核验后停止，浏览器保留 8765 项目页。

## 外部连接与效果证据

真实来源和模型试跑见[完整记录](SMOKE_RESULTS_20260920.md)。另有公开源下载与正文解析开发检查：中文 Hello Algo 快速排序作者 Markdown（6,573 字节，3,207 解析字符）、OpenStax 进程章节（321,606 字节，32,340 字符）、BCcampus 数据库规范化（86,270 字节，12,462 字符）、Python 数据结构（101,544 字节，23,649 字符）。这些为当时开发检查的返回值，未构成冻结语料集，也不据此计算文档解析成功率。

默认 `curated` 是网址目录检索后读取真实网页；本轮没有配置或真实调用 Brave 全网搜索。AI 覆盖判断与字符串引文检查不能替代独立语义评价。知识覆盖率、引用支持率、合理停止率及资源开销的正式对照实验按[协议](../AUTO_EXPLORATION_V1.md)后续执行。
