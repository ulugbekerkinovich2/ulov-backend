"""Content endpoints — read, cache, unknown kind."""

from __future__ import annotations

import pytest

CONTENT = "/api/v1/content"


@pytest.mark.integration
def test_empty_content_returns_empty_list(api_client) -> None:
    # Nothing seeded in tests — endpoint still responds 200.
    resp = api_client.get(f"{CONTENT}/traffic-rules?lang=uz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "traffic_rules"
    assert body["lang"] == "uz"
    assert body["items"] == []


@pytest.mark.integration
def test_content_after_upsert(api_client, db) -> None:
    from app.modules.content import service as content_svc

    content_svc.upsert_page(
        db,
        kind="tips",
        lang="uz",
        slug="winter",
        title="Qishda haydash",
        body={"category": "seasonal", "articles": []},
    )
    db.commit()  # make visible to the request's transaction
    resp = api_client.get(f"{CONTENT}/tips?lang=uz")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == "winter"
    assert items[0]["title"] == "Qishda haydash"


def test_content_rejects_short_lang(api_client) -> None:
    resp = api_client.get(f"{CONTENT}/tips?lang=english")
    assert resp.status_code == 422
