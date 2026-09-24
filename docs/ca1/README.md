# CA1 preparation package

当前按原题要求准备：英文文献综述、系统设计、核心文字与 RAG 初始原型。老师尚未另发字数、格式或评分细则。

**正式主报告为 [Lumori 英文论文前半部分 v0.5](../thesis/README.md)**，共 43 页，采用单栏论文格式和正文连续排版，减少小节与图片造成的页面空白。正文覆盖文献综述、系统设计、R1–R8 实验、真实历史调用证据和 AI 辅助内容审核。多模态输出研究留待后续补充。

本版统一重绘了 12 个确定性矢量模块图，保留 21 幅编号图及原有浅色截图和实验图。正文以实验轮次、实现状态和版本替代开发日历日期；原始路径、日期与版本关系保存在 [证据索引](../thesis/evidence_index_v05.json)。课程任务书移出学术文献表后保留 24 条文献，正文仍明确交代需求来自课程任务书。实验数字、分母、局限和结论均未改动，也没有增加新的模型调用或实验。

v0.4 正文与构建源码快照保存在 `docs/thesis/versions/v0.4/`，旧版 Word/PDF 继续保留。旧版 v0.1 报告及本目录 `Progress_Report.md`、`Literature_Review.md` 属于早期历史快照，不能用来描述当前运行状态。

当前实现与验收边界另见 [CA1 差距审查](CA1_Readiness_Audit_20260919.md)、[演示与验收记录](CA1_Demo_and_Acceptance.md)。新审核不冒充人工教师审核，也未改写历史质量核验字段。
## 阅读顺序

1. [最新英文论文前半部分](../thesis/README.md)：正式主报告、Word/PDF、可编辑正文与审核记录。`output/FYP_CA1_Progress_Report_English_v0.1.docx` 保留为旧版快照。
2. `output/FYP_CA1_Literature_Review_English_v0.1.docx`：可独立修改和提交给导师讨论的英文文献综述。
3. 本目录 `Progress_Report.md` 和 `Literature_Review.md`：早期 v0.1 可编辑正文；当前主报告正文为 `docs/thesis/Manuscript.md`。
4. `literature/Source_Ledger.md`：文献读取记录、适用边界及预印本信息核对。
5. `literature/reference_index.csv` 和 `literature/papers/`：14 篇论文的索引、来源地址、校验值与 PDF。
6. [CA1_Demo_and_Acceptance.md](CA1_Demo_and_Acceptance.md)：归档后端状态、英文演示流程、真实 API 验证步骤与结果链接，结论适用于各自记录的运行条件。
7. `Manual_Review_Form.csv`：空白人工审核记录，尚无评分。
8. [最终验证汇总](evidence/backend-verification-20260912.json) 与 `evidence/`：按日期保留的软件测试、预检、最小真实接口调用及完整 RAG 运行证据。早期未配置的预检和首轮失败属于历史记录，不能覆盖后续真实结果；具体运行结论见验收记录。

## 当前报告与证据

最新版的完成情况、局限和待补工作以 [论文前半部分](../thesis/README.md) 和 [CA1 差距审查](CA1_Readiness_Audit_20260919.md) 为准。技术原型、真实历史调用、回归测试和内容质量判断分开记录，不能互相替代。

新正文是 `docs/thesis/Manuscript.md`，生成入口为 `scripts/build_thesis_report.py`。旧 `scripts/ca1_content.py` 和 `scripts/build_ca1_documents.py` 仅用于重建历史 v0.1 文档，不再是当前主报告入口。所有原始实验和失败记录继续保留。

v0.5 模块图由 `scripts/build_thesis_visuals_v05.py` 重建；正文构建器不再自动重建旧图，也不会调用模型 API。已有截图、实验图和外部授权图继续作为存档素材使用。重建 Word 后须通过 `render_docx.py --emit_pdf` 渲染并逐页检查，依据实际分页更新目录与图目录的 `page_map.json`，再次渲染确认后再发布 PDF。完整说明见[论文重建流程](../thesis/README.md#rebuilding)。


## CA1 milestone archive (2026-09-20)

See the historical [release index](../releases/CA1_20260920.md) for the repository boundaries and validation recorded at that milestone. The current thesis is [Part I v0.5](../thesis/README.md); the milestone index and earlier CA1 v0.1 documents remain historical records.
