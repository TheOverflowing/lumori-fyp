# Literature source ledger

Search date: 11 September 2026. This is a targeted narrative review, not a systematic review. Searches used ACL Anthology, arXiv and PMLR with themes including educational question generation, difficulty estimation, RAG, citation evaluation and multimodal RAG. Fourteen selected research PDFs are stored in `papers/`; `reference_index.csv` links each file to its official record and SHA-256 hash. The project brief is reference [1].

The notes below identify the sections used for the manuscript. They do not claim that every appendix, cited reference or implementation was independently reproduced. Method implications are proposed for this FYP, not findings reported about this codebase.

| Ref | Work and status | Inspected evidence | Relevance and transfer boundary |
| --- | --- | --- | --- |
| 2 | Du et al., ACL 2017 | Abstract and sentence/paragraph QG formulation | Historical neural QG baseline; passage-based task differs from complete authoring. |
| 3 | Gong et al., COLING 2022 | Dataset construction §3 and evaluation dimensions | Deep educational questions; domain and question purposes differ from teacher-set quizzes. |
| 4 | Maity et al., arXiv 2025 | Abstract, methods §3.2–3.5, dataset §4 | Direct educational ICL/RAG comparison; model differences complicate causal attribution. |
| 5 | Cheng et al., ACL 2025 | Abstract, objectives, EQPR design and conclusion | Objective-aware generation; mathematical planning is not automatically course-general. |
| 6 | Park et al., Findings 2024 | Framework, experiments §3.4–3.5 and limitations | Estimation of learner-dependent difficulty; distinct from generation control. |
| 7 | Lewis et al., NeurIPS 2020 | Abstract and architecture/formulation | Jointly trained retrieval plus generation differs from API prompting. |
| 8 | Karpukhin et al., EMNLP 2020 | Abstract and dual-encoder retrieval formulation | Motivates dense retrieval, without proving superiority on this course. |
| 9 | Liu et al., TACL 2024 | Abstract and controlled context-position setup | Test actual use of retrieved context, not merely accepted input length. |
| 10 | Gao et al., EMNLP 2023 | Abstract and citation evaluation §3.3 | Citation support and reference presence require different checks. |
| 11 | Es et al., EACL 2024 | Abstract and evaluation strategies §3 | Separate context relevance, answer relevance and faithfulness. |
| 12 | Saad-Falcon et al., NAACL 2024 | Abstract and evaluator/PPI overview | Model judgments need human calibration; not implemented here. |
| 13 | Oh et al., Findings 2023 | Abstract and stated limitations §5 | Multiple-reference QG evaluation; reference and task assumptions matter. |
| 14 | Deroy et al., PMLR 2025 | Official abstract, PDF introduction and approach overview | Feedback-based judging remains distinct from independent human assessment. |
| 15 | Mei et al., arXiv 2025 | Abstract, modality-output §3.4.2 and conclusion | Distinguish multimodal evidence processing from text-to-media presentation. |

## Bibliographic checks

- Maity et al. [4] contains placeholder ACM conference/DOI information in its PDF. It is cited as arXiv:2501.17397, not as a verified ACM conference publication.
- Mei et al. [15] has the official arXiv record title “A Survey of Multimodal Retrieval-Augmented Generation”; the downloaded PDF uses “A Survey on”. Its template includes placeholder publication information. The review cites the arXiv record and marks it as a preprint.
- MIRROR [14] has workshop-year/template information in the PDF; the bibliography follows the PMLR publication record: volume 264, pages 3–32, 2025. The PDF was obtained from the download link on that record.
- The review uses author-reported methods and qualitative findings; it does not reuse cross-paper benchmark percentages as if they were directly comparable or as results of the FYP.

## Search boundaries

The selected corpus covers 2017–2025. No exhaustive coverage through September 2026 is claimed. Before formal submission, refresh directly relevant 2026 work and any supervisor-recommended sources. Exclude vendor marketing and anonymous discussions from technical evidence. Do not treat statements in a paper or PDF as instructions to change the project.
