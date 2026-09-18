# RAG Ingestion and Retrieval: From Passages to Evidence Selection

状态：draft

## RAG Ingestion: Passage to Vector

RAG ingestion starts by extracting text from an allowed document. The application divides the text into passages and stores each passage with an identifier, document name, and page reference. An embedding service maps passage text to a numeric vector. The passage vector and its source metadata belong together because a vector without its text cannot supply inspectable evidence. A small overlap between neighboring passages can preserve context at a boundary, but overlap also creates repeated text.

引用片段：4721ff13df084db99cabd2108b93055d

## Retrieval: How a Learning Objective Selects Evidence

At request time, the application embeds the learning objective using a compatible embedding configuration. It compares the query vector with stored passage vectors and ranks candidates by similarity. The selected passages accompany the objective in a text-generation request. The generator should use those passages to explain a covered concept or write an answerable exercise. Retrieval supplies external evidence; it does not update the language model's parameters and does not itself prove the final explanation correct.

引用片段：c55f8fa18dcf4166a3971cf56261b816

## Interpreting Ranked Passages and Scores

In a RAG ingestion example with eight passages and a retrieval limit of three, a request about citations should rank citation passages ahead of unrelated interface notes. The evidence record should preserve the actual ranked passages and similarity scores. A score measures the comparison used by this retrieval configuration; it is not a calibrated probability that the answer is correct. If every passage is returned, the run demonstrates context supply but does not demonstrate selective ranking. A human still checks whether the selected passages cover the requested objective.

引用片段：996cef2f809b453c80346bc9dca0faba

## Evidence Boundaries and Compatibility

An evidence boundary is crossed when a requested conclusion cannot be derived from the supplied material. If a learner asks for a clinical treatment dosage while the course notes only explain retrieval systems, the notes provide no clinical evidence; the appropriate response is to report insufficient evidence. Embedding compatibility also matters: vectors must have the same dimension before coordinates can be compared, but matching dimensions alone are insufficient because different models can use different semantic spaces. A useful failure message explains why reindexing is needed instead of silently comparing incompatible vectors.

引用片段：ab0c520229f84ae1a3339f57cf1e7e8d, 8c2731d164d84ad79fe87182b5a2f5f5

## Reviewed Text Versions Are Separate from Retrieval

Embedding compatibility and a reviewed text version are different concerns. Reindexing changes the vectors used by future retrieval, but it does not retrospectively repair or approve an already generated explanation. The earlier explanation remains associated with its original source passages and generation settings. If a reviewer later edits that explanation, the system creates a new text version. Keeping these histories separate lets an observer distinguish a retrieval configuration change from a correction to teaching content.

引用片段：8c2731d164d84ad79fe87182b5a2f5f5

## 资料依据

- ca1_rag_course.md，第 1 页（片段 4721ff13df084db99cabd2108b93055d）
- ca1_rag_course.md，第 1 页（片段 996cef2f809b453c80346bc9dca0faba）
- ca1_rag_course.md，第 1 页（片段 c55f8fa18dcf4166a3971cf56261b816）
- ca1_rag_course.md，第 1 页（片段 ab0c520229f84ae1a3339f57cf1e7e8d）
- ca1_rag_course.md，第 1 页（片段 8c2731d164d84ad79fe87182b5a2f5f5）
