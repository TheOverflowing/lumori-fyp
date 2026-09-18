# Why an Existing Citation May Fail to Support an Answer

状态：draft

## Citation identifiers versus citation support

An existing citation identifier only shows that a passage can be found in the recorded source set. It does not show that the passage supports every sentence in an explanation. Assessing support requires reading the cited text and making a content judgment, not just confirming that the identifier is valid. Automated validation of identifiers therefore cannot be treated as human approval of the answer.

引用片段：5dd315c3075b4ddbb4b726be825a4a68

## 1. A generated explanation says: 'Because human review is required, retrieval always eliminates mistakes.' It cites a course passage that only states human review is required. Explain why the citation identifier is structurally valid but the claim is still unsupported, using this example. Then state what extra judgment is needed beyond checking the identifier.



参考答案：The identifier is structurally valid because it points to a passage that can be found in the recorded source set, so a mechanical check passes. However, the passage only states that human review is required; it does not say retrieval always eliminates mistakes. So the cited text does not support the factual conclusion. Beyond checking that the identifier belongs to the supplied passages, a system or reviewer must judge whether the passage actually contains the information needed for the claim and whether the explanation preserves any conditions or limitations. Those second and third judgments require content judgment, not just identifier validation, so the draft must not be called human-approved merely because its citation identifiers passed validation.

解析：The correct response separates two things: (1) whether the citation identifier is found in the supplied passages, which can be checked mechanically, and (2) whether the cited passage actually contains the information needed for the claim and preserves its conditions. In the example, the passage about human review being required cannot support the stronger claim that retrieval always eliminates mistakes, so the citation is structurally valid but factually unsupported. The extra judgment is a content judgment, not identifier validation.

引用片段：5dd315c3075b4ddbb4b726be825a4a68

## 资料依据

- ca1_rag_course.md，第 1 页（片段 5dd315c3075b4ddbb4b726be825a4a68）
- ca1_rag_course.md，第 1 页（片段 ab0c520229f84ae1a3339f57cf1e7e8d）
- ca1_rag_course.md，第 1 页（片段 996cef2f809b453c80346bc9dca0faba）
- ca1_rag_course.md，第 1 页（片段 1aca2ff1a17b42f6ac5f0a97e7bdc4f2）
- ca1_rag_course.md，第 1 页（片段 c55f8fa18dcf4166a3971cf56261b816）
