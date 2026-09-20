# R6 query-rewrite semantic audit — 2026-09-19

## Scope and evidence boundary

Reviewer: **Codex AI assistant**. This is an **AI-assisted query-only audit**, not human annotation, teacher review, a second independent human rater, or a calibrated semantic-accuracy measure. It is a separate review pass from the DeepSeek rewrite calls. The reviewing assistant also authored the synthetic input perturbations in an earlier subtask; therefore this is not independent of dataset authoring and should not be presented as a blinded external adjudication.

For this review pass, the only input file read was:

`docs/rag/r6-experiments/20260919T153526570109Z/rewrite-audit-inputs.json`

Input SHA-256: `99927988bb538d7d73684ea6206ac26e0a10a3a2a0a1574b216b97da5075fe18`.

The file exposes 40 colloquial inputs, language, visible model output, parsed response, and validation status. No canonical query file, source documents, answers, relevance labels, retrieval rankings, or retrieval metrics were consulted in this pass. Every supplied row is included below, including validation failures. Assessment compares each rewrite only with that row's colloquial input; it does not use a counterpart language to repair an input. This document does not modify the run outputs or retrospectively select/exclude cases.

The review checks named entities, numbers and units, negations and relational qualifiers, answer type, newly asserted facts, unresolved references, and whether preserving the original is a reasonable fallback. A concise keyword query can be useful for retrieval while being unsuitable as the sole instruction for downstream answer generation. Query-only preservation is not evidence of improved retrieval.

## Observed protocol outcomes and review categories

| Outcome | Count | Interpretation |
|---|---:|---|
| Validation succeeded and text changed | 20 | 7 English and 13 Chinese outputs |
| Validation succeeded; original text preserved with `needs_clarification=true` | 13 | 8 English and 5 Chinese outputs |
| Validation failed | 7 | 5 English and 2 Chinese outputs; all have `rewrite_clarification_must_preserve_input` |
| Total audited | 40 | No row excluded |

All seven failures have a visible JSON proposal that requests clarification while also shortening the input. They are **contract/validation failures**, not demonstrated network errors, missing provider responses, or seven observed hallucinations. The input file does not include the effective query passed to retrieval, so this audit can recommend and assess an original-input fallback but cannot independently verify that downstream fallback executed. For the 13 successful clarification responses, exact input preservation is directly observable.

| AI review category | Count | Meaning |
|---|---:|---|
| `rewrite_ok` | 14 | No definite material change found from the visible input; no retrieval-quality claim |
| `rewrite_scope_warning` | 4 | A relational or referential qualifier is visibly dropped; actual retrieval harm remains unmeasured here |
| `rewrite_ambiguity_warning` | 2 | Main intent is retained, but missing context remains despite `needs_clarification=false` |
| `preserve_clarification` | 13 | Exact input preservation; clarification is reasonable or conservative |
| `rejected_clarification` | 7 | Proposal rejected by the exact-preservation contract; original-input fallback is appropriate |

These counts are descriptive review dispositions, not an automatic accuracy score. In particular, the 14 `rewrite_ok` cases are not a validated teaching-quality or retrieval-success rate.

## Important findings

1. **Relational qualifiers can disappear.** The Chinese Microsoft/C++ rewrite drops “还,” converting an additional-item question into a general question about additions. The automotive Windows Mobile pair, by contrast, retains “what else”/“除了.” This suggests a concrete preservation requirement for words such as “else,” “other,” “except,” and their Chinese equivalents.
2. **Keyword compression can hide unresolved references.** “那些恶意程序” becomes generic malware compatibility keywords; “that plug-in hybrid electric vehicle” and “那本书” lose their specific references. No replacement entity is fabricated, but omission can widen the target. Such cases should keep the original query available and expose unresolved context rather than treating the compression as a complete interpretation.
3. **Clarification decisions are not consistent across languages.** Both API, minor-upgrade, right-click, and rules pairs preserve their inputs. The administrator-login, malware, Performance-tab, and Google-office pairs receive different clarification behavior across languages. Some surface forms differ, and this small constructed sample does not establish language bias; it does show that one language's flag cannot be assumed to represent its counterpart.
4. **The strict fallback contract has a measurable operational consequence.** Seven proposals correctly express uncertainty but also remove filler, so they fail validation. This protects the exact original input under the chosen contract, but the failures should be reported as policy noncompliance rather than provider unavailability. Any future contract relaxation must be preregistered and separately evaluated, not retroactively used to relabel this run.
5. **No concrete answer, new named entity, date, quantity, or framework was observed being invented in the 40 visible proposals.** This narrower observation does not establish complete intent preservation: qualifiers and scope can still change. The anomalous “cook” and “developing problems” inputs were flagged rather than silently corrected.

## Per-query review

For failed rows, “visible proposal” below is the model's rejected output and must not be interpreted as an accepted rewrite. For successful rows, the same field reflects the accepted response. The input file itself remains the authoritative raw evidence.

### 01. `ba89994b4a3022079a0498e7304e7183af27d824-en`

- Input: Wait, what else was it that Microsoft added to C++? I'm a bit lost on that part.
- Visible proposal: What else did Microsoft add to C++?
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible proposal keeps Microsoft, C++, and “what else”; trimming filler is not itself a semantic failure. However, clarification=true conflicts with changing the input under the recorded validator contract. Preserve the complete original on rejection. The unresolved “else” makes conservative clarification reasonable.

### 02. `ba89994b4a3022079a0498e7304e7183af27d824-zh`

- Input: 我有点绕晕了，微软还给 C++ 加了什么东西来着？
- Visible proposal: 微软给 C++ 加了什么
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_scope_warning`. The rewrite preserves Microsoft and C++ but deletes “还” (what else/additionally). Asking for all additions is broader than asking for the additional item. This is a visible loss of a relational qualifier, although no particular answer is invented. Prefer retaining “还” and leave its missing reference unresolved rather than silently generalizing.

### 03. `dcf3b56ecf9af55b4761170adcaeaaae9ec28ab9-en`

- Input: I'm going over this for practice: which parent company was it that founded solutions for computer peripherals and publishing?
- Visible proposal: which parent company founded solutions for computer peripherals and publishing
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The proposed text retains the parent-company answer type and both computer-peripherals and publishing constraints. The awkward “founded solutions” and unspecified company context remain unresolved. The validation failure is a clarification/preservation contract violation, not observed answer hallucination. Keeping the original is a defensible fallback.

### 04. `dcf3b56ecf9af55b4761170adcaeaaae9ec28ab9-zh`

- Input: 我想复习一下这点：给计算机外围设备和出版业找到解决方案的，那家母公司到底是哪家呀？
- Visible proposal: 给计算机外围设备和出版业找到解决方案的母公司是哪家
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible shorter question preserves parent-company identity and both application domains. It requests clarification but removes the original study wrapper, violating the exact-preservation requirement. The parent-company reference is still unresolved; reverting to the complete input is appropriate under this contract.

### 05. `592d6edc47227423980f8f007e60384bcdcfc414-zh`

- Input: Windows Mobile 除了汽车这块，还能用在哪个领域啊？
- Visible proposal: Windows Mobile 除了汽车领域还能用在哪个领域
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. “汽车这块” becomes “汽车领域,” while “除了” and the request for an additional domain remain explicit. The product and exclusion constraint are preserved.

### 06. `592d6edc47227423980f8f007e60384bcdcfc414-en`

- Input: So Windows Mobile is available for cars, but what else is it available for?
- Visible proposal: Windows Mobile available for cars, what else is it available for?
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains Windows Mobile, the automotive context, and the request for another supported domain. Removing “So” changes only discourse packaging. No new domain, entity, or answer is supplied.

### 07. `3944a7514988e371d977973aed5dc78d34b34d00-en`

- Input: I'm not clear on where these APIs get used. Which platforms are we talking about?
- Visible proposal: I'm not clear on where these APIs get used. Which platforms are we talking about?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact input is preserved. “These APIs” has no antecedent in the supplied query, so avoiding guessed API names or platforms is appropriate. The flag records uncertainty; it does not resolve that uncertainty or show that the user was actually asked a question.

### 08. `3944a7514988e371d977973aed5dc78d34b34d00-zh`

- Input: 这些 API 到底是用在哪些平台上的呀？这块我还没搞明白。
- Visible proposal: 这些 API 到底是用在哪些平台上的呀？这块我还没搞明白。
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact input is preserved. “这些 API” remains unspecified. Clarification is a defensible response because neither an API family nor a platform should be invented from this query alone.

### 09. `a601c310538e74c0410a87e363b2ebf79a92090e-en`

- Input: For that plug-in hybrid electric vehicle, how far can it go on a gallon of fuel, in miles? I just want to check the figure.
- Visible proposal: plug-in hybrid electric vehicle miles per gallon
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_scope_warning`. The vehicle class and miles-per-gallon unit are retained, but “that” is removed and a question about a referenced vehicle becomes a class-level keyword phrase. The absent vehicle identity has not been resolved. No fuel-economy number is invented; the concern is potential scope broadening and an overconfident false clarification flag.

### 10. `a601c310538e74c0410a87e363b2ebf79a92090e-zh`

- Input: 我就想确认一下那个数字：混合动力电动载具用一加仑燃料，能跑多少英里呀？
- Visible proposal: 混合动力电动载具一加仑燃料能跑多少英里
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. The hybrid-electric vehicle description, one-gallon denominator, miles numerator, and request for the numerical value are retained. Removing “确认一下那个数字” drops conversational framing, not a vehicle identifier supplied in this input.

### 11. `0b88b2cb12a32df0d86cca8ed7ab3d1279b76622-en`

- Input: Suppose I don't have admin rights. How would I log in as a user then?
- Visible proposal: Suppose I don't have admin rights. How would I log in as a user then?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the lack of administrator privileges and the login-method request. The system or service is unnamed; conservative clarification is reasonable, though this file alone cannot establish that retrieval from an already selected course would require it.

### 12. `0b88b2cb12a32df0d86cca8ed7ab3d1279b76622-zh`

- Input: 假如我这个用户没有管理员权限，那我该怎么登录呢？
- Visible proposal: 没有管理员权限 怎么登录
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ambiguity_warning`. The absence of administrator permissions and login-method intent are retained. No system, service, or account context is added. The text is a faithful compression, but needs_clarification=false should not be read as proof that the unspecified login environment is resolved; the English counterpart is more conservative.

### 13. `8a180f4ebe6ee6a6f4e423270db1f5959d031353-en`

- Input: I'm stuck on this question: 'What cook did Berners-Lee write?' Can you help me work that out?
- Visible proposal: What cook did Berners-Lee write?
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible output retains the unusual phrase “What cook did Berners-Lee write?” and correctly avoids guessing a replacement word or book title. Its clarification=true is reasonable, but stripping the wrapper violates exact preservation. Falling back to the original preserves this visible wording defect for later clarification.

### 14. `8a180f4ebe6ee6a6f4e423270db1f5959d031353-zh`

- Input: 伯纳斯-李写过的那本书，叫什么来着？我想把这一点记清楚。
- Visible proposal: 伯纳斯-李 写过 的 书 叫什么
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_scope_warning`. The author and request for a book name survive, but “那本书” becomes a generic “书.” The query does not identify the referenced book; replacing that reference with an unqualified book request can broaden the target. No title is hallucinated. Retaining the specific reference or flagging unresolved ambiguity is preferable.

### 15. `09ce36a5de7f2832466f260292fbf807a316e596-en`

- Input: Which operating systems can those malware programs actually run on? That compatibility bit is confusing me.
- Visible proposal: Which operating systems can those malware programs actually run on? That compatibility bit is confusing me.
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation retains “those malware programs,” the operating-system answer type, and compatibility. Because the malware set is unidentified, conservative clarification is well grounded in the visible text.

### 16. `09ce36a5de7f2832466f260292fbf807a316e596-zh`

- Input: 那些恶意程序到底能在哪些操作系统上运行啊？兼容性这块我有点没弄懂。
- Visible proposal: 恶意程序 运行 操作系统 兼容性
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_scope_warning`. Deletes “那些” and turns a question about a particular malware set into generic malware/operating-system/compatibility keywords. The operating-system topic remains, but the set restriction is lost. This is a visible scope risk; clarification=false does not supply the missing malware identity.

### 17. `dda9dc69388e8570cb06daba61091bc4dd97b41e-en`

- Input: There was that minor upgrade—what was its name again?
- Visible proposal: There was that minor upgrade—what was its name again?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation retains the minor-upgrade name request. The product and upgrade are not identified in the input, so declining to expand them is appropriate.

### 18. `dda9dc69388e8570cb06daba61091bc4dd97b41e-zh`

- Input: 那个小一点的升级版本，名字叫啥来着？
- Visible proposal: 那个小一点的升级版本，名字叫啥来着？
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the smaller-upgrade reference and name slot. The absent product/version context remains visible; clarification is appropriate without guessing it.

### 19. `b1f082d1a1f5c08b20a41307cf8933cb28bf538e-en`

- Input: Could you help me check when CERN said the World Wide Web would be free?
- Visible proposal: when CERN said the World Wide Web would be free
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains CERN, the World Wide Web being free, and the time of the announcement. Removes only the polite checking wrapper. No date is introduced.

### 20. `b1f082d1a1f5c08b20a41307cf8933cb28bf538e-zh`

- Input: 帮我理一下这个时间点：欧洲核子研究中心是什么时候宣布万维网免费的呀？
- Visible proposal: 欧洲核子研究中心 宣布 万维网 免费 时间
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Keyword form preserves the organization, announcement event, World Wide Web, free status, and time slot. The answer type remains explicit as “时间.”

### 21. `62991f321504514ca359bafe5e5c5ee70e0ac736-en`

- Input: I've got the name Morro here, but what is it, exactly?
- Visible proposal: I've got the name Morro here, but what is it, exactly?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation avoids guessing what the name Morro denotes. Clarification is conservative and defensible, but without source context it cannot be established that the name is actually ambiguous within the selected corpus. This is not an erroneous rewrite.

### 22. `62991f321504514ca359bafe5e5c5ee70e0ac736-zh`

- Input: 我看到“小丘”这个词，有点不懂，它到底是什么呀？
- Visible proposal: 小丘 是什么
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains the literal term “小丘” and the definition request. Does not substitute any English entity or provide a definition. Whether the term refers to a technical name or an ordinary noun cannot be settled by query-only review.

### 23. `102fc1d7e8b2dd1b6b5a206ecae9a66d5bc85035-zh`

- Input: 谷歌在曼哈顿的那个办公楼，到底是哪个地址啊？
- Visible proposal: 谷歌在曼哈顿的那个办公楼，到底是哪个地址啊？
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation retains the office/address slot and “那个” reference. Conservative clarification may help distinguish offices, but no evidence in this file establishes that such clarification is necessary. The English counterpart is normalized without the same flag.

### 24. `102fc1d7e8b2dd1b6b5a206ecae9a66d5bc85035-en`

- Input: Whereabouts in Manhattan is the Google office? I mean the actual location.
- Visible proposal: Where is the Google office in Manhattan located?
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Google, Manhattan, and the office-location request remain. “Whereabouts” is normalized to “Where ... located”; no address, office identity, or time constraint is inserted. This does not establish that only one office is possible.

### 25. `5881daefb343d7edc39e4894ef4c0fac6fd180b4-en`

- Input: Back in 2012, what was it that Softpedia reviewed? I need to refresh my memory.
- Visible proposal: Softpedia reviewed 2012
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains Softpedia, 2012, and the review relation. Keyword compression omits the explicit “what” answer slot but does not add or replace an object. It is a plausible retrieval query, not a complete restatement of the task; the original should remain the generation instruction.

### 26. `5881daefb343d7edc39e4894ef4c0fac6fd180b4-zh`

- Input: 我想回顾一下，Softpedia 在 2012 年评论的到底是什么东西呀？
- Visible proposal: Softpedia 2012 年评论
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains Softpedia, 2012, and the review topic. The reviewed-item request becomes implicit in a keyword query; no object is supplied. Keep the original question for answer generation even if using this phrase for retrieval.

### 27. `89d39291f0bb52e14e9dae67c970ef9927bd388a-en`

- Input: How far back does the basic idea behind hypertext go? I’m trying to get a feel for how old it is.
- Visible proposal: history of hypertext basic idea origin
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. “history,” “basic idea,” and “origin” retain the temporal-origin intent for hypertext without inventing an inventor or date. The wording is broader than a direct “how far back” question but still targets its origin; no definite qualifier loss is visible.

### 28. `89d39291f0bb52e14e9dae67c970ef9927bd388a-zh`

- Input: 我想弄明白它到底有多久的历史：隐含的超文本概念，多早以前就已经有了呀？
- Visible proposal: 隐含的超文本概念有多久的历史？
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains the underlying/implicit hypertext concept and its historical age. Conversational framing is removed while the temporal question remains explicit.

### 29. `2e8295d077c1faa92d7ef9d97ea726b2f01c4971-en`

- Input: If I want to start the program using right-click, which option do I pick after that?
- Visible proposal: If I want to start the program using right-click, which option do I pick after that?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the right-click action, starting a program, and the subsequent option-name slot. The unspecified program/platform makes clarification sensible; no menu item is guessed.

### 30. `2e8295d077c1faa92d7ef9d97ea726b2f01c4971-zh`

- Input: 我要用右键那个办法启动程序，点完右键以后该选哪一项呢？
- Visible proposal: 我要用右键那个办法启动程序，点完右键以后该选哪一项呢？
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the right-click sequence and startup option request. Clarification appropriately avoids inventing the program or menu item.

### 31. `6c5a6fc4af7ba42ab451e1d5d35f76d0d815180b-en`

- Input: Hang on, who did DOS get bought from in the first place?
- Visible proposal: who did DOS get bought from in the first place
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible proposal preserves DOS and the seller/source-of-purchase question, while removing filler. The model requests clarification but changes the input, causing the recorded contract failure. DOS alone may not identify a unique transaction; retaining the original is a reasonable fallback without guessing one.

### 32. `6c5a6fc4af7ba42ab451e1d5d35f76d0d815180b-zh`

- Input: 等一下，DOS 当时到底是从谁手里买来的呀？
- Visible proposal: DOS 当时到底是从谁手里买来的呀？
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible proposal keeps DOS and the seller slot; only the opening filler is removed. The failure comes from exact-preservation policy with clarification=true, not an observed wrong seller. Preserve the whole original on fallback; no buyer, year, or version should be inferred.

### 33. `5bfd33773a60aca0ec82bcd02628fd68de6af419-en`

- Input: For my revision notes, I need the year Tim Berners-Lee left CERN. What year was that again?
- Visible proposal: What year did Tim Berners-Lee leave CERN?
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Preserves Tim Berners-Lee, CERN, the departure event, and year granularity. Only revision-note framing and repetition are removed. No date is invented.

### 34. `5bfd33773a60aca0ec82bcd02628fd68de6af419-zh`

- Input: 我在整理复习笔记，蒂姆伯纳斯离开欧洲核子研究中心是在哪一年啊？
- Visible proposal: 蒂姆伯纳斯离开欧洲核子研究中心是在哪一年
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Preserves the supplied person name, organization, departure event, and year slot. Removing the study wrapper changes no visible constraint.

### 35. `3cac4b9bfac03831642f85130bad2144ea4e017d-en`

- Input: That Performance tab—what sort of chart does it show? I'm not sure I have that straight.
- Visible proposal: That Performance tab—what sort of chart does it show? I'm not sure I have that straight.
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation retains the Performance-tab chart-type request. The application is unnamed; conservative clarification is reasonable and avoids inferring a particular product.

### 36. `3cac4b9bfac03831642f85130bad2144ea4e017d-zh`

- Input: 那个“性能”选项卡里显示的是哪种图表呀？我有点记不清了。
- Visible proposal: “性能”选项卡里显示的是哪种图表
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ambiguity_warning`. Preserves the “性能” tab and chart-type slot, while removing filler and “那个.” The application was never specified, so the rewrite does not resolve it. The normalized text is semantically plausible, but the false clarification flag is less conservative than the corresponding English output.

### 37. `952e1e711d2468ac8e59fc7fda3914ae541608aa-en`

- Input: I'm revising this question: 'What frameworks can be used to support developing problems for mobile devices?' Could you help with that?
- Visible proposal: What frameworks can be used to support developing problems for mobile devices?
- Recorded status: `failed`; `needs_clarification=true`; error `rewrite_clarification_must_preserve_input`.
- AI review: `rejected_clarification`. The visible output preserves the anomalous “developing problems for mobile devices” rather than silently replacing it or naming frameworks. Clarification is reasonable, but removing the wrapper breaches exact preservation. Retain the original for fallback and ask about the ambiguous wording before interpreting it.

### 38. `952e1e711d2468ac8e59fc7fda3914ae541608aa-zh`

- Input: 想学一下移动设备程序开发这块，有哪些框架能给这类开发提供支持呀？
- Visible proposal: 移动设备程序开发 框架 支持
- Recorded status: `succeeded`; `needs_clarification=false`.
- AI review: `rewrite_ok`. Retains mobile-device program development, frameworks, and support. Omits the learning wrapper without adding framework names or changing the development domain; the requested set remains implicit in the keyword form.

### 39. `8c5a49b2f896be001b6700222c758dbf448ddd7f-en`

- Input: I'm trying to understand the reason here: what are the rules being violated for?
- Visible proposal: I'm trying to understand the reason here: what are the rules being violated for?
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the reason/purpose request. “The rules” lacks an antecedent, so clarification is appropriate; no rules or motives are guessed.

### 40. `8c5a49b2f896be001b6700222c758dbf448ddd7f-zh`

- Input: 我主要没想明白原因：为什么要违反这些规则呀？
- Visible proposal: 我主要没想明白原因：为什么要违反这些规则呀？
- Recorded status: `succeeded`; `needs_clarification=true`.
- AI review: `preserve_clarification`. Exact preservation keeps the reason for violating “这些规则.” Since the rules are unidentified, retaining the original and requesting context is reasonable.

## Interpretation and follow-up

Keep original user input as the canonical task instruction, regardless of which string is used to search. If experimenting with rewrite-only retrieval, separately count material qualifier loss, conservative unchanged queries, validation failures, and model/service failures. A possible later policy is to use an accepted rewrite as an additional retrieval candidate while preserving the original; this audit does not establish whether that policy is better or justify enabling it by default.

Preserve all 40 inputs in the frozen comparison and show failures in the denominator under the experiment's stated fallback policy. If reporting a sensitivity analysis for ambiguous inputs, define its cases from this text-only audit, disclose the subset, and retain the full-sample primary result. Do not tune the ambiguity list or rewrite prompt after examining per-query retrieval outcomes and then reuse this same sample as untouched held-out evidence.

A proper future semantic study should use fresh real-user or independently authored inputs, domain-aware human adjudicators, explicit agreement measurement, and source-aware clarification checks. The present artifact supports error analysis and protocol transparency only.
