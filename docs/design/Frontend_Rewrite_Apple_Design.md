# Frontend rewrite — Apple Design

Completed: 2026-09-11

This is a replacement of the frontend, rather than another stylesheet overlay. The active frontend consists of a new `index.html`, one new `style.css`, and a new ES-module `app.js`. The old `workspace.css` was removed. Prior source is retained in the timestamped `frontend-before-rewrite-*.zip` archive in this directory. Existing locally served Lucide icons and their license were retained.

## Design and architecture

- A course-aware sidebar, translucent toolbar, content canvas and responsive mobile navigation replace the previous shell.
- The overview prioritizes the current course, creation shortcuts, recent materials and preparation steps.
- The library supports filename search, status filters, a native import dialog and a source-reading dialog.
- The writing interface groups content type, learning goal and output settings, with source context nearby. Question settings are omitted for lessons. Drafts are held in memory per course for the current page session.
- The content library supports title search and review-status filters. Review uses a document surface with contextual sources, media actions and version-bound evaluation.
- Editing preserves citation identifiers, saves a new version, and returns to review. Approval, media generation/approval and exports remain connected to their existing endpoints.
- The separate learning view renders approved content. Answers are fetched only after the learner requests them.
- Hash navigation supports browser history. A render revision prevents late page requests from replacing a more recent route. API errors are escaped and displayed inline for forms; submitted controls are restored after errors.
- Native dialogs, semantic navigation, focus-visible rings, a working skip link, text-size-aware units, and reduced-motion/transparency/contrast rules are part of the new foundation. Occasional dialog motion is limited to subtle scale and opacity; navigation has no decorative transition.

## Verification

The browser session exercised the production UI with its existing course and a separate local QA server backed only by deterministic mock providers. The fixture server is reproducible via `scripts/ui_fixture_server.py`; it creates a new temporary data directory on each run and never opens production data.

Verified with browser interactions:

1. New course creation and switching back to the original isolated course.
2. Real local sample-file import into the isolated course, parsing, status filtering, filename search, source reading and index submission.
3. Lesson/quiz switching, question settings visibility, count changes, and preservation of a learning goal and settings across navigation.
4. Mock-provider generation submission and navigation from the completed job to its material.
5. Material editing, version increment, text approval and version-bound evaluation submission.
6. Learning page initially without answers; explicit reveal followed by an answer/analysis expansion.
7. Production unconfigured-provider error shown inline and the submit control restored.
8. Desktop overview, compose and populated review screens; mobile compose, library and learning screens. Mobile compose/library document widths equal the 390px viewport.
9. No console errors observed in the isolated QA tab.

JavaScript syntax check passed. Existing automated integration suite: **9 passed**, with two existing dependency deprecation warnings. These tests use mock providers and do not establish real model quality, media playback quality or live-provider connectivity. Media controls and endpoint wiring were rewritten; actual generated audio/image playback was not included in the browser test. Reduced-transparency/high-contrast rules were implemented but not browser-emulated.

The isolated QA tabs and server were closed after verification. The production local preview remains on port 8765.
