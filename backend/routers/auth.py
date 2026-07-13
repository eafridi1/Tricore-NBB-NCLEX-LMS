"""
backend/routers/auth.py
========================
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_otp,
    hash_password,
    pwd_context,
    verify_password,
)
from database import get_db
from email_utils import send_email
from models import LoginLog, LoginStatus, Session, User, UserRole
from auth_utils import otp_context
from validators import StrongPassword

router = APIRouter()
bearer = HTTPBearer()

# ── Config constants ────────────────────────────────────────────────────────
# NOTE: these were not in your Week 1 tasks.md numbers explicitly except
# "5 failed attempts / 15 min" — the rest (OTP expiry, OTP attempts, verify
# token expiry, reset token expiry) come from the contract.py docstrings.
# Centralising them here so they're easy to tune via env vars later instead
# of hunting through route bodies.
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 3
VERIFY_TOKEN_EXPIRY_HOURS = 24
RESET_TOKEN_EXPIRY_HOURS = 1
ACCESS_TOKEN_EXPIRY_MINUTES = 15
REFRESH_TOKEN_EXPIRY_DAYS = 7

# bcrypt has a 72-byte input cap — used only for OTP hashing below, not
# password hashing (that's already handled inside hash_password()).
# OTPs are 6 digits so this never matters in practice, but bcrypt also has
# real per-call cost; hashing a 6-digit OTP at cost=12 (your password
# setting) adds ~250ms to every login. Using a cheap, separate context for
# OTPs keeps step-2 verification fast without weakening password security.
from passlib.context import CryptContext  # noqa: E402



# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 1, per Task 2.4. Validators added
# here since the contract only defines shape, not validation logic.

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: StrongPassword  # SecretStr — never logged or printed


class RegisterResponse(BaseModel):
    message: str = "Account created. Check your email to verify."
    user_id: int


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="sarah@example.com")
    password: SecretStr

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "email": "sarah@example.com",
                "password": "S3cur3P@ss!"
            }]
        }
    }
    # SecretStr but NOT StrongPassword —
    # login should NOT validate strength rules,
    # only the stored hash matters. A user with an
    # old weak password must still be able to log in
    # (so they can change it). Enforcing StrongPassword
    # here would lock out anyone whose password predates
    # the new rules.


class LoginStep1Response(BaseModel):
    status: str = "otp_sent"
    message: str = "Check your email for a 6-digit code."


class TwoFAVerifyRequest(BaseModel):
    # CONTRACT GAP: the contract's TwoFAVerifyRequest only has `otp`, with
    # no email/user identifier field. But step 2 needs to know WHICH user's
    # OTP to check — the access token doesn't exist yet at this point in the
    # flow, so there is no JWT to decode a user id from.
    # FIX ADDED (commented why below): added `email` here, matching what
    # your own Week 1 useAuth.ts hook already assumes
    # (`TwoFAVerifyReq & { email: string }`). If you'd rather not change the
    # contract, the alternative is a short-lived, server-set HttpOnly
    # "login_session" cookie issued by /auth/login that step 2 reads instead
    # of trusting client-supplied email. That is more secure (prevents OTP
    # cross-account guessing) but is a bigger behavior change than your
    # contract currently describes. Going with `email` here to match the
    # contract's spirit and your frontend code as-is; flagging the tradeoff.
    email: EmailStr = Field(..., example="sarah@example.com")
    otp: str = Field(..., min_length=6, max_length=6, example="482910")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., example="a3f9c2...")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., example="reset_token_hex...")
    new_password: StrongPassword


class MessageResponse(BaseModel):
    message: str


# ── Helpers ─────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str | None:
    # Behind a reverse proxy (nginx/Render/Railway) the real client IP is in
    # X-Forwarded-For, not request.client.host. Falling back to
    # request.client.host for local dev where there's no proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _log_attempt(
    db: AsyncSession,
    request: Request,
    status_: LoginStatus,
    user_id: int | None = None,
) -> None:
    db.add(
        LoginLog(
            user_id=user_id,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            status=status_,
        )
    )
    # NOTE: intentionally not committing here — caller commits once at the
    # end of the route so the log write and the state change (e.g. OTP
    # issued, lockout set) land in the same transaction. If the route fails
    # after this point the log entry rolls back too, which is correct: we
    # don't want orphan "success" log rows for a request that errored out
    # downstream.


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=os.getenv("ENV") == "production",  # plain http on localhost
        # can't carry a `secure` cookie reliably across browsers.
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60,
        # path="/" (not "/auth"): the frontend's middleware.ts checks for
        # this cookie's presence on every page route (e.g. /dashboard) to
        # decide whether to redirect to /login. A cookie scoped to /auth
        # is never attached to those navigations, so the middleware always
        # sees it as missing and bounces a freshly-logged-in user right
        # back to /login.
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/")


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        # SECURITY NOTE: contract.py doesn't specify the duplicate-email
        # status code. 409 Conflict is the correct HTTP semantic here, but
        # it does confirm an email exists in the system (the same
        # enumeration tradeoff the contract explicitly avoids on
        # /forgot-password and /resend-verification). Registration UX
        # generally needs this confirmation ("an account with this email
        # already exists") so leaving it as 409, but flagging the
        # inconsistency with the rest of the module's anti-enumeration
        # stance in case product wants it silent too.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    verify_token = secrets.token_hex(32)
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password.get_secret_value()),
        role=UserRole.student,
        is_verified=False,
        is_active=True,
        verify_token=verify_token,
        verify_expires=datetime.now(timezone.utc)
        + timedelta(hours=VERIFY_TOKEN_EXPIRY_HOURS),
    )
    db.add(user)
    await db.flush()  # populates user.id without committing yet

    send_email(
        to=user.email,
        subject="Verify your TriCore account",
        body=(
            f"Hi {user.name},\n\n"
            f"Verify your email: http://localhost:3000/verify-email?token={verify_token}\n"
            f"This link expires in {VERIFY_TOKEN_EXPIRY_HOURS} hours."
        ),
    )

    await db.commit()
    return RegisterResponse(user_id=user.id)


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.verify_token == token))

    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token.")

    if user.verify_expires and user.verify_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Verification link has expired. Please request a new one.",
        )

    user.is_verified = True
    user.verify_token = None
    user.verify_expires = None
    await db.commit()
    return MessageResponse(message="Email verified. You can now log in.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)
):
    user = await db.scalar(select(User).where(User.email == data.email))

    # Anti-enumeration: always return the same message whether or not the
    # account exists, per the contract's own docstring for this route.
    if user and not user.is_verified:
        user.verify_token = secrets.token_hex(32)
        user.verify_expires = datetime.now(timezone.utc) + timedelta(
            hours=VERIFY_TOKEN_EXPIRY_HOURS
        )
        send_email(
            to=user.email,
            subject="Verify your TriCore account",
            body=(
                f"Verify your email: "
                f"http://localhost:3000/verify-email?token={user.verify_token}"
            ),
        )
        await db.commit()
    # else: silently no-op — matches "succeeds even if email not found"

    return MessageResponse(message="Verification email sent if account exists.")


@router.post("/login", response_model=LoginStep1Response)
async def login(
    data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await db.scalar(select(User).where(User.email == data.email))

    now = datetime.now(timezone.utc)

    if not user:
        # Logged with user_id=None since there's no user row to attach to.
        await _log_attempt(db, request, LoginStatus.failed_password)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        await _log_attempt(db, request, LoginStatus.account_locked, user.id)
        await db.commit()
        minutes_left = max(1, int((user.locked_until - now).total_seconds() // 60))
        raise HTTPException(
            status_code=429,
            detail=f"Account locked. Try again in {minutes_left} minute(s).",
        )

    if not user.is_verified:
        # CONTRACT GAP: contract.py's /auth/login docstring doesn't mention
        # an unverified-account case at all — only "401 on bad credentials"
        # and "429 if locked." Decided to treat unverified as 403 (distinct
        # from bad-credentials 401) so the frontend can show "please verify
        # your email" instead of "wrong password." If product wants this
        # folded into the generic 401 to avoid leaking verification status,
        # change the status_code below to 401 and the detail message to the
        # generic one.
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in.",
        )

    if not verify_password(data.password.get_secret_value(), user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            await _log_attempt(db, request, LoginStatus.account_locked, user.id)
        else:
            await _log_attempt(db, request, LoginStatus.failed_password, user.id)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Correct password — reset the failed counter and issue an OTP.
    user.failed_logins = 0
    user.locked_until = None

    otp = generate_otp()
    user.otp_hash = otp_context.hash(otp)
    user.otp_expires = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    user.otp_attempts = 0

    send_email(
        to=user.email,
        subject="Your TriCore login code",
        body=f"Your 6-digit code is: {otp}\nExpires in {OTP_EXPIRY_MINUTES} minutes.",
    )

    # NOTE: not logging this as `success` yet — success is only logged once
    # 2FA actually completes in /auth/2fa-verify below. This row would
    # otherwise misrepresent "logged in" when only step 1 passed.
    await db.commit()
    return LoginStep1Response()


@router.post("/2fa-verify", response_model=TokenResponse)
async def verify_2fa(
    data: TwoFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == data.email))
    now = datetime.now(timezone.utc)

    if not user or not user.otp_hash or not user.otp_expires:
        raise HTTPException(status_code=400, detail="No active login attempt found.")

    if user.otp_expires < now:
        user.otp_hash = None
        user.otp_expires = None
        await db.commit()
        raise HTTPException(
            status_code=400, detail="Code expired. Please log in again."
        )

    if user.otp_attempts >= MAX_OTP_ATTEMPTS:
        # Already maxed out from a previous request — clear the OTP so the
        # student can't keep hammering this endpoint after the 3rd failure.
        user.otp_hash = None
        user.otp_expires = None
        await _log_attempt(db, request, LoginStatus.failed_2fa, user.id)
        await db.commit()
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect codes. Please log in again.",
        )

    if not otp_context.verify(data.otp, user.otp_hash):
        user.otp_attempts += 1
        await _log_attempt(db, request, LoginStatus.failed_2fa, user.id)
        await db.commit()
        attempts_left = MAX_OTP_ATTEMPTS - user.otp_attempts
        raise HTTPException(
            status_code=401,
            detail=f"Incorrect code. {max(0, attempts_left)} attempt(s) left.",
        )

    # OTP correct — clear it so it can't be reused.
    user.otp_hash = None
    user.otp_expires = None
    user.otp_attempts = 0

    # One-session policy: wipe any existing sessions for this user before
    # creating the new one, so logging in on a second device kills the
    # first device's session (per BR6 in your Open Decisions appendix —
    # confirm this is the chosen policy vs. "block new login" before
    # shipping; this implementation assumes "invalidate oldest/others").
    await db.execute(delete(Session).where(Session.user_id == user.id))

    refresh_token = create_refresh_token()
    session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
    )
    db.add(session)

    access_token = create_access_token(user.id, user.role.value)
    _set_refresh_cookie(response, refresh_token)

    await _log_attempt(db, request, LoginStatus.success, user.id)
    await db.commit()

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided.")

    session = await db.scalar(
        select(Session).where(Session.refresh_token == refresh_token)
    )
    now = datetime.now(timezone.utc)

    if not session or session.expires_at < now:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    # BUG WATCH: Week 1 tasks.md Task 5.1's middleware.ts checks
    # `request.cookies.has("refresh_token")` to decide whether to redirect
    # to /login. That check only confirms the COOKIE exists, not that the
    # session row backing it is still valid — a stale/expired cookie still
    # passes that check client-side. This route is the actual source of
    # truth and correctly 401s here; just make sure your frontend's 401
    # interceptor (Task 5.2) is what ultimately redirects to /login, not
    # the middleware's cookie-presence check alone, or a expired-but-present
    # cookie will let the user "in" to a protected page that then fails on
    # first data fetch instead of failing at the route guard.
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Account no longer active.")

    session.last_used_at = now
    await db.commit()

    access_token = create_access_token(user.id, user.role.value)
    return RefreshResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    # The access token in the Authorization header tells us the user is
    # "currently logged in" per the bearer dependency, but logout actually
    # needs to delete the SESSION row, which is keyed by refresh_token (a
    # cookie), not by the access token (which is stateless JWT and isn't
    # stored anywhere to "delete"). Decoding the access token here mainly
    # serves as an auth gate (you must present a valid token to call
    # logout at all) — the actual invalidation works off the cookie.
    try:
        decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await db.execute(delete(Session).where(Session.refresh_token == refresh_token))
        await db.commit()

    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
):
    user = await db.scalar(select(User).where(User.email == data.email))

    if user:
        user.reset_token = secrets.token_hex(32)
        user.reset_expires = datetime.now(timezone.utc) + timedelta(
            hours=RESET_TOKEN_EXPIRY_HOURS
        )
        send_email(
            to=user.email,
            subject="Reset your TriCore password",
            body=(
                f"Reset your password: "
                f"http://localhost:3000/reset-password?token={user.reset_token}\n"
                f"This link expires in {RESET_TOKEN_EXPIRY_HOURS} hour."
            ),
        )
        await db.commit()
    # else: silently no-op — anti-enumeration, matches contract docstring.

    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    user = await db.scalar(select(User).where(User.reset_token == data.token))

    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token.")

    if user.reset_expires and user.reset_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="Reset link has expired. Please request a new one."
        )

    user.password_hash = hash_password(data.new_password.get_secret_value())
    user.reset_token = None
    user.reset_expires = None
    # Also resetting lockout state on password reset — if the account was
    # locked from failed attempts, a successful password reset is a strong
    # signal the legitimate owner has regained control, so don't make them
    # wait out a stale lockout timer too.
    user.failed_logins = 0
    user.locked_until = None

    # Contract docstring says "invalidates all active sessions" — delete
    # every session for this user so any device logged in under the old
    # password is forced to log in again with the new one.
    await db.execute(delete(Session).where(Session.user_id == user.id))

    await db.commit()
    return MessageResponse(message="Password updated. Please log in.")