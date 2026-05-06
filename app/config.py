"""Application configuration.

All runtime knobs live here. Values are read from environment variables (with
``.env`` support via python-dotenv). Never read ``os.environ`` directly in
business code — import ``settings`` from this module so there is one source of
truth and one place to validate defaults.

Pydantic v1 is pinned (see ``pyproject.toml``); ``BaseSettings`` lives in
``pydantic`` itself — *not* ``pydantic_settings`` (v2-only).
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """Typed view of all environment variables."""

    # ---- Runtime ----------------------------------------------------------
    APP_ENV: str = Field("dev", regex="^(dev|staging|prod)$")
    APP_NAME: str = "ulov-backend"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"  # noqa: S104 — intentional for containers
    APP_PORT: int = 8000
    APP_VERSION: str = "0.1.0"
    APP_LOG_LEVEL: str = "INFO"
    APP_LOG_JSON: bool = False

    # ---- CORS -------------------------------------------------------------
    CORS_ORIGINS: List[str] = []

    @validator("CORS_ORIGINS", pre=True)
    def _split_cors(cls, v: object) -> List[str]:  # noqa: N805
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        raise TypeError("CORS_ORIGINS must be a comma-separated string or list")

    # ---- Database ---------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg2://ulov:ulov@postgres:5432/ulov"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ---- Redis ------------------------------------------------------------
    REDIS_URL: str = "redis://redis:6379"
    REDIS_CACHE_DB: int = 0
    REDIS_OTP_DB: int = 1
    REDIS_REFRESH_DB: int = 2
    REDIS_ARQ_DB: int = 3
    REDIS_PUBSUB_DB: int = 4

    # ---- Auth / JWT -------------------------------------------------------
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_SECONDS: int = 900
    JWT_REFRESH_TTL_SECONDS: int = 2592000
    REFRESH_COOKIE_NAME: str = "ulov_refresh"
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: str = "strict"

    # ---- OTP --------------------------------------------------------------
    OTP_TTL_SECONDS: int = 120
    OTP_MAX_ATTEMPTS: int = 5
    OTP_LOCK_SECONDS: int = 600
    OTP_DEV_ECHO: bool = True  # Never true in prod.

    # ---- S3 / MinIO -------------------------------------------------------
    S3_ENDPOINT_URL: Optional[AnyHttpUrl] = None
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "ulov"
    # Public read URL prefix (e.g. R2 dev URL or custom CNAME). Joined with
    # the object key to produce the URL we hand back to the client.
    S3_PUBLIC_URL: Optional[AnyHttpUrl] = None
    S3_PRESIGN_EXPIRES_SECONDS: int = 600
    S3_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MiB

    # ---- SMS providers ----------------------------------------------------
    ESKIZ_EMAIL: str = ""
    ESKIZ_PASSWORD: str = ""
    ESKIZ_FROM: str = "4546"
    PLAYMOBILE_LOGIN: str = ""
    PLAYMOBILE_PASSWORD: str = ""
    PLAYMOBILE_FROM: str = ""

    # ---- Payments ---------------------------------------------------------
    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET: str = ""
    PAYME_TEST_MODE: bool = True
    CLICK_MERCHANT_ID: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_SECRET_KEY: str = ""

    # ---- Push (FCM HTTP v1) -----------------------------------------------
    FCM_PROJECT_ID: str = ""
    # Path to a service-account JSON key (mounted as a secret in prod).
    FCM_SERVICE_ACCOUNT_JSON: str = ""

    # ---- Observability ----------------------------------------------------
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ---- Rate limits ------------------------------------------------------
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_WRITE_PER_MINUTE: int = 30
    RATE_LIMIT_READ_PER_MINUTE: int = 120

    # ---- Internal admin (sqladmin) ---------------------------------------
    # Mount /admin only when both creds + secret are set. The session secret
    # signs the login cookie; rotate it to invalidate everyone's session.
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_SESSION_SECRET: str = ""

    # ---- Misc -------------------------------------------------------------
    DEFAULT_LANGUAGE: str = "uz"
    TIMEZONE: str = "Asia/Tashkent"

    # ------------------------------------------------------------------
    # Derived
    # ------------------------------------------------------------------
    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "dev"

    def redis_url_for(self, db: int) -> str:
        """Return a REDIS_URL pointing at a specific logical DB."""
        base = self.REDIS_URL.rstrip("/")
        # redis://host:port or redis://host:port/<db>
        if "?" in base:
            # Keep query string intact.
            host, _, query = base.partition("?")
            return f"{host.rsplit('/', 1)[0]}/{db}?{query}"
        # Strip any trailing /<n> and re-append.
        parts = base.rsplit("/", 1)
        if len(parts) == 2 and parts[1].isdigit():
            base = parts[0]
        return f"{base}/{db}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton so import-time cost is paid once."""
    return Settings()  # reads env / .env


settings = get_settings()
