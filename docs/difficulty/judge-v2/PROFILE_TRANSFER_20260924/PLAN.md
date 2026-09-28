# 新题与学生背景对照：运行前计划

固定评委：difficulty-judge-v4.1-reference-capacity-20260924。保留现有系统提示、schema、解码设置和宿主校验；本轮不调参、不按输出重写题目、不自动修复/重试。

四道新题：奇数和证明、二分边界查找修复、自愿辅导的因果结论、同时期记录与事后回忆的比较。均为 AI 新编写的教学题，不是已验证试题。本轮使用新措辞和新材料家族；不声称整个数学或学科概念从未出现在开发阶段。

每题三种背景：

1. 已学所需基础概念，但没有完成此类任务的练习经验；
2. 有明确、相关的重复独立练习经历；
3. 第 1 类背景的同义改述，用于检验措辞敏感性。

每个家族的题干逐字一致；改变的只是 learner_profile。概念学习不等于熟练完成组合任务。三类描述都是假设学习者，未招募实际学生。预期：相关练习增加不应使预估难度升高；同义改述不应改变候选等级集合。不预定任何单题必须是 easy/medium/hard，不要求熟练后必须下降一档。

计划：4 道独立题 × 3 个背景场景 × 2 次重复 = 24 次调用，上限 24；DeepSeek 当前配置模型别名、thinking off、temperature 0、max_tokens 6000。独立上下文，固定打乱次序。无第二模型复核，避免本轮混合多个变量。运行前保存所有提示、题目、代码散列；原始失败和弃判保留。

观测项：格式有效率、明确等级覆盖、候选集合重复一致性；intro→practised 的不升高/严格下降/逆转/未能确定关系；intro→paraphrase 的候选集合一致。比较候选区间，不将 uncertain 视为中等，不把两次不同范围的 uncertain 视为完全一致。单位分别报告为 4 道题、12 个场景、24 次调用，避免虚增样本量。

评审输入仅含题干、学生背景、证据目录和 schema。题目 ID、家族、对照关系、预期、标签均不进入提示。没有教师标签、学生实测难度或“AI 判准率”。已有 AI 评审表只用于前期规则开发，不作为本轮金标准。

运行方式：

```sh
.venv/bin/python scripts/difficulty_judge_comparison.py --comparison v4 --dataset benchmarks/difficulty_profiles_v1/cases.json --max-calls 24 --output /private/tmp/profile-dry
.venv/bin/python scripts/difficulty_judge_comparison.py --live --comparison v4 --dataset benchmarks/difficulty_profiles_v1/cases.json --max-calls 24 --output docs/difficulty/judge-v2/PROFILE_TRANSFER_20260924
```
