# P4：Advanced 与其他完整解析策略对照

本报告由保存的原始预测重新计分生成；没有重新调用模型。选型范围是本机实际测试的配置与明确时间预算。

图表：[开发集CER](figures/development-cer.png) · [独立确认CER](figures/confirmation-cer.png) · [配对不确定性区间](figures/confirmation-uncertainty.png)。同目录另存可编辑SVG。解释与选择见 [FINDINGS.md](FINDINGS.md)。

## 实验设计

- 开发集：沿用 P1/P3 的 12 个源页，其中 6 页文本计 CER，中英文各 3 页；每页三个配对条件，共 36 次调用/策略。
- 独立确认：新增 12 个源文档组，与开发集及彼此不重复；8 页文本，中英文各 4 页，4 页复杂材料；36 次调用/策略。清单prose层按标注类别筛选，包含试题/索引，不等于全部是连续叙述正文。
- 新装的Docling/Granite/Paddle运行时先完成非基准合成样例检查；Advanced复用P3已通过检查的运行时。源文档选择先于预测；原方案确认入围者按开发集平均CER固定后才运行。
- 根据开发集Paddle段落乱序案例，增加只关闭merge_layout_blocks的受控变体；这是开发阶段的数据驱动消融，追加方案在变体预测和全部确认预测之前固定，详见paddle-unmerged-amendment.json。
- 原始块坐标进一步显示检测阶段就有列间乱序，追加固定几何阅读顺序规则。几何候选无条件进入第四组确认，其身份/规则先于任何确认预测固定，不根据确认结果调参；代码合成测试后的Y分割修正另有时间和哈希记录。
- CER 使用 NFKC、移除空白、保留大小写/标点的整页编辑距离；阅读顺序与表示格式差异也会产生错误。失败保留，空预测 CER=100%。CER 可因插入超过100%，不改称“准确率”。
- 初筛规则为 CER≤10% 且预测长度≥参考80%；是项目阈值，并非教学可用性认证。
- 新专业候选每输入240秒，包括冷启动、解析和导出；既有轻量解析保留原120秒预算。单次耗时仅描述，不是严格等资源吞吐排名。
- 表格/图像指标使用原始及扫描两条件；旋转退化图未进行坐标配准，事先排除。表格 TEDS 是新增描述性指标，不替代预注册正文选型。

## 同一开发集比较

| 策略 | 完成/尝试 | 有文字/尝试 | 原始 PDF CER | 扫描 PDF CER | 退化图 CER | 三条件平均 CER | 初筛达标/可评分调用 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P1 adaptive（冻结基线） | 36/36 | 36/36 | 9.81% | 10.60% | 20.70% | 13.70% | 10/18 |
| MinerU Basic | 36/36 | 36/36 | 5.69% | 5.42% | 14.94% | 8.68% | 12/18 |
| MinerU Standard | 36/36 | 36/36 | 4.69% | 4.11% | 9.18% | 5.99% | 14/18 |
| MinerU Advanced | 35/36 | 35/36 | 6.19% | 4.02% | 23.16% | 11.12% | 14/18 |
| Docling + Tesseract + TableFormerV2 | 36/36 | 36/36 | 13.12% | 21.84% | 55.38% | 30.11% | 6/18 |
| GraniteDocling 258M MLX | 36/36 | 34/36 | 8.92% | 24.97% | 48.73% | 27.54% | 9/18 |
| PaddleOCR-VL 1.6 MLX | 36/36 | 36/36 | 13.45% | 12.07% | 13.00% | 12.84% | 12/18 |
| PaddleOCR-VL 1.6（不合并块） | 36/36 | 36/36 | 13.45% | 12.07% | 13.00% | 12.84% | 12/18 |
| PaddleOCR-VL 1.6 + 几何阅读顺序 | 36/36 | 36/36 | 6.51% | 5.13% | 13.00% | 8.21% | 14/18 |

## 源文档隔离确认

原方案按开发均值选出的新候选：**MinerU Advanced**；另有事先追加的固定几何顺序候选。两者与Standard和冻结adaptive一起确认，全部规则先于确认预测固定。

| 策略 | 完成/尝试 | 有文字/尝试 | 原始 PDF CER | 扫描 PDF CER | 退化图 CER | 三条件平均 CER | 初筛达标/可评分调用 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P1 adaptive（冻结基线） | 36/36 | 36/36 | 15.64% | 14.58% | 23.28% | 17.83% | 16/24 |
| MinerU Standard | 36/36 | 36/36 | 5.78% | 4.73% | 8.72% | 6.41% | 20/24 |
| MinerU Advanced | 36/36 | 36/36 | 2.34% | 2.46% | 3.92% | 2.90% | 23/24 |
| PaddleOCR-VL 1.6 + 几何阅读顺序 | 36/36 | 36/36 | 4.12% | 4.64% | 3.18% | 3.98% | 24/24 |

确认集 Standard CER − 新候选 CER = 3.51 个百分点；按源页和语言分层的探索性 bootstrap 95%区间为 [-0.12, 9.76] 个百分点。三个变体随同源页一起重采样，不能当成独立文档扩充样本量。

几何方案相对 Standard 的平均 CER 降低为 2.43 个百分点，探索性区间 [-1.37, 8.56]。在同一份未合并识别结果上，只改变排序的配对效果为 0.37 个百分点。这里有多个预设候选比较，不作总体显著性或无偏最优保证。

两个新增入围者之间的补充描述性比较：MinerU Advanced CER − 几何方案 CER = -1.07 个百分点，探索性区间 [-1.66, -0.46]。此区间是在部分确认预测已可见后增加的分析，非新增预注册假设；未据此改参数、改样本或增删入围者。

## 表格与配图

图片按 IoU≥0.5 一对一最大匹配，所有无图页误报仍计入精确率。表格先按同样位置规则匹配，未找到的标注表格记0分，再计算 TEDS。TEDS 使用固定 IBM PubTabNet 算法的项目适配版，统一 HTML 表格包装和 th/td；结构版不比较单元格文字，内容版受 LaTeX/Unicode 表达影响。

| 数据/配置 | 条件 | 图片匹配/标注 | 图片精确率 | 表格匹配/标注 | 表格精确率 | TEDS结构 | TEDS内容 |
|---|---|---:|---:|---:|---:|---:|---:|
| p3-basic | native_pdf | 8/10 | 57.14% | 6/6 | 100.00% | 96.63% | 92.03% |
| p3-basic | image_only_pdf | 8/10 | 61.54% | 6/6 | 100.00% | 96.65% | 90.00% |
| p3-standard | native_pdf | 8/10 | 57.14% | 6/6 | 100.00% | 97.18% | 95.92% |
| p3-standard | image_only_pdf | 8/10 | 61.54% | 6/6 | 100.00% | 99.09% | 96.33% |
| advanced | native_pdf | 7/10 | 77.78% | 6/6 | 100.00% | 99.09% | 97.55% |
| advanced | image_only_pdf | 7/10 | 77.78% | 6/6 | 100.00% | 99.09% | 96.78% |
| docling-tess | native_pdf | 10/10 | 62.50% | 5/6 | 100.00% | 69.22% | 57.09% |
| docling-tess | image_only_pdf | 10/10 | 71.43% | 5/6 | 100.00% | 64.92% | 44.24% |
| granite-mlx | native_pdf | 8/10 | 47.06% | 4/6 | 100.00% | 40.43% | 35.76% |
| granite-mlx | image_only_pdf | 3/10 | 33.33% | 4/6 | 100.00% | 41.06% | 36.40% |
| paddle-mlx | native_pdf | 9/10 | 50.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| paddle-mlx | image_only_pdf | 9/10 | 60.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| paddle-unmerged | native_pdf | 9/10 | 50.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| paddle-unmerged | image_only_pdf | 9/10 | 60.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| paddle-xycut | native_pdf | 9/10 | 50.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| paddle-xycut | image_only_pdf | 9/10 | 60.00% | 6/6 | 100.00% | 99.06% | 97.49% |
| confirmation-standard | native_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 98.30% |
| confirmation-standard | image_only_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 99.60% |
| confirmation-challenger | native_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 99.60% |
| confirmation-challenger | image_only_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 99.60% |
| confirmation-geometry | native_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 99.38% |
| confirmation-geometry | image_only_pdf | 0/0 | N/A | 3/3 | 100.00% | 100.00% | 99.49% |

确认集没有 figure 类金标准，不能声称验证了图片召回率；该集保留3个table金标准，本轮未对公式语义计分。配图定位不代表图意解释正确；公式与代码语义、真实拍照、下游 RAG 仍未取得独立准确率。

## 语言分层

| 集合/配置 | 语言 | 三条件平均 CER | 初筛达标 |
|---|---|---:|---:|
| development/P1 adaptive（冻结基线） | english | 8.24% | 5/9 |
| development/P1 adaptive（冻结基线） | simplified_chinese | 19.17% | 5/9 |
| development/MinerU Basic | english | 10.56% | 4/9 |
| development/MinerU Basic | simplified_chinese | 6.80% | 8/9 |
| development/MinerU Standard | english | 8.64% | 6/9 |
| development/MinerU Standard | simplified_chinese | 3.34% | 8/9 |
| development/MinerU Advanced | english | 16.81% | 7/9 |
| development/MinerU Advanced | simplified_chinese | 5.43% | 7/9 |
| development/Docling + Tesseract + TableFormerV2 | english | 24.54% | 3/9 |
| development/Docling + Tesseract + TableFormerV2 | simplified_chinese | 35.69% | 3/9 |
| development/GraniteDocling 258M MLX | english | 29.60% | 6/9 |
| development/GraniteDocling 258M MLX | simplified_chinese | 25.48% | 3/9 |
| development/PaddleOCR-VL 1.6 MLX | english | 8.34% | 6/9 |
| development/PaddleOCR-VL 1.6 MLX | simplified_chinese | 17.34% | 6/9 |
| development/PaddleOCR-VL 1.6（不合并块） | english | 8.34% | 6/9 |
| development/PaddleOCR-VL 1.6（不合并块） | simplified_chinese | 17.34% | 6/9 |
| development/PaddleOCR-VL 1.6 + 几何阅读顺序 | english | 8.34% | 6/9 |
| development/PaddleOCR-VL 1.6 + 几何阅读顺序 | simplified_chinese | 8.09% | 8/9 |
| confirmation/P1 adaptive（冻结基线） | english | 1.39% | 12/12 |
| confirmation/P1 adaptive（冻结基线） | simplified_chinese | 34.27% | 4/12 |
| confirmation/MinerU Standard | english | 8.56% | 8/12 |
| confirmation/MinerU Standard | simplified_chinese | 4.26% | 12/12 |
| confirmation/MinerU Advanced | english | 1.56% | 12/12 |
| confirmation/MinerU Advanced | simplified_chinese | 4.25% | 11/12 |
| confirmation/PaddleOCR-VL 1.6 + 几何阅读顺序 | english | 4.68% | 12/12 |
| confirmation/PaddleOCR-VL 1.6 + 几何阅读顺序 | simplified_chinese | 3.28% | 12/12 |

## 确认集配对变化与反例

下表逐项保留改善、退化和不变的次数；分母24是8个正文源页的三个变体，不能当作24份独立文档。所有配对分数见 confirmation/paired-cases.csv/json。没有依据金标准为每页选择解析器。

| 基准 → 候选 | 改善 | 退化 | 不变 | 最不利配对案例 | CER变化 |
|---|---:|---:|---:|---|---:|
| P1 adaptive（冻结基线） → MinerU Standard | 15 | 9 | 0 | p04/degraded_image | 0.88% → 37.36% |
| MinerU Standard → MinerU Advanced | 7 | 5 | 12 | p07/degraded_image | 6.54% → 11.82% |
| MinerU Standard → PaddleOCR-VL 1.6 + 几何阅读顺序 | 8 | 11 | 5 | p02/native_pdf | 1.88% → 8.72% |

## 失败和耗时

| 集合/配置 | 样本 | 条件 | 失败 | 秒 |
|---|---|---|---|---:|
| development/MinerU Advanced | p03 | degraded_image | TimeoutError | 240.1 |
| development/GraniteDocling 258M MLX | p03 | image_only_pdf | 空白输出（未抛异常） | 12.1 |
| development/GraniteDocling 258M MLX | p03 | degraded_image | 空白输出（未抛异常） | 13.0 |

| 集合/配置 | 平均秒/调用（含失败） |
|---|---:|
| development/P1 adaptive（冻结基线） | 3.5 |
| development/MinerU Basic | 14.6 |
| development/MinerU Standard | 25.8 |
| development/MinerU Advanced | 64.8 |
| development/Docling + Tesseract + TableFormerV2 | 15.8 |
| development/GraniteDocling 258M MLX | 35.7 |
| development/PaddleOCR-VL 1.6 MLX | 24.7 |
| development/PaddleOCR-VL 1.6（不合并块） | 31.5 |
| development/PaddleOCR-VL 1.6 + 几何阅读顺序 | 31.5 |
| confirmation/P1 adaptive（冻结基线） | 1.8 |
| confirmation/MinerU Standard | 18.5 |
| confirmation/MinerU Advanced | 45.7 |
| confirmation/PaddleOCR-VL 1.6 + 几何阅读顺序 | 39.6 |

## 可复现材料与边界

- `preregistration.json`、`protocol-notes.md`、`table-protocol.json`：规则和后续澄清；`confirmation/frozen-finalists.json`：验证前冻结的入围者。
- `runs/`、`confirmation/`：所有预测、JSON结构、裁图、日志、计分、配置与源码快照；`models/`：上游修订及权重SHA256。
- `comparison.csv/json`、`structures/`、`audit.json`：分层汇总、区域/表格细分及预测重放审计。
- 几何策略的开发/确认输出均从对应未合并识别结果确定性重放，所有文字、类型、坐标逐项保持不变。重放行不是新的模型调用，耗时为原识别记录加排序时间；audit.json分开计算实际推理与排序重放数量。
- `SETUP.md`、`REFERENCES.md`、依赖锁文件：设备、安装和运行条件，官方参考。旧 P1/P3 记录保持原样。
- 来源是公开基准及其已有人工校验标注，并非本项目新增人工标注；确认集只与本项目开发源文档隔离，不能证明未进入模型训练。
- 材料是一般中英文文档，不代表计算机本科课程总体；模拟退化不是实拍照片。有限候选和小样本不能证明全球最优。
- 本轮未调用付费API，也未向外部模型上传私人资料；未更改线上默认解析器、账号数据、历史索引和生成记录。
- CER 改善不能直接解释为 RAG Recall 或教学事实准确性改善，后续需要固定 chunk/embedding/检索后的配对下游实验。

- 确认p04三栏索引存在阅读顺序反例，且上游参考含疑似零字形标注噪声；已目视记录于 confirmation/case-notes.md，未改金标准、未删页、未调参。CER也受参考质量与格式影响。
