# Vault — Master Plan (Original Prompt + Master Implementation Plan)

---

## ⚠️ READ THIS FIRST — Briefing for the next Claude Code session (or any AI/contributor picking up mid-stream)

**What this document is.** This file is the single source of original intent for the Vault project. Part 1 below is the verbatim long prompt the user (Naman Moudgill) gave at the very start of this project to a senior-architect-role Claude. Part 2 below is the verbatim original architectural response that came back — the **Master Implementation Plan**: Architecture Plan + day-by-day Implementation Plan + full production-grade PostgreSQL schema + the first drafts of all the derived MD files. **Nothing here is summarized.** When you see "the master plan," that means Part 2 of this document.

**The relationship between this file and the other seven MD files.**
The seven Markdown files in this repo (`README.md` at repo root, plus `docs/ARCHITECTURE.md`, `docs/STACK.md`, `docs/DECISIONS.md`, `docs/PHASES.md`, `docs/API.md`, `docs/PROBLEMS.md`) are **derived from** the master plan in Part 2. They were generated in the same pass to make the plan navigable and operational. If a derived doc and the master plan ever disagree, the master plan is the source of intent — update the derived doc to match, or amend the master plan with a dated note. Do not silently rewrite the master plan.

**Read order if you are a new AI session and the user has just asked you to continue the project:**
1. **This file (`docs/MASTER_PLAN.md`) — read it in full.** Part 1 tells you what was asked. Part 2 tells you what was designed. Together they are the full context that the other seven docs were boiled down from.
2. `README.md` — how to run the stack locally.
3. `docs/ARCHITECTURE.md` — system diagram + canonical DB schema (matches `api/alembic/versions/20260526_0001_baseline.py`).
4. `docs/STACK.md` — every dependency and why it's in the tree.
5. `docs/DECISIONS.md` — ADR-style log of non-obvious choices.
6. `docs/PHASES.md` — day-by-day delivery checklist (Phases 1–7). Treat the unchecked boxes as the live to-do list.
7. `docs/API.md` — HTTP contract.
8. `docs/PROBLEMS.md` — known issues, risks, deferred work, demo-day mitigations.

**Project at a glance (so you can orient before reading 1,600 lines):**
- **Product:** Vault — Ramp-inspired AI-native corporate spend intelligence platform. Demo for **E2E Cloud** (Indian GPU cloud company). Not a clone — a focused slice showing what an AI-native spend platform looks like with LLM inference as a first-class building block.
- **Stack:** FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + Alembic 1.13 + Pydantic v2 + python-jose JWT (HS256) + passlib/bcrypt + ARQ (Redis) on the backend. React 18 + Vite 5 + TypeScript 5.6 strict + Tailwind 3 + TanStack Query 5 + React Router 6 on the frontend. Postgres 15, Redis 7, MinIO (local dev S3) / E2E S3-compatible object storage (prod), E2E TIR (OpenAI-compatible) for LLM inference. Mailhog for dev email. Docker Compose ties it all together.
- **LLM model:** `meta-llama/Llama-3.1-8B-Instruct` via E2E TIR endpoint. **Text-only** (Llama 3.2 introduced vision, 3.1 did not). The receipt OCR pipeline therefore marks all uploads `NEEDS_REVIEW` immediately — no LLM call (see Phase 4 deviations and `docs/DECISIONS.md`). Policy engine is the primary LLM pipeline and the demo centerpiece.
- **Three LLM use cases**, each with strict Pydantic-validated structured output: (1) receipt parsing — currently honest NEEDS_REVIEW (text-only model), (2) policy engine (temp 0, the demo centerpiece — **live as of Phase 4**), (3) weekly digest (temp 0.3 — **live as of Phase 6**).
- **Multi-tenancy:** every business table carries `org_id`. Enforced in `api/api/deps.py::get_current_user` — that dependency asserts `user.org_id == jwt.org_id` and is the *single* trust boundary. No row-level security in Postgres for the demo.
- **Transaction state machine:** `INITIATED → POLICY_CHECKED → APPROVED | FLAGGED | BLOCKED → CLEARED → SETTLED`, with append-only `transaction_events` audit log on every transition. Phase 4: `create_transaction` commits INITIATED + POLICY_CHECKED then enqueues `run_policy_check` ARQ job (replaces the old sync stub).
- **Roles:** `ADMIN`, `FINANCE_MANAGER`, `EMPLOYEE`. Enforced at the route layer via `require_role(*allowed)`.
- **Timeline:** Tue 2026-05-26 → Mon 2026-06-01 EOD (demo). Solo dev + AI, ~8 hrs/day. Eight phases (6.5 added post-plan). **Phases 1–6 are complete** (see "Current state" below). **Phase 6.5 (Marketing landing page + App UI redesign, Ramp-parity) is next, followed by Phase 7 (Demo hardening).**

**Working directory & layout:**
- Primary working directory: `/Users/namanmoudgill13/Desktop/Vault/`
- Backend: `api/` (FastAPI app in `api/api/`, Alembic in `api/alembic/`, Dockerfile at `api/Dockerfile`)
- Frontend: `web/` (Vite + React + TS)
- Docs: `docs/` (this file + the seven derived docs)
- Compose: `docker-compose.yml` at repo root
- Env: `.env` at repo root (gitignored — contains real TIR JWT). `.env.example` is the contract.

**Current state (as of 2026-05-28 — verify before acting):**
- **Phase 1 complete.** Repo scaffolded; Docker Compose stack boots clean; Alembic baseline migration (`0001_baseline`) creates every table; `/health` returns `{db: ok, redis: ok, tir: configured}`; all auth endpoints working end-to-end; React app boots; LoginPage/SignupPage/DashboardPage functional; axios interceptor with 401-refresh-then-redirect implemented; React Query wired; seed script creates 1 org + 4 users.
- **Phase 2 complete.** Cards CRUD with freeze/unfreeze/cancel + audit_log; users list/invite/update with RBAC; `OrgScope` dependency; 18 passing tests (deps + multi-tenancy); frontend CardsPage, SettingsPage, AppLayout; router updated with `/cards` and `/settings` routes. All live-verified via `docker compose` smoke tests.
- **Phase 3 complete + post-phase bugs fixed.** Transaction state machine end-to-end. `TransactionService` with `LEGAL_TRANSITIONS` dict enforcing valid state edges. 6 REST endpoints live and smoke-tested. **31 total tests** at phase end. Frontend: TransactionsPage with filter bar + VerdictBadge + NewTransactionDialog + TransactionDetailDrawer (event timeline + FM/ADMIN approve/reject panel). Seed creates 8 demo transactions (5 CLEARED, 2 FLAGGED, 1 BLOCKED).
- **Phase 4 complete + validation fixes applied (2026-05-28).** Both LLM pipelines live. S3 receipt upload flow end-to-end with MinIO for local dev. Policy engine ARQ job with real LLM (Llama 3.1 8B at temp 0) evaluating org's written policies. `receipt_id` and `matched_policy_id` FK mappings restored in ORM models. Alembic migration `0003_policy_soft_delete` adds `deleted_at` to policies. **40 total tests passing.** Frontend: PoliciesPage, ReceiptUploader, updated TransactionsPage + AppLayout nav.
- **Phase 5 complete + validation fixes applied (2026-05-28).** Dashboard (Recharts charts, Redis-cached aggregations), Reimbursements (full SUBMITTED → POLICY_CHECKED → APPROVED/REJECTED → PAID state machine + ARQ policy check), Departments (CRUD + monthly budget status + Redis-deduped threshold alerts). All 9 critical/high validation issues (C1–C3, H1–H6) resolved before shipping. **46 total tests passing.** Frontend: rebuilt DashboardPage, new ReimbursementsPage + DepartmentsPage, AppLayout nav updated. 3 new routers live: `/api/v1/dashboard`, `/api/v1/reimbursements`, `/api/v1/departments`.
- **Phase 6 complete + validation fixes applied (2026-05-28).** Digest engine (aggregate_spend_data + LLM + SMTP email + ARQ cron Mon 09:00 IST), notifications read layer (list/unread-count/mark-read/mark-all-read), UI polish (AppLayout rebuilt as left sidebar, DigestPage, Toast, EmptyState on all list pages, Inter font). All validation issues (C1, H2–H5, M7, L9, L10) resolved. **48 total tests passing.** 2 new routers: `/api/v1/digest`, `/api/v1/notifications`. `POST /digest/generate` returns HTTP 202 immediately; LLM runs in BackgroundTasks with own DB session.
- **Phase 2 known gaps / deviations:**
  - `shadcn/ui` not installed. All Phase 1–5 UI is plain Tailwind. Deferred to Phase 6.
  - `GET /cards` returns `Card[]` (flat array), not `{items, next_cursor}`. Cursor pagination deferred. `docs/API.md` updated to match.
  - Seed script seeds 2 departments and 3 demo reimbursements. Cards created via API in demo walkthrough.
  - API runs on host port **8001** (remapped from 8000 — port conflict with user's `multimodal-*` containers). `VITE_API_BASE_URL=http://localhost:8001` reflects this. Postgres and Redis are internal-only (no host port exposure).
- **Phase 3 known deviations:**
  - No Phase 3 migration created — all three transaction tables were already in `0001_baseline`. `alembic upgrade head` is idempotent. See `docs/DECISIONS.md`.
  - `GET /transactions` returns a flat `Transaction[]` array (same cursor-pagination deferral as `/cards`).
- **Phase 4 known deviations:**
  - `ocr_receipt` does not call the LLM. Llama 3.1 8B is text-only. All uploads land as `NEEDS_REVIEW`. Real OCR pending vision-capable model availability on TIR. See `docs/DECISIONS.md`.
  - MinIO added to `docker-compose.yml` for local dev. `S3_PUBLIC_URL` config var rewrites presigned URL host from Docker-internal to `http://localhost:9000` for browser access.
  - Policy soft-delete (migration `0003`) — `DELETE /policies/{id}` sets `deleted_at`, never hard-deletes.
  - `create_transaction` now commits only INITIATED + POLICY_CHECKED (2 events) then enqueues `run_policy_check`. The `POLICY_CHECKED` state is now visible briefly on the frontend before the ARQ job resolves it.
- **Phase 5 known deviations:**
  - Reimbursement APPROVED/FLAGGED LLM verdicts stay at `POLICY_CHECKED` — FM always signs off. Original spec said APPROVED verdict → auto-APPROVED. Changed because FM's approve endpoint required `POLICY_CHECKED`; auto-transition to `APPROVED` made it unreachable (C2 fix).
  - `GET /departments` open to all authenticated roles (not just FM/ADMIN). Required for employee reimbursement submission form (department picker).
  - M1–M6 deferred: `department_id` and `manager_id` org-scope validation, pending_approvals KPI completeness, invalid bucket 422, MoM edge cases. Logged in `docs/PROBLEMS.md`.
- **Phase 6 known deviations:**
  - SSE (`GET /notifications/stream`) not implemented. Polling used instead: `useUnreadCount` polls every 30s. Sufficient for demo.
  - Digest aggregator omits "unused SaaS proxy" and "duplicate vendors" heuristics from the original spec. LLM derives insights from total/categories/departments/merchants data. Indistinguishable in the demo.
  - MinIO ports remapped: S3 API `9090:9000`, console `9091:9091` (was `9000:9000` / `9001:9001` — port conflict with local containers).
- **Phase 3 + Phase 4 post-phase bugs fixed** (see `docs/PROBLEMS.md` for full entries):
  - Phase 3 — C1 (404 not 403), C2 (stub return), H2 (FOR UPDATE on approve/reject), H3 (list LIMIT), M1–M6 (various).
  - Phase 4 — C1 (React ReferenceError), C2 (MinIO), C3 (OCR hallucination), C4 (receipt org-scope), C5 (soft-delete), H1–H7 (idempotency/single-commit/enqueue/sanitization/onReceiptReady/whitelist/fixture).
  - Phase 5 — C1 (two-phase idempotency), C2 (FM approve 409), C3 (no AuditLog in ARQ), H1 (enqueue failure), H2 (Redis before commit), H3 (Redis crash), H4 (date key instability), H5 (PieChart width), H6 (departments EMPLOYEE access).
  - Phase 6 — C1 (read-all route ordering), H2 (asyncio.to_thread for SMTP), H3 (HTTP 202 async digest), H4 (date range validation), H5 (naive datetime onupdate), M7 (date guard on generate button), L9 (Toast timer leak), L10 (digest panel flicker).
- **All Phase 1 critical/high bugs resolved:**
  - Login `MultipleResultsFound` → fixed by migration `0002_global_email_unique` (global `UNIQUE(email)`) + app-layer guard.
  - Login timing oracle → dummy bcrypt hash run on every missing-user path.
  - Refresh token race → `with_for_update().execution_options(populate_existing=True)`.
  - `get_db()` rollback-on-exception fixed; `APP_SECRET_KEY` min-length validator added.
  - Missing `Department` ORM model fixed; refresh JWT `jti` added to prevent hash collision.

**Operational rules (hard rules — do not violate without explicit user request):**
- **Never commit `.env` or secrets.** `.env.example` is the contract. The TIR API key is a long-lived JWT — never log it, never echo it in error responses.
- **Never add `Co-Authored-By Claude` lines to git commits.** User preference.
- **Database changes always go through Alembic.** Never edit the schema by hand on a running container.
- **Every LLM call goes through `api/api/llm/` (when that module exists) with structured output validation.** No ad-hoc `httpx.post` to TIR in business code.
- **Every new business table gets `org_id` + composite index in the same migration that creates it.** No exceptions.
- **Money is stored as cents (`BIGINT`), never float.**
- **Emails are stored as `CITEXT`, unique within `(org_id, email)`.**
- **`audit_log` and `transaction_events` are append-only by convention** — no DELETE/UPDATE in code.

**External services & credentials (in `.env`, gitignored):**
- `TIR_BASE_URL=https://infer.e2enetworks.net/project/p-6530/endpoint/is-10649/v1/`
- `TIR_API_KEY=<long JWT>` — text-only Llama 3.1 8B Instruct endpoint
- `TIR_MODEL=meta-llama/Llama-3.1-8B-Instruct`
- E2E S3-compatible object storage at `https://objectstore.e2enetworks.net` (access keys not yet filled — needed before Phase 4)
- SMTP via Mailhog locally on port 1025 (UI on 8025)

**How to verify the stack is alive before doing anything destructive:**
```bash
docker compose ps                                       # all containers up?
curl -s http://localhost:8001/health                    # {db: ok, redis: ok, tir: configured}
docker compose logs api --tail=50                       # recent errors?
```

**Demo priorities — what gets cut if we slip** (do not cut from the top; cut from the bottom):
1. Working auth + multi-tenancy (Phase 1–2) — **non-negotiable**.
2. One LLM pipeline working end-to-end (prefer **policy engine** over OCR — more visually impressive in demo).
3. Transactions + state machine (Phase 3) — **non-negotiable**.
4. Dashboard charts (Phase 5).
5. Weekly digest (Phase 6) — falls back to "preview generated on-demand" if cron breaks.
6. S3 uploads (Phase 4) — if access keys aren't ready, mock with local volume + signed-URL placeholder.
7. Polish (Phase 7) — always last.

**One last thing.** If anything in this briefing feels stale, verify against the actual code/git state before acting — the project moves fast and this briefing is a snapshot. The verbatim Part 1 and Part 2 below, however, are immutable history: they are what was asked and what was designed at the start. Treat them as the contract.

---

## Part 1 — Original prompt (verbatim)

You are a senior software architect. I need you to produce three 
deliverables for a project called Vault — a Ramp-inspired AI-native 
corporate spend intelligence platform. Do not write any application 
code yet. Produce only:

1. Architecture Plan
2. Implementation Plan (phased, day-by-day)
3. Complete Database Schema (SQL, production-grade)

---

## CONTEXT — WHAT VAULT IS

Vault is a clone of Ramp (ramp.com) — a $32B fintech company with 
$1B ARR. Ramp's core philosophy: earn interchange fees like every 
card company, but build the product to actively help companies spend 
LESS. The intelligence layer IS the product. The card is just the 
data pipe.

Vault replicates Ramp's intelligence layer:
- AI reads receipts automatically
- AI enforces spend policies written in plain English
- AI generates a weekly spend digest that finds waste, duplicates, 
  and anomalies

This is being built as a demonstration of AI-assisted development 
speed for E2E Cloud — an Indian GPU cloud infrastructure company. 
The demo is for a consultant review. It must look and behave like a 
real product, not a student project.

---

## CONFIRMED TECH STACK

### Frontend
- React 18 + Vite
- TypeScript
- Tailwind CSS
- shadcn/ui (component library)
- Recharts (spend charts and visualisations)
- React Query (server state management)
- React Router v6
- Axios (API calls)

### Backend
- Python 3.11
- FastAPI (async, production-grade)
- SQLAlchemy 2.0 (async ORM)
- Alembic (migrations)
- Pydantic v2 (validation and serialisation)
- PostgreSQL 15 (primary database)
- Redis 7 (job queue, caching, session store)
- ARQ or Celery (async task queue for digest generation)
- Uvicorn + Gunicorn (production server)

### AI / LLM
- Model: Llama 3.1 8B Instruct
- Hosted on: E2E TIR (OpenAI-compatible API endpoint)
- Access via: openai Python SDK pointed at E2E TIR base URL
- Three LLM use cases only (see below)
- Always use the Instruct variant — never base model
- Output validation: Pydantic schemas on every LLM response
- Fallback: if LLM response fails schema validation, flag for 
  human review — never crash

### Infrastructure
- Deployment: E2E Cloud
- Containerisation: Docker + Docker Compose
- Object storage: E2E Object Storage (S3-compatible) for receipt 
  images
- Auth: JWT-based, organisation-scoped (multi-tenant)
- Environment config: python-dotenv + .env files

---

## CONFIRMED FEATURES — BUILD ALL OF THESE

### 1. Multi-tenant organisation setup
- A company signs up and creates an organisation
- Users belong to one organisation
- Every DB query is scoped by org_id — no cross-tenant data leakage
- Roles within an org: ADMIN, FINANCE_MANAGER, EMPLOYEE

### 2. RBAC (Role-Based Access Control)
- ADMIN: full access — issue cards, set policies, view all spend, 
  manage users
- FINANCE_MANAGER: approve expenses, view all transactions, set 
  budgets, export reports
- EMPLOYEE: view own transactions only, upload receipts, submit 
  reimbursements
- Permission checks at the route level using FastAPI dependencies

### 3. Virtual card management
- Issue virtual cards per user or per project
- Each card has: daily_limit, monthly_limit, total_limit, 
  category_restrictions (array), status (ACTIVE/FROZEN/CANCELLED)
- Cards belong to an org and are assigned to a user
- Admin can freeze/unfreeze/cancel any card instantly

### 4. Transaction feed with state machine
- Every transaction has a strict lifecycle:
  INITIATED → POLICY_CHECKED → APPROVED | FLAGGED | BLOCKED → 
  CLEARED → SETTLED
- State transitions are append-only events — never mutate the 
  transaction record directly
- Every state change is logged in a transaction_events table with: 
  timestamp, from_state, to_state, triggered_by (user_id or 
  'system'), reason
- Transactions are created via a mock endpoint (no real card network)

### 5. Receipt upload → AI OCR → auto-fill (LLM Use Case 1)
- Employee uploads a receipt image (JPEG/PNG/PDF)
- Image is stored in E2E Object Storage
- A background job sends the image to Llama 3.1 8B Instruct with 
  a vision prompt
- LLM returns structured JSON: 
  {merchant: str, amount: float, currency: str, date: str, 
   category: str, confidence: float}
- Pydantic validates the response — if confidence < 0.7, flag for 
  manual review
- The transaction form is auto-populated with extracted data
- The receipt is linked to the transaction record

### 6. Plain-English policy engine (LLM Use Case 2)
- Admins write policies in natural language:
  e.g. "No alcohol purchases above ₹2,000"
  e.g. "All SaaS tools over ₹10,000 require CFO approval"
  e.g. "Travel expenses must have a receipt attached"
- Policies are stored as plain text strings in the DB, active/inactive
- When a transaction is submitted, ALL active policies are fetched 
  and sent to the LLM with the transaction details
- LLM returns structured JSON:
  {verdict: 'APPROVED'|'FLAGGED'|'BLOCKED', 
   reason: str, 
   policy_matched: str | null,
   requires_approval_from: str | null}
- Temperature: 0 (fully deterministic)
- Result is stored in transaction_policy_results table
- If FLAGGED: notify Finance Manager via in-app notification
- If BLOCKED: transaction does not proceed, employee sees explanation

### 7. Reimbursement workflow
- Employee submits a reimbursement request with: amount, description, 
  receipt image, category
- Request goes through the same policy engine
- Finance Manager sees a queue of pending approvals
- Approve → marks as APPROVED, triggers mock payout
- Reject → requires a reason, employee is notified

### 8. Department budgets
- Admins create departments and assign monthly budgets
- Each transaction is tagged to a department
- Real-time budget vs actuals tracking
- Alert when department hits 80% of monthly budget

### 9. Spend dashboard
- Metrics: total spend, spend by category (pie/bar), spend by 
  department, spend by card, month-over-month delta
- Filters: date range, department, category, card, user
- All charts use Recharts
- Data is computed server-side and returned as aggregated JSON

### 10. Weekly AI spend digest (LLM Use Case 3)
- Runs as a background job every Monday at 9am (or triggered manually 
  for demo)
- Aggregates the past 7 days of transaction data per org
- Computes: top spend categories, unused subscriptions (SaaS tools 
  with no activity), duplicate vendors, anomalous spend vs prior week
- Sends aggregated data to LLM with prompt:
  "You are a CFO assistant. Write a concise spend digest with 
   specific actionable recommendations. Be direct. Max 250 words."
- Temperature: 0.3
- Digest is stored in DB and displayed on dashboard
- Also sent via email (use SMTP or Resend API)

### 11. In-app notifications
- Real-time notifications for: policy flags, approval requests, 
  budget alerts, digest ready
- Use Server-Sent Events (SSE) or polling (polling is fine for demo)
- Notification bell in navbar with unread count

---

## EXPLICIT SCOPE BOUNDARIES — DO NOT BUILD THESE

Do not suggest, scaffold, or mention:
- Real card network integration (Visa/Mastercard/RuPay APIs)
- Real bank account connectivity or Plaid
- KYC/KYB compliance flows
- Multi-currency or FX conversion
- Mobile app (React Native or otherwise)
- Travel booking module
- Vendor contract management
- ERP integrations (QuickBooks, Tally, Xero, NetSuite)
- Fine-tuning the LLM — use Instruct as-is with prompt engineering
- Any model larger than 8B parameters
- GraphQL (use REST only)
- Microservices (monolith FastAPI app, single deployable)

---

## DATABASE SCHEMA REQUIREMENTS

Produce a complete PostgreSQL schema with:
- Full CREATE TABLE statements with correct data types
- All primary keys (UUID, not integer)
- All foreign keys with ON DELETE behaviour specified
- Indexes on every foreign key and every column used in WHERE clauses
- created_at and updated_at on every table
- Enum types defined as PostgreSQL ENUM or CHECK constraints
- A separate transaction_events table for the state machine audit log
- A separate transaction_policy_results table for LLM policy verdicts
- A receipts table linked to transactions
- A policies table (plain text, active/inactive, per org)
- A digests table (stores weekly AI digest text per org)
- A notifications table
- A departments table with budget tracking
- A cards table with all limit fields

---

## ARCHITECTURE PLAN REQUIREMENTS

Include:
- Full system architecture diagram described in text (component by 
  component)
- How the frontend and backend communicate (REST, async, SSE)
- How the LLM pipeline works end to end for each of the 3 use cases
- How multi-tenancy is enforced at the DB and API layer
- How background jobs are structured (ARQ/Celery beat for digest)
- How receipt images flow from upload to LLM to DB
- How Docker Compose is structured (which services, ports, volumes)
- Environment variables required (list all of them)

---

## IMPLEMENTATION PLAN REQUIREMENTS

Produce a day-by-day plan for a solo developer targeting a full 
working demo by end of Monday. Assume development starts now. 
Each day should have:
- Clear deliverables
- Which files/modules get created
- What is testable/demonstrable at end of that day
- No day should be overloaded — be realistic about what one person 
  can ship in a day with AI assistance

Priority order if time runs short:
1. Transaction feed + state machine (must have)
2. Receipt AI pipeline (must have — best demo moment)
3. Policy engine (must have — best demo moment)
4. Spend dashboard (should have)
5. Reimbursement workflow (should have)
6. Weekly AI digest (nice to have — can be triggered manually)
7. Notifications (nice to have)
8. Department budgets (nice to have)

---

## OUTPUT FORMAT

Produce your response in this exact order:

### 1. SYSTEM ARCHITECTURE
(Full architecture description, component by component)

### 2. LLM PIPELINE DESIGN
(All 3 use cases — exact prompt structure, input, output schema, 
 validation logic, fallback behaviour)

### 3. DOCKER COMPOSE STRUCTURE
(All services, ports, volumes, environment variables)

### 4. DATABASE SCHEMA
(Full SQL — every table, every constraint, every index)

### 5. FOLDER STRUCTURE
(Full monorepo layout — frontend and backend, every directory 
 and key file named)

### 6. API ROUTES
(Every REST endpoint — method, path, auth required, request body, 
 response shape)

### 7. IMPLEMENTATION PLAN
(Day-by-day, realistic, with deliverables per day)

Do not write application code. Do not skip any section. Do not 
summarise the schema — write every table in full SQL.## DOCUMENTATION FILES

Produce starter content for these 7 markdown files as the final 
section of your output. These files will be created in the project 
at the paths specified. Do not summarise — write the full content 
for each file.

---

### README.md (project root)
Write a complete README with:
- What Vault is — one sharp paragraph
- The Ramp philosophy in 2-3 lines (why this product exists)
- The 3 AI features explained in plain English for a non-technical reader
- Prerequisites (Python 3.11, Node 18, Docker, E2E TIR access)
- How to run the full project locally in one command (Docker Compose)
- Environment variables required (reference .env.example)
- Folder structure overview (2 levels deep)
- A "How the AI works" section explaining the 3 LLM pipelines simply

---

### docs/ARCHITECTURE.md
Pull the full content from Sections 1, 2, and 3 of this output 
(System Architecture, LLM Pipeline Design, Docker Compose Structure) 
and format it cleanly as a standalone document. A developer reading 
this file fresh should understand the entire system without reading 
anything else.

---

### docs/DECISIONS.md
Pre-populate with the 8 most important design decisions already made 
for this project. Use this exact format for each:

## [YYYY-MM-DD] — Decision Title
**Decision:** What was decided
**Why:** The reasoning behind it
**Alternatives considered:** What was rejected and why
**Impact:** What this decision affects in the codebase

Decisions to include:
- FastAPI over Django
- React + Vite over Next.js
- Llama 3.1 8B Instruct over larger models
- ARQ vs Celery for background jobs
- UUID primary keys over integer IDs
- PostgreSQL enums vs CHECK constraints
- Pydantic validation on every LLM response
- Monolith over microservices

---

### docs/PHASES.md
The full implementation plan as a trackable checklist.
Format:

## Phase N — Phase Name
**Goal:** One line describing what this phase delivers
**Estimated time:** X hours
**Testable at end of phase:** What you can demo when this phase is done

### Deliverables
- [ ] Deliverable 1
- [ ] Deliverable 2

Include every phase from the implementation plan. 
Each deliverable must be specific enough to know 
when it is done — not "set up backend" but 
"FastAPI app boots with /health endpoint returning 200".

---

### docs/PROBLEMS.md
Write a header, purpose statement, and one example entry 
showing the format. Then leave the rest empty for the 
developer to fill in during the build.

Format for each entry:
## [YYYY-MM-DD] — Problem Title
**Symptom:** What the developer observed
**Root cause:** What actually caused it
**Fix:** Exact steps taken to resolve
**Time lost:** Honest estimate
**How to avoid next time:** One line

---

### docs/STACK.md
Every technology in the stack. For each one:

## [Technology Name] vX.X
**Purpose:** What it does in this project
**Why chosen:** One line
**Key config:** Any non-obvious setup required
**Gotchas:** Known issues or sharp edges at setup time
**Docs:** Link to official documentation

Cover every item in the tech stack — frontend, backend, 
database, cache, queue, LLM, storage, auth, deployment.

---

### docs/API.md
Pull the full content from Section 6 of this output 
(API Routes) and format it as a clean standalone API 
reference. For every endpoint use this format:

## [METHOD] /path/to/endpoint
**Auth required:** Yes / No — [role required]
**Description:** One line

**Request body:**
\`\`\`json
{ example request }
\`\`\`

**Response:**
\`\`\`json
{ example response }
\`\`\`

**Error responses:**
- 401 — reason
- 403 — reason
- 422 — reason

Group endpoints by resource: Auth, Users, Cards, 
Transactions, Receipts, Policies, Reimbursements, 
Departments, Digest, Notifications.

---

## Part 2 — Master implementation plan, original response (verbatim)

Now the deliverable. I'll write all 7 doc files to `/Users/namanmoudgill13/Desktop/Vault/` and also render the full architecture/schema/plan in this response.

---

# VAULT — Architecture, Schema & Implementation Plan

---

## 1. SYSTEM ARCHITECTURE

### 1.1 High-level shape

Vault is a **monolithic FastAPI backend** + **React/Vite SPA frontend** + **PostgreSQL** + **Redis** + **ARQ worker** + **S3-compatible object storage** + **external LLM endpoint (E2E TIR)**. Single deployable per environment via Docker Compose.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Browser (React SPA)                           │
│  React 18 · Vite · TS · Tailwind · shadcn/ui · Recharts · RQuery    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS · JWT in Authorization header
                           │ REST (JSON) + SSE for notifications
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FastAPI (Uvicorn workers via Gunicorn)             │
│  ├── routers/      (auth, users, cards, txn, receipts, policies,    │
│  │                  reimbursements, departments, digest, notifs)    │
│  ├── deps/         (get_db, get_current_user, require_role,         │
│  │                  get_org_scope)                                  │
│  ├── services/     (business logic; pure-ish; takes session in)     │
│  ├── ai/           (llm_client, prompts, schemas, validators)       │
│  ├── jobs/         (arq tasks: ocr_receipt, run_policy, gen_digest) │
│  └── models/       (SQLAlchemy 2.0 async ORM)                       │
└──────┬──────────────┬─────────────────┬───────────────┬─────────────┘
       │              │                 │               │
       ▼              ▼                 ▼               ▼
┌────────────┐ ┌────────────┐  ┌──────────────────┐ ┌──────────────┐
│ PostgreSQL │ │  Redis 7   │  │ E2E Object Store │ │  E2E TIR     │
│    15      │ │ (queue +   │  │ (S3-compatible;  │ │  Llama 3.1   │
│ (primary)  │ │  cache +   │  │  receipts/)      │ │  8B Instruct │
│            │ │  pubsub)   │  │                  │ │  (OpenAI API)│
└────────────┘ └─────┬──────┘  └────────▲─────────┘ └──────▲───────┘
                     │                  │                  │
                     ▼                  │                  │
              ┌─────────────────┐       │                  │
              │   ARQ Worker    ├───────┴──────────────────┘
              │   (separate     │   reads images, calls LLM,
              │   container)    │   writes results to DB
              └─────────────────┘
```

### 1.2 Components

**Frontend (`/web`)** — Vite dev server in dev (port 5173), built static assets served by nginx in prod (port 80). All API calls go to `/api/*`; nginx reverse-proxies to FastAPI. React Query owns server state; Axios is the transport with an interceptor that attaches `Authorization: Bearer <jwt>` and handles 401 → redirect to `/login`. React Router v6 for routing; protected routes are wrapped in a `RequireAuth` + `RequireRole` HOC.

**FastAPI app (`/api`)** — Uvicorn workers behind Gunicorn (`-k uvicorn.workers.UvicornWorker -w 2` is plenty for the demo). All endpoints are async. Three middlewares: CORS, request-ID injection, structured JSON logging. SQLAlchemy 2.0 async session is created per-request via dependency. Pydantic v2 for request/response models. Health endpoint at `/health` (returns DB+Redis+TIR liveness).

**ARQ worker (`/api`, same image, different command)** — Pulls jobs off Redis. Three job types: `ocr_receipt`, `run_policy_check`, `generate_digest`. Worker shares the SQLAlchemy models with the API. Cron entry for digest: `Monday 9am IST`.

**Postgres (`db`)** — Primary store. Multi-tenant via `org_id` FK on every business table. Schema migrations via Alembic; one canonical baseline migration + incremental ones.

**Redis (`redis`)** — Three roles: (1) ARQ task queue, (2) cached aggregations for dashboard (5-min TTL), (3) SSE pub/sub channel for real-time notifications (`notif:{user_id}`).

**Object storage (`E2E Object Storage`, S3-compatible)** — Bucket `vault-receipts`. Path scheme: `org/{org_id}/receipts/{receipt_id}.{ext}`. Backend generates presigned PUT URLs; browser uploads directly to bucket; backend records the object key. ARQ worker downloads via presigned GET when running OCR.

**LLM endpoint (E2E TIR)** — OpenAI-compatible. `OPENAI_API_BASE=https://infer.e2enetworks.net/project/<id>/endpoint/<id>/v1`. Accessed through `openai` Python SDK. All three pipelines hit this same endpoint.

### 1.3 Frontend ↔ Backend communication

- **REST**: All CRUD and queries. JSON in / JSON out. Pagination via `?limit=&cursor=` (cursor = base64-encoded `(created_at, id)`).
- **Async UI feedback**: When an action kicks off a background job (e.g., receipt upload → OCR), the API returns immediately with `status: "processing"` and a `receipt_id`. The client polls `GET /receipts/{id}` every 2s until `status: "completed"` or `"failed"` (React Query `refetchInterval`).
- **Real-time notifications**: `GET /notifications/stream` is an SSE endpoint. The FastAPI handler subscribes to the Redis pub/sub channel for the current user and streams events as they arrive. Client uses `EventSource`. Fallback path (and what we ship for the demo if SSE flakes): client polls `GET /notifications?unread=true` every 10s.

### 1.4 Multi-tenancy enforcement

- **JWT contains** `{user_id, org_id, role, exp}`. Signed HS256.
- **`get_current_user` dependency** decodes the JWT, loads the user, asserts `user.org_id == jwt.org_id`, and returns a `CurrentUser` object containing `org_id`.
- **`get_org_scope` dependency** returns a `Scope` object that wraps a SQLAlchemy session and *requires* every query to be filtered by `org_id`. Concretely, services receive `scope: Scope` and use `scope.query(Card)` which internally calls `select(Card).where(Card.org_id == scope.org_id)`.
- **DB-layer defense**: Every business table has `org_id UUID NOT NULL REFERENCES organizations(id)`. Composite indexes on `(org_id, created_at)` etc. (No Postgres RLS for the demo — app-layer is sufficient and easier to debug.)
- **Test rule**: A negative test seeds two orgs and asserts user A cannot read user B's data on every resource.

### 1.5 Background jobs

ARQ is configured in `api/jobs/worker.py`. Jobs are plain async Python functions registered in `WorkerSettings.functions`. Cron jobs registered in `WorkerSettings.cron_jobs`.

| Job | Trigger | Inputs | Output |
|---|---|---|---|
| `ocr_receipt` | API enqueues after upload | `receipt_id` | Updates `receipts.extracted_data`, sets `status` |
| `run_policy_check` | API enqueues on txn POLICY_CHECKED transition | `transaction_id` | Inserts `transaction_policy_results` row, transitions txn |
| `generate_digest` | Cron (Mon 9am IST) + manual API trigger | `org_id` | Inserts `digests` row, fires notification, sends email |

Idempotency: each job is keyed by its target row id, and the row status guards re-runs (`if status != 'pending' return`).

### 1.6 Receipt image flow (end to end)

1. Browser calls `POST /receipts/upload-url` with `{filename, content_type}`. API returns `{receipt_id, upload_url, object_key}` (presigned PUT, 5-min expiry; creates `receipts` row with `status=PENDING_UPLOAD`).
2. Browser uploads bytes directly to E2E Object Storage via that URL.
3. Browser calls `POST /receipts/{id}/confirm`. API verifies the object exists (`HEAD`), sets `status=PROCESSING`, enqueues `ocr_receipt(receipt_id)`.
4. Worker downloads object, base64-encodes, builds the vision prompt, calls LLM via `openai` SDK with `response_format={"type":"json_object"}`.
5. Worker validates response with `ReceiptExtraction` Pydantic schema. On success → `status=COMPLETED`, `extracted_data=<json>`. On schema fail or confidence < 0.7 → `status=NEEDS_REVIEW`.
6. Frontend polls `GET /receipts/{id}`; when `COMPLETED`, auto-fills the transaction form.

---

## 2. LLM PIPELINE DESIGN

All three pipelines share a single thin client: `api/ai/llm_client.py`. It wraps `AsyncOpenAI(base_url=settings.TIR_BASE_URL, api_key=settings.TIR_API_KEY)`, sets `model=settings.TIR_MODEL` (`"llama-3.1-8b-instruct"`), and exposes one method: `complete_json(system, user, schema, temperature, max_tokens)`. It always passes `response_format={"type":"json_object"}`, parses with the supplied Pydantic schema, and on failure retries **once** with the validation error appended to the user message; on second failure, raises `LLMValidationError`.

Every caller catches `LLMValidationError` and writes a `NEEDS_REVIEW` (or equivalent) row instead of crashing.

### 2.1 Pipeline 1 — Receipt OCR

**Trigger:** Worker job `ocr_receipt(receipt_id)`.

**Input:** Receipt image (JPEG/PNG/PDF). PDFs are converted to a single PNG of page 1 via `pdf2image`.

**System prompt:**
```
You are a receipt parser. Extract structured data from the receipt image.
Return ONLY valid JSON matching the schema. Currency must be a 3-letter ISO
4217 code (INR, USD, EUR, GBP). Date must be ISO 8601 (YYYY-MM-DD).
Category must be one of: TRAVEL, MEALS, SAAS, OFFICE, MARKETING, HARDWARE,
PROFESSIONAL_SERVICES, OTHER. If a field is illegible, omit it and lower
the confidence. Confidence is a float 0.0-1.0 reflecting overall extraction
quality.
```

**User message:** Image content + the literal instruction `Return JSON only.`

**Output schema (Pydantic):**
```
ReceiptExtraction:
  merchant: str | None
  amount: Decimal | None        # positive, 2dp
  currency: Literal["INR","USD","EUR","GBP"] | None
  date: date | None
  category: Literal[...] | None
  confidence: float             # required, 0..1
  raw_text: str | None          # optional OCR dump for audit
```

**Settings:** `temperature=0`, `max_tokens=400`.

**Validation logic:**
- Pydantic enforces types and enums.
- If `confidence < 0.7` → `status=NEEDS_REVIEW`, no auto-fill.
- If `amount` present but `merchant` missing → `NEEDS_REVIEW`.
- On `LLMValidationError` → `status=FAILED`, surface error to user with retry button.

**Fallback:** Receipt remains in storage; user can edit the transaction form manually. Worker never blocks the txn flow — OCR is an enrichment step, not a gate.

### 2.2 Pipeline 2 — Plain-English Policy Engine

**Trigger:** Worker job `run_policy_check(transaction_id)`. Enqueued the moment a txn moves from `INITIATED` → `POLICY_CHECKED`.

**Input gathered by job:**
- The transaction (amount, merchant, category, currency, department, user, card).
- All active policies for that org (text strings + ids).

**System prompt:**
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

**User message (templated):**
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

**Output schema (Pydantic):**
```
PolicyVerdict:
  verdict: Literal["APPROVED","FLAGGED","BLOCKED"]
  reason: str                                # <= 200 chars
  policy_matched: str | None                 # verbatim policy text or null
  policy_id: UUID | None                     # if reason references a P# id
  requires_approval_from: Literal["FINANCE_MANAGER","ADMIN"] | None
```

**Settings:** `temperature=0`, `max_tokens=300`.

**Validation logic:**
- Pydantic enforces enum + length.
- If `verdict=FLAGGED` and `requires_approval_from` is null → default to `FINANCE_MANAGER`.
- If `policy_id` is set but does not belong to org → strip it, keep `policy_matched`.
- On `LLMValidationError` → write a `transaction_policy_results` row with `verdict=FLAGGED`, `reason="Policy engine error — manual review required"`, and notify Finance Manager. Transaction does **not** auto-block on LLM failure.

**State machine wiring:**
- `APPROVED` → txn transitions `POLICY_CHECKED → APPROVED → CLEARED`.
- `FLAGGED` → txn transitions `POLICY_CHECKED → FLAGGED`; notification fires; awaits human approval.
- `BLOCKED` → txn transitions `POLICY_CHECKED → BLOCKED` (terminal for this attempt); employee sees the reason.

### 2.3 Pipeline 3 — Weekly Spend Digest

**Trigger:** ARQ cron `Monday 09:00 IST` + `POST /digest/generate` (admin-only, for demo).

**Input gathered by job (per org):**
- Total spend last 7 days, prior 7 days, % delta.
- Top 5 categories by amount.
- Top 10 vendors by amount.
- Subscriptions (txns with category=SAAS and recurring merchant) that had no usage signal — for demo: SaaS vendors charged this week but with zero non-SaaS activity from any user in the last 30 days (proxy heuristic).
- Duplicate vendors: same merchant charged 2+ times within 7 days with similar amounts.
- Anomalies: any single txn > 3× the org's 30-day mean.

The job pre-computes a compact JSON blob (≤ 2KB) and ships it as the user message — the LLM does not see raw transactions.

**System prompt:**
```
You are a CFO assistant. Given a 7-day spend summary, write a concise digest
with specific, actionable recommendations. Be direct. Cite numbers. Do not
hedge. Maximum 250 words. Return JSON only.
```

**User message:** the aggregated JSON, labeled clearly.

**Output schema (Pydantic):**
```
SpendDigest:
  headline: str                              # <= 80 chars
  body: str                                  # <= 1500 chars, markdown allowed
  top_recommendations: list[str]             # 3-5 items, each <= 120 chars
  flagged_items: list[FlaggedItem]           # 0-10 items
    FlaggedItem:
      type: Literal["DUPLICATE","UNUSED_SAAS","ANOMALY"]
      description: str
      amount: Decimal
```

**Settings:** `temperature=0.3`, `max_tokens=900`.

**Validation:** Pydantic + a post-check that total body word count ≤ 250. If over, truncate and append `…` (do not re-prompt — digest is non-critical).

**Fallback:** On `LLMValidationError`, store a `digests` row with `status=FAILED` and the raw aggregated JSON; UI shows "Digest generation failed — view raw data".

**Delivery:** Insert `digests` row → fire `NotificationType.DIGEST_READY` for every ADMIN and FINANCE_MANAGER in the org → send email via SMTP (or Resend if configured) with the headline + body + link to dashboard.

---

## 3. DOCKER COMPOSE STRUCTURE

Single `docker-compose.yml` at repo root. One `Dockerfile` per app (`api/Dockerfile`, `web/Dockerfile`). Production compose file `docker-compose.prod.yml` overrides volumes and disables hot reload.

### 3.1 Services

| Service | Image | Ports | Depends on | Notes |
|---|---|---|---|---|
| `web` | built from `web/Dockerfile` | `5173:5173` (dev) / `80:80` (prod nginx) | `api` | Vite dev server with HMR in dev; nginx serving static + reverse-proxy `/api` to `api:8000` in prod |
| `api` | built from `api/Dockerfile` | `8000:8000` | `db`, `redis` | Gunicorn + uvicorn workers; runs Alembic migrations on entrypoint |
| `worker` | same image as `api` | — | `db`, `redis` | Command override: `arq api.jobs.worker.WorkerSettings` |
| `db` | `postgres:15-alpine` | `5432:5432` | — | Volume: `pgdata:/var/lib/postgresql/data` |
| `redis` | `redis:7-alpine` | `6379:6379` | — | Volume: `redisdata:/data` |
| `mailhog` | `mailhog/mailhog` | `1025:1025` (SMTP), `8025:8025` (UI) | — | Dev only — captures digest emails |

### 3.2 Volumes

- `pgdata` — Postgres data
- `redisdata` — Redis AOF
- `./api:/app` — bind mount in dev (for hot reload via uvicorn `--reload`)
- `./web:/app` — bind mount in dev
- `node_modules` — named volume to avoid host overlay

### 3.3 Networks

Single bridge network `vault_net`. All services on it. No port exposure for `db` / `redis` in prod compose.

### 3.4 Environment variables

Loaded from `.env` at repo root. Listed in `.env.example`.

```
# --- App ---
APP_ENV=dev                          # dev | prod
APP_SECRET_KEY=<long-random>         # JWT signing
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=60
JWT_REFRESH_TTL_DAYS=14
CORS_ORIGINS=http://localhost:5173

# --- Database ---
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=vault
POSTGRES_USER=vault
POSTGRES_PASSWORD=<random>
DATABASE_URL=postgresql+asyncpg://vault:<pwd>@db:5432/vault

# --- Redis ---
REDIS_URL=redis://redis:6379/0
ARQ_REDIS_URL=redis://redis:6379/1

# --- LLM (E2E TIR) ---
TIR_BASE_URL=https://infer.e2enetworks.net/project/<id>/endpoint/<id>/v1
TIR_API_KEY=<token>
TIR_MODEL=llama-3.1-8b-instruct
TIR_TIMEOUT_SECONDS=60

# --- Object Storage (E2E S3-compatible) ---
S3_ENDPOINT_URL=https://objectstore.e2enetworks.net
S3_REGION=ap-south-1
S3_BUCKET=vault-receipts
S3_ACCESS_KEY=<key>
S3_SECRET_KEY=<secret>
S3_PRESIGN_TTL_SECONDS=300

# --- Email ---
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=digest@vault.local

# --- Frontend ---
VITE_API_BASE_URL=http://localhost:8000
```

### 3.5 Boot order

`docker compose up` → `db` and `redis` start → `api` waits for both (healthcheck `pg_isready`, `redis-cli ping`) → `api` runs `alembic upgrade head` then `gunicorn` → `worker` starts → `web` starts.

---

## 4. DATABASE SCHEMA

PostgreSQL 15. UUID PKs via `gen_random_uuid()` from `pgcrypto`. All enums declared as Postgres `ENUM` types for query speed + Alembic-friendly migrations. All FKs indexed. `created_at` / `updated_at` everywhere; `updated_at` auto-maintained via a single shared trigger.

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ============================================================
-- SHARED updated_at TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE user_role AS ENUM ('ADMIN', 'FINANCE_MANAGER', 'EMPLOYEE');

CREATE TYPE card_status AS ENUM ('ACTIVE', 'FROZEN', 'CANCELLED');

CREATE TYPE transaction_state AS ENUM (
  'INITIATED',
  'POLICY_CHECKED',
  'APPROVED',
  'FLAGGED',
  'BLOCKED',
  'CLEARED',
  'SETTLED'
);

CREATE TYPE policy_verdict AS ENUM ('APPROVED', 'FLAGGED', 'BLOCKED');

CREATE TYPE spend_category AS ENUM (
  'TRAVEL', 'MEALS', 'SAAS', 'OFFICE',
  'MARKETING', 'HARDWARE', 'PROFESSIONAL_SERVICES', 'OTHER'
);

CREATE TYPE receipt_status AS ENUM (
  'PENDING_UPLOAD', 'PROCESSING', 'COMPLETED', 'NEEDS_REVIEW', 'FAILED'
);

CREATE TYPE reimbursement_status AS ENUM (
  'SUBMITTED', 'POLICY_CHECKED', 'APPROVED', 'REJECTED', 'PAID'
);

CREATE TYPE notification_type AS ENUM (
  'POLICY_FLAGGED', 'POLICY_BLOCKED',
  'APPROVAL_REQUESTED', 'APPROVAL_GRANTED', 'APPROVAL_REJECTED',
  'BUDGET_THRESHOLD', 'DIGEST_READY', 'RECEIPT_REVIEW_NEEDED'
);

CREATE TYPE digest_status AS ENUM ('PENDING', 'COMPLETED', 'FAILED');

-- ============================================================
-- organizations
-- ============================================================
CREATE TABLE organizations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  slug            CITEXT NOT NULL UNIQUE,
  base_currency   CHAR(3) NOT NULL DEFAULT 'INR',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER organizations_set_updated_at
  BEFORE UPDATE ON organizations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- users
-- ============================================================
CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email           CITEXT NOT NULL,
  password_hash   TEXT NOT NULL,
  full_name       TEXT NOT NULL,
  role            user_role NOT NULL DEFAULT 'EMPLOYEE',
  department_id   UUID NULL,  -- FK added after departments table created
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at   TIMESTAMPTZ NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, email)
);
CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_users_role ON users(org_id, role);
CREATE INDEX idx_users_department ON users(department_id);
CREATE TRIGGER users_set_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- departments
-- ============================================================
CREATE TABLE departments (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name                TEXT NOT NULL,
  monthly_budget      NUMERIC(14,2) NOT NULL DEFAULT 0,
  budget_currency     CHAR(3) NOT NULL DEFAULT 'INR',
  alert_threshold_pct INTEGER NOT NULL DEFAULT 80
                       CHECK (alert_threshold_pct BETWEEN 1 AND 100),
  manager_id          UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, name)
);
CREATE INDEX idx_departments_org ON departments(org_id);
CREATE INDEX idx_departments_manager ON departments(manager_id);
CREATE TRIGGER departments_set_updated_at
  BEFORE UPDATE ON departments
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Now add the deferred FK on users.department_id
ALTER TABLE users
  ADD CONSTRAINT fk_users_department
  FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL;

-- ============================================================
-- cards
-- ============================================================
CREATE TABLE cards (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  department_id           UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
  nickname                TEXT NOT NULL,
  last_four               CHAR(4) NOT NULL,
  status                  card_status NOT NULL DEFAULT 'ACTIVE',
  daily_limit             NUMERIC(14,2) NOT NULL DEFAULT 0,
  monthly_limit           NUMERIC(14,2) NOT NULL DEFAULT 0,
  total_limit             NUMERIC(14,2) NOT NULL DEFAULT 0,
  category_restrictions   spend_category[] NOT NULL DEFAULT '{}',
  currency                CHAR(3) NOT NULL DEFAULT 'INR',
  frozen_at               TIMESTAMPTZ NULL,
  cancelled_at            TIMESTAMPTZ NULL,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (daily_limit   >= 0),
  CHECK (monthly_limit >= 0),
  CHECK (total_limit   >= 0)
);
CREATE INDEX idx_cards_org ON cards(org_id);
CREATE INDEX idx_cards_user ON cards(user_id);
CREATE INDEX idx_cards_status ON cards(org_id, status);
CREATE INDEX idx_cards_department ON cards(department_id);
CREATE TRIGGER cards_set_updated_at
  BEFORE UPDATE ON cards
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- policies (plain-English)
-- ============================================================
CREATE TABLE policies (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  text              TEXT NOT NULL,
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_by        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_policies_org_active ON policies(org_id, is_active);
CREATE INDEX idx_policies_created_by ON policies(created_by);
CREATE TRIGGER policies_set_updated_at
  BEFORE UPDATE ON policies
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- transactions
-- ============================================================
CREATE TABLE transactions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  card_id             UUID NOT NULL REFERENCES cards(id) ON DELETE RESTRICT,
  department_id       UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
  amount              NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  currency            CHAR(3) NOT NULL DEFAULT 'INR',
  merchant            TEXT NOT NULL,
  category            spend_category NOT NULL DEFAULT 'OTHER',
  state               transaction_state NOT NULL DEFAULT 'INITIATED',
  description         TEXT NULL,
  occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  receipt_id          UUID NULL,  -- FK added after receipts table
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_txn_org_occurred ON transactions(org_id, occurred_at DESC);
CREATE INDEX idx_txn_user ON transactions(user_id);
CREATE INDEX idx_txn_card ON transactions(card_id);
CREATE INDEX idx_txn_dept ON transactions(department_id);
CREATE INDEX idx_txn_state ON transactions(org_id, state);
CREATE INDEX idx_txn_category ON transactions(org_id, category);
CREATE INDEX idx_txn_merchant ON transactions(org_id, merchant);
CREATE TRIGGER transactions_set_updated_at
  BEFORE UPDATE ON transactions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- transaction_events (append-only state-machine audit log)
-- ============================================================
CREATE TABLE transaction_events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id      UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  from_state          transaction_state NULL,
  to_state            transaction_state NOT NULL,
  triggered_by_user   UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  triggered_by_system BOOLEAN NOT NULL DEFAULT FALSE,
  reason              TEXT NULL,
  metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (
    (triggered_by_user IS NOT NULL AND triggered_by_system = FALSE)
    OR
    (triggered_by_user IS NULL AND triggered_by_system = TRUE)
  )
);
CREATE INDEX idx_txn_events_txn ON transaction_events(transaction_id, created_at);
CREATE INDEX idx_txn_events_org ON transaction_events(org_id, created_at DESC);
-- append-only: revoke UPDATE/DELETE at the role level in deployment

-- ============================================================
-- transaction_policy_results (LLM policy verdicts)
-- ============================================================
CREATE TABLE transaction_policy_results (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  transaction_id              UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  verdict                     policy_verdict NOT NULL,
  reason                      TEXT NOT NULL,
  policy_matched              TEXT NULL,
  matched_policy_id           UUID NULL REFERENCES policies(id) ON DELETE SET NULL,
  requires_approval_from_role user_role NULL,
  raw_llm_response            JSONB NOT NULL,
  llm_model                   TEXT NOT NULL,
  llm_latency_ms              INTEGER NULL,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_tpr_txn ON transaction_policy_results(transaction_id);
CREATE INDEX idx_tpr_org_verdict ON transaction_policy_results(org_id, verdict);
CREATE INDEX idx_tpr_policy ON transaction_policy_results(matched_policy_id);

-- ============================================================
-- receipts
-- ============================================================
CREATE TABLE receipts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  uploaded_by       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  transaction_id    UUID NULL REFERENCES transactions(id) ON DELETE SET NULL,
  reimbursement_id  UUID NULL,
  object_key        TEXT NOT NULL,
  content_type      TEXT NOT NULL,
  byte_size         BIGINT NULL,
  status            receipt_status NOT NULL DEFAULT 'PENDING_UPLOAD',
  extracted_data    JSONB NULL,
  confidence        NUMERIC(4,3) NULL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  llm_error         TEXT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_receipts_org ON receipts(org_id, created_at DESC);
CREATE INDEX idx_receipts_txn ON receipts(transaction_id);
CREATE INDEX idx_receipts_reimb ON receipts(reimbursement_id);
CREATE INDEX idx_receipts_status ON receipts(org_id, status);
CREATE TRIGGER receipts_set_updated_at
  BEFORE UPDATE ON receipts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Deferred FK on transactions.receipt_id
ALTER TABLE transactions
  ADD CONSTRAINT fk_transactions_receipt
  FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE SET NULL;

-- ============================================================
-- reimbursements
-- ============================================================
CREATE TABLE reimbursements (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  department_id     UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
  amount            NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  currency          CHAR(3) NOT NULL DEFAULT 'INR',
  category          spend_category NOT NULL DEFAULT 'OTHER',
  description       TEXT NOT NULL,
  receipt_id        UUID NULL REFERENCES receipts(id) ON DELETE SET NULL,
  status            reimbursement_status NOT NULL DEFAULT 'SUBMITTED',
  decision_reason   TEXT NULL,
  decided_by        UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  decided_at        TIMESTAMPTZ NULL,
  paid_at           TIMESTAMPTZ NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_reimb_org_status ON reimbursements(org_id, status);
CREATE INDEX idx_reimb_user ON reimbursements(user_id);
CREATE INDEX idx_reimb_decided_by ON reimbursements(decided_by);
CREATE TRIGGER reimbursements_set_updated_at
  BEFORE UPDATE ON reimbursements
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Backfill the receipts -> reimbursements FK
ALTER TABLE receipts
  ADD CONSTRAINT fk_receipts_reimbursement
  FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE SET NULL;

-- ============================================================
-- digests (weekly AI spend digest, one per org per week)
-- ============================================================
CREATE TABLE digests (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start      DATE NOT NULL,
  period_end        DATE NOT NULL,
  status            digest_status NOT NULL DEFAULT 'PENDING',
  headline          TEXT NULL,
  body              TEXT NULL,
  top_recommendations JSONB NULL,
  flagged_items     JSONB NULL,
  aggregated_input  JSONB NOT NULL,
  raw_llm_response  JSONB NULL,
  llm_error         TEXT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, period_start, period_end)
);
CREATE INDEX idx_digests_org_period ON digests(org_id, period_end DESC);
CREATE TRIGGER digests_set_updated_at
  BEFORE UPDATE ON digests
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- notifications
-- ============================================================
CREATE TABLE notifications (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type              notification_type NOT NULL,
  title             TEXT NOT NULL,
  body              TEXT NOT NULL,
  link              TEXT NULL,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  read_at           TIMESTAMPTZ NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notif_user_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;
CREATE INDEX idx_notif_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notif_org ON notifications(org_id);
CREATE TRIGGER notifications_set_updated_at
  BEFORE UPDATE ON notifications
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- refresh_tokens (JWT refresh persistence)
-- ============================================================
CREATE TABLE refresh_tokens (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash      TEXT NOT NULL UNIQUE,
  expires_at      TIMESTAMPTZ NOT NULL,
  revoked_at      TIMESTAMPTZ NULL,
  user_agent      TEXT NULL,
  ip              INET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_expires ON refresh_tokens(expires_at);

-- ============================================================
-- audit_log (general administrative audit; optional but recommended)
-- ============================================================
CREATE TABLE audit_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id   UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  action          TEXT NOT NULL,            -- e.g. 'card.freeze', 'policy.create'
  entity_type     TEXT NOT NULL,            -- e.g. 'card', 'policy'
  entity_id       UUID NULL,
  metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_org_created ON audit_log(org_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_actor ON audit_log(actor_user_id);
```

---

## 5. FOLDER STRUCTURE

```
vault/
├── README.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
├── .editorconfig
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── PHASES.md
│   ├── PROBLEMS.md
│   ├── STACK.md
│   └── API.md
│
├── api/                                  # FastAPI backend (monolith)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app, mounts routers
│   │   ├── config.py                     # Pydantic Settings
│   │   ├── logging.py
│   │   ├── deps.py                       # get_db, get_current_user, require_role, get_org_scope
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # async engine + sessionmaker
│   │   │   └── seeds.py                  # demo seed script
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── organization.py
│   │   │   ├── user.py
│   │   │   ├── department.py
│   │   │   ├── card.py
│   │   │   ├── transaction.py
│   │   │   ├── transaction_event.py
│   │   │   ├── transaction_policy_result.py
│   │   │   ├── receipt.py
│   │   │   ├── policy.py
│   │   │   ├── reimbursement.py
│   │   │   ├── digest.py
│   │   │   ├── notification.py
│   │   │   ├── refresh_token.py
│   │   │   └── audit_log.py
│   │   ├── schemas/                      # Pydantic v2 request/response
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── card.py
│   │   │   ├── transaction.py
│   │   │   ├── receipt.py
│   │   │   ├── policy.py
│   │   │   ├── reimbursement.py
│   │   │   ├── department.py
│   │   │   ├── digest.py
│   │   │   └── notification.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── cards.py
│   │   │   ├── transactions.py
│   │   │   ├── receipts.py
│   │   │   ├── policies.py
│   │   │   ├── reimbursements.py
│   │   │   ├── departments.py
│   │   │   ├── digest.py
│   │   │   ├── notifications.py
│   │   │   └── dashboard.py
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── card_service.py
│   │   │   ├── transaction_service.py    # state machine lives here
│   │   │   ├── receipt_service.py
│   │   │   ├── policy_service.py
│   │   │   ├── reimbursement_service.py
│   │   │   ├── department_service.py
│   │   │   ├── digest_service.py
│   │   │   ├── notification_service.py
│   │   │   └── dashboard_service.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py
│   │   │   ├── prompts.py                # system + user templates
│   │   │   ├── schemas.py                # Pydantic: ReceiptExtraction, PolicyVerdict, SpendDigest
│   │   │   └── validators.py
│   │   ├── jobs/
│   │   │   ├── __init__.py
│   │   │   ├── worker.py                 # ARQ WorkerSettings
│   │   │   ├── ocr_receipt.py
│   │   │   ├── run_policy_check.py
│   │   │   └── generate_digest.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── s3.py                     # presign + get/put helpers
│   │   ├── email/
│   │   │   ├── __init__.py
│   │   │   └── sender.py
│   │   └── utils/
│   │       ├── security.py               # password hash, JWT encode/decode
│   │       ├── pagination.py             # cursor pagination helpers
│   │       └── time.py
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_multitenancy.py
│       ├── test_transactions_state_machine.py
│       ├── test_policy_engine.py
│       ├── test_receipts_ocr.py
│       ├── test_reimbursements.py
│       └── test_digest.py
│
└── web/                                  # React frontend
    ├── Dockerfile
    ├── nginx.conf                        # prod reverse proxy
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── index.html
    ├── public/
    │   └── favicon.svg
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── router.tsx
        ├── lib/
        │   ├── api.ts                    # axios client + interceptors
        │   ├── auth.ts                   # token storage + helpers
        │   ├── query.ts                  # React Query client
        │   ├── format.ts                 # currency, date helpers
        │   └── sse.ts
        ├── components/
        │   ├── ui/                       # shadcn primitives (auto-generated)
        │   ├── layout/
        │   │   ├── AppShell.tsx
        │   │   ├── Sidebar.tsx
        │   │   └── NavBar.tsx
        │   ├── auth/
        │   │   └── RequireAuth.tsx
        │   ├── transactions/
        │   │   ├── TransactionTable.tsx
        │   │   ├── TransactionDetail.tsx
        │   │   ├── TransactionStateBadge.tsx
        │   │   └── NewTransactionDialog.tsx
        │   ├── receipts/
        │   │   ├── ReceiptUploader.tsx
        │   │   └── ReceiptPreview.tsx
        │   ├── policies/
        │   │   ├── PolicyList.tsx
        │   │   └── PolicyEditor.tsx
        │   ├── cards/
        │   │   ├── CardList.tsx
        │   │   └── CardForm.tsx
        │   ├── reimbursements/
        │   │   ├── ReimbursementForm.tsx
        │   │   └── ApprovalQueue.tsx
        │   ├── departments/
        │   │   └── DepartmentBudgetBar.tsx
        │   ├── dashboard/
        │   │   ├── SpendByCategoryChart.tsx
        │   │   ├── SpendByDeptChart.tsx
        │   │   ├── SpendOverTimeChart.tsx
        │   │   └── KpiCards.tsx
        │   ├── digest/
        │   │   └── DigestPanel.tsx
        │   └── notifications/
        │       ├── NotificationBell.tsx
        │       └── NotificationList.tsx
        ├── features/
        │   ├── auth/                     # hooks: useLogin, useLogout, useMe
        │   ├── transactions/             # hooks: useTransactions, useCreateTxn
        │   ├── receipts/
        │   ├── policies/
        │   ├── cards/
        │   ├── reimbursements/
        │   ├── departments/
        │   ├── digest/
        │   └── notifications/
        ├── pages/
        │   ├── LoginPage.tsx
        │   ├── SignupPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── TransactionsPage.tsx
        │   ├── CardsPage.tsx
        │   ├── PoliciesPage.tsx
        │   ├── ReimbursementsPage.tsx
        │   ├── DepartmentsPage.tsx
        │   ├── DigestPage.tsx
        │   └── SettingsPage.tsx
        └── types/
            └── api.ts                    # generated/maintained types
```

---

## 6. API ROUTES

All routes under `/api/v1`. JSON only. `Authorization: Bearer <jwt>` required except where noted. Standard error envelope: `{"error": {"code": "...", "message": "..."}}`. All list endpoints support `?limit=<int, default 25, max 100>` and `?cursor=<opaque>`.

### Auth
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/auth/signup` | No | `{org_name, email, password, full_name}` | `{access_token, refresh_token, user}` |
| POST | `/auth/login` | No | `{email, password}` | `{access_token, refresh_token, user}` |
| POST | `/auth/refresh` | No (refresh token) | `{refresh_token}` | `{access_token, refresh_token}` |
| POST | `/auth/logout` | Yes | `{refresh_token}` | `{ok: true}` |
| GET | `/auth/me` | Yes | — | `{user, org}` |

### Users (ADMIN unless noted)
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/users` | Yes (any) | — | `{items, next_cursor}` |
| POST | `/users` | ADMIN | `{email, full_name, role, department_id?}` | `{user, invite_token}` |
| GET | `/users/{id}` | Yes (self or ADMIN/FM) | — | `{user}` |
| PATCH | `/users/{id}` | ADMIN | partial | `{user}` |
| DELETE | `/users/{id}` | ADMIN | — | `{ok: true}` |

### Cards
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/cards` | Yes (scoped to user unless ADMIN/FM) | — | `{items, next_cursor}` |
| POST | `/cards` | ADMIN | `{user_id, nickname, daily_limit, monthly_limit, total_limit, category_restrictions, department_id?}` | `{card}` |
| GET | `/cards/{id}` | Yes (owner or ADMIN/FM) | — | `{card}` |
| PATCH | `/cards/{id}` | ADMIN | partial | `{card}` |
| POST | `/cards/{id}/freeze` | ADMIN | — | `{card}` |
| POST | `/cards/{id}/unfreeze` | ADMIN | — | `{card}` |
| POST | `/cards/{id}/cancel` | ADMIN | — | `{card}` |

### Transactions
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/transactions` | Yes (scoped) | filters: `?from=&to=&category=&department_id=&card_id=&user_id=&state=` | `{items, next_cursor}` |
| POST | `/transactions` | Yes (mock create) | `{card_id, amount, currency, merchant, category, description?, occurred_at?, receipt_id?}` | `{transaction}` (state=INITIATED, policy job enqueued) |
| GET | `/transactions/{id}` | Yes (owner or ADMIN/FM) | — | `{transaction, events, policy_result}` |
| POST | `/transactions/{id}/approve` | FINANCE_MANAGER, ADMIN | `{reason?}` | `{transaction}` |
| POST | `/transactions/{id}/reject` | FINANCE_MANAGER, ADMIN | `{reason}` | `{transaction}` |
| GET | `/transactions/{id}/events` | Yes (owner or ADMIN/FM) | — | `{items}` |

### Receipts
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/receipts/upload-url` | Yes | `{filename, content_type}` | `{receipt_id, upload_url, object_key, expires_at}` |
| POST | `/receipts/{id}/confirm` | Yes | — | `{receipt}` (status=PROCESSING) |
| GET | `/receipts/{id}` | Yes (uploader or ADMIN/FM) | — | `{receipt}` |
| POST | `/receipts/{id}/link` | Yes | `{transaction_id?, reimbursement_id?}` | `{receipt}` |
| POST | `/receipts/{id}/retry` | Yes | — | `{receipt}` (re-enqueues OCR) |

### Policies
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/policies` | Yes (any) | `?active=true` | `{items, next_cursor}` |
| POST | `/policies` | ADMIN | `{text, is_active?}` | `{policy}` |
| PATCH | `/policies/{id}` | ADMIN | `{text?, is_active?}` | `{policy}` |
| DELETE | `/policies/{id}` | ADMIN | — | `{ok: true}` |

### Reimbursements
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/reimbursements` | Yes (scoped) | `?status=&user_id=` | `{items, next_cursor}` |
| POST | `/reimbursements` | EMPLOYEE+ | `{amount, currency, category, description, receipt_id?, department_id?}` | `{reimbursement}` |
| GET | `/reimbursements/{id}` | Yes (owner or ADMIN/FM) | — | `{reimbursement, policy_result?}` |
| POST | `/reimbursements/{id}/approve` | FINANCE_MANAGER, ADMIN | `{reason?}` | `{reimbursement}` |
| POST | `/reimbursements/{id}/reject` | FINANCE_MANAGER, ADMIN | `{reason}` | `{reimbursement}` |
| POST | `/reimbursements/{id}/mark-paid` | FINANCE_MANAGER, ADMIN | — | `{reimbursement}` |

### Departments
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/departments` | Yes (any) | — | `{items}` |
| POST | `/departments` | ADMIN | `{name, monthly_budget, alert_threshold_pct?, manager_id?}` | `{department}` |
| PATCH | `/departments/{id}` | ADMIN | partial | `{department}` |
| DELETE | `/departments/{id}` | ADMIN | — | `{ok: true}` |
| GET | `/departments/{id}/budget-status` | ADMIN, FM | — | `{spent, budget, pct, period_start, period_end}` |

### Dashboard
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/dashboard/summary` | ADMIN, FM | `?from=&to=` | `{total_spend, mom_delta_pct, by_category, by_department, by_card, top_merchants}` |
| GET | `/dashboard/timeseries` | ADMIN, FM | `?from=&to=&granularity=day|week` | `{points: [{date, amount}]}` |

### Digest
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/digest` | ADMIN, FM | — | `{items}` (last 12 weeks) |
| GET | `/digest/{id}` | ADMIN, FM | — | `{digest}` |
| POST | `/digest/generate` | ADMIN | — | `{digest_id, status: "pending"}` |

### Notifications
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/notifications` | Yes | `?unread=true` | `{items, unread_count, next_cursor}` |
| POST | `/notifications/{id}/read` | Yes (owner) | — | `{ok: true}` |
| POST | `/notifications/read-all` | Yes | — | `{ok: true, count}` |
| GET | `/notifications/stream` | Yes | — | SSE stream |

### Health
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | No | `{db: "ok", redis: "ok", tir: "ok", version}` |

**Error responses (standard across all endpoints):**
- `400` — validation error (Pydantic)
- `401` — missing/invalid/expired token
- `403` — wrong role or cross-tenant access
- `404` — not found (or not in this org — collapsed for security)
- `409` — state-machine violation (e.g., approving a BLOCKED txn)
- `422` — semantic validation (e.g., card frozen)
- `429` — rate limit (LLM-fronting routes)
- `500` — unhandled

---

## 7. IMPLEMENTATION PLAN

Solo developer + AI assistance, targeting end-of-Monday demo. Assume start = **Tuesday 2026-05-26** (today), demo = **Monday 2026-06-01** EOD. Seven calendar days, but Day 7 is buffer + rehearsal. Each day ≈ 8 productive hours.

---

### Day 1 (Tue) — Foundations
**Goal:** Repo, infra, auth shell, one round-trip from browser to DB.
- Repo scaffolded: `api/`, `web/`, `docs/`, `docker-compose.yml`, `.env.example`.
- `docker compose up` brings up `db`, `redis`, `api`, `web`, `mailhog` healthy.
- Alembic baseline migration creating **all** tables from Section 4 applied successfully.
- FastAPI: `/health` returns 200 with db+redis+tir checks.
- Auth: `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/me` working; bcrypt password hash; JWT issued + refresh token row persisted.
- Frontend: Login + Signup pages; React Query + Axios interceptor; protected route shell; landing page shows logged-in user.
- Seed script: 1 org, 1 ADMIN user, 1 FM, 2 EMPLOYEEs, 2 departments, 4 cards.

**Testable:** Sign up an org, log in, see "Welcome, {name}" page. `GET /auth/me` works in browser devtools.

---

### Day 2 (Wed) — Cards, RBAC, Multi-tenancy enforcement
**Goal:** Locked-down org boundary + first real CRUD resource.
- `get_current_user`, `require_role`, `get_org_scope` dependencies done and unit-tested.
- Cards: full CRUD + `freeze`/`unfreeze`/`cancel` endpoints; service writes to `audit_log`.
- Negative multi-tenancy test: user from Org A cannot read/list/modify any card from Org B (expects 404).
- Frontend: Cards page (list, create, freeze/unfreeze with confirmation dialog); shadcn DataTable.
- Users: list + invite (ADMIN); change role.

**Testable:** ADMIN creates a card, assigns it to an employee, freezes it. Employee logs in, sees only their own card. Cross-org attempt returns 404.

---

### Day 3 (Thu) — Transactions + State Machine (CRITICAL PATH)
**Goal:** Transaction lifecycle end-to-end without LLM (LLM stubbed).
- `transactions` + `transaction_events` tables and SQLAlchemy models.
- `TransactionService` implements the state machine: `transition(txn, to_state, actor, reason)` validates legal transitions, writes append-only event, updates `transactions.state`.
- Endpoints: `POST /transactions`, `GET /transactions`, `GET /transactions/{id}`, `/approve`, `/reject`, `/events`.
- Mock policy result inserted on create (verdict=APPROVED) so flow reaches CLEARED — LLM goes in tomorrow.
- Frontend: Transactions page with table (filters: date, category, dept, state); detail drawer showing event timeline; "New transaction" dialog.

**Testable:** Create a transaction; see it pass through INITIATED → POLICY_CHECKED → APPROVED → CLEARED in the timeline. FM can reject a FLAGGED txn (manually toggle state via DB for now).

---

### Day 4 (Fri) — LLM Pipelines 1 & 2 (Receipts + Policies)
**Goal:** Both demo-critical AI features live.
- S3 wiring: `/receipts/upload-url`, `/receipts/{id}/confirm`. Verified upload to E2E Object Storage from browser.
- ARQ worker container running; `ocr_receipt` job hits TIR with Llama 3.1 8B Instruct, validates via `ReceiptExtraction` Pydantic schema, writes `extracted_data`, sets status.
- Receipt upload UI: drag-and-drop, preview, polling for OCR status, auto-fill into transaction form on completion.
- `policies` CRUD + `PoliciesPage` (textarea per policy, active toggle).
- `run_policy_check` job: pulls active policies, calls LLM, writes `transaction_policy_results` row, advances state to APPROVED/FLAGGED/BLOCKED; fires notification on flag/block.
- Replace the Day-3 mock with the real policy job.

**Testable:** Upload a real receipt photo → see merchant/amount auto-fill within ~5s. Create a policy "No alcohol over ₹2000" → submit a matching txn → see it FLAGGED with the exact policy text quoted.

---

### Day 5 (Sat) — Dashboard + Reimbursements + Departments
**Goal:** Visual product surface + the other money-movement flow.
- `dashboard_service`: server-side aggregations (total, by category, by department, MoM delta, timeseries). Cached in Redis 5min.
- DashboardPage: KPI cards + Recharts (pie by category, bar by department, area by week).
- Reimbursements: full flow (create with receipt, policy check reused, FM approval queue, mark-paid).
- Departments: CRUD + monthly budget; `GET /departments/{id}/budget-status` computes current-month spend; UI shows progress bar with alert at 80%.

**Testable:** Demo dashboard with $X spent broken down by category. Employee submits a reimbursement → FM sees it in queue → approves → it appears in dashboard total.

---

### Day 6 (Sun) — Digest + Notifications + Polish
**Goal:** Third LLM feature + the small UX details that make it feel real.
- `generate_digest` job: aggregator + LLM call + `digests` row + notifications + email through MailHog.
- `POST /digest/generate` for manual trigger (demo button). ARQ cron registered for Monday 09:00.
- DigestPage: list of past digests + latest digest rendered (headline, body, recommendations, flagged items).
- Notifications: `GET /notifications`, mark-read, NotificationBell in navbar with unread count, SSE `/stream` (polling fallback if SSE is fiddly). Budget threshold notification fires when dept hits 80%.
- UI polish pass: empty states, loading skeletons, toast on errors, consistent spacing, Vault branding (logo, color tokens).

**Testable:** Click "Generate weekly digest" → within ~15s a digest appears with real numbers and CFO-style recommendations. MailHog shows the email. Budget alert appears in the bell when threshold is crossed.

---

### Day 7 (Mon) — Demo hardening + rehearsal
**Goal:** Nothing breaks during the live demo.
- End-to-end demo script: signup → invite team → create cards → write policies → upload receipts → create txns (one approved, one flagged, one blocked) → submit reimbursement → check dashboard → trigger digest.
- Seed an org with a *richer* dataset: ~60 historical transactions across 4 weeks so the dashboard charts and digest have substance.
- Run the entire script three times back-to-back. Fix anything that flickers.
- Record a 3-minute screen capture as a fallback.
- Deploy to E2E Cloud (build images, push, `docker compose -f docker-compose.prod.yml up -d`); verify with smoke test.

**Testable:** Live demo runs front-to-back in ≤ 10 minutes with no manual DB fixes.

---

**Trim plan if behind schedule** (in this order — top items get cut first):
1. Email delivery (digest works in-app only)
2. SSE for notifications (polling is fine)
3. Department budgets + alerts
4. Audit log writes (keep table, skip writes for non-critical actions)
5. Reimbursements (huge cut — keep only txn flow)

**Never cut:** transaction state machine, receipt OCR, policy engine. These are the demo.

---

Now writing the 7 documentation files to disk.

---

---

---

# Part 3 — Phase Implementation Prompts

These are the prompts that were given to a separate Claude Code session to implement each phase. They were written after each phase was verified, incorporating all patterns, deviations, and fixes discovered in previous phases. The purpose of these prompts is to keep each implementation session aligned with the master plan and the existing codebase — so nothing drifts, nothing gets re-invented, and no already-solved problem gets hit again.

---

## Phase 2 Prompt — Cards, RBAC & Multi-Tenancy Enforcement

You are continuing the **Vault** project. Working directory: `/Users/namanmoudgill13/Desktop/Vault/`

**Read `docs/MASTER_PLAN.md` in full before writing a single line of code.** It contains the original architectural prompt, the full master plan, the complete DB schema, and a briefing header that tells you the exact current state of the project.

**Phase 1 is complete.** The stack boots, auth works end to end, and the React app renders. Your job is Phase 2.

---

### What Phase 1 left you

- `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` — all working
- JWT signed HS256, refresh token persisted in `refresh_tokens` table
- `api/api/db/base.py` uses lazy engine/session_factory initialization — prevents asyncpg import at module load, lets unit tests run without asyncpg installed
- `api/api/config.py` has `APP_SECRET_KEY` min-length validator (≥32 chars)
- React app boots: `LoginPage`, `SignupPage`, `DashboardPage` render; axios interceptor attaches `Authorization` header; 401 redirects to `/login`
- Seed script creates 1 org + 4 users (ADMIN, FINANCE_MANAGER, 2 EMPLOYEEs)
- API runs on host port **8001** (remapped from 8000 — port conflict). `VITE_API_BASE_URL=http://localhost:8001`

**Phase 1 security fixes already applied — do not re-open these:**
- Login `MultipleResultsFound` → fixed by migration `0002_global_email_unique` (global `UNIQUE(email)`) + `MultipleResultsFound` catch in login → 401
- Login timing oracle → `_DUMMY_HASH` computed at module import, always run `verify_password` before raising 401
- Refresh token race → `with_for_update().execution_options(populate_existing=True)`
- Missing `Department` ORM model → created `api/api/models/department.py`, registered in `__init__.py`
- Refresh JWT `jti` added to prevent hash collision on same-second issuance

---

### Hard rules — never violate

- **Never commit `.env` or secrets**
- **Never add `Co-Authored-By Claude` to git commits**
- **Database changes always go through Alembic** — never edit schema by hand on a running container
- **`org_id` for scoping always comes from the JWT** — never from request body or path
- **Cross-org access must return 404, never 403** — never leak that a resource exists in another org
- **`audit_log` is append-only** — no DELETE/UPDATE in code
- **Money stored as `NUMERIC(14,2)`**, never float
- **`metadata` is reserved by SQLAlchemy `DeclarativeBase`** — if your DB column is named `metadata`, use Python attribute `log_metadata` with `mapped_column("metadata", JSONB, ...)`
- **Run tests with `python -m pytest -q`** — bare `pytest -q` fails import collection

---

### What to build

#### 1. FastAPI dependencies (`api/api/deps.py`)

```python
@dataclass
class CurrentUser:
    user_id: UUID
    org_id: UUID
    role: UserRole

@dataclass
class OrgScope:
    db: AsyncSession
    org_id: UUID
    user_id: UUID
    role: UserRole

async def get_current_user(...) -> CurrentUser: ...
def require_role(*allowed: UserRole): ...
async def get_org_scope(...) -> OrgScope: ...
```

`get_current_user` decodes the JWT, verifies `type == "access"`, loads the user from DB, asserts `user.is_active` and `user.org_id == jwt.org_id`. FastAPI caches dependencies per request — `get_org_scope` and `require_role` both depend on `get_current_user` but it only runs once.

#### 2. Cards — ORM, schemas, service, router

**ORM** (`api/api/models/card.py`): `CardStatus` enum (ACTIVE/FROZEN/CANCELLED), `SpendCategory` enum (8 values matching baseline). All Postgres enum types already exist in the DB from `0001_baseline` — use `PG_ENUM(..., create_type=False)` on every enum declaration or Alembic will try to CREATE TYPE and crash on a non-fresh DB.

**Service** (`api/api/services/card_service.py`):
- `list_cards(scope)` — EMPLOYEE sees only own cards (`card.user_id == scope.user_id`); ADMIN/FM see all org cards
- `get_card(scope, card_id)` — 404 if not in org; EMPLOYEE 404 if not their card
- `create_card(scope, data)` — validate `user_id` belongs to `scope.org_id`; validate `department_id` belongs to `scope.org_id` if provided; `last_four` generated with `secrets.choice(string.digits)` (not `random.choices` — Mersenne Twister is not CSPRNG)
- `update_card`, `freeze_card`, `unfreeze_card`, `cancel_card` — write `AuditLog` row **before** `commit()` so audit and state change are atomic. If the commit fails, the audit row rolls back too.

**Router** (`api/api/routers/cards.py`): `GET/POST /cards`, `GET/PATCH /cards/{id}`, `POST /cards/{id}/freeze|unfreeze|cancel`. Mount at `/api/v1` in `main.py`.

#### 3. Users — service, router

**Service** (`api/api/services/user_service.py`):
- `list_users(scope)`, `get_user(scope, user_id)`
- `invite_user(scope, data)` — accepts `password` in body (`is_active=True` immediately, no email flow for demo). Validate `department_id` belongs to `scope.org_id` if provided. Write audit log. `invite_token` in response is `str(uuid4())` placeholder.
- `update_user(scope, user_id, data)` — **last-ADMIN guard**: if target user is an active ADMIN and the update would demote their role OR set `is_active=False`, count all active ADMINs in the org. If count ≤ 1, raise 422. Guard applies to ANY admin being changed, not just self. Validate `department_id` if being reassigned.

**Router** (`api/api/routers/users.py`): `GET/POST /users`, `GET/PATCH /users/{id}`. Mount at `/api/v1`.

#### 4. AuditLog ORM (`api/api/models/audit_log.py`)

Columns from baseline DDL: `id, org_id, actor_user_id, action, entity_type, entity_id, metadata (JSONB), created_at`. **Python attribute must be `log_metadata`** with `mapped_column("metadata", JSONB, ...)` — `metadata` is reserved by `DeclarativeBase`.

#### 5. Tests

`api/tests/test_deps.py` — 8 unit tests: valid token, expired token, wrong role, mismatched org_id, inactive user, missing token, wrong token type, get_org_scope shape.

`api/tests/test_multitenancy.py` — 10 unit tests covering:
- Cross-org GET/freeze/unfreeze/cancel/update on card → 404
- EMPLOYEE cannot see another user's card within same org → 404
- `create_card` with cross-org `user_id` → 404
- `create_card` with cross-org `department_id` → 404
- `update_card` with cross-org `department_id` → 404
- `invite_user` with cross-org `department_id` → 404

All tests use `AsyncMock` for `scope.db`. **`db.add = MagicMock()`** explicitly — `session.add()` is synchronous; leaving it as `AsyncMock` produces unawaited-coroutine warnings.

#### 6. Frontend

**`CardsPage.tsx`** — plain Tailwind table, "New card" dialog, freeze/unfreeze/cancel with confirmation modals. No shadcn/ui — it is not installed and will not be installed until Phase 5/6 polish.

**`SettingsPage.tsx`** — users table, "Invite member" dialog, "Change role" modal, deactivate/reactivate toggle.

**`AppLayout.tsx`** — sticky top bar, `NavLink` tabs (Dashboard / Cards / Settings), user info + sign-out.

Update router to add `/cards` and `/settings` routes, both wrapped in `ProtectedLayout` (`RequireAuth` + `AppLayout`).

#### 7. Seed script update

Extend `api/api/db/seeds.py` to create: 2 departments (Engineering ₹500k, Marketing ₹300k), 4 cards (Bob: Travel/1001 + SaaS/1002; Carol: Ads/2001 + Events/2002).

---

### Update docs only if implementation intentionally deviates

Log deviations in `docs/DECISIONS.md`. Tick completed boxes in `docs/PHASES.md`. Do not rewrite `docs/MASTER_PLAN.md`.

---

### Definition of done

1. `docker compose up --build` clean, migration runs, seed runs
2. `python -m pytest -q` passes all tests
3. ADMIN creates a card, assigns to EMPLOYEE. EMPLOYEE logs in, sees only their card. Cross-org GET on known card UUID returns 404. ADMIN freezes the card; employee's view updates on refetch.
4. Tick all Phase 2 boxes in `docs/PHASES.md`

---

## Phase 3 Prompt — Transactions + State Machine

You are continuing the **Vault** project. Working directory: `/Users/namanmoudgill13/Desktop/Vault/`

**Read `docs/MASTER_PLAN.md` in full before writing a single line of code** — it contains a briefing header (~90 lines) with the exact current state, stack, and rules. Then read `docs/PHASES.md` for the Phase 3 deliverables checklist.

**Phases 1 and 2 are complete and verified.**

---

### Current state going into Phase 3

- API on host port **8001**. Verify stack: `docker compose ps` and `curl -s http://localhost:8001/health`
- Models: `Organization`, `Department`, `User`, `RefreshToken`, `Card`, `AuditLog` — all registered in `api/api/models/__init__.py`
- Services: `auth_service`, `card_service`, `user_service`
- Routers: `auth`, `cards`, `users` — all mounted at `/api/v1`
- `OrgScope` dataclass: bundles `db`, `org_id`, `user_id`, `role` — passed to every service function
- Frontend pages: `LoginPage`, `SignupPage`, `DashboardPage`, `CardsPage`, `SettingsPage`
- Run tests with `python -m pytest -q` — never bare `pytest`

---

### Hard rules — never violate

- **Never commit `.env` or secrets**
- **Never add `Co-Authored-By Claude` to git commits**
- **No new Alembic migration** — `transactions`, `transaction_events`, `transaction_policy_results` tables and all their enum types (`transaction_state`, `policy_verdict`) are already in `0001_baseline`. Creating a migration would fail with "table already exists."
- **`create_type=False`** on every `PG_ENUM` — all enum types already exist in DB
- **`metadata` reserved by SQLAlchemy `DeclarativeBase`** — use `event_metadata` with `mapped_column("metadata", JSONB)` for the `transaction_events.metadata` column
- **Do not map `receipt_id` FK in `Transaction`** and do not map `matched_policy_id` FK in `TransactionPolicyResult` — `Receipt` and `Policy` ORM models do not exist yet. SQLAlchemy raises `NoReferencedTableError` at startup if a FK references an unregistered mapper. Add a comment: `# restored in Phase 4`
- **`transaction_events` is append-only** — no UPDATE or DELETE anywhere in the codebase
- **Cross-org access → 404 never 403**
- **`org_id` always from `scope.org_id`** — never from body or path
- **Single commit per service function**
- **Audit log written before commit** on every privileged mutation
- **Money as `Numeric(14,2)`** — never float
- **`db.add = MagicMock()`** in test helpers — `session.add()` is sync

---

### What to build

#### State machine

```python
LEGAL_TRANSITIONS: dict[TransactionState, set[TransactionState]] = {
    TransactionState.INITIATED:       {TransactionState.POLICY_CHECKED},
    TransactionState.POLICY_CHECKED:  {TransactionState.APPROVED, TransactionState.FLAGGED, TransactionState.BLOCKED},
    TransactionState.APPROVED:        {TransactionState.CLEARED},
    TransactionState.FLAGGED:         {TransactionState.APPROVED, TransactionState.BLOCKED},
    TransactionState.BLOCKED:         set(),
    TransactionState.CLEARED:         {TransactionState.SETTLED},
    TransactionState.SETTLED:         set(),
}

async def transition(
    scope: OrgScope,
    txn: Transaction,
    to_state: TransactionState,
    reason: str | None = None,
    triggered_by_system: bool = False,
) -> Transaction:
    # Add TransactionEvent to session BEFORE mutating txn.state (atomicity)
    # Does NOT commit — caller commits once after all transitions
```

Illegal transition → `HTTPException(409)`.

#### `create_transaction(scope, data)`

1. Validate `card_id` belongs to `scope.org_id` — 404 if not
2. Validate `card.status == ACTIVE` — 422 if not
3. EMPLOYEE may only use their own card — **404** (not 403) if `card.user_id != scope.user_id`
4. Validate `department_id` belongs to `scope.org_id` if provided — 404 if not
5. Insert `Transaction` with `id=uuid4()` (explicit — lets event rows reference it before DB flush)
6. `await scope.db.flush()`
7. Write INITIATED event explicitly
8. `transition(POLICY_CHECKED, triggered_by_system=True)`
9. Run policy stub — returns `PolicyVerdict`. Stub thresholds: `amount > ₹1,00,000` → BLOCKED; `amount > ₹50,000` → FLAGGED; otherwise APPROVED
10. Branch on verdict: APPROVED → transition APPROVED → CLEARED; FLAGGED → transition FLAGGED (stop); BLOCKED → transition BLOCKED (stop)
11. Write `AuditLog` row
12. **Single `await scope.db.commit()`** — all events + policy result + audit log land together

#### Other service functions

- `list_transactions(scope, filters)` — EMPLOYEE filtered to own; bounded with `limit` (default 50, max 200) + `offset`; filters: `from_date`, `to_date`, `category`, `department_id`, `card_id`, `user_id` (ignored for EMPLOYEE), `state`
- `get_transaction(scope, txn_id)` — returns `(txn, events, latest_policy_result)`; EMPLOYEE 404 if not their txn
- `approve_transaction(scope, txn_id, reason)` — FM/ADMIN only; guard `txn.state == FLAGGED`; `SELECT FOR UPDATE` via `_load_transaction(for_update=True)`; transitions FLAGGED → APPROVED → CLEARED; writes audit log
- `reject_transaction(scope, txn_id, reason)` — same guard; transitions FLAGGED → BLOCKED
- `list_events(scope, txn_id)` — same ownership check as `get_transaction`

#### Router

`POST /transactions`, `GET /transactions`, `GET /transactions/{id}`, `POST /transactions/{id}/approve`, `POST /transactions/{id}/reject`, `GET /transactions/{id}/events`. Mounted at `/api/v1`.

#### Frontend

- **`TransactionsPage.tsx`** — filterable table; state badges colored by state (gray/blue/green/yellow/red/teal/purple); "New Transaction" button
- **`NewTransactionDialog`** — card dropdown, merchant, amount, currency (default INR), category, description, department, date
- **`TransactionDetailDrawer`** — slide-in; event timeline (timestamp, from→to, actor, reason); policy result with `VerdictBadge` (separate component from `StateBadge` — different type contract); Approve/Reject panel for FM/ADMIN when `state === "FLAGGED"`
- Add `/transactions` route and "Transactions" tab in `AppLayout` nav
- React Query hooks in `web/src/features/transactions/hooks.ts`

#### Seed transactions

Extend `api/api/db/seeds.py` to seed 8 transactions: 5 CLEARED (normal amounts), 2 FLAGGED (>₹50k), 1 BLOCKED (>₹1L). Use ADMIN scope in the seed so the EMPLOYEE card-ownership check is bypassed.

#### Tests (`api/tests/test_transactions.py` — 13 tests)

State machine: legal transitions pass; INITIATED→APPROVED raises 409; BLOCKED terminal raises 409; SETTLED terminal raises 409.

RBAC: EMPLOYEE own card succeeds; EMPLOYEE other card raises **404**; EMPLOYEE cannot approve (403 at route layer); FM can approve FLAGGED → state becomes CLEARED.

Multi-tenancy: cross-org GET → 404; cross-org card in create → 404.

Event trail: `create_transaction` writes exactly 4 events (INITIATED+POLICY_CHECKED+APPROVED+CLEARED) in one commit (`commit.call_count == 1`); reject writes BLOCKED event with reason.

EMPLOYEE filter: `?user_id=<other>` is silently ignored for EMPLOYEE scope — compile SQL and assert only `scope.user_id` appears.

---

### Update docs only if implementation intentionally deviates

Log in `docs/DECISIONS.md`. Tick `docs/PHASES.md`. Do not rewrite `docs/MASTER_PLAN.md`.

---

### Definition of done

1. `docker compose up --build` clean
2. `python -m pytest -q` passes all tests
3. `POST /api/v1/transactions` → response shows `state: "CLEARED"` with 4 events in `GET /transactions/{id}/events`
4. TransactionsPage renders at `/transactions` with table, filters, dialog, drawer all working
5. A FLAGGED transaction (seeded: amount >₹50k) can be approved or rejected from the drawer
6. Tick all Phase 3 boxes in `docs/PHASES.md`

---

## Phase 4 Prompt — LLM Pipelines (Receipts + Policy Engine)

You are continuing the **Vault** project. Working directory: `/Users/namanmoudgill13/Desktop/Vault/`

**Read `docs/MASTER_PLAN.md` in full before writing a single line of code.** Then `docs/PHASES.md`, `docs/DECISIONS.md`, `docs/PROBLEMS.md`.

**Phases 1, 2, 3 are complete and verified.**

---

### Current state going into Phase 4

**Backend:**
- Models: `Organization`, `Department`, `User`, `RefreshToken`, `Card`, `AuditLog`, `Transaction`, `TransactionEvent`, `TransactionPolicyResult` — all registered in `api/api/models/__init__.py`
- Services: `auth_service`, `card_service`, `user_service`, `transaction_service`
- Routers: `auth`, `cards`, `users`, `transactions` — all mounted at `/api/v1` in `main.py`
- `api/api/config.py` already has: `TIR_BASE_URL`, `TIR_API_KEY`, `TIR_MODEL`, `TIR_TIMEOUT_SECONDS`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PRESIGN_TTL_SECONDS` — no config changes needed
- `api/api/jobs/worker.py` — stub ARQ `WorkerSettings` with only `ping`. Worker container already in `docker-compose.yml` and running.
- `api/api/ai/`, `api/api/storage/`, `api/api/email/` — directories exist, are empty, fill them
- `requirements.txt` already has: `openai==1.51.0`, `boto3==1.35.30`, `arq==0.26.1`

**Database:** `policies`, `receipts`, `notifications` tables already exist in `0001_baseline`. **Do not create a migration.**

**Two deferred FK mappings from Phase 3 to restore** (see `docs/PROBLEMS.md` and `docs/DECISIONS.md`):
- `Transaction.receipt_id` → `receipts.id` — commented out in `transaction.py`, restore after `Receipt` ORM exists
- `TransactionPolicyResult.matched_policy_id` → `policies.id` — commented out, restore after `Policy` ORM exists

**Frontend:** Plain Tailwind throughout. shadcn/ui is not installed.

---

### Hard rules — never violate

- **Never commit `.env` or secrets**
- **Never add `Co-Authored-By Claude` to git commits**
- **No new Alembic migration** — all Phase 4 tables are in `0001_baseline`
- **Every LLM call goes through `api/api/llm/llm_client.py`** with Pydantic-validated output — no raw `httpx.post` to TIR anywhere in business code
- **`org_id` always from `scope.org_id`** — never from body or path
- **Cross-resource access → 404 never 403**
- **Single commit per service function**
- **Audit log written before commit** on every privileged mutation
- **`transaction_events` append-only** — no UPDATE/DELETE
- **Money as `Numeric(14,2)`** — never float
- **`create_type=False`** on every `PG_ENUM` — `receipt_status` and `notification_type` already exist in DB
- **`metadata` reserved by `DeclarativeBase`** — use aliased attribute + `mapped_column("metadata", JSONB)` if DB column is named `metadata`
- **`db.add = MagicMock()`** in test helpers
- **`python -m pytest -q`** — never bare `pytest`

---

### What to build

#### Step 1 — LLM client (`api/api/llm/llm_client.py`)

```python
async def complete_json(
    system: str,
    user: str,
    schema: type[BaseModel],
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> BaseModel:
```

- `openai.AsyncOpenAI` pointed at `settings.TIR_BASE_URL`, `api_key=settings.TIR_API_KEY`
- Parse response as JSON, validate with `schema.model_validate_json(...)`
- On `ValidationError`: retry **once** with validation error appended to prompt
- On second failure: raise `LLMValidationError`
- On network error: raise `LLMUnavailableError`
- Record latency in ms for every call

#### Step 2 — LLM schemas (`api/api/llm/schemas.py`)

```python
class ReceiptExtraction(BaseModel):
    merchant: str
    amount: Decimal = Field(gt=0)
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    date: str
    category: SpendCategory = SpendCategory.OTHER
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None

class PolicyCheckResult(BaseModel):
    verdict: Literal["APPROVED", "FLAGGED", "BLOCKED"]
    reason: str = Field(max_length=1000)
    policy_matched: str | None = None
    requires_approval_from: Literal["FINANCE_MANAGER", "ADMIN"] | None = None
```

#### Step 3 — S3 helpers (`api/api/storage/s3.py`)

`presign_put`, `presign_get`, `head`, `get_bytes` — boto3 wrapped in `asyncio.to_thread`. Raise `StorageNotConfiguredError` if `S3_ACCESS_KEY` is empty.

#### Step 4 — ORM models (no migration)

**`api/api/models/policy.py`** — columns: `id, org_id, text, is_active, created_by, created_at, updated_at`. No new enum types.

**`api/api/models/receipt.py`** — columns from baseline. `receipt_status` enum → `PG_ENUM(..., create_type=False)`. Omit `reimbursement_id` FK mapping (no `Reimbursement` ORM yet — add comment `# Phase 5`).

**`api/api/models/notification.py`** — columns: `id, org_id, user_id, type, entity_id, body, read_at, created_at, updated_at`. `notification_type` enum → `create_type=False`.

Register all three in `api/api/models/__init__.py`. Then restore the two deferred FK mappings in `transaction.py`.

#### Step 5 — Notification helper (`api/api/services/notification_service.py`)

**Write-only in Phase 4** — no read endpoints (Phase 6).

```python
async def fire_notification(db, org_id, user_id, type, entity_id, body) -> None:
    db.add(Notification(...))  # caller commits

async def notify_all_fms(db, org_id, type, entity_id, body) -> None:
    # query all active FINANCE_MANAGERs in org, fire_notification for each
```

#### Step 6 — Policy service and router

Service: `list_policies`, `get_policy`, `create_policy`, `update_policy`, `delete_policy` — all scoped by `scope.org_id`. Write `AuditLog` on create/update/delete.

Router endpoints: `GET/POST /policies`, `GET/PATCH/DELETE /policies/{id}`. ADMIN-only for write; ADMIN + FINANCE_MANAGER for read. Mount at `/api/v1`.

#### Step 7 — Receipt service and router

Service: `create_upload_url` (creates Receipt in PENDING_UPLOAD, returns presigned PUT URL), `confirm_upload` (sets PROCESSING, enqueues `ocr_receipt` job), `get_receipt`, `retry_ocr` (resets to PROCESSING, re-enqueues).

Router: `POST /receipts/upload-url`, `POST /receipts/{id}/confirm`, `GET /receipts/{id}`, `POST /receipts/{id}/retry`. Mount at `/api/v1`.

Also add optional `receipt_id: UUID | None = None` to `TransactionCreate` schema and set `txn.receipt_id = data.receipt_id` in `create_transaction` before flush.

#### Step 8 — ARQ jobs

**`api/api/jobs/ocr_receipt.py`**

```python
async def ocr_receipt(ctx: dict, *, receipt_id: str) -> None:
```

1. Open new DB session via `get_session_factory()()`
2. Load Receipt, verify `status == PROCESSING` — if not, return (idempotent)
3. Download bytes from S3 via `get_bytes(receipt.object_key)`
4. **Model is text-only (Llama 3.1 8B has no vision).** Construct a text prompt from file metadata (filename from `object_key`, `content_type`, `byte_size`) and send to LLM to generate plausible structured extraction. No system OCR library needed.
5. Validate with `ReceiptExtraction` via `llm_client.complete_json(..., temperature=0)`
6. On `LLMValidationError`/`LLMUnavailableError`: `status=FAILED`, write `llm_error`, commit, return
7. If `confidence < 0.7`: `status=NEEDS_REVIEW`, write `extracted_data`, commit
8. Otherwise: `status=COMPLETED`, write `extracted_data`, commit

**`api/api/jobs/policy_check.py`**

```python
async def run_policy_check(ctx: dict, *, txn_id: str) -> None:
```

1. Open new DB session
2. Load Transaction — if missing or `state != POLICY_CHECKED`, return (idempotent)
3. Load all active policies for `txn.org_id`
4. No active policies → transition POLICY_CHECKED → APPROVED → CLEARED, write stub `TransactionPolicyResult`, commit, return
5. Build policy check prompt with txn details + all policy texts
6. Call `llm_client.complete_json(..., schema=PolicyCheckResult, temperature=0)`
7. On LLM error → write FLAGGED result, transition FLAGGED, `notify_all_fms(POLICY_FLAGGED)`, commit
8. Write `TransactionPolicyResult` with all fields including `llm_latency_ms`
9. Branch on verdict:
   - APPROVED → APPROVED → CLEARED, commit
   - FLAGGED → FLAGGED, `notify_all_fms(POLICY_FLAGGED, body=f"Flagged: {txn.merchant} ₹{txn.amount}")`, commit
   - BLOCKED → BLOCKED, `notify_all_fms(POLICY_BLOCKED, body=f"Blocked: {txn.merchant} ₹{txn.amount}")`, commit

**Update `api/api/jobs/worker.py`:**
```python
from api.jobs.ocr_receipt import ocr_receipt
from api.jobs.policy_check import run_policy_check

class WorkerSettings:
    functions = [ping, ocr_receipt, run_policy_check]
    keep_result = 300
```

**Update `api/api/services/transaction_service.py`** — remove `_run_policy_stub` entirely. Replace the synchronous stub block in `create_transaction` with:

```python
await transition(scope, txn, TransactionState.POLICY_CHECKED, triggered_by_system=True)
scope.db.add(AuditLog(..., action="transaction.create", log_metadata={...}))
await scope.db.commit()
await scope.db.refresh(txn)

pool = await create_pool(RedisSettings.from_dsn(settings.ARQ_REDIS_URL))
await pool.enqueue_job("run_policy_check", txn_id=str(txn.id))
await pool.aclose()

return txn   # returns in POLICY_CHECKED state — frontend polls
```

Update `test_transactions.py` — `test_create_transaction_writes_events` now asserts 2 events (INITIATED + POLICY_CHECKED), not 4. Mock `create_pool` with `unittest.mock.patch`.

#### Step 9 — Frontend

**`PoliciesPage.tsx`** — list of policies, "Add policy" dialog (large textarea + active checkbox), edit, delete with confirmation. ADMIN only. React Query hooks in `web/src/features/policies/hooks.ts`. Add `/policies` route and "Policies" tab in `AppLayout` (visible to ADMIN + FINANCE_MANAGER).

**`ReceiptUploader.tsx`** — drag-drop/click, PUT to presigned URL directly, poll `GET /receipts/{id}` every 3s while PROCESSING, status badge with spinner, `onExtracted(extracted_data)` callback.

**Update `NewTransactionDialog`** — add `ReceiptUploader` at top; when `onExtracted` fires, auto-fill merchant/amount/currency/category; show "Auto-filled from receipt" banner; include `receipt_id` in POST payload.

**Update `TransactionDetailDrawer`** — while `state === "POLICY_CHECKED"` show pulsing "AI checking policies…" badge and poll every 3s; when resolved, show final state + policy result (`VerdictBadge` + `policy_matched` quoted block + `reason`).

---

### Tests

`api/tests/test_policy_service.py`: create succeeds, audit log written, cross-org GET → 404, cross-org delete → 404.

`api/tests/test_policy_check_job.py`: no policies → auto-approves; LLM error → FLAGGED + notification written; APPROVED verdict → CLEARED; FLAGGED verdict → FM notification row added for each FM in org.

---

### Definition of done

1. `docker compose up --build` clean — worker logs `[arq] worker started`, API no startup errors
2. `python -m pytest -q` passes all tests
3. `POST /api/v1/policies` creates a policy; `GET /api/v1/policies` returns it
4. `POST /api/v1/transactions` returns `state: "POLICY_CHECKED"`; worker transitions to final verdict within seconds
5. A transaction violating an active policy → `state: "FLAGGED"` + notification row for every FM
6. ReceiptUploader works in `NewTransactionDialog`; `GET /receipts/{id}` eventually shows `COMPLETED` with `extracted_data`
7. PoliciesPage renders at `/policies`; drawer shows "AI checking policies…" while POLICY_CHECKED
8. Tick all Phase 4 boxes in `docs/PHASES.md`
9. Log deviations in `docs/DECISIONS.md`