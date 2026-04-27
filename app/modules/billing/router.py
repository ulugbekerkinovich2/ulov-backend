"""Billing endpoints — plans, checkout, webhooks."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_db
from app.modules.billing import service as svc
from app.modules.billing.models import SubscriptionPlan
from app.modules.billing.schemas import (
    CheckoutIn,
    CheckoutOut,
    PaymentOut,
    PlanOut,
    WebhookIn,
)

router = APIRouter()


@router.get(
    "/plans",
    response_model=List[PlanOut],
    summary="Active subscription plans",
)
def list_plans(db: Session = Depends(get_db)) -> List[PlanOut]:
    rows = db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.active.is_(True))
        .order_by(SubscriptionPlan.monthly_price)
    ).scalars()
    return [PlanOut.from_orm(p) for p in rows]


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending subscription payment",
)
def checkout(
    body: CheckoutIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutOut:
    payment = svc.checkout_subscription(
        db,
        user,
        plan_code=body.plan_code,
        center_id=body.center_id,
        provider=body.provider,
    )
    # Phase 7 will call the provider SDK to mint a real checkout URL. Until
    # then we surface a deterministic placeholder so the frontend can still
    # round-trip the ``payment_id``.
    redirect = f"https://checkout.example/{body.provider}/{payment.id}"
    return CheckoutOut(
        payment_id=payment.id,
        amount=payment.amount,
        provider=body.provider,
        status=payment.status,
        redirect_url=redirect,
    )


@router.post(
    "/webhooks/payme",
    summary="Payme JSON-RPC webhook (Basic auth + provider error envelope)",
)
async def webhook_payme(
    request: Request,
    db: Session = Depends(get_db),
):
    """Payme expects HTTP 200 OK regardless of protocol-level errors.

    The adapter (``app.integrations.payme``) builds the response body; we
    only relay it.
    """
    from app.integrations.payme import dispatch

    body = await request.json()
    return dispatch(db, body, authorization=request.headers.get("authorization"))


@router.post(
    "/webhooks/click",
    summary="Click form-encoded webhook (md5 signature)",
)
async def webhook_click(request: Request, db: Session = Depends(get_db)):
    from app.integrations.click import handle

    form = await request.form()
    return handle(db, dict(form))


@router.post(
    "/webhooks/test",
    response_model=PaymentOut,
    summary="Test/manual webhook (used in dev + integration tests)",
)
def webhook_test(body: WebhookIn, db: Session = Depends(get_db)) -> PaymentOut:
    p = svc.apply_webhook(
        db,
        payment_id=body.payment_id,
        external_ref=body.external_ref,
        status=body.status,
    )
    return PaymentOut.from_orm(p)
