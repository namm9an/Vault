from arq.connections import RedisSettings

from api.config import get_settings
from api.jobs.ocr_receipt import ocr_receipt
from api.jobs.policy_check import run_policy_check

_settings = get_settings()


def _redis_settings() -> RedisSettings:
    url = _settings.ARQ_REDIS_URL
    # arq parses host/port/db from a redis:// URL
    return RedisSettings.from_dsn(url)


async def ping(ctx) -> str:
    return "pong"


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [ping, ocr_receipt, run_policy_check]
    keep_result = 60
