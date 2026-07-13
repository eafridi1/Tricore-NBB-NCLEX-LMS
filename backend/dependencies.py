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