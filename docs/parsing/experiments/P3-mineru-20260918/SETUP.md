# MinerU 本机实验环境与复现说明

2026-09-18。此文记录 P3 的实际安装与运行过程；准确率从 `runs/` 原始预测计算。P1/P2 不被覆盖，应用默认解析器不在此实验中修改。

## 实际测试配置

| 项目 | 值 |
|---|---|
| 机器 | Apple Silicon arm64，10 核 CPU，16 GiB 统一内存 |
| Python | 3.12.14，独立 `.venv-mineru` |
| MinerU 工具 | 4.0.2 |
| 小模型运行时 | ONNX Runtime 1.30.0，CPU；intra=4，inter=1 |
| 小模型 bundle | `opendatalab/MinerU-4_models_onnx` |
| Basic | `tier=basic, ocr_mode=auto, image_analysis=True` |
| Standard | `tier=standard, ocr_mode=auto, image_analysis=True`；GGUF + llama.cpp，本机 Metal |
| VLM | `MinerU2.5-Pro-2605-1.2B-Q8_0.gguf` 及配套 Q8_0 projector |
| 请求并发设置 | `model.vlm.max_concurrency=2`；不是 llama.cpp Engine 的槽位数 |
| 其他 LLM 辅助 | 标题层级与跨页表格单元格合并均关闭 |
| 执行 | 每个输入独立工作进程，240 秒超时；每档 12 页 × 3 条件 |

独立环境的 `pip check` 通过。完整依赖锁定在 [`setup/requirements-mineru.lock.txt`](setup/requirements-mineru.lock.txt)，安装来源及实际安装包版本另存 JSON。主应用的 `.venv` 和依赖配置没有因此变更。

## 权重来源与核验

小模型的 Hugging Face 固定修订为 `358310b4f64b95f9fefc372ad899356e4111f376`。13 个必需文件合计 858,204,914 bytes，按 LFS SHA-256 或普通配置文件的 Git blob SHA-1 核验。

VLM 使用 MinerU 官方模型注册表指向的转换仓库 `jinzhenj/MinerU2.5-Pro-2605-1.2B-GGUF`，固定修订为 `9185688a0495e1577d521a757c7c0b62dd38ca48`。主权重 531,066,496 bytes，projector 709,409,600 bytes，均核对 LFS SHA-256。权重文件大小不等于运行内存或 Python 环境磁盘占用。

最初通过 Hugging Face 下载时公式模型传输很慢，保留日志后中止该下载；随后使用 MinerU 官方 CLI 的 ModelScope 来源完成下载，并对下载文件再次核对以上 Hugging Face 上游哈希。没有手工伪造模型就绪标记。官方 `mineru-kit models verify` 对 Basic 与 Standard 均返回正常。

证据在 `setup/basic-model-identity.json`、`setup/vlm-model-identity.json`、`setup/*-upstream.json`、`setup/download-*.log`、`setup/verify-*.txt`。本轮所用模型文件合计约 2.1 GB。

## 运行检查与环境问题

在基准数据评分前，先使用自编英文测试图 `setup/smoke-input.png` 验证运行：

- Basic 成功，完整工作进程约 8.33 秒；峰值 RSS 约 0.85 GiB。
- Standard 首次在沙箱失败，日志为无法创建 Metal command queue；该失败和约 9 秒耗时完整保存。
- 相同 Standard 代码在允许本机 Metal 访问的宿主环境运行成功，约 36.01 秒，峰值 RSS 约 2.21 GiB。

这是运行环境检查，不是 OCR 基准准确率。正式 Standard 36 条件全部在可使用 Metal 的宿主环境执行。正式解析中的异常/超时保留空预测并计入准确率分母，不能以安装故障为由删除难样本。

工作进程仅继承允许的运行环境变量；配置固定为 `model.source=local`，不继承 DeepSeek、OpenRouter 等 API 密钥，也不调用远程推理。ONNX 遥测在 worker 中显式关闭。本轮只处理公开基准和自编测试图，未上传私人课程材料，未调用付费模型 API。

## 时间结果的限制

Basic 与模型下载、运行检查和 Standard 有部分重叠；P1 同期有软件测试负载。Basic 使用 CPU 沙箱环境，Standard 使用宿主 Metal。各输入冷启动 Python 与模型，但系统文件缓存和 Metal 着色器缓存可能复用；工作进程时间还包括结构和图片保存。P1 文字实验关闭了图片资产导出。因此保存耗时用于描述本次运行，不能据此作公平速度、稳定吞吐或成本排名。

## 复现入口

在项目根目录创建独立运行时：

```sh
.venv/bin/python -m venv .venv-mineru
.venv-mineru/bin/python -m pip install -r docs/parsing/requirements-mineru.lock.txt
.venv/bin/python scripts/evaluate_mineru_parsing.py --prepare
```

权重必须与本轮身份文件一致。下载和验证应通过 `scripts.evaluate_mineru_parsing.isolated_environment()` 返回的环境执行对应 CLI；它设置项目内 `MINERU_HOME`、`MINERU_CONFIG` 和缓存路径，不覆盖用户全局配置。例如在主环境 Python 中调用：

```python
import subprocess
from scripts.evaluate_mineru_parsing import ROOT, isolated_environment

subprocess.run([
    str(ROOT / '.venv-mineru/bin/mineru-kit'),
    'models', 'download', '--tier', 'standard',
    '--small-backend', 'onnx', '--vlm-engine', 'llama-cpp',
    '--source', 'modelscope',
], env=isolated_environment(), check=True)
```

未来上游模型文件可能改变；下载后必须先比对本轮哈希，再称为精确复现。正式运行使用新的输出目录，脚本拒绝覆盖已有目录：

```sh
.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers basic --output NEW_EXPERIMENT/runs/basic --timeout 240
.venv/bin/python scripts/evaluate_mineru_parsing.py --tiers standard --output NEW_EXPERIMENT/runs/standard --timeout 240
.venv/bin/python scripts/summarize_mineru_experiment.py NEW_EXPERIMENT
```

Standard 需要运行环境允许 Metal。重放本轮应优先采用 `runs/<tier>/source-snapshot/` 的冻结识别与评分源码，并保持其项目根目录相对布局；汇总源代码另行快照。当前代码若发生变化，必须重新记录哈希，不把新结果覆盖为旧运行。

官方依据：[4.0.2 发布](https://github.com/opendatalab/MinerU/releases/tag/mineru-4.0.2-released)、[档位与运行时](https://opendatalab.github.io/MinerU/usage/tiers/)、[模型来源](https://opendatalab.github.io/MinerU/usage/model_source/)、[SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/)。核验日期：2026-09-18。
