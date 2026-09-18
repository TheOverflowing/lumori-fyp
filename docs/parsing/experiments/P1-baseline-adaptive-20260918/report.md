# P1 文档解析实测记录

运行时间（UTC）：2026-09-18T03:30:54.625540+00:00。实际保存 216 个解析输出。

这是本机公开材料小样本实验，不是官方 OmniDocBench 分数。12 个不同源页面中，中英文各 6 页；CER 和工程合格率只评价其中的 6 页普通文字页面。每个输入类别的文字覆盖率则包含全部 12 页。

领域分布：academic_literature 5 页；exam_paper 3 页；book 4 页。不是完整计算机课程代表样本。

工程合格规则在查看分数前固定：CER ≤ 10%，且输出非空白字符数 ≥ 参考答案的 80%。空白和异常记入分母。CER 保留大小写和标点，整页阅读顺序错误也计入。

| 策略 | 输入 | 有文字/总页 | 工程合格/可评分页 | Macro CER | Micro CER | 秒/页 |
|---|---|---:|---:|---:|---:|---:|
| pypdf_baseline_v0 | native_pdf | 11/12 | 4/6 | 20.98% | 13.96% | 0.088 |
| pypdf_baseline_v0 | image_only_pdf | 0/12 | 0/6 | 100.00% | 100.00% | 0.001 |
| pypdf_baseline_v0 | degraded_image | 0/12 | 0/6 | 100.00% | 100.00% | 0.000 |
| poppler_layout_v1 | native_pdf | 11/12 | 1/6 | 72.84% | 70.72% | 0.243 |
| poppler_layout_v1 | image_only_pdf | 0/12 | 0/6 | 100.00% | 100.00% | 0.143 |
| poppler_layout_v1 | degraded_image | 0/12 | 0/6 | 100.00% | 100.00% | 0.002 |
| tesseract_v1 | native_pdf | 12/12 | 4/6 | 10.79% | 8.76% | 5.760 |
| tesseract_v1 | image_only_pdf | 12/12 | 4/6 | 10.60% | 8.61% | 6.324 |
| tesseract_v1 | degraded_image | 12/12 | 2/6 | 20.70% | 17.51% | 3.783 |
| tesseract_psm6_v1 | native_pdf | 12/12 | 0/6 | 63.21% | 65.32% | 6.393 |
| tesseract_psm6_v1 | image_only_pdf | 12/12 | 0/6 | 62.65% | 65.00% | 6.808 |
| tesseract_psm6_v1 | degraded_image | 12/12 | 0/6 | 62.90% | 65.07% | 4.208 |
| adaptive_local_v1 | native_pdf | 12/12 | 4/6 | 9.81% | 7.47% | 0.740 |
| adaptive_local_v1 | image_only_pdf | 12/12 | 4/6 | 10.60% | 8.61% | 6.144 |
| adaptive_local_v1 | degraded_image | 12/12 | 2/6 | 20.70% | 17.51% | 3.661 |
| rapidocr_v1 | native_pdf | 12/12 | 0/6 | 60.52% | 63.82% | 7.226 |
| rapidocr_v1 | image_only_pdf | 12/12 | 0/6 | 59.71% | 63.06% | 7.494 |
| rapidocr_v1 | degraded_image | 12/12 | 0/6 | 64.65% | 67.55% | 4.923 |

## 小样本不确定性

6 页可评分文字中：0/6 的 Wilson 95% 参考区间为 0.0%–39.0%；1/6 的 Wilson 95% 参考区间为 3.0%–56.4%；2/6 的 Wilson 95% 参考区间为 9.7%–70.0%；3/6 的 Wilson 95% 参考区间为 18.8%–81.2%；4/6 的 Wilson 95% 参考区间为 30.0%–90.3%；5/6 的 Wilson 95% 参考区间为 43.6%–97.0%；6/6 的 Wilson 95% 参考区间为 61.0%–100.0%。

这些区间只显示样本量很小，不能当成所有课程材料的总体保证。statistics.json 同时保留按语言分层、对同一源页面配对重采样的 Macro CER 差值区间；没有进行显著性或全球最优策略声明。

## 解释边界与负面结果

- 有文字并不代表文字正确。扫描 PDF 的文本覆盖率与 CER、工程合格率必须同时阅读。
- `poppler_layout_v1` 保留视觉行布局，双栏串行化可能交错左右栏；直接替换原生 pypdf 文本存在阅读顺序退化。
- `tesseract_psm6_v1` 假设单一文本块，复杂双栏页面可能比自动分页模式更差，不能统一启用。
- 图表、公式样例只测执行和文字覆盖；结构和语义准确性未测量。图像边框、原图保存、识别置信度不是图像语义分数。
- 降采样、旋转和 JPEG 是受控退化，不是真实手机拍照数据。
- 每种组合只运行一次，包含子进程启动及可能的缓存影响。P1 同期另有软件 pytest 测试（含账号密码散列和少量 OCR 测试）运行，CPU 未保证空闲；这些墙钟时间仅为描述记录，不能据此做稳定吞吐或严格速度排名。
- 初始 pypdf 环境未安装 fontTools，部分英文 CFF 字体发出可选依赖警告；保留真实基线，不静默补依赖后覆盖。

## 证据与复现

- configuration.json：运行配置、版本、数据和源代码散列。
- source-snapshot/ 与 source-snapshot.json：实验时的代码副本与完整性记录。
- runtime-identity.json：OCR 模型、可执行文件、训练语言数据与环境散列。
- native-worker-integrity.json：运行期间资源边界修复前后的原生提取函数一致性说明；父解析器持有运行初始版本，原生子进程可能读取修复后的模块。
- outputs/：每次调用的原始预测文本、解析报告与异常。
- rows.json / rows.csv：逐页实际结果。summary.json / summary.csv：原始分组汇总。
- statistics.json：追加的样本量、Wilson 区间和配对重采样区间。
- 数据说明和使用条款在 ../../benchmarks/omnidocbench-pilot-v1/README.md。
