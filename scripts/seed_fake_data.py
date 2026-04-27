"""Seed fake data into the empty tables for demo / UX testing.

Idempotent — re-running skips rows already present (matched by unique key
where one exists, otherwise by row count > 0). Assumes the canonical seed
(``import_user_json.py``) has already run, so demo users + cars + centres
are in place.

Tables filled:
  * subscription_plans          — basic / pro / vip (admin reference data)
  * insurance_companies         — 4 mock UZ insurers
  * insurance_tariffs           — 3 OSAGO/KASKO tariffs
  * mechanics                   — 2-3 per centre
  * reviews                     — 5-15 per centre, mostly 4-5★
  * service_transitions         — synthesise a believable timeline per
                                  imported service
  * mileage_readings            — append history rows for each car
  * trips + trip_points         — 3 short Tashkent trips per demo customer
  * sos_requests                — a couple of past calls
  * notifications               — demo customer inbox
  * devices                     — one Android push token per user
  * payments                    — one paid subscription + one pending insurance
  * insurance_policies          — one active policy per demo customer car
  * condition_images            — before/after pair for the most recent
                                  completed service of each car

Usage::

    docker compose exec api python -m scripts.seed_fake_data
"""

from __future__ import annotations

import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

# Make ``app`` importable when run as ``python scripts/...``.
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.billing.models import Payment, SubscriptionPlan  # noqa: E402
from app.modules.cars.models import Car, MileageReading  # noqa: E402
from app.modules.insurance.models import (  # noqa: E402
    InsuranceCompany,
    InsurancePolicy,
    InsuranceTariff,
)
from app.modules.mechanics.models import Mechanic  # noqa: E402
from app.modules.notifications.models import Device, Notification  # noqa: E402
from app.modules.reviews.models import Review  # noqa: E402
from app.modules.service_centers.models import ServiceCenter  # noqa: E402
from app.modules.services.models import (  # noqa: E402
    ConditionImage,
    Service,
    ServiceItem,
    ServiceTransition,
)
from app.modules.sos.models import SosProvider, SosRequest  # noqa: E402
from app.modules.trips.models import Trip, TripPoint  # noqa: E402
from app.modules.users.models import User  # noqa: E402

random.seed(42)  # deterministic fakes — re-runs produce the same shape


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Subscription plans
# ---------------------------------------------------------------------------
def seed_subscription_plans(db: Session) -> None:
    print("Subscription plans...")
    plans = [
        ("basic", "Basic", 15_000_000, 30),
        ("pro", "Pro", 35_000_000, 30),
        ("vip", "VIP", 90_000_000, 30),
    ]
    for code, name, price, days in plans:
        if db.query(SubscriptionPlan).filter_by(code=code).first():
            continue
        db.add(
            SubscriptionPlan(
                code=code, name=name, monthly_price=price, duration_days=days, active=True
            )
        )
        print(f"  + plan {code}")


# ---------------------------------------------------------------------------
# Insurance reference data
# ---------------------------------------------------------------------------
def seed_insurance(db: Session) -> None:
    print("Insurance companies + tariffs...")
    companies = [
        ("Gross Insurance", 4.7, 1245, 12_000_000, ["24/7 yordam", "Onlayn da'vo"]),
        ("Apex Insurance", 4.5, 980, 11_500_000, ["Tezkor to'lov", "Mobil ariza"]),
        ("Uzagrosug'urta", 4.6, 1102, 10_000_000, ["Davlat kafolati", "Filial keng"]),
        ("Alfa Invest", 4.4, 715, 13_500_000, ["KASKO chegirma", "Premium servis"]),
    ]
    for name, rating, reviews, base, perks in companies:
        if db.query(InsuranceCompany).filter_by(name=name).first():
            continue
        db.add(
            InsuranceCompany(
                name=name,
                rating=int(rating * 10),  # column is BigInteger; store ×10
                reviews_count=reviews,
                logo_url=None,
                base_price=base,
                perks=perks,
                active=True,
            )
        )
        print(f"  + company {name}")

    tariffs = [
        ("osago_basic", "OSAGO — minimal", 12_000_000),
        ("osago_full", "OSAGO — to'liq qoplov", 18_500_000),
        ("kasko_basic", "KASKO — bazaviy", 45_000_000),
    ]
    coefficients = {
        "brand": {"Chevrolet": 1.05, "Toyota": 1.1, "BMW": 1.4, "Lada": 0.9},
        "year_band": {"2020+": 1.2, "2015-2019": 1.0, "2010-2014": 0.85, "pre-2010": 0.7},
    }
    for code, name, base in tariffs:
        if db.query(InsuranceTariff).filter_by(code=code).first():
            continue
        db.add(
            InsuranceTariff(
                code=code,
                name=name,
                base_price=base,
                coefficients=coefficients,
                active=True,
            )
        )
        print(f"  + tariff {code}")


# ---------------------------------------------------------------------------
# Mechanics — per centre
# ---------------------------------------------------------------------------
def seed_mechanics(db: Session) -> None:
    print("Mechanics...")
    pool = [
        ("Akmal Karimov", ["motor", "diagnostika"]),
        ("Bekzod Yusupov", ["tormoz", "podvеska"]),
        ("Sardor Tursunov", ["aircon", "electricity"]),
        ("Jahongir Aliyev", ["motor", "transmission"]),
        ("Rustam Soatov", ["body", "paint"]),
    ]
    centers = list(db.execute(select(ServiceCenter)).scalars())
    for c_idx, center in enumerate(centers):
        existing = db.query(Mechanic).filter_by(center_id=center.id).count()
        if existing >= 2:
            continue
        chosen = random.sample(pool, k=random.randint(2, 3))
        for m_idx, (name, types) in enumerate(chosen):
            login = f"mech-{c_idx}-{m_idx}-{uuid.uuid4().hex[:4]}"
            db.add(
                Mechanic(
                    center_id=center.id,
                    full_name=name,
                    login=login,
                    password_hash=hash_password("demo-password"),
                    service_types=types,
                )
            )
            print(f"  + mechanic {name} @ {center.name}")


# ---------------------------------------------------------------------------
# Reviews — per centre
# ---------------------------------------------------------------------------
def seed_reviews(db: Session) -> None:
    print("Reviews...")
    samples = [
        (5, "Mukammal xizmat, tez va sifatli."),
        (5, "Aniq vaqtda yetkazib berishdi, rahmat."),
        (4, "Yaxshi, lekin biroz qimmatroq."),
        (5, "Ustalar professional. Tavsiya qilaman."),
        (4, "Hammasi yaxshi, navbat biroz uzoq edi."),
        (3, "O'rtacha — yana borishni o'ylab ko'raman."),
        (5, "Diagnostika tekin, narxlari halol."),
        (4, "Joy toza, mijozlarga hurmat."),
    ]
    customers = list(db.execute(select(User).where(User.role == "customer")).scalars())
    if not customers:
        print("  ! no customers; skipping")
        return
    centers = list(db.execute(select(ServiceCenter)).scalars())
    for center in centers:
        if db.query(Review).filter_by(center_id=center.id).count() >= 5:
            continue
        n = random.randint(5, 10)
        for _ in range(n):
            rating, text = random.choice(samples)
            customer = random.choice(customers)
            db.add(
                Review(
                    user_id=customer.id,
                    center_id=center.id,
                    service_id=None,
                    rating=rating,
                    text=text,
                )
            )
        print(f"  + {n} reviews @ {center.name}")


# ---------------------------------------------------------------------------
# Service transitions — synthesise from existing services
# ---------------------------------------------------------------------------
def seed_service_transitions(db: Session) -> None:
    print("Service transitions...")
    services = list(
        db.execute(
            select(Service).where(Service.deleted_at.is_(None))
        ).scalars()
    )
    actor = db.query(User).filter_by(role="owner").first()
    actor_id = actor.id if actor else None
    for s in services:
        if db.query(ServiceTransition).filter_by(service_id=s.id).count() > 0:
            continue
        base = s.created_at or _utcnow()
        rows = [(None, "waiting", base, None)]
        if s.status in ("in_progress", "paused", "completed", "cancelled"):
            rows.append((
                "waiting",
                "in_progress",
                base + timedelta(minutes=15),
                None,
            ))
        if s.status in ("paused",):
            rows.append((
                "in_progress",
                "paused",
                base + timedelta(hours=1),
                "kutilmagan ehtiyot qism",
            ))
        if s.status == "completed":
            rows.append((
                "in_progress",
                "completed",
                s.completed_at or (base + timedelta(hours=2)),
                None,
            ))
        if s.status == "cancelled":
            rows.append((
                "in_progress",
                "cancelled",
                base + timedelta(hours=1),
                s.cancel_reason or "mijoz so'rovi",
            ))
        for from_, to_, at, reason in rows:
            db.add(
                ServiceTransition(
                    service_id=s.id,
                    from_status=from_,
                    to_status=to_,
                    by_user_id=actor_id,
                    reason=reason,
                    at=at,
                )
            )
        print(f"  + {len(rows)} transitions for service {str(s.id)[:8]}")


# ---------------------------------------------------------------------------
# Mileage readings — back-fill history per car
# ---------------------------------------------------------------------------
def seed_mileage_readings(db: Session) -> None:
    print("Mileage readings...")
    cars = list(db.execute(select(Car)).scalars())
    for car in cars:
        if db.query(MileageReading).filter_by(car_id=car.id).count() > 0:
            continue
        # 6 monthly readings ramping up to current mileage.
        points = 6
        target = car.mileage or 50000
        step = max(target // (points * 2), 500)
        base_ts = int((_utcnow() - timedelta(days=180)).timestamp() * 1000)
        for i in range(points):
            value = max(0, target - step * (points - i - 1))
            db.add(
                MileageReading(
                    car_id=car.id,
                    value=value,
                    source="user" if i % 2 == 0 else "service",
                    recorded_at=base_ts + i * 30 * 24 * 3600 * 1000,
                )
            )
        print(f"  + {points} readings for car {car.plate}")


# ---------------------------------------------------------------------------
# Trips + GPS points
# ---------------------------------------------------------------------------
_TASHKENT_ROUTES = [
    # (name, polyline of (lat, lng))
    (
        "Yunusobod → Olmazor",
        [(41.367, 69.288), (41.36, 69.272), (41.345, 69.265), (41.33, 69.255)],
    ),
    (
        "Chilonzor → Markaz",
        [(41.275, 69.205), (41.288, 69.225), (41.298, 69.247), (41.311, 69.279)],
    ),
    (
        "Aeroport tomon",
        [(41.311, 69.28), (41.295, 69.288), (41.275, 69.292), (41.262, 69.282)],
    ),
]


def seed_trips(db: Session) -> None:
    print("Trips + GPS points...")
    customer = db.query(User).filter_by(role="customer").first()
    if customer is None:
        print("  ! no customer; skipping")
        return
    if db.query(Trip).filter_by(user_id=customer.id).count() >= 3:
        return
    car = db.query(Car).filter_by(owner_id=customer.id).first()
    for idx, (name, route) in enumerate(_TASHKENT_ROUTES):
        started = _utcnow() - timedelta(days=idx + 1, hours=random.randint(1, 5))
        finished = started + timedelta(minutes=20 + idx * 10)
        # Crude distance estimate: 1.5 km per polyline hop.
        distance_km = round((len(route) - 1) * 1.5, 3)
        duration_s = int((finished - started).total_seconds())
        avg_speed = round(distance_km / max(duration_s / 3600, 0.001), 2)
        trip = Trip(
            user_id=customer.id,
            car_id=car.id if car else None,
            started_at=started,
            finished_at=finished,
            distance_km=distance_km,
            duration_s=duration_s,
            avg_speed=avg_speed,
            fuel_l_est=round(distance_km * 0.07, 3),
            polyline=";".join(f"{lat},{lng}" for lat, lng in route),
        )
        db.add(trip)
        db.flush()
        for j, (lat, lng) in enumerate(route):
            db.add(
                TripPoint(
                    trip_id=trip.id,
                    lat=lat,
                    lng=lng,
                    speed=random.uniform(20, 60),
                    heading=random.uniform(0, 360),
                    ts=started + timedelta(seconds=int(duration_s * j / max(len(route) - 1, 1))),
                )
            )
        print(f"  + trip {name} ({distance_km} km)")


# ---------------------------------------------------------------------------
# SOS requests — past calls
# ---------------------------------------------------------------------------
def seed_sos_requests(db: Session) -> None:
    print("SOS requests...")
    customer = db.query(User).filter_by(role="customer").first()
    if customer is None or db.query(SosRequest).count() > 0:
        return
    providers = list(db.execute(select(SosProvider)).scalars())
    if not providers:
        return
    samples = [
        (random.choice([p for p in providers if p.category == "tow"] or providers),
         "completed", "Avtomobil ishga tushmadi"),
        (random.choice([p for p in providers if p.category == "roadside"] or providers),
         "completed", "Akkumulyator quvvatsiz"),
        (random.choice([p for p in providers if p.category == "fuel"] or providers),
         "cancelled", "Yaqindagi yoqilg'i shoxobchasiga o'zim yetib oldim"),
    ]
    for prov, status, note in samples:
        db.add(
            SosRequest(
                user_id=customer.id,
                provider_id=prov.id,
                status=status,
                lat=41.311 + random.uniform(-0.02, 0.02),
                lng=69.279 + random.uniform(-0.02, 0.02),
                note=note,
            )
        )
        print(f"  + SOS {prov.category} ({status})")


# ---------------------------------------------------------------------------
# Notifications + devices
# ---------------------------------------------------------------------------
def seed_notifications(db: Session) -> None:
    print("Notifications + devices...")
    customer = db.query(User).filter_by(role="customer").first()
    if customer is None:
        return
    if db.query(Notification).filter_by(user_id=customer.id).count() == 0:
        msgs = [
            ("service.completed", "Xizmat yakunlandi", "Avtomobilingiz tayyor — qabul qilib oling."),
            ("billing.paid", "To'lov muvaffaqiyatli", "Subscription #demo qabul qilindi."),
            ("insurance.expiring", "Sug'urta tugayapti", "Polisingiz 7 kun ichida tugaydi — yangilang."),
            ("content.tip", "Yangi maslahat", "Qishki shinalar haqida yangi maqola."),
        ]
        for kind, title, body in msgs:
            db.add(
                Notification(
                    user_id=customer.id,
                    kind=kind,
                    title=title,
                    body=body,
                    payload={"demo": True},
                    read_at=_utcnow() if kind == "content.tip" else None,
                )
            )
            print(f"  + notif {kind}")

    # Devices — one per user.
    for user in db.execute(select(User)).scalars():
        if db.query(Device).filter_by(user_id=user.id).count() > 0:
            continue
        db.add(
            Device(
                user_id=user.id,
                token=f"demo-fcm-{uuid.uuid4().hex}",
                platform="android",
            )
        )
        print(f"  + device for {user.phone}")


# ---------------------------------------------------------------------------
# Payments + insurance policies
# ---------------------------------------------------------------------------
def seed_payments_and_policies(db: Session) -> None:
    print("Payments + insurance policies...")
    owner = db.query(User).filter_by(role="owner").first()
    customer = db.query(User).filter_by(role="customer").first()
    plan = db.query(SubscriptionPlan).filter_by(code="basic").first()
    center = db.query(ServiceCenter).first()

    if owner and plan and center and db.query(Payment).count() == 0:
        # Paid subscription
        paid = Payment(
            user_id=owner.id,
            kind="subscription",
            target_id=center.id,
            plan_id=plan.id,
            amount=plan.monthly_price,
            provider="payme",
            status="paid",
            external_ref=f"PAYME-DEMO-{uuid.uuid4().hex[:8]}",
            paid_at=_utcnow() - timedelta(days=7),
        )
        # Pending insurance payment
        pending = Payment(
            user_id=customer.id if customer else owner.id,
            kind="insurance",
            target_id=None,
            plan_id=None,
            amount=14_500_000,
            provider="click",
            status="pending",
        )
        db.add_all([paid, pending])
        print("  + 1 paid subscription, 1 pending insurance")

        # Bump the centre's subscription window so frontend reflects "active".
        center.subscription_plan_id = plan.id
        center.subscription_until = (_utcnow() + timedelta(days=plan.duration_days)).isoformat()

    # One active policy per car.
    if customer:
        tariff = db.query(InsuranceTariff).filter_by(code="osago_basic").first()
        company = db.query(InsuranceCompany).first()
        if tariff and db.query(InsurancePolicy).filter_by(user_id=customer.id).count() == 0:
            for car in db.execute(
                select(Car).where(Car.owner_id == customer.id)
            ).scalars():
                today = date.today()
                db.add(
                    InsurancePolicy(
                        user_id=customer.id,
                        car_id=car.id,
                        tariff_id=tariff.id,
                        company_id=company.id if company else None,
                        price=14_500_000,
                        valid_from=today - timedelta(days=30),
                        valid_to=today + timedelta(days=335),
                        payment_status="paid",
                        payment_provider="payme",
                        external_ref=f"POLIS-{uuid.uuid4().hex[:8].upper()}",
                    )
                )
                print(f"  + policy for car {car.plate}")


# ---------------------------------------------------------------------------
# Condition images — for the most recent completed service per car
# ---------------------------------------------------------------------------
def seed_condition_images(db: Session) -> None:
    print("Condition images...")
    customer = db.query(User).filter_by(role="customer").first()
    if customer is None:
        return
    base_url = "https://pub-15bb9454790b4d0da1f150fe663d2be0.r2.dev/services/demo"
    for car in db.execute(select(Car).where(Car.owner_id == customer.id)).scalars():
        latest = (
            db.query(Service)
            .filter_by(car_id=car.id, status="completed")
            .order_by(Service.completed_at.desc())
            .first()
        )
        if latest is None:
            continue
        if db.query(ConditionImage).filter_by(service_id=latest.id).count() > 0:
            continue
        for stage in ("before", "after"):
            db.add(
                ConditionImage(
                    service_id=latest.id,
                    url=f"{base_url}/{latest.id}-{stage}.jpg",
                    stage=stage,
                    uploaded_by=customer.id,
                )
            )
        print(f"  + before/after for service {str(latest.id)[:8]}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> None:
    db: Session = SessionLocal()
    try:
        seed_subscription_plans(db)
        db.commit()
        seed_insurance(db)
        db.commit()
        seed_mechanics(db)
        db.commit()
        seed_reviews(db)
        db.commit()
        seed_service_transitions(db)
        db.commit()
        seed_mileage_readings(db)
        db.commit()
        seed_trips(db)
        db.commit()
        seed_sos_requests(db)
        db.commit()
        seed_notifications(db)
        db.commit()
        seed_payments_and_policies(db)
        db.commit()
        seed_condition_images(db)
        db.commit()
        print("✓ fake data seeded")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"✗ failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
