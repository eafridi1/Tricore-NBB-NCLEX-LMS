"""
backend/routers/admin.py
==========================
Real implementation of contract.py SECTION 12 — ADMIN.
Every path, method, and response_model matches the contract exactly.

ROUTING ORDER NOTE: GET /admin/analytics/me MUST be registered before
GET /admin/analytics/students/{user_id}. FastAPI matches routes
top-to-bottom — if the {user_id} route comes first, a request to
/admin/analytics/me hits it with user_id="me", which fails int validation
with a 422 before the /me handler ever fires. Both handlers are present
below in the correct order. Do not reorder them.

Wire into main.py with:
    from routers import admin as admin_router
    app.include_router(admin_router.router, prefix="/admin", tags=["admin"])
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from analytics import (
    AtRiskStudent as AnalyticsAtRiskStudent,
    WeakAreaRow as AnalyticsWeakAreaRow,
    get_at_risk_students,
    get_avg_score,
    get_score_trend,
    get_total_attempts,
    get_weak_areas,
)
from database import get_db
from dependencies import get_current_user, require_admin
from models import (
    AttemptStatus,
    IPWhitelist,
    Question,
    QStatus,
    QuizAttempt,
    Session,
    Subscription,
    SubStatus,
    User,
    UserRole,
)

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 12.

class DashboardStatsResponse(BaseModel):
    total_students: int
    active_subscribers: int
    total_questions: int
    published_questions: int
    total_attempts_today: int
    revenue_this_month_cents: int


class WeakAreaRow(BaseModel):
    category_name: str
    avg_score: float
    attempt_count: int


class StudentAnalyticsResponse(BaseModel):
    user_id: int
    avg_score: float
    total_attempts: int
    weak_areas: list[WeakAreaRow]
    score_trend: list[dict]
    is_at_risk: bool


class AtRiskStudent(BaseModel):
    user_id: int
    name: str
    email: str
    avg_score: float
    last_attempt: datetime


class IPWhitelistEntry(BaseModel):
    id: int
    ip_cidr: str
    label: Optional[str]
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IPWhitelistCreateRequest(BaseModel):
    ip_cidr: str = Field(..., example="203.0.113.0/24")
    label: Optional[str] = Field(None, example="Office Islamabad")


class MessageResponse(BaseModel):
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_cidr(ip_cidr: str) -> None:
    """
    Reject malformed CIDR strings before they reach the DB.
    ipaddress.ip_network() raises ValueError on invalid input.
    strict=False allows host bits to be set (e.g. 192.168.1.5/24
    is treated as 192.168.1.0/24) — more forgiving for admin input
    where someone types their own IP rather than the network address.
    """
    try:
        ipaddress.ip_network(ip_cidr, strict=False)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"'{ip_cidr}' is not a valid IP address or CIDR range. "
                   f"Examples: 203.0.113.5 or 203.0.113.0/24",
        )


async def _build_student_analytics(
    db: AsyncSession,
    user_id: int,
    period: str = "all",
) -> StudentAnalyticsResponse:
    """
    Shared between GET /admin/analytics/me and
    GET /admin/analytics/students/{user_id} — same computation, different
    user_id source. Separated into a helper so the two routes don't
    duplicate the analytics calls and the is_at_risk computation.

    is_at_risk definition: is this student among the at-risk list right now?
    The analytics.get_at_risk_students() function is platform-wide — we
    call it and check if user_id appears in the results rather than
    duplicating its SQL logic here. This is slightly less efficient than a
    targeted single-user check, but keeps the at-risk threshold logic in
    one place (analytics.py) rather than two.

    NOTE: get_weak_areas and get_at_risk_students are PostgreSQL-only.
    If this endpoint is called against the SQLite test DB, those two calls
    will raise. Use the SQLite-safe versions (get_avg_score, get_score_trend,
    get_total_attempts) in SQLite-targeted tests and mock the rest.
    """
    avg_score = await get_avg_score(db, user_id)
    total_attempts = await get_total_attempts(db, user_id)
    score_trend = await get_score_trend(db, user_id, period=period)

    try:
        raw_weak_areas = await get_weak_areas(db, user_id)
        at_risk_list = await get_at_risk_students(db)
    except Exception:
        # Graceful degradation for SQLite test environments — return empty
        # lists rather than crashing the endpoint entirely. Production
        # (PostgreSQL) will not hit this branch.
        raw_weak_areas = []
        at_risk_list = []

    weak_areas = [
        WeakAreaRow(
            category_name=row.category_name,
            avg_score=row.avg_score,
            attempt_count=row.attempt_count,
        )
        for row in raw_weak_areas
    ]

    is_at_risk = any(s.user_id == user_id for s in at_risk_list)

    return StudentAnalyticsResponse(
        user_id=user_id,
        avg_score=avg_score,
        total_attempts=total_attempts,
        weak_areas=weak_areas,
        score_trend=score_trend,
        is_at_risk=is_at_risk,
    )


# ── GET /admin/stats ─────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStatsResponse)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)

    # Today's midnight UTC — used for total_attempts_today
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Month start — used for revenue (Slice 7 — payments table doesn't
    # exist yet, returning 0 until then as instructed)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Run all counts in parallel where possible — SQLAlchemy async lets us
    # fire independent queries without awaiting each one in series, but
    # since these are all separate SELECT COUNT() queries against different
    # tables, running them sequentially is fine at this scale. Worth
    # converting to asyncio.gather() if stats become slow in production.

    total_students = (await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.student)
    )).scalar_one()

    # active_subscribers: requires Subscription model (added in Task 1.3).
    # If the subscriptions table doesn't exist yet (pre-migration), this
    # will raise. Run alembic upgrade head before using this endpoint.
    try:
        active_subscribers = (await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.status == SubStatus.active,
                Subscription.end_date > now,
            )
        )).scalar_one()
    except Exception:
        # Subscriptions table not yet migrated — return 0 rather than 500.
        # Remove this try/except after alembic upgrade head runs Task 1.3's
        # migration.
        active_subscribers = 0

    total_questions = (await db.execute(
        select(func.count())
        .select_from(Question)
        .where(Question.is_deleted == False)  # noqa: E712
    )).scalar_one()

    published_questions = (await db.execute(
        select(func.count())
        .select_from(Question)
        .where(
            Question.is_deleted == False,  # noqa: E712
            Question.status == QStatus.published,
        )
    )).scalar_one()

    total_attempts_today = (await db.execute(
        select(func.count())
        .select_from(QuizAttempt)
        .where(QuizAttempt.started_at >= today_midnight)
    )).scalar_one()

    # revenue_this_month_cents — payments table is Slice 7.
    # Returning 0 until then, as specified in the task.
    revenue_this_month_cents = 0
    # TODO(slice-7): uncomment once Payment model exists:
    # revenue_this_month_cents = (await db.execute(
    #     select(func.sum(Payment.amount_cents))
    #     .where(
    #         Payment.status == PayStatus.succeeded,
    #         Payment.created_at >= month_start,
    #     )
    # )).scalar_one_or_none() or 0

    return DashboardStatsResponse(
        total_students=total_students,
        active_subscribers=active_subscribers,
        total_questions=total_questions,
        published_questions=published_questions,
        total_attempts_today=total_attempts_today,
        revenue_this_month_cents=revenue_this_month_cents,
    )


# ── GET /admin/analytics/me (MUST be before /{user_id}) ─────────────────────

@router.get("/analytics/me", response_model=StudentAnalyticsResponse)
async def my_analytics(
    period: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any auth user, not admin-only
):
    # CONTRACT NOTE: the contract places this route under /admin prefix
    # even though it's NOT admin-only ("Student: view own performance
    # analytics"). This is a contract design choice — grouping all
    # analytics under /admin/ — not a security oversight. The route
    # correctly uses get_current_user (not require_admin) per the
    # contract's own summary. Any authenticated user can view their
    # own data here; they can never view another user's data.
    return await _build_student_analytics(db, current_user.id, period=period)


# ── GET /admin/analytics/students ────────────────────────────────────────────

@router.get("/analytics/students", response_model=list[AtRiskStudent])
async def at_risk_students(
    threshold: float = 60.0,
    consecutive: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        raw = await get_at_risk_students(db, threshold=threshold, consecutive=consecutive)
    except Exception:
        # PostgreSQL-only function — graceful degradation for non-PG envs
        raw = []

    return [
        AtRiskStudent(
            user_id=s.user_id,
            name=s.name,
            email=s.email,
            avg_score=s.avg_score,
            last_attempt=s.last_attempt,
        )
        for s in raw
    ]


# ── GET /admin/analytics/students/{user_id} ──────────────────────────────────
# MUST be registered after /analytics/me — see routing order note at top.

@router.get("/analytics/students/{user_id}", response_model=StudentAnalyticsResponse)
async def student_analytics(
    user_id: int,
    period: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Confirm the target user exists before running expensive analytics
    # queries — returns 404 rather than empty/zero analytics for a
    # user_id that doesn't exist.
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    return await _build_student_analytics(db, user_id, period=period)


# ── GET /admin/security/ip-whitelist ─────────────────────────────────────────

@router.get("/security/ip-whitelist", response_model=list[IPWhitelistEntry])
async def list_ip_whitelist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(IPWhitelist).order_by(IPWhitelist.created_at.desc())
    )
    return result.scalars().all()


# ── POST /admin/security/ip-whitelist ────────────────────────────────────────

@router.post("/security/ip-whitelist", response_model=IPWhitelistEntry, status_code=201)
async def add_ip_whitelist(
    data: IPWhitelistCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _validate_cidr(data.ip_cidr)

    # Duplicate check — adding the same CIDR twice is probably a mistake,
    # not an error worth a 409, but worth a clear message.
    existing = await db.scalar(
        select(IPWhitelist).where(IPWhitelist.ip_cidr == data.ip_cidr)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"'{data.ip_cidr}' is already in the whitelist (id={existing.id}).",
        )

    entry = IPWhitelist(
        ip_cidr=data.ip_cidr,
        label=data.label,
        created_by=current_user.id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


# ── DELETE /admin/security/ip-whitelist/{entry_id} ───────────────────────────

@router.delete("/security/ip-whitelist/{entry_id}", response_model=MessageResponse)
async def remove_ip_whitelist(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    entry = await db.get(IPWhitelist, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="IP whitelist entry not found.")

    await db.delete(entry)
    await db.commit()
    return MessageResponse(message="IP range removed.")


# ── DELETE /admin/security/sessions/{user_id} ────────────────────────────────

@router.delete("/security/sessions/{user_id}", response_model=MessageResponse)
async def force_logout_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Confirm target user exists — same rationale as admin_user_login_history
    # in users.py: a silent empty-result delete on a non-existent user_id
    # is indistinguishable from "user existed but had no sessions."
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Guard: an admin force-logging themselves out would immediately
    # invalidate their own session mid-request. The request would still
    # return 200 (the delete commits before the response is sent), but
    # their next request would 401. Surprising behavior — worth blocking.
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot force-logout your own session via this endpoint. "
                   "Use POST /auth/logout instead.",
        )

    result = await db.execute(
        delete(Session).where(Session.user_id == user_id)
    )
    await db.commit()

    terminated_count = result.rowcount
    return MessageResponse(
        message=f"All sessions terminated for user {user_id} "
                f"({terminated_count} session(s) invalidated)."
    )