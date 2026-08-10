"""
backend/routers/subscriptions.py
=================================
Subscription & plan management.
Every path, method, and response_model matches contract.py exactly.

This file currently implements the PLAN routes (Slice 7, step 1).
Subscription-status routes (/check, /me, etc.) are added in later steps.
"""
from __future__ import annotations

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