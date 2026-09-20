# Lumori 多模态模型与 API 选型记录

核查日期：2026-09-19。阶段：官方资料调研；未调用付费生成 API，未产生模型质量排名或实测性能结果。

部署约束：国内服务器，供 FYP 演示与评审，不面向大众开放。任务重点是把有资料依据的中英文计算机课程内容转换为音频、配图和视频。文档图片理解与生成教学图片属于不同能力，应保留独立配置。

## 1. 初步决策

以阿里云百炼北京地域作为第一轮主平台，减少账号、地域和接入方式的组合数量。语音选择 Qwen Audio，图像选择 Qwen Image，生成式视频选择 Wan。MiniMax 语音、Seedream 图像和其他国内视频模型作为对照。此决定依据平台适配与实验成本，并不表示已证明这些模型的教学质量最好。

| 用途 | 第一轮候选 | 接入平台 | 官方价格核查 |
|---|---|---|---|
| 讲解音频 | `qwen-audio-3.1-tts-flash` | 百炼北京 | ¥1 / 万计费字符 |
| 语音质量对照 | `qwen-audio-3.0-tts-plus` | 百炼北京 | ¥1.4 / 万计费字符 |
| 教学配图 | `qwen-image-3.0` | 百炼北京 | 1K/2K 输出 ¥0.18/张；参考输入 ¥0.02/张 |
| 图像质量对照 | `qwen-image-3.0-pro` | 百炼北京 | 1K ¥0.25/张、2K ¥0.50/张；参考输入另计 |
| 生成式短片 | `wan3.0-video` | 百炼北京 | 720P 标价 ¥0.60/秒，1080P ¥1.20/秒；输入视频与输出视频时长相加计费 |
| 低成本图生视频基线 | `wan2.6-i2v-flash` | 百炼北京 | 720P、`audio=false`，¥0.15/输出秒 |

来源：[百炼官方定价](https://help.aliyun.com/zh/model-studio/model-pricing)。价格保留原地域与原币种，预算使用标价，不依赖限时折扣或赠送额度。按上述输出单价，100 张 Qwen 标准版图片约 ¥18；无输入视频的 10 秒 Wan3 720P 输出约 ¥6。实际账单还可能包含参考输入、重试及其他步骤。

## 2. 语音：术语准确性优先

Qwen Audio 提供语气指令、语速等控制与 `hot_fix` 发音/文本替换。音色和具体模型支持的功能不完全一致，应固定组合验证。先使用预设音色，不把声音克隆加入首轮范围。数学公式与代码应先转换为核对过的口语脚本，并与原文分别保存版本。[Qwen Audio HTTP API](https://help.aliyun.com/en/model-studio/cosyvoice-tts-http-api)、[SSML 与公式能力](https://help.aliyun.com/zh/model-studio/ssml-latex-user-guide)

国内对照推荐 MiniMax 中国官方 `speech-2.8-hd`，价格 ¥3.50/万计费字符；Turbo 为 ¥2.00/万。MiniMax 的一个汉字按两个计费字符计，其他字符遵循文档规则，不可直接把“万字符”当作“万个汉字”。百炼也列出带 `MiniMax/` 前缀的型号；不同平台的 ID 与参数不能直接混用。MiniMax 的长文本异步合成值得用于整节课旁白。[MiniMax 中国定价](https://platform.minimax.cn/docs/guides/pricing-paygo)、[语音 HTTP API](https://platform.minimax.io/docs/api-reference/speech-t2a-http)

海外候选为 ElevenLabs `eleven_multilingual_v2` / `eleven_v3`，以及 OpenAI `gpt-4o-mini-tts`。当前部署条件下不作为演示的首要依赖，也没有证据证明其在中英混合计算机术语上优于国内候选。OpenAI 官方说明内置音色主要针对英文优化。[ElevenLabs 模型文档](https://elevenlabs.io/docs/overview/models)、[OpenAI TTS 指南](https://developers.openai.com/api/docs/guides/text-to-speech)

## 3. 图片：区分概念插图与精确图表

Qwen Image 3.0 支持生成和参考图编辑。官方兼容接口仍返回图片 URL，`response_format=b64_json` 会被忽略；Lumori 现有适配器只接受内联图片，因此必须增加结果下载和存储处理，不能仅替换模型名。模型、Key 与 endpoint 必须同地域。[Qwen Image 3.0 API](https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference)

同场比较的国内候选是火山方舟 Seedream 5.0 Lite。官方更新记录列出 `doubao-seedream-5-0-lite-260128`；完整 Ark 接口正文在本轮抓取中受动态页面限制，正式接入前仍须核对控制台可用 ID、参数和账号权限。[官方更新记录](https://www.volcengine.com/docs/6492/2165228?lang=en)、[Seedream 提示指南](https://www.volcengine.com/docs/82379/1829186)

海外对照可保留 `gemini-3.1-flash-image` 与 `gpt-image-2.5-sunburst`，本轮不据厂商介绍宣称其教学效果更佳。Gemini Developer API 地区表未列中国大陆，因此不把其官方直连作为国内演示默认路径。[Gemini 图像 API](https://ai.google.dev/gemini-api/docs/image-generation)、[OpenAI 图像模型](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)、[Gemini 地区](https://ai.google.dev/gemini-api/docs/available-regions)

工程建议：链表、二叉树、网络拓扑、矩阵、算法状态表先生成可验证结构，再用 SVG、Mermaid 或程序绘图渲染。生成图像用于视觉类比、概念插画、背景和参考图编辑。需要精确拼写的标题与符号可以由程序叠加，但必须保留这个处理步骤，不能把最终字形准确率全部归功于图像模型。

## 4. 视频：教学动画与生成短片并行

Wan3 当前为 Preview，支持文生视频、图像参考、首尾帧等控制，最长 30 秒。接口是提交任务、轮询、取回结果的异步流程；官方描述通常需要 1–5 分钟，此时间不是 Lumori 实测数据。演示应显示任务状态，并保留预先生成且明确标识的真实样例。[Wan3 API](https://help.aliyun.com/en/model-studio/wan3-video-generation-api-reference)

首轮分为两条路线：

1. 算法教学视频：已核对的状态序列 → 图表/动画 → 独立 TTS → 字幕与视频合成。可研究 Manim/Remotion/FFmpeg 实现，但本轮尚未接入。
2. 概念说明短片：已审核分镜与参考图 → Wan 等视频 API → 内容复核 → 与解说合成。先测 5–10 秒片段，不直接生成整节长课。

火山方舟官方已列 Seedance2.0 / Fast / Mini，但本轮未从可读取的创建任务正文核实完整 API ID 和个人账户权限，暂列后续候选，不引用第三方猜测的型号。[方舟产品页](https://www.volcengine.com/product/ark)、[视频任务 API](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)

国内视频主要对照建议选 MiniMax 中国官方 `MiniMax-H3`。创建接口为 `POST https://api.minimax.cn/v2/video_generation`，支持 4–15 秒、768P/2K；返回任务 ID 后查询结果。`MiniMax-H3-Max` 是极速版本，支持 5–15 秒、480P/768P，不能按名称推断其质量更高。首尾帧模式和多模态参考模式互斥。[H3 创建接口](https://platform.minimax.cn/docs/api-reference/video-generation-v2-create)、[任务查询](https://platform.minimax.cn/docs/api-reference/video-generation-v2-query)

H3 768P 输出 ¥0.50/秒，2K ¥0.80/秒；少量参考图免费，视频参考及超过免费张数的图片另计。首测 1 张参考图、10 秒、768P 时，输出约 ¥5。与 Wan3 对照时记录 768P/720P 的规格差异，不能把费用或画质差异全部归因于模型。[MiniMax 中国定价](https://platform.minimax.cn/docs/guides/pricing-paygo)

海外视频备选为 `gemini-omni-1.1-flash` 与 Veo3.1；需要单独验证地区与语言适配。Sora 不适合新接入：官方已宣布 Sora2 模型及 Videos API 于 **2026-09-24** 关闭。[Gemini Omni](https://ai.google.dev/gemini-api/docs/omni)、[Veo](https://ai.google.dev/gemini-api/docs/veo)、[OpenAI 视频服务关闭说明](https://developers.openai.com/api/docs/guides/video-generation)

## 5. 现有 OpenRouter 与当前代码适配

OpenRouter 当前已经提供专用图片 `/api/v1/images` 和异步视频 `/api/v1/videos` API，可以保留为跨模型实验入口。现有 Key 不等于已验证具体模型权限、国内网络成功率或价格；型号与供应商应通过对应模型目录确认并记录，不能将底层官方模型 ID 直接当成聚合平台 ID。[OpenRouter 图片 API](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)、[OpenRouter 视频 API](https://openrouter.ai/docs/guides/overview/multimodal/video-generation)

本轮本地代码检查（2026-09-19 工作树，非已发布版本）：

- `app/providers.py` 已有语音与图片入口：语音预期原始 MP3，图片预期 `data[0].b64_json`。原生百炼/MiniMax 的返回格式需独立适配。
- `app/pipeline.py` 媒体生成要求文本已审核且版本匹配，保存文本版本与哈希；当前单段语音有 3,800 字符限制。
- `app/static/multimodal.js` 的视频仍为 upcoming，尚无完整生成流程。

建议新增统一后台媒体任务，保存提供商、精确型号、地域、输入版本、参数、任务 ID、计费和状态。处理超时后的任务恢复，避免盲目重新提交导致重复收费。临时媒体链接应及时转存，并沿用账号数据隔离。文本通过审核不表示新生成图片、音频、视频自动通过事实审核。

## 6. 第一轮对照实验计划（尚未执行）

| 模态 | 固定样本 | 主要比较 |
|---|---|---|
| 语音 | 12 段：中文/英文/混合各 4；包含 SQL、FIFO、O(log n)、否定句与公式 | Qwen Flash、Qwen Plus、MiniMax HD；术语准确率、漏读增读、听懂程度、耗时及成本 |
| 图片 | 12 项：中英文各 6；精确关系图与概念插画分别统计 | Qwen 标准/Pro、Seedream；标签文字、实体与连接关系、编辑遵从性、合格率 |
| 视频 | 6 个固定分镜，中英文各 3；每候选重复生成 2 次，约 5–10 秒 | Wan3、低成本图生视频、MiniMax H3；步骤顺序、关系保持、字幕、音画对齐、合格率 |

先锁定课程资料、脚本、分镜、参考图与评分规则，再调用候选。保存全部输出与失败，不挑最好样片代替完整实验。每次记录请求时间、型号/版本、供应商、输入规格、输出规格、重试次数、总成本与结论。以“总支出 / 合格输出数”报告每份可用教学素材成本，失败和返工也纳入。

自动检查、AI 辅助审阅、真实教师/学生评价分别标注；AI 审阅不能记录为独立人工评审。模型选择先看内容正确性和可用性，再比较主观观感、延迟与费用。样本规模小的结果只支持试点决策，不直接外推到所有课程或宣称提升学习效果。

## 7. 状态与下一步

已完成：模型与官方平台筛选、价格地域核对、当前适配器差距检查、试点评测设计。

尚未完成：账号权限检查、国内服务器网络实测、生成调用、质量评分与模型最终定选。本轮未修改应用代码、未启用多模态付费调用。
