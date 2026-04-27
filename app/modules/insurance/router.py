"""Insurance endpoints — tariffs, quote, policy."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_customer, get_db
from app.modules.insurance import service as svc
from app.modules.insurance.models import InsuranceTariff
from app.modules.insurance.schemas import (
    PolicyCreateIn,
    PolicyOut,
    QuoteIn,
    QuoteOut,
    TariffOut,
    CompanyOut,
    BuyPolisIn,
)

router = APIRouter()


@router.get(
    "/companies",
    response_model=List[CompanyOut],
    summary="Active insurance companies",
)
def list_companies(db: Session = Depends(get_db)) -> List[CompanyOut]:
    from app.modules.insurance.models import InsuranceCompany

    rows = db.execute(
        select(InsuranceCompany)
        .where(InsuranceCompany.active.is_(True))
        .order_by(InsuranceCompany.name)
    ).scalars()
    return [CompanyOut.from_orm(c) for c in rows]


@router.post(
    "/buy",
    response_model=PolicyOut,
    summary="Buy a policy (Phase 6 simple mock)",
)
def buy_policy(
    body: BuyPolisIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> PolicyOut:
    # Just a mock implementation for now
    policy = svc.buy_mock(db, user.id, body)
    return PolicyOut.from_orm(policy)


@router.get(
    "/tariffs",
    response_model=List[TariffOut],
    summary="Active insurance tariffs",
)
def list_tariffs(db: Session = Depends(get_db)) -> List[TariffOut]:
    rows = db.execute(
        select(InsuranceTariff)
        .where(InsuranceTariff.active.is_(True))
        .order_by(InsuranceTariff.code)
    ).scalars()
    return [TariffOut.from_orm(t) for t in rows]


@router.post(
    "/quotes",
    response_model=QuoteOut,
    summary="Quote a policy for a given tariff + car",
)
def get_quote(
    body: QuoteIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> QuoteOut:
    _, price, breakdown = svc.quote(
        db, tariff_code=body.tariff_code, car_id=body.car_id, owner_id=user.id
    )
    return QuoteOut(
        tariff_code=body.tariff_code,
        car_id=body.car_id,
        price=price,
        breakdown=breakdown,
    )


@router.post(
    "/policies",
    response_model=PolicyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending policy (payment wired in Phase 6)",
)
def create_policy(
    body: PolicyCreateIn,
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> PolicyOut:
    policy = svc.create_policy(
        db,
        user.id,
        tariff_code=body.tariff_code,
        car_id=body.car_id,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
    )
    return PolicyOut.from_orm(policy)


@router.get(
    "/policies",
    response_model=List[PolicyOut],
    summary="List my policies",
)
def list_my_policies(
    user: CurrentUser = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> List[PolicyOut]:
    from app.modules.insurance.models import InsurancePolicy

    rows = db.execute(
        select(InsurancePolicy)
        .where(InsurancePolicy.user_id == user.id)
        .order_by(InsurancePolicy.created_at.desc())
    ).scalars()
    return [PolicyOut.from_orm(p) for p in rows]
