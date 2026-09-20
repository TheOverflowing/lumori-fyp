# R8B: clarity × style diagnostic (version 1)

This dataset contains **64 AI-authored bilingual queries**, with exact support spans from licensed, frozen course material. It is intended for a controlled, one-follow-up clarification experiment. It is **not student data, an independent human annotation set, or an unseen-corpus benchmark**.

## Design

- 8 new information needs, each with one distinct supporting source file.
- 2 query languages: English and Chinese.
- 2 styles: formal and colloquial.
- 2 clarity states: sufficient and underspecified.
- 8 rows per family; 32 sufficient and 32 underspecified queries overall.
- All 12 original R7 course files remain in `documents`, including four that are not positive support documents for this diagnostic.
- Each family has an English and Chinese closed-book intention profile. The two styles and two clarity conditions share the same intended need.

The factorial design separates colloquial language from missing task information: a colloquial query may be fully answerable, while a formally phrased query may omit a crucial condition. Sufficient rows do not require a follow-up just because the user does not know the answer.

| Family | New question | Information omitted in underspecified form | Support language |
|---|---|---|---|
| `binary-boundary-update` | Boundary update for one binary-search iteration | Comparison result | Chinese |
| `hash-quadratic-offset` | Collision probe offsets | Probing strategy | Chinese |
| `avl-rotation-case` | Rotation order for known factor values | Node and child balance factors | Chinese |
| `quick-stack-limit` | Limiting Quicksort recursion stack growth | Optimization objective | Chinese |
| `stack-push-capacity` | Work and cost of an individual dynamic-array stack push | Capacity state | Chinese |
| `graph-cover-components` | Continuing traversal across disconnected components | Whole-graph vs reachable-only coverage | English |
| `insertion-small-input` | Insertion sort on very small arbitrary-order arrays | Input size | English |
| `merge-empty-input` | Merge helper with one exhausted input | Merge step vs recursive base case | English |

These information needs differ from R7's canonical questions. For example, the R7 stack question asked about removal order; this version asks about an individual push at capacity. The R7 insertion-sort question concerned nearly sorted data; this version explicitly assumes arbitrary order and asks about small input sizes.

## Role separation is mandatory

The JSON file is an **authoring/evaluation container**, not a model prompt. Do not send the entire file to any role.

1. **Clarification/search system:** current visible query and the actual follow-up dialogue only. Do not include family identifiers that reveal hidden conditions, canonical sufficient queries, profile, alternatives, labels, evidence, or documents in its question-generation input.
2. **Closed-book user simulator:** current query, generated follow-up question, and the language-matched `intent_profiles` string only. The profile has the user's intended task and known conditions but no requested answer, formula, source identifier, evidence, or retrieval result. The simulator must say it does not know facts absent from this profile; it must not solve the educational question. A request for the answer itself is not a successful clarification.
3. **Evaluator:** may access profiles, expected clarification labels, exact evidence spans, and retrieval outputs. Preserve raw role inputs so isolation can be audited.

`possible_interpretations` is authoring/evaluation metadata demonstrating two materially different plausible intents. It is not an option list to give to the search system or simulator. `families[].queries` is the explicit canonical information need and must remain hidden from both active roles.

Use opaque row identifiers in prompts. The stable descriptive IDs are useful for analysis but could leak the missing condition if shown to the question generator.

## Split and statistical unit

Components connect families sharing positive source documents. This version has 8 components of one family each. Before any retrieval/API result, the components are sorted by:

```text
SHA256(UTF-8("r8b-split:" + lexicographically_smallest_family_id))
```

The first 2 components form the development set and the remaining 6 the test set. The complete hashes and assignments are stored in `metadata.split_components`; every row carries its fixed split and component ID.

- Development: 2 families / 16 rows — disconnected-graph coverage and merge empty-input handling.
- Test: 6 families / 48 rows — all remaining families.
- Each test style × clarity cell has 12 rows, with 6 per language.
- Use paired, component-level analysis. The 48 test rows are not 48 independent information needs.
- Components are source files from **two textbooks**, not independent textbooks or institutions.

This split was generated from the declared `r8b` seed, not selected to improve results. The existing course files and topics have been used in earlier experiments, so the holdout concerns new information needs rather than unseen source material.

## Source provenance and support

`documents` is copied unchanged from the frozen R7 base:

```text
docs/rag/r7-experiments/20260919T161914951306Z/base.json
SHA256 e67e65dbf142d61f3ec8c1cc952298efebb00250a94c61011249aca574ceb836
```

Original paths, URLs, pinned revisions, authors, licences, and SHA-256 checksums are retained. Hello Algo uses CC-BY-NC-SA-4.0; OpenDSA source files carry their original licence metadata. Original raw source markup is preserved; external images, includes, or interactive slides are not expanded. The selected support relies only on text or code actually present in each file.

Each evidence interval uses Unicode code-point offsets `[start, end)` in its document's `text`. These are known sufficient spans rather than exhaustive relevance judgments. Absence from this list does not establish irrelevance.

The dataset author inspected the frozen course texts and R7 canonical questions, but did not inspect retrieval rankings, call models, use human annotations, or change original human files. Validation checked every document against its frozen on-disk source and SHA-256, every evidence substring, all 64 unique IDs, factorial counts, and consistent split membership.

## Interpretation boundaries

- `requires_clarification=true` means the missing information is required to select **this benchmark's intended single case**. A product could also reasonably answer multiple cases or state an assumption; the label does not establish that a follow-up is universally mandatory.
- For example, an unspecified binary-search comparison can be answered with a complete case table. That response may be useful even when it does not retrieve the profile's one selected case first.
- A no-follow-up retrieval miss against hidden intent does not prove that a different answer to the visible ambiguous query is incorrect. Call this **conditional-intent retrieval** and report it separately from sufficient-query retrieval.
- Report follow-up detection, false follow-up rate, question answerability from the profile, number of interactions, clarification resolution, and retrieval quality separately.
- Evaluate generated follow-up questions for answer leakage. Asking the user for the answer or for the relevant document is not an acceptable way to improve retrieval.
- This small synthetic set cannot establish real-user satisfaction, real-world ambiguity prevalence, general university-course coverage, or optimal production routing.

## Schema

- `metadata`: design, role isolation, provenance, limitations, fixed split components.
- `documents[]`: the 12 source documents with complete frozen text and provenance.
- `families[]`: `id`, canonical bilingual `queries`, bilingual hidden `intent_profiles`, exact `evidence`, `source_ids`, `ambiguous_slot`, bilingual `possible_interpretations`, novelty statement, component and split.
- `queries[]`: `id`, `family_id`, `language`, `style`, `clarity`, visible `text`, `requires_clarification`, component and split.

The JSON itself is the durable dataset. Hash it before any online experiment and retain a frozen copy alongside the role projections and call ledger.

## 冻结前审核修订

2026-09-20：原数据SHA256 30e7c86c7150ed2a2abdd0a839e3cc55d1705d6854975ee8c6a6618e70efe7de。API与排名生成之前，统一采用协议中的SHA256(r8b-split:+文档分量family代表)划分，dev为graph-cover-components, merge-empty-input，其余六个需求test。AVL明确输入及用户profile补充左高度减右高度的符号约定；平方探测统一说明相对最初冲突槽位的偏移；证据来源说明允许原文内已有代码。以上不补入所问的旋转顺序、探测公式或其他答案。主文与dataset.json元数据已经同步修正。AVL证据扩展到原文表头与两行；快排两种风格统一保持基准选择不变且询问最坏栈空间；图遍历口语版本补齐无向条件。
