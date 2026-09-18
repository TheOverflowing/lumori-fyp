# P3：MinerU 4.0.2 本机对照

日期：2026-09-18。此前只比较了轻量文本/OCR候选，本轮将专业结构解析器加入同一固定公开样本；不把未测试候选排除为“不适用”。

另见[结果解释与选型](FINDINGS.md)、[安装与精确复现说明](SETUP.md)。正式运行72次，成功返回72次；有输出与内容准确分开统计。

## 配置与证据范围

- 上游工具：MinerU 4.0.2；小模型：官方 MinerU-4 ONNX bundle，CPU、4 intra / 1 inter线程；Standard 采用官方配置的 MinerU2.5-Pro-2605-1.2B Q8_0 GGUF + llama.cpp。
- 本机：Apple Silicon arm64、16 GiB统一内存、10核CPU。依赖位于独立 `.venv-mineru`，配置和权重位于 `tmp/mineru-runtime/`。主应用依赖、资料与默认解析器未修改。
- 先冻结[方案](preregistration.json)，通过非基准自编图的运行检查后，再运行全部12页×3变体。档位分别存档，不把安装/下载失败当识别准确率，也不删除正式运行中的失败。
- 与P1相同：CER仅评6个正文页；NFKC去空白、保留大小写和标点；达标要求CER≤10%且文字长度≥金标准80%。复杂页保存结构输出，未计算TEDS、CDM或图意准确率。
- 用MiddleJson有序正文span评分，保留页眉页脚及原输出顺序，不将Markdown新增标记、图片路径作为正文。未基于答案纠字、重排或筛选样本。
- 权重先下载、校验，再设为local离线推理；worker不继承API密钥。未调用付费模型API，也未上传私人课程。

## 相同样本的对照结果

| 策略 | 输入 | 有文字/12 | 正文达标/6 | Macro CER | Micro CER | 平均秒/页* |
|---|---|---:|---:|---:|---:|---:|
| pypdf_baseline_v0 | native_pdf | 11/12 | 4/6 | 20.98% | 13.96% | 0.09 |
| pypdf_baseline_v0 | image_only_pdf | 0/12 | 0/6 | 100.00% | 100.00% | 0.00 |
| pypdf_baseline_v0 | degraded_image | 0/12 | 0/6 | 100.00% | 100.00% | 0.00 |
| adaptive_local_v1 | native_pdf | 12/12 | 4/6 | 9.81% | 7.47% | 0.74 |
| adaptive_local_v1 | image_only_pdf | 12/12 | 4/6 | 10.60% | 8.61% | 6.14 |
| adaptive_local_v1 | degraded_image | 12/12 | 2/6 | 20.70% | 17.51% | 3.66 |
| rapidocr_v1 | native_pdf | 12/12 | 0/6 | 60.52% | 63.82% | 7.23 |
| rapidocr_v1 | image_only_pdf | 12/12 | 0/6 | 59.71% | 63.06% | 7.49 |
| rapidocr_v1 | degraded_image | 12/12 | 0/6 | 64.65% | 67.55% | 4.92 |
| mineru_4_0_2_basic_onnx | native_pdf | 12/12 | 5/6 | 5.69% | 5.66% | 11.59 |
| mineru_4_0_2_basic_onnx | image_only_pdf | 12/12 | 5/6 | 5.42% | 5.41% | 16.65 |
| mineru_4_0_2_basic_onnx | degraded_image | 12/12 | 2/6 | 14.94% | 15.23% | 15.60 |
| mineru_4_0_2_standard_onnx | native_pdf | 12/12 | 5/6 | 4.69% | 5.08% | 15.95 |
| mineru_4_0_2_standard_onnx | image_only_pdf | 12/12 | 6/6 | 4.11% | 4.49% | 34.98 |
| mineru_4_0_2_standard_onnx | degraded_image | 12/12 | 3/6 | 9.18% | 10.67% | 26.35 |

*时间为一次性描述记录，不是公平吞吐排名：P1同期有pytest负载；P3 Basic与模型下载、运行检查及Standard有重叠。Basic在沙箱中使用CPU，Standard因沙箱无法创建Metal队列而在宿主环境使用本机GPU。每页为独立进程，包含导入、加载、解析与结构/图片保存；操作系统及着色器缓存可能被复用。P1未包含图片资产导出。

## 语言分层与逐页退化

每种语言仅3个正文源页，避免让混合均值掩盖差异。以下均为Macro CER。

| 策略 | 输入 | 英文 CER（n=3） | 中文 CER（n=3） |
|---|---|---:|---:|
| adaptive_local_v1 | native_pdf | 6.77% | 12.85% |
| adaptive_local_v1 | image_only_pdf | 6.72% | 14.48% |
| adaptive_local_v1 | degraded_image | 11.23% | 30.17% |
| mineru_4_0_2_basic_onnx | native_pdf | 7.00% | 4.39% |
| mineru_4_0_2_basic_onnx | image_only_pdf | 6.71% | 4.12% |
| mineru_4_0_2_basic_onnx | degraded_image | 17.98% | 11.90% |
| mineru_4_0_2_standard_onnx | native_pdf | 7.00% | 2.38% |
| mineru_4_0_2_standard_onnx | image_only_pdf | 5.73% | 2.49% |
| mineru_4_0_2_standard_onnx | degraded_image | 13.21% | 5.15% |

与现有adaptive方案逐页配对；均值改善不等于每页都改善。

| 候选 | 输入 | 改善页/6 | 退化页/6 | 不变页/6 | 退化样本 |
|---|---|---:|---:|---:|---|
| mineru_4_0_2_basic_onnx | native_pdf | 4 | 2 | 0 | p01, p02 |
| mineru_4_0_2_basic_onnx | image_only_pdf | 4 | 2 | 0 | p01, p03 |
| mineru_4_0_2_basic_onnx | degraded_image | 3 | 3 | 0 | p01, p02, p03 |
| mineru_4_0_2_standard_onnx | native_pdf | 4 | 2 | 0 | p01, p02 |
| mineru_4_0_2_standard_onnx | image_only_pdf | 5 | 1 | 0 | p01 |
| mineru_4_0_2_standard_onnx | degraded_image | 4 | 2 | 0 | p01, p02 |

以源页为重采样单位、语言内配对的729种bootstrap组合，以下为CER降低百分点（当前adaptive−候选）。这是小型开发样本的探索性区间，不能转化为课程总体或统计显著性保证。

| 候选 | 输入 | 平均降低（百分点） | 95%探索性区间 |
|---|---|---:|---:|
| mineru_4_0_2_basic_onnx | native_pdf | 4.12 | [-1.52, 12.21] |
| mineru_4_0_2_basic_onnx | image_only_pdf | 5.18 | [1.02, 11.89] |
| mineru_4_0_2_basic_onnx | degraded_image | 5.76 | [-1.02, 16.11] |
| mineru_4_0_2_standard_onnx | native_pdf | 5.12 | [-1.52, 15.22] |
| mineru_4_0_2_standard_onnx | image_only_pdf | 6.49 | [1.36, 15.03] |
| mineru_4_0_2_standard_onnx | degraded_image | 11.53 | [1.45, 18.60] |

## 配图区域定位（新口径，不是图意理解）

预测image/chart框与官方figure标注包围框按归一化坐标做IoU≥0.5的一对一最大匹配。所有12页计入，因此无图页的误报也进入精确率分母；失败保留。原PDF和扫描版分别评分；退化图需要额外坐标配准，在评分前即排除。详见[冻结协议](setup/figure-protocol.json)。

| 档位 | 输入 | 匹配/标注区域 | 预测区域 | 区域召回 | 区域精确率 |
|---|---|---:|---:|---:|---:|
| mineru_4_0_2_basic_onnx | native_pdf | 8/10 | 14 | 80.00% | 57.14% |
| mineru_4_0_2_basic_onnx | image_only_pdf | 8/10 | 13 | 80.00% | 61.54% |
| mineru_4_0_2_standard_onnx | native_pdf | 8/10 | 14 | 80.00% | 57.14% |
| mineru_4_0_2_standard_onnx | image_only_pdf | 8/10 | 13 | 80.00% | 61.54% |

整页预览保留率与此处区域召回不同，不能直接拿P1的4/4页预览和这里的Figure框比较。原PDF与标注版本、渲染页面可能存在细微差异；这是开发样本上的局部定位评测。

Basic的p04将金标准合并标注的上下两张子图分别提取，各自与整图的IoU不足0.5，按冻结规则计为未命中。这是分组差异，并不直接证明子图丢失；未在看到结果后合并框或调阈值。另对p06/p10各一张Basic裁图与原页目视核对，详见[视觉检查记录](visual-review.json)，不作为新增人类标注。

## 运行资源和审计

| 档位 | 已完成调用 | 峰值RSS中位数 | 最大RSS |
|---|---:|---:|---:|
| mineru_4_0_2_basic_onnx | 36 | 1.24 GiB | 3.05 GiB |
| mineru_4_0_2_standard_onnx | 36 | 2.35 GiB | 3.48 GiB |

RSS是macOS工作进程的观测值，不等于整个系统峰值或完整GPU显存。模型文件大小、Python环境占用和运行RSS也不是同一指标。

原始结构、Markdown、图片、预测正文、运行日志、每页分数分别位于各 `runs/<tier>/outputs/`。`comparison.csv/json`为汇总；[verification.json](verification.json)从72份MinerU结果（成功时读取原始结构，失败时保留空预测）和108份P1对照预测重新计算指标，校验输入/参考答案/资产/源码哈希，并保存同页配对的小样本bootstrap。评分与适配的软件检查见本轮[JUnit记录](metric-tests.xml)；软件检查不等于识别准确率。

12个源页中只有6个正文准确率样本，三种变体不能写成36个独立样本。所有选型仍属于同一开发集；不宣称官方OmniDocBench成绩或对所有课程最强。高质量表格、公式、配图内容还需要专项标注与独立测试。

## 复现

```sh
.venv/bin/python scripts/evaluate_mineru_parsing.py --prepare
# 模型下载/验证需使用 setup/config.yaml 对应的 MINERU_HOME / MINERU_CONFIG；具体冻结环境见run配置。
.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers basic --output NEW_EXPERIMENT/runs/basic
.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers standard --output NEW_EXPERIMENT/runs/standard
.venv/bin/python scripts/summarize_mineru_experiment.py NEW_EXPERIMENT
```

官方依据：[MinerU4发布](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.2-released)、[档位与硬件](https://opendatalab.github.io/MinerU/usage/tiers/)、[本地SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)、[输出协议](https://opendatalab.github.io/MinerU/reference/output_files/)、[模型下载](https://opendatalab.github.io/MinerU/usage/model_source/)。核验日期2026-09-18。
