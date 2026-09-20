# Difficulty, retry and review toolbar polish

Date: 2026-09-20. This record describes implemented behavior and deterministic regression checks. Browser screenshots and visual observations are recorded separately by the main task.

| Before | After | Why |
| --- | --- | --- |
| Export was a button beside two bare blue links. | Status and version form one group; Export and the approved learning view use matching controls. Evidence download sits under “More exports” in the export dialog. | Keep common actions consistent and secondary information available without crowding the toolbar. |
| A stopped generation could send the user back to an empty creation form. | Failed, insufficient-evidence and cancelled text-generation tasks offer “Edit request.” Resumable failures also retain the separate “Continue generation” action. | Let the user change the original inputs without confusing a new request with continuation of existing work. |
| A retained result could conceal a difference between the requested difficulty and the model’s assessment. | `model_adjusted` displays the requested level and assessed level separately, with a compact disclosure explaining the difference. | Preserve the authoring target and report the actual judgment without implying exact matching. |

## Difficulty policy and evidence boundary

The current `difficulty-calibration-v1` policy specifies three strict rounds before considering an eligible retained candidate. The policy ranks eligible candidates by distance from the requested level, then its remaining confidence and attempt criteria. It records the requested and assessed levels separately. Answer correctness, source support and other applicable quality gates are not relaxed merely to retain a result. The policy’s `correctness_relaxed` field remains false.

The UI labels this case “已保留结果，难度有偏差” / “Result retained with a difficulty difference.” The “Calibration details” disclosure states that the result did not strictly match the requested difficulty and still needs review. Individual questions only receive the extra inline assessed-level label when that level differs from the requested level. Slot identifiers bind assessments to their actual questions; position alone does not choose the assessment.

Saving a new content version invalidates the prior current-assessment claim. Both strict and adjusted prior assessments show the new-version review requirement. The server marks an edited version `needs_review`; question rendering does not display old model judgments as current when given that status.

These are operational generation and presentation rules. Synthetic judgments in tests verify state handling, labels and contracts. They do not measure model efficacy, genuine difficulty calibration, teacher agreement, learner correctness or learning gains.

## Restoring a request

`GET /api/jobs/{jid}/generation-request` checks ownership before returning an allowlisted creation request. It reconstructs the saved clarification context without another provider call. The frontend restores the resolved topic, material type, content language, question type/count, learner profile, selected document identifiers and difficulty allocation.

The restore helper creates independent editable data and does not use browser storage. Explicit learner-profile text remains authored text, including after an interface-language change. If a legacy request has no profile, the regular creation form supplies its localized default. Invalid historical allocations remain visible for correction rather than silently being redistributed.

The main page restores the fusion and automatic-exploration switches, then removes those flags from the form draft so later settings edits remain authoritative. It generates a new request key on submission and does not reuse preparation identifiers or consumed clarification tokens. “Continue generation” remains a distinct operation that resumes eligible saved work.

## Toolbar and export interaction

The review bar groups status/version separately from the action controls. The approved learning-view link and Export button share the same 44 px minimum height and secondary appearance. On phones the actions use a shared row, and their heights remain equal if a label wraps. Existing theme colors and reduced-motion behavior are retained.

The native “More exports” disclosure contains the evidence attachment link. PDF, Word and Markdown choices remain in the export dialog. Question material retains the explicit option to include answers and explanations. Document transfers support cancellation; persisted media downloads use native browser attachments so the browser controls transfer progress and large-file handling.

## Regression checks

The focused frontend checks cover:

- Requested/assessed labels in Chinese and English; question-slot matching; no duplicate inline difference label when the levels match; edited-version invalidation.
- Restore actions for failed, insufficient-evidence and cancelled generation tasks in both simple and detailed progress modes; no restore action for running/successful generation or media tasks; both choices for resumable generation failures.
- A live transition into failure, escaped task identifiers, localized recovery copy and absence of a fabricated result action.
- Form restoration, exact difficulty allocation, removal of execution-only fields, toolbar approval gating and evidence-link placement.

Reproduce with:

```sh
node --test tests/frontend_difficulty.test.mjs tests/frontend_generation_progress.test.mjs tests/frontend_generation_retry.test.mjs tests/frontend_content_review.test.mjs
```

Recorded result: **80 tests passed, 0 failed** on 2026-09-20, including nine newly added difficulty/progress regression cases in this pass.

No live provider or learner experiment is part of this frontend check. The tests use synthetic content and task states; they must not be cited as measured improvements in generation quality.
