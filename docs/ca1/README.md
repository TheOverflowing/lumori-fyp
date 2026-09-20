# CA1 preparation package

当前按原题要求准备：英文文献综述、系统设计、核心文字与 RAG 初始原型。老师尚未另发字数、格式或评分细则。

**正式主报告现已更新为 [Lumori 英文论文前半部分 v0.4](../thesis/README.md)**（2026-09-20），采用新的单栏论文排版，覆盖更新后的系统流程图、扩展文献综述、R1–R8 实验、真实调用证据和 AI 辅助内容审核。多模态输出研究留待后续补充。旧版 v0.1 报告及本目录旧正文保留为 2026-09-11 历史快照，不能用来描述当前运行状态。

当前实现与验收边界另见 [CA1 差距审查](CA1_Readiness_Audit_20260919.md)、[演示与验收记录](CA1_Demo_and_Acceptance.md)。新审核不冒充人工教师审核，也未改写历史质量核验字段。
## 阅读顺序

1. [最新英文论文前半部分](../thesis/README.md)：正式主报告、Word/PDF、可编辑正文与审核记录。`output/FYP_CA1_Progress_Report_English_v0.1.docx` 保留为旧版快照。
2. `output/FYP_CA1_Literature_Review_English_v0.1.docx`：可独立修改和提交给导师讨论的英文文献综述。
3. 本目录 `Progress_Report.md` 和 `Literature_Review.md`：同步的可编辑正文。
4. `literature/Source_Ledger.md`：文献读取记录、适用边界及预印本信息核对。
5. `literature/reference_index.csv` 和 `literature/papers/`：14 篇论文的索引、来源地址、校验值与 PDF。
6. [CA1_Demo_and_Acceptance.md](CA1_Demo_and_Acceptance.md)：最新后端状态、英文演示流程、真实 API 验证步骤与结果链接。
7. `Manual_Review_Form.csv`：空白人工审核记录，尚无评分。
8. [最终验证汇总](evidence/backend-verification-20260912.json) 与 `evidence/`：按日期保留的软件测试、预检、最小真实接口调用及完整 RAG 运行证据。早期未配置的预检和首轮失败属于历史记录，不能覆盖后续真实结果；具体运行结论见验收记录。

## 当前报告与证据

最新版的完成情况、局限和待补工作以 [论文前半部分](../thesis/README.md) 和 [CA1 差距审查](CA1_Readiness_Audit_20260919.md) 为准。技术原型、真实历史调用、回归测试和内容质量判断分开记录，不能互相替代。

新正文是 `docs/thesis/Manuscript.md`，生成入口为 `scripts/build_thesis_report.py`。旧 `scripts/ca1_content.py` 和 `scripts/build_ca1_documents.py` 仅用于重建历史 v0.1 文档，不再是当前主报告入口。所有原始实验和失败记录继续保留。


## CA1 milestone archive (2026-09-20)

See [release index](../releases/CA1_20260920.md) for repository boundaries and validation. The current thesis is [Part I v0.4](../thesis/README.md); earlier CA1 v0.1 documents below/above are retained historical deliverables.
