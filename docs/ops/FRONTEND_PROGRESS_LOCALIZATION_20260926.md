# Frontend progress and control-language update

Date: 2026-09-26

| Before | After | Why |
| --- | --- | --- |
| Native validation messages were localized only after submission or a previous validation error. | First pointer entry, keyboard focus, edits and language changes prepare messages in the selected language. | Browsers can expose these messages as hover hints before form submission. |
| Generation views showed activity, steps and question counts without an overall bar. | Both layouts show a persistent bar above the stage list/workbench, with the number of completed steps. | Users can follow confirmed progress without replacing the existing animations or controls. |

## Progress semantics

- Declared backend stages have equal visual weight. The accepted question count subdivides the writing stage; started question numbers and failed repair attempts do not advance it.
- The bar represents workflow completion, not elapsed-time completion or an estimate of time remaining. Time-only snapshots leave it unchanged.
- Only a saved, successful job reaches 100. An interrupted task retains its last recorded stage/question progress. Temporary connection failures preserve the last snapshot.
- Historical jobs without stage telemetry remain indeterminate. Audio, image, video and future stages are included only if the backend actually declares them.
- A resumed job may reopen a stage; the display follows that backend state, so monotonic progress across retries is not guaranteed.
- Updates change the existing fill transform. The transition lasts 280 ms and is removed for reduced motion; forced-color and increased-contrast styles are provided.

## Localization boundaries

Application-owned titles already had translation mappings. This change covers native form validation before submission and preserves selected files, entered values, and application-owned custom validation. Authored course/document titles are unchanged. The operating system file dialog still follows system settings.

## Validation

- `node --test tests/frontend_*.test.mjs`: 251 passed, 0 failed.
- Changed JavaScript syntax checks and `git diff --check`: passed.
- Browser QA used `scripts.citation_progress_fixture_server:create_fixture` on loopback port 8775 with a temporary database and no real model calls.
- Detailed and simple views, English and Chinese, light and dark styles, failure and success were exercised. An eight-stage simulated job advanced from 41 to 45 when accepted questions changed from 1/3 to 2/3; a duration-only update kept 45. Failure retained 45; success reached 100 and exposed the result action. These are UI fixture values, not provider performance measurements.
- At a 390 px viewport the detailed view had no page-width overflow (body width 390 px); the bar remained inside the viewport. Browser console errors: none on the tested pages.
- In the actual generation form served by the fixture, an empty objective exposed `Please fill out this field.` before submission. Typing a valid objective cleared the message. Switching language preserved the typed objective. Keyboard clearing followed by switching to Chinese yielded `请填写此字段。`.
- Unit coverage includes indeterminate legacy jobs, media stages, terminal states, reconnection, in-place updates, validation reset, disabled controls, and preserving external custom errors. OS reduced-motion behavior is covered by CSS and existing motion tests; the browser visual pass used the current non-reduced-motion setting.

The fixture's new **Check a question** control makes within-stage progress reproducible without external requests.
