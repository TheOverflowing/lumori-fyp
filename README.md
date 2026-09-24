# Lumori · FYP 研究与 CA1 档案

当前归档：**2026-09-24**。请从[版本与材料索引](docs/releases/UPDATE_20260924.md)进入；最新论文为 [Part I v0.5](docs/thesis/README.md)。可部署产品另存于 [TheOverflowing/Lumori](https://github.com/TheOverflowing/Lumori)。

CEG 311 FYP 的首版本地应用。按完整的 RAG 内容生成、难度控制、语音和图片、教师审核与学生学习流程设计。当前先完成 CA1 的文字生成与 RAG 后端，真实调用包括 DeepSeek 文字模型、OpenRouter 嵌入与专用重排模型，配图理解已按用户选择启用，语音和生成新图仍按原有配置独立控制。

界面功能说明见[使用指南 / User guide](docs/USER_GUIDE.md)，包含资料开关、删除与恢复、解析档位、图片理解、难度分配和审核流程。

测验与作业已接入[逐题出题 Agent](docs/agent/README.md)：拆分大任务、独立解题、调度计算工具、答案复核、局部修复与中断续做。题数上限为 50，实际受调用额度限制；正确性与难度仍需评估，不能把模型通过当成人工验证。

可选 Harness 后端的思考模式、严格 JSON、有限字段重评与固定题目对照见 [H5 实验记录](docs/agent/harness/H5_THINKING_JSON_20260919.md)，逐组保留调用、失败与预算调整；默认运行模式仍保持原配置。

[H6 主 Agent 与独立逐题子任务](docs/agent/harness/H6_SUPERVISOR_20260919.md)增加分批出题计划、按题分配资料、独立生成与复核、确定性汇总；首版串行派发，可从检查点续做。CPU 作者提交一个规格后由程序计算，单次输出预算可配置至 32768 tokens。

H6 仍为可选实验模式：中英文单题已交付，真实多题组因规划或要求覆盖未达标而停止；完整结果、失败样本和独立复核均已保留。

[H7 灵活答案与逐项验收](docs/agent/harness/H7_FLEXIBLE_ANSWERS_20260919.md)新增 `supervisor_v2`：支持有依据的多种论述立场，为每项要求保留题干和答案证据；数值题保持计算结果，另写可独立复核的概念解释。31 次真实调用交付 5/6 道草稿，包含英文双题整组；独立审核仍发现逻辑和难度缺口，不能将交付率当正确率。审核后已加按题资料归属与无截断组卷，默认模式暂不切换。

设置中的“逐题子代理（测验与作业）”按账号保存，默认关闭。开启后，新建测验或作业使用 `supervisor_v2` 先规划，再按 `AGENT_MAX_PARALLEL_QUESTIONS`（1–40，默认 20）有界并行出题、解题与复核；实际同时出题数不会超过题目总数。原生 DeepSeek 接口也可使用。关闭后保留现有逐题流程，学习讲解不受影响。模式与并发上限写入新任务检查点；旧任务按原有串行检查点续做。并发调度与 20–40 题真实接口实验见 [实验记录](benchmarks/subagent_parallelism_v1/README.md)。

完整研究方案见 [方案 Markdown](docs/Full_Scope_Research_Proposal.md) 和 [方案 Word](output/FYP_Full_Scope_Research_Proposal_API_First_v0.2.docx)。以前的单人任务书保留；当前采用 v0.2 全量 API 优先计划。

CA1 英文阶段报告、独立文献综述、论文来源与演示验收步骤见 [CA1 材料包](docs/ca1/README.md)。

中英文计算机课程的检索算法、固定评测集、逐轮结果和离线复现方法见 [RAG 实验档案](docs/rag/README.md)。最新 [R4 文献候选实测](docs/rag/R4_RESULTS_20260912.md)比较 16 个开发集配置，先锁定方案再验证新保留集。当前应用采用 token 切分、标题与查询指令、有界混合召回及 Qwen3-Reranker-8B。保留集答案跨度命中率持平，MRR@5 从 0.8868 提升到 0.9524；不同数据来源与接口失败均单独说明。

文档解析现使用 MinerU Standard / Advanced，支持扫描 PDF 与 PNG/JPEG。可选 Docling 裁图、DeepSeek 图意说明和图片语义检索，保留原图、图注与独立模型说明；详细流程与真实联调见 [I1 集成记录](docs/parsing/integration/I1-mineru-docling-20260918/README.md)。旧解析预览仍可读取。文献、指标口径和首轮真实标注对照见 [文档解析实验](docs/parsing/README.md)；文字覆盖率与识别准确率分开报告。

此前 [R3 切分对照](docs/rag/CHUNKING_RESULTS_20260912.md)接入了递归边界、来源坐标、章节和关键词元数据。R4 当前配置使用 256 个 Qwen tokenizer token 的正文上限、无重叠；原字符切分及向量方案保留用于对照与兼容。

## 启动

当前目录已装好 `.venv` 环境，双击 `run.command`，或执行：

```sh
./run.command
```

浏览器打开 http://127.0.0.1:8765 ，先注册或登录。终端按 Ctrl+C 停止。服务使用单进程，暂不要加 `--workers`。已实现本地邮箱与密码账号、可撤销会话和服务端数据隔离；公网部署还需 HTTPS、邮件验证与密码恢复等配置。完整说明见 [账号与数据隔离](docs/auth/README.md)。

在新环境安装（Python 3.12 已验证）：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python scripts/prepare_rag_tokenizer.py
./run.command
```

## 配置接口

复制 `.env.example` 为 `.env`，在本地填写，保存后重启。没有配置时也能新建课程、导入资料、查看片段；真实索引及生成会明确提示缺少配置。

每类能力独立设置 `BASE_URL`、`API_KEY`、`MODEL`、`PATH` 和 `EXTRA_JSON`。`BASE_URL` 写平台的 API 根地址（保留平台要求的 `/v1` 等前缀），`PATH` 为相对接口路径，最终请求是两者拼接。不要把完整请求路径重复填写。密钥只保存在本地 `.env`，不写入文档或代码仓库。

当前 CA1 配置如下，`.env.example` 已提供不含密钥的默认值：

| 能力 | API 根地址 | 模型 |
| --- | --- | --- |
| 文字 | `https://api.deepseek.com` | `deepseek-flash` |
| 嵌入 | `https://openrouter.ai/api/v1` | `qwen/qwen3-embedding-8b` |
| 重排 | `https://openrouter.ai/api/v1` | `qwen/qwen3-reranker-8b` |

选定策略需要已校验的 Qwen tokenizer 文件；上述准备命令只下载固定版本的 tokenizer，不下载本地重排模型权重。`RERANK_USE_EMBEDDING_KEY=true` 仅允许在完全相同的网关地址复用嵌入密钥。重排失败会使本次任务失败并保存调用记录，不会静默换成未经本轮验证的降级策略。

文字设置 `TEXT_JSON_MODE=true`，启用 JSON 对象输出；`TEXT_EXTRA_JSON={"thinking":{"type":"disabled"},"max_tokens":6000}` 关闭本次生成的思考模式并设置输出上限。未来使用 `deepseek-v4.1flash` 时，须明确修改 `TEXT_MODEL` 并重新验收，程序不会自动切换模型。嵌入请求固定使用 `encoding_format=float`。

| 前缀 | 请求及返回约定 | 默认路径 |
| --- | --- | --- |
| TEXT | `messages` → `choices[0].message.content` 中的 JSON 对象 | `/chat/completions` |
| EMBEDDING | 文本列表 `input` → 带 `index` 的 `embedding` 浮点向量 | `/embeddings` |
| RERANK | `query`、`documents` → 带 `index` 的 `relevance_score` | `/rerank` |
| SPEECH | `input`、`voice`、MP3 格式 → MP3 二进制 | `/audio/speech` |
| IMAGE | `prompt` → `data[0].b64_json`，PNG/JPEG/WebP | `/images/generations` |

这是首版兼容协议，并非所有服务商都能直接使用。URL-only 图片响应、其他鉴权和其他返回结构需要扩展 `app/providers.py`。图片服务若要求指定返回格式，可先通过平台默认设置或新增适配器支持；当前 EXTRA_JSON 不允许覆盖协议关键字段。`SPEECH_VOICE` 需填写平台支持的音色。

`EXTRA_JSON` 用于平台额外参数，例如支持时设置温度。不能覆盖 model/messages/input/prompt/voice/n/encoding_format/response_format/stream/query/documents/top_n。JSON 输出格式通过 `TEXT_JSON_MODE` 设置。界面“配置已填写”不表示已经通过真实连通测试。

`MAX_DAILY_API_CALLS=100` 按账号、UTC 日统计，含嵌入、重排、生成、难度复核、结构修正、媒体和失败尝试。这是调用次数上限，不是费用上限。整批工作流通常使用一次作者调用与一次题目复核；逐题 Agent 通常每题使用作者、独立解题与答案复核三个角色调用，另有检索、规划和修复成本。提供方错误不自动重做整批题目；Harness 的有限响应结构重评按单独配置执行。调用记录保留状态、耗时、HTTP 状态和经过白名单筛选的 token 用量与平台返回费用；平台未返回费用时不估算为零。

新 Agent 任务冻结 `configuration.repair_policy`（版本 `question-repair-v2`），每题普通尝试预算为 `max(3, AGENT_MAX_REPAIRS + 1)`。普通尝试耗尽后，纯格式问题会自动进入兼容处理，优先复用原候选，不另设第三轮或第六轮的格式截止线；仍受原任务调用上限、每日额度及服务可用性约束。兼容保留完整内容与原始响应，随后照常独立解题和复核。作者默认按四个选项生成选择题；兼容存储允许 2–26 个不同的非空选项，答案必须映射到实际存在的选项，不通过截删选项或概念来凑格式。旧检查点缺少 `repair_policy` 时沿用原普通预算；用户明确选择“继续修正”可为未通过题目增加三轮，保留已完成题目及历史证据，不重置原任务调用数。

## 使用流程

1. 注册或登录账号，再新建课程，导入 PDF、UTF-8 TXT/Markdown 或 PNG/JPEG 照片。扫描页自动尝试本地 OCR；在“文字与原图”逐页核对。`sample_data/intro_to_rag.md` 是自编演示资料，不是课程正式教材。
2. 查看片段，配置嵌入 API 后点击“建立索引”。到任务记录查看自动更新的状态。
3. 选择知识点、材料类型、题型与数量，并填写目标学生基础。题目可统一为同一难度，也可按整数题数分配简单／中等／困难；每档允许为 0，合计须等于总题数，可全部出难题。学习讲解只选择讲解深度。测验与作业默认只生成题目，可开启“添加题前讲解”加入学习目标与背景讲解；题干中的必要条件和答案解析照常保留。开关只影响本次新生成，不会自动修改旧内容。学习目标等文本输入不再设置固定字数上限；外部模型自身的上下文限制仍由接口反馈。提交后进入生成进度页，可查看当前阶段与耗时；完成后打开结果审核。失败或证据不足时可点“返回修改 / Edit request”回填已保存的生成条件，再调整后提交，不需要从头填写。
4. “内容与审核”只展示当前所选课程的生成内容，记录使用与材料类型一致的图标，并在标题下标明讲解、测验或作业。状态筛选、标题搜索、待审核计数及运行中／失败任务均限定在当前课程；切换课程会重置状态筛选与搜索，课程选择会在刷新后保留。在详情对照来源审核，必要时编辑。引用 ID 检查不证明内容正确。
5. 创作页预留文字、语音、配图和视频输出位置。确认文字后，可在详情的多模态区域调用已配置的语音和配图接口；核对媒体后分别确认。视频标记为后续支持，目前没有对应生成请求。
6. 详情的“内容评价”默认折叠，每个内容版本保留一份当前评价；保存后回显，重新打开可修改，新版本单独评价。整体评分和逐题难度仍可导出 CSV，重复修改不会增加同一版本的样本数。
7. 点击“导出”选择 PDF、Word（DOCX）或 Markdown；题目可选择是否包含答案与解析；这与生成前的“添加题前讲解”分别控制，导出会保留当前版本已有的正文。PDF/Word 使用数字引用和来源列表，不调用模型。已生成的语音、配图可直接下载；未来视频也使用相同的媒体文件下载接口。学习页默认折叠答案，可主动查看解析。

修改文字会生成新版本并撤销审核，旧媒体不会出现在新版本学习视图。更换嵌入地址、模型或参数后必须重建索引；检索前会检查索引完整性与向量一致性。课程归账号所有；资料、RAG 片段、生成内容、任务、媒体和导出均在服务端验证账号归属。检索只使用当前账号所选课程的资料；同课程相同文件通过哈希去重。首次草稿与版本记录一并写入数据库，避免只保存其中一项。

难度计划逐题约束标签、认知过程、课程概念及简短评分要点。生成后使用同一文字模型的独立请求与上下文检查题目，不向复核模型提供作者目标或难度设计理由；新任务若仅难度不匹配，会最多尝试三轮；仍不匹配时，从通过其他质量检查的候选中按“相邻档位、任意档位”依次放宽，保留目标档位与实际模型判断，明确显示“难度已调整”。格式兼容与难度放宽分别记录，进度中区分格式、内容、依据、重复及难度问题。资料不足、歧义、低置信度与答案错误仍需修正，不能因为格式兼容就标为通过；持有完整失败题目检查点的任务可选择“继续修正”，无需重填或重做已通过题目。没有新策略字段的旧 Agent 检查点仍沿用对应旧流程。编辑后的版本显示需要重新复核，历史内容不会被自动标记为已验证。模型复核只是筛查，仍需教师确认；教师评分与目标一致率也不是学生答对率。完整规则、调用代价和校准边界见 [难度控制说明](docs/Difficulty_Control.md)，修复与兼容记录见 [更新记录](docs/ops/format-repair-20260920/README.md)。

成功材料可通过 `GET /api/contents/{content_id}/evidence` 导出来源与版本证据。`GET /api/jobs/{job_id}/evidence` 同时覆盖生成失败和证据不足的任务，保留请求、检索来源、尝试结果与脱敏调用记录，便于解释失败而无需创建虚假的成功材料。`GET /api/jobs/{job_id}/generation-request` 供“返回修改”恢复生成条件，验证当前账号归属且不调用模型；再次提交才创建新任务。

## 当前实现与限制

- 已实现：中英文注册与登录、可撤销会话、服务端账号隔离、一次性旧数据恢复、导入解析、嵌入与文本及媒体 API 适配、课程向量检索、结构化材料校验、逐题难度计划与模型复核、任务持久化、幂等生成、编辑审核与版本、媒体审核、学习视图和整体／逐题评分导出；扫描件/照片 OCR、逐页解析报告、原页/内嵌图像保留及历史图像引用。
- R4 阶段后端：534 项测试通过，双语真实检索、索引原子迁移与冻结实验重放完成，见 [R4 结果](docs/rag/R4_RESULTS_20260912.md)。这不代表真人已评审生成质量。
- 历史难度验证：[Python 全套 106 项](docs/ca1/evidence/difficulty-tests-20260912.xml)与 33 项前端测试通过；隔离浏览器中的全难分配、总数校验、讲解切换、逐题显示和人工评价流程通过。2026-09-12 的 [真实验收结果](docs/ca1/evidence/difficulty-20260912T042551358609Z/results.json) 使用隔离数据完成 14 片段索引、全部困难 3 题和三档各 1 题；两份最终草稿的分布与目标一致并通过模型复核，共 9 次 API 尝试。全难首稿有两题被复核为中等，已拦截并重新生成，原失败证据保留。教师质量确认和学生难度校准仍未完成。
- 历史自动化验证：难度重构前 53 项测试通过，覆盖协议、JSON 修复、失败证据、索引完整性和审核流程，见 [测试结果](docs/ca1/evidence/backend-tests-20260912.xml)。本轮难度控制的最终验证结果另记于 [开发记录](docs/Development_Status.md)，不能用旧测试数量代表新版本通过。测试夹具不发起真实模型调用，不用于应用展示。
- 历史真实接口与 RAG：中英文 4096 维嵌入及 JSON 文字输出通过；`education-v2` 的最终真实验收用 9 次调用完成 14 片段索引、lesson/quiz/assignment 生成、来源不足拒答和 10 项审核流程检查，见 [该版本验收结果](docs/ca1/evidence/live-20260912T040126795872Z/results.json)。三份材料已保存在本地演示课程，均为待人工审核的草稿。该记录未包含 `education-v3` 新增的模型难度复核；模型效果、实际难度和教学价值仍需人工评审；语音与图片未做本次真实联调。
- 第一版限制：单文件 10 MB / 300 页 / 400 片段；本地 OCR 和页面预览默认各限 30 页、整份解析限 120 秒；当前切分为 256 个 Qwen tokenizer token 的正文上限、无重叠，原文坐标仍按 Python 字符记录；标准 Markdown 结构保护，不保证深层嵌套块或 PDF 版面；当前为有界混合 Top20、专用重排 Top5 与 1024-token 原文上下文预算，可配置；每次最多 50 题，实际受调用额度限制；选择题和简答题；单段语音最多 3800 字符。
- 后续：正式人工盲评与实验组别管理、基于学生答题数据的难度校准、基于调用记录的延迟和成本分析；长语音、更多格式适配；账号共享与协作权限、邮件验证及密码恢复、正式实验。

课程资料、数据库、媒体及解析图片（`document_assets/`）保存在 `data/`，密钥在 `.env`，两者均列入 `.gitignore`。备份时停止应用后复制整个 `data/`，恢复时同样先停服务。程序中断会将已归属账号的运行任务标为失败，已归属的排队任务重启后继续；尚未归属的历史任务保持原状且不自动执行。外部接口不提供端到端 exactly-once 保证；不确定调用是否完成时先检查平台记录。

## 开发与验证

```sh
.venv/bin/python -m pytest -q
```

CA1 真实验收方法、隔离数据说明和人工评审要求见 [演示与验收清单](docs/ca1/CA1_Demo_and_Acceptance.md)。

旧工作区中的 `CA1 live smoke 20260912T040126795872Z` 课程包含最终验收材料；完成指定账号的恢复后可见。首次失败、提示修正及重新验证记录见 [开发记录](docs/Development_Status.md)；历史 Word/PDF 阶段报告仍为 9 月 11 日快照，本次未重建。

`app/main.py` 是 HTTP 和审核接口，`app/pipeline.py` 是解析检索生成流程，`app/chunking.py` 处理切分与元数据，`app/retrieval.py` 处理排序，`app/providers.py` 是模型协议边界，`app/store.py` 管理 SQLite。`app/document_parsing.py` 处理逐页 OCR 与视觉证据，`app/document_storage.py` 管理缓存解析页和历史图片。前端在 `app/static/`，自动接口说明在 `/docs`。`app/auth.py` 管理密码与会话，`app/account_migration.py` 管理明确授权的旧数据恢复。测试里的媒体字节只检查协议传递与版本逻辑，不能代表有效音频或图像质量测试。

研究正文统一保存在 `scripts/proposal_content.py`；`scripts/build_full_proposal.py` 同步生成 Word 和 Markdown。Word 沿用选定的 System Design 模板，修改后应重新渲染并检查最终文件。

## 项目进度与版本管理

当前基线见 [2026-09-18 项目进度](docs/project/PROGRESS_2026-09-18.md)，日常分支、提交与恢复约定见 [版本管理说明](docs/project/VERSION_CONTROL.md)。代码、报告和实验记录纳入 Git；密钥、账号数据库、模型权重和运行缓存保留本机。
