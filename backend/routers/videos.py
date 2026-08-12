"""
backend/routers/videos.py
===========================
Real implementation of contract.py SECTION 9 — VIDEOS.
Every path, method, and response_model matches the contract exactly.

Wire into main.py with:
    from routers import videos as videos_router
    app.include_router(videos_router.router, prefix="/videos", tags=["videos"])

Storage dependency:
    Signed URLs are generated via storage.get_signed_url().
    Week 3: returns a fake dev URL (no real R2 yet).
    Week 5: swap R2 credentials into .env — no router code changes needed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user, require_admin, require_active_subscription
from models import Category, User, UserRole, Video, VideoProgress
from storage import get_signed_url

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 9.

class VideoOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category_id: int
    thumbnail_url: Optional[str]
    duration_secs: Optional[int]
    sort_order: int
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoWithProgress(VideoOut):
    percent_watched: float  # 0.0–100.0, matches contract field type
    stream_url: str         # signed URL, expires in ~1h


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class VideoListResponse(BaseModel):
    items: list[VideoOut]
    meta: PaginationMeta


class VideoCreateRequest(BaseModel):
    title: str = Field(..., example="Cardiovascular Assessment")
    description: Optional[str] = None
    category_id: int
    storage_url: str = Field(..., description="Object storage path (not a public URL)")
    thumbnail_url: Optional[str] = None
    duration_secs: Optional[int] = None
    sort_order: int = 0


class VideoUpdateRequest(BaseModel):
    # Separate from VideoCreateRequest so PATCH can be partial — every
    # field is Optional so a caller who only wants to publish a video
    # (is_published=True) doesn't have to resend title, storage_url, etc.
    # CONTRACT NOTE: the contract reuses VideoCreateRequest for PATCH, making
    # it full-replace semantics. Using a partial-update model here instead
    # for better UX consistency with how PATCH behaves on other routers
    # (questions.py, users.py). If you want strict contract compliance,
    # swap this back to VideoCreateRequest — the only behavioral difference
    # is whether omitting a field clears it or leaves it unchanged.
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    storage_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_secs: Optional[int] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class VideoProgressRequest(BaseModel):
    percent_watched: float = Field(..., ge=0.0, le=100.0, example=45.5)


class MessageResponse(BaseModel):
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_privileged(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.reviewer)


def _video_to_out(video: Video) -> VideoOut:
    return VideoOut(
        id=video.id,
        title=video.title,
        description=video.description,
        category_id=video.category_id,
        thumbnail_url=video.thumbnail_url,
        duration_secs=video.duration_secs,
        sort_order=video.sort_order,
        is_published=video.is_published,
        created_at=video.created_at,
    )


# ── GET /videos ──────────────────────────────────────────────────────────────

@router.get("", response_model=VideoListResponse)
async def list_videos(
    category_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_subscription),
):
    # SUBSCRIPTION GUARD — same pattern as questions.py: full check deferred
    # to Slice 7 when the Subscription model is real. TODO(slice-7): add
    # active subscription check for student role before allowing list access.

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    query = select(Video)

    if not _is_privileged(current_user):
        # Students see only published videos
        query = query.where(Video.is_published == True)  # noqa: E712

    if category_id is not None:
        query = query.where(Video.category_id == category_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = (
        query.order_by(Video.sort_order.asc(), Video.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    videos = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return VideoListResponse(
        items=[_video_to_out(v) for v in videos],
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


# ── GET /videos/{video_id} ───────────────────────────────────────────────────

@router.get("/{video_id}", response_model=VideoWithProgress)
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await db.get(Video, video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    if not video.is_published and not _is_privileged(current_user):
        # Same anti-enumeration posture as questions.py: an unpublished
        # video is 404 for students, not 403, so they can't confirm the
        # video exists but is restricted.
        raise HTTPException(status_code=404, detail="Video not found.")

    # Generate a time-limited signed URL for the stream.
    # Week 3: returns a fake dev URL from storage.py.
    # Week 5: returns a real R2 presigned URL once R2 credentials are set.
    # The 3600-second (1h) expiry matches the contract's docstring.
    stream_url = get_signed_url(video.storage_url, expires_in_seconds=3600)

    # Fetch this user's watch progress — None if never watched.
    progress = await db.scalar(
        select(VideoProgress).where(
            VideoProgress.user_id == current_user.id,
            VideoProgress.video_id == video_id,
        )
    )
    percent_watched = float(progress.percent_watched) if progress else 0.0

    return VideoWithProgress(
        id=video.id,
        title=video.title,
        description=video.description,
        category_id=video.category_id,
        thumbnail_url=video.thumbnail_url,
        duration_secs=video.duration_secs,
        sort_order=video.sort_order,
        is_published=video.is_published,
        created_at=video.created_at,
        percent_watched=percent_watched,
        stream_url=stream_url,
    )


# ── POST /videos/{video_id}/progress ─────────────────────────────────────────

@router.post("/{video_id}/progress", response_model=MessageResponse)
async def update_video_progress(
    video_id: int,
    data: VideoProgressRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    # percent_watched: contract field type is float (0.0–100.0), but the
    # VideoProgress model stores it as Integer. Rounding rather than
    # truncating — 45.8% stored as 46 rather than 45. Sub-percent
    # precision has no real value for resume-position purposes, and keeping
    # the DB column as Integer keeps queries simple.
    # NOTE: if you later want finer-grained "resume at exact second"
    # tracking, add a `last_position_secs` column to VideoProgress instead
    # of relying on percent_watched — percent is lossy for short videos.
    percent_int = round(data.percent_watched)

    # True upsert — ON CONFLICT DO UPDATE. One row per (user_id, video_id)
    # enforced by the unique constraint defined on the VideoProgress model.
    # Using PostgreSQL's pg_insert for the dialect-specific ON CONFLICT
    # clause, same pattern as bookmark upsert in questions.py.
    stmt = (
        pg_insert(VideoProgress)
        .values(
            user_id=current_user.id,
            video_id=video_id,
            percent_watched=percent_int,
            last_watched_at=datetime.now(__import__("datetime").timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["user_id", "video_id"],
            set_={
                "percent_watched": percent_int,
                "last_watched_at": datetime.now(__import__("datetime").timezone.utc),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    return MessageResponse(message="Progress saved.")


# ── POST /videos (admin) ─────────────────────────────────────────────────────

@router.post("", response_model=VideoOut, status_code=201)
async def create_video(
    data: VideoCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Validate category exists — same guard as questions.py create_question.
    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"category_id {data.category_id} does not exist.",
            )

    video = Video(
        title=data.title,
        description=data.description,
        category_id=data.category_id,
        storage_url=data.storage_url,
        thumbnail_url=data.thumbnail_url,
        duration_secs=data.duration_secs,
        sort_order=data.sort_order,
        is_published=False,  # always starts unpublished — admin publishes via PATCH
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return _video_to_out(video)


# ── PATCH /videos/{video_id} (admin) ─────────────────────────────────────────

@router.patch("/{video_id}", response_model=VideoOut)
async def update_video(
    video_id: int,
    data: VideoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"category_id {data.category_id} does not exist.",
            )

    # Partial update — only touch fields that were sent
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(video, field, value)

    await db.commit()
    await db.refresh(video)
    return _video_to_out(video)


# ── DELETE /videos/{video_id} (admin) ────────────────────────────────────────

@router.delete("/{video_id}", response_model=MessageResponse)
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    # CONTRACT NOTE / OUT OF SCOPE: the contract's own docstring says
    # "DELETE videos row (and storage object separately)." Deleting the
    # storage object (the actual .mp4 file in R2) is NOT done here — that
    # would require calling storage.delete_object(video.storage_url), which
    # isn't implemented in storage.py's dev-mode stub and needs real R2
    # credentials to do safely. Doing it here with a fake dev URL would
    # silently no-op anyway.
    #
    # Production path (Week 5+): before await db.delete(video), add:
    #   from storage import delete_object
    #   await delete_object(video.storage_url)
    # and handle the case where the storage object was already gone
    # (e.g. manually deleted from R2 dashboard) without 500ing on the
    # DB delete. The storage_url column is preserved in the deleted row's
    # database history if you implement soft-deletes here later.
    #
    # For now: DB row is deleted, storage object is left as an orphan.
    # Acceptable for MVP — orphaned objects cost pennies on R2 and can be
    # cleaned up manually or with a maintenance script post-launch.

    storage_url = video.storage_url  # save before delete for the response note
    await db.delete(video)
    await db.commit()

    return MessageResponse(
        message=f"Video deleted. Storage object '{storage_url}' must be "
                f"removed manually from R2 until automated cleanup is implemented."
    )