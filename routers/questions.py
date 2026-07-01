"""
backend/routers/questions.py
==============================
Real implementation of contract.py SECTION 6 — QUESTIONS.
Every path, method, and response_model below matches the contract exactly.

Wire into main.py with:
    from routers import questions as questions_router
    app.include_router(questions_router.router, prefix="/questions", tags=["questions"])
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user, require_admin_or_reviewer
from models import Bookmark, Category, Difficulty, Question, QStatus, User, UserRole

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 6.

class QuestionOption(BaseModel):
    text: str = Field(..., example="Administer oxygen immediately")


class QuestionOut(BaseModel):
    id: int
    stem: str
    options: list[QuestionOption]
    correct_answer: Optional[int]
    rationale: Optional[str]
    category_id: int
    nclex_domain: str
    difficulty: Difficulty
    status: QStatus
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class QuestionListResponse(BaseModel):
    items: list[QuestionOut]
    meta: PaginationMeta


class QuestionCreateRequest(BaseModel):
    stem: str = Field(..., example="A nurse is caring for a patient...")
    options: list[QuestionOption] = Field(..., min_length=4, max_length=4)
    correct_answer: int = Field(..., ge=0, le=3, example=1)
    rationale: str = Field(..., example="Option B is correct because...")
    category_id: int = Field(..., example=1)
    nclex_domain: str = Field(..., example="Safe and Effective Care Environment")
    difficulty: Difficulty = Field(..., example=Difficulty.medium)


class QuestionUpdateRequest(BaseModel):
    stem: Optional[str] = None
    options: Optional[list[QuestionOption]] = None
    correct_answer: Optional[int] = Field(None, ge=0, le=3)
    rationale: Optional[str] = None
    category_id: Optional[int] = None
    nclex_domain: Optional[str] = None
    difficulty: Optional[Difficulty] = None


class QuestionStatusUpdateRequest(BaseModel):
    status: QStatus = Field(..., description="Target workflow state.")


class BulkImportResponse(BaseModel):
    imported: int
    errors: list[dict[str, Any]]


class MessageResponse(BaseModel):
    message: str


# ── Workflow transition rules ───────────────────────────────────────────────
# Per contract docstring: "draft→in_review, in_review→published,
# published→archived." Modeled as an explicit allow-list rather than
# inferring from enum order, since enum order isn't guaranteed to encode
# workflow adjacency and a future status added to the enum (e.g. "rejected")
# shouldn't silently become a valid transition just by being adjacent.
#
# NOTE: contract.py's own docstring doesn't mention in_review→draft
# ("send back for revision"), but the original stubbed Week 1 task list
# (Task 3.3-equivalent for questions, referenced in your Feature Breakdown
# doc's Slice 6) explicitly calls for a "Send Back" admin action. Adding
# in_review→draft here to support that — flagging since it's not literally
# in this contract section's docstring, only implied by adjacent project
# docs. If that's not wanted, delete the in_review: {"draft", ...} entry
# below and in_review→draft will correctly 400.
VALID_TRANSITIONS: dict[QStatus, set[QStatus]] = {
    QStatus.draft: {QStatus.in_review},
    QStatus.in_review: {QStatus.published, QStatus.draft},  # draft = send-back
    QStatus.published: {QStatus.archived},
    QStatus.archived: set(),  # terminal state, no transitions out
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_question_out(q: Question, strip_answer: bool) -> QuestionOut:
    """
    Single conversion point from ORM row to response model, with the
    role-based stripping applied here rather than scattered across routes.
    options is stored as JSONB list[dict] in the DB — reconstructing it
    into QuestionOption objects rather than trusting Pydantic to coerce
    raw dicts, since the JSONB shape isn't guaranteed to exactly match the
    Pydantic field names if the DB content predates a schema change.
    """
    options = [QuestionOption(text=opt["text"]) for opt in q.options]
    return QuestionOut(
        id=q.id,
        stem=q.stem,
        options=options,
        correct_answer=None if strip_answer else q.correct_answer,
        rationale=None if strip_answer else q.rationale,
        category_id=q.category_id,
        nclex_domain=q.nclex_domain,
        difficulty=q.difficulty,
        status=q.status,
        reviewed_by=q.reviewed_by,
        reviewed_at=q.reviewed_at,
        created_by=q.created_by,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


def _is_privileged(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.reviewer)


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("", response_model=QuestionListResponse)
async def list_questions(
    category_id: Optional[int] = None,
    difficulty: Optional[Difficulty] = None,
    status: Optional[QStatus] = None,
    nclex_domain: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # SUBSCRIPTION GUARD — per Task instructions, full subscription check
    # comes in Slice 7. Leaving an explicit TODO marker (not a silent
    # no-op) so this isn't forgotten once /subscriptions/check exists for
    # real. The shape this needs to become:
    #
    #   if current_user.role == UserRole.student:
    #       sub = await db.scalar(
    #           select(Subscription).where(
    #               Subscription.user_id == current_user.id,
    #               Subscription.status == "active",
    #               Subscription.end_date > datetime.now(timezone.utc),
    #           )
    #       )
    #       if not sub:
    #           raise HTTPException(status_code=403, detail="subscription_required")
    #
    # TODO(slice-7): wire real subscription check once Subscription model exists.

    privileged = _is_privileged(current_user)

    # is_deleted filter applies unconditionally, per Task instructions —
    # this is not role-gated. A soft-deleted question never appears in any
    # list response, admin included.
    query = select(Question).where(Question.is_deleted == False)  # noqa: E712

    if privileged:
        # Admins/reviewers see all statuses by default, but an explicit
        # ?status= filter still narrows further if provided.
        if status is not None:
            query = query.where(Question.status == status)
    else:
        # Students always locked to published, regardless of any ?status=
        # query param they might pass — ignoring rather than rejecting it,
        # since a student passing ?status=draft "by mistake" (e.g. copying
        # an admin's URL) should just see published results, not a 403.
        query = query.where(Question.status == QStatus.published)

    if category_id is not None:
        query = query.where(Question.category_id == category_id)
    if difficulty is not None:
        query = query.where(Question.difficulty == difficulty)
    if nclex_domain is not None:
        query = query.where(Question.nclex_domain == nclex_domain)

    # Count total matching rows before applying pagination, for meta.total.
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    page = max(1, page)
    per_page = max(1, min(per_page, 100))  # hard ceiling — contract doesn't
    # specify a max, but an unbounded per_page lets a caller request
    # per_page=999999 and pull the entire table in one response. 100 is a
    # reasonable ceiling for question lists; revisit if a real screen needs
    # more (unlikely — UI paginates well below this).

    query = query.order_by(Question.id).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    questions = result.scalars().all()

    strip_answer = not privileged
    items = [_to_question_out(q, strip_answer) for q in questions]

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return QuestionListResponse(
        items=items,
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


@router.post("", response_model=QuestionOut, status_code=201)
async def create_question(
    data: QuestionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_reviewer),
):
    category = await db.get(Category, data.category_id)
    if not category:
        raise HTTPException(
            status_code=400, detail=f"category_id {data.category_id} does not exist."
        )

    question = Question(
        stem=data.stem,
        options=[opt.model_dump() for opt in data.options],
        correct_answer=data.correct_answer,
        rationale=data.rationale,
        category_id=data.category_id,
        nclex_domain=data.nclex_domain,
        difficulty=data.difficulty,
        status=QStatus.draft,
        created_by=current_user.id,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    # Creator always sees the full question they just made, regardless of
    # role — no point stripping correct_answer from someone who just typed
    # it in.
    return _to_question_out(question, strip_answer=False)


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = await db.get(Question, question_id)

    # is_deleted check is a 404, not a filtered-out list item, since this
    # is a direct single-resource lookup. Per Task instructions: "never
    # appear in any list or detail response" — detail response here means
    # returning 404 rather than a question payload with is_deleted=true
    # leaking through, which the contract's QuestionOut shape doesn't even
    # have a field for anyway.
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found.")

    privileged = _is_privileged(current_user)

    if not privileged and question.status != QStatus.published:
        # A student hitting a draft/in_review/archived question's ID
        # directly (e.g. guessed sequential ID) gets the same 404 as a
        # genuinely missing question — not a 403, which would confirm the
        # ID exists but is restricted. Matches the anti-enumeration posture
        # used elsewhere in this project (auth.py's forgot-password, etc.).
        raise HTTPException(status_code=404, detail="Question not found.")

    return _to_question_out(question, strip_answer=not privileged)


@router.patch("/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: int,
    data: QuestionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_reviewer),
):
    question = await db.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found.")

    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category:
            raise HTTPException(
                status_code=400, detail=f"category_id {data.category_id} does not exist."
            )

    # Apply only the fields that were actually provided — this IS a true
    # partial update (unlike categories.py's PATCH, which reuses the
    # create shape). QuestionUpdateRequest gives every field its own
    # Optional, so None here genuinely means "not provided," not "clear
    # this field." exclude_unset relies on the caller not sending an
    # explicit `null` for a field they want left alone vs. one they
    # genuinely didn't include — standard Pydantic partial-update pattern.
    update_data = data.model_dump(exclude_unset=True)

    if "options" in update_data:
        update_data["options"] = [opt for opt in update_data["options"]]
        # already plain dicts after model_dump(), JSONB column accepts as-is

    was_published = question.status == QStatus.published

    for field, value in update_data.items():
        setattr(question, field, value)

    # Per contract docstring: "Editing a published question sets status
    # back to in_review." Only triggers if it WAS published before this
    # edit — editing a draft or in_review question doesn't need to reset
    # anything, it's already in a pre-publish state.
    if was_published:
        question.status = QStatus.in_review
        question.reviewed_by = None
        question.reviewed_at = None

    question.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(question)

    return _to_question_out(question, strip_answer=False)


@router.patch("/{question_id}/status", response_model=QuestionOut)
async def update_question_status(
    question_id: int,
    data: QuestionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_reviewer),
):
    question = await db.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found.")

    allowed = VALID_TRANSITIONS.get(question.status, set())
    if data.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_transition",
                "current_status": question.status.value,
                "requested_status": data.status.value,
                "allowed": [s.value for s in allowed],
            },
        )

    question.status = data.status

    if data.status == QStatus.published:
        question.reviewed_by = current_user.id
        question.reviewed_at = datetime.now(timezone.utc)
    elif data.status == QStatus.draft:
        # Send-back path — clear any prior review marks so a re-submission
        # doesn't carry a stale reviewed_by/reviewed_at from a previous
        # round that got sent back.
        question.reviewed_by = None
        question.reviewed_at = None

    question.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(question)

    return _to_question_out(question, strip_answer=False)


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_questions(
    current_user: User = Depends(require_admin_or_reviewer),
):
    # NOT IMPLEMENTED — out of scope for this task. The Week 2 Feature
    # Breakdown doc lists this under Slice 6 (Admin Panel), not Slice 2
    # (Question Bank), with its own dedicated Claude prompt covering CSV
    # parsing, row-level validation, and all-or-nothing batch insert
    # semantics. Implementing a half version here (e.g. accepting a file
    # upload but not actually validating rows) would be worse than leaving
    # this honestly unimplemented, since a silently-incomplete bulk import
    # endpoint is a way to lose admin-submitted question data.
    #
    # Kept here only so the route exists and 404s correctly distinguish
    # from a routing error vs. genuinely not-built-yet — matches contract's
    # path/response_model exactly, just doesn't do the work.
    raise HTTPException(
        status_code=501,
        detail="Bulk import is implemented in Slice 6 (Admin Panel), not yet available.",
    )


@router.post("/{question_id}/bookmark", response_model=MessageResponse)
async def bookmark_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = await db.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found.")

    # True upsert via Postgres-specific ON CONFLICT DO NOTHING, matching
    # the contract docstring's explicit instruction. Using the dialect-
    # specific insert() rather than a SELECT-then-INSERT pattern avoids a
    # race condition where two rapid double-clicks both pass the SELECT
    # check before either INSERT commits, which would violate the unique
    # constraint on a plain insert and 500 instead of being truly
    # idempotent.
    stmt = (
        pg_insert(Bookmark)
        .values(user_id=current_user.id, question_id=question_id)
        .on_conflict_do_nothing(index_elements=["user_id", "question_id"])
    )
    await db.execute(stmt)
    await db.commit()

    return MessageResponse(message="Bookmarked.")


@router.delete("/{question_id}/bookmark", response_model=MessageResponse)
async def unbookmark_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bookmark = await db.scalar(
        select(Bookmark).where(
            Bookmark.user_id == current_user.id,
            Bookmark.question_id == question_id,
        )
    )
    # NOTE: contract doesn't specify 404-vs-200 behavior for unbookmarking
    # something that was never bookmarked. Treating this as idempotent in
    # the same spirit as the bookmark route's docstring ("idempotent —
    # returns 200, not an error") even though that line technically only
    # describes the POST route. A DELETE on a non-existent bookmark
    # reaching the same end state (no bookmark row exists) succeeding
    # quietly is the more consistent behavior — flag if you'd rather this
    # 404 instead.
    if bookmark:
        await db.delete(bookmark)
        await db.commit()

    return MessageResponse(message="Bookmark removed.")


# ─────────────────────────────────────────────────────────────────────────────
# NOT IMPLEMENTED IN THIS FILE — GET /questions/bookmarks
# ─────────────────────────────────────────────────────────────────────────────
# Your prompt asked for this route ("GET /questions/bookmarks: return own
# bookmarks joined with question data... filtered by is_deleted=False"),
# but the SECTION 6 — QUESTIONS contract you pasted does NOT define it —
# only POST/DELETE /{question_id}/bookmark live in this section. Looking at
# the full contract.py from earlier in this conversation, the list endpoint
# (GET /bookmarks, returning BookmarkListResponse with items: list[BookmarkOut])
# is defined under a SEPARATE router — SECTION 7 — BOOKMARKS, prefix
# "/bookmarks", not "/questions/bookmarks". Two different paths, two
# different response shapes, two different router files in contract.py's
# own organization.
#
# Rather than inventing a path that doesn't match either contract section
# (which would create exactly the frontend/backend drift this whole
# contract-first approach exists to prevent), implement this as its own
# router file matching contract.py SECTION 7 exactly:
#
#   backend/routers/bookmarks.py
#   router = APIRouter()
#
#   @router.get("", response_model=BookmarkListResponse)
#   async def list_bookmarks(page: int = 1, per_page: int = 20, ...):
#       # SELECT Bookmark JOIN Question WHERE Bookmark.user_id = current_user.id
#       #   AND Question.is_deleted == False
#       ...
#
#   # main.py:
#   app.include_router(bookmarks_router.router, prefix="/bookmarks", tags=["bookmarks"])
#
# Ask for this as its own implementation task (paste SECTION 7 — BOOKMARKS)
# rather than folding it into this file under the wrong prefix.