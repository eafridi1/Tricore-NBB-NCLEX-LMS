"""
backend/routers/bookmarks.py
==============================
Real implementation of contract.py SECTION 7 — BOOKMARKS.
Single endpoint: GET /bookmarks

Prefix is /bookmarks — not /questions/bookmarks.
The bookmark toggle endpoints (POST/DELETE /questions/{id}/bookmark)
are in routers/questions.py, which is the correct location per the
contract's own section split. This file only owns the list endpoint.

Wire into main.py with:
    from routers import bookmarks as bookmarks_router
    app.include_router(bookmarks_router.router, prefix="/bookmarks", tags=["bookmarks"])
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user
from models import Bookmark, Question, User
from typing import Any  # for the options JSONB

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 7.
# BookmarkOut only exposes id, question_id, created_at — the contract does
# NOT include the full question payload here (stem, options, etc.) even
# though the question is joined to apply the soft-delete filter. The join
# is purely for filtering, not for projecting additional fields.
# If a future screen needs richer bookmark cards (stem preview, category,
# difficulty) that's a contract addition, not something to silently add here.

class BookmarkOut(BaseModel):
    id: int
    question_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class BookmarkListResponse(BaseModel):
    items: list[BookmarkOut]
    meta: PaginationMeta

# ── Bookmarks review (hydrated with question content) ─────────────────────────
class BookmarkedQuestion(BaseModel):
    bookmark_id: int
    question_id: int
    created_at: datetime
    stem: str
    options: list[Any]
    category_id: int | None
    difficulty: str
    correct_answer: int
    rationale: str

    model_config = {"from_attributes": True}


class BookmarkReviewResponse(BaseModel):
    items: list[BookmarkedQuestion]
    meta: PaginationMeta


@router.get("/review", response_model=BookmarkReviewResponse)
async def review_bookmarks(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The student's bookmarked questions, hydrated with full question content
    including the correct answer and rationale. This is a REVIEW/study context
    (own saved questions, post-quiz) — unlike the live quiz endpoints, answers
    are intentionally included here so students can study what they saved.
    """
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    base_query = (
        select(Bookmark, Question)
        .join(Question, Question.id == Bookmark.question_id)
        .where(
            Bookmark.user_id == current_user.id,
            Question.is_deleted == False,  # noqa: E712
        )
    )

    count_q = select(func.count()).select_from(
        select(Bookmark.id)
        .join(Question, Question.id == Bookmark.question_id)
        .where(
            Bookmark.user_id == current_user.id,
            Question.is_deleted == False,  # noqa: E712
        )
        .subquery()
    )
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(
        base_query
        .order_by(Bookmark.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()  # list of (Bookmark, Question) tuples

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    items = [
        BookmarkedQuestion(
            bookmark_id=bm.id,
            question_id=q.id,
            created_at=bm.created_at,
            stem=q.stem,
            options=q.options,
            category_id=q.category_id,
            difficulty=q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty),
            correct_answer=q.correct_answer,
            rationale=q.rationale,
        )
        for bm, q in rows
    ]

    return BookmarkReviewResponse(
        items=items,
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


# ── Route ────────────────────────────────────────────────────────────────────

@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    # Base query: own bookmarks only, joined to Question for the soft-delete
    # filter. Using an inner join (not outer) so a bookmark whose question
    # has been hard-deleted (edge case — should never happen with soft-delete
    # discipline, but defensible) also drops out rather than crashing the
    # serializer on a null question_id resolution.
    base_query = (
        select(Bookmark)
        .join(Question, Question.id == Bookmark.question_id)
        .where(
            Bookmark.user_id == current_user.id,
            Question.is_deleted == False,  # noqa: E712
        )
    )

    # Count total matching rows before pagination.
    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Ordered by most-recently-bookmarked first — consistent with the quiz
    # history and login-history list endpoints (newest first), and what a
    # student reviewing saved questions would naturally expect.
    result = await db.execute(
        base_query
        .order_by(Bookmark.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    bookmarks = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return BookmarkListResponse(
        items=[
            BookmarkOut(
                id=bm.id,
                question_id=bm.question_id,
                created_at=bm.created_at,
            )
            for bm in bookmarks
        ],
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )