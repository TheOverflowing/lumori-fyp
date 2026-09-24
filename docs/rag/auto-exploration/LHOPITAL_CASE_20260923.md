# 自动探索：洛必达法则零候选故障与修复

日期：2026-09-23。真实用户输入为 `Could you give me some questions about "L'Hôpital's rule"`，开启了自动探索。调查读取既有任务审计，不修改用户课程。

## 原因

当时搜索配置是 `curated`，并未配置 Brave 全网搜索密钥。`curated` 是有限的本地公开课程目录，原先重点覆盖计算机课程。两次相关任务各产生六条合理的英文/中文检索词，包括 `L'Hôpital's rule` 和“洛必达法则”；**每条候选数都是 0**。因此失败发生在候选发现阶段，尚未下载、解析、嵌入或向量召回；不能归因于 RAG 相似度或 DeepSeek 对问题的理解。用户界面已有“当前公开课程目录中没有匹配资料，目录覆盖有限”的区分提示。

## 修改

精选目录加入 [Mathematics LibreTexts 的洛必达法则章节](https://math.libretexts.org/Bookshelves/Calculus/Supplemental_Modules_(Calculus)/Integral_Calculus/3:_L'Hopital's_Rule_and_Improper_Integrals/3.2:_L'Hopital's_Rule)。该精确页面标注 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 和作者 Larry Green；系统只为这一精确 URL 记录经过核实的许可，不把同一网站的其它页面一并视为开放许可。索引别名加入英文拼写、变音符号与撇号变体及简繁中文“洛必达”；通用目录匹配会统一去除拉丁字母变音符号并规范化撇号。医院管理等相似拼写不应误匹配。

没有采用 [OpenStax Calculus Volume 1](https://openstax.org/books/calculus-volume-1/pages/4-8-lhopitals-rule) 作为自动入库资料：该书的页面明确禁止未经许可将内容送入大语言模型或生成式 AI 服务。LibreTexts 页面下载得到 132,311 字节，现有 HTML 解析提取约 2,952 字符正文，包含定义、公式和例题；解析器仍标记公式/视觉内容未完全解释，因此不能把本次测试当数学公式解析的完整质量证明。

## 复核

| 阶段 | 原故障 | 修改后隔离运行 |
| --- | --- | --- |
| 中英文搜索 | 六条查询均返回 0 个候选 | 六条查询各返回 1 个候选 |
| 下载与许可 | 未开始 | 同一 CC BY 4.0 页面安全下载并核对精确 URL |
| 解析、嵌入、召回 | 未开始 | 来源入库 1 份，召回 4 个片段 |
| 资料充分性 | `no_search_results` | 模型判断 `sources_sufficient` |
| 耗时 | 不作可比计时 | 17.57 秒 |

修改后的真实接口测试在临时 SQLite 中运行，用 `deepseek-flash` 与当前嵌入服务，结束后销毁数据库；未生成题目、未改动用户资料。精简原始结果保存在 [`live_isolated_retrieval_20260923.json`](../../../benchmarks/auto_exploration_lhopital_v1/live_isolated_retrieval_20260923.json)。同时，自动探索与来源发现的 210 项离线测试通过。`sources_sufficient` 是系统内部模型判断，不是教师审查或题目正确率。

## 边界

这解决了此次洛必达法则的**零候选**问题，也提高了同一主题写法差异下的命中率；`curated` 仍是有限目录，不能保证任意学科、任意知识点都有资料。若要真正覆盖开放互联网，需要配置现有的 Brave 搜索提供方及其独立密钥；找到链接后仍必须通过许可、下载、解析、候选向量检索和证据核查，不能把搜索结果摘要直接当课程证据。旧失败任务冻结了当时的目录版本；复测应新建生成任务。

后续默认策略已扩展为[精选目录 + 有界百科搜索](HYBRID_SEARCH_20260923.md)。本节以上的六条查询统计仍是修复前及目录修复时的历史结果。
