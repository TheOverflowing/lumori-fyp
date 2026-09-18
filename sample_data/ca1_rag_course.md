# CA1 demonstration course: evidence, retrieval, and reviewed learning materials

This is self-authored synthetic teaching material for a software demonstration. It is not an official course handout, a research result, or a benchmark of any model. Its examples deliberately separate evidence from claims about quality. The notes contain several topics so that the application must select a subset of passages for a request. A successful demonstration does not establish accuracy for real students.

## RAG ingestion and retrieval

RAG ingestion begins with extracting text from an allowed document. The application divides the text into passages and stores each passage with an identifier, document name, and page reference. An embedding service maps passage text to a numeric vector. The passage vector and its source metadata belong together: a vector without its text cannot supply a reader with inspectable evidence. A small overlap between neighboring passages can preserve context at a boundary, although overlap also creates repeated text.

At request time, the application embeds the learning objective using a compatible embedding configuration. It compares the query vector with stored passage vectors and ranks the candidates by similarity. The selected passages accompany the objective in a text-generation request. The generator should use those passages to explain a covered concept or write an answerable exercise. Retrieval supplies external evidence; it does not update the language model's parameters and does not itself prove the final explanation correct.

For a RAG ingestion example, imagine a document with eight passages and a retrieval limit of three. A request about citations should rank citation passages ahead of unrelated interface notes. The evidence record should preserve the actual ranked passages and similarity scores. A score measures the comparison used by this retrieval configuration; it is not a calibrated probability that the answer is correct. If every passage is returned, the run demonstrates context supply but does not demonstrate selective ranking. A human still checks whether the selected passages cover the requested objective.

## Citation support and evidence boundaries

Citation support requires reading the cited text. An existing citation identifier proves that a passage can be found in the recorded source set. It does not prove that the passage supports every sentence in the explanation. For example, a passage saying that human review is required cannot support a generated claim that retrieval always eliminates mistakes. The citation is structurally valid in that example, but the factual conclusion is unsupported.

When assessing citation support, separate three questions. First, does the cited identifier belong to the passages supplied to this generation? Second, does that passage contain the information needed for the claim? Third, does the explanation preserve any conditions or limitations in that information? A program can check the first question mechanically. The second and third require a content judgment. An automated draft must not be described as human-approved merely because its citation identifiers passed validation.

An evidence boundary is crossed when a requested conclusion cannot be derived from the supplied material. Suppose a learner asks for a clinical treatment dosage while the course notes only explain retrieval systems. The notes provide no clinical evidence. The appropriate response is to report insufficient evidence and avoid inventing a dosage or an exercise that presents one as correct. The generator may explain that the relevant source material is missing. A provider outage or malformed response is an operational failure, not a successful refusal based on evidence.

## Embedding compatibility and index versions

Embedding compatibility concerns the relationship between stored document vectors and a new query vector. Vectors must have the same dimension before their coordinates can be compared. Matching dimensions alone are insufficient: two models can use different semantic spaces while producing the same number of coordinates. A query from one space must not be assumed compatible with passages embedded by another model.

The application should associate an embedding configuration signature with each indexed passage. A signature can identify the embedding model, endpoint, and relevant options without containing an API credential. Replacing a credential for the same embedding configuration does not by itself change the semantic space. Changing the model or relevant embedding options requires checking compatibility and usually rebuilding document vectors before generating new material. A useful failure message explains why reindexing is needed instead of silently comparing incompatible vectors.

Embedding compatibility and a reviewed text version are different concerns. Reindexing changes the vectors used by future retrieval. It does not retrospectively repair or approve an already generated explanation. The earlier explanation remains associated with its original source passages and generation settings. If a reviewer later edits that explanation, the system creates a new text version. Keeping these histories separate lets an observer distinguish a retrieval configuration change from a correction to teaching content.

## Reviewed text version and learning access

A reviewed text version identifies the exact content a reviewer inspected. Newly generated teaching material begins as a draft. Saving an edit creates a later draft version, and approval applies to the current version. A learning view should show content only when that current version is approved. If someone changes approved text, its new version needs review before it is shown as published learning material. An approval request for an older version should fail instead of approving unseen changes.

For a reviewed text version example, version one is the original generated draft. A reviewer corrects its title or explanation and saves version two. Approval of version two permits the learning view to display that text. A later save creates version three and returns the material to draft. The original version-one evidence should remain inspectable so an evaluator can tell what the generator produced and what a person changed. A technical script exercising these transitions does not supply a human quality judgment.

For practice questions, the learning view can hide the reference answer, explanation, and difficulty rationale until answers are requested. Hiding fields in the returned student-facing object is stronger than merely hiding text with a visual style. This local demonstration does not implement authenticated roles, secure examinations, or classroom access control. The answer-reveal option is a practice feature. It must not be presented as protection against a learner who directly requests the answer endpoint.

## Difficulty intent and assessment design

Difficulty intent describes the reasoning a question is designed to require. An easy item can ask a learner to identify one concept or explain one direct relationship from the notes. A medium item can apply a concept in a supplied situation or compare two closely related cases. A hard item can require combining several covered concepts and analyzing constraints. Difficulty should come from the intended reasoning, not from unnecessarily obscure wording or facts outside the source.

For an easy example, ask what retrieval supplies to a generator. For a medium example, describe an answer with an existing but irrelevant citation and ask why structural validation is insufficient. For a hard example, describe a change to the embedding model and a later edit to approved teaching text, then ask which stored objects need rebuilding or renewed approval. Each example stays within this document. A multiple-choice question needs distinct options and one defensible keyed answer; a short-answer question needs a reference answer that a reviewer can justify from the cited passages.

Difficulty intent is not measured student difficulty. Without learner response data, the system cannot claim that a label predicts how many students will answer correctly. A reviewer can assess whether the requested cognitive demand matches the question design, but that judgment is different from empirical calibration. Record the intended demand and any review notes separately. Do not invent student scores, learning gains, or instructor ratings for a software demonstration.

## Evaluation records and failures

An evaluation record should distinguish software checks, content review, and learning outcomes. Software checks can establish that a request completed, that an answer field was hidden, or that a citation identifier belongs to the saved source set. Content review examines correctness, evidence support, answerability, ambiguity, and the suitability of the intended reasoning demand. Learning outcomes require an appropriate study involving learners. Passing the first category does not establish the second or third.

When preserving evaluation records, retain the initial generated draft, the actual retrieved text, generation settings that exclude credentials, and later revisions. A human reviewer supplies their own observations and ratings; an automated test should leave those fields blank. A failed request should remain in the record with its status and safe error information. A request refused because evidence was missing is a different outcome from a network error. Neither should be silently replaced by a fabricated successful example.

A compact demonstration can cover a lesson, a quiz, and an assignment with one question per assessment. One out-of-source objective can probe the refusal behavior. These few examples are integration evidence, not a statistically representative evaluation. State the sample size and whether any human actually reviewed the output. A later evaluation can add diverse course materials, blinded review, and real learner tasks once its protocol is agreed.

## Local operation, exports, and deferred media

This prototype is a local development application. A course groups source documents and generated materials. An export should preserve the teaching text and enough citation metadata to inspect its provenance outside the application. A generation evidence export is more detailed than a student handout: it can contain retrieved passages, configuration signatures, revision history, and provider call usage. Exported material should identify whether the current text is draft or approved.

Credentials belong in local configuration and must not appear in handouts, evidence bundles, or screenshots prepared for review. A daily call limit bounds attempts, including attempts that fail. Before a live demonstration, confirm that text and embedding capabilities are configured; this check alone does not prove that the provider accepts the chosen model. Reusing existing local evidence for workflow demonstrations avoids unnecessary new provider calls.

Speech and image generation are deferred in this text-focused CA1 demonstration. A future media asset should be tied to the exact reviewed text version so that it cannot silently accompany an unrelated revision. After editing the text, previously approved media should require a consistency check. The presence of an image or audio API setting is not evidence that media quality has been validated. The current demonstration should make only the claims supported by its saved text, retrieval, and workflow records.
