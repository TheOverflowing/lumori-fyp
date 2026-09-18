# P4 补充参考与对应实验

核查日期：2026-09-18。仅使用项目作者、官方文档和模型仓库；外部论文/榜单分数不是本项目实测值。更完整的候选研究见 [文档解析参考汇总](../../research/REFERENCES_20260918.md)。

| 官方来源 | 本轮采用的内容 | 证据位置 |
|---|---|---|
| [MinerU tiers](https://opendatalab.github.io/MinerU/usage/tiers/) | 比较 Advanced 与 Standard；高档位不先验等于更低错误率 | Advanced配置、P3权重身份、原始预测 |
| [Docling自定义转换](https://docling-project.github.io/docling/_generated/examples/custom_convert/) 与 [OCR](https://docling-project.github.io/docling/concepts/OCR/) | 显式固定 OCR、版面与表格组件，保留结构和图片来源 | `runs/docling-tess/` |
| [Docling最小VLM流程](https://docling-project.github.io/docling/_generated/examples/minimal_vlm_pipeline/) | 独立测试VLM整页解析 | `runs/granite-mlx/` |
| [GraniteDocling作者模型卡](https://huggingface.co/ibm-granite/granite-docling-258M) | 258M文档模型与官方MLX实现；中文能力须实测，不能从英文推广 | `models/granite-mlx/` |
| [PaddleOCR-VL1.6作者模型卡](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) | 区分元素识别模型与完整文档管线；固定公开权重 | `models/paddleocr-vl16/` |
| [PaddleOCR Apple Silicon完整指南](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html) | 原生Paddle版面分析 + MLX-VLM本地元素服务；无需CUDA或付费API | `scripts/evaluate_paddle_parsing.py`、preflight、完整run |
| [PP-DocLayoutV3](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3) | Paddle版面检测/顺序组件，与仅调用VLM整页提示区分 | `models/paddle-layout-v3/` |
| [IBM PubTabNet TEDS源码](https://github.com/ibm-aur-nlp/PubTabNet/blob/master/src/metric.py) | 表格树编辑相似度；项目适配统一包装并新增位置匹配要求 | `research/pubtabnet/identity.json`、原始源码/许可证、`table-protocol.json` |

实际源码优先使用各 run 的快照和安装包版本。TEDS 上游固定修订为 `8ffde9024bd331f5a61c3c549fdf30dd3c3e43a5`；适配代码保留 IBM 著作权及 Apache2.0 来源，完整 LICENSE 存在 research/pubtabnet。不是直接调用官方 OmniDocBench 全套评测器。

未测试的 OvisOCR2、DeepSeek-OCR2、HPD-Parsing、olmOCR2 等仍标记为未测。模型名称、参数量、其他设备上的排行榜或吞吐量不能替代本机实验；本轮“最佳”只在实际跑过的配置和明确任务指标之间选择。

## 阅读顺序研究补充

这部分在项目几何规则冻结后补充核查，用于解释研究关联和边界，不把自编规则称为下面论文的完整复现。

- Shuai Liu, Youmeng Li, Jizeng Wei：[XY-Cut++: Advanced Layout Ordering via Hierarchical Mask Mechanism on a Novel Benchmark](https://arxiv.org/abs/2504.10258v3)。初稿2025-04-14，v3更新2026-01-28。研究多栏阅读顺序及分层处理，说明阅读顺序应作为独立模块评价。本项目只实现一个小型、确定性的空白分割规则，没有实现其完整掩码/多粒度/跨模态方法，也不引用其榜单分数作为本项目成绩。
- Iddo Hakim et al.：[Reading Order Inference for Complex Document Layouts](https://arxiv.org/abs/2607.01018v1)，2026-07-01。用语言信号和有向图处理复杂、环绕式阅读流。它提示纯几何方法的适用边界；本轮未安装其语言模型或复现该方法，不宣称本规则能解决环绕注释、任意杂志版面。
- [OpenDataLoader Reading Order官方说明](https://opendataloader.org/docs/reading-order)：工程中把阅读顺序作为明确步骤。该项目本轮未单独实测。

项目规则与实验：`geometry-preregistration.json`保存开发阶段追加方案；`geometry-rule-freeze.json`保存合成测试后的最终代码哈希；`scripts/parsing_reading_order.py`使用归一化框、栏间空白和固定阈值重排未合并文本块，保留页眉页脚等位置及全部原文字。不是按参考答案挑段落，也不是AI改写正文。
