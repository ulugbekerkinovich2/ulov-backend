"""Import the canonical ERP demo dataset from ``ulov-erp.json``.

This is the file the admin Login page advertises (``servis1`` / ``1234``,
``mexanik1`` / ``1234``). Importing it gives the platform a coherent demo:

  * 1 admin (``admin`` / ``admin123``) — role=admin
  * 1 owner (``servis1`` / ``1234``)   — phone +998901234567, runs
                                          "AutoPro Service"
  * 1 mechanic (``mexanik1`` / ``1234``)— phone +998907654321
  * Mechanics roster (bobur, akmal)    — both bound to AutoPro Service
  * 3 customer cars + service history (with parts + prices)
  * 5 reviews on AutoPro Service

The script is idempotent — re-runs are safe. We upsert by the natural keys:
phone for users, plate for cars, login for mechanics.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from dateutil import parser as dt_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.cars.models import Car  # noqa: E402
from app.modules.mechanics.models import Mechanic  # noqa: E402
from app.modules.reviews.models import Review  # noqa: E402
from app.modules.service_centers.models import ServiceCenter  # noqa: E402
from app.modules.services.models import Service, ServiceItem  # noqa: E402
from app.modules.users.models import User  # noqa: E402

def _candidate_paths() -> list:
    import os

    here = Path(__file__).resolve()
    out = []
    env = os.environ.get("ULOV_ERP_PATH")
    if env:
        out.append(Path(env))
    out.append(here.parent.parent.parent / "ulov-erp.json")
    out.append(here.parent.parent / "ulov-erp.json")
    out.append(Path("/ulov-erp.json"))
    out.append(Path("/Users/m3/Documents/ulov-plus/ulov-erp.json"))
    return out


def _resolve_data_path() -> Path:
    for p in _candidate_paths():
        if p.exists():
            return p
    raise FileNotFoundError(
        "ulov-erp.json not found in any candidate location"
    )


DATA_PATH = None  # resolved at runtime

UUIDLike = Union[uuid.UUID, str]


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------
def _parse_dt(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return dt_parser.parse(str(raw))
    except (ValueError, TypeError):
        return None


def _upsert_user(
    db: Session,
    *,
    phone: str,
    role: str,
    full_name: str,
    password: str,
) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        user = User(
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            full_name=full_name,
        )
        db.add(user)
        db.flush()
        print(f"  + user {phone} ({role}) — {full_name}")
        return user
    # Update role/name/password to match the canonical ERP dataset on every run.
    user.role = role
    user.full_name = full_name
    user.password_hash = hash_password(password)
    db.flush()
    print(f"  = updated user {phone} ({role}) — {full_name}")
    return user


def _upsert_center(
    db: Session, *, owner: User, name: str, phone: str, address: str
) -> ServiceCenter:
    c = db.query(ServiceCenter).filter(ServiceCenter.name == name).first()
    if c is None:
        c = ServiceCenter(
            owner_user_id=owner.id,
            name=name,
            phone=phone,
            address=address,
            services=[],
        )
        db.add(c)
        db.flush()
        print(f"  + centre {name}")
    elif c.owner_user_id != owner.id:
        c.owner_user_id = owner.id
        db.flush()
        print(f"  = re-pointed centre {name} → owner {owner.phone}")
    # Sync owner phone onto user's center_id so JWTs include it on login.
    if owner.center_id != c.id:
        owner.center_id = c.id
        db.flush()
    return c


def _upsert_mechanic(
    db: Session,
    *,
    center: ServiceCenter,
    full_name: str,
    login: str,
    password: str,
    service_types: list,
) -> Mechanic:
    m = db.query(Mechanic).filter(Mechanic.login == login).first()
    if m is None:
        m = Mechanic(
            center_id=center.id,
            full_name=full_name,
            login=login,
            password_hash=hash_password(password),
            service_types=service_types,
        )
        db.add(m)
        db.flush()
        print(f"  + mechanic {login} → {full_name}")
        return m
    m.center_id = center.id
    m.full_name = full_name
    m.password_hash = hash_password(password)
    m.service_types = service_types
    m.deleted_at = None
    db.flush()
    print(f"  = updated mechanic {login}")
    return m


def _upsert_customer_for_car(
    db: Session, *, owner_name: str, owner_phone: str
) -> User:
    if not owner_phone:
        # Fall back to a synthetic phone so cars always have a real owner row.
        owner_phone = f"+998{abs(hash(owner_name)) % 1_000_000_000:09d}"
    user = db.query(User).filter(User.phone == owner_phone).first()
    if user is not None:
        return user
    user = User(
        phone=owner_phone,
        password_hash=hash_password("demo-password"),
        role="customer",
        full_name=owner_name,
    )
    db.add(user)
    db.flush()
    print(f"  + customer {owner_phone} — {owner_name}")
    return user


def _upsert_car(db: Session, *, owner: User, raw: Dict[str, Any]) -> Car:
    plate = raw["plateNumber"]
    car = db.query(Car).filter(Car.plate == plate).first()
    if car is None:
        car = Car(
            owner_id=owner.id,
            plate=plate,
            plate_type="standard",
            brand=raw["brand"],
            model=raw["model"],
            year=raw["year"],
            color=raw.get("color"),
            vin=raw.get("vin"),
            mileage=raw.get("currentMileage", 0),
        )
        db.add(car)
        db.flush()
        print(f"  + car {plate} ({raw['brand']} {raw['model']})")
    else:
        # Bump mileage if the JSON has a higher value; never decrease.
        if car.mileage < (raw.get("currentMileage") or 0):
            car.mileage = raw["currentMileage"]
            db.flush()
    return car


def _upsert_service(
    db: Session,
    *,
    car: Car,
    center: ServiceCenter,
    raw: Dict[str, Any],
) -> Service:
    """Match by (car_id, mileage_at_intake) — cheap natural key for demo data."""
    mileage = raw.get("mileage", 0)
    s = (
        db.query(Service)
        .filter(Service.car_id == car.id)
        .filter(Service.mileage_at_intake == mileage)
        .first()
    )
    if s is not None:
        return s
    created_at = _parse_dt(raw.get("date") or raw.get("createdAt")) or datetime.utcnow()
    s = Service(
        car_id=car.id,
        center_id=center.id,
        status="completed",
        mileage_at_intake=mileage,
        next_recommended_mileage=raw.get("nextRecommendedMileage"),
        created_at=created_at,
        started_at=created_at,
        completed_at=created_at,
        notes=raw.get("notes"),
    )
    db.add(s)
    db.flush()
    for item_raw in raw.get("items", []):
        db.add(
            ServiceItem(
                service_id=s.id,
                service_type=item_raw.get("serviceType", "service"),
                parts=item_raw.get("parts", []),
                notes=item_raw.get("notes"),
                service_price=int(item_raw.get("servicePrice") or item_raw.get("price") or 0),
                parts_price=int(item_raw.get("partsPrice") or 0),
                created_at=created_at,
            )
        )
    print(f"  + service {raw.get('id')} — {len(raw.get('items', []))} items")
    return s


def _upsert_review(
    db: Session, *, center: ServiceCenter, customer: User, raw: Dict[str, Any]
) -> None:
    text = raw.get("comment") or raw.get("text") or ""
    existing = (
        db.query(Review)
        .filter(Review.center_id == center.id)
        .filter(Review.text == text)
        .first()
    )
    if existing is not None:
        return
    db.add(
        Review(
            user_id=customer.id,
            center_id=center.id,
            rating=int(raw.get("rating", 5)),
            text=text,
        )
    )
    print(f"  + review {raw.get('rating', '?')}★ — {text[:40]}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def import_erp() -> None:
    try:
        path = _resolve_data_path()
    except FileNotFoundError as exc:
        print(exc)
        sys.exit(1)
    print(f"reading {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    db: Session = SessionLocal()
    try:
        # ---- Users ---------------------------------------------------------
        print("Users...")
        users_by_username: Dict[str, User] = {}
        for u in data.get("users", []):
            phone = u.get("phone")
            if not phone:
                # Synthesise: admin gets a dedicated phone so all users have one.
                phone = {
                    "admin": "+998900000099",
                }.get(u["username"], f"+998900{abs(hash(u['username'])) % 10_000_000:07d}")
            user = _upsert_user(
                db,
                phone=phone,
                role=u.get("role", "customer"),
                full_name=u.get("name", u["username"]),
                password=u.get("password", "demo-password"),
            )
            users_by_username[u["username"]] = user
        db.commit()

        owner = users_by_username.get("servis1")
        if owner is None:
            print("✗ no servis1 owner in ulov-erp.json — abort")
            return

        # ---- Centre --------------------------------------------------------
        print("Centre...")
        centre = _upsert_center(
            db,
            owner=owner,
            name=owner.full_name and "AutoPro Service" or "AutoPro Service",
            phone=owner.phone,
            address="Toshkent, Buyuk Ipak Yo'li 12",
        )
        # Sync the mechanic-user's center_id too.
        mech_user = users_by_username.get("mexanik1")
        if mech_user is not None and mech_user.center_id != centre.id:
            mech_user.center_id = centre.id
            db.flush()
        db.commit()

        # ---- Mechanics -----------------------------------------------------
        print("Mechanics...")
        for m in data.get("mechanics", []):
            full_name = f"{m.get('name', '')} {m.get('surname', '')}".strip()
            _upsert_mechanic(
                db,
                center=centre,
                full_name=full_name or m.get("login", "mechanic"),
                login=m["login"],
                password=m.get("password", "1234"),
                service_types=m.get("serviceTypes", []),
            )
        # Plus expose the mexanik1 demo login at the centre too.
        _upsert_mechanic(
            db,
            center=centre,
            full_name=mech_user.full_name if mech_user else "Demo Mexanik",
            login="mexanik1",
            password="1234",
            service_types=data.get("serviceTypes", [])[:3],
        )
        # And servis1 itself, so the admin Login form's "username=servis1"
        # path (which falls back to mechanic-login) keeps working alongside
        # phone-login.
        _upsert_mechanic(
            db,
            center=centre,
            full_name=owner.full_name or "Servis Egasi",
            login="servis1",
            password="1234",
            service_types=data.get("serviceTypes", []),
        )
        db.commit()

        # ---- Vehicles + services ------------------------------------------
        print("Vehicles + services...")
        car_owner_index: Dict[str, User] = {}
        for v in data.get("vehicles", []):
            car_user = _upsert_customer_for_car(
                db,
                owner_name=v.get("ownerName", "Mijoz"),
                owner_phone=v.get("ownerPhone", ""),
            )
            car = _upsert_car(db, owner=car_user, raw=v)
            car_owner_index[v["id"]] = car_user
            for s in v.get("services", []):
                _upsert_service(db, car=car, center=centre, raw=s)
        db.commit()

        # ---- Reviews -------------------------------------------------------
        print("Reviews...")
        any_customer = next(iter(car_owner_index.values()), None) or owner
        for r in data.get("reviews", []):
            _upsert_review(db, center=centre, customer=any_customer, raw=r)
        db.commit()

        print("\n✓ ulov-erp data imported")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"✗ import failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_erp()
