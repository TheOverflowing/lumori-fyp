# 文档解析小规模公开基准 P1

本目录用于论文实验的可复现起点，不是 OmniDocBench 官方评测结果，也不是正式计算机本科课程测试集。
这里保留公开原始页面、原始标注、精确来源和派生文件。程序、模型或者人工复核都不能在看过输出后修改这些参考答案。

## 数据来源与使用范围

来源是 [OpenDataLab 官方 OmniDocBench 数据集](https://huggingface.co/datasets/opendatalab/OmniDocBench)，
对应 [CVPR 2025 论文](https://arxiv.org/abs/2412.07626)。该基准的标注流程包含人工标注和专家检查；
本项目直接使用发布的标注，不将其描述为项目作者自己完成的人工标注，也不以生成模型输出作为参考答案。
上游流程同时使用智能标注和模型质检，所以也不把它描述成完全不涉及模型的标注过程。

数据集 README 限定研究用途、禁止商业使用。这里不把代码仓库的 Apache 2.0 许可证移植到论文、教材等源文档上。
若后续公开本项目，请保留出处和上游说明，优先发布下载脚本、清单、散列及实验结果；不要默认把这些材料作为商业课程库分发。

- 标注及图像 revision：`aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec`。
- 原 PDF revision：`f15134380fc1835bbb9eff38883023f79a54bc06`。
- 完整标注索引 SHA-256：`a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`。
- `manifest.json` 包含每个文件的下载 URL、字节数、SHA-256、语言、来源页 ID、原始标注路径及变换规则。
- 原 PDF 与当前图像按上游同名页 ID 对齐。两个版本间可能存在遮罩或渲染差异，不能把 native PDF 与 image PDF 的全部差异都归因为解析器。

## 样本选择

从原 PDF 与当前标注的同名页面交集中选择。过滤条件和排序在观察解析分数前固定：

1. 语言为 English 或 Simplified Chinese；来源标注为 academic literature、book、colorful textbook 或 exam paper。
2. 不包含 `ignore` 或 `mask` 区域；可评分文字至少 200 个非空白字符。
3. 按文件名 SHA-256 升序排序。
4. 每种语言先取 3 页纯文字候选，再分别取 1 页含表格、1 页含独立公式、1 页含配图的候选，不重复选择。
5. 纯文字候选不含标注为 table、figure、equation_isolated 的区域，也不含 LaTeX 文本；并不保证页面没有未标注的装饰图形。

结果是 **12 个不同源页面，中英文各 6 页**。其中 6 页可做纯文字串准确性评估，另外 6 页保留表格、公式和图片结构标注作为压力样例。
这些材料跨学科，包含期刊论文、教材和试卷；不能用这个样本估计所有计算机课程材料的真实成功率。
每页生成多个输入版本是配对实验，不把 36 个变体当成 36 份独立新文档。

## 三类实验输入

| 输入 | 来源与目的 |
|---|---|
| native_pdf | 上游公开的原始 PDF 页；可能本来就是扫描件，不一概称为数字原生 PDF |
| image_only_pdf | 将上游页面图像嵌入单页 PDF，完全没有文字层；验证扫描 PDF 路径 |
| degraded_image | 页面图像缩小至 65%，旋转 +2 度，JPEG quality 55；验证有限的倾斜、降采样与压缩退化 |

`page_image` 是未经修改的上游图像，保留在清单中，可在追加实验中单独使用。
合成退化不是实际相机照片，不覆盖透视、阴影、反光、折痕、遮挡或手写。
图片转 PDF 使用原图比例，按 200 DPI 设置页面尺寸，不添加文字。
`scan-qa.png` 是重新渲染的验证缩略图，`contact-sheet.png` 用于检查内容完整性。

## 指标：解析率必须说明分子和分母

| 指标 | 规则 | 可以回答什么 | 不能证明什么 |
|---|---|---|---|
| completed_without_exception | 调用返回且输出页数正确 | 程序是否完成处理 | 页面是否读出文字或读对 |
| nonempty_page_rate | 有非空白文字页 / 全部输入页，包含失败 | 是否获得任何文字 | 字符、表格或事实正确率 |
| macro CER | 每页字符编辑数 / 参考字符数，再按页平均 | 文本串与人工标注的差异 | 单独的 OCR 字形错误率 |
| micro CER | 总编辑数 / 总参考字符数 | 按字符数加权的文本差异 | 短页面与长页面同等重要 |
| English WER | 英文单词及标点分词后的编辑数 / 参考词数 | 英文词序列差异 | 合理的中文分词误差率 |
| usable_page_rate | CER ≤ 10% 且输出长度 ≥ 参考的 80%，分母为全部 6 页可评分文字页 | 本轮预设的工程合格率 | 行业统一标准、教学语义正确或可直接免审核 |
| seconds/page | 包含解析、渲染和 OCR 子进程启动的墙钟时间 | 这台机器这次运行的时延 | 稳定吞吐、GPU 性能或生产并发性能 |

CER 先执行 Unicode NFKC，再去空白；**保留大小写和标点，不删除错字来提高分数**。
编辑距离采用插入、删除、替换各 1 的 Levenshtein 距离；原始 CER 可以超过 100%。
没有输出或处理异常时，预测串为空，CER = 100%，不会将失败样本剔除。
程序中的位向量实现使用独立动态规划实现做随机对照验证。

这里的整页 CER 同时受识别、内容遗漏、额外输出和阅读顺序影响。
例如双栏文章按“逐行跨两栏”拼接，会比按“左栏到底再右栏”拼接得到更高 CER，即使大多数字符认对。
参考串保留上游文字块的阅读顺序，包含有标注的页眉、页脚及页码。

表格的参考答案是 HTML，公式可能是 LaTeX。将这些标记直接与 OCR 的普通文字比较会混淆表示形式与识别错误，
所以这 6 页复杂页面**不参与本轮 CER 或 usable_page_rate**，其结构指标记为未测量。
[官方评测](https://github.com/opendatalab/OmniDocBench) 提供元素匹配、表格 TEDS、公式 CDM 和版面检测等评测；
正式论文比较需要固定同一版评测器和数据，不能把本地整页 CER 与官方排行榜分数混用。

## 后续评估图片与复杂结构

- 表格：建立预测 HTML 与人工标注表格的区域匹配，使用 TEDS/结构 TEDS，并单独检查单元格文本。
- 公式：保存 LaTeX 结果，使用官方 CDM/公式编辑指标，不将 Unicode 和 LaTeX 直接硬比较。
- 配图：分别评估区域定位召回率（预设 IoU）、原图保留率、图注绑定准确率。保存整页预览不等于提取了独立图形。
- 图表语义：需要人工标注图中实体、坐标轴、数值和关系，才能评价描述准确性；现有图像边框不能代替语义参考答案。
- 真实照片：另建同一教材页的实际手机照片，覆盖视角、光照、阴影、反光、折痕；与本目录的受控退化样本分开汇报。
- 课程适配：追加有许可的计算机本科中英文教材/讲义；先固定开发集和独立测试集，再调参，按来源文档划分以免同一文档跨集合泄漏。

## 复现

在提供 Pillow 和 reportlab 的 Python 环境执行 `scripts/prepare_parsing_benchmark.py`。
项目附带 `manifest.json`、完整参考标注及全部输入散列，便于检查数据是否漂移。

```bash
.venv/bin/python -m pytest tests/test_parsing_metrics.py -q
.venv/bin/python scripts/evaluate_document_parsing.py \
  --output docs/parsing/experiments/NEW-UNUSED-RUN-DIRECTORY \
  --strategies pypdf_baseline_v0 poppler_layout_v1 tesseract_v1 tesseract_psm6_v1 adaptive_local_v1 rapidocr_v1 \
  --variants native_pdf image_only_pdf degraded_image
```

脚本拒绝覆盖已有实验目录。每次运行保存配置、版本、数据及代码散列、逐页原始输出、错误、CSV 和分组汇总。
复现历史结果使用相应实验目录内的 `source-snapshot/` 代码；最新生产代码可能已经修复边界问题或更改策略。
RapidOCR 需要先按项目 OCR 环境说明准备本地模型；本轮不使用远程识别或收费模型 API。
