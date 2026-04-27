"""Aggregate module routers under ``/api/v1``.

Each module exposes a ``router`` in ``modules/<name>/router.py``. We import
them lazily here so a half-built module does not break the rest of the app.
As phases progress, uncomment each block.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")


# ---- Phase 1: Foundation ----------------------------------------------------
from app.modules.auth.router import router as auth_router  # noqa: E402

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# ---- Phase 2: Customer core --------------------------------------------------
from app.modules.cars.router import router as cars_router  # noqa: E402
from app.modules.content.router import router as content_router  # noqa: E402
from app.modules.notifications.router import devices_router, router as notifications_router  # noqa: E402
from app.modules.reviews.router import router as reviews_router  # noqa: E402
from app.modules.users.router import router as users_router  # noqa: E402

api_router.include_router(users_router, tags=["users"])
api_router.include_router(cars_router, prefix="/cars", tags=["cars"])
api_router.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
api_router.include_router(content_router, prefix="/content", tags=["content"])
api_router.include_router(
    notifications_router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(devices_router, prefix="/devices", tags=["devices"])

# ---- Phase 3: Center core ----------------------------------------------------
from app.modules.mechanics.router import router as mechanics_router  # noqa: E402
from app.modules.service_centers.router import router as centers_router  # noqa: E402
from app.modules.services.router import router as services_router  # noqa: E402

api_router.include_router(
    centers_router, prefix="/service-centers", tags=["service-centers"]
)
# Mechanics router uses absolute paths (`/service-centers/{id}/mechanics` and
# `/mechanics/{id}`), so it mounts without a prefix.
api_router.include_router(mechanics_router, tags=["mechanics"])
# Services router likewise uses absolute paths for `/vehicles/lookup`,
# `/service-centers/{id}/...`, `/services/{id}/...`, and `/ws/...`.
api_router.include_router(services_router, tags=["services"])

# ---- Reference data (vehicle brands, colours, service intervals) ------------
from app.modules.reference.router import router as reference_router  # noqa: E402

api_router.include_router(reference_router, prefix="/reference", tags=["reference"])

# ---- Phase 4: Uploads --------------------------------------------------------
from app.modules.uploads.router import router as uploads_router  # noqa: E402

api_router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])

# ---- Phase 5: Secondary ------------------------------------------------------
from app.modules.fuel_stations.router import router as fuel_stations_router  # noqa: E402
from app.modules.insurance.router import router as insurance_router  # noqa: E402
from app.modules.sos.router import router as sos_router  # noqa: E402
from app.modules.trips.router import router as trips_router  # noqa: E402

api_router.include_router(trips_router, prefix="/trips", tags=["trips"])
api_router.include_router(sos_router, prefix="/sos", tags=["sos"])
api_router.include_router(
    fuel_stations_router, prefix="/fuel-stations", tags=["fuel-stations"]
)
api_router.include_router(insurance_router, prefix="/insurance", tags=["insurance"])

# ---- Phase 6: Admin analytics + billing -------------------------------------
from app.modules.billing.router import router as billing_router  # noqa: E402
from app.modules.stats.router import router as stats_router  # noqa: E402

# Stats router uses absolute paths (`/service-centers/{id}/stats/...`).
api_router.include_router(stats_router, tags=["stats"])
api_router.include_router(billing_router, prefix="/billing", tags=["billing"])

# ---- Phase 9: Audit + admin -------------------------------------------------
from app.modules.admin.router import router as admin_router  # noqa: E402
from app.modules.audit.router import router as audit_router  # noqa: E402

# Both routers use absolute paths for clarity.
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(audit_router, tags=["audit"])


@api_router.get("/ping", tags=["meta"], summary="Liveness marker for the v1 prefix")
def ping() -> dict:
    """Trivial hook so the /api/v1 mount is always testable."""
    return {"pong": True}
