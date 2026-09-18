# [Workflow demo] Citation Support vs. Citation Validity

状态：approved

## A valid citation identifier is not the same as support

Citation support requires actually reading the cited text. An existing citation identifier only proves that a passage can be found in the recorded source set; it does not prove that the passage supports every sentence in the explanation [927abd040836438c9f6bf776c1ba13e6].

A concrete example from the notes: a passage stating that human review is required cannot support a generated claim that retrieval always eliminates mistakes. In this case the citation is structurally valid, but the factual conclusion is unsupported [927abd040836438c9f6bf776c1ba13e6].

To assess citation support, the notes separate three questions: (1) does the cited identifier belong to the passages supplied to this generation, (2) does that passage contain the information needed for the claim, and (3) does the explanation preserve any conditions or limitations in that information? A program can check only the first question mechanically; the second and third require a content judgment [927abd040836438c9f6bf776c1ba13e6].

引用片段：927abd040836438c9f6bf776c1ba13e6

## 1. Using the example from the notes, explain why an existing citation identifier can fail to support an answer. In your answer, refer to the three questions the notes say should be separated when assessing citation support.



参考答案：An existing citation identifier only proves that a passage can be found in the recorded source set; it does not prove the passage supports every sentence of the explanation. For example, a passage stating that human review is required cannot support a generated claim that retrieval always eliminates mistakes: the citation is structurally valid but the factual conclusion is unsupported. The notes say to separate three questions: (1) does the cited identifier belong to the passages supplied to this generation; (2) does that passage contain the information needed for the claim; (3) does the explanation preserve any conditions or limitations in that information? Only the first can be checked mechanically; the second and third require a content judgment.

解析：A citation identifier is a structural record, not a factual guarantee. The notes give the human-review example: the cited passage requires human review, so it cannot support a claim that retrieval always eliminates mistakes. The three-question framework shows that identifier validity (question 1) is only the mechanical part; whether the passage contains the needed information (question 2) and whether conditions are preserved (question 3) require content judgment [927abd040836438c9f6bf776c1ba13e6].

引用片段：927abd040836438c9f6bf776c1ba13e6

## 资料依据

- ca1_rag_course.md，第 1 页（片段 927abd040836438c9f6bf776c1ba13e6）
- ca1_rag_course.md，第 1 页（片段 b8d1c525d5a74f3d907600b3ab25679d）
- ca1_rag_course.md，第 1 页（片段 d14b60c9729e4fc08d980b82032db14b）
- ca1_rag_course.md，第 1 页（片段 00543ff624d047b5af2091756e21a0a1）
- ca1_rag_course.md，第 1 页（片段 a3bb2fdd8752421a8ea9593de052ccb5）
