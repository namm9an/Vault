from arq.connections import RedisSettings

from api.config import get_settings

_settings = get_settings()


def _redis_settings() -> RedisSettings:
    url = _settings.ARQ_REDIS_URL
    # arq parses host/port/db from a redis:// URL
    return RedisSettings.from_dsn(url)


async def ping(ctx) -> str:
    return "pong"


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [ping]
    keep_result = 60
