# Learning Studio — material and proportion refinement

final result: passed

Scope: refine the existing app using the user's apple-design and emil-design-eng instructions. Preserve minimal copy and frosted materials. The original reference supplies material direction; this revision intentionally changes the dashboard's proportions rather than cloning the social feed.

## Findings resolved

| Before | After | Why |
| --- | --- | --- |
| Bright outlined glass shell, heading, section and inner rows stacked together | Unframed canvas and heading, frosted navigation/creation controls, quieter reading panels | Separate material hierarchy and reduce repetitive borders |
| Tall creation buttons with small centered contents | 98px desktop actions, 38px icon tiles and readable horizontal labels | Match container dimensions to actual content |
| Stacked full-width empty panels | Two aligned desktop panels, one column at narrower widths | Make the home composition compact and balanced |
| Long mobile navigation scrolls offscreen | Five visible icon/short-label entries with full accessible names | Keep every destination discoverable |
| Repeated full-width text actions and two new-course buttons | Compact accessible icon controls; home toolbar opens import, course selector retains new-course | Reduce repetition without losing actions |
| Generic hover rule can turn the settings control blue | Explicit settings/plain hover selectors | Keep the material palette coherent |

## Evidence

- Original material source: `/var/folders/zp/0gw373bn7d14c0_n45qm1vdc0000gn/T/codex-clipboard-5a59aeb7-a2f0-4c44-89af-66c14bafbf21.png`, 646 × 1224.
- Initial UI was inspected live at desktop size before editing. The saved `polish-before.jpg` was later found cropped to 765 × 1000; rejected for numerical/full-frame before-after comparison. No pixel-fidelity claim is made from it.
- Final real-course home: `output/ui-review/polish-desktop.jpg`, 1440 × 1000 image and viewport.
- Populated temporary course: `output/ui-review/polish-populated.jpg`, 1280 × 720.
- Creation form: `output/ui-review/polish-compose.jpg`, 1280 × 720.
- Material review: `output/ui-review/polish-review.jpg`, 1280 × 720.
- Mobile populated home: `output/ui-review/polish-mobile.jpg`, 390 × 844.
- Mobile modal: `output/ui-review/polish-mobile-dialog.jpg`, 390 × 844; final saved image explicitly inspected showing the modal.
- Tablet: 820 × 1000 live screenshot inspected; no horizontal overflow.
- All listed accepted JPEG dimensions verified from file metadata. One image pixel per CSS pixel; no image transformations used.

## Visual review

Typography: platform system fonts retained. Desktop controls and status text enlarged, main heading around 32–38px, measured label hierarchy. Mobile inputs use 16px. Short mobile labels retain explicit full accessible names.

Spacing/layout: consistent 22–26px large radii and 10–14px nested controls. Heading and sections align. Home's long test course name, populated rows, empty state and review content inspected. Tablet and mobile layouts remain inside viewport. Focused creation, dialog and review regions were inspected in their dedicated captures.

Color/material: warm neutral canvas, subtle sage backdrop, frosted navigation and action cards with one soft highlight. Reading content stays near opaque. No refraction renderer or native Apple material parity is claimed.

Assets: existing local SVG icon set retained. No decorative bitmap or fake content added. Test course content exists only in the temporary fixture instance.

Copy: taglines/footer remain removed; concise state, input names and errors preserved. Source excerpts remain intact.

## Functional verification

1. Home quiz entry opens creation with quiz selected.
2. Switching to lesson hides question controls; topic input updates character count.
3. In `scripts/ui_fixture_server.py` isolated service, submitting a lesson completes through mocked providers and opens the task list. Opening its details displays the generated material and review controls.
4. Mobile home and review inspected at 390px; document width equals 390. Tablet at 820px also has matching document width.
5. Mobile new-course icon opens modal. Tab focuses the course-name field. Computed dialog transition becomes 0s on keyboard input. Escape dismisses and restores focus to the trigger.
6. Temporary-tab browser error log returned no errors.
7. `node --check app/static/app.js` exits 0.
8. Independent static/visual review found no remaining blocker or P2; minor hover cascade issue corrected before final capture.

## Limits

- Mocked providers verify UI plumbing; no live API/model calls or quality testing.
- Real course data was read only. Temporary testing used a separate data directory.
- Reduced motion, reduced transparency, increased contrast and no-backdrop-filter fallback rules are implemented; OS preference emulation was not exercised. Keyboard no-animation mode was directly checked.
- Existing upload/media/approval backend behavior was not retested exhaustively for these presentation changes.
- Default browser viewport restored for delivery; local service kept available.

## Dark appearance and bilingual interface — 2026-09-12

Result: passed for the new preference controls and the exercised UI flows.

- Added a compact theme/language capsule to the toolbar, including the learning view. Theme follows the OS until explicitly selected; theme and UI language are stored independently. Saved appearance applies before stylesheet paint. Storage restrictions retain working session preferences.
- Dark materials cover navigation, surfaces, input fields, filters, status badges, dialogs, reading content and hover/focus states. Existing light appearance and minimal copy are retained.
- Explicitly marked interface copy is localized in place. Authored course names, documents, generated material and typed input remain unchanged. Generation language stays independent of interface language. Known application errors are translated; unknown provider diagnostics remain as returned.
- Node verification: `node --test tests/frontend_preferences.test.mjs` — 16 passed. Covers system/saved appearance, persistence, storage failure and synchronization, error-message descriptors, plural counts, escaping, locale dates and input preservation. Frontend JavaScript syntax checks passed.
- Isolated browser fixture at port 8766 verified: theme and language switching, persistence after reload, English navigation/forms/review/learning/modal labels, source search and active filter preservation, unsaved topic and quiz selection preservation, edit-title/notes/rating preservation, open source details, and cross-tab language changes while a populated new-course dialog stays open. Mocked generation completed from the English interface with Chinese material language preserved.
- Desktop and 390px mobile layouts were visually inspected; no horizontal overflow in inspected creation/source/learning pages. Dark mobile dialog inspected. The current live course page was reloaded and displayed in dark Chinese appearance; this task made no course-data writes to the live service.
- Final accepted images (file dimensions verified): `output/ui-review/theme-dark-zh-desktop.jpg` and `theme-light-en-desktop.jpg` at 1440 × 1000; `theme-dark-zh-mobile.jpg` at 390 × 844. Images are direct browser captures.
- Limits: no live model calls; browser-native picker/validation language follows browser behavior. OS appearance behavior is unit-tested; reduced transparency/contrast styling was inspected in code, not emulated in the browser during this addition.


## Input limits, content discovery and multimodal slots — 2026-09-12

Result: passed for the requested fixes.

- Removed fixed maximum character lengths from authored text in both frontend controls and Pydantic models. Required fields, minimum lengths, list/count constraints, request IDs and file/provider operational limits remain separate.
- Diagnosis confirmed three existing successful materials were stored under the second course; reload selected the first course, and global job navigation did not align course context. The library now defaults to all courses, includes course metadata, supports course/status/title filters, and remembers selected workspace course. Opening content aligns the workspace course before subsequent actions.
- Generation submission goes to the library. Library and jobs refresh every three seconds while visible, preserve search/filter values, and stop updates on route disposal. Pending and unsuccessful generations have distinct status rows; failures are not fabricated as completed materials. Late task-detail and submission responses do not hijack a newly opened view.
- Added a declarative output-format registry and visible text/audio/image/video positions on creation and review screens. Audio/image use the existing approval-gated backend. Video is explicitly upcoming and has no API action. Actual media is rendered by kind and version.
- Automated validation: 66 Python tests passed; 24 Node tests passed. Includes long inputs through generation/edit/evaluation, cross-course data and job metadata/privacy, asynchronous update lifecycle, language/theme persistence and escaping. Existing dependency deprecation warnings only.
- Browser verification used the isolated mock-provider fixture: a 3,250-character English topic submitted and produced a listed material; a second tab generated another draft while the first library retained its query and draft filter, and the visible count updated from 1 to 2 without navigation. Approval enabled audio/image actions while video stayed disabled. Mobile English material list and output formats stayed within 390px with no maximum-length attributes on the creation form.
- Live read-only verification after restarting the idle local server: all three existing materials visible, and opening a material selected its course consistently across reload. No live generation or course-data edits were performed by this task.
- Accepted captures: `output/ui-review/library-live-fixed.jpg` (1280 × 720), `output/ui-review/multimodal-mobile-fixed.jpg` (390 × 844). Direct screenshots, no image transformations.
- Limits: multimodal protocol paths remain subject to configured provider availability; this change did not test real audio/image output quality or implement video generation. UI tests used temporary data only. The temporary service was stopped; the updated live service remains available.


## Input surfaces and controls — 2026-09-12

- Added a shared, quiet field material in `app/static/inputs.css`, with sage/ivory and dark variants, a soft focus edge, and compact native choices. Lesson depth now sits beside material language at desktop widths; mobile choices stack.
- Added `input-controls.js`: textareas grow and shrink with their content, capped at 420px for the main writing area and 320px for supporting fields before internal scrolling. These are visual height caps, not text limits. The remaining learner-profile maxlength was removed; the current backend already accepts long profiles.
- Numeric inputs retain native keyboard editing and form constraints, with separate 44px minus/plus buttons. Boundary buttons remain focusable with aria-disabled; hidden/disabled field states and exact difficulty allocations stay in sync. Numeric labels use explicit for/id associations so clicking their text cannot trigger a stepper button.
- Browser QA used the temporary mock-provider fixture. Verified native stepping at total 1/10 and allocation 0, manual values, empty-value recovery, preset synchronization, and mismatch reporting without redistribution. A 2,222-character topic expanded from 152px to 420px with internal scrolling; a 1,740-character learner profile reached 320px. Both survived theme and language switches, and shorter text returned to the smaller writing surface.
- At 390px, document width remained 390px and every visible stepper button measured 44px. Inspected English/light allocation rows and Chinese/dark creation fields. A new-course dialog retained visible keyboard focus with 0s transitions; all 11 dynamically inserted edit textareas were enhanced without changing their initial values.
- Automated checks: 106 Python tests and 33 Node tests passed; changed JavaScript syntax checks passed. Existing dependency deprecation warnings only. No live generation, approval, or course-data edits were performed.
- Accepted captures: `output/ui-review/input-light-mobile.jpg`, `output/ui-review/input-dark-mobile.jpg` (390×844), and `output/ui-review/input-live-final.jpg` (actual in-app panel). The earlier `input-light-desktop.jpg` is an intermediate focus capture before the final select alignment correction.
- The existing creation preview was empty before reload and was updated in place. OS accessibility preference emulation and live-provider output quality were not tested for this presentation change.

## English control copy — 2026-09-19

- Replaced browser-owned file-picker text with localized page copy while preserving the native file input, keyboard focus, file selection, and multipart upload. Empty state, picker title, and selected filename update without replacing the input.
- English language toggles now show ZH with the English tooltip “Switch to Chinese.” Other marked tooltip and interface strings were checked for translation coverage.
- Native required/email/number/length/format validation now follows the app locale. Stored difficulty-validation keys also update when the locale changes; editing a valid value clears owned native errors without overwriting unrelated business validation.
- Added five focused regression tests for native validity, business errors, file-selection preservation, and missing translations. All 60 frontend tests passed; changed entry/module syntax checks passed.
- Isolated browser QA: English required-login and empty-file validation bubbles displayed English; a test Markdown file remained selected across English → Chinese → English switches in another tab and then imported successfully. The source list showed the parsed file. No browser console errors were captured. Production account/course data was not modified.
- Scope: application interface text is localized. Authored course content and filenames remain original. The operating system's file browsing window follows the operating system language.
