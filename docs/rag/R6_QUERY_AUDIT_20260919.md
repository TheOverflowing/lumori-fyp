# R6 query-only intention audit — 2026-09-19

## Status and evidence boundary

This is a second **AI-assisted query-only audit**, not human annotation, educator validation, or an independent estimate of retrieval relevance. The reviewer inspected only `original_text` and `colloquial_text`, with query IDs used for traceability. No answer, source passage, relevance label, retrieval output, or rewrite-model response was consulted in making these judgments.

- Input: `benchmarks/rag/query-rewrite-v1/queries.json`
- Input file SHA-256: `0d0feeea5d17b85705d412cc9a2b4d6aab91aa5351c99549e86c95994631dd0d`
- Reviewed: 40 queries (20 paired families, English and Chinese).
- Disposition: all 40 are acceptable for the proposed mild colloquial-perturbation diagnostic; no mandatory edit identified.
- The source query file was not modified by this review.
- Criterion: preserve the requested information, entities, quantities, negation, restrictions, and unresolved references. Conversational framing and first-person phrasing are allowed.
- “Pass” means acceptable intent fidelity for this diagnostic. It does not certify that the original question is complete, correctly translated, factually meaningful, or answerable.

## Interpretation limits

1. Most perturbations add conversational framing or mild paraphrase while keeping technical terms. The resulting experiment does not establish robustness to severe ellipsis, implicit multi-turn context, dialect, arbitrary spelling errors, or removal of essential entities.
2. The `canonical` arm should be described as the **original benchmark wording reference**, not a manually corrected canonical gold query. Some original English wording is awkward or apparently erroneous. The English strings containing `cook` and `developing problems` deliberately retain those original words; a rewrite might improve retrieval by correcting a suspected error, a mechanism distinct from removing conversational language.
3. Existing unresolved references such as “these APIs”, “the program”, the unnamed minor upgrade, and the Performance tab remain unresolved. A rewrite must not invent the missing entity. A clarification or unchanged-query fallback can be appropriate.
4. English/Chinese originals are not always literal equivalents: examples include Morro versus 小丘, cook versus 书, and developing problems versus 程序开发. Slice comparisons should acknowledge inherited language asymmetry.
5. This audit supplies a reproducible qualitative assessment of query fidelity only. It does not create new human relevance labels or justify declaring all variants semantically identical in every possible context.
6. Any later revision motivated by retrieval results creates a new dataset version; do not silently edit the frozen queries or replace a poor-performing example.

## Per-query judgments

| Query ID | Judgment | Query-only rationale |
|---|---|---|
| `ba89994b4a3022079a0498e7304e7183af27d824-en` | Pass | Microsoft/C++ 与“还添加什么”的开放补充项保持；大小写和空格差异不改变实体。 |
| `ba89994b4a3022079a0498e7304e7183af27d824-zh` | Pass | Microsoft/C++ 与“还添加什么”的开放补充项保持；大小写和空格差异不改变实体。 |
| `dcf3b56ecf9af55b4761170adcaeaaae9ec28ab9-en` | Pass — source wording caveat | 母公司、外围设备和出版领域保持；英文 founded solutions 的原始不自然措辞未擅自纠正，不能据此断言英文原问题本身明确。 |
| `dcf3b56ecf9af55b4761170adcaeaaae9ec28ab9-zh` | Pass — source wording caveat | 母公司、外围设备和出版领域保持；英文 founded solutions 的原始不自然措辞未擅自纠正，不能据此断言英文原问题本身明确。 |
| `592d6edc47227423980f8f007e60384bcdcfc414-en` | Pass — mild wording caveat | Windows Mobile、汽车用途和另一用途的问法保持；英文 cars 比 automotive 更具体，但此处仍明确询问汽车之外的另一用途。可在下轮预注册时统一为 automotive use，当前不按检索结果改写。 |
| `592d6edc47227423980f8f007e60384bcdcfc414-zh` | Pass — mild wording caveat | Windows Mobile、汽车用途和另一用途的问法保持；英文 cars 比 automotive 更具体，但此处仍明确询问汽车之外的另一用途。可在下轮预注册时统一为 automotive use，当前不按检索结果改写。 |
| `3944a7514988e371d977973aed5dc78d34b34d00-en` | Pass — unresolved referent | 平台目标保持；these APIs/这些 API 的缺失指代来自原问句，审核不补造 API 名称。 |
| `3944a7514988e371d977973aed5dc78d34b34d00-zh` | Pass — unresolved referent | 平台目标保持；these APIs/这些 API 的缺失指代来自原问句，审核不补造 API 名称。 |
| `a601c310538e74c0410a87e363b2ebf79a92090e-en` | Pass | 目标为每加仑行驶英里数，单位保留；英文保留 plug-in，中文不额外添加原中文没有的插电式限定。 |
| `a601c310538e74c0410a87e363b2ebf79a92090e-zh` | Pass | 目标为每加仑行驶英里数，单位保留；英文保留 plug-in，中文不额外添加原中文没有的插电式限定。 |
| `0b88b2cb12a32df0d86cca8ed7ab3d1279b76622-en` | Pass | 无管理员权限的前提及如何登录的目标保持；第三人称到第一人称不改变条件。 |
| `0b88b2cb12a32df0d86cca8ed7ab3d1279b76622-zh` | Pass | 无管理员权限的前提及如何登录的目标保持；第三人称到第一人称不改变条件。 |
| `8a180f4ebe6ee6a6f4e423270db1f5959d031353-en` | Pass — original-language asymmetry | 英文引用保留疑似笔误 cook，未推断为 book；中文原问题已问书，口语版询问书名。两种语言原始措辞的质量不对等。 |
| `8a180f4ebe6ee6a6f4e423270db1f5959d031353-zh` | Pass — original-language asymmetry | 英文引用保留疑似笔误 cook，未推断为 book；中文原问题已问书，口语版询问书名。两种语言原始措辞的质量不对等。 |
| `09ce36a5de7f2832466f260292fbf807a316e596-en` | Pass | 恶意程序兼容哪些操作系统改述为能在哪些系统运行，保留查询对象与兼容性目标。 |
| `09ce36a5de7f2832466f260292fbf807a316e596-zh` | Pass | 恶意程序兼容哪些操作系统改述为能在哪些系统运行，保留查询对象与兼容性目标。 |
| `dda9dc69388e8570cb06daba61091bc4dd97b41e-en` | Pass — unresolved referent | 小幅/较小升级的名称目标保持；并未补充是哪项产品或版本。 |
| `dda9dc69388e8570cb06daba61091bc4dd97b41e-zh` | Pass — unresolved referent | 小幅/较小升级的名称目标保持；并未补充是哪项产品或版本。 |
| `b1f082d1a1f5c08b20a41307cf8933cb28bf538e-en` | Pass | CERN/欧洲核子研究中心、宣布、免费万维网与时间目标保留。 |
| `b1f082d1a1f5c08b20a41307cf8933cb28bf538e-zh` | Pass | CERN/欧洲核子研究中心、宣布、免费万维网与时间目标保留。 |
| `62991f321504514ca359bafe5e5c5ee70e0ac736-en` | Pass — original-language asymmetry | 英文保留 Morro，中文保留“小丘”；不自行认定该词对应的软件或实体。跨语名称差异不是本轮口语扰动制造的。 |
| `62991f321504514ca359bafe5e5c5ee70e0ac736-zh` | Pass — original-language asymmetry | 英文保留 Morro，中文保留“小丘”；不自行认定该词对应的软件或实体。跨语名称差异不是本轮口语扰动制造的。 |
| `102fc1d7e8b2dd1b6b5a206ecae9a66d5bc85035-en` | Pass | Google/谷歌、Manhattan/曼哈顿与办公地点/地址目标保留。 |
| `102fc1d7e8b2dd1b6b5a206ecae9a66d5bc85035-zh` | Pass | Google/谷歌、Manhattan/曼哈顿与办公地点/地址目标保留。 |
| `5881daefb343d7edc39e4894ef4c0fac6fd180b4-en` | Pass | Softpedia、2012 与评测对象保留；英文口语版修复了原问句 did ... reviewed 的语法，不新增事实。 |
| `5881daefb343d7edc39e4894ef4c0fac6fd180b4-zh` | Pass | Softpedia、2012 与评测对象保留；英文口语版修复了原问句 did ... reviewed 的语法，不新增事实。 |
| `89d39291f0bb52e14e9dae67c970ef9927bd388a-en` | Pass — source wording caveat | 询问超文本概念存在多久/起源有多早保持；中文保留原本的“隐含”措辞，不将其纠正为英文 underlying 的解释。 |
| `89d39291f0bb52e14e9dae67c970ef9927bd388a-zh` | Pass — source wording caveat | 询问超文本概念存在多久/起源有多早保持；中文保留原本的“隐含”措辞，不将其纠正为英文 underlying 的解释。 |
| `2e8295d077c1faa92d7ef9d97ea726b2f01c4971-en` | Pass — unresolved referent | 右键后选择哪个选项以启动程序保持；未推断程序名。 |
| `2e8295d077c1faa92d7ef9d97ea726b2f01c4971-zh` | Pass — unresolved referent | 右键后选择哪个选项以启动程序保持；未推断程序名。 |
| `6c5a6fc4af7ba42ab451e1d5d35f76d0d815180b-en` | Pass | DOS 的出售方/从谁购买保持；dos 到 DOS 是大小写规范化。 |
| `6c5a6fc4af7ba42ab451e1d5d35f76d0d815180b-zh` | Pass | DOS 的出售方/从谁购买保持；dos 到 DOS 是大小写规范化。 |
| `5bfd33773a60aca0ec82bcd02628fd68de6af419-en` | Pass | 人名、离开 CERN 的事件及年份粒度保持；不额外要求日期或原因。 |
| `5bfd33773a60aca0ec82bcd02628fd68de6af419-zh` | Pass | 人名、离开 CERN 的事件及年份粒度保持；不额外要求日期或原因。 |
| `3cac4b9bfac03831642f85130bad2144ea4e017d-en` | Pass — unresolved referent | Performance/性能选项卡显示的图表种类保持；未推断应用程序名称。 |
| `3cac4b9bfac03831642f85130bad2144ea4e017d-zh` | Pass — unresolved referent | Performance/性能选项卡显示的图表种类保持；未推断应用程序名称。 |
| `952e1e711d2468ac8e59fc7fda3914ae541608aa-en` | Pass — original-language asymmetry | 英文逐字保留 developing problems 的疑似错误，未偷换为 programs；中文原问题已指程序开发，口语版保持。 |
| `952e1e711d2468ac8e59fc7fda3914ae541608aa-zh` | Pass — original-language asymmetry | 英文逐字保留 developing problems 的疑似错误，未偷换为 programs；中文原问题已指程序开发，口语版保持。 |
| `8c5a49b2f896be001b6700222c758dbf448ddd7f-en` | Pass — unresolved referent | 违反规则的原因/目的保持；规则本身仍缺少指代背景，未添加具体规则。 |
| `8c5a49b2f896be001b6700222c758dbf448ddd7f-zh` | Pass — unresolved referent | 违反规则的原因/目的保持；规则本身仍缺少指代背景，未添加具体规则。 |

## Required changes and optional future controls

No mandatory query changes are requested before freezing. One mild wording boundary is recorded for the English Windows Mobile item: `cars` is narrower than `automotive`, although the question still asks for the other supported use. If a future preregistration seeks exact preservation of that phrase, use `automotive use` before running that new version.

A stronger follow-up should preregister separate perturbation categories and include a query-only fidelity check for each: conversational wrapper, lexical paraphrase, typo correction, omitted technical term, and unresolved reference. Their outcomes should remain separate from this 40-query diagnostic.
