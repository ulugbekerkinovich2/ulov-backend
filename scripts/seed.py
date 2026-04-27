"""Idempotent seed script.

Run with ``make seed``. Loads reference data that the platform cannot function
without (subscription plans, insurance tariffs, SOS providers, content pages,
vehicle brands). Safe to re-run; every insert is an ``INSERT ... ON CONFLICT
DO NOTHING`` keyed on natural keys.

Currently a stub — the individual datasets are filled in per phase:
    Phase 2 → content_pages, stories, vehicle_brands
    Phase 5 → sos_providers, fuel_stations
    Phase 6 → subscription_plans, insurance_tariffs
"""

from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.modules.content import service as content_svc
from app.modules.content.seed_data import ALL_ROWS as CONTENT_ROWS

log = get_logger(__name__)


def _seed_content(session) -> None:  # type: ignore[no-untyped-def]
    for kind, lang, slug, title, body in CONTENT_ROWS:
        content_svc.upsert_page(
            session, kind=kind, lang=lang, slug=slug, title=title, body=body
        )
    log.info("content_seed_done", rows=len(CONTENT_ROWS))


def main() -> None:
    configure_logging()
    log.info("seed_started")
    session = SessionLocal()
    try:
        _seed_content(session)
        # TODO(P5): sos providers, fuel stations
        # TODO(P6): subscription plans, insurance tariffs
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    log.info("seed_finished")


if __name__ == "__main__":
    main()
