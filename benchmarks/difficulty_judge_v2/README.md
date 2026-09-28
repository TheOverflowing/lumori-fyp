# 固定难度评委诊断集

本集 8 题为 AI 编写/改写的开发诊断材料，含冻结 R8 人文题。全部 teacher_label 和 empirical_difficulty 为 null，不是金标准。h_base 删除教学提示而保留原有任务要求，h_padding 仅添加阅读提示，h_hint 恢复教学提示；数学题构造表述/提示对照。m_missing 和 m_no_profile 检验缺条件和缺学生背景。

所有题目为 diagnostic，暂无教师确认的参照集与独立测试集。不得把同一题家族的改写版本拆到未来参照集和测试集。

baseline_template.json 保存原始 v1 系统提示和 schema，记录来源散列。对照工具会清空原题私有参考，替换学生背景、题干及可见材料，不向评委传递 id、fixture_kind、变式关系或标签。诊断方法见 docs/difficulty/judge-v2/STANDARD_V2.md。

运行（默认仅构造输入，不调用模型；输出目录必须不存在）：

```sh
.venv/bin/python scripts/difficulty_judge_comparison.py --output /private/tmp/judge-v2-dry
.venv/bin/python scripts/difficulty_judge_comparison.py --live --output docs/difficulty/judge-v2/NEW_RUN
```

默认且最多 32 次调用，两次重复。使用独立临时数据库；不修改 .env、生产数据库、正式判级或生成流程。研究用模型调用和实验代码均归档，费用缺失时不推断为零。

teacher_review_template.csv 为独立标注表：交给教师时仅提供 id、学生背景和题目，不提供模型结果、fixture_kind、预设对照关系。每位教师填写自己的行，留下姓名代号/背景、认知要求、等级和依据；仲裁另存，不覆盖原始分歧。没有完成标注前不计算准确率。

交付给教师：TEACHER_PACKET.md 与 teacher_review_template.csv（每人独立复制一份）。题号已打乱并匿名化。teacher_id_mapping.json 供研究者回填结果使用，不随题包发送；两名教师均看不到开发假设及模型等级。
