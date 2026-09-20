# Generation format repair — 2026-09-20

## Incident and diagnosis

The reported job (`5b1fb64f2a894b06b06ba0c48aa36988`) stopped at question 2 after two author attempts. Question 1 had already passed; question 3 had not started. Both author calls returned HTTP 200. This failure was caused by format validation, not a provider outage:

1. A multiple-choice candidate supplied six options and the answer `(B)`. The old validator required exactly four options.
2. The replacement short-answer candidate supplied seven concept labels. The old validator allowed at most six.

Neither candidate reached independent solving or review. The earlier three-round setting applied to difficulty calibration after other quality checks passed; it did not extend ordinary author-contract repair.

## Current behavior

- New Agent tasks allow at least three ordinary attempts per question; a larger configured allowance is respected.
- After ordinary format repair is exhausted, the workflow automatically enters format compatibility. It first tries saved candidates locally, preserving their original responses and recording all transformations. This can avoid another author call.
- Strict author instructions still request four distinct choices. Compatible parsing accepts 2–26 nonempty, distinct choices and checks the answer against the actual option count. Exact wrapped letters such as `(B)` and `[B]`, or lowercase letters, become a bare uppercase key. Ambiguous prose is not guessed into a key.
- Compatibility preserves every supplied option and concept label. It does not truncate six choices to four or delete a seventh concept just to satisfy a template.
- Unresolved format issues continue through compatible repair without a separate fixed fourth/sixth-attempt cutoff. Existing lifetime/daily API budgets and provider availability still apply; this is not an unlimited-call promise.
- Parsed candidates still undergo scope, source, duplication, independent-answer and review checks. A format adjustment does not make an incorrect answer pass. Difficulty fallback still requires an otherwise acceptable candidate.
- Failed content checks remain bounded. Eligible failed tasks offer **Continue refining / 继续修正**, granting another three ordinary attempts to the first unfinished question. Passed questions, the original request, evidence, rejected attempts and cumulative call ledger remain intact. Repeated resume submissions are rejected while work is already running.
- Historical checkpoints retain their frozen configuration. Explicit continuation extends the failed question without rewriting the original evidence or resetting the task budget.
- The legacy pipeline also uses three strict attempts followed by compatible format handling and retains its answerability and difficulty checks.

## Interface verification

| Before | After | Why |
| --- | --- | --- |
| Generic “check failed” event for format and content errors | Separate format, difficulty, source, duplicate and content-check messages | Explain what the system is correcting without exposing raw provider output |
| Failed task offered no continuation for quality rejection | “Questions need refinement” with **Continue refining** and saved-question count | Preserve completed work and avoid repeating the generation form |
| No visible compatibility transition | Format-adapting and format-compatible timeline events | Make automatic recovery visible |

Verified in a separate, offline fixture server with a temporary database: English and Chinese failure states, saved progress, continuation button, completed state, and the **View result** link opening material details. No browser warnings or errors were observed. No fixture generation/resume call was sent to a model. These UI fixtures do not establish live-model answer quality.

- [Chinese progress screenshot](progress-zh.png)
- [English progress screenshot](progress-en.png)
- [Completed-state screenshot](completed-en.png)

## Validation and evidence limits

The final targeted backend regression run passed **593 tests**; frontend tests passed **213 tests**. Two backend dependency deprecation warnings remain. Checks include native and harness generation, legacy generation, interrupted review continuation, manual continuation authorization, account isolation, call budgets, preservation of six options in PDF/Word exports, and preservation of original author responses.

Specific regressions verify that a seventh author output can resolve a format failure, that failed compatible answer reviews do not publish content, and that continuation after earlier compatibility attempts retains the complete history.

- [Backend test output](backend-tests.txt) / [JUnit result](backend-tests.xml)
- [Frontend test output](frontend-tests.txt)
- [Read-only incident replay](incident-replay.json)

The real incident's two saved author outputs both pass compatible structural validation. The six-option candidate retains all six options, and the short-answer candidate retains all seven concepts. Original-response hashes confirm that neither stored response was rewritten. The production database was opened read-only for this replay, and **zero model calls** were made. No independent solver or reviewer was run on these real candidates during this fix, so this is structural recovery evidence, not proof that either answer is correct or that the original task has completed.

The original failed task remains saved with one of three questions completed. The updated progress calculation exposes `resumable: true` and `resume_kind: repair`; continuing it does not require re-entering its generation settings.

## Local rollout

After confirming there were no queued or running jobs, the local service on port 8765 was restarted with the updated backend. Application startup completed successfully and the browser loaded the application and its updated progress assets with HTTP 200 responses. Temporary fixture service and verification tabs were closed.

The currently signed-in browser account differs from the incident job's owner. Its request for that job correctly returned HTTP 404 under account isolation; no ownership or authentication state was changed. Therefore the real-job continuation eligibility above was verified from the saved checkpoint in a read-only check, while the visible continuation flow was verified with the separate fixture. The original job must be opened using its owning account. It was not resumed automatically during verification.
