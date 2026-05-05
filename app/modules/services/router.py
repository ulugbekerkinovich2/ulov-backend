"""Services HTTP endpoints + WebSocket hooks.

Endpoints
---------
* GET  ``/vehicles/lookup``                   — VIN/plate lookup (staff)
* POST ``/service-centers/{id}/intakes``      — convenience intake
* POST ``/service-centers/{id}/services``     — create service explicitly
* GET  ``/service-centers/{id}/services``     — queue
* GET  ``/services/{id}``                     — detail
* PATCH ``/services/{id}``                    — update items / fields
* POST ``/services/{id}/transition``          — state machine
* POST ``/services/{id}/condition-photos``    — upload metadata
* GET  ``/services/{id}/condition-photos``    — list photos
* GET  ``/services/{id}/timeline``            — transitions log
* WS   ``/ws/services/{id}``                  — customer real-time
* WS   ``/ws/centers/{id}``                   — staff queue real-time
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.events import (
    CH_SERVICE_ONE,
    CH_SERVICES,
    CH_USER,
    build_channel,
    make_event,
    publish,
    subscribe,
)
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.deps import (
    CurrentUser,
    get_current_staff,
    get_current_user,
    get_db,
    get_redis_pubsub,
)
from app.modules.cars import repository as cars_repo
from app.modules.notifications import service as notifs
from app.modules.service_centers import service as centers_svc
from app.modules.services import repository as services_repo
from app.modules.services import service as svc
from app.modules.services.schemas import (
    CarLookupOut,
    ConditionPhotoIn,
    ConditionPhotoOut,
    CustomerBookingIn,
    IntakeIn,
    ServiceCarOut,
    ServiceCreateIn,
    ServiceItemOut,
    ServiceOut,
    ServiceOwnerOut,
    ServicePatchIn,
    TransitionIn,
    TransitionOut,
    VehiclePatchIn,
)

log = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_service_out(service, items=None) -> ServiceOut:
    out = ServiceOut.from_orm(service)
    out.items = [ServiceItemOut.from_orm(i) for i in (items or [])]
    if hasattr(service, "car") and service.car:
        owner_out = None
        if hasattr(service.car, "owner") and service.car.owner:
            owner_out = ServiceOwnerOut.from_orm(service.car.owner)
        
        out.car = ServiceCarOut(
            id=service.car.id,
            brand=service.car.brand,
            model=service.car.model,
            year=service.car.year,
            plate=service.car.plate,
            color=service.car.color,
            vin=service.car.vin,
            mileage=service.car.mileage,
            owner=owner_out
        )
    
    if hasattr(service, "center") and service.center:
        out.center_name = service.center.name
    
    if hasattr(service, "mechanic") and service.mechanic:
        out.mechanic_name = service.mechanic.full_name

    return out


async def _publish_event(redis: Redis, service, *, type_: str, **payload) -> None:
    event = make_event(
        type_,
        payload={
            "service_id": str(service.id),
            "center_id": str(service.center_id),
            "status": service.status,
            **payload,
        },
        at=datetime.utcnow().isoformat() + "Z",
    )
    await publish(redis, build_channel(CH_SERVICE_ONE, service_id=service.id), event)
    await publish(redis, build_channel(CH_SERVICES, center_id=service.center_id), event)
    
    if hasattr(service, "car") and service.car and service.car.owner_id:
        await publish(redis, build_channel(CH_USER, user_id=service.car.owner_id), event)


def _notify_customer_on_transition(db: Session, service, to_status: str) -> None:
    car = cars_repo.get_by_id(db, service.car_id)
    if car is None:
        return
    titles = {
        "in_progress": ("Ish boshlandi", "Avtomobilingizda ish boshlandi."),
        "paused": ("Ish to‘xtatildi", "Avtomobilingizdagi ish vaqtincha to‘xtatildi."),
        "completed": ("Xizmat yakunlandi", "Avtomobilingiz tayyor — qabul qilib oling."),
        "cancelled": ("Xizmat bekor qilindi", "Xizmat bekor qilindi."),
    }
    if to_status not in titles:
        return
    title, body = titles[to_status]
    notifs.create_notification(
        db,
        user_id=car.owner_id,
        kind=f"service.{to_status}",
        title=title,
        body=body,
        payload={"service_id": str(service.id), "to_status": to_status},
    )


# ---------------------------------------------------------------------------
# Vehicle lookup
# ---------------------------------------------------------------------------
@router.get(
    "/vehicles/lookup",
    response_model=List[CarLookupOut],
    summary="Search vehicles by VIN, plate, owner phone, or tech-passport (staff)",
)
def vehicle_lookup(
    # VIN accepts both full (11-17 chars, exact match) and short queries
    # (4-10 chars) — service layer treats anything under 11 as a suffix
    # lookup so drivers can search by the last 4-6 characters of the VIN.
    vin: Optional[str] = Query(None, min_length=4, max_length=17),
    plate: Optional[str] = Query(None, min_length=1, max_length=20),
    phone: Optional[str] = Query(None, min_length=4, max_length=20),
    tech_passport: Optional[str] = Query(None, min_length=1, max_length=20),
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> List[CarLookupOut]:
    """Always returns a list — empty when nothing matched, multiple rows when
    a phone search hits an owner with several cars. The intake flow uses
    POST /service-centers/{id}/intakes which still expects exactly one car.
    """
    cars = svc.search_vehicles(
        db, user, vin=vin, plate=plate, phone=phone, tech_passport=tech_passport,
    )
    if not cars:
        return []

    # Resolve owner display info in one round trip rather than N queries.
    from app.modules.auth import repository as auth_repo

    owner_cache: dict = {}
    out: List[CarLookupOut] = []
    for car in cars:
        owner = owner_cache.get(car.owner_id)
        if owner is None:
            owner = auth_repo.get_user_by_id(db, car.owner_id)
            owner_cache[car.owner_id] = owner
        out.append(
            CarLookupOut(
                car_id=car.id,
                owner_id=car.owner_id,
                owner_name=owner.full_name if owner else None,
                owner_phone=owner.phone if owner else None,
                brand=car.brand,
                model=car.model,
                year=car.year,
                plate=car.plate,
                vin=car.vin,
                mileage=car.mileage,
            )
        )
    return out


@router.get(
    "/vehicles/{car_id}",
    response_model=CarLookupOut,
    summary="Get a vehicle by id with owner info (staff)",
)
def get_vehicle_detail(
    car_id: UUID,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CarLookupOut:
    """Companion to /vehicles/lookup — used by the centre admin's vehicle
    detail page to load a car that may not yet have a service in this
    centre (so it isn't in the locally-cached queue).
    """
    from app.modules.auth import repository as auth_repo

    car = cars_repo.get_by_id(db, car_id)
    if car is None:
        raise NotFoundError("Vehicle not found", code="VEHICLE_NOT_FOUND")
    owner = auth_repo.get_user_by_id(db, car.owner_id)
    return CarLookupOut(
        car_id=car.id,
        owner_id=car.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_phone=owner.phone if owner else None,
        brand=car.brand,
        model=car.model,
        year=car.year,
        plate=car.plate,
        vin=car.vin,
        mileage=car.mileage,
    )


@router.patch(
    "/vehicles/{car_id}",
    response_model=CarLookupOut,
    summary="Update a vehicle's fields (staff)",
)
def patch_vehicle(
    car_id: UUID,
    body: VehiclePatchIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> CarLookupOut:
    """Staff-side car edit. Distinct from PATCH /cars/{id} (customer) —
    that endpoint enforces ownership; this one trusts the staff role and
    can additionally update the owner's display name (handy for fixing
    typos when registering a walk-in customer). Phone changes are
    intentionally not supported here: phone is the user's lookup key and
    the customer reauth flow has to handle that.
    """
    from app.core.plate import detect_plate_type
    from app.modules.auth import repository as auth_repo
    from app.modules.users import repository as users_repo

    car = cars_repo.get_by_id(db, car_id)
    if car is None:
        raise NotFoundError("Vehicle not found", code="VEHICLE_NOT_FOUND")

    car_data = body.car_payload()
    if car_data:
        if "plate" in car_data and "plate_type" not in car_data:
            try:
                car_data["plate_type"] = detect_plate_type(car_data["plate"]).value
            except Exception:  # noqa: BLE001
                pass
        cars_repo.update_fields(db, car.id, **car_data)

    if body.owner_name is not None:
        users_repo.update_fields(db, car.owner_id, full_name=body.owner_name)

    car = cars_repo.get_by_id(db, car_id)
    owner = auth_repo.get_user_by_id(db, car.owner_id)
    return CarLookupOut(
        car_id=car.id,
        owner_id=car.owner_id,
        owner_name=owner.full_name if owner else None,
        owner_phone=owner.phone if owner else None,
        brand=car.brand,
        model=car.model,
        year=car.year,
        plate=car.plate,
        vin=car.vin,
        mileage=car.mileage,
    )


@router.get(
    "/vehicles/{car_id}/services",
    response_model=List[ServiceOut],
    summary="Vehicle service history (staff or owner)",
)
def list_vehicle_history(
    car_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ServiceOut]:
    services = svc.list_for_car(db, car_id, user, limit=limit, offset=offset)
    out: List[ServiceOut] = []
    for s in services:
        out.append(_to_service_out(s, svc.list_items(db, s.id, user)))
    return out


# ---------------------------------------------------------------------------
# Centre-scoped: queue + create + intake
# ---------------------------------------------------------------------------
@router.get(
    "/service-centers/{center_id}/services",
    response_model=List[ServiceOut],
    summary="Centre service queue (filterable)",
)
def list_center_services(
    center_id: UUID,
    status_in: Optional[List[str]] = Query(None, alias="status"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> List[ServiceOut]:
    services = svc.list_for_center(
        db,
        center_id,
        user,
        statuses=status_in,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    out: List[ServiceOut] = []
    for s in services:
        out.append(_to_service_out(s, svc.list_items(db, s.id, user)))
    return out


@router.post(
    "/service-centers/{center_id}/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a service in a centre",
)
async def create_service(
    center_id: UUID,
    body: ServiceCreateIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_pubsub),
) -> ServiceOut:
    s = svc.create(
        db,
        center_id,
        user,
        car_id=body.car_id,
        mileage_at_intake=body.mileage_at_intake,
        mechanic_id=body.mechanic_id,
        next_recommended_mileage=body.next_recommended_mileage,
        notes=body.notes,
        items=[i.dict() for i in body.items],
    )
    items = svc.list_items(db, s.id, user)
    await _publish_event(redis, s, type_="service.created")
    return _to_service_out(s, items)


@router.post(
    "/service-centers/{center_id}/intakes",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a service via VIN / plate intake",
)
async def intake(
    center_id: UUID,
    body: IntakeIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_pubsub),
) -> ServiceOut:
    car = svc.lookup_vehicle(db, user, vin=body.vin, plate=body.plate)
    s = svc.create(
        db,
        center_id,
        user,
        car_id=car.id,
        mileage_at_intake=body.mileage_at_intake,
        mechanic_id=body.mechanic_id,
        notes=body.notes,
    )
    items = svc.list_items(db, s.id, user)
    await _publish_event(redis, s, type_="service.created")
    return _to_service_out(s, items)


@router.post(
    "/service-centers/{center_id}/bookings",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Customer-side booking — request a service at a centre",
)
async def book_service(
    center_id: UUID,
    body: CustomerBookingIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_pubsub),
) -> ServiceOut:
    s = svc.book_by_customer(
        db,
        center_id,
        user,
        car_id=body.car_id,
        items=[i.dict() for i in body.items],
        notes=body.notes,
    )
    items = svc.list_items(db, s.id, user)
    await _publish_event(redis, s, type_="service.created")
    return _to_service_out(s, items)


# ---------------------------------------------------------------------------
# Single service
# ---------------------------------------------------------------------------
@router.get(
    "/my/services",
    response_model=List[ServiceOut],
    summary="List my personal service history",
)
def list_my_services(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ServiceOut]:
    services = svc.list_mine(db, user, limit=limit, offset=offset)
    out: List[ServiceOut] = []
    for s in services:
        out.append(_to_service_out(s, svc.list_items(db, s.id, user)))
    return out


@router.get("/services/{service_id}", response_model=ServiceOut, summary="Service detail")
def get_service(
    service_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServiceOut:
    s = svc.get_for_user(db, service_id, user)
    items = svc.list_items(db, s.id, user)
    return _to_service_out(s, items)


@router.patch(
    "/services/{service_id}",
    response_model=ServiceOut,
    summary="Update service items / metadata",
)
def patch_service(
    service_id: UUID,
    body: ServicePatchIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> ServiceOut:
    data = body.dict(exclude_unset=True)
    if "items" in data and data["items"] is not None:
        data["items"] = [i.dict() if hasattr(i, "dict") else i for i in data["items"]]
    s = svc.patch(db, service_id, user, data)
    items = svc.list_items(db, s.id, user)
    return _to_service_out(s, items)


@router.post(
    "/services/{service_id}/transition",
    response_model=ServiceOut,
    summary="Move the service through the state machine",
)
async def transition_service(
    service_id: UUID,
    body: TransitionIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_pubsub),
) -> ServiceOut:
    s, _t = svc.transition(
        db, service_id, user, to_status=body.to_status, reason=body.reason
    )
    _notify_customer_on_transition(db, s, body.to_status)
    items = svc.list_items(db, s.id, user)
    await _publish_event(
        redis, s, type_="service.transitioned", to_status=body.to_status
    )
    return _to_service_out(s, items)


@router.post(
    "/services/{service_id}/condition-photos",
    response_model=ConditionPhotoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a before/during/after photo URL",
)
def add_condition_photo(
    service_id: UUID,
    body: ConditionPhotoIn,
    user: CurrentUser = Depends(get_current_staff),
    db: Session = Depends(get_db),
) -> ConditionPhotoOut:
    # Resolve an upload key (from /uploads/presign) into a public URL; this
    # keeps clients ignorant of bucket layout.
    if body.key and not body.url:
        from app.modules.uploads.client import public_url_for

        url = public_url_for(body.key)
    else:
        url = body.url  # type: ignore[assignment]
    img = svc.add_condition_photo(db, service_id, user, url=url, stage=body.stage)
    return ConditionPhotoOut.from_orm(img)


@router.get(
    "/services/{service_id}/condition-photos",
    response_model=List[ConditionPhotoOut],
    summary="List condition photos",
)
def list_condition_photos(
    service_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ConditionPhotoOut]:
    s = svc.get_for_user(db, service_id, user)
    return [
        ConditionPhotoOut.from_orm(p)
        for p in services_repo.list_condition_images(db, s.id)
    ]


@router.get(
    "/services/{service_id}/timeline",
    response_model=List[TransitionOut],
    summary="Audit log of state transitions",
)
def timeline(
    service_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TransitionOut]:
    return [TransitionOut.from_orm(t) for t in svc.list_timeline(db, service_id, user)]


# ---------------------------------------------------------------------------
# WebSocket — token from query string ``?access_token=...``
# ---------------------------------------------------------------------------
def _ws_user_from_token(token: Optional[str]) -> CurrentUser:
    if not token:
        raise UnauthorizedError("Missing token", code="WS_TOKEN_MISSING")
    claims = decode_access_token(token)
    return CurrentUser(
        id=str(claims["sub"]),
        role=str(claims.get("role", "customer")),
        center_id=claims.get("center_id"),
    )


async def _ws_pump(ws: WebSocket, redis: Redis, channels: List[str]) -> None:
    """Forward published events on ``channels`` to the WebSocket client.

    The reader task ends as soon as either side hangs up: a client disconnect
    raises ``WebSocketDisconnect`` from ``receive``; a Redis error or a
    cancelled subscription terminates the consumer.
    """
    async def _consume() -> None:
        try:
            async for evt in subscribe(redis, channels):
                await ws.send_text(json.dumps(evt, default=str))
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001
            # Redis hiccup / cancellation — let the wait loop tear down.
            return

    async def _drain_inbound() -> None:
        # We don't act on inbound frames — just keep reading so a client
        # disconnect (1000, 1001 going away, etc.) surfaces here. Swallow
        # WebSocketDisconnect inside the task so it doesn't bubble up as an
        # "unhandled task exception" in the asyncio default handler.
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            return

    consumer = asyncio.create_task(_consume())
    drainer = asyncio.create_task(_drain_inbound())
    try:
        await ws.send_text(json.dumps({"type": "ws.ready", "channels": channels}))
        done, pending = await asyncio.wait(
            {consumer, drainer}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        for task in (consumer, drainer):
            if not task.done():
                task.cancel()


async def get_ws_pubsub(ws: WebSocket) -> Redis:
    """FastAPI dependency — pulls the pub-sub Redis client.

    Routes consume this via ``Depends`` so tests can override it with a
    fakeredis client (the same way HTTP routes are overridden in
    ``api_client``).
    """
    clients = getattr(ws.app.state, "redis_clients", None)
    if clients is None:
        raise RuntimeError("redis_clients not initialised on app.state")
    return clients[settings.REDIS_PUBSUB_DB]


@router.websocket("/ws/services/{service_id}")
async def ws_service(
    ws: WebSocket,
    service_id: UUID,
    access_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_ws_pubsub),
) -> None:
    try:
        user = _ws_user_from_token(access_token)
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return

    try:
        svc.get_for_user(db, service_id, user)
    except Exception:
        await ws.close(code=4403)
        return

    await ws.accept()
    await _ws_pump(
        ws,
        redis,
        [build_channel(CH_SERVICE_ONE, service_id=service_id)],
    )


@router.websocket("/ws/centers/{center_id}")
async def ws_center(
    ws: WebSocket,
    center_id: UUID,
    access_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_ws_pubsub),
) -> None:
    try:
        user = _ws_user_from_token(access_token)
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return

    try:
        centers_svc.assert_ops_access(db, center_id, user)
    except Exception:
        await ws.close(code=4403)
        return

    await ws.accept()
    await _ws_pump(
        ws,
        redis,
        [build_channel(CH_SERVICES, center_id=center_id)],
    )


@router.websocket("/ws/me")
async def ws_me(
    ws: WebSocket,
    access_token: Optional[str] = Query(None),
    redis: Redis = Depends(get_ws_pubsub),
) -> None:
    try:
        user = _ws_user_from_token(access_token)
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return

    await ws.accept()
    await _ws_pump(
        ws,
        redis,
        [build_channel(CH_USER, user_id=user.id)],
    )
