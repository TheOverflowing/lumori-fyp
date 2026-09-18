# 文档解析研究参考与实验选择（2026-09-18）

检索日期：2026-09-18。范围：计算机本科课程的中英文电子 PDF、扫描 PDF、拍摄照片，以及表格、公式和教学配图。本文只采用作者论文、项目官方仓库、官方文档及模型/数据集卡片；机器可读清单见 [sources_20260918.json](sources_20260918.json)。引用编号 S01–S37 与 JSON 一致。

**本文是文献研究和实验设计，不是本系统已经取得的性能报告。** 下文文献数值全部标为“外部报告”，本项目实测必须来自独立运行目录中的样本、原始输出和指标计算记录。“最新”表示截至检索日核验到的版本，不表示穷尽所有项目，也不表示对所有文件最优。

后续实验状态：MinerU 4.0.2 的 Basic 与 Standard 已加入本机实测，详见 [P3 报告](../experiments/P3-mineru-20260918/report.md)和[环境/权重核验记录](../experiments/P3-mineru-20260918/SETUP.md)。下文未测候选的论文成绩仍保持外部证据身份；P3 没有替它们给出本项目分数。

## 1. 为什么不能只看“文件解析成功”

PDF 有文本层并不等于文本能按正常阅读顺序提取。扫描 PDF 的主要内容可能只是图片；照片则没有 PDF 文本层。即使 OCR 输出了文字，双栏串行、漏页、公式符号误读、表格错列和配图丢失仍可能发生。pypdf 官方明确区分原生电子 PDF、扫描 PDF 和已做 OCR 的 PDF，并说明它自身不识别图片中的文字。[S01：pypdf 文档](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)

本项目应分别回答四个问题：

1. **工程上是否处理完成**：能打开、没有超时或崩溃、每页都有状态。
2. **内容是否提取完整且准确**：正文、代码、表格、公式、图片是否遗漏或被改写。
3. **证据是否可追溯**：每段文字和图片能否回到原文件、页码、区域。
4. **教学任务是否仍可完成**：错误是否影响定义、算法步骤、复杂度、公式、图中的关系以及后续出题。

字符数量、OCR 平均置信度、程序退出码只能帮助发现问题，不能单独证明“解析率”。如果一张照片没有文字但含有算法流程图，空白 OCR 输出不应被解释为“空白页面”；应保留图像证据并标记尚需视觉理解。

## 2. 核验到的技术版本与适用边界

| 候选 | 截至检索日核验版本 | 对本项目的价值 | 环境与边界 |
|---|---|---|---|
| PP-OCRv6 + RapidOCR | PP-OCRv6 于 2026-06-11 发布；RapidOCR 3.9.2 于 07-21 发布 | 轻量检测、文字识别，适合扫描和照片的本机 OCR 候选 | ONNX Runtime CPU 路线；3.9.0 起默认模型为 v6 small；不提供完整图意理解 |
| MinerU | 工具 4.0.2，2026-09-17；大改版 4.0.0 于 09-16 发布 | 原生文本、OCR、版面、表格/公式及图像证据的分档处理 | `basic` 模型约 0.8 GB；Apple Silicon 基包自动带 Torch；不是几十 MB 的无模型解析库 |
| PaddleOCR-VL | 模型 1.6，05-28 发布，06-02 论文；工具包 3.7.0 | 复杂版面和真实拍摄畸变；表格、公式、图表专项任务 | 需要对应模型运行时或已核验的服务端点；现有 DeepSeek/OpenRouter 密钥不自动等于可调用 |
| Docling | 2.128.0，2026-09-16 | 结构化文档、表格、页码/区域来源、图片导出 | 官方支持 macOS/arm64；具体 OCR 引擎和模型另行固定 |
| olmOCR 2 | `olmOCR-2-7B-1025`，2025-10-22 论文 | 英文文档和基于具体事实的单元测试评价方式 | 本地官方 GPU 路线列出至少 12 GB NVIDIA 显存、30 GB 磁盘；英文结果不能外推中文 |
| DeepSeek-OCR 2 | 2026-01-28 论文 | 视觉 token 重排、阅读顺序、局部裁切研究对照 | 官方示例为 CUDA/vLLM/Transformers；不同于当前 `deepseek-flash` |
| OvisOCR2 | 2026-07-15 技术报告，0.8B | 新的端到端解析对照，输出可含视觉区域 | 尚未在本机测试；模型卡给出保留视觉区域并裁图的示例 |
| HPD-Parsing | 2026-07-21 技术报告，1B | 布局统一规划、区域并行解码的吞吐方向 | 需要专门推理实现；论文 TPS 不等于本机整页耗时 |

来源：[S09：PaddleOCR releases](https://github.com/PaddlePaddle/PaddleOCR/releases)、[S11：RapidOCR releases](https://github.com/RapidAI/RapidOCR/releases)、[S02：MinerU releases](https://github.com/opendatalab/MinerU/releases)、[S19：Docling releases](https://github.com/docling-project/docling/releases)、[S24：olmOCR](https://github.com/allenai/olmocr)、[S27：DeepSeek-OCR 2](https://github.com/deepseek-ai/DeepSeek-OCR-2)、[S33：OvisOCR2](https://huggingface.co/ATH-MaaS/OvisOCR2)、[S35：HPD-Parsing](https://huggingface.co/PaddlePaddle/HPD-Parsing)。

### 2.1 第一轮最可行：保留文本层，再比较 OCR 回退

PP-OCRv6 的 tiny/small/medium 采用面向检测和识别的小模型设计，论文在作者内部数据上报告 medium 的识别准确率 83.2%、检测 Hmean 86.2%。这些是特定 OCR 任务上的**外部报告**，不能当成本系统扫描文档的成功率。[S10：PP-OCRv6 论文](https://arxiv.org/abs/2606.13108)

RapidOCR 的官方安装路线是 `rapidocr` 加 `onnxruntime`，不需要为了 CPU 推理加载整个 Paddle/Torch 栈。其发布记录说明 v3.9.0 的默认检测/识别模型已改为 PP-OCRv6 small，wheel 约 29 MB。应记录安装版本、实际权重文件名与 SHA-256，避免只写“使用了 PaddleOCR”而无法复现。[S11：发布记录](https://github.com/RapidAI/RapidOCR/releases)、[S12：安装文档](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)、[S13：模型注册表](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml)

建议的本项目假设：电子 PDF 优先直接读文本层；文字不足、乱码、疑似扫描页才进入 OCR；保留逐页选择及失败原因。是否比“所有页都 OCR”更准确、更快，必须在相同样本上测量。应分别比较 Tesseract、PP-OCRv6 small，必要时加 tiny 形成准确率/耗时对照。

### 2.2 MinerU 需要区分工具版本、模型版本与质量档位

MinerU2.5 的论文提出先在缩小页图上分析布局，再识别原始分辨率的局部区域。对细小代码、数学符号和密集表格，这比仅把整页缩小喂给视觉模型更值得实验。[S07：MinerU2.5](https://arxiv.org/abs/2509.22186)

2026 年的 MinerU2.5-Pro 保持 1.2B 架构，重点改进困难样本覆盖、跨模型一致性检查与渲染后核对标注。对 FYP 更有借鉴价值的是**建立失败样本集并有针对性改进**，而非直接照搬其大规模训练成本。[S08：MinerU2.5-Pro](https://arxiv.org/abs/2604.04771)

工具 4.0 已将旧 `pipeline/vlm/hybrid` 选择重构为四档。无模型原生 PDF 实验应显式运行 `mineru-kit parse input.pdf -o output.md --tier flash --ocr-mode txt`；这里的 `txt` 不会为扫描页补 OCR。`basic` 使用小模型，`standard/advanced` 再引入视觉语言模型。默认档位和命令行为不同，实验配置必须写完整。[S03：Quick Start](https://opendatalab.github.io/MinerU/quick_start/)、[S04：Tiers and Runtimes](https://opendatalab.github.io/MinerU/usage/tiers/)

官方资源表的约 0.8 GB/basic、约 2 GB/standard 是**模型下载规格**，不含全部运行时；Apple Silicon 基包带 Torch。因此不将 MinerU basic 放进限制几百 MB 的第一轮轻量依赖实验。[S05：资源表](https://github.com/opendatalab/MinerU/blob/master/README.md)

### 2.3 复杂版面与图片：结构解析要和视觉解释分开

Docling 的模块化结构以及页/图片来源信息适合作为工程参考；代码采用 MIT，但模型须按各自许可核验。官方支持 macOS 与 arm64，不代表任何配置都有相同性能。[S17：Docling 论文](https://arxiv.org/abs/2501.17887)、[S18：仓库](https://github.com/docling-project/docling)

PaddleOCR-VL1.5 针对扫描、倾斜、弯折、屏摄与光照引入 Real5 评测；1.6 继续针对薄弱区域进行训练改进。应把它作为照片和复杂版面的后续候选，而不是假定一次视觉模型调用能正确恢复全部元素。[S14：1.5 论文](https://arxiv.org/abs/2601.21957)、[S15：1.6 论文](https://arxiv.org/abs/2606.03264)

DeepSeek-OCR2 的研究重点是按图像语义重新组织视觉 token；olmOCR2 的特色是用具体可验证的文档事实构造测试奖励。前者提示我们单独检查阅读顺序，后者提示我们在字符误差以外检查关键术语、表格邻接关系、公式和不应出现的内容。[S25：DeepSeek-OCR2](https://arxiv.org/abs/2601.20552)、[S23：olmOCR2 评测说明](https://arxiv.org/html/2510.19817v1)

OvisOCR2 和 HPD-Parsing 分别提供端到端、区域并行解码方向的较新对照。它们适合第二阶段在固定数据和可用设备上比较，不应因为参数少或论文吞吐高就替代当前整个服务。[S32：OvisOCR2](https://arxiv.org/abs/2607.13639)、[S34：HPD-Parsing](https://arxiv.org/abs/2607.18839)

## 3. 文献指标如何读：外部结果不等于项目结果

| 模型/系统 | 外部报告值 | 测试对象与口径 | 本项目是否实测此结果 |
|---|---:|---|---|
| MinerU2.5-Pro | 95.69 | OmniDocBench v1.6 Overall，作者论文 | 否 |
| PaddleOCR-VL1.5 | 94.5 | OmniDocBench v1.5 Overall，作者论文 | 否 |
| PaddleOCR-VL1.6 | 96.33 | OmniDocBench v1.6 Overall，作者论文 | 否 |
| PaddleOCR-VL1.6 | 93.19 | Real5-OmniDocBench Overall，数据集维护者当前表格 | 否 |
| DeepSeek-OCR2 | 91.09 | OmniDocBench v1.5 Overall，论文表1 | 否 |
| olmOCR2 | 82.4 ± 1.1 | 英文 olmOCR-Bench 单元测试分数，作者论文 | 否 |
| OvisOCR2 | 96.58 | OmniDocBench v1.6 Overall，作者论文 | 否 |
| HPD-Parsing | 94.91 | OmniDocBench v1.6 Overall，模型卡 | 否 |

来源：[S08](https://arxiv.org/abs/2604.04771)、[S14](https://arxiv.org/abs/2601.21957)、[S15](https://arxiv.org/abs/2606.03264)、[S31](https://huggingface.co/datasets/PaddlePaddle/Real5-OmniDocBench)、[S26](https://arxiv.org/html/2601.20552v1)、[S22](https://arxiv.org/abs/2510.19817)、[S32](https://arxiv.org/abs/2607.13639)、[S35](https://huggingface.co/PaddlePaddle/HPD-Parsing)。

这些行不是可直接排序的统一排行榜：v1.5/v1.6 的标注和匹配逻辑、Real5 的物理畸变、olmOCR 的测试条件都不同。截至检索日，OmniDocBench 仓库记录更新到 v1.7，但结果表仍明确命名 `v1.6_full`。仓库版本、数据版本、分割和评测协议应分别锁定；不能把所有字段都简写成“OmniDocBench”。该仓库给出的 Overall 是文本相似度、表格 TEDS 与公式 CDM 的平均值，**不是“96.33% 的文件完全解析正确”**；阅读顺序另列。[S28：评测公式及版本记录](https://github.com/opendatalab/OmniDocBench)

还有一个应保留的差异：OvisOCR2 作者论文写 96.58，而检索时 OmniDocBench 仓库中的对应行是 96.47。未经核验模型快照、配置和评测变更前，不把二者合并、平均或选更高者作为唯一真值。[S32：论文](https://arxiv.org/abs/2607.13639)、[S28：维护者结果](https://github.com/opendatalab/OmniDocBench)

## 4. 建议的本项目评价标准

下列是**本项目拟定的操作标准**，并非某篇论文宣称的行业统一合格线。正式结论应冻结阈值后在保留测试集上计算，调参不得使用最终测试集。

| 层级 | 指标与分母 | 为什么要独立报告 |
|---|---|---|
| 文件完成率 | 在资源限制内输出有效逐页结果的文件数 / 全部尝试文件数 | 不把超时、损坏、异常页从分母中移走 |
| 有效页提取率 | 有所需内容且产生有效文本/结构的页数 / 所有需要文本/结构的页数 | 真空白页、纯图片页另分类；不能把任意非空文字算成功 |
| 字符准确性 | CER = 编辑操作数 / 标准答案字符数；中英文分开，另报宏平均 | 中文不能简单套英文分词 WER；CER 可能大于1，不截断原始值 |
| 关键事实保留 | 已正确提取的人工标注关键事实 / 全部已标注事实 | 对课程中的负号、变量、复杂度、指针方向比一般标点更敏感 |
| 阅读顺序 | 块顺序编辑距离或成对先后关系准确率 | 整页字符集正确也可能无法连贯阅读 |
| 表格 | TEDS/TEDS-S；另查表头和关键单元格对应关系 | OCR 到了数字不代表数字仍在正确行列 |
| 公式 | CDM 或渲染等价验证；必要时符号级人工核验 | 不同 LaTeX 字符串可能渲染相同；负号/上下标错不可忽略 |
| 图片提取 | 人工标注图片区域的召回率、误检率；IoU阈值明确 | 导出整页不能算找到了所有独立配图 |
| 图片可追溯性 | 图片是否有源文件、页码、bbox、原像素或可复现裁切 | 避免生成说明无法回查 |
| 图片语义质量 | 关键关系/数值正确率；无依据描述率；人工评审一致性 | OCR/裁图通过不代表理解了树、流程图和函数曲线 |
| 人工可用率 | 人工判定可直接用于指定教学任务的文档数 / 所有评审文档 | 与“程序完成率”分开，说明 rubric 和标注人数 |
| 效率/成本 | 每页耗时p50/p95、峰值内存、下载/磁盘、失败重试、API费用 | 单模型吞吐不包括渲染、网络、布局分析和串行流程 |

参考基础：OmniDocBench 的元素与结构指标，[S28](https://github.com/opendatalab/OmniDocBench)；olmOCR 的关键事实/顺序测试，[S23](https://arxiv.org/html/2510.19817v1)。上述指标组合、业务分母和人工可用率定义属于本项目实验设计。

人工标注建议保留：文档许可与来源、原始文件哈希、语言、内容类型、页码、正文金标准、图片/表格/公式框、阅读顺序、关键教学事实、标注者和复核状态。模型生成的参考答案可作为初稿，但未经人逐页核对不可写为“人工标注”。没有金标准的页应报告 `not_evaluated`，不要以0或100代替。

正式数据建议分三层：

- **可控合成样本**：以已知文字、代码、公式和图形生成页面，再控制旋转、低分辨率和噪声；便于定位回归，但不能代表真实扫描仪和拍摄畸变。
- **公开真实页与人工标注**：选计算机教材、课件和公开基准的中英文子集；按整份源文档划分开发/测试，避免同页降质副本跨集合泄漏。
- **真实拍摄对照**：将同一页与扫描/拍照版本配对。Real5 完整映射1355原始页到五种条件，适合借鉴配对设计，而非只测干净电子PDF。[S30：Real5论文](https://arxiv.org/abs/2603.04205)

若学生手写笔记进入产品范围，增加单独评测。2026-08 的 WildHandBench 报告500份手写文档，并研究模型是否用语言先验“猜字”；它说明印刷文档高分不足以担保手写情况。其报告的最高模型分数71.85%同样不是本系统结果。[S36：WildHandBench](https://arxiv.org/abs/2608.22959)

## 5. PDF 配图处理方案：先保存证据，再描述含义

建议统一输出四种不同对象，不能混为一个文本字段：

1. **原始视觉证据**：嵌入图片或按布局区域从页面渲染图裁切。保存文件哈希、页码、bbox、像素尺寸和提取方式。
2. **图中文字**：针对裁图做 OCR，保留检测框和识别来源；图例、节点标签、坐标轴、数值仍需核对。
3. **原文图注及上下文**：关联 Figure/图编号、邻近正文、标题层级；保留图注究竟是原文还是模型生成。
4. **可选语义描述**：以后用视觉模型解释关系、流程、趋势。明确 `generated_description`，引用原图与模型/提示词版本，不能冒充原文。

仅抽取 PDF 的嵌入图片会漏掉由线段、文字和矢量对象组合的图；仅渲染整页又无法说明找到了哪幅配图。因此应允许“图像对象提取”和“页图区域裁切”并存。Docling 给出图、表和页图导出示例，并支持基于来源坐标裁图，可作为结构设计参考。[S20：导出示例](https://github.com/docling-project/docling/blob/main/docs/examples/export_figures.py)、[S21：视觉模型文档](https://github.com/docling-project/docling/blob/main/docs/usage/vision_models.md)

针对计算机课程，语义评价可以采用具体检查：二叉树父子关系是否保留；流程图分支条件与箭头方向是否正确；网络拓扑端点是否匹配；曲线图坐标轴、单位和趋势是否一致。应同时统计遗漏和无依据新增内容。模型说“不确定”仍然保留原图供复核；不要补造图中没有的关系。

进入 RAG 时，建议正文、OCR标签、原始图注、生成说明分别标记；检索命中后能够返回同页图像证据。未做视觉理解的图片应标记为“已保留，尚未解释”，不能把占位字符串或图片文件名当成已获得完整知识。

## 6. 有边界的实验次序

| 阶段 | 对比 | 固定条件 | 拟回答的问题 |
|---|---|---|---|
| P0 | 当前文本解析基线 | 原始样本、原代码/依赖、同一评分器 | 现在到底漏了哪些页和元素？ |
| P1 | 文本层 + 本机 OCR 回退，Tesseract 与 PP-OCRv6 small 对照 | 相同页面渲染、相同语言设置与资源限制 | 扫描/照片准确性是否改善，代价多大？ |
| P2 | 纠偏/方向处理；必要时分区域 OCR；tiny/small 比较 | 一次只改一种处理 | 哪项预处理有效，是否损害干净页？ |
| P3 | Docling、MinerU4 basic/standard、PaddleOCR-VL1.6 | 固定模型权重与版面配置；同一测试集 | 结构、公式、图片区域是否比纯 OCR 更好？ |
| P4 | OvisOCR2、DeepSeek-OCR2、HPD-Parsing或已核验API | 明确设备、服务、费用和模型快照 | 复杂失败页上是否值得增加视觉模型成本？ |
| P5 | RAG下游任务与图片描述人工评测 | 固定切分/嵌入/召回/生成配置 | 解析改善是否真正提高证据和教学内容质量？ |

P0/P1 属于当前资源条件下的优先实验。P3/P4 的候选存在并不表示已经安装、调用或胜出。第一轮保持原文档、用户资料和历史 RAG 实验档案不变；在独立运行目录产出新的解析结果。

每次运行至少保存：`run_id`、输入清单及哈希、源许可证、评测标注版本、解析器/模型/运行时版本、硬件、渲染DPI、语言、页数限制、超时、所有原始逐页输出、失败日志、评分器版本、逐页指标、汇总CSV及人工复核记录。失败样本也保留。多次实验不能只记录胜者；应公开未改善、退化和未评测部分。

## 7. 安装与许可核验事项

这里记录已核验的实施边界，不代表本次已经执行安装：

- 轻量首选候选是固定版本 `rapidocr==3.9.2` 与 ONNX Runtime，实际安装和模型哈希由实验记录确认。官方 tiny 识别 ONNX 单文件列为4.46MB，但这是**识别器本身**，不是包含检测和运行时的完整系统。[S37：官方模型文件](https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_onnx/tree/main)
- MinerU4 的许可证是 Apache2基础加附加条款，包含在线服务标识要求；不要在报告里误写为纯 Apache2 或历史版本许可。[S06：当前许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)
- Docling 代码 MIT，模型许可另查；RapidOCR、PaddleOCR、DeepSeek-OCR2、olmOCR、OvisOCR2 等也须区分代码、权重、依赖和数据许可。
- OmniDocBench 代码 Apache2，但 README 对源PDF写明科研、非商业使用。Real5 材料标为 Apache2，同时保留其继承的原PDF与标注条款。因此基准研究目录不能直接当作产品中任意用户可用的公共课程库。[S28：版权说明](https://github.com/opendatalab/OmniDocBench)、[S31：Real5许可](https://huggingface.co/datasets/PaddlePaddle/Real5-OmniDocBench)
- 模型仓库有权重，不意味着已提供兼容现有密钥的在线端点；调用前分别核对服务名、支持输入、实际模型编号、价格及数据去向。本文未调用付费视觉API，也未将任何用户课程资料上传给研究网站。

## 8. 同日实际实验与原路线的区别

上述阶段表是最初研究路线，保留原文作为历史记录。实际实验编号随后按用户要求扩展：P3实测MinerU4.0.2 Basic/Standard；P4改为Advanced与可在本机运行的其他完整解析管线对照。不能把路线表中曾计划的OvisOCR2、DeepSeek-OCR2、HPD-Parsing写成已经测试过。

P4开发实验完成MinerU Advanced、Docling标准布局+Tesseract+TableFormerV2、GraniteDocling258M MLX、PaddleOCR-VL1.6完整Paddle+MLX管线，以及关闭块合并的受控变体；进一步冻结一个只改变阅读顺序的几何规则。每项正式开发识别36个输入；几何规则复用原预测，不新增模型调用。

完整协议、官方来源及实现边界见 [P4参考](../experiments/P4-candidate-expansion-20260918/REFERENCES.md)、[本机环境](../experiments/P4-candidate-expansion-20260918/SETUP.md)；开发与新增源文档隔离确认结果见 [P4报告](../experiments/P4-candidate-expansion-20260918/report.md)。项目几何规则与XY-Cut++、图结构阅读顺序论文的关联属于背景讨论，不宣称完整复现这些论文。

表格新增项目适配TEDS结构/内容评分；图片保留区域匹配和裁图证据。所有这些分数均为本项目指定小样本与配置的实测结果，不复制上游排行榜，不外推为课程事实或图意准确率。公式语义、真实拍照和下游RAG改善仍需另做实验。
