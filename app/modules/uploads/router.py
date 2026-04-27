"""Upload endpoints — presign + confirm."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_db
from app.modules.uploads import service as svc
from app.modules.uploads.schemas import (
    ConfirmIn,
    ConfirmOut,
    PresignIn,
    PresignOut,
)

router = APIRouter()


@router.post(
    "/presign",
    response_model=PresignOut,
    summary="Mint a presigned PUT URL for direct upload to object storage",
)
def presign_upload(
    body: PresignIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresignOut:
    url, headers, key, expires = svc.presign_put(
        db,
        user,
        kind=body.kind,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        filename=body.filename,
        entity_id=body.entity_id,
    )
    from app.modules.uploads.client import public_url_for

    return PresignOut(
        upload_url=url,
        headers=headers,
        key=key,
        public_url=public_url_for(key),
        expires_in=expires,
    )


@router.post(
    "/confirm",
    response_model=ConfirmOut,
    summary="Persist the uploaded URL onto the owning entity",
)
def confirm_upload(
    body: ConfirmIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfirmOut:
    url, entity_id = svc.confirm(
        db, user, kind=body.kind, key=body.key, entity_id=body.entity_id
    )
    return ConfirmOut(kind=body.kind, public_url=url, entity_id=entity_id)
