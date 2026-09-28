# Validation — 28 September 2026

Scope: repository synchronization and README correction for development through 26 September. This run did not call paid model APIs, regenerate research outputs, change `.env`, or restart the application.

## Research checkout

| Check | Observed result |
| --- | --- |
| Full backend suite, initial run | 2,965 passed, 1 failed, 22 skipped; 12 subtests passed, 433.01 seconds |
| Correction and focused rerun | All 8 tests in `test_content_library.py` and `test_difficulty_shadow_api.py` passed after updating the job-detail field contract |
| Frontend suite | 291 passed, 0 failed |
| Python compilation | `app/` and `scripts/` passed |
| Shared application manifest | 133 files matched byte-for-byte in the prepared product checkout |

The initial failure was an outdated exact-key assertion: `/api/jobs/{id}` now includes `difficulty_shadow`. The test now checks that this field is present and is `None` when the observer is disabled. The application implementation was unchanged by this correction. The full suite was not repeated after this test-only update; the focused rerun covers both the original failure and observer API behavior. Two dependency deprecation warnings remain.

Commands:

```sh
PYTHONPATH=. .venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_content_library.py tests/test_difficulty_shadow_api.py
node --test tests/frontend_*.test.mjs
.venv/bin/python -m compileall -q app scripts
git -c core.whitespace=cr-at-eol diff --cached --check
```

Skipped tests include opt-in Harness runtime integrations. These results do not establish live-provider availability, model quality, teacher approval, or learner difficulty.

## Integrity and publication boundary

- [SHA-256 manifest](app-manifest-20260928.json) covers application files, including the new observer and frontend modules.
- Pending files were checked against configured local secret values and common provider/GitHub token and private-key patterns. No configured secret was found; the only long token-pattern match was an explicit synthetic security-test input.
- Environment files, databases, uploads, downloaded models, virtual environments and personal application materials remain excluded. Research responses and frozen code snapshots remain in the research repository.
- CSV archives retain their existing CRLF bytes. Whitespace checks use `cr-at-eol` to accept those line endings without changing historical hashes.
- Local Markdown destinations in the updated READMEs and release index were checked after preparing the validation files.

## Deployment and GitHub Actions

The product checkout preserves Docker/Compose, model manifests and the existing container smoke script; its regression results are recorded in `TheOverflowing/Lumori/docs/VALIDATION_20260928.md`.

The local Docker daemon was unavailable, so no new local container build or container smoke test is claimed. Previous 24 September research and product GitHub Actions runs were rechecked and had completed successfully. They validate the previous commit only.

For checks associated with this synchronization, use the commit-specific runs on [research Actions](https://github.com/TheOverflowing/lumori-fyp/actions) and [product Actions](https://github.com/TheOverflowing/Lumori/actions). Their state is external to this pre-push record; publishing a commit does not itself establish successful deployment.
