"""
backend/routers/subscriptions.py
=================================
Subscription & plan management.
Every path, method, and response_model matches contract.py exactly.

This file currently implements the PLAN routes (Slice 7, step 1).
Subscription-status routes (/check, /me, etc.) are added in later steps.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from dependencies import get_current_user
from models import Subscription, SubStatus


from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import require_admin
from models import Plan, User

router = APIRouter()


# ── Schemas (copied from contract.py) ─────────────────────────────────────────
class PlanOut(BaseModel):
    id: int
    name: str
    price_cents: int
    currency: str
    duration_days: int
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class PlanCreateRequest(BaseModel):
    name: str = Field(..., example="3-Month Access")
    price_cents: int = Field(..., example=8999, description="$89.99 = 8999")
    currency: str = Field("USD", max_length=3)
    duration_days: int = Field(..., example=90)
    description: Optional[str] = None


# ── GET /subscriptions/plans ──────────────────────────────────────────────────
@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Public — no auth. Returns plans with is_active=TRUE."""
    result = await db.execute(select(Plan).where(Plan.is_active == True))  # noqa: E712
    return result.scalars().all()


# ── POST /subscriptions/plans ─────────────────────────────────────────────────
@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(
    data: PlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    plan = Plan(**data.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


# ── PATCH /subscriptions/plans/{plan_id} ──────────────────────────────────────
@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: int,
    data: PlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    for field, value in data.model_dump().items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan

# ══ Subscription status & history (Slice 7 step 3) ════════════════════════════

class SubscriptionCheckResponse(BaseModel):
    has_access: bool
    status: Optional[SubStatus]
    end_date: Optional[datetime]
    days_remaining: Optional[int]


class SubscriptionOut(BaseModel):
    id: int
    user_id: int
    plan: PlanOut
    status: SubStatus
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    grace_until: Optional[datetime]
    cancelled_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


GRACE_DAYS = 3  # BR9: 3-day read-only grace period after end_date


def _compute_access(sub: Optional[Subscription], now: datetime) -> SubscriptionCheckResponse:
    """
    Compute effective access from a subscription, applying BR9 grace on read
    (derived from dates rather than stored status). has_access is True for
    active and for the 3-day grace window after end_date.
    """
    if sub is None or sub.status in (SubStatus.pending, SubStatus.cancelled):
        return SubscriptionCheckResponse(
            has_access=False,
            status=sub.status if sub else None,
            end_date=sub.end_date if sub else None,
            days_remaining=None,
        )

    if sub.end_date is None:
        return SubscriptionCheckResponse(
            has_access=False, status=sub.status, end_date=None, days_remaining=None
        )

    grace_end = sub.end_date + timedelta(days=GRACE_DAYS)

    if now <= sub.end_date:
        return SubscriptionCheckResponse(
            has_access=True,
            status=SubStatus.active,
            end_date=sub.end_date,
            days_remaining=(sub.end_date - now).days,
        )
    elif now <= grace_end:
        return SubscriptionCheckResponse(
            has_access=True,
            status=SubStatus.grace,
            end_date=sub.end_date,
            days_remaining=(grace_end - now).days,
        )
    else:
        return SubscriptionCheckResponse(
            has_access=False,
            status=SubStatus.expired,
            end_date=sub.end_date,
            days_remaining=0,
        )


@router.get("/check", response_model=SubscriptionCheckResponse)
async def check_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Called on every protected page load. has_access reflects BR9 grace."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    return _compute_access(sub, datetime.now(timezone.utc))


@router.get("/me", response_model=list[SubscriptionOut])
async def my_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The current user's subscription history, newest first, with nested plan."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
    )
    subs = result.scalars().all()
    if not subs:
        return []

    plan_ids = {s.plan_id for s in subs}
    plan_result = await db.execute(select(Plan).where(Plan.id.in_(plan_ids)))
    plans_by_id = {p.id: p for p in plan_result.scalars().all()}

    out: list[SubscriptionOut] = []
    for s in subs:
        out.append(
            SubscriptionOut(
                id=s.id,
                user_id=s.user_id,
                plan=PlanOut.model_validate(plans_by_id.get(s.plan_id)),
                status=s.status,
                start_date=s.start_date,
                end_date=s.end_date,
                grace_until=s.grace_until,
                cancelled_at=s.cancelled_at,
                created_at=s.created_at,
            )
        )
    return out