# Embedding Compatibility, Review Status, and What Must Be Rebuilt

状态：draft

## Embedding compatibility and the embedding configuration signature

Embedding compatibility concerns the relationship between stored document vectors and a new query vector. Vectors must have the same dimension before coordinates can be compared, but matching dimensions alone are not enough: two models can use different semantic spaces while producing the same number of coordinates. A query from one space must not be assumed compatible with passages embedded by another model. The application should associate an embedding configuration signature with each indexed passage; this signature can identify the embedding model, endpoint, and relevant options without containing an API credential. Replacing a credential for the same embedding configuration does not by itself change the semantic space, but changing the model or relevant embedding options requires checking compatibility and usually rebuilding document vectors before generating new material. A useful failure message explains why reindexing is needed instead of silently comparing incompatible vectors.

引用片段：7e841d89f57e41e4b04745d3b883044b, d14b60c9729e4fc08d980b82032db14b

## Reindexing is not approval

Embedding compatibility and a reviewed text version are different concerns. Reindexing changes the vectors used by future retrieval. It does not retrospectively repair or approve an already generated explanation. The earlier explanation remains associated with its original source passages and generation settings. Keeping these histories separate lets an observer distinguish a retrieval configuration change from a correction to teaching content.

引用片段：8652cf4f1cb542c0a739c7b3788b3f4a

## Reviewed text versions and renewed approval

A reviewed text version identifies the exact content a reviewer inspected. Newly generated teaching material begins as a draft. Saving an edit creates a later draft version, and approval applies to the current version. A learning view should show content only when that current version is approved. If someone changes approved text, its new version needs review before it is shown as published learning material. An approval request for an older version should fail instead of approving unseen changes. For example, version one is the original generated draft; a reviewer corrects its title or explanation and saves version two; approval of version two permits the learning view to display that text; a later save creates version three and returns the material to draft. The original version-one evidence should remain inspectable so an evaluator can tell what the generator produced and what a person changed. A technical script exercising these transitions does not supply a human quality judgment.

引用片段：6252d551cbf3483a80ddbb893aa33e9c

## What a model change plus an edit requires

If the embedding model or relevant embedding options change, compatibility with the existing index must be checked and the document vectors usually rebuilt; otherwise a query vector from the new model may be compared against passages from an incompatible space. If a reviewer also edits an approved explanation, that edit creates a new text version that returns to draft and needs renewed approval before it is shown as published learning material. Rebuilding the index does not approve the edited explanation, and approving the edited text does not fix the index. Both the retrieval configuration change and the content correction have their own required actions and histories.

引用片段：7e841d89f57e41e4b04745d3b883044b, 8652cf4f1cb542c0a739c7b3788b3f4a, 6252d551cbf3483a80ddbb893aa33e9c

## 1. A team changes the embedding model used for retrieval. At the same time, a reviewer edits an already approved explanation. Explain (a) how embedding compatibility between the new model and the existing index should be handled, including what usually needs rebuilding, and (b) what happens to the edited explanation at the text-version level, including what renewed approval is required. Then explain why completing one of these actions does not take care of the other.



参考答案：For (a), the new model or changed embedding options mean compatibility with the existing index must be checked. Vectors must have the same dimension to be comparable, but matching dimensions alone are not sufficient because two models can use different semantic spaces while producing the same number of coordinates; a query from one space must not be assumed compatible with passages embedded by another model (d14b60c9729e4fc08d980b82032db14b). The embedding configuration signature associated with each indexed passage identifies the model, endpoint, and relevant options without containing an API credential; replacing only a credential for the same configuration does not change the semantic space (7e841d89f57e41e4b04745d3b883044b). Changing the model or relevant embedding options therefore usually requires rebuilding the document vectors before generating new material, and if reindexing is needed, the failure message should explain why rather than silently comparing incompatible vectors (7e841d89f57e41e4b04745d3b883044b). For (b), newly generated teaching material begins as a draft, and approval applies to the current version. Saving an edit creates a later draft version, so the approved text becomes a draft that needs review, and the learning view should show content only when its current version is approved; an approval request for an older version should fail instead of approving unseen changes (6252d551cbf3483a80ddbb893aa33e9c). Completing one action does not substitute for the other because reindexing changes the vectors used by future retrieval but does not retrospectively repair or approve an already generated explanation, and the earlier explanation remains associated with its original source passages and generation settings; keeping these histories separate lets an observer distinguish a retrieval configuration change from a correction to teaching content (8652cf4f1cb542c0a739c7b3788b3f4a). Thus the index must be checked and usually rebuilt for retrieval compatibility, while the edited explanation needs renewed approval as a new draft text version.

解析：Start by separating the two concerns. Retrieval compatibility depends on whether stored document vectors and the new query vector belong to the same embedding configuration; a changed model or changed relevant options requires a compatibility check and usually a rebuild of document vectors, because equal dimension count does not guarantee the same semantic space (d14b60c9729e4fc08d980b82032db14b, 7e841d89f57e41e4b04745d3b883044b). Separately, text approval tracks the exact inspected version: a save after approval creates a later draft, so the edited explanation returns to draft and needs renewed approval before being shown (6252d551cbf3483a80ddbb893aa33e9c). The two do not substitute for each other: reindexing changes future retrieval but does not repair or approve an earlier explanation and its original source passages and settings (8652cf4f1cb542c0a739c7b3788b3f4a).

引用片段：d14b60c9729e4fc08d980b82032db14b, 7e841d89f57e41e4b04745d3b883044b, 8652cf4f1cb542c0a739c7b3788b3f4a, 6252d551cbf3483a80ddbb893aa33e9c

## 资料依据

- ca1_rag_course.md，第 1 页（片段 8652cf4f1cb542c0a739c7b3788b3f4a）
- ca1_rag_course.md，第 1 页（片段 6252d551cbf3483a80ddbb893aa33e9c）
- ca1_rag_course.md，第 1 页（片段 7e841d89f57e41e4b04745d3b883044b）
- ca1_rag_course.md，第 1 页（片段 d14b60c9729e4fc08d980b82032db14b）
- ca1_rag_course.md，第 1 页（片段 59d6ea0db5084434a6649e74373dfdc6）
