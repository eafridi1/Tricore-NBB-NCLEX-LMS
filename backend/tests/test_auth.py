# backend/tests/test_auth.py
"""
Integration tests for SECTION 1 — AUTH
All 9 endpoints: register, verify-email, resend-verification,
login, 2fa-verify, refresh, logout, forgot-password, reset-password.

Test philosophy:
  - Happy path first: confirm the main flow works end-to-end.
  - Error cases: focus on business-rule violations (wrong password,
    expired token, locked account) not HTTP plumbing (missing fields
    are covered by Pydantic/FastAPI and don't need explicit tests).
  - No mocking: tests call real FastAPI routes against a real (in-memory)
    database. email_utils.send_email() prints to console — that's fine
    for tests, we just verify the DB side-effects instead of the email.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import User, Session, LoginLog, LoginStatus
from auth_utils import hash_password

pytestmark = pytest.mark.asyncio


# ── POST /auth/register ──────────────────────────────────────────────────────

async def test_register_success(client: AsyncClient, db: AsyncSession):
    resp = await client.post("/auth/register", json={
        "name": "Sarah Khan",
        "email": "sarah@test.com",
        "password": "Secure123!",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "user_id" in data
    assert data["user_id"] > 0

    # Verify DB state
    user = await db.get(User, data["user_id"])
    assert user is not None
    assert user.email == "sarah@test.com"
    assert user.is_verified is False
    assert user.verify_token is not None


async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    payload = {"name": "Ali Test", "email": "dup@test.com", "password": "Secure123!"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409


async def test_register_weak_password_no_uppercase(anon_client: AsyncClient):
    resp = await anon_client.post("/auth/register", json={
        "name": "Ahmed Test", "email": "a@test.com", "password": "nouppercase1",
    })
    assert resp.status_code == 422


async def test_register_weak_password_no_digit(anon_client: AsyncClient):
    resp = await anon_client.post("/auth/register", json={
        "name": "Bilal Test", "email": "b@test.com", "password": "NoDigitHere",
    })
    assert resp.status_code == 422


async def test_register_weak_password_no_lowercase(anon_client: AsyncClient):
    resp = await anon_client.post("/auth/register", json={
        "name": "C Test", "email": "c@test.com", "password": "NOLOWER123!",
    })
    assert resp.status_code == 422


async def test_register_weak_password_no_special_char(anon_client: AsyncClient):
    resp = await anon_client.post("/auth/register", json={
        "name": "D Test", "email": "d@test.com", "password": "NoSpecial123",
    })
    assert resp.status_code == 422


# ── GET /auth/verify-email ───────────────────────────────────────────────────

async def test_verify_email_success(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    reg = await client.post("/auth/register", json={
        "name": "Bob Test", "email": "verify@test.com", "password": "Secure123!",
    })
    assert reg.status_code == 201, reg.text
    user = await db.scalar(select(User).where(User.email == "verify@test.com"))
    token = user.verify_token

    resp = await client.get(f"/auth/verify-email?token={token}")
    assert resp.status_code == 200

    await db.refresh(user)
    assert user.is_verified is True
    assert user.verify_token is None


async def test_verify_email_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/verify-email?token=notarealtoken")
    assert resp.status_code == 400


async def test_verify_email_already_used(client: AsyncClient, db: AsyncSession):
    """Token is cleared after first use — second click on the same link 400s."""
    from sqlalchemy import select
    reg = await client.post("/auth/register", json={
        "name": "Carol Test", "email": "double@test.com", "password": "Secure123!",
    })
    assert reg.status_code == 201, reg.text
    user = await db.scalar(select(User).where(User.email == "double@test.com"))
    token = user.verify_token

    await client.get(f"/auth/verify-email?token={token}")  # first use — succeeds
    resp = await client.get(f"/auth/verify-email?token={token}")  # second use
    assert resp.status_code == 400


# ── POST /auth/resend-verification ──────────────────────────────────────────

async def test_resend_verification_success(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    reg = await client.post("/auth/register", json={
        "name": "Dave Test", "email": "resend@test.com", "password": "Secure123!",
    })
    assert reg.status_code == 201, reg.text
    user = await db.scalar(select(User).where(User.email == "resend@test.com"))
    old_token = user.verify_token

    resp = await client.post("/auth/resend-verification", json={"email": "resend@test.com"})
    assert resp.status_code == 200

    await db.refresh(user)
    assert user.verify_token != old_token  # new token issued


async def test_resend_verification_unknown_email_silent(client: AsyncClient):
    """Anti-enumeration: always 200, even for an email that doesn't exist."""
    resp = await client.post("/auth/resend-verification", json={
        "email": "nobody@test.com"
    })
    assert resp.status_code == 200


# ── POST /auth/login ─────────────────────────────────────────────────────────

async def _make_verified_user(db: AsyncSession, email: str = "login@test.com") -> User:
    user = User(
        name="Login User",
        email=email,
        password_hash=hash_password("Secure123!"),
        role="student",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def test_login_step1_success(client: AsyncClient, db: AsyncSession):
    await _make_verified_user(db)
    resp = await client.post("/auth/login", json={
        "email": "login@test.com", "password": "Secure123!",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "otp_sent"


async def test_login_wrong_password(client: AsyncClient, db: AsyncSession):
    await _make_verified_user(db, "wrong@test.com")
    resp = await client.post("/auth/login", json={
        "email": "wrong@test.com", "password": "WrongPassword1",
    })
    assert resp.status_code == 401


async def test_login_increments_failed_counter(client: AsyncClient, db: AsyncSession):
    user = await _make_verified_user(db, "counter@test.com")
    assert user.failed_logins == 0

    await client.post("/auth/login", json={
        "email": "counter@test.com", "password": "WrongPassword1",
    })
    await db.refresh(user)
    assert user.failed_logins == 1


async def test_login_lockout_after_5_failures(client: AsyncClient, db: AsyncSession):
    # NOTE: if this fails with timezone error, apply _as_utc() fix to auth.py's
    # locked_until comparison: replace `user.locked_until > now` with
    # `_as_utc(user.locked_until) > now` where now = datetime.now(timezone.utc)
    await _make_verified_user(db, "lockout@test.com")
    payload = {"email": "lockout@test.com", "password": "WrongPassword1"}

    for _ in range(5):
        await client.post("/auth/login", json=payload)

    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 429
    assert "locked" in resp.json()["detail"].lower()


async def test_login_unverified_account(client: AsyncClient, db: AsyncSession):
    user = User(
        name="Unverified",
        email="unverified@test.com",
        password_hash=hash_password("Secure123!"),
        role="student",
        is_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    resp = await client.post("/auth/login", json={
        "email": "unverified@test.com", "password": "Secure123!",
    })
    assert resp.status_code == 403


async def test_login_nonexistent_email(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "email": "ghost@test.com", "password": "Secure123!",
    })
    assert resp.status_code == 401


async def test_login_logs_attempt_to_db(client: AsyncClient, db: AsyncSession):
    await _make_verified_user(db, "logged@test.com")
    await client.post("/auth/login", json={
        "email": "logged@test.com", "password": "WrongPassword1",
    })
    log = await db.scalar(
        select(LoginLog).where(LoginLog.status == LoginStatus.failed_password)
    )
    assert log is not None


# ── POST /auth/2fa-verify ────────────────────────────────────────────────────

async def test_2fa_verify_success(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone
    from auth_utils import otp_context  # moved to auth_utils from auth.py — see auth_utils_patch.txt

    user = await _make_verified_user(db, "otp@test.com")
    otp = "482910"
    user.otp_hash = otp_context.hash(otp)
    user.otp_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    user.otp_attempts = 0
    await db.flush()

    resp = await client.post("/auth/2fa-verify", json={
        "email": "otp@test.com", "otp": otp,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Session row created
    session = await db.scalar(select(Session).where(Session.user_id == user.id))
    assert session is not None

    # OTP cleared
    await db.refresh(user)
    assert user.otp_hash is None


async def test_2fa_verify_wrong_otp(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone
    from auth_utils import otp_context  # moved to auth_utils from auth.py — see auth_utils_patch.txt

    user = await _make_verified_user(db, "wrongotp@test.com")
    user.otp_hash = otp_context.hash("111111")
    user.otp_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    user.otp_attempts = 0
    await db.flush()

    resp = await client.post("/auth/2fa-verify", json={
        "email": "wrongotp@test.com", "otp": "999999",
    })
    assert resp.status_code == 401

    await db.refresh(user)
    assert user.otp_attempts == 1


async def test_2fa_verify_expired_otp(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone
    from auth_utils import otp_context  # moved to auth_utils from auth.py — see auth_utils_patch.txt

    user = await _make_verified_user(db, "expiredotp@test.com")
    user.otp_hash = otp_context.hash("123456")
    user.otp_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    user.otp_attempts = 0
    await db.flush()

    resp = await client.post("/auth/2fa-verify", json={
        "email": "expiredotp@test.com", "otp": "123456",
    })
    assert resp.status_code == 400


# ── POST /auth/logout ────────────────────────────────────────────────────────

async def test_logout_deletes_session(
    client: AsyncClient, db: AsyncSession,
    student_user: User, student_token: str
):
    # Create a session row first
    from datetime import datetime, timedelta, timezone
    session = Session(
        user_id=student_user.id,
        refresh_token="test-refresh-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()

    resp = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {student_token}"},
        cookies={"refresh_token": "test-refresh-token"},
    )
    assert resp.status_code == 200

    remaining = await db.scalar(
        select(Session).where(Session.user_id == student_user.id)
    )
    assert remaining is None


async def test_logout_requires_auth(client: AsyncClient):
    resp = await client.post("/auth/logout")
    assert resp.status_code in (401, 403)  # depends on HTTPBearer auto_error setting


# ── POST /auth/forgot-password ───────────────────────────────────────────────

async def test_forgot_password_sets_token(client: AsyncClient, db: AsyncSession):
    user = await _make_verified_user(db, "forgot@test.com")
    assert user.reset_token is None

    resp = await client.post("/auth/forgot-password", json={"email": "forgot@test.com"})
    assert resp.status_code == 200

    await db.refresh(user)
    assert user.reset_token is not None
    assert user.reset_expires is not None


async def test_forgot_password_unknown_email_silent(client: AsyncClient):
    """Anti-enumeration: always 200."""
    resp = await client.post("/auth/forgot-password", json={
        "email": "nobody@test.com"
    })
    assert resp.status_code == 200


# ── POST /auth/reset-password ────────────────────────────────────────────────

async def test_reset_password_success(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone

    user = await _make_verified_user(db, "reset@test.com")
    user.reset_token = "valid-reset-token"
    user.reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.flush()

    resp = await client.post("/auth/reset-password", json={
        "token": "valid-reset-token",
        "new_password": "NewSecure456!",
    })
    assert resp.status_code == 200

    await db.refresh(user)
    assert user.reset_token is None
    assert user.failed_logins == 0


async def test_reset_password_invalid_token(client: AsyncClient):
    resp = await client.post("/auth/reset-password", json={
        "token": "fake-token", "new_password": "NewSecure456!",
    })
    assert resp.status_code == 400


async def test_reset_password_expired_token(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone

    user = await _make_verified_user(db, "expired_reset@test.com")
    user.reset_token = "expired-token"
    user.reset_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.flush()

    resp = await client.post("/auth/reset-password", json={
        "token": "expired-token", "new_password": "NewSecure456!",
    })
    assert resp.status_code == 400


async def test_reset_password_clears_all_sessions(client: AsyncClient, db: AsyncSession):
    from datetime import datetime, timedelta, timezone

    user = await _make_verified_user(db, "session_clear@test.com")
    user.reset_token = "clear-sessions-token"
    user.reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    session = Session(
        user_id=user.id,
        refresh_token="old-session",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()

    await client.post("/auth/reset-password", json={
        "token": "clear-sessions-token", "new_password": "NewSecure456!",
    })

    remaining = await db.scalar(
        select(Session).where(Session.user_id == user.id)
    )
    assert remaining is None