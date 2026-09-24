# Task controls and question revision — interface verification

Date: 2026-09-22. Scope: frontend changes for stopping tasks, reading preserved questions, and revising one question. All screenshots use an isolated temporary database and synthetic task responses. They are not evidence of live model generation, answer quality, or actual backend cancellation.

## Interface changes

| Before | After | Why |
| --- | --- | --- |
| No control over a running task | “Stop task” waits for a safe stop; requested stop is visibly disabled | Set a clear expectation without promising to interrupt/refund a provider request already in flight |
| Preserved question checkpoints are not readable | Separate read-only partial page, with completed/total count and an incomplete label | Make completed work useful without presenting it as an approved complete result |
| Only whole-content manual editing | “Revise question” on each question; choose rewrite or explanation only, add instructions, optionally choose difficulty | Change one unsatisfactory question without recreating the rest |
| New text is difficult to compare | Collapsed previous/current comparison containing only changed fields | Keep the page minimal; answer/explanation differences remain in a second collapsed disclosure |

Native dialogs, existing surfaces and controls are reused. Inputs remain keyboard-operable, focus returns to the triggering question on Escape, and no new animation is introduced. The explanation-only option hides and omits difficulty. Question identity uses its stable slot ID, with `q{index + 1}` for historical records.

## Automated verification

- `node --test tests/frontend_*.test.mjs`: **233 passed, 0 failed** (see `frontend-tests.txt`).
- Added coverage for safe cancel visibility, pending cancel disablement, cancelled terminal polling, resumed/partial actions, revision results, read-only rendering, changed-fields-only comparisons, escaped authored text, explanation-only payloads, retained idempotency keys, duplicate submissions, invalid instructions and stale route/session replies.
- JavaScript syntax checks and `git diff --check` passed.

## Browser verification

Isolated server: `scripts/task_revision_fixture_server.py` on temporary port 8773.

Verified through actual UI actions:

1. Stop the synthetic running task: stopping copy and disabled stop control, then terminal stopped state with one of two questions retained and a continue action.
2. Open the partial page: one question, original question number, collapsed answer and sources, clear 1/2 incomplete label, no approve/export/edit controls.
3. Open a question revision: switch explanation-only/rewrite, retain entered instructions, submit to the existing progress page, open version 2.
4. New version has draft status, no inherited media controls, and only changed stem/explanation in the comparison. Answer differences remain collapsed.
5. Chinese/English, light/dark, desktop and 390 × 844 layouts. No horizontal overflow at 390 px (`scrollWidth == innerWidth == 390`). Escape closes the dialog and returns focus to its trigger.
6. No browser warnings or errors were logged.

`fixture-audit.json` records **zero provider calls**, one synthetic stop request and one synthetic rewrite request. The fixture synthesizes stopped/succeeded states; backend reliability and revision correctness require their separate tests.

Screenshots:

- `stopped-zh.png`
- `partial-zh.png`
- `revision-dialog-zh.png`
- `comparison-en.png`
- `comparison-mobile-en.png`
- `revision-mobile-en.png`
- `revision-mobile-dark-en.png`

The fixture tab was closed and the temporary viewport override reset. No production data or main server state was changed by these checks.

## Integration follow-up

After backend integration, instruction validation now requires 2–2000 characters, comparison panels require an exact matching revision version, and new revision/task-capacity/source-scope errors have English translations. Later manual saves no longer display an earlier AI revision as the current change. Manual text saves and text/media approval responses are ignored by the visible page after navigation; the server-side action still applies to its original version. The existing revision form already ignores replies after route/session changes. These behavioral changes added three tests and required no layout changes or repeated browser run.
