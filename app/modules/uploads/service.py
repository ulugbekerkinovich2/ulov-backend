"""Upload domain logic.

Two-step flow:
  1. Client calls ``POST /uploads/presign`` with the kind and content type.
     We mint a presigned PUT URL pointing at S3/R2.
  2. Client uploads the bytes directly to that URL.
  3. Client calls ``POST /uploads/confirm`` with the returned key. We record
     the public URL on the relevant entity (avatar / car photo / centre avatar).

Keys are namespaced by kind + owner id + uuid so two uploads never collide.
"""

from __future__ import annotations

import mimetypes
import uuid
from typing import Dict, Optional, Tuple, Union
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.deps import CurrentUser
from app.modules.cars import repository as cars_repo
from app.modules.service_centers import repository as centers_repo
from app.modules.service_centers import service as centers_svc
from app.modules.uploads.client import get_s3_client, public_url_for
from app.modules.uploads.schemas import ALLOWED_CONTENT_TYPES, UPLOAD_KINDS
from app.modules.users import repository as users_repo

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Authorization — who can upload what
# ---------------------------------------------------------------------------
def _ext_for(content_type: str, filename: Optional[str]) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()[:8]
    ext = mimetypes.guess_extension(content_type) or ".bin"
    return ext.lstrip(".")


def _key_for(
    kind: str, user: CurrentUser, *, entity_id: Optional[UUIDLike], ext: str
) -> str:
    # Draft car_photo uploads (no entity_id yet) live under the user's namespace
    # so they're trivially attributable and easy to garbage-collect later.
    car_photo_scope = str(entity_id) if entity_id else f"_drafts/{user.id}"
    parts = {
        "avatar": ("avatars", str(user.id)),
        "car_photo": ("cars", car_photo_scope),
        "center_avatar": ("centers", str(entity_id or uuid.uuid4())),
        "center_gallery": ("centers", str(entity_id or uuid.uuid4()) + "/gallery"),
        "service_photo": ("services", str(entity_id or uuid.uuid4())),
        # Stories / posts published by a centre. Just stash under
        # centers/{id}/stories — the caller chains POST /content/stories
        # with the returned public_url, no DB write happens here.
        "story_image": ("centers", str(entity_id or uuid.uuid4()) + "/stories"),
    }[kind]
    return f"{parts[0]}/{parts[1]}/{uuid.uuid4().hex}.{ext}"


def _assert_can_upload(
    db: Session,
    kind: str,
    user: CurrentUser,
    entity_id: Optional[UUIDLike],
) -> None:
    if kind == "avatar":
        # Anyone may upload their own avatar.
        return
    if kind == "car_photo":
        # Two valid modes:
        #   * entity_id set     → editing an existing car; verify ownership
        #     and write photo_url on confirm.
        #   * entity_id is None → "draft" upload before the car row exists;
        #     the client includes the returned public_url in POST /cars.
        if entity_id is None:
            return
        car = cars_repo.get_by_id(db, entity_id)
        if car is None:
            raise NotFoundError("Car not found", code="CAR_NOT_FOUND")
        if str(car.owner_id) != str(user.id) and user.role != "admin":
            raise ForbiddenError("Not your car", code="CAR_NOT_OWNER")
        return
    if kind in ("center_avatar", "center_gallery"):
        if entity_id is None:
            raise ValidationError(
                "entity_id required for centre photos", code="UPLOAD_ENTITY_REQUIRED"
            )
        center = centers_repo.get_by_id(db, entity_id)
        if center is None:
            raise NotFoundError("Centre not found", code="CENTER_NOT_FOUND")
        if user.role == "admin":
            return
        if str(center.owner_user_id) != str(user.id):
            raise ForbiddenError("Not your centre", code="CENTER_NOT_OWNER")
        return
    if kind == "service_photo":
        # Authorisation is enforced where the URL is later attached
        # (service-photo creation endpoint). Here we only require staff.
        if user.role not in {"mechanic", "owner", "admin"}:
            raise ForbiddenError("Staff only", code="UPLOAD_STAFF_ONLY")
        return
    if kind == "story_image":
        # Stories are owned by a centre — only the centre's owner (or an
        # admin) may publish them.
        if entity_id is None:
            raise ValidationError(
                "entity_id required for story photos", code="UPLOAD_ENTITY_REQUIRED"
            )
        center = centers_repo.get_by_id(db, entity_id)
        if center is None:
            raise NotFoundError("Centre not found", code="CENTER_NOT_FOUND")
        if user.role == "admin":
            return
        if str(center.owner_user_id) != str(user.id):
            raise ForbiddenError("Not your centre", code="CENTER_NOT_OWNER")
        return
    raise ValidationError("unsupported kind", code="UPLOAD_KIND_INVALID")


# ---------------------------------------------------------------------------
# Presign + confirm
# ---------------------------------------------------------------------------
def presign_put(
    db: Session,
    user: CurrentUser,
    *,
    kind: str,
    content_type: str,
    size_bytes: int,
    filename: Optional[str],
    entity_id: Optional[UUIDLike],
) -> Tuple[str, Dict[str, str], str, int]:
    ct = content_type.lower()
    if ct not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            "content_type not allowed", code="UPLOAD_CONTENT_TYPE_INVALID"
        )
    # Videos are only meaningful for story posts. Everything else (avatars,
    # car / centre / service photos) must stay image-only.
    if ct.startswith("video/") and kind != "story_image":
        raise ValidationError(
            "video uploads are only allowed for stories",
            code="UPLOAD_CONTENT_TYPE_INVALID",
        )
    if size_bytes > settings.S3_MAX_UPLOAD_BYTES:
        raise ValidationError(
            "file too large",
            code="UPLOAD_TOO_LARGE",
            details={"max_bytes": settings.S3_MAX_UPLOAD_BYTES},
        )
    _assert_can_upload(db, kind, user, entity_id)

    ext = _ext_for(content_type, filename)
    key = _key_for(kind, user, entity_id=entity_id, ext=ext)
    s3 = get_s3_client()
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.S3_PRESIGN_EXPIRES_SECONDS,
    )
    headers = {"Content-Type": content_type}
    log.info(
        "upload_presigned",
        kind=kind,
        user_id=str(user.id),
        key=key,
        size=size_bytes,
    )
    return url, headers, key, settings.S3_PRESIGN_EXPIRES_SECONDS


def confirm(
    db: Session,
    user: CurrentUser,
    *,
    kind: str,
    key: str,
    entity_id: Optional[UUIDLike],
) -> Tuple[str, Optional[UUIDLike]]:
    """Persist the uploaded URL onto the relevant entity.

    Returns ``(public_url, entity_id)``. For ``service_photo`` we don't write
    to a DB row here (the services router does that via
    ``POST /services/{id}/condition-photos`` to also stamp the stage).
    """
    _assert_can_upload(db, kind, user, entity_id)
    public = public_url_for(key)

    if kind == "avatar":
        users_repo.update_fields(db, user.id, avatar_url=public)
    elif kind == "car_photo":
        # Draft upload (no car yet) — caller will include public_url in
        # POST /cars. We only return the URL.
        if entity_id is not None:
            cars_repo.update_fields(db, entity_id, photo_url=public)
    elif kind == "center_avatar":
        centers_repo.update_fields(db, entity_id, avatar_url=public)
    elif kind == "center_gallery":
        # Append to gallery_urls (capped at 5). The centre row is fetched fresh
        # so we don't clobber concurrent additions.
        center = centers_repo.get_by_id(db, entity_id)
        existing = list(center.gallery_urls or [])
        if public not in existing:
            existing.append(public)
            existing = existing[-5:]
            centers_repo.update_fields(db, entity_id, gallery_urls=existing)
    # service_photo: caller chains POST /services/{id}/condition-photos.

    log.info(
        "upload_confirmed", kind=kind, user_id=str(user.id), key=key
    )
    return public, entity_id


# ---------------------------------------------------------------------------
# Server-side direct upload (browser → API → S3)
# ---------------------------------------------------------------------------
def upload_direct(
    db: Session,
    user: CurrentUser,
    *,
    kind: str,
    file: UploadFile,
    entity_id: Optional[UUIDLike],
) -> Tuple[str, Optional[UUIDLike]]:
    """Stream a multipart file to S3/R2 from the API.

    Used when the browser can't reach object storage directly (CORS,
    captive networks, etc). Validates type/size, uploads, and applies the
    same DB write that ``confirm`` would.
    """
    if kind not in UPLOAD_KINDS:
        raise ValidationError("unsupported kind", code="UPLOAD_KIND_INVALID")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            "content_type not allowed", code="UPLOAD_CONTENT_TYPE_INVALID"
        )

    _assert_can_upload(db, kind, user, entity_id)

    ext = _ext_for(content_type, file.filename)
    key = _key_for(kind, user, entity_id=entity_id, ext=ext)

    body = file.file.read()
    size_bytes = len(body)
    if size_bytes <= 0:
        raise ValidationError("empty upload", code="UPLOAD_EMPTY")
    if size_bytes > settings.S3_MAX_UPLOAD_BYTES:
        raise ValidationError(
            "file too large",
            code="UPLOAD_TOO_LARGE",
            details={"max_bytes": settings.S3_MAX_UPLOAD_BYTES},
        )

    s3 = get_s3_client()
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )

    public = public_url_for(key)

    if kind == "avatar":
        users_repo.update_fields(db, user.id, avatar_url=public)
    elif kind == "car_photo" and entity_id is not None:
        cars_repo.update_fields(db, entity_id, photo_url=public)
    elif kind == "center_avatar":
        centers_repo.update_fields(db, entity_id, avatar_url=public)
    elif kind == "center_gallery":
        center = centers_repo.get_by_id(db, entity_id)
        existing = list(center.gallery_urls or [])
        if public not in existing:
            existing.append(public)
            existing = existing[-5:]
            centers_repo.update_fields(db, entity_id, gallery_urls=existing)
    # service_photo / draft car_photo: no DB write here.

    log.info(
        "upload_direct",
        kind=kind,
        user_id=str(user.id),
        key=key,
        size=size_bytes,
    )
    return public, entity_id
