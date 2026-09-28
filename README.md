# Lumori · 教育内容生成与研究档案

Lumori 是面向教师的教育内容生成与审核 Web 应用：导入课程资料，通过检索增强生成（RAG）编写中英文讲解、测验和作业，再对照来源审核、编辑和导出。项目同时用于 CEG 311 FYP 的系统实现与实验研究。

**本次同步：2026-09-28**。近期功能开发与实验记录截至 9 月 26 日，详见[本次更新](docs/releases/UPDATE_20260928.md)与[验证记录](docs/releases/VALIDATION_20260928.md)。论文最新归档仍为 [Part I v0.5](docs/thesis/README.md)，论文和历史实验各自保留原版本，不自动代表当前代码。

| 入口 | 内容 |
| --- | --- |
| [使用指南](docs/USER_GUIDE.md) | 课程、资料、生成、审核和导出操作 |
| [可部署产品仓库](https://github.com/TheOverflowing/Lumori) | Docker Compose、服务器配置、备份及产品回归测试 |
| [CA1 材料](docs/ca1/README.md) / [论文](docs/thesis/README.md) | 阶段报告、验收方法、可编辑稿及历史证据 |
| [RAG](docs/rag/README.md) / [解析](docs/parsing/README.md) / [生成 Agent](docs/agent/README.md) | 各模块的设计、实验和限制 |

本仓库 `lumori-fyp` 保存应用源码、研究脚本、冻结实验与论文材料；`Lumori` 保存可部署应用及运行配置。账号数据库、用户上传、模型权重和密钥均留在仓库之外。

## 当前能做什么

- **课程与资料管理**：账号注册/登录、服务端数据隔离，导入 PDF、PNG/JPEG、UTF-8 TXT/Markdown；按课程管理资料的启用、删除与恢复，查看原文、解析页和来源。
- **文档解析与检索**：PDF/照片可用 MinerU Standard / Advanced；按选择使用 Docling 提图与视觉模型说明。检索采用有界混合召回、专用重排，保留来源坐标与引文。TXT/Markdown 可直接解析；完整 PDF/图片功能需要额外解析环境。
- **讲解、测验与作业**：选择知识点、学生基础、语言、题型和题数；测验/作业支持选择题、简答题及简单/中等/困难的整数配额，最多 50 题，实际完成量受调用额度限制。
- **逐题生成与复核**：作者、盲解和复核分别调用模型；支持局部修复、检查点续做、取消、已通过题目的部分结果及按版本修改单题。账号设置可开启规划后的有界并发出题。
- **可选资料探索**：Auto exploration 在资料不足时搜索候选，经来源、许可证、正文和覆盖检查后收录。默认 hybrid 使用教学来源目录和 Wikipedia 文章搜索；完整 Brave 搜索需要单独密钥。
- **审核与交付**：对照来源编辑、保存新版本、审核内容及媒体，按版本记录整体评价与逐题难度，导出 PDF、Word、Markdown 和评价 CSV；学习页可折叠答案。
- **连续编辑与阅读**：生成条件和未提交编辑按账号、课程及版本保存在当前浏览器，支持恢复与清空；返回列表恢复位置，长内容支持章节/题号导航和窄屏下拉定位。草稿保留 30 天，不跨设备同步。
- **可选媒体**：已有语音和图片生成适配接口，需要单独配置并审核；视频仍未实现。资料中的图片理解与生成新图片是不同功能。

### 最近的进展

| 模块 | 当前变化 | 详细记录 |
| --- | --- | --- |
| Harness 候选运行时 | 覆盖自动探索的模型与搜索阶段、课程讲解、题目规划/作者/盲解/复核；权限、预算、下载和组卷仍由应用控制 | [接入说明](docs/agent/harness/README.md)、[全流程试运行](docs/agent/harness/FULL_FLOW_PILOT_20260924.md) |
| 逐题恢复与证据 | 新的子代理任务按题修复，无效成品引文可有限重评；单题耗尽后保留其余题目检查点，整组通过后才保存完整草稿 | [协议改进与复测](docs/agent/runtime-comparison/IMPROVEMENT_20260924.md) |
| 难度观察器 `review_v2` | 先盲解，再核验答案、解释与来源；程序区分内容问题、证据不足、相邻难度边界与明确等级。默认关闭，仅观察，不自动返工或改变发布门槛 | [协议与边界](docs/difficulty/review-v2/README.md)、[求解配置实验](docs/difficulty/review-v2/SOLVER_OPT_20260926_REPORT.md) |
| 前端 | 草稿恢复、列表返回位置、长内容目录、输入框与进度显示改进 | [连续操作验证](docs/ops/frontend-continuity-20260926/README.md)、[进度本地化](docs/ops/FRONTEND_PROGRESS_LOCALIZATION_20260926.md) |

## 本地启动

新环境需要 Python 3.12。以下路径以仓库根目录为准：

```sh
git clone https://github.com/TheOverflowing/lumori-fyp.git
cd lumori-fyp
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
cp .env.example .env
# 在本地编辑 .env，填写自己的接口配置。
.venv/bin/python scripts/prepare_rag_tokenizer.py
./run.command
```

打开 **http://127.0.0.1:8765**，注册账号后创建课程。已有环境可直接运行 `./run.command`，Ctrl+C 停止。仓库不附带虚拟环境；Tokenizer 准备脚本下载固定版本的分词器，不下载本地嵌入或重排模型权重。

最小安装可以使用 TXT/Markdown。默认 `.env.example` 选择 MinerU，**上述依赖安装不会安装 MinerU/Docling**；PDF/照片解析需配置 `MINERU_*`、`DOCLING_*` 的独立环境，参阅[解析集成](docs/parsing/integration/I1-mineru-docling-20260918/README.md)。在新机器部署完整应用，优先使用[产品仓库的 Docker 指南](https://github.com/TheOverflowing/Lumori#readme)。Harness 同样需要[单独安装](docs/agent/harness/INSTALL_20260919.md)。

## 配置与默认行为

配置示例见 [`.env.example`](.env.example)，实现见 [`app/config.py`](app/config.py)。更改配置后重启；进程环境变量可以覆盖 `.env`。下表描述仓库示例，实际运行取决于部署配置和账号选择。

| 配置 | 示例默认值 / 含义 |
| --- | --- |
| `TEXT_*` | DeepSeek 接口、`deepseek-flash`；JSON 输出，默认关闭 thinking |
| `EMBEDDING_*` / `RERANK_*` | OpenRouter 的 `qwen/qwen3-embedding-8b` / `qwen/qwen3-reranker-8b` |
| `GENERATION_WORKFLOW` / `AGENT_RUNTIME` | `agent_v1` / `native`；Harness 为可选运行时 |
| `AGENT_ORCHESTRATION` | `sequential_v1`；网页开启“逐题子代理”后，新任务采用 `supervisor_v2` |
| `AGENT_MAX_PARALLEL_QUESTIONS` | 20，可设 1–40；只限制开启子代理后的同时出题数 |
| Auto exploration | 新账号默认关闭；启用后沿用来源与任务预算限制 |
| `DIFFICULTY_SHADOW_MODE` | `off`；启用 `shadow` 后默认每任务观察前 1 题，最多额外 2 次调用 |
| `MAX_DAILY_API_CALLS` / `AGENT_MAX_CALLS` | 每账号每 UTC 日 100 次 / 每 Agent 任务 180 次；两项限制同时生效 |
| 检索配置 | 256-token 正文分块、无重叠，候选 Top20、重排 Top5、1024-token 原文上下文预算 |

模型标识是本项目配置值，供应商可用性、权限和费用需用自己的账户确认。文字、嵌入和重排按各自接口填写；重排仅在配置允许且网关地址完全相同时复用嵌入密钥。重排失败会保存失败记录，不静默切换策略。

`BASE_URL` 填 API 根地址，`PATH` 填相对路径，避免重复拼接。`EXTRA_JSON` 提供额外参数，不能覆盖模型、消息、输入等协议关键字段。`VISION_*` 负责资料图片理解；留空时沿用文字端点，但该模型仍必须支持图片输入。`SPEECH_*` 和 `IMAGE_*` 分别用于语音与新图片生成。

调用额度包含检索、生成、复核、修复、媒体和失败尝试，**不是金额上限**。多题、并行或 Harness 工具循环可能用尽默认日额度。调用记录保留状态、耗时及平台返回的用量/费用；没有返回费用就记为未知。

## 使用流程

1. 新建课程、导入资料，检查“文字与原图”和片段，再建立索引。可用自编的 [`sample_data/intro_to_rag.md`](sample_data/intro_to_rag.md) 试用。
2. 选择讲解/测验/作业，填写知识点与学生基础，设置题型、数量、难度配额。测验和作业可选择是否添加题前讲解。
3. 查看生成阶段和问题诊断。资料不足时补充资料或调整要求；可续做的任务从已保存检查点恢复，已通过题目无需全部重做。
4. 在“内容与审核”核对题目、答案及来源，必要时编辑并保存新版本，再确认审核。修改文字会撤销该版本的审核状态，旧媒体不会出现在新版本学习视图。
5. 按需生成并审核媒体、记录评价，导出内容。测验/作业导出可选择是否包含答案与解析。

草稿、内容版本、模型复核和教师审核是不同状态。新生成结果仍需审核；引用 ID 有效不等于事实或答案正确。

## 难度与实验结论的边界

生成主流程保留目标难度和模型判断。新策略最多尝试三轮严格难度匹配；如果只有难度不匹配、其他质量门槛通过，可按相邻档位再到任意档位放宽，并明确显示“难度已调整”。格式兼容不会豁免答案、依据、歧义或内容质量检查。旧检查点保留创建时策略，详见[难度控制](docs/Difficulty_Control.md)。

新增 `review_v2` 是独立的可选观察器。它不取代现有生成复核，不自动改题，也不授权发布。分析/核验模型与思考强度分别可配，缺阶段、未知证据或不足的依据会弃判。当前抽样不能证明整份测验通过，模型评审也不能替代教师盲评或学生实测难度。

研究结果应从对应冻结材料读取：

- [R4 检索实验](docs/rag/R4_RESULTS_20260912.md)：保留集答案跨度命中率持平，MRR@5 从 0.8868 提升到 0.9524，说明该评测条件下排序改善。
- [Harness 对照](docs/agent/runtime-comparison/IMPROVEMENT_20260924.md)：已有真实流程交付和引用协议验证，也保留格式失败、难度调整、语义漏检与误拒风险；不能据小样本认定优于 native。
- [难度求解实验](docs/difficulty/review-v2/SOLVER_OPT_20260926_REPORT.md)：复杂题完整解答在特定配置下改善，但难度分歧、弃判、核验截断与额外耗时仍存在，正式自动判级/返工尚无充分依据。
- [历史 CA1 验收](docs/ca1/CA1_Demo_and_Acceptance.md)：保留当时版本与失败样本，不用历史测试数量代表本版验证。

## 开发与验证

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=. .venv/bin/python -m pytest -q
node --test tests/frontend_*.test.mjs
```

前端测试需 Node.js（CI 使用 22）。本次测试结果、跳过项目和部署验证边界见[验证记录](docs/releases/VALIDATION_20260928.md)。测试多使用接口替身和隔离数据，不能据此宣称真实模型质量、生产性能或教师认可。

主要代码：`app/main.py` 管理 HTTP 与审核接口，`app/pipeline.py` 管理导入/检索/生成流程，`app/generation_agent.py` 管理逐题工作与检查点，`app/providers.py` 管理外部 API，`app/store.py` 管理 SQLite，前端位于 `app/static/`。启动后的接口文档位于 `/docs`。

## 部署、数据与尚未完成的工作

- SQLite 和进程内任务队列要求**单应用进程、单实例**；不要增加 Uvicorn workers。`/healthz` 检查数据库与后台工作线程，`/livez` 检查服务存活。
- 数据库、课程资料、媒体及解析图片在 `data/`，密钥在 `.env`。停机后备份完整 `data/` 及配置；只回滚代码不能恢复数据库。
- 公网使用需要 HTTPS、正确的主机/代理配置及部署验收。目前尚无邮箱验证、密码找回或邀请制管理。完整设置见[账号说明](docs/auth/README.md)与[部署仓库](https://github.com/TheOverflowing/Lumori)。
- 尚需独立教师盲评、学生答题数据校准、冻结配置下的质量/耗时/成本评估；账号协作、长语音、更多媒体格式和视频生成仍属后续范围。

项目方案见[研究方案](docs/Full_Scope_Research_Proposal.md)，历史发布见 [2026-09-24 快照](docs/releases/UPDATE_20260924.md)，日常提交与恢复约定见[版本管理](docs/project/VERSION_CONTROL.md)。
