"""Lazy S3 client.

Only one client per process; built on first call. Configured to talk to
either MinIO (dev) or Cloudflare R2 (prod) — both are S3-compatible.

R2 quirks worth knowing:
  * region must be ``"auto"`` (we still pass it; boto3 doesn't care)
  * the public URL is *not* the API endpoint; it's a separate dev-URL or
    custom CNAME the client downloads from. We keep it on
    ``settings.S3_PUBLIC_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.config import settings


@lru_cache(maxsize=1)
def get_s3_client() -> Any:
    """Return a boto3 S3 client tuned for path-style buckets (MinIO/R2)."""
    return boto3.client(
        "s3",
        endpoint_url=str(settings.S3_ENDPOINT_URL) if settings.S3_ENDPOINT_URL else None,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def public_url_for(key: str) -> str:
    """Best-effort public read URL for ``key``.

    Falls back to the API endpoint when no public URL is configured (the
    object will require an additional GET presign to fetch).
    """
    if settings.S3_PUBLIC_URL:
        return f"{str(settings.S3_PUBLIC_URL).rstrip('/')}/{key.lstrip('/')}"
    if settings.S3_ENDPOINT_URL:
        return f"{str(settings.S3_ENDPOINT_URL).rstrip('/')}/{settings.S3_BUCKET}/{key.lstrip('/')}"
    return key
