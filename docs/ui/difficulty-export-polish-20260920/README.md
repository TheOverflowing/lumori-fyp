# Difficulty calibration, document references and review controls

Verified on 20 September 2026. This record describes a software behavior and presentation change, not a new model-quality or learner-difficulty experiment.

## Delivered behavior

- New generation requests make up to three strict difficulty rounds when a usable candidate differs only in assessed difficulty. After that, the closest candidate that passed its other quality gates is retained, preferring adjacent levels before allowing a wider difference. The requested target remains unchanged, and the actual assessment and `adjusted` acceptance are recorded separately. Correctness, source support, ambiguity, joint low confidence and API budgets are not waived. Existing checkpoints retain their original policy and budget.
- Failed generation requests expose **Edit request**. It restores the original course, topic, learner profile, question type/count, exact zero-inclusive difficulty distribution, content language, source selection and generation preferences. A resolved clarification is preserved in the restored topic. Consumed preparation identifiers and job identity are not reused; recovery itself makes no model call. Resumable tasks keep their existing **Continue generation** action.
- PDF/Word group passages from one document into one bibliography entry and one citation number, combining referenced pages. Different documents with equal filenames remain separate. JSON evidence and stored sources retain passage identity. Web review still uses passage-level source inspection and can have different numbers.
- Export and approved-content learning-view controls share the same secondary style. Evidence JSON is under the initially collapsed **Export → More exports** disclosure.

See [implementation and Before/After/Why review](IMPLEMENTATION.md), [current difficulty policy](../../Difficulty_Control.md), [export API](../../CONTENT_EXPORTS.md), and [user guide](../../USER_GUIDE.md).

## Automated checks

| Check | Result | Evidence |
| --- | --- | --- |
| Backend generation, difficulty, review, resume, ownership, recovery and exports | 440 passed; 2 existing deprecation warnings | [JUnit](backend-tests.xml), [log](backend-tests.txt) |
| Complete current frontend test collection | 197 passed | [log](frontend-tests.txt) |
| Final API projection change preserving original assessment rationale | 20 passed; overlaps the backend group | [JUnit](assessment-projection-tests.xml), [log](assessment-projection-tests.txt) |
| Patch whitespace validation | Passed | `git diff --check` |

The final projection change was followed by the relevant API regression subset; repeated runs are not counted as additional unique tests. Tests use offline provider responses. The nine frontend behavior additions and earlier focused checks are detailed in IMPLEMENTATION.md.

Reproduction:

```sh
.venv/bin/python -m pytest -q tests/test_difficulty_calibration.py tests/test_difficulty_pipeline.py tests/test_generation_agent.py tests/test_harness_quality_gates.py tests/test_flexible_agent.py tests/test_cpu_spec_agent.py tests/test_supervisor_agent.py tests/test_harness_schema_repair.py tests/test_agent_resume_api.py tests/test_difficulty_api.py tests/test_author_material_scope.py tests/test_job_progress.py tests/test_generation_request_recovery.py tests/test_account_isolation.py tests/test_content_exports.py tests/test_content_evaluations.py tests/test_content_downloads.py
node --test tests/frontend*.test.mjs
.venv/bin/python -m pytest -q tests/test_generation_request_recovery.py tests/test_difficulty_api.py
```

## Browser checks

The isolated `scripts/difficulty_export_fixture_server.py` wrapper uses a fresh temporary database, separate session cookie, historical source excerpts and explicitly synthetic quiz/calibration/job states. No normal-account materials, ratings or model configuration were changed.

Verified through the actual UI:

1. Matching Export and learning-view actions, with evidence absent from the review toolbar.
2. Export disclosure starts closed, exposes the correct evidence link when expanded, and reopens closed.
3. Requested Hard and assessed Easy/Medium are visible separately; the inspector says the result has a difficulty difference. English explicitly uses **Target difficulty**.
4. A failed job's **返回修改** action restored the exact bilingual topic and learner profile, mixed question type, English output, two questions and allocation `0 / 0 / 2`. Settings showed both Fusion and Auto explore enabled, matching the saved request. No generation was submitted.
5. Chinese and English copy, light and dark themes, and mobile layout. At a 390 px viewport, both toolbar actions measured 169 × 44 px; document scroll width remained 390 px.
6. No browser console errors were reported for the isolated page. The fixture's audit endpoint reported `provider_calls: 0` after the interactions.

Screenshots: [toolbar desktop](toolbar-en.png), [export menu](export-menu-en.png), [mobile toolbar](toolbar-mobile-zh.png), [mobile export](export-mobile-zh.png), [mobile dark](toolbar-mobile-dark.png), [failed request](failed-request-zh.png), [restored request](restored-request-zh.png), [current normal-app toolbar](toolbar-live.png). Early desktop screenshots precede the English label refinement from Difficulty to Target difficulty; final label text was rechecked in the live DOM. All adjusted acceptance and approved quiz states in fixture screenshots are synthetic UI data, not human review claims. Temporary viewport changes were reset and the fixture server was stopped.

## Rendered documents

Six final files (English lesson, Chinese lesson and quiz, each as PDF and Word) were rendered and all 16 pages inspected. Historical English/Chinese lessons with 10/11 same-document chunks now each have one D2L bibliography entry. The quiz groups three chunks into two documents, combines pages 1–2 and starts its answer key on a new page. Word keeps each bibliography entry together so license text is not orphaned.

See [document QA](documents/QA.md), [artifact hashes and pages](documents/manifest.json), and [source grouping/invariance](documents/source-grouping.json). Root additionally inspected the final English PDF and Chinese Word bibliography pages. The long Chinese Word sample naturally leaves its bibliography on a short final page.

This turn verifies export contents and layout. It does not claim to fix the previously recorded Codex in-app-browser Word attachment-saving limitation; see the [initial export QA](../review-exports-20260920/README.md). No paid model experiment was run, and no model-accuracy, strict difficulty-match-rate or learner-outcome improvement is claimed.

## Local application

The normal app at `http://127.0.0.1:8765` was restarted with the existing startup command after confirming zero queued/running jobs. Startup succeeded and the normal signed-in material detail page displayed the updated toolbar and its existing saved rating. The app remains available; no commit or remote publication was performed as part of this request.
