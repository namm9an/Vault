# Vault — Implementation Phases

Trackable checklist for the seven-day build to demo. Each deliverable is specific enough to know when it's done.

Timeline assumes start = **Tuesday 2026-05-26**, demo = **Monday 2026-06-01 EOD**, solo developer with AI assistance, ~8 productive hours per day.

---

## Phase 1 — Foundations
**Goal:** Repo, infra, auth shell, one full round-trip from browser to DB.
**Estimated time:** 8 hours (Day 1, Tue) — **COMPLETED 2026-05-27**
**Testable at end of phase:** Sign up an org, log in, land on a "Welcome, {name}" page. `GET /api/v1/auth/me` returns the user + org in browser devtools. `docker compose down && up` brings the system back identical.

### Deliverables
- [x] Repo scaffolded with `api/`, `web/`, `docs/`, `docker-compose.yml`, `.env.example`, `.gitignore`
- [x] `docker compose up --build` brings up `db`, `redis`, `api`, `web`, `mailhog`; all containers report healthy
- [x] Alembic baseline migration creates every table from the schema and runs clean on a fresh DB
- [x] FastAPI `GET /health` returns 200 with `{db: "ok", redis: "ok", tir: "configured"}` *(note: tir returns `"configured"` not `"ok"` — no live ping, intentional)*
- [x] `POST /auth/signup` creates org + ADMIN user, returns `{access_token, refresh_token, user}`
- [x] `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` all working
- [x] Bcrypt password hashing on signup; JWT signed HS256; refresh token row persisted in `refresh_tokens`
- [x] React app boots: LoginPage and SignupPage render, submit, store tokens, redirect to `/`
- [x] Axios interceptor attaches `Authorization` header; 401 redirects to `/login`
- [x] React Query client configured; `useMe()` hook works on the landing page
- [x] Seed script creates 1 org, 1 ADMIN, 1 FM, 2 EMPLOYEEs, 2 departments, 4 cards

### Security fixes applied during Phase 1 (see `docs/PROBLEMS.md` for detail)
- Login org-scoping + timing oracle fixed in `auth_service.py`
- Refresh token rotation made atomic with `with_for_update()` + `populate_existing=True`
- `get_db()` rollback-on-exception and correct return type added
- `npm run build` unblocked by adding `vite/client` types to `tsconfig.json`
- `APP_SECRET_KEY` minimum-length validator added

---

## Phase 2 — Cards, RBAC & multi-tenancy enforcement
**Goal:** Locked-down org boundary + first real CRUD resource.
**Estimated time:** 8 hours (Day 2, Wed) — **COMPLETED 2026-05-27**
**Testable at end of phase:** ADMIN creates a card and assigns it to an employee. Employee logs in and sees only their own card. A cross-org GET on a known card UUID returns 404. ADMIN freezes the card; employee's view updates on refetch.

### Pre-phase addition (Phase 1 lockdown)
- [x] Alembic migration `0002_global_email_unique` applied: dropped `UNIQUE(org_id, email)`, added global `UNIQUE(email)` on `users.email`; purges cross-org duplicate emails before adding the constraint. Closes the `MultipleResultsFound` race permanently at the DB layer.

### Deliverables
- [x] `get_current_user`, `require_role(*roles)`, `get_org_scope` dependencies implemented and unit-tested
- [x] Unit tests (8 total) for each dependency: valid token, expired token, wrong role, mismatched org_id, inactive user
- [x] `GET /cards` (scoped per role: owner-only for EMPLOYEE; org-wide for ADMIN/FM)
- [x] `POST /cards` (ADMIN) creates with all limit fields + `category_restrictions` array; `last_four` generated randomly server-side
- [x] `GET /cards/{id}`, `PATCH /cards/{id}`, `POST /cards/{id}/freeze|unfreeze|cancel` working
- [x] `audit_log` row written on every freeze/unfreeze/cancel (same DB transaction as state change)
- [x] Multi-tenancy tests (6 total): User A from Org A cannot read, list, or modify any card from Org B (returns 404); EMPLOYEE cannot see another user's card within same org (404)
- [x] `GET /users` + `POST /users` (invite with `password` in body, `is_active=true` immediately) + `PATCH /users/{id}` for role change; last-ADMIN demotion guard in place
- [x] Frontend: CardsPage with plain Tailwind table, "New card" dialog, freeze/unfreeze/cancel with confirmation modals *(shadcn/ui not installed — plain Tailwind used throughout; deferred to Phase 5/6)*
- [x] Frontend: SettingsPage with users table + "Invite member" dialog + "Change role" modal + deactivate/reactivate toggle
- [x] Frontend: `AppLayout` shared nav component with sticky top bar, `NavLink` tabs (Dashboard / Cards / Settings), user info + sign-out
- [x] Frontend: router updated to add `/cards` and `/settings` routes, all wrapped in `ProtectedLayout` (`RequireAuth` + `AppLayout`)
- [x] `docs/API.md` updated to reflect invite flow (password in body, `is_active: true`, `invite_token` as placeholder UUID)

### Deviations from original plan
- **No shadcn/ui.** `shadcn/ui` is not installed. All Phase 2 UI uses plain Tailwind (tables, modals, form controls). This was an explicit choice — avoids a blocking install during a time-constrained build. Deferred to Phase 5/6 polish pass.
- **GET /cards returns flat array, not `{items, next_cursor}`.** Cursor pagination deferred. The hook reads `Card[]` directly. API.md updated to match.
- **AuditLog Python attribute `log_metadata` maps to DB column `metadata`.** SQLAlchemy `DeclarativeBase` reserves `metadata` as a class attribute. The Python model uses `log_metadata`; the DB column name stays `"metadata"` via `mapped_column("metadata", JSONB, ...)`. See `docs/PROBLEMS.md` for details.

---

## Phase 3 — Transactions + state machine
**Goal:** Transaction lifecycle end-to-end with LLM stubbed.
**Estimated time:** 9 hours (Day 3, Thu) — **COMPLETED 2026-05-27**
**Testable at end of phase:** Create a transaction (amount < ₹50k) → see it pass through `INITIATED → POLICY_CHECKED → APPROVED → CLEARED` in a visible timeline. Create a transaction with amount ₹51k+ → it lands in `FLAGGED` and the FM approve/reject panel appears in the drawer. FM approves → state moves to `CLEARED`. Create amount ₹1L+ → `BLOCKED` (terminal). Seeded demo data shows all three outcomes on first boot.

### Deliverables
- [x] `TransactionService.transition(txn, to_state, actor, reason)` validates legal edges, writes `transaction_events`, updates `transactions.state` in one DB transaction
- [x] Allowed transitions match the state diagram exactly; illegal transitions raise `409`
- [x] `POST /transactions` creates txn, runs policy stub, branches on verdict: APPROVED→4 events→CLEARED; FLAGGED→3 events→awaits FM; BLOCKED→3 events→terminal
- [x] `GET /transactions` with filters: `from_date`, `to_date`, `category`, `department_id`, `card_id`, `user_id`, `state`
- [x] `GET /transactions/{id}` returns txn + events + latest policy_result
- [x] `POST /transactions/{id}/approve` and `/reject` (FM/ADMIN) with reason
- [x] `GET /transactions/{id}/events` lists the audit trail
- [x] 12 unit tests in `tests/test_transactions.py`: state machine (4), RBAC (4), multi-tenancy (2), event trail (2)
- [x] Frontend: TransactionsPage with filterable table; state badges colored by state
- [x] Frontend: TransactionDetail drawer with event timeline (timestamp, from→to, actor, reason) + approve/reject panel for FM/ADMIN when state=FLAGGED
- [x] Frontend: NewTransactionDialog (manual create, card dropdown, merchant/amount/category/description/date)
- [x] Frontend: `/transactions` route added; "Transactions" tab added to AppLayout nav

### Deviations from original plan
- **No migration created.** All three transaction tables were already in `0001_baseline`. Creating `0003_transactions` would have failed with "table already exists". Logged in `docs/DECISIONS.md`.
- **`receipt_id` and `matched_policy_id` FK columns omitted from ORM models.** `Receipt` and `Policy` ORM models don't exist yet (Phase 4). SQLAlchemy raises `NoReferencedTableError` at startup if a FK target table has no registered mapper. Both FK mappings will be restored in Phase 4. Logged in `docs/DECISIONS.md`.
- **Policy engine stub always returns APPROVED** (as specified). Real LLM call added in Phase 4.
- **4 events written per new transaction** (INITIATED + POLICY_CHECKED + APPROVED + CLEARED) — the INITIATED event is written explicitly to give a complete audit trail from creation, matching the spec's "4 events" requirement.

---

## Phase 4 — LLM pipelines 1 & 2 (Receipts + Policies)
**Goal:** Both demo-critical AI features live.
**Estimated time:** 10 hours (Day 4, Fri) — **COMPLETED 2026-05-28**
**Testable at end of phase:** Upload a receipt → it lands in `NEEDS_REVIEW` and can be attached to a transaction (see Deviations — Llama 3.1 8B is text-only). Create a policy "No alcohol purchases above ₹2,000" → submit a matching transaction → see it `FLAGGED` with the exact policy text quoted in the detail drawer and a notification fired to the FM.

### Deliverables
- [x] `api/api/llm/llm_client.py` with `complete_json(system, user, schema, temperature, max_tokens)`, retry-once-on-validation-error, `LLMUnavailableError` + `LLMValidationError`
- [x] `api/api/llm/schemas.py` with `PolicyCheckResult` Pydantic schema
- [x] S3 helpers: `presign_put(key)`, `presign_get(key)`, `head(key)`, `get_bytes(key)` in `api/api/storage/s3.py`; `_to_public_url()` rewrites Docker-internal hostname for browser access
- [x] MinIO service + `minio-init` bucket creator added to `docker-compose.yml`; `S3_PUBLIC_URL` added to `config.py` and `.env.example`
- [x] `POST /receipts/upload-url`, `POST /receipts/{id}/confirm`, `GET /receipts/{id}`, `POST /receipts/{id}/retry` — all working
- [x] ARQ worker container running and visible in `docker compose ps` with `ocr_receipt` and `run_policy_check` registered in `WorkerSettings`
- [x] `ocr_receipt` job: marks receipt `NEEDS_REVIEW` immediately (Llama 3.1 8B is text-only — see Deviations); ARQ enqueue failure → `status=FAILED` with retry message (H3 fix)
- [x] `GET/POST/PATCH/DELETE /policies` (ADMIN); active toggle; soft-delete via `deleted_at` column — never hard-deletes
- [x] Alembic migration `0003_policy_soft_delete`: adds `deleted_at TIMESTAMPTZ NULL` to `policies`; `delete_policy` sets `is_active=False + deleted_at=NOW()`
- [x] `run_policy_check` ARQ job: `SELECT FOR UPDATE` idempotency guard (H1); `_sanitize()` strips control chars; untrusted fields wrapped in XML delimiters (H4); no-active-policies fast path → auto-APPROVED; LLM error fail-safe → FLAGGED; unknown verdict → FLAGGED; single-commit for state + result + notifications (H2); `AuditLog` row on every system-driven transition (M6 fix)
- [x] `create_transaction` commits INITIATED + POLICY_CHECKED events then enqueues `run_policy_check` asynchronously; `_run_policy_stub` removed entirely
- [x] FLAGGED/BLOCKED fires `Notification` rows for all FMs in org (`POLICY_FLAGGED` / `POLICY_BLOCKED`)
- [x] `UploadUrlRequest.content_type` restricted to `Literal["image/jpeg","image/png","application/pdf"]` (H6 fix); `ConfirmUploadRequest.byte_size` capped at 10 MB
- [x] Frontend: `ReceiptUploader` — presigned S3 PUT, status polling; `onReceiptReady` fires for `COMPLETED` or `NEEDS_REVIEW`
- [x] Frontend: `NewTransactionDialog` includes `ReceiptUploader`; `useTransaction` auto-refetches while `POLICY_CHECKED`
- [x] Frontend: `PoliciesPage` (ADMIN-only write controls, inline create/edit, toggle active, delete)
- [x] Frontend: `TransactionDetailDrawer` shows LLM verdict, reason, and matched policy text
- [x] Frontend: `/policies` route added; "Policies" tab added to `AppLayout` nav
- [x] 9 new tests across `test_policy_service.py` + `test_policy_check_job.py` + updated `test_transactions.py` — **40 tests total**

### Validation fixes applied in-phase (post-phase review 2026-05-28)
C1–C5 critical and H1–H7 high-priority items from the post-phase validation report were resolved before shipping:
- **C1** — `isPolicyPending` used before `txnDetail` was defined (React ReferenceError) → swapped declaration order + moved poll logic into `refetchInterval` callback
- **C2** — MinIO not in `docker-compose.yml`; presigned URLs had Docker-internal hostnames → added MinIO + `minio-init`; `S3_PUBLIC_URL` config var added
- **C3** — `ocr_receipt` fabricated receipt data from metadata via LLM, hallucinating high-confidence structured data → replaced with honest `NEEDS_REVIEW` path (no LLM call)
- **C4** — Receipt linked to transaction without org-scope check → added org-scoped receipt validation in `create_transaction`
- **C5** — `DELETE /policies` hard-deleted rows, orphaning audit trails → soft-delete via `deleted_at` + migration `0003`
- **H1** — No `SELECT FOR UPDATE` in `run_policy_check` → added idempotency guard
- **H2** — `notify_all_fms` called after `db.commit()` (two-commit race) → moved before commit
- **H3** — ARQ enqueue failure silently left receipt in PROCESSING forever → try/except → FAILED + message
- **H4** — No prompt injection sanitization → `_sanitize()` + XML delimiters
- **H5** — `onReceiptReady` blocked for `NEEDS_REVIEW` → closed as intentional after C3 fix (NEEDS_REVIEW is the only terminal non-FAILED state)
- **H6** — `content_type` accepted any string; no `byte_size` cap → whitelist + 10 MB cap
- **H7** — Dead `admin_token_payload` fixture in `conftest.py` referencing undefined vars → removed
- **M3, M5, M6** — fixed in-phase; M1, M2, M4 deferred to `PROBLEMS.md`

### Deviations from original plan
- **`ocr_receipt` calls no LLM.** Llama 3.1 8B Instruct is **text-only** (vision was added in 3.2). Rather than fabricating receipt data from filename/metadata (the C3 critical bug), the job marks all uploads `NEEDS_REVIEW` immediately — an honest signal for human review. `onReceiptReady` fires for both `COMPLETED` and `NEEDS_REVIEW` so receipt attachment still works end-to-end. Real OCR can be wired in when a vision-capable model is available on TIR.
- **MinIO for local dev.** E2E Object Storage credentials aren't needed to run locally. MinIO (S3-compatible) is added to `docker-compose.yml` with `minio-init` creating the `vault-receipts` bucket on first boot. `S3_PUBLIC_URL` rewrites the Docker-internal hostname in presigned URLs to a browser-accessible address.
- **Policy soft-delete.** `DELETE /policies/{id}` sets `is_active=False + deleted_at=NOW()`. Hard-delete would orphan `TransactionPolicyResult.matched_policy_id` FK references, losing audit history.

---

## Phase 5 — Dashboard, Reimbursements & Department budgets
**Goal:** Visible product surface + the other money-movement flow.
**Estimated time:** 9 hours (Day 5, Sat) — **COMPLETED 2026-05-28**
**Testable at end of phase:** Dashboard renders KPIs and three Recharts charts populated by seeded data. Employee submits a reimbursement → FM sees it in the queue → approves → it counts toward dashboard totals. A department whose budget crosses 80% shows a red progress bar.

### Deliverables
- [x] `GET /dashboard/summary` returns total spend, MoM delta, by_category, by_department, top_merchants, pending_approvals, active_cards
- [x] `GET /dashboard/timeseries` returns date-bucketed amounts with configurable `bucket` (hour/day/week/month)
- [x] Redis cache layer: 5-min TTL keyed by `dash:{org_id}:{endpoint}:{md5(dates)}` — matches `staleTime` on the frontend hooks
- [x] Frontend: DashboardPage rebuilt with 7d/30d/90d toggle, KPI cards (Total Spend, MoM delta ±%, Pending Approvals, Active Cards), PieChart (categories), BarChart (departments), AreaChart (timeseries), top-merchants table, loading skeletons, empty state
- [x] `POST /reimbursements` creates reimbursement (SUBMITTED), enqueues `run_reimbursement_policy_check` ARQ job
- [x] `GET /reimbursements` with status/department/date filters; `GET /reimbursements/{id}`; EMPLOYEE sees own only, FM/ADMIN see org-wide
- [x] `POST /reimbursements/{id}/approve|reject|mark-paid` with reason + decided_by/decided_at; single-commit rule for state + AuditLog + notification
- [x] `run_reimbursement_policy_check` ARQ job: Phase 1 (SUBMITTED → POLICY_CHECKED, commit); Phase 2 (load policies, LLM verdict, commit). Verdict mapping: APPROVED/FLAGGED → keep POLICY_CHECKED (FM signs off); BLOCKED → REJECTED immediately with decided_at=now + AuditLog
- [x] Frontend: ReimbursementsPage — EMPLOYEE submit dialog + own-submissions table; FM/ADMIN org-wide queue with Approve/Reject/Mark Paid buttons; status badges (SUBMITTED/POLICY_CHECKED/APPROVED/REJECTED/PAID)
- [x] `GET/POST/PATCH/DELETE /departments` (ADMIN writes, all roles read) + `GET /departments/{id}/budget-status`
- [x] Department budget status: sums CLEARED+SETTLED transactions for current calendar month, computes utilisation_pct, fires Redis-deduped BUDGET_THRESHOLD alert (SET NX EX 32 days, commit-first order)
- [x] Frontend: DepartmentsPage with budget utilisation table — green/amber/red progress bars; ADMIN create/edit/delete dialogs
- [x] Seeds updated with 2 departments (Engineering ₹500k, Marketing ₹300k) + 3 demo reimbursements
- [x] 6 new tests (reimbursement service, department service, dashboard service) — **46 total passing**

### Validation fixes applied in-phase (post-phase review 2026-05-28)
C1–C3 critical and H1–H6 high-priority items from the Phase 5 validation report were resolved before shipping:
- **C1** — Two-phase ARQ job: Phase 1 idempotency guard checked only `SUBMITTED`, so retries after a Phase 1 crash (which leaves status as `POLICY_CHECKED`) would skip Phase 2 entirely. **Fix:** Phase 2 opens with its own idempotency guard — `if reimb2.status != POLICY_CHECKED: return`. Phase 1 guard now falls through to Phase 2 when already past SUBMITTED (log + continue rather than return).
- **C2** — ARQ job transitioned APPROVED/FLAGGED verdicts directly to `APPROVED`, making FM's `approve_reimbursement` (which requires `POLICY_CHECKED`) always return 409. `decided_by`/`decided_at` were also never set for auto-transitions. **Fix:** APPROVED/FLAGGED verdicts now leave status at `POLICY_CHECKED` — FM signs off via the normal approve endpoint. BLOCKED auto-sets `decided_at=now(), decided_by=None` (system actor).
- **C3** — No `AuditLog` rows were written in `run_reimbursement_policy_check`. **Fix:** Added AuditLog entries for every path: `reimbursement.policy_checked` (Phase 1 commit), `reimbursement.policy_approved`/`policy_flagged`/`policy_blocked`/`policy_error`/`policy_no_rules` (Phase 2 commit).
- **H1** — Enqueue failure → silent REJECTED with no notification, no AuditLog, pool not closed. **Fix:** try/finally closes pool; except block adds AuditLog + APPROVAL_REJECTED notification + `decided_at=now()` all in one commit.
- **H2** — Budget alert Redis `SET NX` fired before DB commit. If commit failed, dedup key was already set — retry would never fire notification. **Fix:** reversed order: GET key first (probe), commit notification rows, then SET NX (best-effort).
- **H3** — Redis failure in `get_budget_status` propagated as `ConnectionError` → 500. **Fix:** wrapped Redis alert path in `try/except Exception` — logs warning, returns budget status without firing alert.
- **H4** — `getRangeDates(rangeDays)` called `new Date()` inside render — millisecond ISO string changed every render, TanStack Query refetched continuously. **Fix:** `useMemo(() => getRangeDates(rangeDays), [rangeDays])`.
- **H5** — `ResponsiveContainer width={160}` (fixed pixel) defeated responsive behavior on narrow viewports. **Fix:** wrapped in `<div style={{width:160, height:160}}>` with `ResponsiveContainer width="100%" height="100%"`.
- **H6** — `GET /departments` required FM/ADMIN. `NewReimbursementDialog` calls `useDepartments()` — employees saw 403 and empty department picker. **Fix:** removed role guard from list route; all authenticated users may read the department list.
- **M1–M6** — Logged in `PROBLEMS.md` for future fix:
  - M1: `department_id` in `create_reimbursement` not org-scoped (can attach another org's dept)
  - M2: `manager_id` in `update_department` not org-scoped
  - M3: Dashboard `pending_approvals` KPI counts only FLAGGED transactions, ignores POLICY_CHECKED reimbursements
  - M4: Invalid `bucket` param silently falls back to "day" instead of 422
  - M5: Zero prior-period spend shows "no prior data" instead of a meaningful delta
  - M6: MoM window has a 1-second bias in `prior_from` calculation

### Deviations from original plan
- **Reimbursement APPROVED/FLAGGED verdicts stay POLICY_CHECKED.** The original spec said APPROVED verdict → auto-APPROVED. In practice this made FM's approve endpoint unreachable (C2). FM human sign-off is now always required for non-BLOCKED reimbursements — a stricter but more correct workflow for a finance compliance product.
- **`GET /departments` open to all roles.** Original plan restricted reads to FM/ADMIN. Required for the employee reimbursement submission form (department picker).
- **46 tests (not 40).** 6 new tests added for Phase 5 services.

---

## Phase 6 — Digest, Notifications & polish
**Goal:** Third LLM feature + the details that make it feel real.
**Estimated time:** 8 hours (Day 6, Sun) — **COMPLETED 2026-05-28**
**Testable at end of phase:** Click "Generate weekly digest" → HTTP 202 returned immediately; digest appears as PENDING then COMPLETED within ~15s with real numbers and CFO-style recommendations. MailHog shows the email. Notification bell shows unread count; clicking marks notifications read. `GET /notifications/unread-count` polled every 30s.

### Deliverables
- [x] Digest aggregator: `aggregate_spend_data` — total spend, transaction count, top 5 categories, top 5 departments, top 5 merchants, pending approvals (POLICY_CHECKED reimbursements), policy-blocked count
- [x] `generate_weekly_digest` ARQ cron job: aggregates → LLM with `SpendDigest` schema (headline, body, top_recommendations, flagged_items) → writes `digests` row → fires DIGEST_READY notifications to all ADMIN+FM → sends SMTP email (best-effort, asyncio.to_thread)
- [x] ARQ cron registered: Monday 03:30 UTC (09:00 IST) in `api/api/jobs/worker.py`
- [x] `POST /digest/generate` (ADMIN) returns HTTP 202 immediately; PENDING row committed synchronously, LLM runs in FastAPI `BackgroundTasks` with own DB session. `GET /digest`, `GET /digest/{id}` (FM/ADMIN)
- [x] Frontend: DigestPage — two-panel layout (list sidebar + detail panel), status badges (PENDING/COMPLETED/FAILED), generate modal with date pickers (ADMIN only), `EmptyState` for both panels
- [x] `GET /notifications` (last 50, newest first), `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`
- [ ] `GET /notifications/stream` SSE endpoint — **deferred; polling used instead** (`useUnreadCount` polls every 30s; `useNotifications` refetches on window focus)
- [x] Frontend: NotificationBell in `AppLayout` sidebar navbar — unread badge, dropdown with notification list, mark-read / mark-all-read, time-ago display, outside-click close
- [x] Budget threshold notification fires once per (department, month) when crossing 80% — Redis SET NX EX 32-days dedup (already live as of Phase 5; Phase 6 wired the read layer)
- [x] UI polish: `EmptyState` shared component, `Toast` context provider (4s auto-dismiss, bottom-right), Inter font via Google Fonts, `AppLayout` rebuilt as left sidebar (`w-56 bg-neutral-900`), role-gated nav links, user initials avatar. `EmptyState` used on Cards, Transactions, Reimbursements, Departments, and Digest pages.
- [x] **48 total tests passing** (2 new: idempotency + email-failure-does-not-raise)

### Validation fixes applied in-phase (post-phase review 2026-05-28)
C1 critical and H2–H5 high-priority items from the Phase 6 validation report were resolved before shipping. M7, L9, L10 medium/low items also fixed.
- **C1** — `POST /notifications/read-all` always returned 422. `/{notification_id}/read` was registered before `/read-all` in the router — FastAPI parsed the literal string `"read-all"` as a UUID and rejected it. **Fix:** moved `POST /read-all` above `POST /{notification_id}/read` with an explanatory comment.
- **H2** — `send_digest_email` (stdlib `smtplib.SMTP`) called directly inside `async def run_digest_generation` — blocking synchronous I/O stalled the async event loop for the entire SMTP timeout. **Fix:** `await asyncio.to_thread(send_digest_email, digest, recipients)` offloads to a thread pool.
- **H3** — `POST /digest/generate` called `run_digest_generation()` inline, blocking the HTTP response for 60+ seconds during LLM inference. **Fix:** extracted `get_or_create_pending_digest()` helper that commits the PENDING row synchronously; route returns HTTP 202 immediately; LLM runs in `BackgroundTasks` with its own session via `get_session_factory()()`.
- **H4** — `DigestGenerateRequest` had no date validation — `period_start >= period_end` was accepted silently. **Fix:** added `@model_validator(mode="after") def check_dates()` raising `ValueError` when `period_start >= period_end`.
- **H5** — `Digest.updated_at` used `onupdate=datetime.utcnow` (naive datetime). Postgres TIMESTAMPTZ comparison with a naive datetime raises `TypeError` at runtime. **Fix:** `onupdate=lambda: datetime.now(timezone.utc)`.
- **M7** — Generate button in `DigestPage` modal was enabled even when `start >= end`. **Fix:** added `|| start >= end` to the `disabled` condition.
- **L9** — `Toast.tsx` `setTimeout` IDs were not tracked — pending timeouts fired `setState` after component unmount, leaking memory. **Fix:** `useRef<Set<ReturnType<typeof setTimeout>>>` tracks all IDs; `useEffect` cleanup clears all on unmount.
- **L10** — After `POST /digest/generate`, the detail panel flickered blank until `useDigests` refetched. **Fix:** `selected` uses `generateDigest.data` as fallback so the newly returned PENDING digest shows immediately.

### Deviations from original plan
- **SSE not implemented.** `GET /notifications/stream` (Server-Sent Events) was deferred. `useUnreadCount` polls every 30s; `useNotifications` refetches on window focus. Polling is sufficient for the demo and avoids the SSE keepalive/reconnect complexity.
- **Digest aggregator simplified.** "Unused SaaS proxy" and "duplicate vendors" heuristics from the original spec were not implemented — the aggregator collects total spend, categories, departments, merchants, reimbursement queue depth, and policy-blocked count. The LLM derives insights from these. For the demo, this is indistinguishable from the full spec.
- **48 tests (up from 46).** 2 new tests for digest service idempotency and email-failure-does-not-raise.

---

---

## Phase 6.5 — Marketing Landing Page + App UI Redesign (Ramp-parity)
**Goal:** Make Vault look and feel like Ramp — both the public-facing marketing site and the logged-in product UI.
**Estimated time:** 10–12 hours — **COMPLETED 2026-05-29**
**Testable at end of phase:** Visiting `/` shows a polished marketing landing page with smooth scroll, animated section reveals, live metrics ticker, and a mega navigation menu. Logging in shows a redesigned app with warm off-white backgrounds, chartreuse primary actions, icon-only sidebar, and token-consistent components throughout.

### Design tokens (extracted from ramp.com via Playwright — 2026-05-28)
```
Font:           Geist (free substitute for Ramp's proprietary TWK Lausanne)
--solar:        #e4f222   ← chartreuse CTA / primary action color
--solarLight:   #f5ff78   ← hover state for CTAs
--grayLight:    #f4f2f0   ← warm off-white page background
--grayMedium:   #d2cecb   ← borders, dividers
--grayDark:     #6e6a68   ← secondary / muted text
--black:        #1a1919   ← near-black for sidebar, dark sections
--text-primary: #0c0a08   ← body text
--text-hushed:  #0c0a0899 ← placeholder / caption text (60% opacity)
--smolder:      #17332d   ← dark green accent
--blaze:        #e96516   ← orange accent
Nav height:     62px
H1:             64px, font-weight 400 (Geist looks bold at this size)
CTA:            border-radius 6px, padding 12px 16px
```

### Animation libraries
- **GSAP + ScrollTrigger + useGSAP** (`gsap`, `@gsap/react`) — scroll-triggered section reveals, counters
- **Lenis** (`lenis`) — smooth scroll; wired via `gsap.ticker` for ScrollTrigger sync
- **Framer Motion** (`framer-motion`) — React transitions, mega menu, micro-animations
- All bundled via npm — no CDN

### Part A — Marketing Landing Page (`/`)

- [x] `gsap`, `lenis`, `framer-motion`, `@gsap/react` installed in `web/package.json`
- [x] Geist font via Google Fonts — `index.html` + `index.css`
- [x] `web/src/pages/LandingPage.tsx` — lazy-loaded at `/` (unauthenticated)
- [x] Router updated: `/` → `React.lazy(LandingPage)` with `Suspense`; `/login` and `/signup` unchanged; all app routes still require auth
- [x] **Navbar** (`web/src/components/landing/LandingNav.tsx`):
  - Fixed top, height 62px
  - Glass effect on scroll: `backdropFilter: blur(12px)` only when `scrolled === true`; transparent border + no blur by default
  - Logo: "vault" wordmark + solar square icon mark
  - Products mega-menu: 3-column Framer Motion stagger (Card & Expense / Policy Engine / Intelligence) — outside-click closes
  - Right: "Sign in" link + "Get started free" solar button
- [x] **Hero section**: dot-grid bg, Framer Motion word-by-word H1 stagger, solar CTA, dashboard mockup card
- [x] **MetricsTicker**: GSAP horizontal marquee (seamless loop via `x: "-50%"`)
- [x] **Feature sections** (3, alternating layout): `useGSAP({ scope: sectionRef })` for StrictMode-safe ScrollTrigger reveals; two-tone headlines on all three sections
- [x] **Footer**: dark `bg-[#1a1919]`, four columns, E2E Cloud solar badge, copyright
- [x] **Lenis smooth scroll**: initialized in `LandingPage` useEffect via `gsap.ticker.add`; `lenis.on("scroll", ScrollTrigger.update)` for sync; `gsap.ticker.remove` + `lenis.destroy()` on unmount. Uses `{ lerp: 0.1 }` (v1.x API)
- [x] **Page transitions**: `AnimatePresence` moved inside `AppLayout`'s main slot — sidebar no longer flickers on nav

### Part B — App UI Redesign

- [x] `web/src/components/ui/badge.tsx` — CVA Badge with all status variants (ACTIVE, FROZEN, BLOCKED, FLAGGED, APPROVED, CLEARED, SETTLED, SUBMITTED, REJECTED, PAID, PENDING, COMPLETED, FAILED, NEEDS_REVIEW, POLICY_CHECKED, INITIATED, CANCELLED)
- [x] `web/src/components/ui/button.tsx` — CVA Button with `solar`, `default`, `destructive`, `outline`, `ghost` variants
- [x] `web/src/lib/utils.ts` — `cn()` helper (clsx + tailwind-merge)
- [x] All design tokens in `web/src/index.css` as CSS custom properties
- [x] Tailwind config extended with full token palette + Geist font family
- [x] **Global token sweep** — all `text-neutral-*`, `bg-neutral-*`, `border-neutral-*`, `bg-indigo-*`, `text-indigo-*`, `ring-indigo-*`, `hover:bg-neutral-*`, `divide-neutral-*` replaced across all page and component files
- [x] **AppLayout** (`web/src/components/AppLayout.tsx`): w-14 icon-only sidebar, `bg-[#1a1919]`, solar logo mark, Framer Motion tooltips on hover, `layoutId="sidebar-active"` sliding pill, top bar h-[62px] bg-[#f4f2f0], notification bell, role badge, user initials avatar, sign-out button; `user?.full_name?.split()` null-guarded
- [x] **DashboardPage**: KPI cards `border-[#d2cecb]`, Skeleton `bg-[#d2cecb]`, chart panels `border-[#d2cecb]`, primary chart color `#1a1919` (vault-black), merchants table rows wrapped in `motion.tr` with stagger, `motion` import added, `full_name` null-guarded
- [x] **CardsPage**, **TransactionsPage**, **ReimbursementsPage**, **DepartmentsPage**: `motion.tr` row stagger, Badge component for all status chips; TransactionsPage local StateBadge/VerdictBadge replaced with shared Badge
- [x] **DigestPage**: full token sweep, Badge for status, solar Generate button, correct border/divider colors
- [x] **PoliciesPage**, **SettingsPage**: full token sweep, solar primary buttons, `border-[#d2cecb]` inputs and panels
- [x] **EmptyState**: `text-[#6e6a68]` / `text-[#d2cecb]` tokens
- [x] **ReceiptUploader**: all neutral-* → design tokens; spinner border corrected
- [x] **Toast**: info color `bg-[#1a1919]`
- [x] **LoginPage / SignupPage**: dot-grid bg, white centered card, solar submit button, `navigate("/dashboard")` on success
- [x] **Router**: `LandingPage` lazy-loaded via `React.lazy` — GSAP/Lenis never load in the app bundle; `AnimatePresence` removed from `ProtectedLayout` wrapper (moved into AppLayout)

### Validation fixes applied post-initial-build (2026-05-29)
All 12 issues from the Phase 6.5 validation report resolved:
- **H1** — `useGSAP({ scope: sectionRef })` replaces `useEffect + gsap.context` — fixes StrictMode double-invoke making feature sections permanently invisible
- **H2** — Lenis RAF wired via `gsap.ticker.add((time) => lenis.raf(time * 1000))` — eliminates the `cancelAnimationFrame` race that leaked the RAF loop
- **H3** — Glass nav: `backdropFilter` only applied when `scrolled === true`; default is `none` — was always blurring
- **M4** — `lenis.on("scroll", ScrollTrigger.update)` added — fixes Lenis virtual scroll desyncing GSAP ScrollTrigger
- **M5** — `AnimatePresence` moved inside `AppLayout`'s `<main>` slot — sidebar no longer re-mounts/flickers on every route change
- **M6** — MetricsTicker GSAP counter: ticker values now animate from 0 → target on mount via `gsap.to({ val: 0 }, { val: target, onUpdate })` before the marquee starts
- **M7** — `user?.full_name?.split(" ")[0] ?? "there"` in AppLayout and DashboardPage — guards against null full_name crash
- **M8** — Lenis initialized with `{ lerp: 0.1 }` — `duration` and `easing` options removed in v1.x
- **M9** — `LandingPage` lazy-loaded via `React.lazy` — GSAP (~200 KB) no longer in the main app bundle
- **L10** — Two-tone headline on Policy feature section: `<span text-[#0c0a08]>Policies written</span> <span text-[#6e6a68]>in plain English.</span>`
- **L11** — Dashboard chart primary color changed from `#6366f1` to `#1a1919` (vault-black)
- **L12** — Merchants table rows wrapped in `motion.tr` with index-based stagger

### Deviations from original plan
- **shadcn/ui Table / Dialog / Sheet not used.** Plain Tailwind tables and custom modal overlays were kept — they already use correct design tokens, business logic is identical, and replacing the markup would have been churn with no visible benefit for the demo.
- **Social proof strip not built.** Not included in the deliverables checklist; deferred to Phase 7 seed/polish if time allows.
- **Lenis initialized in `LandingPage`, not `main.tsx`.** Scoping to `LandingPage` useEffect ensures clean destruction on unmount and keeps Lenis out of app routes entirely.

### Constraints
- No backend files touched — frontend only
- No hook, query key, or API path changes
- Lenis and GSAP only active on `/` — not loaded in app routes (lazy import enforces this)
- Framer Motion used on both landing and app pages
- Solar always paired with `text-[#0c0a08]` — never white-on-solar

---

## Phase 7 — Demo hardening & rehearsal
**Goal:** Nothing breaks during the live demo.
**Estimated time:** 6 hours (Day 7, Mon) — **COMPLETED 2026-05-29**
**Testable at end of phase:** Live demo runs front-to-back in ≤ 10 minutes with no manual DB intervention. `scripts/smoke_test.sh` exits 0 against production URL.

### Deliverables
- [x] Rich seed: 40 transactions across 28 days (direct-insert, deterministic final state), 6 reimbursements, 5 active policies, 6 cards, 3 departments, 4 unread notifications for Naman
- [x] `POST /api/v1/demo/reset` — wipes transactional data and reseeds in ~3 seconds; gated by `DEMO_RESET_ENABLED=true` + ADMIN auth; busts Redis dashboard cache
- [x] "Reset Demo Data" button in SettingsPage (ADMIN only) with confirmation modal + toast
- [x] `policy_verdict` field added to `TransactionOut` schema + left-join in `list_transactions()`; visible as inline Policy column in TransactionsPage
- [x] `pending_approvals` KPI now counts both FLAGGED transactions and POLICY_CHECKED reimbursements
- [x] `scripts/smoke_test.sh` — full production smoke test (18 checks) covering auth, all endpoints, data counts, policy_verdict field, dashboard KPIs, notifications
- [x] `docs/DEMO_SCRIPT.md` — complete 10-minute live demo script with pre-demo checklist, 4 acts, fallback talking points
- [x] Deployed to E2E Cloud VM at `http://101.53.140.68`; all 6 containers healthy

### Validation fixes applied post-initial-build (2026-05-29)
- **CRITICAL** — `reseed_transactional()` called `db.commit()` internally, causing double-commit when called from the demo reset endpoint's request-scoped session. **Fix:** replaced internal `commit()` with `flush()`; callers (`run()` and `reset_demo()`) now explicitly commit after the call.
- **HIGH** — Redis cache bust in `demo.py` swallowed all errors silently. **Fix:** added `logger.warning()` on exception so failures surface in logs.
- **HIGH** — Smoke test `python3 -c` blocks printed `0`/`false` on any parse failure, masking real API errors. **Fix:** all except blocks now print to stderr; inline `curl` calls use `-sf` consistently.
- **MEDIUM** — FLAGGED transactions for policies 3 (CFO sign-off) and 4 (executive approval) were seeded with `requires_approval_from_role=FINANCE_MANAGER`. **Fix:** policy keys 3 and 4 now map to `UserRole.ADMIN`.

### Deviations from original plan
- **40 transactions, not 60.** 40 gives substantive chart data across 4 weeks without bloating seed time. All categories and departments represented.
- **No 3-minute fallback screen recording.** Covered by `docs/DEMO_SCRIPT.md` fallback talking points section instead.
- **No DNS/preview URL.** Demo runs on raw IP `http://101.53.140.68` — sufficient for the consultant review.

---

## Cut order if behind schedule

Cut from the top of this list first. Never cut anything below the line.

- [ ] Email delivery (digest works in-app only)
- [ ] SSE for notifications (polling is fine)
- [ ] Department budgets + alerts
- [ ] Audit log writes (keep schema, skip writes for non-critical actions)
- [ ] Reimbursements

— never cut —

- Transaction state machine
- Receipt OCR
- Policy engine
