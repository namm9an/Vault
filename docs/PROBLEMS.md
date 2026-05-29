# Vault — Problems & Fixes

A running log of problems that cost time during the build, the root cause, and the fix. Write entries when the problem is fresh — by the time you forget, the lesson is gone.

**Purpose:** This file pays off when you (or someone else) hit a similar symptom three months from now. Optimize entries for *searchability by symptom*, not for storytelling.

Add new entries at the top.

---

## [2026-05-29] — `.env.prod` committed to public GitHub repo

**Symptom:** GitGuardian alert — "Generic Password exposed on GitHub" for `namm9an/Vault`, pushed 2026-05-29 06:43:33 UTC.

**Root cause:** `.env.prod` was not in `.gitignore` (only `.env` and `.env.local` were listed). The production env file was created and committed as part of the Phase 7 deploy commit.

**Fix:** (1) Added `.env.prod` to `.gitignore`. (2) Ran `git-filter-repo --path .env.prod --invert-paths --force` to purge the file from all history. (3) Force-pushed to GitHub. (4) Rotated the TIR endpoint from `is-10649` to `is-10708`. The token itself was not rotated (same JWT, different endpoint deployment).

**Time lost:** ~45 minutes.

**How to avoid next time:** Any file matching `*.env*` or `.env.*` should be in `.gitignore` from day one. The rule is: if it contains a secret, it never touches git. Use `.env.example` as the contract and `scp` to sync prod env to VM manually.

---

## [2026-05-29] — asyncpg DNS resolution failure in Docker during alembic migrations

**Symptom:** `api` container crashed on startup with `socket.gaierror: [Errno -2] Name or service not known` during `alembic upgrade head`. The hostname `db` could not be resolved by asyncpg's `_create_ssl_connection` even though the `db` container was healthy and DNS worked fine in `docker compose run` containers.

**Root cause:** asyncpg's `_create_ssl_connection` uses `asyncio.run_in_executor` + `socket.getaddrinfo`, which resolves DNS differently from the main-thread synchronous path. In the main service container (not a run container), Docker's embedded DNS (127.0.0.11) was not reachable from within asyncio's thread pool executor during early container startup.

**Fix:** Added `psycopg2-binary==2.9.9` to `api/requirements.txt`. Rewrote `api/alembic/env.py` to use a synchronous `create_engine` (psycopg2) for migrations instead of `async_engine_from_config` (asyncpg). Alembic doesn't need async — sync is cleaner and avoids the DNS issue entirely.

**Time lost:** ~2 hours of investigation.

**How to avoid next time:** Always use a sync DB driver for Alembic migrations. Async drivers add no value for schema migrations and introduce subtle executor/DNS timing issues in Docker.

---

## [2026-05-29] — arq.crons import error — module is arq.cron (singular)

**Symptom:** `worker` container crashed immediately with `ModuleNotFoundError: No module named 'arq.crons'`.

**Root cause:** `api/api/jobs/worker.py` had `from arq.crons import cron` (plural). In arq 0.26.1 the module is `arq.cron` (singular).

**Fix:** Changed to `from arq.cron import cron`.

**Time lost:** 5 minutes.

**How to avoid next time:** Check the arq changelog when pinning a version. The module was renamed between versions.

---

## [2026-05-29] — reseed_transactional() committed inside function, causing double-commit in demo reset endpoint

**Symptom:** Demo reset endpoint returned 500 intermittently — "This Session's transaction has been rolled back due to a previous exception during flush" or similar SQLAlchemy session state errors.

**Root cause:** `reseed_transactional()` called `await db.commit()` internally, but the docstring said "The caller is responsible for committing." The FastAPI request-scoped session in `reset_demo()` also tries to manage transaction state. Two commits on the same session caused state corruption on retry.

**Fix:** Replaced `await db.commit()` with `await db.flush()` inside `reseed_transactional()`. Both callers (`run()` in seeds.py and `reset_demo()` in demo.py) now explicitly call `await db.commit()` after the function returns.

**Time lost:** Caught in code review — zero runtime impact before fix.

**How to avoid next time:** Functions that take a session parameter must never commit — that is the caller's responsibility. The docstring was correct; the implementation wasn't.

---

## [2026-05-28] — Toast setTimeout IDs leaked on unmount — setState after unmount (L9 — low)

**Symptom:** No visible crash in normal use. In tests or rapid navigation, React emitted `Can't perform a React state update on an unmounted component` warnings. Each toast started a 4-second `setTimeout` that tried to call `setToasts` even after `ToastProvider` was unmounted.

**Root cause:** `Toast.tsx` called `setTimeout(...)` without storing the return ID, so there was no way to cancel pending timers on unmount.

**Fix:** Added `useRef<Set<ReturnType<typeof setTimeout>>>(new Set())` to track all active timer IDs. Each new timer's ID is added to the set. A `useEffect` cleanup function clears all IDs via `clearTimeout` on unmount.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** Any `setTimeout` inside a React component or provider must store its ID and clear it on unmount. The test: "can this timer outlive the component?" If yes, track the ID.

---

## [2026-05-28] — Digest detail panel flickered blank after generate (L10 — low)

**Symptom:** After clicking "Generate" in the modal, the selected ID was set to the new digest's ID but `digests.data` hadn't refetched yet — the `find()` returned `undefined`, so `selected` was `null` and the detail panel showed the "Select a digest" empty state for ~1–2 seconds before the refetch completed.

**Root cause:** `selected` was derived only from `digests.data`: `(digests.data ?? []).find(d => d.id === selectedId) ?? null`. The `generateDigest.mutateAsync` return value (the PENDING digest) was discarded.

**Fix:** Changed `selected` to use `generateDigest.data` as a fallback: `(digests.data ?? []).find(d => d.id === selectedId) ?? generateDigest.data ?? null`. The mutation result is immediately available, so the panel shows the PENDING digest without waiting for the list refetch.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** When a mutation returns the newly created item, use that return value immediately as a fallback for derived state instead of relying solely on the next list refetch.

---

## [2026-05-28] — Generate button allowed period_start >= period_end (M7 — medium)

**Symptom:** The "Generate" button in the DigestPage modal was enabled even when start and end dates were equal or inverted. Submitting such a request would hit the backend `@model_validator` and return a 422, but the error was swallowed silently in the mutation catch block.

**Root cause:** The `disabled` condition was `loading || !start || !end` — it checked for empty values but not for invalid date ordering.

**Fix:** Added `|| start >= end` to the `disabled` condition. Invalid date ranges are blocked at the UI layer before any network request is made.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** Any date range input should enforce `start < end` in both the UI (disabled state) and the backend (model validator). Validate at both layers.

---

## [2026-05-28] — Digest.updated_at used naive datetime — TypeError on tz-aware comparison (H5 — high)

**Symptom:** Any ORM operation that triggered the `onupdate` hook on `Digest.updated_at` raised `TypeError: can't compare offset-naive and offset-aware datetimes`. Not hit during basic CRUD but would surface during digest status polling comparisons.

**Root cause:** `onupdate=datetime.utcnow` — `datetime.utcnow()` returns a naive datetime (no timezone info). The `updated_at` column is `TIMESTAMPTZ` (timezone-aware). SQLAlchemy/asyncpg raises `TypeError` when it compares or writes a naive datetime against a timezone-aware column.

**Fix:** Changed to `onupdate=lambda: datetime.now(timezone.utc)`. The lambda produces a timezone-aware UTC datetime on every update.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** Never use `datetime.utcnow()` in new code — it is deprecated in Python 3.12 and always produces naive datetimes. Always use `datetime.now(timezone.utc)` for UTC timestamps.

---

## [2026-05-28] — DigestGenerateRequest accepted period_start >= period_end (H4 — high)

**Symptom:** `POST /digest/generate` with `{"period_start": "2026-05-28", "period_end": "2026-05-28"}` (equal dates) returned 202 and started generating a digest for a zero-length period. The LLM received a date range where start equalled end, producing a nonsensical digest.

**Root cause:** `DigestGenerateRequest` had no validator enforcing `period_start < period_end`.

**Fix:** Added `@model_validator(mode="after") def check_dates()` to `DigestGenerateRequest`. Raises `ValueError("period_start must be before period_end")` when `period_start >= period_end`, which Pydantic surfaces as a 422 with a clear message.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** Any schema with two date fields representing a range must validate ordering. Add a `@model_validator` as a checklist item alongside nullable/positive/length validators.

---

## [2026-05-28] — POST /digest/generate blocked HTTP response for 60+ seconds (H3 — high)

**Symptom:** `POST /digest/generate` held the HTTP connection open for the full LLM inference duration (~15–60 seconds). The browser showed a spinning request in devtools; on slower connections the request timed out before a response was received.

**Root cause:** `generate_digest_route` called `await run_digest_generation(scope, ...)` directly — the entire pipeline (DB aggregation + LLM call + email) ran synchronously in the request handler before any response was sent.

**Fix:** Extracted `get_or_create_pending_digest()` as a shared helper that commits only the PENDING row. The route calls this helper, returns HTTP 202 with the PENDING digest immediately, and schedules `_bg_generate` as a `BackgroundTasks` task. The background task opens its own DB session via `get_session_factory()()` and runs the full pipeline independently of the HTTP connection.

**Time lost:** ~20 minutes to design and implement (caught in validation).

**How to avoid next time:** Any route that triggers LLM inference must never run it inline. The pattern: commit a PENDING row → return 202 → run inference in BackgroundTasks (or ARQ for production). Polling `GET /{id}` is the client's contract.

---

## [2026-05-28] — send_digest_email blocked the async event loop (H2 — high)

**Symptom:** When a digest completed and email sending was triggered, the entire FastAPI event loop stalled for the duration of the SMTP connection (~2–5s on MailHog, potentially longer on real SMTP servers). During this time, no other requests could be processed.

**Root cause:** `send_digest_email` uses stdlib `smtplib.SMTP`, which is synchronous blocking I/O. Calling it directly inside `async def run_digest_generation` blocks the event loop — every `async def` runs on the same thread and cannot yield while smtplib is waiting on a socket.

**Fix:** Changed the call to `await asyncio.to_thread(send_digest_email, digest, recipients)`. This offloads the synchronous function to a thread pool executor, freeing the event loop immediately.

**Time lost:** Caught in validation — zero build-time impact.

**How to avoid next time:** Any synchronous blocking I/O (file I/O, subprocess, smtplib, requests, boto3 sync) called from an `async def` must be wrapped in `asyncio.to_thread(...)`. The test: "does this function have a blocking socket call or file read?" If yes, it belongs in a thread.

---

## [2026-05-28] — POST /notifications/read-all always returned 422 (C1 — critical)

**Symptom:** `POST /notifications/read-all` returned `422 Unprocessable Entity` on every call. The error body showed `value is not a valid uuid` for the path parameter `notification_id`, despite no UUID being passed.

**Root cause:** `POST /notifications/{notification_id}/read` was declared before `POST /notifications/read-all` in the router. FastAPI matched the path `/notifications/read-all` against the parameterized route first and attempted to parse `"read-all"` as a UUID — which fails validation, producing the 422 before the handler was ever called.

**Fix:** Moved `POST /notifications/read-all` above `POST /notifications/{notification_id}/read` in `notifications.py`. Added a comment explaining the ordering requirement.

**Time lost:** Caught in validation — would have been a demo-day blocker (mark-all-read button non-functional).

**How to avoid next time:** In FastAPI, literal path segments must always be registered before parameterized segments at the same path level. The rule: if you have both `/foo/bar` and `/foo/{id}`, declare `/foo/bar` first.

---

## [2026-05-28] — Employees got 403 on GET /departments — reimbursement picker empty (H6 — high)

**Symptom:** `NewReimbursementDialog` showed an empty department dropdown. Employees opening the reimbursement submit form saw no selectable departments. Console showed 403 on `GET /api/v1/departments`.

**Root cause:** `GET /departments` had `require_role(UserRole.ADMIN, UserRole.FINANCE_MANAGER)` — the same guard as write operations. The employee role was never considered because the original plan treated departments as an admin-only concern, predating the employee reimbursement submission form that needs the list.

**Fix:** Removed the `require_role` dependency from the `GET /departments` list route. All authenticated users within an org may read the department list (names + IDs). Budget-status and write routes retain their FM/ADMIN guards.

**Time lost:** Caught in post-phase validation — zero wasted build time, but would have blocked the employee reimbursement demo flow.

**How to avoid next time:** When designing RBAC for a new resource, enumerate all the consumers of each endpoint (not just admins). Employee-facing forms that reference other resources need at least a read-scope for those resources.

---

## [2026-05-28] — PieChart collapsed to zero height on narrow viewports (H5 — high)

**Symptom:** The "Spend by category" pie chart on the DashboardPage disappeared on laptop-width screens and was invisible by default in the demo viewport.

**Root cause:** `<ResponsiveContainer width={160} height={160}>` — setting a fixed pixel `width` on `ResponsiveContainer` defeats its purpose. When the container's parent is narrower than 160px, Recharts resolves the fixed width but reports 0 height, collapsing the chart.

**Fix:** Wrapped the `ResponsiveContainer` in `<div style={{width: 160, height: 160}}>` and set `width="100%" height="100%"` on the container — it now fills the fixed-size parent correctly on all viewports.

**Time lost:** ~5 minutes (caught in validation).

**How to avoid next time:** `ResponsiveContainer` should always receive percentage dimensions. Use a fixed-size wrapper `<div>` to constrain the dimensions; never pass fixed pixels to `width` or `height` on the container itself.

---

## [2026-05-28] — Dashboard refetched on every render — date strings changed each render (H4 — high)

**Symptom:** The network tab showed `GET /dashboard/summary` and `GET /dashboard/timeseries` firing continuously — several times per second. The server-side Redis cache was irrelevant because TanStack Query saw a new cache key on every render.

**Root cause:** `const [fromDate, toDate] = getRangeDates(rangeDays)` was called directly in the component body. `getRangeDates` calls `new Date()` internally, producing a millisecond-resolution ISO timestamp (`2026-05-28T10:23:45.123Z`) that changes on every render. TanStack Query uses the full query key for cache identity — a new string means a cache miss, which triggers a refetch.

**Fix:** `const [fromDate, toDate] = useMemo(() => getRangeDates(rangeDays), [rangeDays])`. The dates are now stable for the lifetime of a given `rangeDays` value, matching the server-side 5-minute Redis TTL.

**Time lost:** ~10 minutes (caught in validation).

**How to avoid next time:** Any value derived from `new Date()` that is used in a TanStack Query key must be memoized or rounded to a coarser unit. The test: "does this value change between renders without user interaction?" If yes, memoize it.

---

## [2026-05-28] — Redis failure crashed get_budget_status — 500 instead of budget data (H3 — high)

**Symptom:** When Redis was unavailable (e.g. during Redis restart), `GET /departments/{id}/budget-status` returned 500. Finance Managers could not see any budget data.

**Root cause:** `get_budget_status` opened a Redis connection inside a `try/finally` but only to ensure `aclose()` was called. The `client.set(...)` call itself was not caught — a Redis `ConnectionError` propagated up through FastAPI as a 500.

**Fix:** Wrapped the entire Redis alert block in `try/except Exception`. On failure, logs a warning and continues to return the budget status. The threshold notification is best-effort; the budget figures (derived from Postgres) are always returned.

**Time lost:** ~10 minutes (caught in validation).

**How to avoid next time:** Side-effect operations (notifications, cache writes) that are not on the critical read path must be wrapped in their own try/except so they cannot degrade a successful data query into an error response.

---

## [2026-05-28] — Budget alert Redis key set before DB commit — notification permanently lost on commit failure (H2 — high)

**Symptom:** Not a visible crash — a correctness issue. If `db.commit()` failed after `client.set(redis_key, "1", nx=True)` succeeded, the Redis dedup key would be set but no notification row would exist in the DB. All future requests would find the key already set and skip the notification forever — a permanently lost alert.

**Root cause:** The original order was: SET NX → `notify_all_fms` → `db.commit()`. The Redis write came before the DB was committed, so a DB failure left an inconsistent state.

**Fix:** Reversed the order: GET key first (probe for existing dedup entry). If absent: call `notify_all_fms`, then `db.commit()`, then SET NX (best-effort inner try/except). If SET NX fails after a successful commit, we may fire one duplicate notification — acceptable compared to a permanently silent alert.

**Time lost:** ~10 minutes (caught in validation).

**How to avoid next time:** When Redis is used as a dedup guard for a DB-persisted action, the DB commit must always happen first. "SET NX before commit" is a write-ordering anti-pattern — the dedup fires before the guarded action succeeds.

---

## [2026-05-28] — Enqueue failure silently rejected reimbursement with no notification, pool leaked (H1 — high)

**Symptom:** When Redis was temporarily unavailable at the moment a reimbursement was submitted, the employee's request returned 200 (created) but the reimbursement status immediately became `REJECTED` with no notification, no `decided_at`, no AuditLog, and no explanation visible to the employee. Additionally, the ARQ Redis pool was never closed if the enqueue failed.

**Root cause:** The `except Exception:` block in `create_reimbursement` set `status=REJECTED` and committed, but called neither `fire_notification` nor `db.add(AuditLog(...))`. The `pool.aclose()` was only called inside the try block, not in a `finally`.

**Fix:** Added `try/finally` to guarantee `pool.aclose()`. The except block now: writes an `AuditLog(action="reimbursement.enqueue_failed")`, fires `APPROVAL_REJECTED` notification to the employee, sets `decided_at=now()`, all committed atomically. The employee sees a REJECTED status with "please retry" in the notification instead of silent confusion.

**Time lost:** ~15 minutes (caught in validation).

**How to avoid next time:** Resource cleanup (pool/connection close) always goes in `finally`, not `try`. Any state mutation that creates a user-visible outcome must be accompanied by an AuditLog entry and a notification — treat them as a unit, not as optional add-ons.

---

## [2026-05-28] — No AuditLog written in run_reimbursement_policy_check (C3 — critical)

**Symptom:** Reimbursements moved through `SUBMITTED → POLICY_CHECKED → REJECTED` (BLOCKED path) with zero rows in `audit_log`. A Finance Manager looking at the audit trail could not determine when or why the policy engine ran, or what verdict was returned.

**Root cause:** The ARQ job was written before the single-commit audit rule was applied consistently. The `approve_reimbursement` and `reject_reimbursement` service functions both write AuditLog correctly, but the ARQ job — which drives most of the early state transitions — was never updated to match.

**Fix:** Added `db.add(AuditLog(...))` calls before every `await db.commit()` in the job:
- Phase 1: `reimbursement.policy_checked` (system actor, `actor_user_id=None`)
- Phase 2 BLOCKED path: `reimbursement.policy_blocked`
- Phase 2 APPROVED path: `reimbursement.policy_approved`
- Phase 2 FLAGGED path: `reimbursement.policy_flagged`
- Phase 2 LLM error path: `reimbursement.policy_error`
- Phase 2 no-policies path: `reimbursement.policy_no_rules`

**Time lost:** ~10 minutes (caught in validation).

**How to avoid next time:** The rule is: every system-driven state change must write an AuditLog with `actor_user_id=None` in the same commit. Apply this as a checklist item when writing any ARQ job that mutates state.

---

## [2026-05-28] — FM Approve always returned 409 for LLM-approved reimbursements (C2 — critical)

**Symptom:** After the ARQ policy check job ran and approved a reimbursement, Finance Managers clicking "Approve" in the UI always received `409 Conflict — reimbursement is not in POLICY_CHECKED state`. FM approval was completely non-functional.

**Root cause:** The ARQ job transitioned APPROVED and FLAGGED verdicts directly to `status=APPROVED`. But `approve_reimbursement` in the service layer guards `if reimb.status != POLICY_CHECKED: raise 409`. The moment the LLM approved a reimbursement, it was moved past the state FM is allowed to act on — making FM approval dead code.

Additionally, `decided_by` and `decided_at` were never set for LLM-driven auto-approvals, leaving those columns NULL on approved records.

**Fix:** Changed the ARQ job so APPROVED and FLAGGED verdicts leave status at `POLICY_CHECKED` (FM must sign off). Only BLOCKED auto-transitions to `REJECTED` (with `decided_at=now(), decided_by=None`). FMs now always sign off manually on non-blocked reimbursements — a stricter but correct workflow. See `docs/DECISIONS.md` for the full reasoning.

**Time lost:** Caught in post-phase validation — would have been a demo-day blocker.

**How to avoid next time:** When an ARQ job drives state transitions, validate that the downstream human-approval endpoints are still reachable. Specifically: if a job auto-transitions to state X, check that no endpoint requires "must be in state X" as a guard — it will be unreachable.

---

## [2026-05-28] — Two-phase ARQ job left reimbursements permanently stuck in POLICY_CHECKED (C1 — critical)

**Symptom:** If the ARQ worker crashed after Phase 1 committed (`status=POLICY_CHECKED`) but before Phase 2 started, the reimbursement was stuck in `POLICY_CHECKED` forever. Any retry found `status != SUBMITTED` in Phase 1 and returned immediately — Phase 2 never ran, and there was no manual recovery path.

**Root cause:** Phase 1's idempotency guard was `if reimb.status != SUBMITTED: return`. This correctly skips Phase 1 for already-processed rows, but it also skipped Phase 2 for rows where Phase 1 had committed but Phase 2 had not yet run — because the check returned early before Phase 2 code was even reached.

**Fix:** Phase 1's idempotency guard now logs and falls through (does not return) when status is already `POLICY_CHECKED`, allowing execution to reach Phase 2. Phase 2 has its own idempotency guard: `if reimb2.status != POLICY_CHECKED: return`. Any status beyond `POLICY_CHECKED` (APPROVED, REJECTED, PAID) causes both phases to skip cleanly.

**Time lost:** ~15 minutes (caught in validation).

**How to avoid next time:** In a two-phase job, Phase 1's guard must distinguish between "already completed all phases" (skip entirely) and "completed Phase 1 only" (skip Phase 1 but continue to Phase 2). The safest pattern: Phase 1 guard blocks only re-execution of Phase 1. Phase 2 has an independent guard on the state that Phase 1 produces.

---

## [2026-05-28] — Medium issues deferred to Phase 6/7 (M1–M6)

The following issues were identified in the Phase 5 validation report and logged for later fix. None are demo blockers.

- **M1** — `department_id` in `create_reimbursement` is not org-scoped. An employee can attach a reimbursement to a department from another org by guessing its UUID. Fix: add `Department.org_id == scope.org_id` to the lookup, same pattern as the receipt org-scope fix in Phase 4.
- **M2** — `manager_id` in `update_department` is not org-scoped. An ADMIN can set a user from another org as department manager. Fix: org-scoped user lookup before assigning.
- **M3** — Dashboard `pending_approvals` KPI counts only `FLAGGED` transactions. It ignores `POLICY_CHECKED` reimbursements. The KPI understates the FM's real work queue. Fix: add a second query for POLICY_CHECKED reimbursements and sum both counts.
- **M4** — `GET /dashboard/timeseries?bucket=invalid` silently falls back to "day" instead of returning 422. Fix: validate `bucket` against a Literal type in the query schema.
- **M5** — Zero prior-period spend (no transactions in the prior window) reports `mom_delta_pct=null` displayed as "no prior data". Should display "+100%" or "first period" depending on current spend. Fix: handle the zero-divisor edge case in `dashboard_service.get_summary`.
- **M6** — `prior_from` in the MoM calculation is `now - 2*days` with a ~1-second bias from `datetime.now()` call latency across two lines. Fix: compute a single `now` snapshot before both window calculations.

---

## [2026-05-28] — ocr_receipt fabricated receipt data from metadata (C3 — critical)

**Symptom:** Every receipt upload immediately showed `status: "COMPLETED"` with a merchant name, amount, and category that looked plausible but were entirely made up. The LLM was returning `confidence: 0.9` for data it had no way to know. Transactions created from these receipts contained hallucinated figures.

**Root cause:** The `ocr_receipt` job sent a "vision" prompt to Llama 3.1 8B Instruct, which is a **text-only** model (vision was added in Llama 3.2). With no image data to work from, the model fabricated receipt fields from the filename, content_type, and byte_size in the prompt context, and returned them with high confidence because its system prompt instructed it never to return confidence < 0.7.

**Fix:** Replaced the entire LLM call path. The `ocr_receipt` job now marks every receipt `NEEDS_REVIEW` immediately with `extracted_data=None` and fires a `RECEIPT_REVIEW_NEEDED` notification. No LLM call is made. `onReceiptReady` on the frontend fires for both `COMPLETED` and `NEEDS_REVIEW` so receipt attachment still works.

**Time lost:** Caught in post-phase validation review — would have been a demo-day blocker if a Finance Manager had noticed fabricated amounts in the policy engine.

**How to avoid next time:** Before writing any LLM integration, verify the model's actual capabilities (text-only vs vision) on the specific endpoint. Never trust that a model will refuse a request it can't fulfill — it may fabricate a confident-looking answer instead.

---

## [2026-05-28] — onReceiptReady blocked NEEDS_REVIEW — receipts could never be attached (H5)

**Symptom:** The `ReceiptUploader` component's `onReceiptReady` callback fired only when `status === "COMPLETED"`. After the C3 fix, `ocr_receipt` never sets `COMPLETED` (all receipts land as `NEEDS_REVIEW`). The receipt could therefore never be attached to a transaction via the upload flow.

**Root cause:** The `onReceiptReady` condition was written before the C3 fix when `COMPLETED` was the expected terminal success state.

**Fix:** Changed the callback condition to fire for both `COMPLETED` and `NEEDS_REVIEW`, suppressed only for `FAILED`. Closed as correct behavior post-C3 — `NEEDS_REVIEW` is the honest "upload succeeded, needs human review" state.

**Time lost:** ~10 minutes.

**How to avoid next time:** Any "done" condition in the polling loop should be derived from the full set of non-error terminal states, not a single expected value.

---

## [2026-05-28] — Presigned URLs had Docker-internal hostname unreachable from browser (C2)

**Symptom:** Receipt upload in the browser failed with a network error immediately after calling `POST /receipts/upload-url`. The returned `upload_url` had hostname `minio:9000` — the Docker-internal name — which the browser cannot resolve.

**Root cause:** `boto3.generate_presigned_url` uses the endpoint URL configured in the S3 client (`S3_ENDPOINT_URL=http://minio:9000` inside Docker). The browser is outside the Docker network and cannot reach `minio:9000`.

**Fix:** Added `S3_PUBLIC_URL` config var. `_to_public_url(presigned_url)` in `s3.py` swaps the scheme+netloc of the presigned URL with `S3_PUBLIC_URL` (`http://localhost:9000` for local MinIO). `presign_put` and `presign_get` both call this before returning.

**Time lost:** ~20 minutes.

**How to avoid next time:** Any presigned URL returned to the browser must be rewritten to a publicly routable hostname. Always test the upload flow end-to-end from the browser, not just from inside the Docker network.

---

## [2026-05-28] — run_policy_check called notify_all_fms after db.commit() — two-commit race (H2)

**Symptom:** In early Phase 4, `notify_all_fms` was called after `await db.commit()`. This meant there were two sequential commits: one for state+result, one for notifications. A process crash between them would leave the transaction in FLAGGED/BLOCKED state with no FM notifications ever written.

**Root cause:** The notification call was placed after the commit as an afterthought, not treated as part of the same atomic outcome.

**Fix:** Moved `await notify_all_fms(...)` to before `await db.commit()`. All three pieces — `TransactionPolicyResult`, `TransactionEvent`, and `Notification` rows — are added to the session and committed together.

**Time lost:** ~10 minutes (caught in code review).

**How to avoid next time:** Any action that must be observable as a unit (state + side effects) must land in the same commit. The rule: "if a crash between A and B would leave the system in a broken state, A and B must be in the same commit."

---

## [2026-05-28] — ARQ enqueue failure in receipt_service left receipt stuck in PROCESSING (H3)

**Symptom:** If Redis was temporarily unavailable when `POST /receipts/{id}/confirm` was called, `arq.create_pool` raised an exception. The receipt was already set to `status=PROCESSING` (committed) but no job was ever enqueued. The receipt was stuck in `PROCESSING` forever with no way for the user to recover.

**Root cause:** No error handling around the ARQ enqueue call. The `status=PROCESSING` mutation was committed before the enqueue, so a failure left an inconsistent state.

**Fix:** Wrapped `create_pool` + `enqueue_job` + `aclose` in a try/except. On any exception, the receipt is set to `status=FAILED` with `llm_error="Failed to enqueue OCR job — please use the retry endpoint."` and re-committed. The user sees a FAILED status with a clear message.

**Time lost:** ~15 minutes.

**How to avoid next time:** Any DB state mutation that depends on a subsequent external operation (queue enqueue, HTTP call) must have a rollback path. Either do both in the same atomic unit, or have an explicit fallback to a recoverable error state.

---

## [2026-05-28] — Receipt could be linked to a transaction from a different org (C4)

**Symptom:** `POST /transactions` with a `receipt_id` from a different org succeeded — the receipt was linked cross-tenant.

**Root cause:** The receipt lookup in `create_transaction` used `select(Receipt).where(Receipt.id == data.receipt_id)` with no `org_id` filter. Any valid receipt UUID would pass the check regardless of which org owned it.

**Fix:** Added `Receipt.org_id == scope.org_id` to the WHERE clause. Returns 404 if the receipt is not found in the current org — consistent with the project rule (cross-resource access returns 404, never 403).

**Time lost:** ~5 minutes (caught in code review).

**How to avoid next time:** Every resource lookup must include `org_id` in the WHERE clause. Add an explicit "does this query scope by org_id?" check to every new service function review.

---

## [2026-05-28] — Hard-delete of policy rows orphaned TransactionPolicyResult.matched_policy_id (C5)

**Symptom:** Deleting a policy that had been matched in a past transaction caused `transaction_policy_results.matched_policy_id` to be SET NULL (cascade), losing the "which policy triggered this verdict" information permanently from the audit trail.

**Root cause:** `delete_policy` called `db.delete(policy)`. The FK had `ON DELETE SET NULL`, so the reference was silently nulled out.

**Fix:** Changed `delete_policy` to a soft-delete: `policy.is_active = False; policy.deleted_at = datetime.now(timezone.utc)`. Added Alembic migration `0003_policy_soft_delete` adding `deleted_at TIMESTAMPTZ NULL` to the `policies` table. All `list_policies` and `get_policy` queries now filter `Policy.deleted_at.is_(None)`.

**Time lost:** ~20 minutes (caught in code review).

**How to avoid next time:** Any table with FK references from an audit trail must use soft-delete. The question "will deleting this row lose audit information?" should be asked for every delete operation during design.

---

## [2026-05-28] — Dead admin_token_payload fixture referenced undefined variables (H7)

**Symptom:** `python -m pytest -q` on fresh clone failed at collection with `NameError: name 'acme_org_id' is not defined` in `api/tests/conftest.py`.

**Root cause:** A leftover `admin_token_payload` fixture referenced `acme_org_id` and `admin_user_id` — variables that existed in a previous iteration of the conftest but had since been removed. The fixture was never used by any test; it was dead code that broke collection.

**Fix:** Removed the `admin_token_payload` fixture entirely.

**Time lost:** ~5 minutes.

**How to avoid next time:** Run `python -m pytest --collect-only -q` after any conftest change to verify collection succeeds before running the full suite.

---

## [2026-05-28] — content_type accepted arbitrary strings; byte_size had no cap (H6)

**Symptom:** `POST /receipts/upload-url` accepted `content_type: "text/html"` and any arbitrary string. `POST /receipts/{id}/confirm` had no byte_size limit — a 1 GB upload would have been presigned and processed without error.

**Root cause:** `UploadUrlRequest.content_type` was typed as `str` with only `min_length=1` validation. `ConfirmUploadRequest.byte_size` had `Field(gt=0)` only.

**Fix:** Changed `content_type` to `Literal["image/jpeg", "image/png", "application/pdf"]` (Pydantic union validation). Added `le=10_485_760` (10 MB) to `byte_size`. Both changes in `api/api/schemas/receipt.py`.

**Time lost:** ~5 minutes.

**How to avoid next time:** Any file upload endpoint must whitelist content types and cap sizes at schema-validation time, not in application logic.

---

## [2026-05-28] — React ReferenceError: isPolicyPending before txnDetail (C1)

**Symptom:** Opening the transactions page crashed with `ReferenceError: Cannot access 'txnDetail' before initialization`. The error only appeared in the browser console; the page was blank.

**Root cause:** In `TransactionsPage.tsx`, `const isPolicyPending = txnDetail?.state === "POLICY_CHECKED"` appeared one line before `const { data: txnDetail } = useTransaction(txnId)`. JavaScript's `let`/`const` are not hoisted; referencing `txnDetail` before the `useTransaction` call is a temporal dead zone error.

**Fix:** Swapped the declaration order. Moved the polling logic into a `refetchInterval` callback inside `useTransaction` so `isPolicyPending` is derived inside the hook, not as a local variable in the component.

**Time lost:** ~10 minutes.

**How to avoid next time:** Never reference a `const`/`let` before its declaration in the same block. TypeScript's strict mode does not catch this particular error because `txnDetail` is reassigned by the hook, but the reference is at the declaration site.

---

## [2026-05-27] — StateBadge used for PolicyVerdict caused silent type mismatch (M3)

**Symptom:** `TransactionDetailDrawer` rendered the policy result verdict badge via `<StateBadge state={txnDetail.latest_policy_result.verdict} />`. TypeScript did not complain because `PolicyVerdict` values (`APPROVED`, `FLAGGED`, `BLOCKED`) are all subsets of `TransactionState` strings. No runtime error occurred in Phase 3.

**Root cause:** `StateBadge` is typed `{ state: TransactionState }`. Passing a `PolicyVerdict` is structurally compatible today but will silently break if Phase 4 introduces a verdict value that is not in `STATE_STYLES` — it would render a `undefined` class string.

**Fix:** Created `VerdictBadge({ verdict: PolicyVerdict })` with its own `VERDICT_STYLES` record. The policy result section in `TransactionDetailDrawer` now uses `VerdictBadge`. The two components have independent style maps and type contracts.

**Time lost:** 0 (caught in code review, not a runtime crash).

**How to avoid next time:** Never pass a narrower union type to a component typed for a broader one unless the broader union's lookup is exhaustively provably safe. When two domain concepts share overlapping string values, give them separate components.

---

## [2026-05-27] — list_transactions unbounded — full org history in memory (H3)

**Symptom:** `GET /transactions` with no filters loaded every transaction in the org into a Python list in one query. On a seeded database with months of history this would transfer megabytes per request.

**Root cause:** `list_transactions` had no `LIMIT` or `OFFSET` clause. The SQLAlchemy query used `.order_by().` without `.limit()`.

**Fix:** Added `limit: int = Field(default=50, ge=1, le=200)` and `offset: int = Field(default=0, ge=0)` to `TransactionFilters`. Applied `.limit(filters.limit).offset(filters.offset)` to the query.

**Time lost:** ~5 minutes.

**How to avoid next time:** Every list endpoint that touches a business table must have a `LIMIT` clause. Make it a code-review checklist item alongside the `org_id` scope check.

---

## [2026-05-27] — Concurrent approve/reject: no row-level lock (H2)

**Symptom:** Two simultaneous `POST /transactions/{id}/approve` calls on the same FLAGGED transaction both succeeded — identical to the refresh-token race in Phase 1.

**Root cause:** `_load_transaction` used a plain `SELECT` with no locking. Two concurrent requests both read `state = FLAGGED`, both passed the state guard, both wrote approval events, and both committed. The second commit wrote a duplicate `CLEARED` event and put the transaction in an internally inconsistent state.

**Fix:** Added `for_update: bool = False` parameter to `_load_transaction`. `approve_transaction` and `reject_transaction` call it with `for_update=True`, which emits `SELECT … FOR UPDATE` — serializing concurrent requests at the DB row level. The first caller acquires the lock; the second waits, reads the now-APPROVED state, and immediately gets a 409.

**Time lost:** ~10 minutes.

**How to avoid next time:** Any endpoint that performs a read-check-write sequence on a row must use `SELECT FOR UPDATE`. This is the same lesson as the refresh token race. Add a "does this endpoint modify state based on current state?" check to every new service function review.

---

## [2026-05-27] — FLAGGED/BLOCKED states unreachable — FM approval demo dead code (C2)

**Symptom:** Every `POST /transactions` call returned `state: "CLEARED"` regardless of amount. Navigating to a transaction detail drawer with state FLAGGED was impossible via the API alone — the approve/reject panel was completely unreachable end-to-end.

**Root cause:** `_run_policy_stub` returned `None` (no return statement). `create_transaction` ignored the return value and unconditionally called `transition(POLICY_CHECKED → APPROVED)` followed by `transition(APPROVED → CLEARED)`. The branch on verdict never existed.

**Fix:** `_run_policy_stub` now returns `PolicyVerdict`. `create_transaction` branches on it:
```python
verdict = await _run_policy_stub(scope, txn)
if verdict == PolicyVerdict.APPROVED:
    await transition(scope, txn, TransactionState.APPROVED, ...)
    await transition(scope, txn, TransactionState.CLEARED, ...)
elif verdict == PolicyVerdict.FLAGGED:
    await transition(scope, txn, TransactionState.FLAGGED, ...)
else:  # BLOCKED
    await transition(scope, txn, TransactionState.BLOCKED, ...)
```

Demo thresholds (no real policies yet): `amount > ₹1,00,000` → BLOCKED; `amount > ₹50,000` → FLAGGED; otherwise APPROVED.

**Time lost:** Caught in post-phase code review. Would have been a demo-day blocker.

**How to avoid next time:** Every stub function that feeds a branch must have a return type annotation. `_run_policy_stub(…) -> None` was the smell — if the caller branches on the return value, the return type must be non-None.

---

## [2026-05-27] — EMPLOYEE other-card check returned 403, leaking card existence (C1)

**Symptom:** `POST /transactions` with an EMPLOYEE scope and a card belonging to another user returned `403 Forbidden`. The 403 tells the caller "the card exists but you can't use it" — leaking that the card UUID is valid.

**Root cause:** The EMPLOYEE ownership guard raised `HTTP_403_FORBIDDEN`. The project rule ("cross-resource access returns 404, never 403 — never leak that a resource exists in another scope") was not followed.

**Fix:** Changed to `HTTP_404_NOT_FOUND` with the same `"card not found in this org"` message. The card's existence is indistinguishable from a card that doesn't exist. Test renamed `test_employee_create_other_card_raises_404`.

**Time lost:** ~5 minutes.

**How to avoid next time:** Add a mental checklist for every new 403: "Does this 403 leak the existence of a resource the caller shouldn't know about?" If yes, return 404 instead.

---

## [2026-05-27] — AsyncMock().add generates unawaited-coroutine warnings in transaction tests

**Symptom:** Running `pytest -q` on `tests/test_transactions.py` passed all 12 tests but printed 12 `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` warnings — one per `scope.db.add(...)` call.

**Root cause:** `db = AsyncMock()` makes every attribute of `db` also an `AsyncMock` by default. This includes `db.add`. In SQLAlchemy, `Session.add()` is synchronous — the service calls it without `await`. The auto-created `AsyncMock` for `db.add` returns a coroutine object each time, which is then immediately discarded without being awaited, triggering the warning.

**Fix:** After `db = AsyncMock()`, explicitly override the sync method: `db.add = MagicMock()`. This matches the real behavior (sync call, no return value needed) and eliminates the warning.

```python
def _make_scope(org_id=None, role="ADMIN"):
    db = AsyncMock()
    db.add = MagicMock()   # session.add() is sync in SQLAlchemy
    return OrgScope(db=db, org_id=org_id or uuid.uuid4(), ...)
```

**Time lost:** ~15 minutes.

**How to avoid next time:** Any SQLAlchemy session method that is sync (`add`, `expunge`, `merge`) must be explicitly set to `MagicMock()` when the parent session is an `AsyncMock`. Async methods (`flush`, `commit`, `rollback`, `execute`, `refresh`) can stay as `AsyncMock`.

---

## [2026-05-27] — NoReferencedTableError: TransactionPolicyResult.matched_policy_id → policies

**Symptom:** `POST /transactions` returned `500 Internal Server Error` immediately after fixing the `receipt_id` error (see entry below). FastAPI logs showed `sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'transaction_policy_results.matched_policy_id' could not find table 'policies' in this MetaData`.

**Root cause:** `TransactionPolicyResult` had a `mapped_column` for `matched_policy_id` with `ForeignKey("policies.id")`. The `Policy` ORM model is Phase 4 work and had not been created yet. SQLAlchemy resolves all FK targets when the ORM metadata is loaded (on import), not lazily — if the target model is absent, it raises immediately.

**Fix:** Removed the `matched_policy_id: Mapped[UUID | None]` column from `TransactionPolicyResult`. Added a comment: `# matched_policy_id FK → policies is added in Phase 4 when the Policy ORM model exists`. The DB column still exists (created in `0001_baseline`); the ORM just doesn't map it until Phase 4.

**Phase 4 action:** Add `from api.models.policy import Policy` to `models/__init__.py`, then restore `matched_policy_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)` in `TransactionPolicyResult`.

**Time lost:** ~10 minutes.

**How to avoid next time:** When a model has a FK to a table whose ORM model does not exist yet, either (a) create a stub model for the target, or (b) omit the FK mapping from the ORM and add a comment. Option (b) is safer for phased builds.

---

## [2026-05-27] — NoReferencedTableError: Transaction.receipt_id → receipts

**Symptom:** `POST /transactions` returned `500 Internal Server Error` the first time it was hit after Phase 3 was deployed to Docker. FastAPI startup logs showed `sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'transactions.receipt_id' could not find table 'receipts' in this MetaData`.

**Root cause:** The `Transaction` ORM model included `receipt_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True)`. The `Receipt` ORM model is Phase 4 work. SQLAlchemy resolves FK targets at metadata-load time (import), not at query time — no `Receipt` mapper meant the FK target `receipts` was unknown.

**Fix:** Removed the `receipt_id` mapped_column from `Transaction`. Added a comment: `# receipt_id column exists in the DB (baseline schema) but the Receipt ORM model is added in Phase 4. Omitting the FK mapping here avoids a NoReferencedTableError at startup. Phase 4 will re-add this once the Receipt model is registered.`

**Phase 4 action:** After creating `api/api/models/receipt.py` and importing `Receipt` in `models/__init__.py`, restore `receipt_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="SET NULL"), nullable=True)` in `Transaction`.

**Time lost:** ~10 minutes.

**How to avoid next time:** Same as the `matched_policy_id` entry above — omit FK mappings for tables whose ORM models don't exist yet, and add a dated comment pointing to the phase that will restore them.

---

## [2026-05-27] — SQLAlchemy DeclarativeBase reserves 'metadata' as a special attribute

**Symptom:** Importing `api.models.audit_log` crashed the FastAPI startup with `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API`.

**Root cause:** SQLAlchemy's `DeclarativeBase` internally uses a class attribute called `metadata` (it holds the `MetaData` object used for schema reflection). Defining `metadata: Mapped[dict] = mapped_column(JSONB, ...)` on any model that inherits from `Base` collides with this reserved name.

**Fix:** Renamed the Python attribute to `log_metadata` while keeping the DB column name as `"metadata"` using the explicit column name argument: `mapped_column("metadata", JSONB, ...)`. Every reference to the attribute in `card_service.py` uses `log_metadata`.

**Time lost:** ~10 minutes.

**How to avoid next time:** When DB column names clash with Python/SQLAlchemy reserved words (`metadata`, `query`, `registry`), always use the `mapped_column("<db_col_name>", ...)` positional argument to decouple the Python attribute name from the DB column name.

---

## [2026-05-27] — Audit log schema mismatch between briefing and actual DDL

**Symptom:** Pre-Phase 2 briefing described `audit_log` as having columns `old_value (JSONB nullable), new_value (JSONB nullable), ip, user_agent`. The baseline migration (`0001_baseline.py`) has none of these — the actual columns are `id, org_id, actor_user_id, action, entity_type, entity_id, metadata (JSONB NOT NULL default {}), created_at`.

**Root cause:** The briefing document was written at project start, before the actual migration DDL was finalized. The DDL in the migration is authoritative; the briefing document drifted.

**Fix:** Read the actual migration DDL before writing the ORM model, not the briefing. The model was written against the real schema — no code was written against the incorrect briefing. `docs/MASTER_PLAN.md` rule upheld: "the code is the source of truth; the docs follow the code."

**Time lost:** 0 (caught before writing code).

**How to avoid next time:** For any table whose schema is described in both a doc and a migration, always open the migration file and cross-check before writing the ORM model.

---

## [YYYY-MM-DD] — Example: Alembic migration silently dropped enum value

**Symptom:** After renaming `TRAVEL` to `BUSINESS_TRAVEL` in `spend_category`, the API started returning `500` on any transaction list call. Logs showed `LookupError: 'TRAVEL' is not among the defined enum values`.

**Root cause:** Postgres `ENUM` types can have values added (`ALTER TYPE ... ADD VALUE`) but not renamed in a single statement. Alembic's autogenerate produced a migration that looked like a rename but actually dropped+recreated the type, losing historical rows still labeled `TRAVEL`.

**Fix:** Reverted the migration. Wrote a manual one that (1) `ALTER TYPE spend_category ADD VALUE 'BUSINESS_TRAVEL'`, (2) `UPDATE transactions SET category='BUSINESS_TRAVEL' WHERE category='TRAVEL'`, (3) left the old value in the enum (Postgres can't remove enum values without recreating the type).

**Time lost:** ~90 minutes.

**How to avoid next time:** Never trust Alembic autogenerate for enum changes. Hand-write enum migrations and review the generated SQL.

---

## [2026-05-27] — asyncpg rejects multi-statement DDL in Alembic migration

**Symptom:** `alembic upgrade head` crashed on first run with `asyncpg.exceptions.PostgresSyntaxError: cannot insert multiple commands into a prepared statement`.

**Root cause:** asyncpg uses prepared statements under the hood. A single `op.execute()` call with multiple `;`-separated DDL statements is treated as one prepared statement — which asyncpg refuses.

**Fix:** Added a `_run(sql)` helper in the baseline migration that splits the SQL string into individual statements (semicolon-delimited, with a `$$`-dollar-quote-aware parser to skip `plpgsql` function bodies) and calls `op.execute()` once per statement.

**Caveat:** The splitter is functional but fragile for future migrations. Prefer one `op.execute()` call per statement going forward, or use `sqlparse.split()`.

**Time lost:** ~45 minutes.

---

## [2026-05-27] — Missing Department ORM model caused every user insert to 500

**Symptom:** `POST /auth/signup` returned `500 Internal Server Error` immediately after the asyncpg fix. Logs showed `sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'users.department_id' could not find table 'departments'`.

**Root cause:** `User` has a FK to `departments.id`, but no `Department` SQLAlchemy model was registered. The migration had created the table; SQLAlchemy just didn't know about it and couldn't resolve the FK during flush.

**Fix:** Created `api/api/models/department.py` and registered `Department` in `api/api/models/__init__.py`.

**Time lost:** ~10 minutes.

---

## [2026-05-27] — Refresh token hash collision (unique violation) when issued in same second

**Symptom:** `POST /auth/refresh` returned `500` with `asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "refresh_tokens_token_hash_key"` when a new refresh token was issued within the same second as a prior one.

**Root cause:** The refresh JWT payload was `{sub, type, iat, exp}` only. HS256 is deterministic — same payload + same secret = identical token = identical SHA-256 hash. The `token_hash` column is `UNIQUE`, so the second insert collides.

**Fix:** Added `"jti": str(uuid4())` to the refresh token payload in `api/api/utils/security.py`, making each token cryptographically unique regardless of timing.

**Time lost:** ~15 minutes.

---

## [2026-05-27] — Login crashes with 500 when two orgs share the same email

**Symptom:** `POST /auth/login` returned `500 Internal Server Error`. Logs showed `sqlalchemy.exc.MultipleResultsFound`. Reproducible by signing up two orgs with the same email address, then logging in with that email.

**Root cause:** `auth_service.login()` queried `SELECT … WHERE email = ?` with no `org_id` filter. The DB schema allows `UNIQUE (org_id, email)` per-org, so two orgs CAN share an email. `scalar_one_or_none()` raises `MultipleResultsFound` when the query returns more than one row.

**Fix (two-part):**
1. `signup()` now checks for any existing user with the same email across all orgs before creating. Returns `409` if found — enforcing global email uniqueness at the app layer.
2. `login()` catches `MultipleResultsFound` and converts it to a `401`, so it cannot 500 even if stale duplicate rows exist.

**Residual risk:** The global uniqueness check in `signup()` is a SELECT then INSERT — a concurrent signup race can still produce duplicates. No global `UNIQUE(email)` constraint exists in the DB (only per-org). For demo scale, the app-layer check is sufficient; add a `UNIQUE(email)` migration index before going multi-tenant in production.

**Time lost:** ~20 minutes.

---

## [2026-05-27] — Login timing oracle: missing users returned faster than wrong-password users

**Symptom:** Not a crash — a security issue. `POST /auth/login` with a non-existent email returned in ~1ms; with an existing email and wrong password it returned in ~80ms (bcrypt cost). An attacker could enumerate valid emails by measuring response time.

**Root cause:** `auth_service.login()` short-circuited on `user is None` before calling `verify_password`, skipping the bcrypt round entirely for missing users.

**Fix:** Added `_DUMMY_HASH` computed once at module import time (`hash_password("__vault_timing_guard__")`). When `user is None`, `verify_password(password, _DUMMY_HASH)` runs before the `raise HTTPException` — paying the full bcrypt cost on every code path.

**Time lost:** 0 (caught in code review, not from a live incident).

---

## [2026-05-27] — Refresh token rotation race: concurrent /refresh calls both succeeded

**Symptom:** Two simultaneous `POST /auth/refresh` calls with the same refresh token both returned 200 with new access tokens. Only one should succeed; the other should get 401.

**Root cause:** `refresh_tokens()` read the row, checked `revoked_at is None`, marked it revoked, then committed — all without a row-level lock. Two concurrent requests both passed the `revoked_at is None` check before either committed.

**Additional issue:** Even after adding `with_for_update()`, SQLAlchemy's identity map could return a cached (pre-lock) version of the row to the second waiter, making it appear unrevoked even after the lock was granted.

**Fix:** Added `.with_for_update().execution_options(populate_existing=True)` to the `select(RefreshToken)` in `refresh_tokens()`. The lock serializes concurrent requests; `populate_existing=True` forces SQLAlchemy to re-read the row from the DB after acquiring the lock, bypassing the identity map cache.

**Time lost:** 0 (caught in code review).

---

## [2026-05-27] — Frontend `npm run build` failed: `Property 'env' does not exist on type 'ImportMeta'`

**Symptom:** `docker compose exec web npm run build` failed with TypeScript error at `web/src/lib/api.ts:4`: `Property 'env' does not exist on type 'ImportMeta'`. Dev server worked fine because Vite injects the types at runtime.

**Root cause:** `tsconfig.json` had no `"types"` field, so `tsc` had no knowledge of Vite's `ImportMeta.env` augmentation. The `vite/client` type package provides this augmentation but was not included.

**Fix:** Added `"types": ["vite/client"]` to `compilerOptions` in `web/tsconfig.json`. Also created `web/src/vite-env.d.ts` with `/// <reference types="vite/client" />` as an explicit reference (belt-and-suspenders).

**Caution:** Adding `"types": ["vite/client"]` restricts TypeScript's auto-inclusion to ONLY that package. If any code relied on ambient `@types/node` globals, those would break. Verified `tsc -b` passes clean.

**Time lost:** ~10 minutes.

---

## [2026-05-27] — `.env` email-validator rejects `.test` TLD during smoke tests

**Symptom:** First smoke test signup (`verify@phase1.test`) returned `422 Unprocessable Entity` with `value is not a valid email address: The part after the @-sign is a special-use or reserved name`.

**Root cause:** Pydantic's `EmailStr` (via `email-validator`) performs strict RFC-compliant TLD validation. `.test` is an IANA reserved TLD and is explicitly rejected.

**Fix:** Use real-looking domains in all tests and seeds (`@acme.com`, `@verifyco.com`). Do not relax `EmailStr` globally — the strict validation is correct behaviour for a production-shaped app.

**Time lost:** ~5 minutes.

---

<!-- Add new entries above this line, newest first. -->
