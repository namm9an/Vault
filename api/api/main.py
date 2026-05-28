from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.config import get_settings
from api.db.base import dispose_engine, get_engine
from api.logging import setup_logging
from api.routers.auth import router as auth_router
from api.routers.cards import router as cards_router
from api.routers.dashboard import router as dashboard_router
from api.routers.departments import router as departments_router
from api.routers.digest import router as digest_router
from api.routers.notifications import router as notifications_router
from api.routers.policies import router as policies_router
from api.routers.receipts import router as receipts_router
from api.routers.reimbursements import router as reimbursements_router
from api.routers.transactions import router as transactions_router
from api.routers.users import router as users_router

settings = get_settings()
setup_logging("INFO" if settings.APP_ENV != "dev" else "DEBUG")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(title="Vault API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    out = {"version": "0.1.0", "db": "unknown", "redis": "unknown", "tir": "unknown"}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        out["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        out["db"] = f"error: {type(e).__name__}"

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        out["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        out["redis"] = f"error: {type(e).__name__}"

    out["tir"] = "configured" if settings.TIR_API_KEY else "not_configured"
    return out


app.include_router(auth_router, prefix="/api/v1")
app.include_router(cards_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(departments_router, prefix="/api/v1")
app.include_router(digest_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(receipts_router, prefix="/api/v1")
app.include_router(reimbursements_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
