# Assessment options and course library fixture

This is an isolated browser QA fixture. The app uses a fresh temporary SQLite
database on every start, a dedicated cookie, no configured model endpoints, and
an explicit request guard that rejects model execution. No production data is
loaded or modified. Source excerpts come from the earlier offline fixture;
content approval states and the interrupted job are synthetic UI cases.

Start from the repository root:

```sh
.venv/bin/python -m scripts.assessment_library_fixture_server --port 8770
```

- App: <http://127.0.0.1:8770/>
- Fixture account: `assessment.library@example.test`
- Fixture password: `Fixture browser password 2026!`
- Cookie: `lumori_assessment_library_fixture`
- Metadata: <http://127.0.0.1:8770/__ui/assessment-library-state>

The metadata route returns the current course IDs, content IDs, provider-call
count, and the most recent 150 API request method/path/query/status entries. It
does not record request bodies, credentials, cookies, or headers. Course A gets
a different ID at each launch; use the metadata endpoint rather than copying an
ID from an earlier run.

| Course | Content and purpose |
| --- | --- |
| A · Machine Learning | Three items with exactly the same title, `Machine learning practice / 机器学习练习`, to test identification by type. Lesson and assignment are approved; quiz needs review. |
| B · Operating Systems | One draft quiz titled `Only in course B · 独立课程记录`, plus one synthetic failed generation. Neither should appear under course A. |
| C · Empty course | No content or generation jobs; changing to this course should show the empty state. |

| Type | Content ID | Saved teaching option |
| --- | --- | --- |
| Lesson | `citation-fixture-content` | Always has lesson sections, even with the stored assessment toggle off. |
| Quiz | `review-export-fixture-quiz` | `include_explanations: false`; two questions, no learning objectives or teaching sections. |
| Assignment | `assessment-library-assignment` | `include_explanations: true`; introduction followed by two questions. |
| Course B quiz | `assessment-library-course-b-content` | `include_explanations: false`; separate document and excerpt IDs owned by course B. |

The fixed course B ID is `assessment-library-course-b`; the empty course ID is
`assessment-library-empty-course`. Course B's interrupted job is
`assessment-library-course-b-failed`.

## Smoke checks already completed

A TestClient run created a fresh fixture, authenticated its dedicated account,
and checked all of the following:

- Course-scoped content responses contain 3, 1, and 0 records respectively.
- Course A exposes all three saved types.
- The quiz contains two questions without a preamble; the assignment retains
  its teaching section and explicit enabled option.
- Course A's jobs do not include course B's interrupted job.
- Course B's interrupted job has the expected course and failed state.
- A model submission attempt is rejected by the fixture guard with HTTP 409.
- Provider-call count remains zero; API request audit entries are recorded.

## Browser QA checklist

1. Sign in and open Content & review. Confirm course A's three items have matching
   creation icons and visible type subtitles, with a draft count of one.
2. Search for a nonexistent title, then change the top-level course to B. Confirm
   the search resets and only B's content and interrupted job appear.
3. Choose C, then A. Confirm the empty state and restoration of A's three items.
4. Open the quiz and assignment to compare question-only versus introduction
   rendering. Confirm answer explanations remain separately available.
5. Open Create materials. Confirm the assessment introduction switch defaults
   off and appears only for Quiz and Assignment, with lesson creation unaffected.
6. Check Chinese/English and narrow layouts. Read the metadata route afterward
   to verify scoped `/api/contents?course_id=...` and `/api/jobs?course_id=...`
   requests and zero provider calls.

| Before | After | Why |
| --- | --- | --- |
| Identical book icons and similar titles obscure the task type. | Existing type-specific creation icons and a localized type subtitle. | Users can identify results without guessing from the title. |
| The library defaults to results from multiple courses. | The current course consistently scopes both results and unfinished jobs. | Course selection has the same meaning throughout the workflow. |

The checklist is a proposed browser procedure, not a claim that browser QA has
already been completed. Save actual screenshots and observations separately.
