from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from database import get_db
from auth_utils import decode_access_token
from models import User, UserRole

bearer = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

"""
backend/dependencies.py — ADDITION
====================================
Add this function to your existing dependencies.py (the one built in
Week 1, Task 3.2, containing get_current_user and require_admin).

questions.py imports `require_admin_or_reviewer`, which doesn't exist yet
in the Week 1 version — Week 1 only needed `require_admin` (for the
admin-only auth/security surfaces). Questions are the first slice where
the `reviewer` role (defined in your UserRole enum since Week 1, but
unused until now) actually matters: contract.py's docstrings consistently
say "Admin/Reviewer" for question create/edit/status routes, not
"Admin" alone.

Paste this into dependencies.py rather than creating a new file — it
belongs alongside get_current_user and require_admin, not as a separate
module.
"""


async def require_admin_or_reviewer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.admin, UserRole.reviewer):
        raise HTTPException(
            status_code=403,
            detail="Admin or reviewer access required.",
        )
    return current_user

# ── Subscription gating (Slice 7 step 4) ──────────────────────────────────────
# Enforces active-or-grace subscription for STUDENTS. Admins and reviewers
# bypass (they manage content). Grace logic mirrors BR9 (end_date + 3 days)
# and must stay consistent with _compute_access in routers/subscriptions.py.
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from models import Subscription, SubStatus

_GRACE_DAYS = 3  # BR9


async def require_active_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Admins and reviewers are never gated — they manage content.
    if current_user.role in (UserRole.admin, UserRole.reviewer):
        return current_user

    # Most recent subscription for this user.
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    has_access = False
    if (
        sub is not None
        and sub.status not in (SubStatus.pending, SubStatus.cancelled)
        and sub.end_date is not None
    ):
        grace_end = sub.end_date + timedelta(days=_GRACE_DAYS)
        if now <= grace_end:  # active window OR within 3-day grace
            has_access = True

    if not has_access:
        raise HTTPException(
            status_code=402,
            detail="An active subscription is required to access this content.",
        )
    return current_user