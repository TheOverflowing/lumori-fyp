# 固定盲分析输入：核验优化前的独立预期

本次冻结 10 行：候选流程的两道旧题各重复两次、四道新题、两份旧 Flash 错误解答。仅阅读各运行的 `dataset.json`、选定的 `analysis_response.json` 与数学 oracle，未读取核验响应、运行 records、宿主最终决策、summary 或上一份审查报告。具体文件路径与 SHA-256 全列于 JSON。

审查者是 AI，曾参与题目编写并审过这些解答；这是在本次核验配对结果出现前固定检查预期，不是新的盲解测试、教师金标准或唯一难度标签。四项内容检查针对学生题目、参考及来源；盲解错误须单独归因，不能据此判参考错误。

| 固定输入 | 四项内容检查 | 盲解正确性 | 难度依据 |
|---|---|---|---|
| CANDIDATE / laboratory_slots_0 | 全 pass | pass | uncertain：把允许枚举/反证说成具备相应基础，证据不足 |
| CANDIDATE / laboratory_slots_1 | 全 pass | pass | pass：覆盖构造与下界，明确保留中/难边界 |
| CANDIDATE / courier_single_failure_corrected_0 | 全 pass | pass | uncertain：可枚举不足以排除非例行策略瓶颈 |
| CANDIDATE / courier_single_failure_corrected_1 | 全 pass | pass | uncertain：承认新策略转化，但单档中等依据仍不足 |
| HELDOUT / glyph_table_lookup_v2_0 | 全 pass | pass | pass：正确识别已给表项的复现 |
| HELDOUT / odd_sum_conditional_draw_v2_0 | 全 pass | pass | uncertain：易/中可有合理分歧，组合未练且完整步骤未提供 |
| HELDOUT / adaptive_pair_identification_v2_0 | 全 pass | pass | pass：完整策略和新下界瓶颈均有据，保留中/难边界 |
| HELDOUT / whole_bundle_wrong_key_v2_0 | 条件 pass；参考/解释/来源支持 fail | pass | pass：按已掌握的商余数直接应用 |
| BASELINE / laboratory_slots_0 | 全 pass | fail | pass：需求分析有据，但实际构造错误 |
| BASELINE / courier_single_failure_corrected_0 | 全 pass | fail | fail：判级理由明确依赖错误的“费用至少10”断言 |

`uncertain` 表示依据不足或合理边界，不算质量通过，也不能直接称为错误难度标签。`demand_supported=pass` 可以认可有依据的相邻候选集合，不代表已证明唯一档位。未因旧 AI 预期为 hard/medium 而强制判定新分析失败。

两个廉价负面对照的精确行键是：

- `SOLVER_OPT_20260926_BASELINE/laboratory_slots_0`：最终构造把 A/B 同放时段 1、C/D 同放时段 2，违反设备规则；正确参考仍为五时段方案。
- `SOLVER_OPT_20260926_BASELINE/courier_single_failure_corrected_0`：两条最终路径共用 C-T，关闭该边后全断；又漏掉 C-T 入边，误称下界至少 10。正确参考两路总费用 8。

本地枚举复核：调度四段无解、五段有两解；快递网络 10 条简单路径、9 组边不相交路径对，最优费用 8。新题 oracle 与实际替代策略均已核对。错误兑换参考要求五枚水晶，但需十五枚筹码、实际只有十四枚；盲解四枚正确。没有新增提供方调用。

冻结文件 `VERIFY_OPT_20260926_PREREGISTERED_AUDIT.json` SHA-256：

`476c8e077a2e2d4e3426dd02e9edbc42aaa9d3dcfda09739a4a0ad48e602046e`
