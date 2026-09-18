# Literature Review

AI-Powered Multimodal Content & Assessment Generation for Educational Applications

Working draft · 11 September 2026


## 1 Review scope and organising questions

This review examines how an educational authoring system can produce course-grounded explanations and assessment items while making its limitations inspectable. It supports the CA1 literature-survey and system-design requirements of the project brief [1]. The organising question is not simply whether a language model can generate a fluent question, but what evidence is needed before an educator should use that question.

A targeted narrative search was conducted on 11 September 2026 using ACL Anthology, arXiv and PMLR. Search themes included educational question generation, difficulty estimation, retrieval-augmented generation, citation evaluation and multimodal RAG. Fourteen research publications from 2017–2025 were selected for methodological relevance. This is not an exhaustive systematic review or a meta-analysis, and no claim is made that all relevant 2026 publications have been covered.

Official publication pages and downloaded full texts were used to check the selected methods, evaluation designs and limitations. Peer-reviewed conference or journal publications form the main evidence base; two arXiv preprints are explicitly distinguished. Publication records take precedence over placeholder venue information in preprint PDFs. The accompanying source ledger records the inspected sections and local copies so that important claims can be checked again.

The synthesis separates four issues: pedagogical suitability, retrieval of supporting material, interpretation of difficulty, and evaluation of generated outputs. Multimodal presentation is reviewed as the next development stage, while the implemented CA1 path remains text-based. Subsequent paragraphs distinguish reported findings from design implications proposed for this project.

A common comparison problem is that papers use different subjects, data, models and evaluation procedures. Their results therefore motivate hypotheses rather than directly predicting performance on the selected FYP course. The report does not combine their benchmark scores into a ranking. Instead, it asks which assumptions transfer to a small, API-based, educator-reviewed system and which require new evidence.


## 2 Educational question generation

Du, Shao and Cardie [2] formulate reading-comprehension question generation with an attention-based sequence-to-sequence model. Their sentence-versus-paragraph comparison and human evaluation show that neural generation can move beyond hand-crafted rules. The study concerns passage-based questions, however, rather than a complete course-authoring workflow.

Gong, Pan and Hu [3] introduce KHANQ, built from learner questions in science-related Khan Academy courses. Their evaluation considers appropriateness, coverage, coherence and complexity. The work exposes a useful distinction between producing a question that can be answered from text and producing one that probes understanding.

Maity, Deroy and Sarkar [4] compare in-context learning, retrieval-based generation and a hybrid approach for educational questions. The preprint uses GPT-4 for ICL and BART with retrieval for its RAG setting. Consequently, differences between these systems cannot automatically be attributed to retrieval alone.

### Implications for the proposed system

For this project, the authoring unit is a learning asset containing an objective, an explanation, questions, reference answers and learner-facing explanations. This is an explicit design choice: an isolated question provides insufficient information for checking whether it tests the intended idea or whether the proposed answer follows from the course. The teacher must be able to inspect these elements together.

The comparison also motivates a controlled baseline. An API-only model without retrieved course passages should be compared with the same model receiving those passages. The prompt, question count, requested language and output format should otherwise remain comparable. Introducing a stronger model in only one condition would confound the contribution of retrieval with the contribution of the generator.

Multiple-choice and short-answer questions are the initial formats. Multiple-choice items need checks for a unique defensible answer and plausible distractors; short-answer items need an explicit marking expectation. Four distinct strings do not guarantee four pedagogically useful options. These judgments remain separate from the implemented structural validator and require inspection by someone familiar with the course.

The resulting research focus is therefore narrower than autonomous curriculum creation: generate reviewable drafts within a specified course, record the evidence used, and measure the amount and type of correction needed before use. This definition provides observable outcomes without presuming that generation automatically saves educator time.


## 3 Difficulty and educational objectives

Cheng et al. [5] propose EQPR, combining planning and reflection for objective-aligned mathematical question generation, with EduMath and EQGEVAL supporting evaluation. Their approach illustrates that educational objectives can be represented and assessed explicitly. Its mathematics-specific planning machinery is not evidence that the same procedure transfers unchanged to every course.

Park et al. [6] use groups of language models to estimate question difficulty for different learner levels. The paper evaluates LLaSA and a zero-shot variant against student-derived difficulty information. Its findings concern difficulty estimation; they do not establish that a generator obeys a requested difficulty label.

### Intended demand versus observed difficulty

The present design treats easy, medium and hard as authoring constraints on intended cognitive demand. An easy item targets a single concept; a medium item applies or compares concepts in a stated situation; a hard item requires integration or justification within the available course content. These are provisional operational definitions, not a validated psychometric scale.

A question can require several reasoning steps yet be easy for an experienced student. Conversely, unfamiliar terminology or unclear wording can make a simple concept difficult. The experiment must therefore avoid interpreting a teacher’s complexity rating as a measured student success probability. Actual difficulty would require an appropriate learner population, response observations and a justified analysis.

The initial study will compare a difficulty label alone with a label plus explicit cognitive constraints, keeping the generator and retrieval settings fixed. Raters should assign their perceived demand category before seeing the requested label. A second comparison can then measure intended-versus-rated agreement. Ambiguous, incorrect or out-of-scope questions are recorded as defects rather than rewarded for appearing difficult.

The prototype currently asks for a brief difficulty rationale, which helps a teacher understand the intended demand. That rationale is generated by the same model and is not independent verification. A model claiming that a question is hard must not be counted as successful difficulty control. The CA1 contribution is the explicit design and testable comparison; calibration to real learners remains future work.


## 4 Retrieval and evidence grounding

Lewis et al. [7] combine a parametric generator with retrieved non-parametric memory and evaluate jointly trained RAG formulations. Their work motivates explicit external knowledge access. The present prototype instead uses inference-time prompting through external APIs and does not reproduce their end-to-end training procedure.

Karpukhin et al. [8] develop dense passage retrieval using a dual encoder for open-domain question answering. This provides a foundation for semantic passage selection. Its benchmark results do not establish that a chosen embedding API retrieves course-specific terminology better than a lexical baseline.

Liu et al. [9] find that model performance can depend on the position of relevant information in long contexts. Their controlled tasks caution against equating context-window capacity with reliable context use. The effect should be rechecked for the eventual provider rather than assumed constant across models.

### A bounded retrieval design

The CA1 implementation splits text within each PDF page, preserving document identity and page number. It embeds these chunks and retrieves the five most similar chunks for a requested learning objective. Cosine similarity ranks candidates; it is not interpreted as the probability that a passage is correct. The selected chunks are saved with the generated asset, making later inspection independent of changes to the original index.

This simple design is a starting point with clear limitations. Page boundaries can split an explanation, character-based chunks may contain several ideas, and a fixed top-five selection can return irrelevant material for unsupported topics. There is no validated relevance threshold or reranker in the current implementation. An insufficient-evidence response is requested from the generator, but reliable abstention still needs testing.

Three failure types must be distinguished: missing support in the uploaded collection, failure to retrieve support that is present, and failure to use retrieved support correctly. They require different fixes. A retrieval error should not be hidden by improving the answer prompt, while a hallucinated answer should not be explained away merely because a relevant passage was available.

Index configuration is also part of the experimental state. The system records an embedding configuration signature and prevents mixed use after a change. This guards against a concrete engineering inconsistency, although it cannot detect an undocumented upstream model revision. Later retrieval experiments should include lexical retrieval, alternative chunk sizes and annotated support passages before adding more complex infrastructure.


## 5 Evaluation of questions and citations

Gao et al. [10] introduce ALCE and distinguish output correctness from citation quality. Citation recall and precision examine support and irrelevant citations. This distinction informs the project’s separation between valid source identifiers and substantive evidence for a claim.

Es et al. [11] propose RAGAs metrics for faithfulness, answer relevance and context relevance using model-based judgments. Saad-Falcon et al. [12] propose ARES, which trains evaluators on synthetic data and uses human annotations for prediction-powered inference. These approaches differ in supervision and calibration requirements.

Oh et al. [13] show why single-reference similarity is restrictive for question evaluation and propose multiple reference paraphrases. Their stated limitations include dependence on an existing reference and restrictions for answer-unconditional generation. Multiple valid questions can therefore make a single reference misleading.

Deroy, Maity and Sarkar [14] propose MIRROR, using iterative model feedback for open-ended question evaluation. Their reported closer alignment with human ratings motivates investigating assisted review, while leaving the need for an independent reference assessment in this course unresolved.

### An evaluation hierarchy

The proposed hierarchy begins with deterministic checks: required fields, question count, answer format and source identifiers. These checks establish that an output can be processed, not that it should be taught. The next level is expert assessment of correctness, support, answerability and intended demand. Model-based scoring may then assist triage, provided disagreement with human judgments is measured.

The study will keep generation and judgment logically separate. Using the same model to generate, explain and grade its own output could reproduce the same error three times. Agreement between two model calls is therefore not a substitute for a course reference. If an automated judge is later used, its identity, prompt, calibration subset and failure cases must be retained.

Reporting only accepted outputs would also hide a system that rejects most requests or spends many calls repairing them. Results should include all submitted requests, failure and abstention rates, and conditional quality among valid outputs. Raw drafts and teacher-corrected versions should be evaluated separately so that manual improvements are not credited to the generator.

For CA1, a small technical smoke test demonstrates data flow and catches integration failures. It is not a sufficiently powered study of educational quality. The later research dataset will contain held-out objectives and annotated support evidence; success on the self-authored demonstration material cannot establish generalisation to an unseen university course.


## 6 Multimodal extension and accessibility

Mei et al. [15] survey multimodal RAG, including retrieval and generation involving different data types. Their taxonomy helps distinguish multimodal evidence processing from presenting text in alternative formats. The current project begins with text retrieval and plans speech and visual transformations after text review.

This distinction matters for the project’s claims. Producing an audio narration and an illustration does not mean that the retrieval component understands diagrams in a scanned textbook. The CA1 parser currently extracts text; OCR, image retrieval and visual reasoning over source documents are not implemented. The report therefore uses “multimodal presentation” for the planned output stage.

The proposed CA2 extension binds each media item to the version of the reviewed text that produced it. A teacher checks terminology and omissions in speech, and relationships, labels and unsupported details in images. A revised explanation invalidates the assumption that existing media still represent the material accurately. Separate review states make this dependency visible.

Alternative formats should offer a practical choice, such as listening to an explanation or inspecting a diagram alongside its text. No claim is made that matching an assumed learning style improves learning outcomes. Accessibility must be checked through concrete features and tasks: readable text, playback controls, transcripts, useful alternative descriptions and avoidance of information available only in one modality.

For the CA1 milestone, documenting these interfaces is sufficient preparation for the later multimodal work; a fully integrated multimodal application belongs to CA2 in the supplied brief. The current implementation already contains media adapters and review logic, but neither those interfaces nor a picture prompt constitute evidence that real media outputs have been validated. This boundary keeps the present milestone focused on the text-and-retrieval path.


## 7 Synthesis and research position

Across the selected literature, generation quality depends on more than linguistic fluency. Question-generation studies identify pedagogical criteria, difficulty work introduces learner or objective dependence, and retrieval evaluation separates finding evidence from using it. The proposed project brings these concerns into a single inspectable authoring workflow, rather than claiming a new foundation model.

The opportunity identified here is a practical and testable integration problem: can a small API-based system make course-grounded question creation more reliable through explicit source links, cognitive constraints and teacher review? The review does not establish that no previous educational system combines these features. A novelty claim would require a broader comparison of systems and published implementations.

| Research question | Controlled comparison | Primary outcome |
| --- | --- | --- |
| RQ1 Course grounding | Same generator without retrieval versus with course retrieval | Correctness and evidence support |
| RQ2 Intended demand | RAG with labels versus RAG with explicit cognitive constraints | Blind-rated demand agreement |
| RQ3 Later media stage | Reviewed text and its generated speech or visual output | Consistency and required corrections |

The first two questions guide CA1 design and the subsequent text experiments. RQ3 is reserved for the multimodal stage. Hypotheses are directional expectations to be tested, not established project results. An unsuccessful comparison is still informative if the record explains whether the cause was retrieval, generation, evaluation ambiguity or implementation failure.

The corresponding design commitments are modest but concrete: preserve the source snapshot, version the generated asset, make structural checks explicit, require review before learner display, and record failed attempts. These commitments create the evidence needed to investigate quality. They do not remove the need for real provider testing, course expertise or careful human evaluation.

Before formal submission, the review should be refreshed for newly relevant work and adjusted to the supervisor’s preferred course and rubric. The current manuscript is a complete working narrative for discussion, with a traceable reference set; its scope and methodological decisions remain open to revision as the project gains actual course data.


## 8 References

[1] CEG 311 FYP project brief. AI-Powered Multimodal Content & Assessment Generation for Educational Applications. AY 2026/2027, p. 27. Supervisor: Mehul Motani.
local: CEG 311 FYP选题介绍 AY2026-2027.pdf

[2] X. Du, J. Shao, and C. Cardie. Learning to Ask: Neural Question Generation for Reading Comprehension. ACL, 2017, pp. 1342–1352.
https://aclanthology.org/P17-1123/

[3] H. Gong, L. Pan, and H. Hu. KHANQ: A Dataset for Generating Deep Questions in Education. COLING, 2022, pp. 5925–5938.
https://aclanthology.org/2022.coling-1.518/

[4] S. Maity, A. Deroy, and S. Sarkar. Leveraging In-Context Learning and Retrieval-Augmented Generation for Automatic Question Generation in Educational Domains. arXiv:2501.17397, 2025. Preprint.
https://arxiv.org/abs/2501.17397

[5] C. Cheng et al. From Objectives to Questions: A Planning-based Framework for Educational Mathematical Question Generation. ACL, 2025, pp. 12836–12856.
https://aclanthology.org/2025.acl-long.628/

[6] J.-W. Park, S.-J. Park, H.-S. Won, and K.-M. Kim. Large Language Models are Students at Various Levels: Zero-shot Question Difficulty Estimation. Findings of EMNLP, 2024, pp. 8157–8177.
https://aclanthology.org/2024.findings-emnlp.477/

[7] P. Lewis et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, vol. 33, 2020, pp. 9459–9474.
https://arxiv.org/abs/2005.11401

[8] V. Karpukhin et al. Dense Passage Retrieval for Open-Domain Question Answering. EMNLP, 2020, pp. 6769–6781.
https://aclanthology.org/2020.emnlp-main.550/


## 9 References continued

[9] N. F. Liu et al. Lost in the Middle: How Language Models Use Long Contexts. Transactions of the Association for Computational Linguistics, vol. 12, 2024, pp. 157–173.
https://aclanthology.org/2024.tacl-1.9/

[10] T. Gao, H. Yen, J. Yu, and D. Chen. Enabling Large Language Models to Generate Text with Citations. EMNLP, 2023, pp. 6465–6488.
https://aclanthology.org/2023.emnlp-main.398/

[11] S. Es, J. James, L. Espinosa-Anke, and S. Schockaert. RAGAs: Automated Evaluation of Retrieval Augmented Generation. EACL System Demonstrations, 2024, pp. 150–158.
https://aclanthology.org/2024.eacl-demo.16/

[12] J. Saad-Falcon, O. Khattab, C. Potts, and M. Zaharia. ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems. NAACL, 2024, pp. 338–354.
https://aclanthology.org/2024.naacl-long.20/

[13] S. Oh et al. Evaluation of Question Generation Needs More References. Findings of ACL, 2023, pp. 6358–6367.
https://aclanthology.org/2023.findings-acl.396/

[14] A. Deroy, S. Maity, and S. Sarkar. MIRROR: A Novel Approach for the Automated Evaluation of Open-Ended Question Generation. PMLR, vol. 264, 2025, pp. 3–32.
https://proceedings.mlr.press/v264/deroy25a.html

[15] L. Mei, S. Mo, Z. Yang, and C. Chen. A Survey of Multimodal Retrieval-Augmented Generation. arXiv:2504.08748, 2025. Preprint; PDF title uses “A Survey on”.
https://arxiv.org/abs/2504.08748
