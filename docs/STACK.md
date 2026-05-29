# Vault — Tech Stack

Every technology in the stack, why it's there, and the sharp edges to watch for.

---

## React v18
**Purpose:** UI framework for the SPA.
**Why chosen:** Most ubiquitous, the team knows it, ecosystem fits everything else (shadcn, Recharts, React Query).
**Key config:** Strict mode on. Concurrent features (Suspense, useTransition) used sparingly — only where the UX clearly improves.
**Gotchas:** `useEffect` running twice in dev under StrictMode is intentional; do not "fix" it by removing StrictMode.
**Docs:** https://react.dev

---

## Vite v5
**Purpose:** Frontend dev server and production bundler.
**Why chosen:** Fastest HMR, zero-config TypeScript, native ESM. Beats Webpack for SPAs by every measure that matters.
**Key config:** `VITE_API_BASE_URL` env var read at build time; dev server proxies `/api` to `http://api:8000` so the SPA can call relative paths.
**Gotchas:** Env vars must be prefixed `VITE_` to be exposed to the browser. Anything else is silently dropped.
**Docs:** https://vite.dev

---

## TypeScript v5.4+
**Purpose:** Type safety for the frontend.
**Why chosen:** Mandatory for a codebase this size. Catches API contract drift at compile time when paired with shared response types.
**Key config:** `strict: true`, `noUncheckedIndexedAccess: true`, `paths` alias `@/*` → `src/*`.
**Gotchas:** Don't fight `noUncheckedIndexedAccess` by `as` casting — use proper narrowing or a runtime check.
**Docs:** https://www.typescriptlang.org/docs/

---

## Tailwind CSS v3.4
**Purpose:** Utility-first styling.
**Why chosen:** Pairs perfectly with shadcn/ui (which is built on Tailwind tokens). No naming overhead, design tokens centralized in the config.
**Key config:** `darkMode: 'class'`; design tokens (colors, radii, font) defined under `theme.extend` and referenced by shadcn components.
**Gotchas:** Dynamic class names (`bg-${color}-500`) don't get extracted by the JIT — use a `clsx` lookup map.
**Docs:** https://tailwindcss.com/docs

---

## shadcn/ui (latest) — NOT YET INSTALLED
**Purpose:** Accessible component primitives copy-pasted into the codebase. **(Planned for Phase 6 polish.)**
**Why chosen:** Not a dependency — we own the source. Built on Radix + Tailwind. Customizable without forking a npm package.
**Current status:** Phase 1–5 UI uses plain Tailwind classes (no Radix, no shadcn primitives). The `src/components/ui/` directory is empty. `components.json` does not exist yet.
**Key config (when installed):** `components.json` at web root. Components live in `src/components/ui/`. Design tokens in `tailwind.config.ts` must match shadcn's CSS variable scheme before installing.
**Gotchas:** When upgrading, re-run the generator per component; it overwrites local edits. Diff before committing.
**Docs:** https://ui.shadcn.com

---

## Recharts v2
**Purpose:** Charts for the spend dashboard.
**Why chosen:** React-native API, declarative, plays nice with Tailwind colors. Good enough for our 3 chart types.
**Key config:** Wrap in `ResponsiveContainer` so charts size to their parent.
**Gotchas:** Tooltips and labels can render off-screen on small viewports; use `wrapperStyle` overrides if needed.
**Docs:** https://recharts.org

---

## React Query (TanStack Query) v5
**Purpose:** Server state management — caching, refetching, optimistic updates, polling.
**Why chosen:** Eliminates a Redux/Zustand layer for server data. `refetchInterval` makes the receipt-OCR polling trivial.
**Key config:** Default `staleTime` of 30s; per-query overrides as needed. One `QueryClient` at app root.
**Gotchas:** Don't put server state in `useState` "as a backup" — it desyncs.
**Docs:** https://tanstack.com/query/latest

---

## React Router v6
**Purpose:** Client-side routing.
**Why chosen:** Standard. Data router APIs (`loader`, `action`) intentionally not used — we rely on React Query for data, Router only for nav.
**Key config:** `createBrowserRouter` with nested layout routes; `RequireAuth` wrapper for protected branches.
**Gotchas:** Use the `Navigate` component for redirects, not `useNavigate` in render — the latter triggers a setState-in-render warning.
**Docs:** https://reactrouter.com

---

## Axios v1
**Purpose:** HTTP client.
**Why chosen:** Interceptors for auth header + 401 handling are easier than fetch wrappers. Cancellation via AbortController works with React Query.
**Key config:** One instance at `src/lib/api.ts`. Request interceptor adds Bearer token. Response interceptor refreshes on 401 once before bouncing to login.
**Gotchas:** Don't import axios directly in components; always use the configured instance, or you skip the interceptors.
**Docs:** https://axios-http.com

---

## Python v3.11
**Purpose:** Backend language.
**Why chosen:** Pinned to 3.11 (not 3.12) because TIR/Llama tooling and some ARQ versions still resolve cleanest there.
**Key config:** `pyproject.toml` with project metadata; dev deps under `[tool.poetry.group.dev.dependencies]` or equivalent.
**Gotchas:** `asyncio.get_event_loop()` deprecated — use `asyncio.get_running_loop()` inside coroutines.
**Docs:** https://docs.python.org/3.11/

---

## FastAPI v0.110+
**Purpose:** Async REST framework.
**Why chosen:** Pydantic-native, async-first, dependency injection that makes auth + scope + DB clean.
**Key config:** APIRouter per resource; one global exception handler; CORS configured from `CORS_ORIGINS`.
**Gotchas:** Don't put long-running CPU work in route handlers — they share the event loop with every other request. Use ARQ.
**Docs:** https://fastapi.tiangolo.com

---

## SQLAlchemy v2.0 (async)
**Purpose:** ORM and query builder.
**Why chosen:** v2.0's typed `select()` API is the cleanest Python ORM has ever been. Async support is first-class.
**Key config:** `create_async_engine(DATABASE_URL)` with `asyncpg`. Sessions yielded from a FastAPI dependency. `expire_on_commit=False`.
**Gotchas:** Never mix sync and async sessions — they share connection pool surprises. Don't call `session.commit()` inside a service if the caller might want to roll back; pass the session in and let the route boundary commit.
**Docs:** https://docs.sqlalchemy.org/en/20/

---

## Alembic v1.13+
**Purpose:** Schema migrations.
**Why chosen:** The standard for SQLAlchemy. Integrates with our async models.
**Key config:** `alembic.ini` reads `sqlalchemy.url` from `DATABASE_URL` at runtime. `env.py` set to async mode.
**Gotchas:** Autogenerate is unreliable for enum changes and column type narrowing — always review the generated SQL.
**Docs:** https://alembic.sqlalchemy.org

---

## Pydantic v2
**Purpose:** Request/response validation; LLM response validation; settings.
**Why chosen:** v2's Rust core is 5–50× faster than v1; required for the LLM-response hot path. Same library for HTTP boundary and AI boundary.
**Key config:** `BaseSettings` from `pydantic-settings` for env config. `model_config = ConfigDict(from_attributes=True)` on ORM-derived schemas.
**Gotchas:** v1 → v2 syntax changed (`.dict()` → `.model_dump()`, `Config` class → `model_config`). Don't mix examples from old docs.
**Docs:** https://docs.pydantic.dev/latest/

---

## PostgreSQL v15
**Purpose:** Primary datastore.
**Why chosen:** ENUM types, JSONB, `gen_random_uuid()`, INET — all native. v15 specifically for `MERGE` and improved partition pruning if we ever need them.
**Key config:** Extensions: `pgcrypto`, `citext`. One shared `set_updated_at()` trigger. UUID PKs everywhere.
**Gotchas:** Enum values can be added but not removed without recreating the type. Plan additions carefully.
**Docs:** https://www.postgresql.org/docs/15/

---

## Redis v7
**Purpose:** Task queue (ARQ), dashboard cache, SSE pub/sub.
**Why chosen:** One service does three jobs. Mature, fast, well-known.
**Key config:** AOF persistence for the queue DB (`appendonly yes`). Separate DB numbers: `0` for cache+pubsub, `1` for ARQ.
**Gotchas:** Don't share a key namespace across the three uses; prefix everything (`cache:`, `arq:`, `notif:`).
**Docs:** https://redis.io/docs/latest/

---

## ARQ v0.25+
**Purpose:** Async task queue + cron.
**Why chosen:** Native `async def` jobs; built-in cron; shares the SQLAlchemy session pattern with the API.
**Key config:** `WorkerSettings` in `api/jobs/worker.py` lists `functions` and `cron_jobs`. Concurrency = 4 for the demo.
**Gotchas:** Jobs must be idempotent — ARQ may retry on worker crash. Guard on the row's status field.
**Docs:** https://arq-docs.helpmanual.io

---

## Uvicorn + Gunicorn
**Purpose:** ASGI server.
**Why chosen:** Uvicorn is the fastest ASGI loop; Gunicorn manages workers and graceful reload. Standard pairing.
**Key config:** `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 api.main:app`. Workers = 2 is plenty for the demo.
**Gotchas:** With Gunicorn, the `--reload` flag is for dev only. For prod use SIGHUP for zero-downtime config reload.
**Docs:** https://www.uvicorn.org · https://gunicorn.org

---

## openai Python SDK (≥ 1.30)
**Purpose:** Client for the E2E TIR endpoint (OpenAI-compatible).
**Why chosen:** TIR exposes the OpenAI Chat Completions API; the official SDK is the path of least resistance.
**Key config:** `AsyncOpenAI(base_url=TIR_BASE_URL, api_key=TIR_API_KEY)`. Use `response_format={"type": "json_object"}` on every call.
**Gotchas:** Don't import `openai.OpenAI` (sync) in async code paths. Pin the SDK — minor versions change the response shape.
**Docs:** https://github.com/openai/openai-python

---

## Llama 3.1 8B Instruct (on E2E TIR)
**Purpose:** The model behind the policy engine (Phase 4) and weekly digest (Phase 6).
**Why chosen:** Hosted on E2E TIR. 8B Instruct is sufficient for tightly-prompted, schema-validated tasks at temperature 0/0.3. Demo aligns with the E2E story.
**Key config:** `temperature=0` for policy engine; `temperature=0.3` for digest. Always `response_format=json_object`. `max_tokens` capped per use case.
**Gotchas:** **Text-only — no vision capability.** Llama 3.2 introduced multi-modal support; 3.1 did not. Do NOT attempt to pass image data to this model — it will hallucinate plausible-looking structured output from non-image tokens (confirmed C3 critical bug). The `ocr_receipt` job correctly avoids calling this model. Never use the base (non-Instruct) variant. The model occasionally returns Markdown-fenced JSON; the client strips fences before parsing.
**Docs:** Model card on Hugging Face: https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct

---

## E2E Object Storage (S3-compatible) / MinIO (local dev)
**Purpose:** Receipt image storage.
**Why chosen:** Part of the E2E stack; integrates by S3 API so any S3 client works. Keeps receipts out of Postgres. MinIO used locally because E2E Object Storage credentials are unavailable in dev/CI.
**Key config:** Bucket `vault-receipts`. Path scheme `org/{org_id}/receipts/{receipt_id}.{ext}`. Presigned PUT for upload, presigned GET for worker download. TTL 5 minutes. `S3_PUBLIC_URL` rewrites Docker-internal hostnames in presigned URLs before returning to the browser.
**Gotchas:** Endpoint URL must include the scheme. `boto3` defaults `addressing_style=auto` may need `path` for self-hosted/MinIO endpoints. The `S3_PUBLIC_URL` rewrite is critical for local dev — without it every browser upload fails with a network error because `minio:9000` is not reachable outside Docker.
**Docs:** E2E Cloud Object Storage documentation (internal). MinIO: https://min.io/docs/

---

## boto3 / botocore (via aioboto3)
**Purpose:** S3 client for presigned URL generation, HEAD, and GET/PUT operations.
**Why chosen:** boto3 is the canonical S3 client; works with any S3-compatible endpoint including E2E Object Storage and MinIO.
**Key config:** `boto3.client("s3", endpoint_url=S3_ENDPOINT_URL, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY, region_name=S3_REGION)`. Sync client wrapped in `asyncio.to_thread` inside the async API. `addressing_style="path"` for MinIO compatibility.
**Gotchas:** Presigned URL generation is CPU-bound and sync — always run in a thread executor (`asyncio.to_thread`). `ClientError` with code `"404"` means the object does not exist; `head()` translates this to `FileNotFoundError`.
**Docs:** https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

---

## JWT (PyJWT v2)
**Purpose:** Stateless authentication.
**Why chosen:** Standard. HS256 keeps it simple — no key distribution needed for a single-app deployment.
**Key config:** `APP_SECRET_KEY` for signing; `JWT_ACCESS_TTL_MINUTES=60`; refresh tokens persisted in DB so we can revoke.
**Gotchas:** Don't put PII in the payload — JWTs are base64, not encrypted. Always validate `exp`, `iat`, and `org_id` membership server-side.
**Docs:** https://pyjwt.readthedocs.io

---

## passlib + bcrypt
**Purpose:** Password hashing.
**Why chosen:** Bcrypt is the default safe choice. Passlib gives a clean API and an upgrade path.
**Key config:** `CryptContext(schemes=["bcrypt"], deprecated="auto")`. Cost factor at the library default (12).
**Gotchas:** Bcrypt silently truncates passwords past 72 bytes — document this in the signup form or pre-hash with SHA-256.
**Docs:** https://passlib.readthedocs.io

---

## Docker + Docker Compose
**Purpose:** Local dev orchestration and production deploy on E2E Cloud.
**Why chosen:** Same tool for dev and prod. One command (`docker compose up`) brings up the entire system.
**Key config:** One `docker-compose.yml` for dev, `docker-compose.prod.yml` as an override.
**Gotchas:** On macOS, bind mounts are slow. Use named volumes for `node_modules` and `.venv` to keep dev responsive.
**Docs:** https://docs.docker.com/compose/

---

## MailHog (dev only)
**Purpose:** Captures outgoing SMTP so the digest email is testable locally.
**Why chosen:** Zero-config; web UI at `:8025`.
**Key config:** `SMTP_HOST=mailhog`, `SMTP_PORT=1025`, no auth.
**Gotchas:** Not for production. Swap to Resend or SES via the same SMTP envelope when deploying.
**Docs:** https://github.com/mailhog/MailHog

---

## pytest v8.3 + pytest-asyncio v0.24 + anyio v4.6
**Purpose:** Backend unit and integration test suite.
**Why chosen:** pytest is the Python standard; `pytest-asyncio` makes `async def` test functions work without boilerplate; `anyio` is the required backend for `asyncio_mode = auto`.
**Key config:** `api/pytest.ini` sets `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`, and `testpaths = tests`. Tests mock the DB session to avoid a live Postgres dependency for unit tests. **46 tests passing as of Phase 5 + validation fixes** (18 from Phase 2 deps/RBAC/multi-tenancy, 13 core transaction tests, 3 policy service tests, 4 policy check job tests, 2 updated transaction enqueue tests, 2 reimbursement service tests, 2 department service tests, 2 dashboard service tests).
**Host testing:** `api/requirements-test.txt` excludes `asyncpg` so the unit suite runs on the host Python without the C extension. Run with `.venv/bin/pytest -q` (the `.venv` inside `api/` has all test deps). Docker is only required for integration tests against a live DB.
**SQLAlchemy `session.add()` is synchronous.** In tests that create an `AsyncMock()` for the DB session, explicitly set `db.add = MagicMock()` after construction. Otherwise `AsyncMock().add` is also an `AsyncMock`, and calling it in the service produces unawaited-coroutine warnings.
**Gotchas:** `asyncio_mode = auto` requires all test coroutines to actually be async; sync test functions still work but will not be auto-wrapped. Do not mix `asyncio` and `trio` backends in the same suite.
**Docs:** https://docs.pytest.org · https://pytest-asyncio.readthedocs.io
