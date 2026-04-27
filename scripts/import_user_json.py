"""Import seed data from /data.json into the live Postgres.

Idempotent — re-running on the same DB skips already-imported rows. Bootstraps
a demo customer + owner when none exist so the script works on a fresh db.

Sections covered:
  * cars + serviceHistory      (demo customer's garage + history)
  * serviceCenters             (linked to demo owner)
  * sosProviders               (tow / roadside / fuel / ...)
  * stories                    (resolves ``centerId`` → centre UUID)
  * fuelStations               (location stored as JSONB ``{lat, lng}``)
  * content                    (trafficRules, fines, tips, roadSigns)
  * roadSigns categories       (one ContentPage per category for better UX)
  * vehicleBrands / Colors /
    serviceIntervals           (served by ``/api/v1/reference/*`` endpoints
                                directly from data.json — see
                                ``app/modules/reference``)

Usage::

    docker compose exec api python -m scripts.import_user_json
    # or, locally:
    cd backend && poetry run python -m scripts.import_user_json
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dateutil import parser
from sqlalchemy.orm import Session

# Make ``app`` importable when run as a plain script (`python scripts/...`).
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.cars.models import Car  # noqa: E402
from app.modules.content.models import ContentPage  # noqa: E402
from app.modules.content.stories_models import Story  # noqa: E402
from app.modules.fuel_stations.models import FuelStation  # noqa: E402
from app.modules.service_centers.models import ServiceCenter  # noqa: E402
from app.modules.mechanics.models import Mechanic  # noqa: E402, F401  (FK target)
from app.modules.services.models import Service, ServiceItem  # noqa: E402
from app.modules.sos.models import SosProvider  # noqa: E402
from app.modules.users.models import User  # noqa: E402

def _resolve_data_path() -> Path:
    """Find ``data.json`` in candidate locations (bundled first)."""
    import os

    here = Path(__file__).resolve()
    candidates: list = []
    env = os.environ.get("ULOV_DATA_PATH")
    if env:
        candidates.append(Path(env))
    # Bundled with the repo — first preference.
    candidates.append(here.parent / "data" / "data.json")
    # Legacy / dev locations.
    candidates.append(here.parent.parent.parent / "data.json")
    candidates.append(here.parent.parent / "data.json")
    candidates.append(Path("/data.json"))
    candidates.append(Path("/Users/m3/Documents/ulov-plus/data.json"))
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]  # let downstream raise a sensible FileNotFoundError


DATA_PATH = _resolve_data_path()

DEMO_CUSTOMER_PHONE = "+998901234567"
DEMO_OWNER_PHONE = "+998900000001"


def _ensure_user(db: Session, *, phone: str, role: str, full_name: str) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if user is not None:
        if user.role != role:
            user.role = role
            db.flush()
        return user
    user = User(
        phone=phone,
        password_hash=hash_password("demo-password"),
        role=role,
        full_name=full_name,
    )
    db.add(user)
    db.flush()
    print(f"  + created {role} user {phone}")
    return user


# ---------------------------------------------------------------------------
# Section importers
# ---------------------------------------------------------------------------
def _import_cars(db: Session, data: Dict[str, Any], user: User) -> Dict[str, uuid.UUID]:
    print("Importing Cars...")
    car_id_map: Dict[str, uuid.UUID] = {}
    for c in data.get("cars", []):
        existing = db.query(Car).filter(Car.plate == c["plate"]).first()
        if existing is not None:
            car_id_map[c["id"]] = existing.id
            print(f"  = car {c['plate']} exists, skipping")
            continue
        car = Car(
            owner_id=user.id,
            plate=c["plate"],
            plate_type="standard",
            brand=c["brand"],
            model=c["model"],
            year=c["year"],
            color=c.get("color"),
            vin=c.get("vin"),
            mileage=c.get("mileage", 0),
            photo_url=c.get("image"),
        )
        db.add(car)
        db.flush()
        car_id_map[c["id"]] = car.id
        print(f"  + car {c['plate']}")
    return car_id_map


def _import_centers(
    db: Session, data: Dict[str, Any], owner: User
) -> Dict[str, uuid.UUID]:
    print("Importing Service Centers...")
    out: Dict[str, uuid.UUID] = {}
    for c in data.get("serviceCenters", []):
        existing = db.query(ServiceCenter).filter(ServiceCenter.name == c["name"]).first()
        if existing is not None:
            out[c["id"]] = existing.id
            print(f"  = centre {c['name']} exists, skipping")
            continue
        location = None
        if c.get("lat") is not None and c.get("lng") is not None:
            location = {"lat": c["lat"], "lng": c["lng"]}
        center = ServiceCenter(
            owner_user_id=owner.id,
            name=c["name"],
            address=c.get("address", ""),
            phone=c.get("phone", ""),
            description=c.get("description"),
            location=location,
            services=c.get("services", []),
            avatar_url=c.get("image"),
        )
        db.add(center)
        db.flush()
        out[c["id"]] = center.id
        print(f"  + centre {c['name']}")
    return out


def _import_history(
    db: Session,
    data: Dict[str, Any],
    car_map: Dict[str, uuid.UUID],
    center_map: Dict[str, uuid.UUID],
) -> None:
    print("Importing Service History...")
    for s in data.get("serviceHistory", []):
        car_uuid = car_map.get(s.get("carId"))
        if car_uuid is None:
            continue

        # Skip if a service exists for this car at this mileage already.
        existing = (
            db.query(Service)
            .filter(Service.car_id == car_uuid)
            .filter(Service.mileage_at_intake == s.get("mileageAt", 0))
            .first()
        )
        if existing is not None:
            continue

        # Resolve centre via name OR centerId.
        center_uuid = None
        if s.get("centerId") and s["centerId"] in center_map:
            center_uuid = center_map[s["centerId"]]
        elif s.get("centerName"):
            cm = (
                db.query(ServiceCenter)
                .filter(ServiceCenter.name == s["centerName"])
                .first()
            )
            if cm is not None:
                center_uuid = cm.id
        if center_uuid is None:
            # Service rows REQUIRE a centre; fall back to the first one we know.
            if not center_map:
                continue
            center_uuid = next(iter(center_map.values()))

        try:
            dt = parser.parse(s["date"]) if s.get("date") else datetime.utcnow()
        except (ValueError, TypeError):
            dt = datetime.utcnow()

        status = s.get("status") or "completed"
        service = Service(
            car_id=car_uuid,
            center_id=center_uuid,
            status=status,
            mileage_at_intake=s.get("mileageAt", 0),
            created_at=dt,
            started_at=dt,
            completed_at=dt if status == "completed" else None,
            notes=f"Master: {s.get('master', '')}".strip(),
        )
        db.add(service)
        db.flush()

        db.add(
            ServiceItem(
                service_id=service.id,
                service_type=s.get("type", "service"),
                service_price=int(s.get("cost") or 0),
                parts_price=0,
                parts=[{"name": p, "spec": ""} for p in s.get("parts", [])],
                created_at=dt,
            )
        )
        print(f"  + history {s.get('type')} for car {s.get('carId')}")


def _import_sos(db: Session, data: Dict[str, Any]) -> None:
    print("Importing SOS Providers...")
    for category, providers in (data.get("sosProviders") or {}).items():
        for p in providers:
            existing = db.query(SosProvider).filter(SosProvider.name == p["name"]).first()
            if existing is not None:
                continue
            db.add(
                SosProvider(
                    category=category,
                    name=p["name"],
                    phone=p.get("phone", ""),
                    city="Toshkent",
                    available_24_7=True,
                )
            )
            print(f"  + sos {category}/{p['name']}")


def _import_stories(
    db: Session, data: Dict[str, Any], center_map: Dict[str, uuid.UUID]
) -> None:
    print("Importing Stories...")
    for st in data.get("stories", []):
        existing = db.query(Story).filter(Story.title == st["title"]).first()
        if existing is not None:
            continue
        valid_until = None
        if st.get("validUntil"):
            try:
                valid_until = parser.parse(st["validUntil"])
            except (ValueError, TypeError):
                valid_until = None
        db.add(
            Story(
                center_id=center_map.get(st.get("centerId")),
                title=st["title"],
                image_url=st.get("image", ""),
                content=st.get("description", ""),
                discount_label=st.get("discount"),
                valid_until=valid_until,
                is_active=True,
            )
        )
        print(f"  + story {st['title']}")


def _import_fuel_stations(db: Session, data: Dict[str, Any]) -> None:
    print("Importing Fuel Stations...")
    for fs in data.get("fuelStations", []):
        # Use brand+address as a uniqueness key (data.json has no stable id).
        existing = (
            db.query(FuelStation)
            .filter(FuelStation.name == fs["brand"])
            .filter(FuelStation.address == fs.get("address", ""))
            .first()
        )
        if existing is not None:
            continue
        db.add(
            FuelStation(
                name=fs["brand"],
                brand=fs["brand"],
                address=fs.get("address", ""),
                location={"lat": fs["lat"], "lng": fs["lng"]},
                prices=fs.get("prices", {}),
            )
        )
        print(f"  + fuel station {fs['brand']}")


def _save_page(
    db: Session, *, kind: str, lang: str, slug: str, title: str, body: dict
) -> bool:
    existing = (
        db.query(ContentPage)
        .filter(ContentPage.kind == kind)
        .filter(ContentPage.lang == lang)
        .filter(ContentPage.slug == slug)
        .first()
    )
    if existing is not None:
        return False
    db.add(
        ContentPage(kind=kind, lang=lang, slug=slug, title=title, body=body)
    )
    return True


def _import_content(db: Session, data: Dict[str, Any]) -> None:
    print("Importing Content (rules / fines / tips / signs)...")

    for c in data.get("trafficRules", []):
        for lang in ("uz", "ru", "en"):
            title = (c.get("title") or {}).get(lang) or c.get("id", "")
            if _save_page(
                db,
                kind="traffic_rules",
                lang=lang,
                slug=c["id"],
                title=title,
                body=c,
            ):
                print(f"  + traffic_rules/{lang}/{c['id']}")

    for f in data.get("fines", []):
        for lang in ("uz", "ru", "en"):
            title = (f.get("title") or {}).get(lang) or f.get("id", "")
            if _save_page(
                db,
                kind="fines",
                lang=lang,
                slug=f["id"],
                title=title,
                body=f,
            ):
                print(f"  + fines/{lang}/{f['id']}")

    for t in data.get("tips", []):
        for lang in ("uz", "ru", "en"):
            title = (t.get("title") or {}).get(lang) or t.get("id", "")
            if _save_page(
                db,
                kind="tips",
                lang=lang,
                slug=t["id"],
                title=title,
                body=t,
            ):
                print(f"  + tips/{lang}/{t['id']}")

    # Road signs — split per-category for nicer browsing, keep a "__all__"
    # blob too for backwards compat with any client expecting one page.
    rs = data.get("roadSigns") or {}
    if rs:
        for cat in rs.get("categories", []):
            cat_id = cat.get("id") or "uncategorised"
            for lang in ("uz", "ru", "en"):
                title = (cat.get("title") or {}).get(lang) or cat_id
                signs_in_cat = [
                    s for s in rs.get("signs", []) if s.get("category") == cat_id
                ]
                body = {
                    "category": cat,
                    "signs": signs_in_cat,
                }
                if _save_page(
                    db,
                    kind="road_signs",
                    lang=lang,
                    slug=cat_id,
                    title=title,
                    body=body,
                ):
                    print(f"  + road_signs/{lang}/{cat_id} ({len(signs_in_cat)} signs)")
        for lang in ("uz", "ru", "en"):
            if _save_page(
                db,
                kind="road_signs",
                lang=lang,
                slug="__all__",
                title="Yo'l belgilari",
                body=rs,
            ):
                print(f"  + road_signs/{lang}/__all__")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
def import_data() -> None:
    if not DATA_PATH.exists():
        print(f"data.json not found at {DATA_PATH}")
        sys.exit(1)

    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    db: Session = SessionLocal()
    try:
        owner = _ensure_user(
            db, phone=DEMO_OWNER_PHONE, role="owner", full_name="Demo Owner"
        )
        customer = _ensure_user(
            db,
            phone=DEMO_CUSTOMER_PHONE,
            role="customer",
            full_name="Demo Customer",
        )
        db.commit()

        car_map = _import_cars(db, data, customer)
        db.commit()

        center_map = _import_centers(db, data, owner)
        db.commit()

        _import_history(db, data, car_map, center_map)
        db.commit()

        _import_sos(db, data)
        db.commit()

        _import_stories(db, data, center_map)
        db.commit()

        _import_fuel_stations(db, data)
        db.commit()

        _import_content(db, data)
        db.commit()

        print("✓ data imported successfully")

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"✗ import failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_data()
