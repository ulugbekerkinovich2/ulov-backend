"""Shared pytest fixtures.

Scopes:
  * ``app``       (session) — FastAPI instance, created once.
  * ``client``    (function) — stateless TestClient (no DB override).
  * ``db_engine`` (session) — real Postgres schema; skips if unreachable.
  * ``db``        (function) — per-test transactional session (rolled back).
  * ``fake_redis``(function) — fakeredis.aioredis for OTP/cache/pub-sub.
  * ``api_client``(function) — TestClient with ``get_db`` + Redis deps
                                overridden to the fixtures above. Use this
                                for every module test that hits the database.
"""

from __future__ import annotations

import os
from typing import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Force a safe env before importing the app.
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("APP_DEBUG", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://ulov:ulov@localhost:5432/ulov_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/ulov-prom")


# ---------------------------------------------------------------------------
# App / client (no DB)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    """Create the FastAPI app once per test session."""
    from app.main import create_app

    return create_app()


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    """Stateless TestClient — no dep overrides. Use ``api_client`` for DB tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
async def async_client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Database — session-scoped schema, per-test transaction rollback
# ---------------------------------------------------------------------------
def _import_all_models() -> None:
    """Trigger ORM model registration across every module."""
    # Order matters: base tables first, referring tables last.
    import app.modules.audit.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.billing.models  # noqa: F401
    import app.modules.cars.models  # noqa: F401
    import app.modules.content.models  # noqa: F401
    import app.modules.fuel_stations.models  # noqa: F401
    import app.modules.insurance.models  # noqa: F401
    import app.modules.mechanics.models  # noqa: F401
    import app.modules.notifications.models  # noqa: F401
    import app.modules.reviews.models  # noqa: F401
    import app.modules.service_centers.models  # noqa: F401
    import app.modules.services.models  # noqa: F401
    import app.modules.sos.models  # noqa: F401
    import app.modules.trips.models  # noqa: F401
    import app.modules.users.models  # noqa: F401


@pytest.fixture(scope="session")
def db_engine():
    from sqlalchemy import text

    from app.db.base import Base
    from app.db.session import engine

    _import_all_models()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres unreachable: {exc}")

    # PostGIS is required for service_centers.location.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    # Clean slate.
    Base.metadata.drop_all(engine)
    # Drop any enum types left over from a prior run.
    with engine.begin() as conn:
        for enum in (
            "plate_type",
            "mileage_source",
            "content_kind",
            "device_platform",
            "user_role",
            "service_status",
            "condition_image_stage",
            "sos_category",
            "sos_request_status",
            "payment_status",
            "payment_provider",
            "payment_kind",
        ):
            conn.execute(text(f"DROP TYPE IF EXISTS {enum} CASCADE"))

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            for enum in (
                "plate_type",
                "mileage_source",
                "content_kind",
                "device_platform",
                "user_role",
            ):
                conn.execute(text(f"DROP TYPE IF EXISTS {enum} CASCADE"))


@pytest.fixture()
def db(db_engine):
    from sqlalchemy.orm import sessionmaker

    connection = db_engine.connect()
    transaction = connection.begin()
    SessionCls = sessionmaker(
        bind=connection, autoflush=False, expire_on_commit=False, future=True
    )
    session = SessionCls()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Redis — fakeredis async client
# ---------------------------------------------------------------------------
@pytest.fixture()
async def fake_redis():
    try:
        from fakeredis.aioredis import FakeRedis
    except ImportError:
        pytest.skip("fakeredis is not installed")

    client = FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        try:
            await client.aclose()  # redis>=5
        except AttributeError:
            await client.close()


# ---------------------------------------------------------------------------
# Integrated TestClient with DB + Redis overrides
# ---------------------------------------------------------------------------
@pytest.fixture()
def api_client(app, db, fake_redis) -> Iterator[TestClient]:
    from app.deps import (
        get_db,
        get_redis_cache,
        get_redis_otp,
        get_redis_pubsub,
        get_redis_refresh,
    )

    def _override_db():
        yield db

    async def _override_redis():
        return fake_redis

    app.dependency_overrides[get_db] = _override_db
    for dep in (
        get_redis_otp,
        get_redis_cache,
        get_redis_refresh,
        get_redis_pubsub,
    ):
        app.dependency_overrides[dep] = _override_redis

    # WebSocket dependency uses a different signature (ws-scoped); override
    # it so tests don't need a live Redis daemon for /ws/* endpoints.
    from app.modules.services.router import get_ws_pubsub

    async def _override_ws_redis():
        return fake_redis

    app.dependency_overrides[get_ws_pubsub] = _override_ws_redis

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
