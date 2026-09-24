# Task recovery and selective question revision

Implementation date: 2026-09-22. This is the first delivery from the project improvement plan: task controls, recoverable work, and local question revisions. It does not represent completion of the proposed independent RAG, difficulty, learner, or multimodal studies.

## User-visible behavior

- The progress page can stop a queued or running task. A queued task stops immediately. An in-flight request finishes or reaches a safe boundary before the running task stops; the UI shows that stopping is pending. A request already sent may have been billed.
- Passed question checkpoints are available in a separate read-only partial view. The view states the completed and requested counts. It does not publish, approve, or export an incomplete set as complete content.
- Interrupted or cancelled checkpointed generation can continue without recreating passed questions. Complete saved role responses are reused. Queued tasks cancelled before checkpoints exist can recover their original generation form instead.
- Each question on the review page has a revision action. Users can rewrite that question, change its target difficulty, or change only its explanation. Supporting material and all other questions remain unchanged.
- A revision creates a new draft version in the same content record. The previous asset remains in revision history; old approval and media are not inherited. A collapsed comparison shows changed question fields, with answers separately collapsed.
- If another editor saves a new version while a revision runs, the revision cannot overwrite that newer version. Repeated HTTP submissions with the same request and key return the existing task, including after it has completed.

## Implementation and boundaries

### Cancellation and recovery

`job_controls` stores the cancellation request separately from the existing jobs table. Call reservation checks cancellation in the same database transaction as call accounting. New provider/search reservations and Harness tool operations are blocked after cancellation. The host preserves complete responses and existing checkpoints before stopping.

The worker distinguishes cooperative cancellation, provider failure, service shutdown, and a storage failure. An unexpected storage error no longer silently kills a consumer or abandons a previously claimed job in `running`. Cancellation and resume update the durable timeline, preserving accumulated active time while excluding the paused interval.

`MAX_PENDING_JOBS_PER_ACCOUNT` defaults to 8 and includes queued plus running account tasks. Idempotent replays do not consume new slots. A resume must also respect the cap. This is an active-task limit, **not** round-robin scheduling or a fairness guarantee. Ownerless research fixtures remain outside the account limit. If parsing succeeds but the account queue cannot accept image enrichment, usable text remains available and image processing is deferred.

`/healthz` returns readiness based on database access and expected live workers, with HTTP 503 when unhealthy. Its public response uses booleans and exposes no account or global queue counts. `/livez` checks application liveness. A live worker awaiting a slow provider can still be ready; a no-progress watchdog is not included in this delivery.

### Selective revision

The server freezes the source content version, selected slot, source snapshots and supporting sections. It uses existing author, answer-blinded solver and reviewer calls for one question; the review additionally checks that the revision instruction is followed and the original learning focus is retained. Other question stems provide duplicate protection but their answers are not supplied to the solver.

Only the explanation is model-editable in explanation mode; the host copies all other question fields from the original. In rewrite mode, the question kind stays fixed and the host restores immutable supporting sections. References come from the selected question and its supporting material; no new retrieval, web exploration or embedding call is made by a revision. Requests for a new topic that existing references cannot support should use a new generation.

The normal cancellation, call limits, retry/checkpoint and correctness gates still apply. Format adaptation does not label a failed answer review as successful. Revision uses a single sequential question worker even when full-set generation uses supervisor planning. Supported arithmetic still goes through existing computation checks; the old question's compiler certificate is not inherited.

Publication uses a version-conditional database update inside one transaction. The explicit slot-level difficulty plan is updated without sorting or moving questions. Revision metadata identifies `selected_question_only`; it is not evidence that untouched questions were rechecked. AI checks are not teacher approval or empirically measured learner difficulty.

### HTTP surface

| Route | Contract |
| --- | --- |
| `POST /api/jobs/{id}/cancel` | Request safe cancellation; repeated cancellation is idempotent. Synchronous preparation jobs are not cancellable through this route. |
| `GET /api/jobs/{id}` | Adds cancellation state and availability of passed partial results. |
| `GET /api/jobs/{id}/partial-content` | Read-only passed questions and their source snapshots, with completed/total counts. |
| `POST /api/jobs/{id}/resume` | Explicitly resumes supported generation/revision checkpoints under the same job and budget. |
| `POST /api/contents/{id}/questions/{slot}/revise` | Version, instruction, mode, optional target difficulty and idempotency key; returns a revision job. |

All task and content routes retain authentication, ownership, course and CSRF boundaries. Job details do not expose original private request payloads.

## Validation record

All automated provider traffic uses isolated fixtures or HTTP MockTransport. UI screenshots use synthetic data. No new real model calls were made for this delivery, so these results demonstrate application behavior, not model answer quality, a recall improvement or a measured production failure-rate improvement.

- Backend: `pytest -q` completed with **2517 passed, 19 skipped, 12 subtests passed**; [full output](task-reliability-20260922/backend-tests.txt). The skipped tests retain their opt-in/environment requirements. Two existing FastAPI/Starlette deprecation warnings remain.
- Frontend: **233 tests passed** using `node --test tests/frontend_*.test.mjs`; [output](task-reliability-20260922/frontend-tests.txt).
- Installed Harness integration: **14 tests passed**, no skips, using real local Runtime/ACP/MCP and mocked upstream responses; [output](task-reliability-20260922/harness-runtime-tests.txt). This separately covers the optional Harness integration tests that the default backend run skips.
- Final budget adjustment: frozen-source revision needs three role calls without reserving an imaginary embedding call. The revision and shared generation tests were rerun after that change: **42 passed**; [output](task-reliability-20260922/revision-budget-tests.txt). These overlap with the full suite and should not be added to its count.
- UI: desktop and 390 px mobile, Chinese/English, light/dark, focus return, partial read-only view and changed-fields comparison. See [UI verification](task-revision-ui-20260922/README.md).
- Behavioral tests cover isolated accounts, unchanged questions and supporting sections, blinded solving, explanation-only immutability, difficulty slot order, instruction-check failure, version races, saved-response resume, lost-response idempotency, call accounting, worker recovery and durable timing.
- Local service was reloaded only after confirming zero queued/running jobs. The final [service check](task-reliability-20260922/service-smoke.json) verifies database/worker readiness and the new revision script at `127.0.0.1:8765`; no generation was submitted.

## Remaining work from the broader plan

Independent held-out course/evidence labels and end-to-end generation comparisons; difficulty calibration and correctness evaluation; frozen automatic-exploration benchmarks; deployment account recovery and operational budgets; later CA2 multimodal outputs. These remain separate work items and should be evaluated with their own experimental protocols.
