"""Arq worker entrypoint.

Launch with::

    arq app.workers.arq_worker.WorkerSettings

Jobs are added by module code via ``arq.create_pool(...)`` + ``pool.enqueue_job(
'task_name', ...)``. Each task function lives under ``tasks/`` and is a top-
level async function so Arq can reference it by name.
"""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.core.logging import configure_logging, get_logger

log = get_logger(__name__)


async def health_check(ctx: dict) -> None:
    log.info("arq_worker_health_check")


async def startup(ctx: dict) -> None:
    configure_logging()
    log.info("arq_worker_started")


async def shutdown(ctx: dict) -> None:
    log.info("arq_worker_stopped")


def _redis_settings() -> RedisSettings:
    # arq wants host/port/db, not a URL — parse the Redis URL once.
    url = settings.redis_url_for(settings.REDIS_ARQ_DB)
    # redis://host:port/db
    rest = url.split("://", 1)[1]
    host_port, _, db = rest.rpartition("/")
    host, _, port = host_port.partition(":")
    return RedisSettings(
        host=host or "localhost",
        port=int(port) if port else 6379,
        database=int(db) if db else settings.REDIS_ARQ_DB,
    )


class WorkerSettings:
    """Arq worker configuration (picked up by ``arq`` CLI)."""

    # Tasks will be added as modules come online. For P0 the list is empty —
    # the worker starts, connects, and idles.
    functions: list = []

    cron_jobs = [cron(health_check, hour=set(range(24)), minute=0)]

    redis_settings = _redis_settings()
    on_startup = startup
    on_shutdown = shutdown

    # Concurrency per worker pod; tune in prod.
    max_jobs = 20
    job_timeout = 300  # 5 min
    keep_result = 3600  # 1 hour
