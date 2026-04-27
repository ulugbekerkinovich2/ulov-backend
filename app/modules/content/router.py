"""Content read endpoints — public (no auth). Admin CRUD lands in Phase 6."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, get_redis_cache, get_current_customer, get_current_user, CurrentUser
from app.modules.content import service as svc
from app.modules.content.stories_models import Story
from app.modules.content.schemas import ContentListOut, StoryOut, StoryIn
from sqlalchemy import select


def _make_kind_route(kind: str):
    """Factory — attaches one public endpoint per content kind."""

    async def _route(
        lang: str = Query(default=settings.DEFAULT_LANGUAGE, min_length=2, max_length=2),
        db: Session = Depends(get_db),
        redis: Redis = Depends(get_redis_cache),
    ) -> ContentListOut:
        items = await svc.list_pages(db, redis, kind=kind, lang=lang)
        return ContentListOut(kind=kind, lang=lang, items=items)

    return _route


router = APIRouter()
router.add_api_route(
    "/traffic-rules",
    _make_kind_route("traffic_rules"),
    methods=["GET"],
    response_model=ContentListOut,
    summary="Traffic rules (CMS-backed)",
)
router.add_api_route(
    "/road-signs",
    _make_kind_route("road_signs"),
    methods=["GET"],
    response_model=ContentListOut,
    summary="Road signs (CMS-backed)",
)
router.add_api_route(
    "/fines",
    _make_kind_route("fines"),
    methods=["GET"],
    response_model=ContentListOut,
    summary="Fines catalogue",
)
router.add_api_route(
    "/tips",
    _make_kind_route("tips"),
    methods=["GET"],
    response_model=ContentListOut,
    summary="Driving tips",
)
@router.get("/stories", response_model=List[StoryOut], summary="List active stories")
def list_stories(db: Session = Depends(get_db)) -> List[StoryOut]:
    stmt = select(Story).where(Story.is_active == True).order_by(Story.created_at.desc())
    return [StoryOut.from_orm(s) for s in db.execute(stmt).scalars()]

@router.post("/stories", response_model=StoryOut, status_code=201)
def create_story(
    body: StoryIn,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StoryOut:
    story = Story(
        center_id=user.center_id if hasattr(user, 'center_id') else None,
        title=body.title,
        image_url=body.image_url,
        content=body.content,
        discount_label=body.discount_label,
        valid_until=body.valid_until
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return StoryOut.from_orm(story)

@router.delete("/stories/{id}", status_code=204)
def delete_story(
    id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    story = db.get(Story, id)
    if not story: return
    db.delete(story)
    db.commit()

@router.post("/stories/{id}/read", status_code=204)
def mark_story_read(id: UUID):
    """Stub — usually tracks read state in Redis or a join table."""
    return
