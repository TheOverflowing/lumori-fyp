# CA1 demonstration and acceptance

The supplied project brief requires a literature survey, system design and an initial functional prototype with core text generation and RAG. It does not provide a report length or specific CA1 date. The English manuscripts are working drafts. This checklist records proposed evidence, not a school-issued scoring rubric.

## Status as of 12 September 2026

| Requirement | Evidence available | Remaining action |
| --- | --- | --- |
| Literature survey | English standalone review, 14 research sources and source ledger | Supervisor review and update before formal submission |
| System design | English report, architecture, source/version rules and implementation | Confirm course and intended difficulty rubric |
| Core text with RAG | Historical [53 passing fixture-based tests](evidence/backend-tests-20260912.xml) and an [`education-v2` live technical acceptance](evidence/live-20260912T040126795872Z/results.json) covering indexing, three materials, refusal and review mechanics | Human review of source support, answerability and intended difficulty; update the formal report |
| Precise difficulty control | `education-v3`: [106 passing Python tests](evidence/difficulty-tests-20260912.xml), 33 passing frontend tests, isolated browser checks and [two real difficulty-control cases](evidence/difficulty-20260912T042551358609Z/results.json), including an observed rejection and regeneration; see [difficulty rules](../Difficulty_Control.md) | Evaluate the actual items with teachers and, for empirical calibration, learner response data; update the formal report |

The current text model is DeepSeek `deepseek-flash`, with JSON-object output enabled and thinking disabled. Embeddings use OpenRouter `qwen/qwen3-embedding-8b` with float encoding. The planned future model `deepseek-v4.1flash` requires an explicit configuration change and a new acceptance run; no automatic switch is configured. Speech and image APIs are outside this run.

[The minimal provider check](evidence/provider-check-20260912.json) records successful real HTTP 200 responses: two English/Chinese embedding inputs produced 4096-dimensional vectors, and the text model returned the requested JSON object. The [final full run](evidence/live-20260912T040126795872Z/results.json), using prompt version `education-v2`, passed all technical checks with nine provider attempts and no structural repair:

| Case | Observed outcome |
| --- | --- |
| Index | 14 source chunks embedded successfully |
| Lesson | A draft explanation with no questions |
| Quiz | A draft with one short-answer question |
| Assignment | A draft with one short-answer question |
| Unsupported objective | `insufficient_evidence`, with a reason and no material created |
| Review mechanics | All ten checks passed; all three materials ended as drafts |

Each supported generation retrieved five of the fourteen candidate chunks, and its expected topic phrases were present. These observations do not prove semantic relevance, factual support or appropriate difficulty. `manual_quality_verified` remains false. Test fixtures remain software evidence only.

The final run explicitly used `--use-app-data` after the existing data was backed up, so the materials are available in the local application's `CA1 live smoke 20260912T040126795872Z` course. A restart check confirmed that the three drafts and five job-evidence exports remain available. Existing course, document and chunk records were unchanged against the backup; see the [verification summary and code hashes](evidence/backend-verification-20260912.json). The default script behavior still uses isolated data. The formal `v0.1` Word/PDF reports and `Progress_Report.md` remain 11 September snapshots and must be updated before submission.

The [first full run](evidence/live-20260912T035641297641Z/results.json), using isolated data, retained a real lesson-generation failure: both permitted attempts included one question when the lesson contract required none. The prompt contained conflicting count fields. Indexing, the quiz, the assignment, the unsupported-objective refusal and all ten review-workflow checks passed; ten provider attempts were recorded. Prompt version `education-v2` resolves the count conflict and passed regression tests and the final full run above. The failed evidence is preserved.

This integration session used 21 real provider attempts: two minimal checks, ten attempts in the first full run and nine in the final run. Call caps are counted separately for each database. DeepSeek did not return cost fields, so no total monetary cost is claimed. These runs demonstrate a small functional prototype; they are not a model-quality benchmark.

## Difficulty-control revision

The brief's requirement for precise control over difficulty levels does not prescribe a mandatory mixture. Uniform mode assigns every item the selected level, including all hard. Custom mode sets exact integer counts for easy, medium and hard, permits zero in any category, and requires their sum to equal the requested total of 1–10. Lessons use explanation depth only. The learner profile defaults to undergraduate students who have studied the selected course materials and is shared by generation and review.

`education-v3` records an ordered item plan, learner profile and `difficulty-rubric-v1`. Each generated item must match its slot and target label and include a cognitive process, course concepts and concise marking points. The rubric's process categories and marking-point counts are operational authoring constraints, not a calibrated measurement of student difficulty.

After structural validation, a separate text-model request reviews the questions, options, answers, explanations and source passages without the author targets, generated labels, design fields or difficulty rationales. Both requests currently use the same `deepseek-flash` model in separate contexts; shared model biases remain possible. A mismatch, low confidence, insufficient support for answering or ambiguity permits at most one regeneration and another review. This shares the single repair allowance with structural failures. A second failure creates no successful material. Transport, upstream HTTP and malformed review responses are not automatically retried.

The check is a model-assisted screening step and still needs teacher confirmation. Editing creates a new version that needs review; old or edited content is not given an unsupported verification status. Teacher item ratings record easy, medium, hard or uncertain separately from model judgments and targets, with a dedicated CSV at `GET /api/difficulty/evaluations/export`. Agreement excludes uncertain judgments and items without a recorded target, and retains the relevant counts; no comparable items means no rate. This is target-versus-teacher agreement, not student accuracy. Because the ordinary teacher detail view can show targets, its ratings are not automatically blind ratings.

The [new real-provider acceptance](evidence/difficulty-20260912T042551358609Z/results.json) indexed 14 chunks of the self-authored source in isolated data, then generated an all-hard three-item case and a mixed case with one item per level. Both final drafts matched their requested distributions and passed model review; `technical_checks_passed=true`. This run used nine API attempts: one for indexing, five for the all-hard case and three for the mixed case.

The first all-hard draft's `q1` and `q3` were classified as medium by the reviewer. The application rejected that draft, regenerated once, and reviewed the replacement successfully; see the preserved [all-hard job evidence](evidence/difficulty-20260912T042551358609Z/all_hard-job-evidence.json). The [mixed case](evidence/difficulty-20260912T042551358609Z/mixed-job-evidence.json) passed on its first attempt. The [Python test report](evidence/difficulty-tests-20260912.xml) records 106 passes with no failures, errors or skips; the three `frontend*.test.mjs` files have 33 passing tests.

Isolated mock-browser checks covered `0/0/5` all-hard allocation; changing the total to six and blocking submission with one item unallocated; independent lesson depth while preserving the quiz distribution; `1/2/2` generation with item details and `model_checked` status; rejecting incomplete teacher ratings; and saving all-uncertain ratings explicitly marked as an isolated test. These browser responses and ratings are software fixtures, not real teacher observations or live-model quality evidence.

`manual_quality_verified` and `student_difficulty_calibrated` remain false. These observations demonstrate the allocation, model-review and repair paths on two examples, not verified teacher judgments or calibrated learner difficulty. This run's nine calls are separate from both the historical nine-call `education-v2` run and the prospective eleven-call standard smoke sequence below. See the [development record](../Development_Status.md) for the latest verified outcomes. The older manuscript and Word/PDF snapshots remain unchanged.

## Prepare a live run

1. Read the root README and copy `.env.example` to the local `.env` if needed, then add the text and embedding keys locally. The sample already specifies the CA1 endpoints and models. Do not put keys in the report. Speech and image are not required for this CA1 run.
2. Confirm the uploaded source is permitted for the provider. Use the self-authored demonstration file for the first smoke run.
3. Run the preflight without model calls:

```sh
.venv/bin/python scripts/ca1_smoke.py
```

Exit code 2 means configuration is missing; it is not a model failure. Configuration present also does not prove connectivity. The latest preflight is written to `evidence/api-preflight.json`; its result is separate from the saved real-provider evidence.

4. Explicitly start real calls when ready:

```sh
.venv/bin/python scripts/ca1_smoke.py --live
```

This uses the actual application and its real API adapters through an in-process local HTTP boundary. It creates a demonstration course, indexes the self-authored `sample_data/ca1_rag_course.md`, and requests an English lesson, quiz, assignment and deliberately unsupported objective. The current sample produces 14 chunks, allowing retrieval to select and rank a subset instead of returning the entire source. The unsupported objective is expected to end with `insufficient_evidence` and create no material.

With `education-v3`, the nominal sequence for this 14-chunk sample is eleven provider attempts: one embedding batch for the index, one query embedding and one generation call for each of the four objectives, and one additional review call for each supported quiz and assignment. The permitted repair path can reach seventeen attempts: each assessment may need regeneration and another review, while each lesson can need one structural repair. This is a prospective call budget, not an observed result. The historical `education-v2` run above actually used nine attempts. Provider failures stop the affected task; actual usage is saved in the evidence. Review calls and failed attempts count toward the configured daily cap and add latency and potential monetary cost.

By default, the run uses an isolated database under `evidence/tmp/runtime/<run_id>/` and writes reviewable output under `evidence/live-<run_id>/`. Use `--output-dir PATH` to choose another evidence root. Only `--use-app-data` selects the application's daily-use database and leaves the demonstration course there. Because isolated runs have their own call ledger, their daily limit does not aggregate calls from other databases or provider activity.

5. To also exercise editing, version approval and the learning view in the same run:

```sh
.venv/bin/python scripts/ca1_smoke.py --live --exercise-review-flow
```

This option adds no model calls beyond those of its live run. It preserves the quiz's original draft, edits a second version, checks rejection of a stale approval, approves the current version, checks default answer hiding and explicit answer reveal, then saves a new draft to remove the temporary approval. The saved approval is a technical workflow demonstration, not a human quality judgment. Running this command after an earlier live run starts a new run and repeats its provider calls.

6. Inspect `results.json`, the copied source and chunks, each job's evidence, and the three successful materials' initial drafts and Markdown exports. With the expected refusal, `all_tasks_succeeded` is correctly false. Use `all_expected_outcomes_observed` and `technical_checks_passed` to assess the run. `manual_quality_verified` remains false until a separate human review is documented. The script leaves all materials as drafts and never supplies reviewer ratings.

## A short supervisor demonstration

- Explain the source-to-question architecture and the boundary between source-ID validation and factual support.
- Open the local application and create a course. Import the self-authored `sample_data/ca1_rag_course.md` or permitted material with multiple distinct sections. The older `intro_to_rag.md` is a one-chunk import example and cannot demonstrate meaningful retrieval ranking.
- Inspect chunks and source pages, then build the index.
- Generate an English explanation and an assessment item for a supported objective. Show retrieved passages, answer and explanation, and the intended difficulty rationale.
- Export the generation evidence. Trace each answer to specific supporting text and state any unsupported part.
- Edit a draft, approve the resulting text version, and open the learning view. Explain that this is a local development view without multi-user authentication.
- Try an objective outside the source. A useful result is an explicit refusal; a fabricated answer is a defect to record, not a case to hide. The current system relies partly on the model for this decision.
- Present failures and remaining work. Reserve full speech and image validation for CA2.

Successful material exports are available at `GET /api/contents/{content_id}/evidence`. For every generation task, including refusal or failure, `GET /api/jobs/{job_id}/evidence` preserves the request, retrieved sources, completed attempts and sanitised call records. Source identifiers and structural checks do not prove factual support. Inspect the actual source passages and answers.

Each call records its outcome, elapsed time, HTTP status and allowlisted usage fields, including token counts and provider-returned cost when present. Missing cost is unknown, not zero. Transport, upstream HTTP and malformed review responses are not automatically retried. A completed generation response that fails structure checks, or an otherwise valid review that rejects the item, shares at most one regeneration allowance; a valid regenerated assessment is reviewed again. All these attempts count toward the daily call cap.

## Record each case

Use `Manual_Review_Form.csv`. Preserve the generated draft before editing and retain the corrected version separately. Record actual reviewer identity locally when a reviewer participates; no reviewer or rating is pre-filled.

A case is usable only after all material factual claims and the answer have support, the question is answerable, the answer is defensible, and its intended cognitive demand is reasonable for the stated audience. Ask the supervisor to agree the final acceptance depth.

Before submission, ensure the report’s status paragraph matches the saved live evidence, code version and actual reviewer observations. Passing the fixture suite cannot close the live-prototype requirement.
