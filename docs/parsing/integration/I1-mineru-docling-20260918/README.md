# I1：MinerU + Docling + 图像语义检索集成记录

日期：2026-09-18。此记录是生产流程集成与小规模联调证据；**不替代 P4 的完整解析评测，也不证明新方案在所有课程上最优**。P1/P3/P4、R1–R5 的历史档案不修改。

## 已实现的流程

1. PDF/PNG/JPEG 上传后保存原文件并创建账号绑定的解析任务。TXT/Markdown 保持 UTF-8 直接读取。
2. 用户选择 Standard / Advanced。MinerU 4.0.2 API 接收 `standard` / `advanced`，内部 effort 分别是 `high` / `xhigh`，不能把 effort 当成 API tier 参数。
3. MinerU 使用 `ocr_mode=auto, image_analysis=False`。不选图片理解仍会对扫描资料执行必要的 OCR。原文、页码、版面块、提取方法和文件哈希单独保存。
4. 勾选图片处理后，解析成功会创建单独的图片后台任务。Docling 2.128.0 只负责版面检测和裁切；不重复进行 OCR 和表格重建。裁图长边最多 1600 像素，默认最多 24 张，裁图总大小最多 32 MiB。
5. 保存图片的文档 ID、页码、归一化左上角坐标 bbox、图像哈希及裁切工具版本。Docling 没有图注时，用同页 MinerU image block 的 IoU≥0.5 匹配已提取图注；无匹配不补写。该关联是几何启发式，并非人工核验。
6. 将裁图、提取图注和最多 6000 字符的同页文字发给视觉接口。默认复用 TEXT 配置的 `deepseek-flash`；独立 `VISION_*` 可替换为其他兼容图片输入的模型。图片用内联 base64 发送，不创建公开图片链接。
7. 结构化字段包括 description、keywords_zh、keywords_en、visible_text、relationships、uncertainties。**这些均属于模型派生内容，包括模型转录的 visible_text，不属于 MinerU 原文或独立 OCR 真值。**保存模型、endpoint signature、提示词版本、origin 和 `verified=false`。
8. 图意文本通过现有 OpenRouter 嵌入接口入库。图片记录与文本 chunks 分表保存，参与同一课程范围内的混合召回、重排及 1024-token 上下文预算。图片使用独立坐标空间，不按原文页字符跨度展开。重切文本不删除图片索引。
9. 审核页的“资料依据”显示召回原图和说明；“文字与原图”页面显示处理状态、原文图注、说明、中英文关键词、不确定信息、编辑和重试入口。

## 失败、缓存与隔离

- 一个图片失败不会删除文字解析或其他图片的成功结果。任务结果含 succeeded/failed/reused；部分失败会明确提示到图片页面重试。
- 描述在嵌入前落库。嵌入失败重试可以复用描述；完成的图片连同向量一起复用，不额外调用 API。
- 缓存键包括图片哈希、原图注/同页上下文、视觉模型 endpoint signature、提示词版本；向量另外保存 embedding signature。
- 编辑说明后清空旧模型关键词、关系、转录和不确定信息，避免把未纠正的旧模型内容混入人工编辑；使旧向量立即失效。点击“重试或更新图片索引”重嵌入，保留人工说明、不重新调用视觉模型。
- 成功重新解析会清空旧图片语义索引；以前材料引用过的图片文件仍保留。失败重新解析保留旧文字和索引。
- 图片文件、列表、编辑、重试、任务列表都通过课程所有者验证；后台任务在任何模型调用前再次验证账号与课程归属。
- 本地模型只允许运行一个重型 worker，独立进程运行，超时/取消杀掉进程组。worker 环境仅继承白名单变量，不继承 API 密钥。
- 多图任务没有静默自动重试。每次视觉/嵌入调用纳入现有每日账号调用上限和费用日志。达到上限会留下失败状态，可后续手动重试。

## 联调轮次与负结果

| 轮次 | 内容 | 结论 |
|---|---|---|
| 根目录 results.json | 首次接入 | 把内部 high effort 误当公开 API tier，MinerU 拒绝；已改为 standard/advanced |
| run-02 | 正确 tier，沙箱执行 | Mac Metal command queue 无法初始化；并非文档准确率失败 |
| run-03 | 获准的本机执行环境，完整公开样本 | 两档解析成功；3 张裁图中 1 张图意成功，2 张模型结构验证失败；保留调用记录 |
| run-03/diagnostic-model-output.json | 单张失败图诊断 | 模型额外输出 `type: json_object`；其他字段结构有效 |
| run-04 | 提示词 v2 + 精确兼容 JSON 模式标记 | 3/3 图片成功；文字/图片共同召回；缓存重跑 0 个新 API 调用 |
| run-05 | 加入 MinerU 图注几何关联的最终集成 | 详见 results.json 与 metrics.json；保留独立轮次，不能用前轮结果代替 |

v2 只剔除值恰好为 `json_object` 的顶层 type 标记，不放宽其余未知字段、类型和长度校验。未增加付费自动重试。

## 数据与指标口径

使用已有公开 OmniDocBench pilot p06 的单页 `image-only.pdf`，含 3 个标注 figure。文件来源、哈希与人工标注保存在原 benchmark manifest/annotation 中。该页是科研论文页面，并非计算机本科课程代表性样本。

- **解析文字覆盖率**：有文字的页数 / 输入页数，不能写成 OCR 识别准确率。
- **CER**：沿用既有 NFKC + 去空白、区分大小写口径，对 reference.txt 计算字符编辑距离 / 真值字符数。可能受阅读顺序、表格转写和图注处理影响，不等于视觉模型事实正确率。
- **图框检出**：对原人工 figure 框计算归一化 bbox 的 IoU≥0.5 一对一匹配，报告 TP/预测数/真值数。单页结果不具有总体统计意义。
- **图意处理完成率**：结构化图意与嵌入均完成 / 本轮裁图数。这是接口和流程成功率，**不是图意正确率**。
- **图片召回**：记录同一次真实查询中来源类型为 figure 的结果。未建立人工 query→figure relevance 标签，因此不报告 Recall@K / MRR 提升。
- **费用**：只汇总上游实际返回的 cost；DeepSeek 没返回货币费用时标记未知，不能当作 0。耗时含进程启动与接口等待，不是纯模型推理速度。

## 验证与运行

测试记录见 verification.json 与保存的测试日志；真实 API 记录见各轮 results.json。浏览器在独立 8766 测试实例验证了中英文上传弹窗、默认关闭图片、已选 Advanced 的重新解析面板、原图显示、状态与操作入口。测试账号和公开样本与正式数据分离。

本机已有 `.venv-mineru`、`.venv-docling` 及模型文件。正常启动仍为根目录 `./run.command`。新安装时仅 `pip install -r requirements.txt` 不足以安装这些独立模型运行环境。路径通过 `MINERU_PYTHON`、`MINERU_RUNTIME`、`DOCLING_PYTHON`、`DOCLING_MODELS` 配置；状态接口会报告依赖是否存在。

- `DOCUMENT_BACKEND=mineru`：正常 `.env` 加载路径的默认值。旧本地解析器保留给离线兼容测试，PDF 网页选择档位总是走 MinerU。
- `DOCUMENT_WORKER_TIMEOUT=600`：每个本地解析/裁切进程的时限。
- `DOCUMENT_MAX_FIGURES=24`：每份文件的裁图处理上限；达到上限保存 truncated 标记。
- `VISION_BASE_URL` 留空时复用 TEXT；配置独立 VISION 时必须同时配置 key/model，不能跨服务复用 TEXT 密钥。
- `IMAGE_*` 仍是生成新图的接口，与视觉理解独立。
- 导入后可在任务页查看解析及图片任务。完成文字解析后仍需点击“建立索引”；纯图片且无可读文字时，先完成图意处理再建索引。

复现命令（会实际使用配置的 API，使用独立输出目录）：

```sh
.venv/bin/python scripts/smoke_document_figures.py --output tmp/new-figure-smoke --live
```

不要复用已经归档的 output 路径。解析器升级、视觉模型变更或图注关联变化后需重新验证。MinerU adapter 当前固定验证 4.0.2。

## 尚未作出的结论

这次没有对大批计算机中英文课程、复杂跨页图、全部扫描退化类型做新评测；未人工逐项核查图片说明、数值和关系。生成阶段目前读取图意文本，**尚未再次把原图发送给生成模型核验**；提示词明确告知这一点，不能宣称视觉事实已经验证。图意是补充证据，原图始终可供人工核对。后续应使用人工 query→figure 标注和事实核对集，与文本-only基线、不同图意模型及上下文策略做受控对照。

## 参考

- [DeepSeek Vision 官方接口说明](https://api-docs.deepseek.com/guides/vision/)
- [Docling Export Figures 示例](https://docling-project.github.io/docling/_generated/examples/export_figures/)
- [MinerU 官方项目](https://github.com/opendatalab/MinerU)，并核对本机 4.0.2 `parser/tier.py` 与 `parser/__init__.py`。
- 原 benchmark 来源与人工标注说明：`docs/parsing/benchmarks/omnidocbench-pilot-v1/manifest.json`。
- 历史候选对照：`docs/parsing/experiments/P4-candidate-expansion-20260918/FINDINGS.md`。历史测试使用 `image_analysis=True`，不能把旧 CER 当成新配置的实测结果。

## 最终实测摘要（run-05）

| 项目 | 实测结果 | 解释边界 |
|---|---:|---|
| Standard 单页解析 | 17.063 s；CER 9.59% | 仅此公开开发页，含启动耗时 |
| Advanced 单页解析 | 28.748 s；CER 6.60% | 不能据此证明全场景更好 |
| Docling 图框匹配 | 3 个预测 / 3 个真值 / 3 个 IoU≥0.5 匹配 | 单页 3 图，不作总体召回率结论 |
| 原文图注关联 | 3/3 | 几何关联，不是人工确认 |
| 首次图意+嵌入完成 | 2/3（66.67%） | 1 次模型结构验证失败，HTTP 200 不等于有效结果 |
| 显式重试 | 新增 2 个 API 调用后 3/3 完成 | 失败图重新描述并嵌入，成功图复用 |
| 最终缓存验证 | 3/3 复用，0 新调用 | final-cache-verification.json |
| 真实混合查询 | 4 个来源中 2 个是图片 | 无 query→figure 人工相关性真值，不计算 Recall@K |
| 后端测试 | 736 passed / 6 skipped | 隔离测试与真实 API 数据分开 |
| 前端测试 | 55 passed | 含英文选项、图片说明转义和人工编辑标记 |

全部本次联调及诊断：已返回货币费用的调用合计 **$0.00101667**；另有 **13 次**调用未返回货币费用，因此这个数字不是总账单。完整日志及 token 用量见 `run-05/metrics.json` 的 call_ledger。
