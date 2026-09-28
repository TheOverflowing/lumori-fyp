# Native 与 DeepSeek Harness：`supervisor_v2` 小规模对照（2026-09-24）

## 结论范围

同一批冻结的 AI 自编虚构材料、同一 `deepseek-flash` 模型、同一 `supervisor_v2` 主规划和逐题验收流程下，四个独立任务完成了真实调用。两份 native 任务各保存一道草稿；两份 Harness 任务未交付。一份 Harness 规划协议不合格，另一份首稿难度被拒、修订阶段耗尽调用额度。**这是一次开发诊断，不支持宣称 native 在质量或成本上优于 Harness。**

已保存草稿也不是教师确认的正确题目。英文 native 草稿的 `answer` 字段主要说明“好答案应包含什么”，并非直接呈现一篇符合题干要求的示范短文；中文草稿给出有依据的立场，但题面把材料和论证路径大量写明，目标 `hard` 是否成立仍需人工与学生数据检验。

## 预先固定的比较条件

- 两个案例：`humanities_zh`（虚构图书馆延时开放）、`humanities_en`（虚构档案展叙述视角）；两者不是翻译对。
- 每案例各跑 `native` 和 `deepseek_harness` 一次，共四个新任务。中文顺序 native→Harness，英文顺序 Harness→native，以减轻简单的先后偏差。
- `use_subagents=true`、`supervisor_v2`、每任务一题、相同冻结资料与模型、thinking 关闭、严格 JSON、单次最多 8192 输出 tokens、候选修复一次、角色字段重评一次。
- 全轮硬限 24 次已记录提供商调用，单任务 Agent 上限 8 次；不修改生产 `.env`、课程、账号或已有内容。所有任务使用隔离 SQLite 数据库。
- 检索由相同冻结片段替代，因此不测 RAG 召回、联网搜索或多题并发。Harness 的系统包装和受限工具协议仍与 native 不同；比较对象是整套运行策略。

完整输入、条件和当时代码哈希见 [manifest.json](manifest.json)、[frozen_cases.json](frozen_cases.json) 与 [code](code)。曾在受限沙箱内尝试运行一次，因外网 DNS 和本地监听权限失败（native 两次连接失败、Harness 两次零调用启动失败）；该轮没有模型质量数据，未计入下表。连通性验证后，在隔离环境重新创建了本表的四个任务。

## 真实运行结果

| 案例 | 运行时 | 草稿 | 调用 | 已知总 tokens | 墙钟时间 | 停止位置 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 中文图书馆 | native | 1/1 | 5 | 29,327 | 28.9 秒 | 首候选通过应用门槛 |
| 中文图书馆 | Harness | 0/1 | 8 | 55,408 | 57.6 秒 | 首候选判 `medium`；修订稿解题阶段达到单任务额度 |
| 英文档案展 | Harness | 0/1 | 1 | 3,116 | 4.0 秒 | 主计划第 5 项使用无效要求类型 `argument_with_counterargument`，协议只允许六种固定类型 |
| 英文档案展 | native | 1/1 | 7 | 37,527 | 32.7 秒 | 首候选判 `medium`，第二候选通过应用门槛 |

总计 **21/24 次**调用，**125,378** 个已知 tokens。调用账本中所有 21 次都有 token 用量；费用字段均缺失，实际金额未知。墙钟时间包含阶段启动与等待，任务按表中顺序串行运行；两边停止阶段不同，不能拿这四个数字推断运行时速度优劣。[summary.json](summary.json)、[results.json](results.json)

## 与应用门槛分开的内容复核

1. **中文 native 草稿：**参考答案区分了简报直接陈述、读者体验和缺失的总体数据，也处理了竞争解释。题干已完整附上三段材料并列出六条详细作答要求，参考答案约 1,586 个字符。它通过模型的 `hard` 判断，但这一判断没有教师或学生标注；“短文”与教师参考答案篇幅之间的教学适配也需确认。[完整草稿](humanities_zh__native.json)
2. **中文 Harness 首稿：**模型门槛给出“正确性通过、难度 medium”，所以它没有发布。人工只读检查还发现参考答案把读者乙归入“原本白天难以到馆”的人；冻结材料只说乙傍晚常在馆备课、更愿意留下来，不能推出她白天难以到馆。这说明“正确性通过”也不是事实保证。修订稿尚未完成独立解题与复核，不能按通过题统计。[失败候选与检查点](humanities_zh__deepseek_harness.json)
3. **英文 Harness：**规划响应的 `r5.kind` 为 `argument_with_counterargument`，不属于 `knowledge/evidence/reasoning/comparison/constraint/interpretation`；当前 schema 的离线重验在 `questions[0].requirements[4].kind` 报 `literal_error`。这是结构失败，没有作者候选，更不能评价其答案质量。[规划响应](humanities_en__deepseek_harness.json)
4. **英文 native 草稿：**第二候选的答案为 232 个按空白分隔的英文词。它以 “A strong answer will satisfy...” 开头，逐项描述评分要点并举例，缺少一篇直接回应题目的连贯短文。应用的要求覆盖和正确性门槛均判通过；这暴露了成品形式与题干“write a short essay”之间尚未被门槛抓住的差异。题干还提供了完整 method note 与较多解释线索，`hard` 标签需独立验证。[完整草稿](humanities_en__native.json)

上述内容复核是开发者对冻结材料和实际成品的逐项阅读，不是盲审、教师金标或学习者表现数据。中文 Harness 首稿与两份 native 成品各为不同的随机生成题目；不能把它们逐句当作同一道题的 A/B 答案。

## 下一轮应验证什么

先用**完全相同的冻结题干与答案**分别送入两个运行时的独立解题、复核阶段，设置一个明确错误和一个正确对照，单独统计错误接受与错误拒绝；保证两组真正进入相同的答案审核节点。再扩大到多次交错重复的端到端任务，并在运行前冻结统一的人工评分表，分别标注结构合规、事实/推理、成品形式、难度、调用和耗时。当前一轮只说明了具体失败模式，不能外推可靠性或决定默认运行时。

复现入口：[runtime_paired_comparison.py](../../../../scripts/runtime_paired_comparison.py)。默认为仅写计划；`--live` 才产生真实调用。归档中的 `code/` 是本次运行前冻结的实际代码；实验脚本随后增加了案例名称校验，不改变本轮执行和结果。所有原始失败及任务 evidence 保留在本目录，运行时私有 SQLite 和 Harness 子进程目录未复制入文档归档。
