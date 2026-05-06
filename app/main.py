"""FastAPI application factory.

Creates the app, wires middleware (request-ID, CORS, GZip), exception
handlers, observability (Sentry + Prometheus), health endpoints, and the
``/api/v1`` router.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app import __version__
from app.api.v1 import api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import bind_request_id, configure_logging, get_logger
from app.deps import close_redis_clients, init_redis_clients

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup + shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            release=__version__,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[FastApiIntegration(), AsyncioIntegration()],
            send_default_pii=False,
        )
        log.info("sentry_initialised", env=settings.APP_ENV)

    # Redis clients (one per logical DB) are lifetime-managed here.
    app.state.redis_clients = await init_redis_clients()
    log.info(
        "app_started",
        env=settings.APP_ENV,
        version=__version__,
        debug=settings.APP_DEBUG,
    )

    try:
        yield
    finally:
        await close_redis_clients(app.state.redis_clients)
        log.info("app_stopped")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="ULOV+ API",
        version=__version__,
        default_response_class=ORJSONResponse,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---- Middleware (order matters; registered bottom-up) -------------------
    # GZip payloads > 1 KiB to shave mobile bandwidth.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_mw(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Assign a request-ID, time the request, add it to logs."""
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_request_id(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Exception handlers will produce the response; we only record the miss.
            log.exception("request_failed", path=request.url.path, method=request.method)
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Request-ID"] = rid
            log.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            return response
        finally:
            bind_request_id(None)

    # ---- Exception handlers -------------------------------------------------
    register_exception_handlers(app)

    # ---- Routers ------------------------------------------------------------
    app.include_router(api_router)

    # ---- Internal admin (sqladmin) — mounted at /admin when configured -----
    from app.admin import mount_admin  # local import: avoid cycle at module load

    mount_admin(app)

    # ---- Health / meta ------------------------------------------------------
    @app.get("/health/live", tags=["meta"], include_in_schema=False)
    def health_live() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"], include_in_schema=False)
    async def health_ready() -> JSONResponse:
        # Best-effort dependency probe. Returns 200 if DB + Redis respond.
        checks = {"database": False, "redis": False}

        # Database
        try:
            from sqlalchemy import text

            from app.db.session import engine

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("health_db_failed", error=str(exc))

        # Redis (cache DB is enough)
        try:
            client = app.state.redis_clients[settings.REDIS_CACHE_DB]
            pong = await client.ping()
            checks["redis"] = bool(pong)
        except Exception as exc:  # noqa: BLE001
            log.warning("health_redis_failed", error=str(exc))

        healthy = all(checks.values())
        status_code = 200 if healthy else 503
        return JSONResponse(
            status_code=status_code, content={"status": "ok" if healthy else "degraded", "checks": checks}
        )

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root() -> dict:
        return {
            "name": "ulov-backend",
            "version": __version__,
            "env": settings.APP_ENV,
            "docs": "/docs",
        }

    return app


app = create_app()
