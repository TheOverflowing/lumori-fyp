# P4 本机环境、运行边界与复现

实验日期：2026-09-18。测试公开基准与合成运行检查图，无付费推理调用、无私人资料上传。应用解析服务与真实账号数据不参与这些批次。

## 运行环境

沿用 P3 的 Apple Silicon arm64、10 核 CPU、16 GiB 统一内存机器与 Python 3.12.14。各个候选安装在独立环境：

| 配置 | 环境和设备 | 识别/结构模型 |
|---|---|---|
| MinerU 4.0.2 Advanced | `.venv-mineru`；ONNX CPU intra4/inter1，llama.cpp Metal，VLM 并发2 | 与 P3 Standard 相同的小模型与 Q8_0 VLM；只改 tier |
| Docling 2.128.0 标准管线 | `.venv-docling`；CPU4 | Heron layout、Tesseract chi_sim/eng PSM3、TableFormerV2 |
| GraniteDocling | `.venv-docling`；Docling VLM 管线，MLX Metal | 官方 GraniteDocling 258M MLX 权重 |
| PaddleOCR-VL 1.6 | `.venv-paddle`：PaddleOCR3.7.0/Paddle3.3.1/PaddleX3.7.2；CPU4，OMP1 | PP-DocLayoutV3 + 本机 MLX-VLM 服务上的官方 BF16 PaddleOCR-VL1.6；单请求并发 |

Paddle 的 MLX 服务由 `.venv-docling` 提供，监听随机本机回环端口。正式每个输入独立启动服务，等待可用后进行版面分析和分块 VLM 识别；正常退出时关闭，达到240秒预算时终止整个进程组。预算包含服务冷启动和图片/结构导出，超时保留为失败，不留下请求干扰下一输入。预测温度0，最多8192输出token/区域。沿用上游默认不执行 chart/seal 专项识别；这不是所有可选功能全部打开的 Paddle 配置。

正式批次顺序：Advanced → Docling标准 → GraniteDocling → PaddleOCR → 固定入围者后的确认集。安装、权重下载及合成运行检查与早期 Advanced 有重叠；故本轮耗时仅描述实际运行，不用于严格速度排名。P1、P3 的历史运行条件见其各自 SETUP，不事后包装成完全相同资源。

## 安装与预检查

- 本轮用项目内缓存和下载目录，不覆盖用户全局模型配置。专业候选 worker 使用环境变量允许名单，不继承项目 API 密钥；正式预测使用本地已校验权重。
- Docling 基础与 VLM 依赖分开安装。首次 VLM 扩展安装在下载 mlx-metal 时发生网络读取超时，保留 `setup/docling-vlm-install-attempt1.log`；后续安装成功。这是准备故障，不是删掉的评测样本。
- Docling、GraniteDocling、Paddle 完整流程均先用非基准的自编英文图片验证。`preflight/` 保留输入识别、实际选项与日志；运行成功仅证明可用，不证明基准识别质量。
- Paddle 可行性最初依据通用模型卡仍不明确；进一步核查专门的官方 Apple Silicon 指南后，采用其明确支持的原生 Paddle + MLX 服务路线。Docker没有用于推理。完整客户端做版面、阅读顺序和裁块，MLX端点仅负责元素识别。
- 依赖检查均通过；实际版本分别见 `requirements-docling.lock.txt`、`requirements-paddle.lock.txt`。未因本轮改变应用 `.venv`。
- `evaluator-tests.txt`、`docling-adapter-tests.txt`、`table-metric-tests.txt` 记录评分与格式适配的软件测试。软件测试通过不等于 OCR 准确率通过。

## 权重与来源

每个模型均固定 Hugging Face commit，以 LFS SHA256 或 Git blob SHA1 对照下载内容；`models/*/identity.json` 另存每个实际文件的 SHA256。

| 模型仓库 | 固定修订 |
|---|---|
| PaddlePaddle/PaddleOCR-VL-1.6 | c5630abae1d940eafe0697512a0325494b02ab42 |
| PaddlePaddle/PP-DocLayoutV3 | 7b48a7566925fa464281f930c58eee04fe2c862a |
| ibm-granite/granite-docling-258M-mlx | e9939db25d2f296c8678d0491c4609a8c596c50a |
| docling-project/docling-layout-heron | 8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 |
| docling-project/TableFormerV2 | 51559fad3946873e26a6f9b8e912f948e8745bef |

Advanced 复用 P3 已核验的 ONNX bundle、GGUF 和 projector，详细身份见 `../P3-mineru-20260918/setup/`。权重文件大小不等于完整环境磁盘占用或推理峰值内存。正式模型输出中的版权与许可继承各自上游，项目代码许可不替代模型或基准材料条件。

## 复现入口

模型必须按身份文件预下载到 `tmp/p4-models/`；运行脚本显式离线，缺权重会报错而不悄悄切换模型。重新实验要使用新目录，不覆盖已有输出。

```sh
# 已安装并匹配本轮依赖/权重的环境中执行；Metal 需正常宿主访问。
.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers advanced --output NEW_ADVANCED_DIR --timeout 240
.venv/bin/python scripts/evaluate_parsing_candidates.py --strategy docling_tess_v2 --output NEW_DOCLING_DIR
.venv/bin/python scripts/evaluate_parsing_candidates.py --strategy granite_mlx --output NEW_GRANITE_DIR
.venv/bin/python scripts/evaluate_paddle_parsing.py --output NEW_PADDLE_DIR

# 纯离线计分重放，不重新识别文档。
.venv-docling/bin/python scripts/report_parsing_p4.py
```

`run_parsing_confirmation.py` 是本轮固定路径的一次性顺序运行器：先依据全部完成的开发分数写入 `frozen-finalists.json`，再运行 baseline、Standard、新候选。确认目录已存在时拒绝覆盖。若要复现新的试验，复制冻结代码并显式更改输出根目录，不应直接重用已有实验目录。

P1 的报告生成器写死了6正文页的说明，确认阶段动态加载P1实际冻结的解析源文件与相同参数，复用计分函数，用通用汇总器生成8正文页统计；P4完整报告明确新的分母。确认集基准没有 figure 标注，因此其图像召回分母为0，报告N/A。

## Advanced 的实际含义

核查本机 MinerU4.0.2 源码：Standard 映射 hybrid `high`，向 VLM 传入已构造的区域块；Advanced 映射 `xhigh`，采用不同的区域识别路径，并在该路径启用 image_analysis 参数、规范化视觉块等处理。因此它不仅是给同一输出多一点计算时间，布局和识别结果也可能变化。`mineru-tier-code-audit.json` 保存源文件哈希与检查结论；这些机制差异不是某次错误的已证实根因。

## 论文图表

图表由独立 tmp/p4-plot-env 中的 Matplotlib 生成，依赖见 requirements-plot.lock.txt；未向正在运行的解析环境安装绘图依赖。完成审计后运行 `tmp/p4-plot-env/bin/python scripts/plot_parsing_p4.py`，输出PNG与可编辑SVG。图表只读取同一comparison.json中的统计，不新增推理成绩。

## Paddle块合并消融

额外配置仅设置 `merge_layout_blocks=False`，其余权重、识别参数和240秒预算不变。独立脚本 `scripts/evaluate_paddle_unmerged.py` 保留默认脚本，避免批次中途修改执行代码；正式输出单独存入 runs/paddle-unmerged。追加方案是在开发样本失败分析后固定的，确认集未用于选择该开关。

## 阅读顺序重放与第四组确认

几何规则不改模型文字，只对未合并Paddle输出进行空白递归分栏排序，开发集直接重放到runs/paddle-xycut。规则与额外确认身份均先于任何确认预测固定。独立run_parsing_geometry_confirmation.py在原三组确认结束后使用同配置未合并识别结果；若已有完全相同识别结果则复用，否则完整识别36个确认输入，然后固定重放到confirmation/geometry。原始识别输出与派生输出分别保存，不能把排序重放当作新增推理次数或独立耗时实验。

## 完成与归档

本轮实际新增324次输入解析运行，另有72条确定性排序重放；与108条历史比较记录合计审计504条。33项评分/格式适配检查通过，阅读顺序合成测试另存reading-order-tests.txt。最终选型为质量优先的Advanced研究候选，依据和取舍见FINDINGS.md与selection.json。

报告/TEDS重算应使用`.venv-docling`，系统Python没有APTED，不能直接导入报告模块。绘图时Fontconfig提示全局缓存目录不可写，但指定DejaVu Sans的三张PNG与SVG成功生成，PNG已逐张目视检查，记录于figures/visual-verification.json；未改变评分数据。

运行结束后的只读进程检查没有发现本轮MLX服务或解析worker遗留，记录于runtime-cleanup.json。8765端口在这次检查中没有监听记录；没有为此启动、停止或修改应用服务。

归档入口为`.venv-docling/bin/python scripts/archive_parsing_p4.py`。它核对P3原有824份文件与P1历史rows哈希，保存当前报告/辅助源码，然后生成artifact-manifest.json。该清单排除自身与Python字节码；权重身份另存models目录，权重文件仍在本机运行目录。
