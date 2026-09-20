# AI assisted content review

Five archived version-one assets, fifteen explanatory sections and eight short-answer questions. Self-authored demonstration course only; no MCQs and no student outcomes.

Read each original unit and its cited retrieved excerpts. Distinguish identifier membership, semantic support, engineering inference, historical scope and intended cognitive demand. Targets and original model judgments were not hidden. No production ratings or approval states changed.

This is not human or teacher review. It is not blind and does not estimate student difficulty. Original archived files and application approvals are unchanged.

{"assets": 5, "sections": 15, "questions": 8, "units": 23, "supported_without_required_revision": 13, "revision_recommended": 10}

## L-S1 supported
RAG Ingestion: Passage to Vector

Directly supported ingestion, metadata and embedding description. Overlap is described as a possible trade-off, not as the current deployed default.

Suggested revision: No factual revision identified; frame this as historical teaching material.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json`; citations: 4721ff13df084db99cabd2108b93055d

## L-S2 supported
Retrieval: How a Learning Objective Selects Evidence

The cited passage states query embedding, similarity ranking and the distinction between retrieval and parameter updates.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json`; citations: c55f8fa18dcf4166a3971cf56261b816

## L-S3 supported
Interpreting Ranked Passages and Scores

The eight-passage example and warning about uncalibrated similarity are directly supported.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json`; citations: 996cef2f809b453c80346bc9dca0faba

## L-S4 supported
Evidence Boundaries and Compatibility

The refusal example and equal-dimension compatibility limitation are present in the cited excerpts.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json`; citations: ab0c520229f84ae1a3339f57cf1e7e8d, 8c2731d164d84ad79fe87182b5a2f5f5

## L-S5 supported
Reviewed Text Versions Are Separate from Retrieval

The cited source explicitly separates reindexing from generated-text revision and approval.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json`; citations: 8c2731d164d84ad79fe87182b5a2f5f5

## A-S1 supported
Two independent concerns: embedding compatibility and reviewed text

The two cited excerpts support embedding signatures and version-bound approval, including the credential-change distinction.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/assignment-draft-v1.json`; citations: e264d1184f83490880d0994c58a6e7f6, 66566f0f9704470ea290999a4579eee9

## A-S2 supported
What must be rebuilt and what must be re-approved

The quoted source directly supports immutable earlier evidence and renewed review after editing.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/assignment-draft-v1.json`; citations: 8c2731d164d84ad79fe87182b5a2f5f5, 66566f0f9704470ea290999a4579eee9

## A-Q1 supported
A course system changes its embedding model and re-runs retrieval so that future searches use vectors from the new model. Later, a reviewer edits the title and explanation of an already generated explanation, saving a new version. Explain (a) which parts must be rebuilt for the embedding change, (b) what happens to the previously generated explanation and its approval status after the edit, and (c) why an approval request aimed at the older version should not succeed. Justify each point using the supplied material.

The reference answer distinguishes re-embedding source passages from resetting approval after a content edit. The multi-part scenario is answerable from the cited excerpts.

Suggested revision: For stronger discrimination, supply a concrete before/after state and require the learner to order the changes. Intended demand: medium to hard, not empirically calibrated.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/assignment-draft-v1.json`; citations: e264d1184f83490880d0994c58a6e7f6, 8c2731d164d84ad79fe87182b5a2f5f5, 66566f0f9704470ea290999a4579eee9

## Q-S1 supported
Citation identifiers versus citation support

The source explicitly distinguishes citation identifier membership from semantic support.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/quiz-draft-v1.json`; citations: 5dd315c3075b4ddbb4b726be825a4a68

## Q-Q1 supported
A generated explanation says: 'Because human review is required, retrieval always eliminates mistakes.' It cites a course passage that only states human review is required. Explain why the citation identifier is structurally valid but the claim is still unsupported, using this example. Then state what extra judgment is needed beyond checking the identifier.

The answer follows the source and identifies the unsupported inference correctly. The example is almost identical to the source, limiting evidence of transfer.

Suggested revision: Use a new source-supported example if the target is application rather than rehearsal. Intended demand: easy to medium.

Evidence: `docs/ca1/evidence/live-20260912T040126795872Z/quiz-draft-v1.json`; citations: 5dd315c3075b4ddbb4b726be825a4a68

## H-S1 revise
检索流程与质量边界

The refusal and non-human-approval statements are supported, but the sentence about retrieval supplying evidence is not directly established by the listed excerpts.

Suggested revision: Attach the actual ingestion/retrieval passage to this section, rather than relying on unstated course context.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, 3aefdf9d56844b0087c9ad5a103275cb

## H-S2 revise
嵌入兼容性与版本约束

Equal dimensions not guaranteeing the same semantic space is directly supported. The index-rebuild instruction is an engineering inference from that passage.

Suggested revision: Add the explicit embedding-signature/reindexing passage and distinguish the inference from directly quoted requirements.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: c7b355510d134e91833f092eec3c72ed

## H-S3 revise
审核记录、导出与本地运行限制

The export and credential statements are supported. The claim about absent authenticated roles appears in e9cd2063..., not in this section's two cited excerpts; it is also historical.

Suggested revision: Add the appropriate historical excerpt and date the example. Do not describe the current authenticated application as lacking accounts.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: 5caef4b8eff94d05a4294501bf115e26, 3aefdf9d56844b0087c9ad5a103275cb

## H-Q1 revise
假设你负责审核一份利用课程本地应用生成的测验草稿。该草稿的引用标识全部通过了自动验证，系统因此将其标记为“已准备好用于教学演示”。作为审核者，你需要判断：(1) 自动验证通过能否等同于人工批准？请引用依据；(2) 若后续发现其中一个引用标识指向了确实存在但与该题结论不相关的文档，这属于哪类问题？自动验证为何不能发现？(3) 请给出两条具体且可操作的整改措施，并说明每条措施如何匹配参考资料中的要求。

The distinction between identifier checks and approval is reasonable. The proposed remedies mainly create ratings and logs; they do not explicitly repair an irrelevant citation or unsupported conclusion.

Suggested revision: Require semantic comparison against the source, correction or withdrawal of the unsupported answer, and only then a recorded review. Intended demand: medium to hard.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, 3aefdf9d56844b0087c9ad5a103275cb, 5caef4b8eff94d05a4294501bf115e26

## H-Q2 revise
某课程团队决定更换嵌入模型：旧模型生成 768 维向量，新模型同样生成 768 维向量。同时，一门已审核课程的教学文本被修改。该课程使用本地检索应用。假设存储系统中保留了旧模型的文档向量和旧版审核记录。请分析：(1) 仅维度相同是否足以保证旧文档向量与新查询向量兼容？为什么？(2) 更换嵌入模型后，哪些存储对象需要重建或重新索引？(3) 教学文本修改后，除了向量问题，审核版本相关的哪些对象需要处理？请给出一个考虑上述约束的更新方案，并论证每一步的必要性。

The compatibility reasoning is sound, but updating review records is underspecified and could be read as overwriting historical approval. The retrieved evidence does not fully state the review state transition.

Suggested revision: Specify a new draft revision, retain the old review unchanged, and require approval of the new version; add the versioning excerpt. Intended demand: hard if the state-transition constraints are explicit.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, ff76236a2ba5478b9f72916629d7ab82, 5caef4b8eff94d05a4294501bf115e26, 3aefdf9d56844b0087c9ad5a103275cb

## H-Q3 revise
某本地开发应用准备向教师展示一门课程的生成证据导出包。该导出包将包含检索段落、配置签名、修订历史和提供商调用用量。课程负责人还计划将同一份导出包用于学生 handout，并可能在未来支持多用户访问。假设你被要求审查该计划，请完成以下任务：(1) 指出将生成证据导出包直接用作学生 handout 的至少两处风险，并说明依据；(2) 针对“是否支持多用户角色与课堂访问控制”给出一个评价性结论，并引用资料说明当前应用能做什么、不能做什么；(3) 给出一个既能满足师生不同需求、又能维持当前隐私与审核要求的导出方案，并论证每一步如何匹配资料中的约束。

The historical role limitation is supported by e9cd2063.... However, retrieved passages and configuration signatures are not inherently secrets, and their automatic exclusion from all student handouts is not established by the source.

Suggested revision: Separate pedagogical relevance and source permissions from credential secrecy. Keep justified citations; identify the old prototype as a dated scenario. Intended demand: hard as a constrained design task.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json`; citations: 5caef4b8eff94d05a4294501bf115e26, e9cd2063c2024317800235d50fd44e44, 3aefdf9d56844b0087c9ad5a103275cb

## M-S1 revise
检索生成与引用支持

The listed excerpts support non-human-approval and insufficient-evidence statements, but do not explicitly provide the retrieval mechanism or the full identifier-versus-support distinction.

Suggested revision: Cite the retrieval and citation-support passages themselves; a correct general claim still needs the appropriate source.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, e9cd2063c2024317800235d50fd44e44

## M-S2 revise
嵌入兼容性与索引版本

Changing embedding models can require new source vectors. The added suggestion that related course materials need review is not tied to an actual content edit and is not supported by the cited compatibility excerpt.

Suggested revision: State that reindexing alone does not invalidate an existing text approval; a subsequent edit creates a separate review requirement.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: c7b355510d134e91833f092eec3c72ed

## M-S3 supported
审核版本、导出与证据记录

The listed excerpts support draft/approved export labels, preserved revisions, excluded credentials and separate operational failures.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: 3aefdf9d56844b0087c9ad5a103275cb, 5caef4b8eff94d05a4294501bf115e26, ff76236a2ba5478b9f72916629d7ab82

## M-S4 supported
难度意图与题目设计

The cognitive-demand definitions and absence of learner calibration are directly supported by the cited source.

Suggested revision: No factual revision identified.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: e9cd2063c2024317800235d50fd44e44, ff76236a2ba5478b9f72916629d7ab82

## M-Q1 revise
根据课程资料，检索为生成器提供的是什么？说明该对象与引用支持之间的关系，并指出结构校验不能替代什么。

The answer is conceptually reasonable, but the two cited excerpts do not explicitly answer what retrieval supplies or fully justify the citation-support distinction.

Suggested revision: Add the missing source excerpts and either simplify to one direct relationship or retain it as a compound comprehension item. Intended demand: easy to medium.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, e9cd2063c2024317800235d50fd44e44

## M-Q2 supported
某课程系统更换了嵌入模型，但新查询向量与旧索引中存储的文档向量维数相同。请结合课程资料分析：为什么不能直接判定两者兼容？为保证检索流程可用，应处理哪些存储对象？

The same-dimensional semantic-space mismatch is directly supported; re-embedding affected documents is a reasonable engineering inference.

Suggested revision: Label reindexing as the inferred action or cite the explicit signature/rebuild passage. Intended demand: medium.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: c7b355510d134e91833f092eec3c72ed

## M-Q3 revise
情境：某课程有一份已批准的教学文本和一套由旧嵌入模型构建的索引。团队决定更换嵌入模型，并在更换后直接编辑已批准教学文本中的一段定义，随后计划导出学生讲义与生成证据。请依据资料论证：在导出前，哪些存储对象需要重建或更新，哪些审核动作需要重新执行；导出应标明什么；同时说明为什么不能用自动测试结果充当人工审核。

The answer conditionally mentions indexes dependent on edited text, but the scenario never establishes that the generated teaching text is an indexed source. That ambiguity obscures the source-index versus generated-version separation.

Suggested revision: Identify the edited object explicitly. Re-embed source documents for the model change; return edited generated content to draft and preserve earlier evidence. Reindex edited content only if it is separately ingested as a source. Intended demand: hard after clarification.

Evidence: `docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json`; citations: c7b355510d134e91833f092eec3c72ed, 3aefdf9d56844b0087c9ad5a103275cb, 5caef4b8eff94d05a4294501bf115e26, ff76236a2ba5478b9f72916629d7ab82
