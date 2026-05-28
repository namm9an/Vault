<div align="center">

# Vault

**AI-native corporate spend intelligence — built on E2E Cloud**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

*Every transaction judged by AI. Every policy enforced automatically. Every rupee explained.*

</div>

---

## What is Vault?

Vault is a Ramp-inspired corporate spend management platform with an AI layer that replaces manual expense work. The card is just a data pipe — the real product is the intelligence on top of it.

- **Finance Managers** get a real-time approval queue for flagged transactions, a weekly AI-generated digest that surfaces waste, and plain-English policies that enforce themselves.
- **Employees** snap a receipt and the form fills itself. They submit transactions in seconds and see exactly why something was flagged.
- **Admins** issue virtual cards with per-category spend limits, freeze them in one click, and control who can see what through role-based access.

---

## The 3 AI Features

### 1 · Receipt Upload → NEEDS_REVIEW
Upload a photo of any receipt (JPEG, PNG, or PDF). Vault stores it in S3-compatible object storage and routes it to a human reviewer — `NEEDS_REVIEW` is the honest status since Llama 3.1 8B is text-only (vision capability arrives in 3.2). The uploaded receipt can still be attached to any transaction immediately. When a vision-capable model is available on E2E TIR, only one job file needs to change to unlock auto-fill.

### 2 · Policy Engine
Write a rule in plain English:
> *"No alcohol purchases above ₹2,000"*
> *"Any SaaS tool over ₹10,000 needs CFO approval"*

Every transaction is judged against every active policy at `temperature=0` — same input, same verdict, always. Approved transactions clear automatically. Flagged ones land in the FM queue. Blocked ones never settle.

### 3 · Weekly Spend Digest
Every Monday at 9 AM IST (or on demand), an ARQ job aggregates the past 7 days and asks the LLM to write a 250-word note for the CFO: top categories, duplicate vendors, idle SaaS tools, anomalies vs. last week. Specific numbers, direct recommendations, no hedging.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.115 · Python 3.11 · Pydantic v2 · SQLAlchemy 2.0 async |
| **Database** | PostgreSQL 15 · Alembic migrations · asyncpg driver |
| **Queue / Cache** | Redis 7 · ARQ (async task queue + cron) |
| **AI** | Llama 3.1 8B Instruct on **E2E TIR** · OpenAI-compatible SDK |
| **Storage** | E2E Object Storage (S3-compatible) for receipt images |
| **Frontend** | React 18 · Vite 5 · TypeScript strict · Tailwind CSS 3.4 |
| **State** | TanStack Query v5 · React Router 6 · Axios |
| **Auth** | JWT (HS256) · bcrypt · refresh token rotation |
| **Infra** | Docker Compose · Gunicorn + Uvicorn · MailHog (dev email) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Browser (SPA)                     │
│        React 18 · Vite · TypeScript · Tailwind       │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS / REST
┌───────────────────────▼─────────────────────────────┐
│               FastAPI Application                    │
│   /auth  /cards  /users  /transactions  /receipts   │
│   /policies  /reimbursements  /dashboard  /digest   │
│                                                      │
│   RBAC deps → OrgScope → Service layer              │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
┌──────────▼──────────┐  ┌─────────▼──────────────────┐
│   PostgreSQL 15     │  │   Redis 7                  │
│   10 tables         │  │   DB 0 → cache + SSE       │
│   UUID PKs          │  │   DB 1 → ARQ task queue    │
│   NUMERIC(14,2)     │  └─────────┬──────────────────┘
│   JSONB policies    │            │
└─────────────────────┘  ┌─────────▼──────────────────┐
                         │   ARQ Worker               │
                         │   ocr_receipt              │
                         │   run_policy_check         │
                         │   generate_digest (cron)   │
                         └─────────┬──────────────────┘
                                   │
                         ┌─────────▼──────────────────┐
                         │   E2E TIR                  │
                         │   Llama 3.1 8B Instruct    │
                         │   (OpenAI-compatible API)  │
                         └────────────────────────────┘
```

---

## Transaction State Machine

Every transaction moves through a strict, enforced state graph. Illegal transitions return `409 Conflict` — there is no way to skip a step.

```
INITIATED ──► POLICY_CHECKED ──► APPROVED ──► CLEARED ──► SETTLED
                     │
                     ├──► FLAGGED ──► APPROVED ──► CLEARED
                     │        └────► BLOCKED  (terminal)
                     │
                     └──► BLOCKED  (terminal)
```

Every state change writes an immutable `transaction_events` row with actor, reason, and timestamp — a full audit trail from creation to settlement.

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/namm9an/Vault.git
cd Vault
cp .env.example .env
# Fill in: APP_SECRET_KEY, TIR_BASE_URL, TIR_API_KEY, TIR_MODEL,
#          S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY

# 2. Bring up the full stack
docker compose up --build

# 3. Seed demo data (first boot only)
docker compose exec api python -m api.db.seeds
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8001/docs |
| MinIO console (S3 UI) | http://localhost:9001 |
| MailHog (email UI) | http://localhost:8025 |
| API health check | http://localhost:8001/health |

Sign up at the web app, or use the seeded accounts from `seeds.py`.

---

## Folder Structure

```
Vault/
├── api/                          Python FastAPI backend
│   ├── api/
│   │   ├── routers/              HTTP endpoints (auth, cards, users, transactions,
│   │   │                         receipts, policies…)
│   │   ├── services/             Business logic — one file per resource
│   │   ├── models/               SQLAlchemy 2.0 async ORM models
│   │   ├── schemas/              Pydantic v2 request / response models
│   │   ├── llm/                  LLM client + Pydantic response schemas
│   │   ├── jobs/                 ARQ background jobs (ocr_receipt, run_policy_check)
│   │   ├── storage/              S3 helpers (presign_put/get, head, get_bytes)
│   │   ├── deps.py               get_current_user · require_role · OrgScope
│   │   └── config.py             pydantic-settings — all env config in one place
│   ├── alembic/                  DB migrations (0001_baseline, 0002_global_email_unique,
│   │                             0003_policy_soft_delete)
│   └── tests/                    40 unit tests — deps, RBAC, multi-tenancy,
│                                 txn state machine, policy service, policy check job
│
├── web/                          React + Vite + TypeScript SPA
│   └── src/
│       ├── pages/                LoginPage · SignupPage · DashboardPage
│       │                         TransactionsPage · CardsPage · PoliciesPage · SettingsPage
│       ├── components/           AppLayout · RequireAuth · ReceiptUploader · VerdictBadge
│       ├── features/             React Query hooks per resource
│       │                         (auth, transactions, cards, policies, receipts…)
│       └── lib/                  Axios client · auth helpers · QueryClient
│
├── docker-compose.yml            Local dev — db, redis, api, worker, web,
│                                 minio, minio-init, mailhog
└── .env.example                  All required environment variables documented
```

---

## Security Model

- **Multi-tenancy:** Every DB query is scoped by `org_id` extracted from the JWT — never from the request body. Cross-org access always returns `404`, never `403` (existence is not leaked).
- **RBAC:** Three roles — `ADMIN`, `FM` (Finance Manager), `EMPLOYEE`. `require_role()` is a FastAPI dependency applied at the route level.
- **Token security:** Access tokens (60 min), refresh tokens (30 days) stored in DB for revocation. Rotation is atomic via `SELECT FOR UPDATE` to close concurrent-refresh races.
- **Money columns:** All amounts stored as `NUMERIC(14,2)` / Python `Decimal`. No floats anywhere in the money path.
- **Audit log:** Every privileged mutation (card freeze, transaction approve/reject, policy engine state change) writes an immutable `audit_log` row in the same DB transaction as the state change. System-driven transitions (policy engine) write `actor_user_id=NULL` rows to distinguish them from human actions in compliance reports.

---

## Built on E2E Cloud

Vault is built end-to-end on [E2E Networks](https://www.e2enetworks.com):

- **AI inference** — Llama 3.1 8B Instruct via E2E TIR (OpenAI-compatible endpoint)
- **Object storage** — Receipt images stored on E2E Object Storage (S3-compatible)
- **Compute** — Production deploy targets E2E Cloud VMs via Docker Compose

---

<div align="center">
Built by <a href="https://github.com/namm9an">Naman Moudgill</a> · <a href="https://www.e2enetworks.com">E2E Networks</a>
</div>
