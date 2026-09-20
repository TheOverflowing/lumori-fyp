# 题前讲解选项与课程内容库验收

日期：2026-09-20。范围：测验／作业的可选题前讲解、内容类型识别，以及当前课程的内容与任务列表。此记录包含离线测试与浏览器验收，不作为真实模型出题质量或学生学习效果的证据。

## 行为变化

| Before | After | Why |
| --- | --- | --- |
| 测验、作业默认先展示讲解及学习目标。 | 新任务默认仅题目；开启“添加题前讲解 / Include an introduction”后加入讲解。 | 用户可按练习用途决定是否需要铺垫。 |
| 同名结果都显示书本图标。 | Lesson 用书本、Quiz 用叠层、Assignment 用文档；标题下显示本地化类型。 | 不必依靠标题猜测任务类型。 |
| 内容库默认混合各门课程的记录。 | 内容、未完成任务、状态计数与搜索均限定左侧当前课程。 | 课程选择在资料、创作和审核中保持一致。 |

开关位于创作页的学生基础之后、输出形式之前，采用现有开关样式，不添加说明小字。Lesson 隐藏该选项，仍正常生成学习讲解。切换界面语言、材料类型或离开后返回创作页时保留当前草稿中的选择；切换课程会清空内容库的搜索词与状态筛选。

## 内容与兼容性约束

- `include_explanations` 为严格布尔字段，新的 Quiz／Assignment 请求默认 `false`。关闭时 `sections` 与 `learning_objectives` 必须为空，参考答案及答案解析保留。
- 作者须将作答必需的条件、数据或阅读片段放进题干。解题、审核阶段同时收到实际学生可见上下文；不会在审核通过后直接删掉题目依赖的讲解。结构化 CPU 题仅移除已经完整出现在题干中的重复约定，并先检查这一条件。
- Native、Harness、逐题 Supervisor 和整批生成均使用此选项。新生成配置在检索或提供方调用前保存；已有 Agent 检查点缺少此字段时按历史含讲解行为继续，已接受的题目保持不变。历史请求的追问指纹保持原有结构。
- “返回修改”恢复保存的选项；页面提交始终携带明确布尔值。历史内容不会自动改成仅题目，编辑与审核仍按其保存配置校验。
- PDF／DOCX 按保存的内容导出，答案导出选项独立于题前讲解。无讲解的题目生成音频时使用标题、题干、选项，不朗读参考答案和解析；已有音频长度限制继续生效。
- 服务端原有账号归属检查保持生效。无课程参数的 API 仍可列出当前账号各门课程，供兼容用途；此次内容库页面始终请求指定课程，并在展示层再次限定课程。

第三方 API 的兼容边界：建议始终显式传入 `include_explanations: false` 或 `true`。如果省略字段，且任务在保存生成配置前就中断，现有记录无法将它与旧版默认含讲解的请求区分；“返回修改”会沿用历史默认开启。正常页面始终显式提交该值，不受影响；已经保存配置、包括模型调用失败后的恢复也不受影响。此次不通过猜测创建时间或改写历史追问请求来规避该边缘情况。

## 自动化验证

- **475 项后端测试通过**，2 条既有 Starlette／httpx 弃用警告。覆盖默认与显式开关、不同生成工作流、旧检查点续做、追问绑定、恢复请求、难度校准、内容库、账号隔离，以及仅题目 PDF／DOCX 的正文与可选答案。[日志](backend-tests.txt) · [JUnit](backend-tests.xml)
- **209 项前端测试通过**。覆盖开关默认值与请求值、隐藏状态、中英文、恢复草稿、类型图标、课程过滤、内容展示、进度、引用与导出等现有前端回归。[日志](frontend-tests.txt)
- JavaScript 语法检查、改动空白检查通过。

后端命令：

```sh
.venv/bin/python -m pytest tests/test_optional_assessment_context.py tests/test_generation_agent.py tests/test_difficulty_pipeline.py tests/test_flexible_agent.py tests/test_supervisor_agent.py tests/test_cpu_spec_agent.py tests/test_difficulty_prompts.py tests/test_workflow.py tests/test_generation_preparation.py tests/test_agent_resume_api.py tests/test_generation_limits.py tests/test_difficulty_calibration.py tests/test_author_material_scope.py tests/test_harness_quality_gates.py tests/test_ca1_smoke.py tests/test_generation_request_recovery.py tests/test_content_library.py tests/test_content_exports.py tests/test_account_isolation.py -q --junitxml=docs/ui/assessment-library-20260920/backend-tests.xml
node --test tests/frontend_*.test.mjs
```

## 浏览器验收

使用[独立测试服务](FIXTURE.md)，临时数据库与独立登录 Cookie，包含三门课程和合成的内容状态。没有修改真实账号资料，也没有触发真实生成。

| 场景 | 观察结果 |
| --- | --- |
| 课程 A 的三种同名内容 | 不同图标与中文／英文类型标签均正确；待审核数为 1。 |
| 搜索不存在的标题，再切到 B | 搜索清空，只显示 B 的独立结果及失败任务；不显示 A 的内容。 |
| 切到空课程 C 并刷新 | 显示空内容与待审核 0；课程选择仍为 C。 |
| 切回 A | 恢复 A 的三条内容，B 的任务不出现。 |
| Quiz 默认状态 | 题前讲解关闭；Lesson 中隐藏；开启后切换英文、Lesson 再回 Quiz 仍保留开启状态。 |
| 键盘操作 | 聚焦开关后空格可切换，焦点样式可见。 |
| 仅题目内容页 | 标题后直接显示题目；展开答案后能看到原参考答案与解析。 |
| 含讲解的 Assignment | 学习目标和讲解仍在题目前，原内容保留。 |
| 390 × 844 窄屏 | 中文与英文类型标签可读，打开按钮位于卡片内；内容宽度 390px，无横向溢出。开关触控区域 51 × 44px。 |
| 页面日志 | 本次测试标签页没有控制台错误或警告。 |

保存的[API 验收记录](browser-api-audit.json)包含最近 96 次内容／任务列表请求，全部带 `course_id`；模型调用数为 **0**。接口请求记录仅包含路径、查询参数和状态，不记录密码、Cookie 或请求正文。窄屏验收完成后已恢复浏览器默认尺寸。

截图：

- [内容库（中文）](library-zh.png)
- [课程 B 的独立结果与任务](course-b.png) · [空课程](empty-course.png)
- [讲解开关（英文）](introduction-switch-en.png)
- [仅题目详情](questions-only-review-en.png) · [含讲解作业](assignment-introduction-en.png)
- [英文窄屏](library-mobile-en.png) · [中文窄屏](library-mobile-zh.png) · [窄屏开关](introduction-switch-mobile-zh.png)

## 本地生效与提供方状态

确认没有活动任务后重启原 8765 服务。首页 HTTP 200，运行中接口声明显示 `include_explanations` 默认值为 `false`。

DeepSeek 的独立最小生成探测在北京时间 **17:16:47** 返回 HTTP 200、有效 JSON，耗时 **635ms**，用量 **44 tokens**；平台未返回费用。没有发送课程材料，也没有重新执行用户失败任务。这证明该次接口调用成功，不代表持续可用性或完整出题流程质量。[复测记录](../../ops/text-service-20260920/followup-probe.json)
