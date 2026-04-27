"""Insurance domain logic.

Quote calculation:

    price = base_price × coef("year_band", car.year)
                       × coef("brand", car.brand)

Coefficients live on the tariff row in JSONB. Missing coefficient = 1.0.
Payment is created in ``pending`` state — Phase 6 wires the actual provider.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Tuple, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.cars import repository as cars_repo
from app.modules.insurance.models import InsurancePolicy, InsuranceTariff, InsuranceCompany
from app.modules.insurance.schemas import BuyPolisIn
from datetime import timedelta

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def buy_mock(db: Session, user_id: UUIDLike, body: BuyPolisIn) -> InsurancePolicy:
    # 1. Verify company
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == body.company_id)
    ).scalar_one_or_none()
    if not company:
        raise NotFoundError("Company not found", code="INSURANCE_COMPANY_NOT_FOUND")

    # 2. Verify car
    car = cars_repo.get_by_id(db, body.car_id)
    if not car:
        raise NotFoundError("Car not found", code="CAR_NOT_FOUND")

    # 3. Use default tariff for now
    tariff = db.execute(select(InsuranceTariff).limit(1)).scalar_one_or_none()
    if not tariff:
        # Create a default one if missing
        tariff = InsuranceTariff(
            id=UUID("00000000-0000-4000-a000-000000000001"),
            code="default",
            name="Default OSAGO",
            base_price=100000,
            coefficients={},
            active=True
        )
        db.add(tariff)
        db.flush()

    # 4. Calculate price (simple mock matching frontend logic)
    price = company.base_price
    if body.period_months == 12:
        price = int(price * 1.6) # VIP
    
    valid_from = date.today()
    valid_to = valid_from + timedelta(days=30 * body.period_months)

    policy = InsurancePolicy(
        user_id=user_id,
        car_id=body.car_id,
        company_id=body.company_id,
        tariff_id=tariff.id,
        price=price,
        valid_from=valid_from,
        valid_to=valid_to,
        payment_status="paid", # Mocked as paid for demo
        payment_provider=body.payment_method,
        external_ref=f"MOCK-{body.passport_series}{body.passport_number}"
    )
    db.add(policy)
    db.flush()
    return policy


def _get_tariff(db: Session, code: str) -> InsuranceTariff:
    t = db.execute(
        select(InsuranceTariff)
        .where(InsuranceTariff.code == code)
        .where(InsuranceTariff.active.is_(True))
    ).scalar_one_or_none()
    if t is None:
        raise NotFoundError(
            "Tariff not found or inactive", code="INSURANCE_TARIFF_NOT_FOUND"
        )
    return t


def _coef(table: Dict[str, Any], key: str, default: float = 1.0) -> float:
    try:
        v = table.get(key, default)
        return float(v)
    except (TypeError, ValueError):
        return default


def _year_band(year: int) -> str:
    if year >= 2020:
        return "2020+"
    if year >= 2015:
        return "2015-2019"
    if year >= 2010:
        return "2010-2014"
    return "pre-2010"


def quote(
    db: Session, *, tariff_code: str, car_id: UUIDLike, owner_id: UUIDLike
) -> Tuple[InsuranceTariff, int, Dict[str, Any]]:
    tariff = _get_tariff(db, tariff_code)
    car = cars_repo.get_by_id(db, car_id)
    if car is None:
        raise NotFoundError("Car not found", code="CAR_NOT_FOUND")
    if str(car.owner_id) != str(owner_id):
        raise ValidationError(
            "car not owned by user", code="INSURANCE_CAR_NOT_OWNED"
        )

    coefficients: Dict[str, Any] = tariff.coefficients or {}
    brand_factor = _coef(coefficients.get("brand", {}), car.brand)
    year_factor = _coef(coefficients.get("year_band", {}), _year_band(car.year))

    price = int(round(tariff.base_price * brand_factor * year_factor))
    breakdown = {
        "base_price": tariff.base_price,
        "brand_factor": brand_factor,
        "year_factor": year_factor,
        "year_band": _year_band(car.year),
    }
    return tariff, price, breakdown


def create_policy(
    db: Session,
    user_id: UUIDLike,
    *,
    tariff_code: str,
    car_id: UUIDLike,
    valid_from: date,
    valid_to: date,
) -> InsurancePolicy:
    if valid_to < valid_from:
        raise ValidationError(
            "valid_to must be on or after valid_from",
            code="INSURANCE_DATE_RANGE_INVALID",
        )
    tariff, price, _ = quote(
        db, tariff_code=tariff_code, car_id=car_id, owner_id=user_id
    )
    policy = InsurancePolicy(
        user_id=user_id,
        car_id=car_id,
        tariff_id=tariff.id,
        price=price,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    db.add(policy)
    db.flush()
    log.info(
        "insurance_policy_created",
        policy_id=str(policy.id),
        user_id=str(user_id),
        tariff_code=tariff_code,
        price=price,
    )
    return policy
