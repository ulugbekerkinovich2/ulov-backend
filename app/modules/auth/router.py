"""Auth endpoints (Phase 1).

Ten endpoints, fully wired to service + repository + Redis.

Corresponds to SYSTEM_ARCHITECTURE.md §20, rows #1–#10.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.rate_limit import client_ip
from app.deps import get_db, get_redis_otp
from app.modules.auth import repository as repo
from app.modules.auth import service as svc
from app.modules.auth.schemas import (
    LoginIn,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    PasswordResetRequestIn,
    PasswordResetConfirmIn,
    RegisterCenterIn,
    MechanicLoginIn,
    RegisterIn,
    TokenOut,
    UserOut,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_TTL_SECONDS,
        # Scope the cookie to the auth prefix so it is only sent where needed.
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")


def _user_agent(request: Request) -> Optional[str]:
    ua = request.headers.get("user-agent")
    return ua[:500] if ua else None


def _token_envelope(
    user, access: str, ttl: int  # type: ignore[no-untyped-def]
) -> TokenOut:
    return TokenOut(
        access_token=access,
        expires_in=ttl,
        user=UserOut.from_orm(user),
    )


async def _send_otp_sms(phone: str, code: str) -> None:
    """Best-effort SMS dispatch — never blocks OTP issuance.

    A failure to send is logged but doesn't fail the request: the OTP is
    already in Redis, and the user can request a resend or fall back to
    ``dev_code`` echo in non-prod.
    """
    from app.core.logging import get_logger
    from app.integrations.eskiz import EskizError, client as eskiz

    log = get_logger(__name__)
    try:
        await eskiz.send_sms(
            phone=phone, message=f"ULOV+ tasdiqlash kodi: {code}"
        )
    except EskizError as exc:
        log.warning("otp_sms_failed", phone=phone, error=str(exc))
    except Exception:  # noqa: BLE001
        log.exception("otp_sms_unexpected", phone=phone)


def _dev_echo(code: str) -> Optional[str]:
    """Return the OTP in the response body only in dev with OTP_DEV_ECHO=true."""
    if settings.OTP_DEV_ECHO and settings.APP_ENV != "prod":
        return code
    return None


# ---------------------------------------------------------------------------
# 1. POST /otp/request
# ---------------------------------------------------------------------------
@router.post(
    "/otp/request",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OtpRequestOut,
    summary="Send a 6-digit OTP to the phone",
)
async def otp_request(
    body: OtpRequestIn,
    redis: Redis = Depends(get_redis_otp),
) -> OtpRequestOut:
    code, ttl = await svc.request_otp(redis, body.phone)
    await _send_otp_sms(body.phone, code)
    return OtpRequestOut(status="sent", ttl_seconds=ttl, dev_code=_dev_echo(code))


# ---------------------------------------------------------------------------
# 2. POST /otp/verify — passwordless login for existing users
# ---------------------------------------------------------------------------
@router.post(
    "/otp/verify",
    response_model=TokenOut,
    summary="Verify OTP; returns tokens for an existing user",
)
async def otp_verify(
    body: OtpVerifyIn,
    response: Response,
    request: Request,
    redis: Redis = Depends(get_redis_otp),
    db: Session = Depends(get_db),
) -> TokenOut:
    await svc.verify_otp(redis, body.phone, body.code)
    user = repo.get_user_by_phone(db, body.phone)
    if user is None:
        # OTP succeeded but the phone is not registered — the frontend should
        # route the user to /register. We don't auto-create here because the
        # current UX asks for full_name + password on first registration.
        raise NotFoundError("User not found — register first", code="AUTH_USER_NOT_FOUND")
    access, refresh, ttl = svc.issue_tokens(
        db,
        sub=user.id,
        role=user.role,
        center_id=user.center_id,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, refresh)
    return _token_envelope(user, access, ttl)


# ---------------------------------------------------------------------------
# 3. POST /register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenOut,
    summary="Register a new customer and log them in",
)
def register_user(
    body: RegisterIn,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    user = svc.register(
        db,
        phone=body.phone,
        password=body.password,
        full_name=body.full_name,
        email=body.email,
        city=body.city,
    )
    access, refresh, ttl = svc.issue_tokens(
        db,
        sub=user.id,
        role=user.role,
        center_id=user.center_id,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, refresh)
    return _token_envelope(user, access, ttl)


# ---------------------------------------------------------------------------
# 5. POST /login  (row #5 in the architecture; customer phone+password)
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenOut,
    summary="Phone + password login (customer)",
)
def login(
    body: LoginIn,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    user = svc.authenticate(db, phone=body.phone, password=body.password)
    access, refresh, ttl = svc.issue_tokens(
        db,
        sub=user.id,
        role=user.role,
        center_id=user.center_id,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, refresh)
    return _token_envelope(user, access, ttl)


# ---------------------------------------------------------------------------
# 4. POST /register-center (Phase 3 onboarding)
# ---------------------------------------------------------------------------
@router.post(
    "/register-center",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenOut,
    summary="Register a new centre owner + the centre itself",
)
def register_center(
    body: RegisterCenterIn,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    user, _center = svc.register_center(
        db,
        phone=body.phone,
        password=body.password,
        full_name=body.full_name,
        center_name=body.center_name,
        center_phone=body.center_phone,
        center_address=body.center_address,
        center_services=body.center_services,
    )
    access, refresh, ttl = svc.issue_tokens(
        db,
        sub=user.id,
        role=user.role,
        center_id=user.center_id,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, refresh)
    return _token_envelope(user, access, ttl)


# ---------------------------------------------------------------------------
# 6. POST /mechanic/login (Phase 3 mechanic login)
# ---------------------------------------------------------------------------
@router.post(
    "/mechanic/login",
    response_model=TokenOut,
    summary="Login for mechanics using centre-scoped login",
)
def mechanic_login(
    body: MechanicLoginIn,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenOut:
    mechanic = svc.authenticate_mechanic(
        db, login=body.login, password=body.password
    )
    # Note: Mechanic tokens might not have a full UserOut record if they
    # don't exist in the users table. 
    # For now, we return a TokenOut with the mechanic's data.
    access, refresh, ttl = svc.issue_tokens(
        db,
        sub=mechanic.id,
        role="mechanic",
        center_id=mechanic.center_id,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, refresh)
    
    # Fake UserOut for the response envelope
    user_out = UserOut(
        id=mechanic.id,
        phone="mechanic", # Placeholder
        full_name=mechanic.full_name,
        role="mechanic",
        center_id=mechanic.center_id,
        created_at=mechanic.created_at,
    )
    
    return TokenOut(
        access_token=access,
        expires_in=ttl,
        user=user_out,
    )


# ---------------------------------------------------------------------------
# 7. POST /refresh
# ---------------------------------------------------------------------------
@router.post(
    "/refresh",
    response_model=TokenOut,
    summary="Rotate access + refresh tokens",
)
def refresh_tokens(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    refresh_cookie: Optional[str] = Cookie(
        default=None, alias=settings.REFRESH_COOKIE_NAME
    ),
) -> TokenOut:
    if not refresh_cookie:
        raise UnauthorizedError(
            "Missing refresh cookie", code="AUTH_REFRESH_MISSING"
        )
    access, new_refresh, ttl, user = svc.rotate_refresh(
        db,
        refresh_cookie,
        user_agent=_user_agent(request),
        ip=client_ip(request),
    )
    _set_refresh_cookie(response, new_refresh)
    return _token_envelope(user, access, ttl)


# ---------------------------------------------------------------------------
# 8. POST /logout
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the refresh cookie",
)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_cookie: Optional[str] = Cookie(
        default=None, alias=settings.REFRESH_COOKIE_NAME
    ),
) -> Response:
    svc.logout(db, refresh_cookie)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 9. POST /password/reset/request
# ---------------------------------------------------------------------------
@router.post(
    "/password/reset/request",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OtpRequestOut,
    summary="Send a password-reset OTP",
)
async def password_reset_request(
    body: PasswordResetRequestIn,
    redis: Redis = Depends(get_redis_otp),
    db: Session = Depends(get_db),
) -> OtpRequestOut:
    user = repo.get_user_by_phone(db, body.phone)
    if user is None:
        # Do not leak whether the phone exists — respond identically.
        return OtpRequestOut(
            status="sent",
            ttl_seconds=settings.OTP_TTL_SECONDS,
            dev_code=None,
        )
    code, ttl = await svc.request_otp(redis, body.phone)
    await _send_otp_sms(body.phone, code)
    return OtpRequestOut(status="sent", ttl_seconds=ttl, dev_code=_dev_echo(code))


# ---------------------------------------------------------------------------
# 10. POST /password/reset/confirm
# ---------------------------------------------------------------------------
@router.post(
    "/password/reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm OTP and set a new password (kills all sessions)",
)
async def password_reset_confirm(
    body: PasswordResetConfirmIn,
    redis: Redis = Depends(get_redis_otp),
    db: Session = Depends(get_db),
) -> Response:
    # Verify OTP first, then look up the user. A successful OTP for a missing
    # user is treated the same as an invalid OTP to avoid enumeration.
    user = repo.get_user_by_phone(db, body.phone)
    if user is None:
        # Consume nothing — still raise the generic error.
        raise UnauthorizedError("Invalid OTP", code="AUTH_OTP_INVALID")
    await svc.verify_otp(redis, body.phone, body.code)
    svc.reset_password(db, user=user, new_password=body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
