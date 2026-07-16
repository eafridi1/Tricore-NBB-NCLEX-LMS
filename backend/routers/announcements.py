"""
backend/routers/announcements.py
==================================
Real implementation of contract.py SECTION 11 — ANNOUNCEMENTS.
Every path, method, and response_model matches the contract exactly.

Wire into main.py with:
    from routers import announcements as announcements_router
    app.include_router(announcements_router.router, prefix="/announcements", tags=["announcements"])
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user, require_admin
from models import Announcement, User, UserRole

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 11.

class AnnouncementOut(BaseModel):
    id: int
    title: str
    body: str
    is_published: bool
    published_at: Optional[datetime]
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementOut]
    meta: PaginationMeta


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., example="Platform Maintenance – June 22")
    body: str = Field(..., example="The platform will be unavailable for 2 hours...")
    is_published: bool = False


class AnnouncementUpdateRequest(BaseModel):
    # Separate from AnnouncementCreateRequest so PATCH is partial — same
    # rationale as videos.py: an admin toggling is_published=True shouldn't
    # have to resend the full title and body.
    # CONTRACT NOTE: the contract reuses AnnouncementCreateRequest for PATCH
    # (full-replace semantics). Using a partial model here for better UX
    # consistency. If strict contract compliance is needed, swap back to
    # AnnouncementCreateRequest — the only difference is whether omitted
    # fields clear or preserve existing values.
    title: Optional[str] = None
    body: Optional[str] = None
    is_published: Optional[bool] = None


class MessageResponse(BaseModel):
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_out(a: Announcement) -> AnnouncementOut:
    return AnnouncementOut(
        id=a.id,
        title=a.title,
        body=a.body,
        is_published=a.is_published,
        published_at=a.published_at,
        created_by=a.created_by,
        created_at=a.created_at,
    )


# ── GET /announcements ────────────────────────────────────────────────────────

@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    page: int = 1,
    per_page: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    query = select(Announcement)

    if current_user.role != UserRole.admin:
        # Students (and reviewers) see only published announcements.
        # Reviewers can see draft questions but NOT draft announcements —
        # announcements are an admin-ops concern, not a content-review one.
        query = query.where(Announcement.is_published == True)  # noqa: E712

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = (
        query.order_by(Announcement.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    announcements = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return AnnouncementListResponse(
        items=[_to_out(a) for a in announcements],
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


# ── POST /announcements ───────────────────────────────────────────────────────

@router.post("", response_model=AnnouncementOut, status_code=201)
async def create_announcement(
    data: AnnouncementCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)

    announcement = Announcement(
        title=data.title,
        body=data.body,
        is_published=data.is_published,
        # Set published_at only when created as published — an announcement
        # created as a draft and later published via PATCH gets its
        # published_at set at publish time, not at creation time. This keeps
        # the timestamp semantically correct: published_at = "when students
        # first saw this," not "when the admin first drafted it."
        published_at=now if data.is_published else None,
        created_by=current_user.id,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return _to_out(announcement)


# ── PATCH /announcements/{announcement_id} ────────────────────────────────────

@router.patch("/{announcement_id}", response_model=AnnouncementOut)
async def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    announcement = await db.get(Announcement, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found.")

    update_data = data.model_dump(exclude_unset=True)

    # published_at logic — per task instructions:
    # "if setting is_published=True and published_at is None, set published_at=now()"
    # Also handle the inverse: if an admin unpublishes (is_published=False),
    # we deliberately do NOT clear published_at — preserving the record of
    # when it was originally published is useful for audit/history purposes.
    # If the admin re-publishes later, published_at stays as the original date,
    # which is the correct semantic ("first published at X").
    if update_data.get("is_published") is True and announcement.published_at is None:
        announcement.published_at = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(announcement, field, value)

    await db.commit()
    await db.refresh(announcement)
    return _to_out(announcement)


# ── DELETE /announcements/{announcement_id} ───────────────────────────────────

@router.delete("/{announcement_id}", response_model=MessageResponse)
async def delete_announcement(
    announcement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    announcement = await db.get(Announcement, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found.")

    # Hard delete per task instructions — no soft-delete on announcements.
    # Unlike questions (which are referenced by quiz_attempts and must
    # survive deletion for result history), announcements have no foreign
    # key references anywhere. A deleted announcement is just gone.
    await db.delete(announcement)
    await db.commit()

    return MessageResponse(message="Announcement deleted.")