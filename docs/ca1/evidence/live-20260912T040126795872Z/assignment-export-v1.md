# Rebuilding vs. Re-approval After an Embedding Model Change and a Text Edit

状态：draft

## Two independent concerns: embedding compatibility and reviewed text

Embedding compatibility concerns the relationship between stored document vectors and a new query vector. Vectors must share the same dimension before coordinates can be compared, and matching dimensions alone are insufficient because two models can use different semantic spaces while producing the same number of coordinates. The application associates an embedding configuration signature with each indexed passage; the signature can identify model, endpoint, and relevant options without containing a credential. Replacing a credential for the same configuration does not by itself change the semantic space, but changing the model or relevant embedding options requires checking compatibility and usually rebuilding document vectors before generating new material. Separately, a reviewed text version identifies the exact content a reviewer inspected: generated material begins as a draft, saving an edit creates a later draft version, and approval applies to the current version.

引用片段：e264d1184f83490880d0994c58a6e7f6, 66566f0f9704470ea290999a4579eee9

## What must be rebuilt and what must be re-approved

Reindexing changes the vectors used by future retrieval; it does not retrospectively repair or approve an already generated explanation, which remains associated with its original source passages and generation settings. If a reviewer edits that explanation, the system creates a new text version, and the learning view should show content only when the current version is approved. An approval request for an older version should fail instead of approving unseen changes, and the original evidence should remain inspectable so an evaluator can tell what the generator produced and what a person changed. Keeping these histories separate lets an observer distinguish a retrieval configuration change from a correction to teaching content.

引用片段：8c2731d164d84ad79fe87182b5a2f5f5, 66566f0f9704470ea290999a4579eee9

## 1. A course system changes its embedding model and re-runs retrieval so that future searches use vectors from the new model. Later, a reviewer edits the title and explanation of an already generated explanation, saving a new version. Explain (a) which parts must be rebuilt for the embedding change, (b) what happens to the previously generated explanation and its approval status after the edit, and (c) why an approval request aimed at the older version should not succeed. Justify each point using the supplied material.



参考答案：(a) Changing the embedding model changes the semantic space, so document vectors must usually be rebuilt before new material is generated; the new query vectors must be compatible with the stored passage vectors. A credential replacement alone would not require this, but a model or relevant option change does, and a useful failure message should explain why reindexing is needed rather than silently comparing incompatible vectors. (b) Reindexing does not retrospectively repair or approve an already generated explanation; that explanation stays tied to its original source passages and generation settings. Editing the title or explanation creates a new draft version, so approval now applies only to the current version, and the learning view should show content only when the current version is approved. (c) An approval request for an older version should fail because it would approve changes the reviewer did not inspect; approval must target the current version. The original version-one evidence should remain inspectable so it is clear what the generator produced and what a person changed.

解析：The embedding model change is a retrieval configuration change: vectors from different semantic spaces must not be compared, so document vectors generally need rebuilding, and reindexing does not retroactively approve generated text. The text edit is a content change: saving an edit creates a later draft, approval binds to the current version, and approving an older version would approve unseen changes. These are separate histories.

引用片段：e264d1184f83490880d0994c58a6e7f6, 8c2731d164d84ad79fe87182b5a2f5f5, 66566f0f9704470ea290999a4579eee9

## 资料依据

- ca1_rag_course.md，第 1 页（片段 8c2731d164d84ad79fe87182b5a2f5f5）
- ca1_rag_course.md，第 1 页（片段 66566f0f9704470ea290999a4579eee9）
- ca1_rag_course.md，第 1 页（片段 e264d1184f83490880d0994c58a6e7f6）
- ca1_rag_course.md，第 1 页（片段 ab0c520229f84ae1a3339f57cf1e7e8d）
- ca1_rag_course.md，第 1 页（片段 6181e69ca2844bd6bd54129e86c1a33f）
