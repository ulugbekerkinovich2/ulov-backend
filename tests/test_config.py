"""Sanity tests for the typed settings."""

from __future__ import annotations


def test_redis_url_for_preserves_host(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    # Force a fresh settings instance for this test.
    from app.config import Settings

    s = Settings()
    assert s.redis_url_for(0) == "redis://localhost:6379/0"
    assert s.redis_url_for(3) == "redis://localhost:6379/3"


def test_redis_url_for_replaces_existing_db(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.config import Settings

    s = Settings()
    assert s.redis_url_for(4) == "redis://localhost:6379/4"


def test_cors_origins_splitting(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example,https://b.example")
    from app.config import Settings

    s = Settings()
    assert s.CORS_ORIGINS == ["https://a.example", "https://b.example"]


def test_cors_origins_empty(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "")
    from app.config import Settings

    s = Settings()
    assert s.CORS_ORIGINS == []
