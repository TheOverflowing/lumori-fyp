# Difficulty prompt experiments — protocol v1

Protocol established on 2026-09-19 before D1 results. This folder is a research archive, separate from production accounts, sources, generated content and application prompt policy.

## Questions and evidence boundary

- Which prompt additions improve agreement with a fixed external AI judge, while retaining correct, grounded, answerable and unambiguous questions?
- How do results vary by target level and output language? What is the cost of each qualified output?
- Does a later feedback or candidate-selection workflow improve outcomes at comparable inference budgets?

D1 is a **development screening**, not a final held-out study. It has no teacher gold labels or student responses. Its fixed contexts are curated teaching fixtures with explicit provenance, not claimed verbatim course excerpts or human-annotated difficulty labels. No automatic update to the production prompt is permitted on the strength of this pilot alone.

## Dataset and controls

`benchmarks/difficulty/cases.json` contains topic-grouped development and held-out cases. Chinese/English and all difficulty variants of one topic stay in the same split. D1 uses only six `pilot=true` development cases: three topics, two languages, one selected target per topic. **Target difficulty and topic/type are confounded in this small screening**; per-level counts are descriptive, not isolated difficulty effects.

Each strategy gets the same learning objective, learner background, question type, language, citation IDs and source text for each case. Retrieval is frozen; no embedding or reranking calls are made. Each call requests one question with the existing LearningAsset contract. The original complete response, including explanation, is retained. No generated question or observed score becomes a few-shot example in another D1 strategy.

The initial six conditions are all single generation calls:

| ID | Intervention | Interpretation |
| --- | --- | --- |
| baseline | Current education-v3 authoring system/schema/rubric | Frozen-context single-question baseline; not the whole production RAG/check/repair pipeline |
| rubric_axes | Knowledge integration, transfer, scaffolding and constraints | Project-designed decomposition, not a validated psychometric scale |
| backward_design | Public answer/marking criteria constrain the task | Single-call adaptation of answer-first planning; not full two-stage PFQS |
| contrastive | Three-level contrasts with illustrative examples | AI-authored examples, no human calibration; not CrossQG cross-filtering |
| scaffold_control | Vary supplied method/hints and required strategy selection | Keep necessary facts complete; do not create difficulty with ambiguity or missing information |
| verify_before_emit | Check answer, uniqueness and level before final output | Same-call self-check; not independent verification or iterative Self-Refine |

The generator remains the configured DeepSeek `deepseek-flash`. Generation temperature is 0.6, maximum output 4096 tokens, and other existing model parameters are preserved and recorded. Run order is shuffled with a recorded seed. One sample per condition is enough only for engineering screening; subsequent validation needs repeated generations and more independent topics.

## External judge

The external judge uses `qwen/qwen3-235b-a22b-2507` through the existing OpenRouter connection, temperature 0 and maximum output 2048 tokens. This choice separates model families and keeps the first experiment small; it does not establish that Qwen is a validated difficulty assessor. Model ID, endpoint signature, response model and usage are archived.

A fixed judge prompt receives learner background, the complete operational rubric, original source text, stem/options, answer and explanation. It does **not** receive target level, strategy, case ID, topic instruction, author difficulty label/reason/design, generated lesson sections, other judges' scores or prior attempts. A separate program compares the returned difficulty with the target only after assessment. The judge may abstain with `uncertain` and reports confidence. Questions are treated as data, not grading instructions.

Judge output fields: `assessed_difficulty`, `correctness`, `grounded`, `answerable`, `ambiguity_free`, `confidence`, and a short `rationale`. Strict schema/boolean checks reject malformed output. No hidden reasoning is requested or archived. An independent-model judgement is still AI evidence, not human review or real student calibration.

## Metrics fixed before the run

- Requested slots: all pre-scheduled case × strategy × repeat combinations.
- Structural validity: existing schema, citation, count, type and target-plan validation.
- Difficulty agreement: external judge's level equals requested level, divided by requested slots.
- **Qualified rate:** structurally valid output AND matched difficulty AND all four quality flags true AND confidence not low, divided by requested slots.
- Unknown/failed/ungraded requests remain in denominators. Judge uncertainty and low confidence are separately counted. Empty level groups are null, never 0% or 100%.
- Record confusion matrix, language and level breakdowns, paired wins/losses/ties versus baseline, call attempts, token usage, duration, and reported cost.
- Report missing cost separately; do not treat missing cost as zero. D1 paired deltas are descriptive. With three source topics, do not claim significant improvements or a strongest method.

Quality flags and difficulty agreement depend on the judge. Add familiar-course human blind ratings and judge agreement analysis before strong pedagogical claims. Later student responses are needed for empirical difficulty calibration.

## Execution and reproducibility

Dry run: `.venv/bin/python scripts/difficulty_experiment.py`

D1 live screening: `.venv/bin/python scripts/difficulty_experiment.py --live --selection pilot --max-calls 80 --concurrency 2`

Expected maximum: 6 strategies × 6 cases × (1 generation + 1 judge) = 72 calls. A generation/assessment canary precedes the remaining schedule. Authentication, balance, permission, missing-model and rate-limit failures halt queued calls. No network, malformed-output or quality retries occur in D1. Generation failures are retained, with no judge call when no valid question exists. Maximum concurrency is two for this run.

Each new run gets a unique output directory, source/code hashes, fixed selected contexts, manifests, full prompts and responses, a shuffled schedule, per-slot results and sanitized provider call logs. API credentials are read in memory and never saved in evidence. The runner opens only its own new SQLite ledger, not the application database. Archived results are never overwritten by subsequent runs.

Offline summary replay: `.venv/bin/python scripts/difficulty_experiment.py --replay <run-directory>`

Replay recomputes aggregates without provider calls; it is not a new experiment or a new independent judgement. These are API experiments: snapshots support inspection and metric replay but do not guarantee bit-identical model reruns.

## Subsequent experiments, not part of D1

1. Inspect development errors and verify a sample of judge decisions. Fix data/implementation defects as separately versioned runs; retain original failures.
2. More topics, repeated runs, both question types at each target, multilingual balance. Keep the topic-held-out set untouched during prompt search.
3. Two-stage answer planning, explicit task-structure planning, targeted feedback rewriting, and multi-candidate selection. Compare against equivalent call/token budgets and retain both initial and final questions.
4. Bounded offline prompt optimization inspired by GEPA/ProTeGi/MIPRO/OPRO. Separate search-training, selection-validation, and final test topics; freeze the final judge. Preserve candidate prompts, parent versions, feedback, evaluation budgets and rejected candidates. D1 does not run these optimizers.
5. Confirm selected variants on the untouched test topics, with independent human calibration and uncertainty intervals clustered by source/topic. No guarantee that a complex prompt will outperform baseline.

Research references, publication status and method-specific boundaries are collected in `LITERATURE_REVIEW_20260919.md`.

## Post-run implementation note — 2026-09-19

The completed D1 run used `difficulty-experiment-v1`; its archived code and original scores remain unchanged. Following the observed whole-asset format failures, v2 explicitly expresses the existing sufficient-evidence/sections/questions contract identically for all six strategies. The command above now uses v2. A one-case engineering smoke run is not a repeat of the six-case D1 study. A separately archived, post-hoc question-only diagnosis reused the unchanged blind judge; it is not the preregistered whole-asset metric. See `D1_RECORD_20260919.md` for distinct results, costs, missing evidence and the independently computed judge false positive.
