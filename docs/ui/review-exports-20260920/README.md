# Content ratings and export QA — 2026-09-20

This is an implementation/verification record, not a RAG experiment or a human quality assessment. Test ratings and audio are synthetic. The ordinary 8765 workspace was inspected read-only and restarted after verifying zero active jobs and saving a SQLite backup; its material content and ratings were not changed by these tests.

## Before / After / Why

| Before | After | Why |
|---|---|---|
| Rating form always expanded and blank after reopening | Default-collapsed rating, version status, saved score/note/question prefill, editable current record | Reduce repeated work and avoid counting edits as independent observations |
| Markdown-only document download | One Export dialog with PDF, Word and Markdown; optional answers for question material | Keep the review page minimal while making the requested export explicit |
| No dedicated media attachment action | Download beside stored audio/images; shared endpoint and video rendering extension | Support current media and future video without claiming video generation exists |
| Closing export could still trigger a late attachment | Modal cancellation aborts the request and suppresses late response downloads | Respect cancellation |
| Media downloaded through a full JavaScript Blob | Native browser attachment download for persisted media | Preserve browser transfer controls for long audio/video |

## Automated checks

- **173 frontend tests passed**: all `tests/frontend_*.test.mjs`, including citation/progress regression checks, per-version rating, save failure/disposal, input language preservation, export options, binary account isolation, cancellation and transfer errors. See [frontend-tests.txt](frontend-tests.txt).
- **131 backend tests passed**, with two pre-existing Starlette deprecation warnings: evaluation persistence, portable exporters, download routes, account isolation, workflow and library. See [backend-tests.txt](backend-tests.txt).
- Python dependency consistency and JavaScript syntax checks passed; `git diff --check` passed.
- The export tests include actual PDF/DOCX parsing, source numbering, hidden answers, embedded fonts, filename safety, JSON/dictionary inputs, unchanged original assets, version conflicts, account isolation and media path containment. A video fixture proves the generic attachment route; it is not a generated video.

## Browser checks

Use `.venv/bin/python -m scripts.review_export_fixture_server` for an isolated fixture on port 8769. It wraps the earlier citation fixture, seeds a bilingual two-question quiz and a 100 ms silent WAV, and does not call any provider. The fixture account and routes are documented in its source. Stop the test server after use.

Verified through the UI:

1. Fresh rating is collapsed and unrated; saving collapses it with Rated · Version 1.
2. Reload restores all three scores, the note and q1/q2 difficulty judgments.
3. Updating a score retains exactly one evaluation and one current pointer, with one prior snapshot in history; provider calls remain zero. See [rating-browser-state.json](rating-browser-state.json).
4. English/Chinese labels and dark/light appearance preserve entered/authored text.
5. At 390 × 844 the page has no horizontal overflow and the export dialog stacks its format choices. Rating and export controls remain usable.
6. PDF with answers unchecked was actually saved by the in-app browser. Its parsed text contains Chinese and excludes the answer section. The synthetic WAV was also saved and parsed as 100 ms.
7. The initial small Word file saved through the browser. After embedding the complete fonts, the latest Word request returned successfully and closed the dialog without UI errors, but its larger file did **not** appear in Downloads during verification. Native attachment navigation returned `net::ERR_BLOCKED_BY_CLIENT` in the in-app browser. Final DOCX bytes and rendering are verified separately; final in-app-browser Word delivery is **not counted as passed**, and no browser restriction was disabled. See [browser-downloads.json](browser-downloads.json).
8. Browser console showed no JavaScript errors. The actual 8765 material reload displayed its existing saved Version 1 rating and the new Export action.

## Visual evidence

- [Desktop export dialog, light](export-dialog-light.png)
- [Phone export dialog, light](export-mobile-light.png)
- [Phone rating expanded, dark](rating-mobile-dark.png)
- [Phone rating collapsed, dark](rating-collapsed-mobile-dark.png)

All eight pages across five final PDF/DOCX samples were rendered and visually inspected. [Document QA, file sizes and limitations](documents/QA.md) records the results; checksums and page counts are in [manifest.json](documents/manifest.json). Document samples and rendering evidence are in `documents/`. The `final-*` directories are authoritative; earlier `render-*` directories document discarded iterations. Review found missing Chinese glyphs in viewer-dependent fonts and an inherited Word title border. The final exporter embeds licensed fonts, removes the title border, preserves Chinese/math text and starts the answer key on a fresh page. Document render evidence is separate from browser download success.

## Deployment and extension contract

See [CONTENT_EXPORTS.md](../../CONTENT_EXPORTS.md) for routes and persistence semantics, and [font provenance and licensing](../../../app/fonts/README.md) for the portable assets. Keep all font/license files under `app/fonts` when copying the core application. Exporting does not require an external model, a running office application or a Codex runtime.
