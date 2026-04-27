"""Auth tests rely on the shared fixtures in ``tests/conftest.py``.

``api_client`` is the integrated TestClient; ``db`` and ``fake_redis`` are
exposed so tests can directly inspect state when needed.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client(api_client):  # noqa: D401 — re-export alias used by pre-existing tests
    """Alias for ``api_client`` — keeps the old auth tests unchanged."""
    return api_client
