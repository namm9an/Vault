# Vault — Architecture

This document describes Vault's full architecture. A developer reading this fresh should understand the system without needing anything else.

---

## 1. System overview

Vault is a **monolithic FastAPI backend** + **React/Vite SPA** + **PostgreSQL 15** + **Redis 7** + **ARQ worker** + **S3-compatible object storage** + **external LLM endpoint (E2E TIR running Llama 3.1 8B Instruct)**. One deployable per environment via Docker Compose.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Browser (React SPA)                           │
│  React 18 · Vite · TS · Tailwind CSS · React Query · React Router   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS · JWT in Authorization header
                           │ REST (JSON) + SSE for notifications
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FastAPI (Uvicorn workers via Gunicorn)             │
│  routers/  deps/  services/  ai/  jobs/  models/                    │
└──────┬──────────────┬─────────────────┬───────────────┬─────────────┘
       │              │                 │               │
       ▼              ▼                 ▼               ▼
┌────────────┐ ┌────────────┐  ┌──────────────────┐ ┌──────────────┐
│ PostgreSQL │ │  Redis 7   │  │ E2E Object Store │ │   E2E TIR    │
│    15      │ │ queue +    │  │  S3-compatible   │ │ Llama 3.1 8B │
│            │ │ cache +    │  │  (receipts/)     │ │   Instruct   │
│            │ │ pubsub     │  │                  │ │  (OpenAI API)│
└────────────┘ └─────┬──────┘  └────────▲─────────┘ └──────▲───────┘
                     │                  │                  │
                     ▼                  │                  │
              ┌─────────────────┐       │                  │
              │   ARQ Worker    ├───────┴──────────────────┘
              │   (separate     │   reads images, calls LLM,
              │   container)    │   writes results to DB
              └─────────────────┘
```

### 1.1 Components

**Frontend (`/web`).** Vite dev server in dev (port 5173); nginx serving built static assets + reverse-proxying `/api` to FastAPI in prod (port 80). React Query owns server state. Axios interceptor attaches `Authorization: Bearer <jwt>` and handles 401 → redirect to `/login`. React Router v6. Protected routes wrapped in `RequireAuth`. `AppLayout` provides the shared sticky nav (Vault logo, org name, NavLink tabs for **Dashboard / Transactions / Cards / Settings**, user info + sign-out). Plain Tailwind CSS used for all components (shadcn/ui deferred to Phase 5/6). `ProtectedLayout` composes `RequireAuth` + `AppLayout` for every protected route.

Pages live in `web/src/pages/`:
- `LoginPage`, `SignupPage` — public
- `DashboardPage` — 7d/30d/90d toggle, KPI cards (Total Spend, MoM delta, Pending Approvals, Active Cards), PieChart (categories), BarChart (departments), AreaChart (timeseries), top-merchants table, loading skeletons (Phase 5)
- `TransactionsPage` — filterable table + `NewTransactionDialog` (includes `ReceiptUploader`) + `TransactionDetailDrawer` (event timeline + FM/ADMIN approve/reject + policy verdict + matched policy text)
- `CardsPage` — virtual card CRUD with freeze/unfreeze/cancel
- `PoliciesPage` — ADMIN-only; inline create/edit/delete policies; active toggle
- `SettingsPage` — user management (invite, role-change, deactivate)
- `ReimbursementsPage` — EMPLOYEE: submit dialog + own-submissions table; FM/ADMIN: org-wide queue with Approve/Reject/Mark Paid actions; status badges (Phase 5)
- `DepartmentsPage` — budget utilisation table with green/amber/red progress bars; ADMIN create/edit/delete dialogs (Phase 5)

Components: `ReceiptUploader` (presigned S3 PUT → status polling → `onReceiptReady` callback), `VerdictBadge` (Phase 4).

**FastAPI app (`/api`).** Uvicorn workers behind Gunicorn (`-k uvicorn.workers.UvicornWorker -w 2`). All endpoints async. Middlewares: CORS, request-ID, JSON logging. SQLAlchemy 2.0 async session per request. Pydantic v2. `/health` returns DB+Redis+TIR liveness. Routers mounted under `/api/v1`: `auth`, `users`, `cards`, `transactions`, `receipts`, `policies` (Phase 4), `reimbursements`, `departments`, `dashboard` (Phase 5 — digest, notifications in Phase 6).

**ARQ worker.** Same image as `api`, different command (`arq api.jobs.worker.WorkerSettings`). Job types: `ocr_receipt`, `run_policy_check`, `generate_digest`. Cron: digest at Mon 09:00 IST.

**Postgres.** Primary store. Multi-tenant via `org_id` FK on every business table. Alembic for migrations.

**Redis.** (1) ARQ queue, (2) cached aggregations for dashboard (5-min TTL), (3) SSE pub/sub on channel `notif:{user_id}`.

**Object storage (E2E S3-compatible).** Bucket `vault-receipts`. Path: `org/{org_id}/receipts/{receipt_id}.{ext}`. Backend issues presigned PUTs; browser uploads direct; worker downloads via presigned GET.

**LLM endpoint.** OpenAI-compatible. Accessed through the `openai` Python SDK. All three pipelines share one thin client.

### 1.2 Frontend ↔ Backend communication

- **REST** for all CRUD/query. JSON in/out. Cursor pagination (`?limit=&cursor=`).
- **Async UI feedback.** Long actions (receipt OCR) return immediately with a status. Client polls every 2s with React Query `refetchInterval`.
- **Real-time notifications.** `GET /notifications/stream` is SSE. Server subscribes to Redis pub/sub for the current user and streams events. Fallback: poll `/notifications?unread=true` every 10s.

### 1.3 Multi-tenancy enforcement

- JWT contains `{user_id, org_id, role, exp}`, signed HS256.
- `get_current_user` dependency decodes JWT, loads user, asserts user.org_id == jwt.org_id.
- `get_org_scope` dependency returns an `OrgScope` dataclass `(db, org_id, user_id, role)` built from the authenticated user. Services receive `OrgScope` and add `WHERE org_id = scope.org_id` to every query manually — there is no magic query proxy; the discipline is in the service layer.
- DB defense: every business table has `org_id UUID NOT NULL REFERENCES organizations(id)`. Composite indexes on `(org_id, created_at)`.
- App-layer enforcement only; no Postgres RLS for the demo (easier to debug).
- Negative test required per resource: User A cannot read User B's data.

### 1.4 Transaction state machine

`TransactionService` in `api/api/services/transaction_service.py` owns the creation and human-approval side. The ARQ job `run_policy_check` owns the system-driven transitions after the LLM verdict. Key design choices:

- **`LEGAL_TRANSITIONS` dict** maps each state to the set of states it may transition to. Attempting an unlisted edge raises `HTTP 409`.
- **`transition(scope, txn, to_state, ...)` is not a commit boundary.** It mutates `txn.state` and appends a `TransactionEvent` row to the session. The caller decides when to `commit()`.
- **Phase 4: 2 events written at creation** (INITIATED + POLICY_CHECKED), committed, then `run_policy_check` ARQ job enqueued. The job writes the remaining events (APPROVED/FLAGGED/BLOCKED and CLEARED) asynchronously. `create_transaction` returns immediately with `state: "POLICY_CHECKED"`.
- **`_write_transition` in `run_policy_check`** writes both a `TransactionEvent` and an `AuditLog` row with `actor_user_id=None` (marking it as a system action) — every policy-engine state change is visible in compliance audit reports.
- **Explicit `id=uuid4()` on construction.** The Transaction object carries its own UUID before any DB flush, so child event rows can reference `txn.id` immediately.
- **`transaction_events` is append-only by convention.** No UPDATE or DELETE ever touches this table in code.

State diagram:
```
INITIATED → POLICY_CHECKED → APPROVED  → CLEARED → SETTLED
                           ↘ FLAGGED   → APPROVED (human) → CLEARED
                                       → BLOCKED (terminal)
                           ↘ BLOCKED (terminal)
```

### 1.5 Background jobs

ARQ configured in `api/jobs/worker.py`. Jobs are async functions registered on `WorkerSettings.functions`; cron on `WorkerSettings.cron_jobs`.

| Job | Trigger | Inputs | Output |
|---|---|---|---|
| `ocr_receipt` | enqueued on upload confirm | `receipt_id` | marks receipt `NEEDS_REVIEW` immediately (Llama 3.1 8B is text-only — no LLM call; fires `RECEIPT_REVIEW_NEEDED` notification) |
| `run_policy_check` | enqueued after `create_transaction` commits | `txn_id` | evaluates active policies via LLM (temp 0); inserts `TransactionPolicyResult`; transitions txn to APPROVED/FLAGGED/BLOCKED; notifies FMs atomically in single commit |
| `run_reimbursement_policy_check` | enqueued after `create_reimbursement` commits | `reimb_id` | **Phase 1:** SUBMITTED → POLICY_CHECKED (commit, FM sees progress). **Phase 2:** loads policies, calls LLM; BLOCKED → REJECTED + AuditLog + employee notification; APPROVED/FLAGGED → stay POLICY_CHECKED (FM signs off) + notify FMs. Both phases have independent idempotency guards (C1 fix). |
| `generate_digest` | cron Mon 09:00 IST + manual API | `org_id` | inserts `digests`, fires notification, sends email (Phase 6) |

Idempotency: each job loads its target row with `SELECT FOR UPDATE`; guards on the row's current state before doing any work.

### 1.5 Receipt image flow (end to end)

1. Browser → `POST /receipts/upload-url` `{filename, content_type}`. API validates content_type against the whitelist (`image/jpeg`, `image/png`, `application/pdf`). Returns `{receipt_id, upload_url, object_key}` (presigned PUT, 5-min expiry, host rewritten via `S3_PUBLIC_URL`). Row created with `status=PENDING_UPLOAD`.
2. Browser uploads bytes directly to S3-compatible storage via the presigned PUT URL.
3. Browser → `POST /receipts/{id}/confirm` with `{byte_size}` (capped at 10 MB). API HEADs the object to verify presence, sets `status=PROCESSING`, enqueues `ocr_receipt(receipt_id)`. Enqueue failure → `status=FAILED` with retry message.
4. Worker loads the receipt with `SELECT FOR UPDATE`. Marks receipt `NEEDS_REVIEW` immediately (Llama 3.1 8B is text-only — no LLM call; honest signal to route to human review). Commits, then fires `RECEIPT_REVIEW_NEEDED` notification.
5. Frontend polls `GET /receipts/{id}` via `refetchInterval`. `onReceiptReady` fires when status is `COMPLETED` or `NEEDS_REVIEW` — receipt can be attached to a transaction in either case. Only `FAILED` suppresses the callback.

---

## 2. LLM pipeline design

A single thin client (`api/ai/llm_client.py`) wraps `AsyncOpenAI(base_url=TIR_BASE_URL, api_key=TIR_API_KEY)`. One method: `complete_json(system, user, schema, temperature, max_tokens)`. Always passes `response_format={"type":"json_object"}`. Parses with the supplied Pydantic schema. On validation failure, retries once with the validation error appended to the user message; second failure raises `LLMValidationError`.

Every caller catches `LLMValidationError` and writes a `NEEDS_REVIEW`/equivalent row. Vault never crashes on a bad LLM response.

### 2.1 Pipeline 1 — Receipt OCR (honest NEEDS_REVIEW path — Phase 4)

**Trigger.** `ocr_receipt(receipt_id)` worker job.

**Current implementation (Phase 4).** Llama 3.1 8B Instruct is text-only. Rather than fabricating receipt data (the C3 critical bug), the job marks the receipt `NEEDS_REVIEW` immediately and fires a `RECEIPT_REVIEW_NEEDED` notification. No LLM call is made. The user fills the transaction form manually.

**Future implementation (when vision model available on TIR).** The job will download the image from S3, build a vision prompt, call the LLM, and validate the response with `ReceiptExtraction`. Output schema:
```
ReceiptExtraction:
  merchant: str | None
  amount: Decimal | None
  currency: Literal["INR","USD","EUR","GBP"] | None
  date: date | None
  category: Literal[...] | None
  confidence: float           # required, 0..1
  raw_text: str | None        # OCR dump for audit
```
`temperature=0`, `max_tokens=400`. `confidence < 0.7` → `NEEDS_REVIEW`. `LLMValidationError` → `FAILED`.

**Fallback.** Receipt always stays in storage. OCR is enrichment — the form can always be filled manually.

### 2.2 Pipeline 2 — Plain-English policy engine

**Trigger.** `run_policy_check(txn_id)` enqueued by `create_transaction` after committing INITIATED + POLICY_CHECKED events. **Live as of Phase 4.**

**System prompt.**
```
You are a corporate spend policy engine. You will be given a transaction and
a list of active policies written in plain English. Determine whether the
transaction is APPROVED, FLAGGED (allow but needs human review), or BLOCKED
(do not allow). Be strict, literal, and deterministic. Quote the matching
policy text verbatim in policy_matched. If multiple policies match, pick
the most restrictive verdict. If no policy applies, return APPROVED with
policy_matched=null and reason="No applicable policy".
Return ONLY JSON matching the schema.
```

**User message.**
```
TRANSACTION:
  amount: {amount} {currency}
  merchant: {merchant}
  category: {category}
  department: {department_name}
  user_role: {role}
  card_id: {card_id}

ACTIVE POLICIES:
  [P1] {policy_1_text}
  [P2] {policy_2_text}
  ...

Apply the policies. Return JSON.
```

**Output schema.**
```
PolicyVerdict:
  verdict: Literal["APPROVED","FLAGGED","BLOCKED"]
  reason: str                              # <= 200 chars
  policy_matched: str | None               # verbatim or null
  policy_id: UUID | None
  requires_approval_from: Literal["FINANCE_MANAGER","ADMIN"] | None
```

**Settings.** `temperature=0`, `max_tokens=300`.

**Validation.** Pydantic. If `FLAGGED` and `requires_approval_from` null → default to `FINANCE_MANAGER`. If `policy_id` set but not in org → strip it but keep `policy_matched`. `LLMValidationError` → write a result row with `verdict=FLAGGED`, `reason="Policy engine error — manual review required"`. Transaction never auto-blocks on LLM failure.

**State wiring.**
- No active policies → fast path: auto-APPROVED → CLEARED without calling LLM.
- `APPROVED` → `POLICY_CHECKED → APPROVED → CLEARED`.
- `FLAGGED` → `POLICY_CHECKED → FLAGGED`, FM notifications fired, awaits human approval.
- `BLOCKED` → `POLICY_CHECKED → BLOCKED` (terminal); employee sees the matched policy reason.
- LLM unavailable / validation error → fail-safe: write FLAGGED result, notify FMs, commit.
- All outcomes use single-commit: result row + state transition + notifications in one `db.commit()`.

### 2.3 Pipeline 3 — Weekly spend digest

**Trigger.** ARQ cron Mon 09:00 IST + `POST /digest/generate` (ADMIN, demo button).

**Aggregator (computed before LLM call, per org).**
- Total spend last 7 days, prior 7 days, % delta.
- Top 5 categories by amount.
- Top 10 vendors by amount.
- Unused SaaS proxy: SaaS vendors charged this week with zero non-SaaS activity in 30 days.
- Duplicate vendors: same merchant 2+ times in 7 days with similar amounts.
- Anomalies: any txn > 3× the 30-day mean.

Result is a compact JSON blob (≤ 2KB) — the LLM never sees raw transactions.

**System prompt.**
```
You are a CFO assistant. Given a 7-day spend summary, write a concise digest
with specific, actionable recommendations. Be direct. Cite numbers. Do not
hedge. Maximum 250 words. Return JSON only.
```

**Output schema.**
```
SpendDigest:
  headline: str                           # <= 80 chars
  body: str                               # <= 1500 chars, markdown allowed
  top_recommendations: list[str]          # 3-5, each <= 120 chars
  flagged_items: list[FlaggedItem]        # 0-10
    FlaggedItem:
      type: Literal["DUPLICATE","UNUSED_SAAS","ANOMALY"]
      description: str
      amount: Decimal
```

**Settings.** `temperature=0.3`, `max_tokens=900`.

**Validation.** Pydantic + word-count cap at 250 (truncate, don't re-prompt — digest is non-critical).

**Fallback.** On error, `digests` row with `status=FAILED` and the raw aggregated JSON; UI shows "Digest generation failed — view raw data".

**Delivery.** Insert `digests` row → fire `DIGEST_READY` notification for every ADMIN and FINANCE_MANAGER in the org → SMTP email with headline + body + link.

---

## 3. Docker Compose structure

One `docker-compose.yml` at repo root. One `Dockerfile` per app. `docker-compose.prod.yml` overrides volumes and disables hot reload.

### 3.1 Services

| Service | Image | Ports | Depends on | Notes |
|---|---|---|---|---|
| `web` | `web/Dockerfile` | `5173:5173` dev / `80:80` prod | `api` | Vite HMR in dev; nginx serving static + reverse-proxying `/api` to `api:8000` in prod |
| `api` | `api/Dockerfile` | `8001:8000` | `db`, `redis` | Gunicorn + uvicorn workers; runs `alembic upgrade head` on entrypoint; host port remapped to 8001 |
| `worker` | same as `api` | — | `db`, `redis` | Command override: `arq api.jobs.worker.WorkerSettings` |
| `db` | `postgres:15-alpine` | `5432:5432` (internal) | — | Volume: `pgdata` |
| `redis` | `redis:7-alpine` | `6379:6379` (internal) | — | Volume: `redisdata` (AOF) |
| `minio` | `minio/minio` | `9000:9000`, `9001:9001` | — | Local S3-compatible storage; added Phase 4; Volume: `miniodata` |
| `minio-init` | `minio/mc` | — | `minio` | One-shot bucket creator; creates `vault-receipts` on first boot |
| `mailhog` | `mailhog/mailhog` | `1025:1025`, `8025:8025` | — | Dev only |

### 3.2 Volumes
- `pgdata` — Postgres data
- `redisdata` — Redis AOF
- `./api:/app` — bind mount in dev
- `./web:/app` — bind mount in dev
- `node_modules` — named volume to avoid host overlay

### 3.3 Networks
One bridge network `vault_net`. In prod compose, `db` and `redis` ports are not exposed to host.

### 3.4 Environment variables

```
# App
APP_ENV=dev
APP_SECRET_KEY=<long-random>
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=60
JWT_REFRESH_TTL_DAYS=14
CORS_ORIGINS=http://localhost:5173

# Database
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=vault
POSTGRES_USER=vault
POSTGRES_PASSWORD=<random>
DATABASE_URL=postgresql+asyncpg://vault:<pwd>@db:5432/vault

# Redis
REDIS_URL=redis://redis:6379/0
ARQ_REDIS_URL=redis://redis:6379/1

# LLM (E2E TIR)
TIR_BASE_URL=https://infer.e2enetworks.net/project/<id>/endpoint/<id>/v1
TIR_API_KEY=<token>
TIR_MODEL=llama-3.1-8b-instruct
TIR_TIMEOUT_SECONDS=60

# Object Storage (E2E S3-compatible / local MinIO)
S3_ENDPOINT_URL=https://objectstore.e2enetworks.net
# S3_PUBLIC_URL: rewrites presigned URL host for browser access.
# Local MinIO: http://localhost:9000  |  E2E prod: same as S3_ENDPOINT_URL or leave empty.
S3_PUBLIC_URL=http://localhost:9000
S3_REGION=ap-south-1
S3_BUCKET=vault-receipts
S3_ACCESS_KEY=<key>
S3_SECRET_KEY=<secret>
S3_PRESIGN_TTL_SECONDS=300

# Email
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=digest@vault.local

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

### 3.5 Boot order

`docker compose up` → `db` and `redis` start → `api` waits for healthchecks (`pg_isready`, `redis-cli ping`) → `api` runs `alembic upgrade head` then starts Gunicorn → `worker` starts → `web` starts.
