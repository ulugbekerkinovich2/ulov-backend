"""Content read endpoints — public (no auth). Admin CRUD lands in Phase 6."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db, get_redis_cache, get_current_user, get_optional_user, CurrentUser
from app.modules.content import service as svc
from app.modules.content.stories_models import Story
from app.modules.content.schemas import ContentListOut, StoryOut, StoryIn
from sqlalchemy import select


# Redis namespace for "user X has read story Y". A SET keyed by user id; we
# expire it after 90 days so old reads naturally fall off and the key doesn't
# grow unbounded for accounts that get a lot of stories.
_STORIES_READ_KEY = "stories:read:{user_id}"
_STORIES_READ_TTL_SECONDS = 90 * 24 * 3600


def _stories_read_key(user_id) -> str:
    return _STORIES_READ_KEY.format(user_id=str(user_id))


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
async def list_stories(
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_cache),
    user: Optional[CurrentUser] = Depends(get_optional_user),
) -> List[StoryOut]:
    stmt = select(Story).where(Story.is_active == True).order_by(Story.created_at.desc())
    rows = list(db.execute(stmt).scalars())

    # Per-user read state. Anonymous callers always see is_read=False.
    read_ids: set = set()
    if user is not None and rows:
        try:
            members = await redis.smembers(_stories_read_key(user.id))
            read_ids = {
                m.decode() if isinstance(m, (bytes, bytearray)) else str(m)
                for m in members
            }
        except Exception:  # noqa: BLE001
            # Redis hiccup shouldn't break the rail.
            read_ids = set()

    out: List[StoryOut] = []
    for s in rows:
        item = StoryOut.from_orm(s)
        item.is_read = str(s.id) in read_ids
        out.append(item)
    return out

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
async def mark_story_read(
    id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_cache),
):
    """Mark a story as read for the calling user.

    Persisted as a Redis SET keyed by user id (so we don't need a join table
    just to track an "opened" flag). The set TTLs out after ~90 days, which
    is well past any story's relevance.
    """
    # Fast 404 — don't write read state for stories that don't exist.
    if db.get(Story, id) is None:
        return
    key = _stories_read_key(user.id)
    try:
        await redis.sadd(key, str(id))
        await redis.expire(key, _STORIES_READ_TTL_SECONDS)
    except Exception:  # noqa: BLE001
        # Best-effort — a read flag isn't worth surfacing 500s.
        pass
    return
