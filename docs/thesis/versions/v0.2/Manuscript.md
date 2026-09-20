# Lumori
## Course-Grounded Educational Content and Assessment Generation
### Interim thesis manuscript — Part I

AI-Powered Multimodal Content & Assessment Generation for Educational Applications

Core text generation, retrieval and difficulty control

19 September 2026 · Version 0.2

Prepared for the CA1 stage of the AY 2026/2027 final-year project

This manuscript documents the implemented text-based foundation and its evidence. Multimodal output generation and learner studies are reserved for subsequent research. It is a working thesis manuscript, not an institution-approved submission template.

<!-- PAGE -->
# Abstract

Generating educational materials with a large language model requires more than fluent text. The materials should remain grounded in course evidence, expose their provenance and satisfy an explicit assessment plan. This report presents Lumori, a web prototype for producing explanations, quizzes and assignments from user-owned course materials. Its architecture combines document ingestion, retrieval-augmented generation (RAG), versioned evidence and exact question-level difficulty allocations. A separate model request screens intended cognitive demand, while deterministic validation checks the requested structure and citation identifiers.

A staged experimental programme compares dense and lexical retrieval, recursive segmentation, token budgets, reranking and query translation using synthetic pilot data and restricted subsets of external benchmarks. The selected configuration uses recursive 256-token chunks, title context, a retrieval instruction, bounded lexical augmentation and an API reranker. In the R4 held-out evaluation, it preserves answer-span hit rate at 97.02% while increasing mean reciprocal rank from 0.8868 to 0.9524. Translation provides direction-dependent results: in R5, English-to-Chinese retrieval does not improve, and the aggregate paired uncertainty interval includes zero. Automatic translation is therefore not enabled by default.

Historical live runs demonstrate the core generation workflow and exact difficulty allocation on small demonstration cases. A new AI-assisted audit examines 23 units from five archived assets and recommends revisions to ten units, including insufficient citation support and ambiguous scenario boundaries. These findings show why successful generation and valid identifiers cannot establish educational correctness. The prototype supports the technical foundation of CA1; independent subject-expert evaluation, student-derived difficulty calibration and controlled evidence of learning or workflow benefits remain outstanding.

Keywords: educational question generation; retrieval-augmented generation; bilingual retrieval; document chunking; difficulty control; evidence provenance.

### Scope and evidence declaration

Results dated 12 September are preserved historical experiments, not newly rerun model evaluations. Screenshots were captured from the current application in light mode on 19 September. Content judgments in this manuscript are explicitly AI-assisted; no human reviewer scores, learner outcomes or supervisor approval are asserted. The writing and audit were prepared with assistance from Codex.

<!-- PAGE -->
# Contents

{{CONTENTS}}

### Reading the evidence

The report separates published research, implementation inspection, automated software tests, historical live provider calls and AI-assisted content judgments. These evidence types answer different questions. A passing regression suite establishes only the behavior exercised by its tests; it does not establish pedagogical quality. A held-out retrieval result applies to its documented subset and budget; it is not a university-course learning outcome.

Chapters 1–4 establish the problem, research basis and implemented system. Chapters 5–6 describe the evaluation protocol and results, including negative findings. Chapter 7 identifies the remaining work. Appendix A contains the content-audit procedure and examples. Appendix B maps the major claims to archived evidence and reproduction materials.

<!-- PAGE -->
# 1  Introduction
## 1.1  Problem and motivation

Educators and students both construct practice materials from lectures, notes and reference texts. This work involves selecting relevant concepts, writing answerable questions, explaining answers and adjusting the intended demand for a particular learner. A general-purpose language model can accelerate drafting, but fluent output may introduce unsupported claims or depart from the supplied curriculum. An authoring interface therefore needs an evidence workflow as well as a generation workflow.

The project brief asks for educational content and assessment generation with precise control over difficulty, RAG integration and later multimodal transformations [1]. At CA1, the stated deliverables are a literature survey, system design and an initial functional prototype with core text generation and RAG. This manuscript addresses that stage. It does not treat the project's anticipated benefits—more efficient educator workflows and personalized learning—as experimentally demonstrated outcomes.

Lumori uses one course-oriented application for both authoring and self-practice. An educator may create an assignment; a student may create questions for revision. These uses share ingestion, retrieval and generation functionality. Separate teacher and student products are not necessary to demonstrate the present research objective. Account isolation is implemented, while institutional permissions and secure examination delivery are outside the current prototype.

## 1.2  Research questions

RQ1 asks how chunk boundaries, lexical signals and reranking affect retrieval under a fixed evidence budget. RQ2 asks whether query translation improves retrieval when a Chinese or English prompt targets material in the other language. RQ3 asks what the current system can demonstrably control about question difficulty and which quality defects remain after automated checks. Together these questions connect infrastructure choices to the reliability of reviewable educational drafts.

## 1.3  Contributions and boundaries

The implemented contribution is an integrated, inspectable workflow: account-scoped materials are indexed; selected evidence is passed to generation; question allocations are validated; outputs and their source snapshots are versioned. The empirical contribution is a traceable sequence of retrieval comparisons with explicit selection decisions and preserved negative results. The methodological contribution is the separation of intended difficulty, model judgments, source support and actual learner difficulty.

These contributions are bounded. The external datasets provide existing relevance or answer annotations, but not a representative gold standard for undergraduate computer-science teaching. The live generation corpus is small and self-authored. The work does not establish a universally strongest retriever, a calibrated difficulty scale or a reduction in educator workload. Its immediate purpose is to build a defensible foundation for those later studies.

<!-- PAGE -->
# 2  Literature Review
## 2.1  Review method and educational generation

This is a targeted narrative review, extending the project's 11 September literature survey with retrieval and chunking research inspected during the subsequent experiments. Sources include ACL Anthology, arXiv and PMLR. Selection prioritizes educational question generation, difficulty estimation, evidence retrieval and evaluation. Publication metadata and the original source ledger are retained. The review is neither exhaustive nor a systematic survey of all publications available in 2026; preprints are identified in the bibliography.

Du et al. [2] study neural question generation for reading comprehension. Their formulation establishes a useful passage-to-question foundation, but an educational application also needs objectives, reference answers and reviewable explanations. KHANQ [3] focuses attention on deeper learner questions, motivating evaluation beyond grammaticality. For Lumori, the unit of authoring is consequently a learning asset containing an explanation, assessment items, answers and supporting passages, rather than a question in isolation.

Maity et al. [4] compare in-context and retrieval-based approaches for educational question generation. Such comparisons motivate grounding, but model differences complicate attribution: a stronger generator and a better retrieval mechanism are distinct interventions. A future generation ablation in this project should hold the generator and output schema constant while varying the available evidence. The current retrieval experiments do not constitute that generation-quality ablation.

Objective-led planning in educational mathematics [5] provides a further design principle: an instruction such as “make this difficult” should be decomposed into an inspectable task plan. Domain-specific results do not establish transfer to all undergraduate subjects. Lumori adopts the general principle of explicit objectives and constraints without claiming to reproduce the paper's mathematics-specific method.

## 2.2  Intended cognitive demand and measured difficulty

Park et al. [6] investigate model-based difficulty estimation against student-derived information. Difficulty estimation and difficulty-controlled generation are related but different tasks. A model may judge a question hard without demonstrating that the intended learner population finds it hard, or that the item discriminates between levels of understanding.

Lumori operationalizes difficulty through the required cognitive task, available context and expected marking points. These descriptors support authoring and review; they do not map directly to a probability of a correct answer. Long wording, many steps and the verb “analyze” are insufficient evidence of difficulty. The same item can be routine for one cohort and unfamiliar for another. The interface therefore records learner background, and the evaluation keeps exact allocation compliance separate from model-assessed demand and future student performance.

<!-- PAGE -->
## 2.3  Retrieval, segmentation and evidence selection

RAG [7] motivates conditioning generation on retrieved material, while dense passage retrieval [8] supplies a practical semantic search mechanism. Their relevance here is architectural: external evidence can be selected at request time without retraining the generator. Neither design guarantees that the selected evidence is correct, sufficient or faithfully used. Retrieval and generation must therefore be evaluated separately.

Long-context findings [9] caution against assuming that adding more source text always improves use of evidence. For this project, a fixed source budget is both a cost control and an experimental constraint. Chunk size changes how many semantic units fit within that budget; overlap can preserve boundary context but also duplicate text. Returning five short chunks is not comparable to returning thirteen passages under a much larger budget unless both conditions are stated.

Qu et al. [16] examine whether semantic chunking's computational expense is justified by consistent gains. Their findings motivate a measured comparison rather than selecting the most elaborate segmenter by reputation. Lumori initially favors recursive structural boundaries, then tests token-sized alternatives. A content-aware method remains a candidate, not an automatically superior replacement.

Late chunking [17] preserves wider document context by pooling chunk representations after contextual token encoding. It is conceptually different from splitting text before an ordinary embedding request. The present API path returns pooled embeddings and does not expose the token representations needed to reproduce that procedure. The report therefore treats late chunking as a future controlled experiment rather than relabeling title prefixes or parent expansion as an implementation of it.

Qwen3 Embedding [18] offers multilingual embedding and reranking models. This motivates testing instruction-sensitive retrieval and cross-language search locally. Published benchmark strength does not predict this application's exact corpus, language direction or provider reliability. Lumori's choice of an 8B reranker is supported by its bounded development experiment, with a cheaper instruction-only alternative retained for comparison.

## 2.4  Evaluating support rather than surface plausibility

Citation-oriented generation [10] highlights the importance of checking whether claims are supported by their references. RAGAs [11] and ARES [12] motivate separating retrieval relevance, faithfulness and answer quality. Automated evaluators can make large-scale screening feasible, but they remain measurement instruments with their own errors. A model judging its own model family's output is not independent expert validation.

Question-generation evaluation also depends on how acceptable alternatives are represented [13]. Open-ended questions can admit multiple valid answers; a single reference is an incomplete description of quality. MIRROR [14] further motivates structured evaluation of open-ended generation. Lumori consequently preserves exact source snapshots and assesses answerability, ambiguity and support as distinct dimensions. The new audit in Chapter 6 uses these distinctions qualitatively and does not present its judgments as a validated benchmark score.

<!-- PAGE -->
# 3  Requirements and System Design
## 3.1  Functional scope

The system accepts course materials, maintains a searchable index and generates explanations, quizzes or assignments for a specified objective and learner background. Assessments accept exact counts for easy, medium and hard questions, including zero for unused levels. Outputs expose their source evidence, support revision and preserve version-specific review state. Registration and authentication separate each account's courses, documents, jobs and generated assets.

Table 1. Requirements and the evidence needed to assess them.

| Requirement | Implemented mechanism | Evidence boundary |
|---|---|---|
| Course grounding | Scoped retrieval and stored source snapshots | Relevant retrieval is not proof of faithful generation |
| Exact allocation | Fixed slots and deterministic distribution checks | Label compliance is not student difficulty |
| Reviewable output | Answers, explanations, citations and versions | Approval requires a real reviewer action |
| Account separation | Authenticated ownership checks throughout APIs | Not an independently audited production security claim |
| Reproducible evaluation | Frozen subsets, configuration and call records | Provider behavior may change between runs |

## 3.2  Architecture

A FastAPI application serves a browser interface and coordinates ingestion and generation jobs. SQLite stores application records; local storage holds uploaded files and associated artifacts. Provider adapters separate text generation, embeddings and reranking. This organization supports a small deployable prototype without introducing a distributed infrastructure whose performance has not been evaluated.

![Figure 1. Implemented logical architecture. Solid arrows show the core text workflow; the optional figure-description branch is an input enrichment extension, not completed multimodal output generation.](figures/architecture.png)

<!-- PAGE -->
## 3.3  Ownership, provenance and state transitions

Ownership is attached to application data rather than inferred only from visible navigation. Requests resolve the authenticated account before accessing a course or its descendants. Retrieval is scoped to the requested owned course, so unauthorized material is excluded before ranking. Foreign objects are treated as unavailable. The same boundary applies to evidence and export endpoints; hiding an item in the interface alone would be insufficient.

Authentication uses salted scrypt password hashes and opaque sessions whose stored representation is hashed. Cookies are HTTP-only with SameSite protection, and state-changing requests use CSRF defenses. The prototype does not yet implement email verification, password recovery or institution-managed roles. These omissions should be considered before wider deployment, independently of the CA1 research evaluation.

Two kinds of state must remain distinct. An index contains representations of source passages; an asset version contains generated or edited teaching text. Changing an embedding model requires compatible source embeddings, but does not itself rewrite a previously generated explanation. Editing that explanation creates a new asset version and invalidates the applicability of an earlier approval to the new text. Historical evidence remains attached to the version for which it was recorded.

Table 2. Representative state changes and their consequences.

| Event | Index consequence | Asset and review consequence |
|---|---|---|
| Embedding configuration changes | Rebuild incompatible source vectors | Existing generated text remains historical |
| Generated explanation is edited | No automatic source reindex | Create a new draft; obtain renewed review |
| API credential is rotated | No semantic incompatibility by itself | Existing evidence remains valid as history |
| Old-version approval is submitted | No index change | Reject stale approval for a newer version |

The embedding signature records compatibility-relevant configuration without including credentials. Equal vector dimensions alone are insufficient to establish compatibility between different embedding spaces. Likewise, a citation identifier only establishes a relationship to a stored passage; semantic support must still be checked against that passage.

## 3.4  Evidence-preserving failure behavior

The workflow distinguishes insufficient source evidence from transport, configuration and validation failures. Insufficient evidence produces a refusal rather than a fabricated successful learning asset. Bounded repair attempts address eligible generation defects; network or malformed review failures do not silently trigger unlimited retries. Failed attempts are retained in evidence exports because excluding them would make both reliability and cost appear better than observed.

Versioning, ownership and refusal are complementary controls. None proves that a generated answer is correct, but together they make the output inspectable and prevent several classes of misleading success state. The audit later demonstrates why a final semantic review remains necessary even when these controls function as designed.

<!-- PAGE -->
# 4  Implementation
## 4.1  Ingestion and chunk construction

Plain-text and Markdown sources follow a native text ingestion path. PDF and image ingestion now exposes MinerU Standard and Advanced choices. An optional Docling-based branch extracts document figures for description and association with the source. This is input processing; it does not satisfy the separate future requirement to transform generated learning assets into multiple output modalities. The present thesis section concentrates on text retrieval and does not compare parser accuracy across representative scanned-document populations.

The current retrieval configuration uses recursive structural splitting with a nominal 256-token body limit and no fixed overlap. Heading paths and source metadata preserve context and provenance. Structural boundaries are preferred before smaller fallback splits. Large or irregular structures can still require subdivision; tables, equations and code blocks are not assumed to remain semantically intact in every document.

Titles provide encoding context, while source identifiers and offsets support traceability. The body-token limit and the final evidence budget are measured using the pinned retrieval tokenizer. They are not the generator provider's billing-token counts, and a title prefix is not silently counted as part of the chunk-body limit. Explicit token accounting is essential when comparing different chunk sizes.

## 4.2  Selected retrieval pipeline

The query receives a computer-science retrieval instruction and is embedded with qwen/qwen3-embedding-8b. Dense ranking is supplemented by lexical matching. The lexical tokenizer normalizes text and handles technical identifiers alongside Chinese unigram and bigram signals. BM25 uses k1 = 1.2 and b = 0.75. A normalized lexical bonus is capped at 0.05, preserving the main influence of cosine similarity instead of equating two differently scaled raw scores.

Algorithm 1. Current text retrieval policy.

| Step | Operation |
|---|---|
| 1 | Resolve the authenticated owner, course and compatible indexed passages. |
| 2 | Encode the instructed query; compute dense and BM25 rankings. |
| 3 | Union the leading candidates from both routes and apply bounded lexical augmentation. |
| 4 | Send at most 20 fused candidates to qwen/qwen3-reranker-8b. |
| 5 | Select up to five passages within a 1,024-token source-body budget. |
| 6 | Preserve selected evidence and pass it to the generation workflow. |

The selected default has no parent-window expansion, no additional metadata-score weight and no automatic query translation. These choices follow the observed comparisons in Chapter 6, not a claim that the omitted methods are ineffective for every corpus. The text model is configured as deepseek-flash; a proposed future model identifier is not presented as a deployed or evaluated replacement.

<!-- PAGE -->
## 4.3  Precise difficulty allocation

Difficulty allocation is represented as an integer plan. If a request contains N questions, the non-negative counts for easy, medium and hard must sum exactly to N. The current interface supports one to ten questions. A request for three hard questions is valid as (0, 0, 3); the system does not impose a balanced distribution. Fixed slots prevent a model from satisfying a request by silently changing labels or rearranging the requested plan.

The operational rubric defines easy questions as recognition or explanation of a clear concept, usually with one or two marking points. Medium questions apply or analyze related concepts in a concrete situation, with two or three linked points. Hard questions integrate concepts, handle constraints and justify a judgment or design, with three to six points. Point counts make the intended design inspectable; they are not themselves a difficulty metric. The learner profile provides the context in which these tasks are intended to be interpreted.

![Figure 2. Exact difficulty allocation in the current light-mode interface. The example requests three hard questions and zero easy or medium questions. This is a captured form state, not an additional generation experiment.](figures/ui-difficulty-light.png)

After structural validation, a separate text-model request assesses the questions without the author's target allocation or generated difficulty-design fields. It receives the questions, answers, evidence, learner profile and rubric. It checks demand, answerability and ambiguity. This is target-blind model screening; generation and screening currently use the same model family and may share errors.

Eligible structural or substantive screening failures share one regeneration allowance. A second unsatisfactory result is not saved as a successful asset. This controls operational behavior, but “precise control” is demonstrated most strongly for the discrete allocation. Whether each item is truly easy, medium or hard for real students requires independent evaluation and response data.

<!-- PAGE -->
## 4.4  Reviewing and revising a learning asset

The material view presents the generated explanation alongside questions, reference answers and accessible source evidence. The evidence panel supports checking what the system actually retrieved rather than assuming the entire uploaded document was available to the generator. Version-specific records distinguish original model checks, later edits and explicit approval actions.

![Figure 3. Current light-mode material and source-evidence view, captured on 19 September. The displayed assignment is a historical generation artifact; the screenshot is evidence of the current interface, not a new assessment of that artifact's quality.](figures/ui-evidence-light.png)

For self-practice, the learning view can conceal answers until requested. This is a usability feature, not a secure assessment boundary. The system does not claim to prevent a learner from accessing solutions in an authoring account. Institutional assessment delivery would require a different permission and release model.

The distinction between model screening and approval is visible in the data model as well as the interface. An edit must not inherit a stale model assessment as though the new text had been screened. Similarly, a teacher's approval does not create a model-review result retroactively. Historical materials without the newer screening fields remain readable with their evidence limitations intact.

## 4.5  Operational constraints

The prototype bounds document size, indexing work, question count and provider requests. These controls support predictable demonstrations and preserve failure evidence. They are not measurements of latency or maximum throughput. Local storage and a single-process job lifecycle remain deployment assumptions; concurrent workloads, process restarts and long-running ingestion need dedicated operational evaluation before broader use.

The figures capture the actual light-mode application. Their captions distinguish current interface state from historical provider results.

<!-- PAGE -->
# 5  Evaluation Methodology
## 5.1  Evidence hierarchy and dataset construction

Five retrieval rounds were conducted on 12 September and preserved as configurations, outputs and comparison tables. R1 was a synthetic pilot; R2 introduced external labels; R3 isolated recursive segmentation comparisons; R4 compared budgeted retrieval configurations; R5 examined query translation. These rounds differ in data and constraints. Their scores must not be plotted as a single continuously improving accuracy curve.

Table 3. Evaluation material and its principal limitation.

| Study | Material and local split | Principal limitation |
|---|---|---|
| R1 | 14 development and 14 test answerable queries | Assistant-authored pilot; no independent labels |
| R2 MLQA | 92 queries; 12 development, 80 test | Answer-derived relevance; restricted bilingual subset |
| R2 T2Ranking | 20 technical queries; 10 development, 10 test | Both local splits drawn from upstream development data |
| R3 | R2 MLQA queries; 12 real course documents for structural audit | Course documents lack human relevance judgments |
| R4 | 184 development and 168 held-out scenarios | Answer-span benchmark; not a full course assessment corpus |
| R5 | 96 development and 124 held-out scenarios | Paired language scenarios and source dependence |

MLQA [19] supplies multilingual extractive question-answering annotations. Its original answer spans support identifying whether retrieved evidence contains an answer, but do not provide exhaustive passage-relevance judgments for this educational task. The T2Ranking [20] subset contains 339 passages with 157 positive and 182 negative query–passage pairs. Its binary labels come from the C-MTEB derivative, not a reconstruction of the original four-level scores; unjudged cross-query pairs are not confirmed negatives.

The real-course collection contains six Chinese Hello Algorithm documents and six English OpenDSA documents. These support inspection of segmentation behavior on authentic educational text. They do not yet supply a manually labeled retrieval test set. “Real course material” and “human-annotated course retrieval benchmark” must therefore remain distinct descriptions.

In R4, development data contain 46 bilingual families and the held-out set contains 42 fresh families. Two query languages and two retrieval conditions produce the scenario counts in Table 3. Full-text families are separated, although titles can overlap. In R5, 31 held-out bilingual families produce 62 mixed-language and 62 cross-language scenarios. Related scenarios are not independent samples simply because their query strings differ.

<!-- PAGE -->
## 5.2  Metrics, budgets and uncertainty

Recall@k is the proportion of labeled relevant passages retrieved among the first k results, averaged over queries. Hit@k records whether at least one relevant result appears. Mean reciprocal rank, MRR@k, rewards an earlier first relevant result. For chunking experiments, answer-span hit instead asks whether the retrieved text contains the annotated answer span. It is not synonymous with exhaustive relevance recall.

For a query q, let Gq be the labeled relevant set, Rq,k the retrieved top-k set and rq the rank of its first relevant result. The query-level recall is |Gq ∩ Rq,k| / |Gq|, hit is 1 if the intersection is non-empty and 0 otherwise, and reciprocal rank is 1/rq if rq ≤ k and 0 otherwise. Reported macro averages weight each query equally. Denominators and truncation policies must accompany these metrics.

The R3 comparison reports both top-five retrieval and a separate 6,000-character condition. The latter can admit substantially more passages and must not be interpreted as a chunking-only gain over the former. R4 and R5 use a fixed source-body token budget. Token counts are measured by the retrieval tokenizer; they do not estimate monetary cost without corresponding provider usage data.

R5 compares methods on paired scenarios. Its paired bootstrap groups scenarios using 25 source-connected components, reducing the risk of treating shared-source examples as independent. The resulting interval describes uncertainty within this restricted corpus, not all Chinese–English educational retrieval. Failed reranking calls remain in the denominators so that observed availability affects the end-to-end comparison rather than being deleted as inconvenient samples.

## 5.3  Configuration selection and audit protocol

R4 configuration selection used development results before the fresh held-out evaluation. Sixteen development configurations and fourteen held-out configurations were evaluated; the local 0.6B reranker variants were not run on the held-out set. An unrun cell is missing evidence, not a zero score. Reporting all tested alternatives also exposes when the selected configuration is not the retrospective leader on a held-out metric.

The new content audit is a separate retrospective exercise. It reads original version-one outputs and their cited source snapshots from five historical assets. Fifteen explanatory sections and eight short-answer questions form 23 review units. The reviewer checks direct support, reasonable inference, answerability, ambiguity, historical scope and intended demand. No multiple-choice questions or real student responses are present in this sample.

The audit is AI-assisted, non-blind and qualitative. It records a rationale and suggested correction for each unit and preserves hashes of the inputs. It does not populate human-review fields, change approval states or estimate a teacher agreement rate. These constraints are part of the method, not omissions to conceal when interpreting the results.

<!-- PAGE -->
# 6  Results and Discussion
## 6.1  Dense and lexical retrieval: R1–R2

The R1 pilot favored dense retrieval: test Recall@5 was 90.48%, compared with 46.43% for the tested BM25, reciprocal-rank fusion and MMR variants. Because its examples were assistant-authored, this result was used to identify a risk in indiscriminate fusion rather than to establish a strong retrieval claim. R2 then tested existing external annotations.

Table 4. R2 local test Recall@5 (%). MLQA has 80 queries; T2Ranking has 10. Absolute scores are not directly comparable across datasets.

| Retrieval method | MLQA | T2Ranking |
|---|---:|---:|
| Dense | 91.25 | 40.58 |
| BM25 | 47.50 | 37.31 |
| Reciprocal-rank fusion | 61.25 | 47.02 |
| Fusion with MMR | 50.00 | 28.29 |
| Bounded dense–lexical augmentation | 91.88 | 44.74 |

Unrestricted fusion did not consistently improve the dense baseline. On MLQA, it sacrificed recall substantially; on the small T2Ranking subset it produced the highest recall among these methods. The bounded lexical method retained the dense route's strength on MLQA while improving T2Ranking recall relative to dense retrieval. This supported its use as a controlled candidate for subsequent experiments, rather than proving a universal advantage.

Other metrics reinforce the trade-off. MLQA MRR@5 increased from 0.8858 to 0.9390 with bounded augmentation, whereas T2Ranking MRR@5 changed from 0.7333 to 0.7167. The latter retrieves a larger fraction of labeled positives without placing the first positive earlier on average. Reporting only recall would obscure that difference. The ten-query T2Ranking test subset is also too small to justify broad domain claims.

## 6.2  Recursive boundaries: R3

On the 80-query MLQA test subset, legacy 1,200-character splitting and recursive 1,200-character splitting both achieved 96.25% answer-span hit under top-five dense retrieval. Recursive 800-character chunks reached 95.00%. Under the separate 6,000-character condition, the corresponding values were 100.00%, 100.00% and 97.50%. These results do not show an isolated hit-rate improvement from recursion.

The real-course structural audit nevertheless provides a practical reason to improve boundaries. Across twelve documents, chunk count increased from 75 to 115 while the recorded repeated-character fraction fell from 9.20% to 3.41%. Cleaner boundaries reduced measured duplication, but more chunks can require more embedding and indexing work. This is a structural trade-off, not proof of lower total cost or higher semantic relevance. Hybrid R3 results change retrieval as well as chunking and cannot isolate the segmenter's contribution.

<!-- PAGE -->
## 6.3  Budgeted configuration selection: R4

R4 compared chunk sizes, title context, query instructions, lexical fusion, reranking and context expansion. The selected API reranker configuration without expansion achieved development answer-span hit of 98.37% and MRR of 0.9570, compared with 88.04% and 0.8053 for the baseline. It was selected before the fresh held-out evaluation.

Table 5. Selected R4 comparisons. Each held-out row contains 168 scenarios; context is mean source-body tokens. MRR is computed from leaf-chunk ranking.

| Configuration | Dev hit (%) | Held-out hit (%) | Held-out MRR | Context |
|---|---:|---:|---:|---:|
| Baseline | 88.04 | 97.02 | 0.8868 | 493.4 |
| Query instruction only | 95.65 | 97.02 | 0.9484 | 598.7 |
| Token 128 | 86.96 | 98.21 | 0.8949 | 369.1 |
| Token hybrid | 96.20 | 96.43 | 0.9334 | 608.3 |
| API 8B, no expansion | 98.37 | 97.02 | 0.9524 | 553.4 |
| API 8B, parent expansion | 98.37 | 97.02 | 0.9524 | 591.8 |

![Figure 4. R4 held-out ranking comparison. Equal hit rates can coexist with different reciprocal ranks; the selected configuration's main observed gain over baseline is ranking, not additional answer coverage.](figures/r4-results.png)

On held-out data, the selected configuration preserved hit at 97.02% and increased MRR by 0.0656. It did not improve held-out hit over baseline. Token-128 achieved a higher held-out hit rate, but lower MRR, and had performed worse on development data. Retrospectively switching the claimed winner based on that held-out result would undermine the original selection procedure.

The instruction-only alternative was competitive: its held-out MRR was 0.9484 without the added reranker stage. Consequently, the full baseline-to-selected gain cannot be attributed solely to reranking. Parent expansion consumed more context without improving these selected metrics, so no expansion remained the default. The evidence supports a defensible operating point, not the claim that the chosen policy is the strongest or most efficient on every relevant objective.

<!-- PAGE -->
## 6.4  Does translation help? R5

R5 compared the original query, a translated query and a dual-query route under the same downstream candidate and context constraints. The shared evaluation corpus contained 207 sources and 236 chunks, including older distractor material. The original policy was retained after a development tie before held-out evaluation; translation was not selected retrospectively from a favorable language slice.

Table 6. R5 held-out answer-span hits. Direction indicates query language to source language; mixed permits both source languages.

| Retrieval condition | Original | Translated | Dual query |
|---|---:|---:|---:|
| English → Chinese (n = 31) | 29/31 (93.55%) | 29/31 (93.55%) | 28/31 (90.32%) |
| Chinese → English (n = 31) | 25/31 (80.65%) | 29/31 (93.55%) | 29/31 (93.55%) |
| Mixed corpus (n = 62) | 55/62 (88.71%) | 53/62 (85.48%) | 53/62 (85.48%) |
| All scenarios (n = 124) | 109/124 (87.90%) | 111/124 (89.52%) | 110/124 (88.71%) |

The aggregate translated-query difference was +1.61 percentage points, with a grouped paired 95% interval of −4.84 to +7.50 points. For dual queries, the difference was +0.81 points with an interval of −4.17 to +5.56. Both intervals include zero. These findings do not establish a reliable aggregate translation benefit on this corpus.

The directional result is especially relevant to an English prompt over Chinese course material. Translation did not improve that slice, while dual retrieval slightly reduced hit. Chinese-to-English retrieval improved numerically, but three of its four net gains corresponded to failures in the original route's API calls. The observed difference therefore mixes availability with semantic retrieval behavior. It cannot all be credited to better translation.

Across development and held-out runs, 660 reranking attempts included 21 HTTP 503 failures; 20 occurred in held-out evaluation. Held-out failure counts were six, six and eight for the original, translated and dual policies respectively, and were retained in scoring. An observed translation also confused “foundation” as a concept with an organization name, illustrating potential query drift.

Mean recorded stage-composite times were approximately 3,552, 3,838 and 4,851 ms for original, translated and dual retrieval. These are experiment-stage measurements, not served application latency. Given uncertain aggregate gains, added work and language-specific regressions, automatic translation remains disabled. A later conditional policy should be evaluated on new source-disjoint course data with availability effects reported separately.

<!-- PAGE -->
## 6.5  Functional validation and generation evidence

The preserved education-v2 live run indexed fourteen demonstration chunks and produced an explanation, a one-question quiz and a one-question assignment. An out-of-scope request produced an insufficient-evidence response. Ten workflow checks passed across nine provider attempts. An earlier unsuccessful run remains archived: an explanation incorrectly contained a question before the conflicting instruction was corrected. The final run is evidence of a small real workflow, not a broad generation benchmark.

The later education-v3 difficulty run requested three hard questions and a mixed allocation of one easy, one medium and one hard question. Both final distributions matched the requested counts, and six final questions passed model screening. One observed rejection led to regeneration. These results support allocation enforcement on the tested cases; they do not validate student difficulty or independent correctness.

Table 7. Validation evidence and permissible interpretation.

| Evidence | Recorded result | What it establishes |
|---|---|---|
| Historical core live run | 3 assets; refusal case; 9 provider attempts | Small real API workflow under its recorded version |
| Historical difficulty run | 2 allocations; 6 final questions | Count compliance and model screening on these cases |
| September 19 core regression | 112 Python tests passed | Exercised software behaviors at the inspected revision |
| September 19 frontend regression | 55 tests passed | Exercised frontend logic, not a learner usability study |
| New retrospective AI audit | 23 units; 10 revisions recommended | Qualitative defects in the inspected historical sample |

The current preflight confirmed configured text and embedding providers, but explicitly did not verify a new live model run. Historical generation results must not be relabeled as validation of the complete present parser–retriever–generator stack. A fresh controlled demonstration of that stack remains an appropriate pre-submission check.

## 6.6  AI-assisted review findings

Thirteen units were judged supported without a required revision and ten received revision recommendations. All inspected citation identifiers belonged to the recorded evidence, yet some associated claims lacked direct support. Problems included citations that did not contain the retrieval mechanism being asserted, unclear distinctions between source reindexing and generated-content editing, and remedies that did not actually correct an unsupported conclusion.

These counts describe a convenience sample and an assistant's judgments, not a quality pass rate. The audit was not blind to the original difficulty targets and used no independent expert raters. Nevertheless, its itemized reasoning reveals defects missed by structural checks and earlier model screening. Its immediate value is to guide revision and strengthen the next evaluation protocol. Appendix A provides concrete examples and identifies all eight reviewed questions.

<!-- PAGE -->
## 6.7  Cost, reliability and reproducibility

The archived R1–R5 ledger contains 1,432 provider attempts: 309 embedding, 110 text and 1,013 reranking attempts. Twenty-eight failures were recorded. The sum of available provider cost fields is 0.86078402, but 138 calls lack a cost value. This incomplete field sum must not be treated as a complete account bill or an exact cost of operating Lumori. Historical CA1 calls, subsequent application activity, local compute and downloads are outside this experiment ledger.

Retries, failures and missing billing fields affect how a retrieval policy should be assessed. A policy can improve rank on successful responses but reduce availability or increase delay. The R5 results expose this problem directly. Future comparisons should report conditional semantic retrieval quality alongside unconditional success, observed latency and complete cost coverage, using the same repeated trial schedule across alternatives.

Reproduction depends on more than the model name. Corpus snapshots, split manifests, chunking configuration, tokenizer revision, embedding compatibility, candidate limits and failure policies affect the results. Archived vectors support analysis without additional embedding calls, while fresh provider calls may differ because hosted models and service conditions evolve. Reproduction should distinguish replaying stored outputs from rerunning the full external computation.

## 6.8  Answers to the research questions

For RQ1, bounded lexical augmentation avoids some failures of unrestricted fusion, recursive splitting improves the measured structural duplication property, and the selected R4 policy improves held-out ranking over baseline without increasing hit. These are different findings with different denominators. No single number summarizes the entire optimization programme, and cheaper alternatives remain competitive.

For RQ2, translation is not uniformly helpful. In the tested English-query/Chinese-source condition it provides no hit-rate gain. The aggregate interval includes zero and part of the favorable reverse-direction result is confounded by API failures. The present evidence supports retaining the multilingual original-query default rather than translating every request.

For RQ3, the system can enforce exact allocations and preserve a record of intended and model-assessed demand. It has not established calibrated learner difficulty. The AI audit further demonstrates that structural validity and a model's difficulty judgment can coexist with insufficient citation support. A future evaluation must therefore measure semantic support and task clarity independently of allocation compliance.

Together, these results favor a transparent, bounded authoring workflow. The relevant engineering objective is not to maximize the number of model stages, but to obtain reviewable evidence and expose failures at an acceptable resource cost. Claims of educational effectiveness await a study with actual educators and learners.

<!-- PAGE -->
# 7  Limitations and Next Research Stage
## 7.1  Threats to validity

The main external-validity limitation is the gap between available benchmark subsets and undergraduate teaching practice. MLQA answer spans and web relevance labels help evaluate retrieval, but do not cover lecture-specific terminology, multi-step proofs, code interpretation or pedagogically useful distractors. The twelve authentic course documents have not yet received independent relevance annotations. A larger collection alone would not fix that missing evaluation layer.

Selection bias also matters. Multiple configurations were explored, and several experiments reuse related material. The R4 held-out family split and R5 grouped uncertainty analysis reduce specific risks but do not establish cross-course generalization. The AI-assisted audit is retrospective, small and unblinded. Its defect counts cannot be extrapolated to all generated assets or compared to teacher ratings that do not yet exist.

The difficulty rubric measures intended demand. Neither model agreement nor a correct allocation demonstrates learner success probability, item discrimination or personalization. Similarly, no timed educator study has measured drafting effort, correction time or usability. The project brief's proposed benefits remain hypotheses, not results.

## 7.2  Priorities before and after CA1

Before submission, the most valuable additions are a fresh demonstration of the current full text path and an independent subject-expert review of source support, answerability and intended demand. The new AI audit can prepare examples and suggested corrections, but should not occupy fields labeled human review. A held-out course evaluation should fix queries and relevance judgments before comparing revised retrieval policies, and keep source families separated.

A generation study should compare the same text model with and without retrieved evidence, then distinguish factual support, objective alignment and correction effort. Multiple-choice evaluation must additionally check whether distractors are plausible and whether exactly one answer is defensible. Student response collection, if undertaken under the appropriate institutional process, would support actual difficulty calibration rather than inference from authoring labels.

## 7.3  Multimodal extension

The later thesis stage will examine transformation of generated text into at least two alternative modalities, as required by the project scope. Audio explanations and visual-aid representations are candidate directions, not completed evaluated outputs. Existing figure extraction and description can provide grounded input evidence, but should be assessed separately for extraction coverage, description fidelity and retrieval usefulness. Multimodal RAG research [15] supplies context for this extension without establishing its performance in Lumori.

The current manuscript therefore concludes at the text-based foundation. The literature survey, architecture, implemented prototype and traceable experiments provide substantive CA1 material. Remaining quality evaluation and fresh integration evidence are explicit, while later multimodal chapters can build on the same provenance and versioning principles without rewriting the earlier experimental record.

<!-- PAGE -->
# References

{{REFERENCES_1}}

<!-- PAGE -->
# References (continued)

{{REFERENCES_2}}

<!-- PAGE -->
# Appendix A  AI-Assisted Content Audit
## A.1  Procedure and traceability

The audit was conducted on 19 September using five archived version-one assets: the explanation, assignment and quiz from the final education-v2 run, followed by the all-hard and mixed assets from education-v3. It compared each unit's actual text with its cited retrieved excerpts. File hashes, original units, citation membership, rationales and proposed revisions are retained in the accompanying JSON and CSV. No original record was rewritten.

A unit was marked for revision when its cited excerpts did not adequately support the claim, the answer recommended an ineffective remedy, the question's state transition was ambiguous, or a historical system limitation could be mistaken for current behavior. Reasonable engineering inference was distinguished from an explicit statement in the source. “Supported” means no required correction was identified in this audit; it is not an expert endorsement.

Table A1. All reviewed short-answer questions. L denotes explanation, A assignment, Q quiz, H all-hard, and M mixed; section-level judgments are recorded separately.

| Review ID | Judgment | Main observation or required change |
|---|---|---|
| A-Q1 | Supported | Separates embedding rebuild from edited-content reapproval; add a concrete state sequence for stronger discrimination. |
| Q-Q1 | Supported | Correctly separates identifier validity and support; closely repeats the source example. |
| H-Q1 | Revise | Ratings or logs do not repair an unsupported assertion; require correction or withdrawal. |
| H-Q2 | Revise | Preserve the old review; create and review a new draft rather than ambiguously update history. |
| H-Q3 | Revise | Distinguish credentials from non-secret technical evidence and date the historical scenario. |
| M-Q1 | Revise | Retrieve and cite the passage directly supporting the role of retrieval. |
| M-Q2 | Supported | Compatibility claim is direct; rebuild is reasonable inference needing a clearer citation. |
| M-Q3 | Revise | Specify whether edited text is an indexed source or only a generated explanation. |

Of fifteen explanatory sections, ten were marked supported and five for revision. Of eight questions, three were marked supported and five required revision. The machine-readable totals are authoritative: thirteen supported units and ten revision recommendations overall.

The audit is not human review and does not measure inter-rater agreement. Targets and original model judgments were visible. A later independent protocol should hide those labels before demand assessment, use subject experts and report disagreements instead of replacing them with a single assistant judgment.

<!-- PAGE -->
## A.2  Two representative corrections

Example 1: correcting an unsupported conclusion. In H-Q1, the proposed answer suggests process changes such as additional ratings or logs in response to a claim whose citation does not support it. Those changes can improve traceability but do not repair the statement itself. The required correction is to compare the claim with its cited excerpt, identify the unsupported part, and either remove it or replace it with a narrower statement justified by the evidence. A further source can support a revised claim only after its relevance and entailment are checked.

Suggested marking expectation: identify the precise unsupported assertion; explain why identifier membership is insufficient; provide a source-consistent correction or explicit withdrawal; retain the original evidence so the change can be inspected. This rubric makes the remedy substantive rather than rewarding generic calls for more review. It remains an AI-proposed revision, not a newly validated question.

Example 2: separating two state transitions. In M-Q3, “edited content” is ambiguous between an indexed course source and a generated learning asset. Requiring reindexing after every edit would conflate these objects. A generated explanation that is not part of the source corpus does not need source re-embedding solely because its wording changes.

Suggested revised scenario: “The embedding model for uploaded source passages changes. Separately, a reviewer edits a generated explanation that has not been ingested as source material. State which vectors must be rebuilt, which content version requires renewed approval, and which historical records should remain unchanged.” The answer should rebuild source representations for compatibility, create and review the edited asset version, and preserve the earlier text and evidence. The question should cite excerpts that explicitly support both distinctions.

## A.3  What the audit changes

The review strengthens the thesis's interpretation rather than rewriting past success flags. Historical model screening remains a recorded event, and the later audit adds new evidence of its limitations. The inspected units demonstrate that reference membership, answerability and direct support are separate checks. They also show why long, multi-part wording should not be accepted as sufficient evidence of high cognitive demand.

The immediate revision backlog is concrete: repair the five flagged questions and five flagged explanatory sections according to the detailed row-level record. Revisions must be saved as new versions and evaluated again before any approval. The present task has documented the judgments and suggestions; it has not silently changed the application's teaching assets or registered an assistant as a human reviewer.

The full audit record is located at docs/thesis/review/AI_Content_Review.md, with corresponding CSV and JSON files. Those files retain more detail than the condensed table, including exact source snapshots. A future reviewer can disagree with the assistant's decision while still inspecting the evidence on which it was based.

<!-- PAGE -->
# Appendix B  Evidence and Reproduction Index

Paths below are relative to the research repository. The deployment-only Lumori repository intentionally omits most research artifacts; it is not a replacement for the evidence archive.

Table B1. Principal local evidence sources.

| ID | Source | Use in this manuscript |
|---|---|---|
| E1 | docs/ca1/literature/Source_Ledger.md | Original publication inspection and literature boundaries |
| E2 | docs/rag/daily-records/20260912/comparison-tables.md | R1–R5 numerical tables and provider ledger |
| E3 | docs/rag/R4_RESULTS_20260912.md | R4 configuration selection and held-out results |
| E4 | docs/rag/R5_RESULTS_20260912.md | Translation directions, failures and uncertainty |
| E5 | docs/ca1/evidence/live-20260912T040126795872Z/ | Historical core generation and source snapshots |
| E6 | docs/ca1/evidence/difficulty-20260912T042551358609Z/ | Historical difficulty allocations and model reviews |
| E7 | docs/ca1/CA1_Readiness_Audit_20260919.md | Current inspection and regression-check boundaries |
| E8 | docs/thesis/review/ | New AI-assisted unit judgments and immutable input hashes |
| E9 | docs/thesis/figures/ | Actual light-mode screenshots and analytical figures |

## B.1  Version and reconstruction

The inspected research baseline is commit 3e61644a251e9e88e450463ebd57ea0d28c41238, associated with checkpoint-2026-09-18. The present report and audit are a subsequent documentation update. Individual experimental outputs retain their own historical configurations; the baseline commit does not imply that every experiment used the current runtime defaults.

The editable manuscript is docs/thesis/Manuscript.md. The report builder is scripts/build_thesis_report.py, and scripts/build_thesis_review.py reconstructs the recorded audit artifact from its preserved inputs and explicitly encoded judgments. Rebuilding that artifact is serialization of those judgments, not a new independent evaluation. The final Word document and PDF are stored in output/ with the Lumori_Thesis_Part_I_v0.2 name.

Reproducing numerical analysis should begin with the archived comparison tables and raw result files. Fresh external experiments should use separate output directories, retain failures and record provider identifiers and configuration. Do not overwrite old outputs or treat a replay as a new provider run. Credentials and personal account data are deliberately excluded from the manuscript and its figures.

## B.2  Subsequent thesis integration

Later chapters will add parsing comparisons, multimodal outputs and educational evaluation when results exist. Chapter numbering is provisional. Apply institutional title-page and declaration requirements when the official template is supplied; no approval or student identifier has been invented.
