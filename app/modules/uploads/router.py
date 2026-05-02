"""Upload endpoints — presign + confirm + server-side direct upload."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_db
from app.modules.uploads import service as svc
from app.modules.uploads.schemas import (
    ConfirmIn,
    ConfirmOut,
    ConfirmOut as DirectUploadOut,
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


@router.post(
    "",
    response_model=DirectUploadOut,
    summary="Upload a file directly through the API (server-side proxy to S3/R2)",
)
def direct_upload(
    file: UploadFile = File(...),
    kind: str = Form(...),
    entity_id: Optional[UUID] = Form(None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectUploadOut:
    """Single-shot upload — the browser sends the file to us, we forward it to
    object storage and (optionally) write the resulting URL to the owning row.

    Useful when the browser can't talk to R2 directly (CORS, restricted
    networks). The presign + confirm pair remains for clients that prefer the
    direct-to-bucket path.
    """
    public_url, eid = svc.upload_direct(
        db,
        user,
        kind=kind,
        file=file,
        entity_id=entity_id,
    )
    return DirectUploadOut(kind=kind, public_url=public_url, entity_id=eid)
