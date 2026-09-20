# Literature update for Part I

The original fourteen-paper narrative review and its full-text inspection records remain in `docs/ca1/literature/Source_Ledger.md`. This update adds focused retrieval sources; it is not an exhaustive search of 2026 publications.

| Manuscript reference | Primary record rechecked | Use and limitation |
|---|---|---|
| 16 | https://aclanthology.org/2025.findings-naacl.114/ | Semantic chunking cost/benefit motivates controlled comparison, not a claim that semantic segmentation never helps. |
| 17 | https://arxiv.org/abs/2409.04701 | Late chunking contextualizes tokens before chunk pooling; not implemented by this application's pooled-vector API. Cited as an arXiv preprint, version 3. |
| 18 | https://arxiv.org/abs/2506.05176 | Qwen3 embedding/reranking model family motivates multilingual and instruction-aware testing. Published benchmark claims are not substituted for local measurements. |
| 19 | https://aclanthology.org/2020.acl-main.653/ | MLQA provenance and original task; local retrieval labels are derived from annotated answer passages, not exhaustive qrels. |
| 20 | https://arxiv.org/abs/2304.03679 | Original T2Ranking paper, marked SIGIR 2023 accepted in the author record. Local data use the binary C-MTEB derivative, not original four-level evaluation. |

This turn rechecked primary publication records and abstracts. Existing local dataset provenance notes and frozen conversion records provide the detailed local subset definitions. No new human labels or retrieval experiments were produced while updating the report.
