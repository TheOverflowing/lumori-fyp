# R7 query severity variants: authoring and AI review record

Date: 2026-09-20. Author and reviewer: Codex AI. Status: **AI-assisted provisional**, not human annotation and not observed student behaviour.

## Access boundary and provenance

The author read only `canonical-only.json`, containing 12 family IDs and their 24 canonical English/Chinese questions. The author did **not** read the corpus, `base.json`, course materials, answer keys, relevance labels, previous retrieval results, or model responses, and made no API calls. All L1–L4 wording and ambiguity interpretations were written from the visible canonical questions alone. L0 is copied character-for-character from the corresponding canonical question. Chinese and English variants were authored independently from their own canonical wording, rather than translating and silently correcting either language.

`variants.json` contains 120 questions: 12 families × 2 languages × 5 levels. Each family has exactly one question at each level in each language. The source projection's SHA-256 is stored in the JSON metadata. The source-corpus hash supplied in that projection was not used to access or inspect the corpus.

## Operational definitions

| Level | Intended change | Answerability policy |
|---|---|---|
| L0 | Canonical formal wording, unchanged | Inherit canonical intent provisionally |
| L1 | Natural conversational wording; preserve algorithm names and constraints | Inherit canonical intent provisionally |
| L2 | Replace some specialist phrasing with everyday words; keep a clear named or explicit core concept | Inherit canonical intent provisionally |
| L3 | Remove algorithm names; describe the identifying mechanism using everyday language, while preserving the necessary constraints | Inherit canonical intent provisionally, subject to independent review |
| L4 | Remove distinguishing mechanisms or constraints, leaving multiple reasonable meanings | Separate ambiguity/clarification evaluation; **do not score against a unique inherited retrieval answer** |

These are qualitative authored strata. They do not establish a numerical or universally monotonic measure of how people speak. In particular, removing terminology sometimes requires a longer, clearer description of the mechanism; L3 therefore need not be the shortest or most grammatically fragmented question. L4 deliberately changes information sufficiency, so its outcomes must not be presented as another point on an ordinary exact-intent retrieval curve.

The questions vary their sentence structures and everyday vocabulary rather than attaching a repeated filler prefix. No input announces its level or asks the system to clarify. `requires_clarification` and `possible_interpretations` are evaluation metadata and must not be shown to the rewriting model or retrieval system.

## Per-family review of the L3/L4 boundary

The following review uses only the original questions and the authored variants. It does not verify answers against course sources.

| Family | Distinguishing content retained in L3, in both languages | Content removed for L4; plausible competing meanings |
|---|---|---|
| binary-order | Checking the middle and discarding one side; asks for the required arrangement before starting | Only searching and tidying remain: binary-search ordering, preparation for a linear scan, or building an index |
| binary-log | Each middle check eliminates half the remaining possibilities; asks how check count grows with input size and why | General narrowing remains: binary search, pruning in a search tree, or indexed filtering |
| hash-delete | Key-to-slot mapping, consecutive probing after a clash, and distinguishing previously occupied from never used | Generic table deletion marker: open-addressing tombstone, database soft deletion, or synchronization/history marker |
| hash-chain | Key-to-slot mapping and linked boxes holding colliding entries; asks to reduce work in an excessively long chain | Generic crowding: hash collision chain, long unsorted container, or overloaded partition |
| avl-factor | Two-branch search tree, rotations to maintain height balance, and a per-node imbalance number | Generic balance number: AVL height imbalance, subtree-size imbalance, or a different tree's balance invariant |
| stack-order | Exactly one accessible end, used for both adding and removing items | Generic container: stack, queue, or priority queue |
| bfs-queue | Exploring across the current front instead of continuing down one trail; asks both waiting-container choice and visit order | Generic graph traversal: breadth-first, depth-first, or priority-guided search |
| dfs-backtrack | Following one route deeper before sideways routes; asks when to retrace and how to continue | Generic returning in a search: depth-first traversal, pathfinding, or constraint-search backtracking |
| quick-partition | A reference item, rearrangement with respect to it, and recursive processing of the resulting pieces | Generic preliminary rearrangement before smaller pieces: pivot partitioning, mergesort division, or other grouping |
| quick-bad-pivot | Reference-based recursive splitting, descending initial values, and always choosing the first item of each current piece | Only reversed input and taking the front item remain: quicksort, insertion-style processing, or another front-item procedure |
| insertion-near | Incrementally fitting the next item into an already ordered prefix; nearly ordered whole input | Generic adaptive sorting on nearly ordered input: insertion sort, a run-aware merge method, or an early-exit bubble variant |
| merge-selection | Two lists already ordered by the same rule; producing one ordered list; asks the next-output choice | Two unspecified lists: sorted merge, concatenation, interleaving, or duplicate resolution |

Some identifying descriptions necessarily unpack the meaning of the canonical algorithm name. For example, breadth-first versus depth-first wording hints at exploration shape, and describing insertion identifies its growing ordered prefix. These are wording-based diagnostic queries, not independently written exam questions; the report should not claim that every level contains precisely equal surface information. No variant was written using an answer key, and no answer rule such as the binary-search precondition, tombstone lookup consequence, balance-factor formula, or next-record comparison was inserted from source material.

## Author review and automatic structural checks

The author reviewed all 120 strings for preservation of the canonical question at L0–L3, natural wording, increasing removal of specialist names, and genuine under-specification at L4. The review retained all 120 questions. This author self-review is not an independent human validation and should not be reported as one.

Structural checks confirmed 120 unique IDs, the complete family/language/level grid, `requires_clarification=false` for all 96 L0–L3 items, `true` for all 24 L4 items, and at least two plausible interpretations for every L4 item. Each L4 currently lists three or four possible meanings. Interpretation lists are illustrative rather than exhaustive semantic gold.

Before model calls, an independent agent may review the question text and these definitions without seeing retrieval outcomes. If that review finds L3 genuinely ambiguous, revise or relabel it **before** freezing inputs; do not repair it after inspecting performance. Save the final frozen file hash in the run manifest. The metadata flags are for evaluation only; avoid leaking them into any model prompt.

## Limits to state in the experiment report

- This is a small, synthetic, bilingual computer-science diagnostic, with correlated variants within each question family.
- Family-level grouping is necessary when splitting data and estimating uncertainty; treating 120 variants as 120 independent information needs would exaggerate evidence.
- L4 tests safe handling of missing information, not whether a model can guess the author's hidden canonical intent.
- Model-produced rewrites need their own intent-preservation review; lexical validity alone cannot establish semantic faithfulness.
- A winning strategy here warrants validation on real student questions and broader course sources before any production default is changed.
