# Query rewrite pilot: synthetic colloquial perturbations

Created: 2026-09-19. Author and intent reviewer: **Codex AI assistant**.

This file provides 40 paired query inputs (20 English, 20 Chinese; 20 bilingual families) for a controlled query-rewrite experiment. Each original public QA question has one deliberately more conversational variant. This is a **synthetic colloquial perturbation benchmark**, not real user logs, human colloquial gold, or a representative undergraduate computer-science course benchmark. It tests sensitivity to these specific paraphrases; it does not establish how frequently real learners encounter a retrieval problem.

## Provenance and deterministic selection

Source: `docs/rag/r5-experiments/20260912T085156100010Z/dataset.json`, the existing R5 dataset derived from public MLQA-style bilingual QA material. Source file SHA-256:

`bba11493050bcc137f236220931d714df045d6ff668e473f533b4301b3ca34f0`

The author projected only source query fields `id`, `family_id`, `text`, `language`, and `split`. No source documents, answer strings, relevance labels, or retrieval outputs were inspected for this authoring task. Reading the entire file as bytes to calculate its hash does not expose its other fields to the author.

Selection was fixed before retrieval:

1. Retain queries with `split == "test"` (62 queries, 31 bilingual families).
2. Sort unique family IDs in ascending order of the hexadecimal SHA-256 digest of the UTF-8 string `"r6-family:" + family_id`.
3. Select the first 20 families without topic, answerability, or expected-performance filtering.
4. Keep both `en` and `zh` queries in each selected family. Output is in this family order, English then Chinese.

The source split was the R5 test set. Reusing it here does **not** make this pilot a previously unseen final test for the entire project: earlier R5 results already exist. The narrower protection is that these new perturbations were authored without inspecting their relevance labels or retrieval outcomes. Future policy selection should be confirmed on fresh data.

## Authoring and intent check

Variants use conversational filler, indirect questions, first-person scenarios, colloquial wording, and learning or revision request wrappers. The wording is deliberately varied rather than applying one common prefix. Unique named entities, numbers, units, constraints, and requested answer type are retained. No answer or new domain fact is supplied.

Each row includes the unmodified `original_text`, `colloquial_text`, `transformation_type`, author, the provisional-label disclaimer, and a short `rationale` from an AI self-review against the original question. This is not independent human adjudication. No external generation API was called to author the perturbations. The English and Chinese questions were preserved independently rather than using one to silently repair the other.

Existing answer labels may be reused **provisionally** for an intent-preserving perturbation. They are not copied into `queries.json` and have not been newly validated as relevance gold for the colloquial input. An experimental runner should retain original labels and any inherited-label caveat, not replace them with new claims of human annotation.

### Known inherited defects retained deliberately

- Some source questions refer to “these APIs,” “the minor upgrade,” “the program,” or “the rules” without identifying them. No missing entity is guessed.
- The English query `8a180f4ebe6ee6a6f4e423270db1f5959d031353-en` says “What cook did Berners-Lee write?” The variant quotes the anomalous question; it does not silently change “cook” to “book.”
- The English query `952e1e711d2468ac8e59fc7fda3914ae541608aa-en` says “developing problems for mobile devices.” The variant preserves that wording in a quoted study request; it does not borrow “programs” from the Chinese question.
- Family `62991f321504514ca359bafe5e5c5ee70e0ac736` uses “Morro” in English and “小丘” in Chinese. This cross-language mismatch remains visible and may impair the inherited relevance assumption.
- Family `a601c310538e74c0410a87e363b2ebf79a92090e` includes “plug-in” in English but not Chinese. The perturbations retain each original constraint set separately.

These cases should remain in the preselected denominator, with a separate diagnostic breakdown if needed. Excluding them after seeing performance would introduce a selection bias. With only 20 bilingual families, family-level paired differences and uncertainty are more informative than treating all 40 inputs as independent samples.

## File format and freeze

`queries.json` is an object containing `metadata` and a `queries` list. Its `id` and `source_query_id` retain the existing source query ID, so experiment code can join without reading the authoring rationale as a retrieval input. Only the selected input string should be passed to each query-processing condition. `family_order` records the deterministic selection.

Frozen `queries.json` SHA-256:

`0d0feeea5d17b85705d412cc9a2b4d6aab91aa5351c99549e86c95994631dd0d`

No model or retrieval results are present in this directory. This authoring task does not choose a production rewriting policy. Keep this file unchanged after experimental runs begin; corrections should create a new version and explicitly invalidate comparisons that depended on the previous wording.
