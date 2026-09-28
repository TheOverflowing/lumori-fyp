# Difficulty review v2: frozen diagnostic set

**2026-09-26 status:** The original files remain frozen. Live review found an arithmetic error in the courier reference; see [the erratum](ERRATA_20260926.md) and the separate, post-observation corrected development case. The four `heldout` cases have now been evaluated with v2.3 / Pro low; they are consumed and subsequent uses are development regressions, not fresh heldout validation.

This set contains eight original, self-contained tasks written with invented course rules. It is an **AI-authored development diagnostic, not a teacher gold standard, an empirical measure of learner difficulty, or a release qualification on its own**. Expected labels were fixed before any model calls. No model calls were made while authoring the set.

`cases.json` has a `cases` array: four `development` cases and four `heldout` cases. Each case includes all material visible to the learner, the supplied reference to audit, exact supporting source text, and a separately stored development expectation. A judge must never receive `expected`, `label_provenance`, case ID, split, or README commentary as grading evidence. Preserve the learner profile in difficulty grading. Include the reference answer and source text only in content verification, not in the first independent solution/difficulty pass.

## What the cases test

| Split | Case | Expected diagnostic behavior |
|---|---|---|
| Development | `dispatch_scaffold` | Easy: the complete eligibility, priority calculation, and decision are provided to the learner. |
| Development | `dispatch_independent` | Medium: independently combine eligibility filtering with priority computation and ranking. |
| Development | `courier_single_failure` | Hard: construct robust routes and prove a cost bound without a supplied robustness method. |
| Development | `notice_boundary_ambiguous` | Invalid question: two permitted answers at the boundary, despite a demand for a unique answer. |
| Heldout | `stack_repair` | Medium: trace state, locate the order error, and select the one legal local repair. |
| Heldout | `laboratory_slots` | Hard: coordinate precedence and shared equipment, then prove the minimum. |
| Heldout | `marking_wrong_option` | Eligible and easy, but fail content verification: the supplied reference option is wrong. |
| Heldout | `beacon_contradiction` | Invalid question: no slot satisfies both supplied timing rules. |

The two dispatch cases are a minimal pair: the same rules, inputs, learner profile and requested answer, with a full worked solution added only to the scaffold case. The medium expectation concerns remaining independent work, not question length. The hard expectations depend on the specified novice foundations and the need to choose a method and justify necessity. Reasonable teachers may adjust these labels; retain their disagreement rather than silently changing the frozen expectations.

Heldout families are stack state repair, scheduling with resources, marking arithmetic, and contradictory timing. They do not reuse development dispatch, robust routing, or boundary tie rules. This is a small process holdout authored by the same AI, not an independently sampled statistical test. Once its results influence a revision, mark it consumed and obtain new untouched families for the next release evaluation. Do not call repeated tests on this file fresh heldout validation.

For invalid questions, `candidates` is empty: an impossible or underdetermined task does not acquire a difficulty label merely because a solver can explain its defect. A wrong reference to an otherwise answerable question has `eligibility=eligible` and `content_status=fail`. These fields deliberately test that answer correctness and difficulty are independent decisions. `uncertain` is a valid content status for later real cases; these invented cases have sufficient evidence to expect pass or fail.

## Freeze and audit

`manifest.json` stores the SHA-256 of the exact dataset and split IDs. Keep this file immutable after the first provider call; any edit requires a new dataset version and a new manifest. Every run must save dataset hash, prompt/code versions, model settings, raw outputs, stage validations, task budget, timing, token usage and any returned monetary cost. Missing cost is unknown, not zero. Preserve every failed or incomplete attempt.

## Fixed release criteria

The following criteria are fixed before running this set. They define separate milestones, not interchangeable evidence.

**Technical readiness for observing real tasks:** defaults stay off; enablement is explicit; host code controls permissions and call/token limits; timeout and provider failure cannot change a delivered answer; malformed output, missing evidence, conflicting stages and insufficient budget produce abstention/manual review. Persist an auditable decision with bounded source excerpts and version identifiers. A task failure must not cancel unrelated questions. All corresponding contract and integration tests must pass. These checks establish implementation behavior only.

**AI diagnostic gate:** run a frozen candidate once on development, revise only with development evidence, then run the untouched heldout set with a frozen prompt. For a diagnostic gate pass, every invalid-question or wrong-reference case must be blocked from automatic acceptance; valid content must not be flagged as a confirmed error; every output must pass host validation or explicitly abstain. Each valid item must have the expected remaining-work explanation and an expected candidate label; abstention is safe but is not a successful difficulty diagnosis. The scaffold must remove the work it provides and must not rank above its independent pair. Both novel hard tasks must retain their unsupplied method-selection/proof demand. Any failure blocks automatic decisions pending revision. Even eight successes establish only this diagnostic result.

**Readiness for automatic, limited difficulty rework:** collect a separate, frozen set of at least 120 real tasks from the intended course and learner population, from at least six course families, with at least 30 invalid-question/wrong-reference cases and at least 30 valid but difficulty-mismatched cases. Two qualified teachers must independently review all tasks without model labels, target labels, or each other's votes; a third adjudicates disagreement. Keep their original votes and report agreement and confusion matrices. Calibrate on a separate development partition; freeze the candidate and thresholds before seeing the release partition. All automatic actions on the release partition must be justified by adjudicated evidence, with zero observed false automatic rework and zero observed automatic acceptance of a confirmed content fault. Require at least 60 automatically actionable reviewed decisions and a one-sided 95% binomial lower confidence bound of at least 95% for action precision; if sample counts are smaller, report insufficient evidence. The 120-task minimum alone does not guarantee the action-count criterion. Report coverage and abstentions so safety cannot be achieved merely by refusing every case. Teacher labels validate expert judgment; learner success rates and instructional effects require a separate learner study.

Before enabling even a limited cohort, reserve enough task budget for the original generation, an independent review, at most one revision, and a full post-revision review. If that budget cannot be reserved, retain the original result and flag it for review. Any revision must pass content and evidence gates again. Use a reversible cohort flag, audit every changed item, and roll back on the first confirmed wrong automatic action. No result in this eight-case AI diagnostic authorizes changing production settings.
