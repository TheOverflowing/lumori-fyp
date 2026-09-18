# CA1 preparation package

当前按原题要求准备：英文文献综述、系统设计、核心文字与 RAG 初始原型。老师尚未另发字数、格式或评分细则。

**当前后端状态以 [演示与验收记录](CA1_Demo_and_Acceptance.md) 和 [开发记录](../Development_Status.md) 为准。** `v0.1` 英文 Word/PDF 及 `Progress_Report.md` 保留 2026 年 9 月 11 日的报告快照；其中“未配置 API”描述的是当时状态。本次先完善后端并保存真实验收证据，尚未重建正式报告文件。

## 阅读顺序

1. `output/FYP_CA1_Progress_Report_English_v0.1.docx`：英文阶段报告，含综述、设计、原型验证与评估计划（路径相对项目根目录）。
2. `output/FYP_CA1_Literature_Review_English_v0.1.docx`：可独立修改和提交给导师讨论的英文文献综述。
3. 本目录 `Progress_Report.md` 和 `Literature_Review.md`：同步的可编辑正文。
4. `literature/Source_Ledger.md`：文献读取记录、适用边界及预印本信息核对。
5. `literature/reference_index.csv` 和 `literature/papers/`：14 篇论文的索引、来源地址、校验值与 PDF。
6. [CA1_Demo_and_Acceptance.md](CA1_Demo_and_Acceptance.md)：最新后端状态、英文演示流程、真实 API 验证步骤与结果链接。
7. `Manual_Review_Form.csv`：空白人工审核记录，尚无评分。
8. [最终验证汇总](evidence/backend-verification-20260912.json) 与 `evidence/`：按日期保留的软件测试、预检、最小真实接口调用及完整 RAG 运行证据。早期未配置的预检和首轮失败属于历史记录，不能覆盖后续真实结果；具体运行结论见验收记录。

## 现在可以算完成什么

英文综述工作稿、系统设计说明、可运行代码和演示操作稿已准备。后端 53 项自动化测试通过；DeepSeek `deepseek-flash` 与 OpenRouter `qwen/qwen3-embedding-8b` 的 [最终真实 RAG 验收](evidence/live-20260912T040126795872Z/results.json) 通过，覆盖 14 片段索引、讲解/测验/作业生成、来源不足拒答及审核流程。三份真实材料已保存在本地演示课程，均为草稿；人工内容质量核验尚未完成。正式报告提交前须同步最新事实，不要把测试夹具当作模型实验结果，也不要将这份工作稿标为导师已批准。

正式报告正文源文件是 `scripts/ca1_content.py`，生成入口是 `scripts/build_ca1_documents.py`。下一次更新正式报告时，应将本轮真实结果同步到正文源文件，再重建 Word/PDF 并检查排版；本次后端记录不代表旧版报告文件已同步更新。
