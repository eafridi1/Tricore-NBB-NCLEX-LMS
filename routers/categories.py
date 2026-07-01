"""
backend/routers/categories.py
==============================
Real implementation of contract.py SECTION 5 — CATEGORIES.
Every path, method, and response_model below matches the contract exactly.

Wire into main.py with:
    from routers import categories as categories_router
    app.include_router(categories_router.router, prefix="/categories", tags=["categories"])
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import require_admin
from models import Category, Question, User

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 5.

class CategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sort_order: int
    question_count: Optional[int] = None  # included when listing for quiz setup

    model_config = {"from_attributes": True}


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., example="Cardiovascular")
    description: Optional[str] = None
    sort_order: int = 0


class MessageResponse(BaseModel):
    message: str


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CategoryOut])
async def list_categories(
    include_count: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if not include_count:
        # Cheap path — no JOIN, no subquery. Most callers (quiz setup
        # dropdowns, nav filters) don't need the count and this avoids an
        # aggregate query on every page load.
        result = await db.execute(
            select(Category).order_by(Category.sort_order)
        )
        categories = result.scalars().all()
        return [
            CategoryOut(
                id=c.id,
                name=c.name,
                description=c.description,
                sort_order=c.sort_order,
                question_count=None,
            )
            for c in categories
        ]

    # include_count=True path — left join + count, grouped per category.
    # CRITICAL: filters Question.is_deleted == False so soft-deleted
    # questions don't inflate the count shown to students/admins picking
    # a category to study. Per Week 2 Task 2.4's soft-delete requirement —
    # every query touching questions must respect is_deleted, this one
    # included even though it's only counting, not returning question rows.
    #
    # NOTE: intentionally NOT filtering Question.status == 'published' here.
    # question_count is meant to represent "how much content exists in this
    # category" for admin-facing contexts (e.g. category manager showing
    # draft+published totals) as well as student-facing contexts (quiz
    # setup, where only published should count). The contract doesn't
    # distinguish these two callers with separate fields, so this counts
    # ALL non-deleted questions regardless of status. If quiz setup needs a
    # student-safe "published only" count, that's a contract gap — flag it
    # rather than silently filtering status here, since changing this query
    # also changes what admins see in the category manager.
    count_subquery = (
        select(
            Question.category_id,
            func.count(Question.id).label("question_count"),
        )
        .where(Question.is_deleted == False)  # noqa: E712
        .group_by(Question.category_id)
        .subquery()
    )

    result = await db.execute(
        select(Category, count_subquery.c.question_count)
        .outerjoin(count_subquery, Category.id == count_subquery.c.category_id)
        .order_by(Category.sort_order)
    )

    return [
        CategoryOut(
            id=category.id,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            question_count=question_count or 0,
        )
        for category, question_count in result.all()
    ]


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    data: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.scalar(select(Category).where(Category.name == data.name))
    if existing:
        # SECURITY NOTE: same tradeoff as auth.py's duplicate-email check —
        # contract.py doesn't specify a status code for this case. 409 is
        # the correct HTTP semantic and this is an admin-only, low-stakes
        # surface (no enumeration concern like the auth routes), so
        # confirming the duplicate is fine here.
        raise HTTPException(
            status_code=409,
            detail=f"A category named '{data.name}' already exists.",
        )

    category = Category(
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        question_count=0,
    )


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    data: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")

    # CONTRACT NOTE: CategoryCreateRequest's fields are all required-with-
    # defaults at the Pydantic level (name has no default, description
    # defaults to None, sort_order defaults to 0) — there's no Optional[str]
    # variant for PATCH the way contract.py gives QuestionUpdateRequest its
    # own all-optional shape. That means a PATCH call that only wants to
    # rename a category still has to resend description and sort_order, or
    # they'll silently reset to None/0 since this reuses CategoryCreateRequest
    # verbatim per the contract. Not changing this — contract.py defines it
    # this way and Task asked to match the contract exactly — but flagging
    # for the frontend dev: PATCH /categories/{id} is full-replace semantics,
    # not partial-update, despite the HTTP verb suggesting otherwise. Worth
    # putting in CONTRACT_STATUS.md notes column if this trips anyone up.
    if data.name != category.name:
        name_clash = await db.scalar(
            select(Category).where(Category.name == data.name, Category.id != category_id)
        )
        if name_clash:
            raise HTTPException(
                status_code=409,
                detail=f"A category named '{data.name}' already exists.",
            )

    category.name = data.name
    category.description = data.description
    category.sort_order = data.sort_order
    await db.commit()
    await db.refresh(category)

    return CategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        # NOTE: not recomputing question_count here — contract's CategoryOut
        # makes it Optional, and the PATCH response in contract.py's own
        # stub doesn't pass question_count either (falls back to the
        # Optional's None default). Leaving it None here matches that, and
        # avoids an extra count query on every rename when the caller
        # likely already has the count from whatever list view they edited
        # from.
    )


@router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")

    # FK guard per the contract's own docstring: "Only allowed if no
    # questions reference this category." Checking against is_deleted=False
    # questions only — if every question in this category has already been
    # soft-deleted, the category itself is safe to remove since nothing
    # live points at it. A soft-deleted question's category_id FK still
    # technically references this row, but that's fine: soft-deleted rows
    # are invisible everywhere already (see Slice 2's is_deleted filtering),
    # so there's no live UI surface that would break.
    linked_question = await db.scalar(
        select(Question.id).where(
            Question.category_id == category_id,
            Question.is_deleted == False,  # noqa: E712
        )
    )
    if linked_question:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete a category that has questions assigned to it. "
                "Reassign or archive those questions first."
            ),
        )

    await db.delete(category)
    await db.commit()

    return MessageResponse(message="Category deleted.")