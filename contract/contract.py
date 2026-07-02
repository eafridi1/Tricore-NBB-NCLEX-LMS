"""
Nurses Beyond Borders — OpenAPI Contract  v1.0
==========================================
CONTRACT-FIRST: Every route returns FAKE data.
Real logic comes later. This file's job is to:
  1. Define every Pydantic request/response shape
  2. Declare every route with the correct HTTP method, path, and response_model
  3. Auto-generate /docs (Swagger UI) so the frontend has a live, testable spec

HOW TO RUN:
    pip install fastapi uvicorn python-jose passlib[bcrypt] stripe
    uvicorn contract:app --reload
    → open http://localhost:8000/docs

HOW TO USE WITH AI:
    When asking AI to build any React component or FastAPI handler, paste
    the relevant section of this file and say:
    "Implement the real logic for this route. Here is the contract it must satisfy."
    The AI will produce code that matches perfectly — no shape mismatches.

ROUTER PREFIXES:
    /auth          → authentication & account
    /users         → user profile & admin user management
    /subscriptions → plans & subscription management
    /payments      → Stripe/PayPal checkout & webhooks
    /categories    → NCLEX topic taxonomy
    /questions     → question bank (CRUD + workflow)
    /quizzes       → quiz engine (start, answer, submit, results)
    /videos        → video lectures
    /pdfs          → study materials
    /bookmarks     → saved questions
    /progress      → video watch progress
    /announcements → platform announcements
    /admin         → admin-only: analytics, sessions, security logs
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nurses Beyond Borders API",
    description=(
        "Contract-first OpenAPI spec for the Nurses Beyond Borders. "
        "All routes return fake data until real logic is wired in. "
        "Use /docs for interactive testing."
    ),
    version="1.0.0",
)

bearer = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED ENUMS  (mirror the PostgreSQL ENUM types exactly)
# ─────────────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    student  = "student"
    admin    = "admin"
    reviewer = "reviewer"

class LoginStatus(str, Enum):
    success         = "success"
    failed_password = "failed_password"
    failed_2fa      = "failed_2fa"
    blocked_ip      = "blocked_ip"
    blocked_geo     = "blocked_geo"
    account_locked  = "account_locked"

class SubStatus(str, Enum):
    active    = "active"
    grace     = "grace"
    expired   = "expired"
    cancelled = "cancelled"
    pending   = "pending"

class PayMethod(str, Enum):
    stripe = "stripe"
    paypal = "paypal"

class PayStatus(str, Enum):
    pending   = "pending"
    succeeded = "succeeded"
    failed    = "failed"
    refunded  = "refunded"

class Difficulty(str, Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"

class QStatus(str, Enum):
    draft      = "draft"
    in_review  = "in_review"
    published  = "published"
    archived   = "archived"

class AttemptStatus(str, Enum):
    in_progress = "in_progress"
    completed   = "completed"
    timed_out   = "timed_out"
    abandoned   = "abandoned"


# ─────────────────────────────────────────────────────────────────────────────
# SHARED UTILITY MODELS
# ─────────────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic success message."""
    message: str

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — AUTH
#  Tables: users · sessions · login_logs
#  Flows:  Registration, Login (+ 2FA), Refresh, Logout, Password Reset
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_auth = APIRouter(prefix="/auth", tags=["Auth"])

# ── Request / Response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:     str        = Field(..., min_length=2, max_length=120, example="Sarah Khan")
    email:    EmailStr   = Field(..., example="sarah@example.com")
    password: str        = Field(..., min_length=8, example="Secret123")

class RegisterResponse(BaseModel):
    message: str = "Account created. Check your email to verify."
    user_id: int

class LoginRequest(BaseModel):
    email:    EmailStr = Field(..., example="sarah@example.com")
    password: str      = Field(..., example="Secret123")

class LoginStep1Response(BaseModel):
    """Returned after correct password — 2FA code has been emailed."""
    status:  str = "otp_sent"
    message: str = "Check your email for a 6-digit code."

class TwoFAVerifyRequest(BaseModel):
    email: EmailStr = Field(..., example="sarah@example.com")
    otp: str = Field(..., min_length=6, max_length=6, example="482910")

class TokenResponse(BaseModel):
    """Full login success. refresh_token is sent as an HttpOnly cookie, not here."""
    access_token: str
    token_type:   str = "bearer"

class RefreshResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., example="a3f9c2...")

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token:        str = Field(..., example="reset_token_hex...")
    new_password: str = Field(..., min_length=8, example="NewSecret456")

# ── Routes ────────────────────────────────────────────────────────────────────

@router_auth.post("/register", response_model=RegisterResponse, status_code=201,
    summary="Register a new student account",
    description="Creates an inactive account and sends a verification email. "
                "Account cannot log in until email is verified.")
async def register(data: RegisterRequest):
    # TODO: check duplicate email, bcrypt password, insert users row,
    #       generate verify_token, send email
    return RegisterResponse(user_id=1)


@router_auth.get("/verify-email", response_model=MessageResponse,
    summary="Verify email address via token link",
    description="Student clicks the link in their email. "
                "Token must exist and not be expired (24h). "
                "Sets is_verified=TRUE, clears verify_token.")
async def verify_email(token: str):
    # TODO: validate token, update users row
    return MessageResponse(message="Email verified. You can now log in.")


@router_auth.post("/resend-verification", response_model=MessageResponse,
    summary="Resend email verification link",
    description="Generates a new verify_token (24h expiry) and resends the email. "
                "Silently succeeds even if email not found (no enumeration).")
async def resend_verification(data: ResendVerificationRequest):
    # TODO: generate new token, update users, send email
    return MessageResponse(message="Verification email sent if account exists.")


@router_auth.post("/login", response_model=LoginStep1Response,
    summary="Step 1 of login — verify password, trigger 2FA",
    description="Validates email + password. On success, generates and emails a 6-digit OTP. "
                "Returns 401 on bad credentials. Returns 429 if account is locked. "
                "Does NOT issue JWT yet — that happens at /auth/2fa-verify.")
async def login(data: LoginRequest, request: Request):
    # TODO: fetch user, check is_verified, check locked_until, bcrypt.verify,
    #       increment failed_logins on fail, generate OTP, email OTP,
    #       log to login_logs
    return LoginStep1Response()


@router_auth.post("/2fa-verify", response_model=TokenResponse,
    summary="Step 2 of login — submit OTP, receive JWT",
    description="Verifies the 6-digit OTP emailed in step 1. "
                "On success: enforces one-session policy, inserts sessions row, "
                "sets refresh_token as HttpOnly cookie, returns access_token in body.")
async def verify_2fa(data: TwoFAVerifyRequest, request: Request):
    # TODO: check OTP hash + expiry, clear OTP fields, delete old sessions,
    #       create new session, issue JWT, set cookie, log success
    return TokenResponse(access_token="fake.jwt.token")


@router_auth.post("/refresh", response_model=RefreshResponse,
    summary="Exchange refresh token cookie for a new access token",
    description="Reads refresh_token from HttpOnly cookie (NOT request body). "
                "Validates against sessions table. Returns a new 15-min access token.")
async def refresh(request: Request):
    # TODO: read cookie, look up session, check expiry, issue new access_token
    return RefreshResponse(access_token="fake.new.jwt.token")


@router_auth.post("/logout", response_model=MessageResponse,
    summary="Log out — invalidate current session",
    description="Deletes the sessions row for the current refresh token. "
                "Also clears the HttpOnly cookie.")
async def logout(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: read refresh_token from cookie, delete sessions row, clear cookie
    return MessageResponse(message="Logged out successfully.")


@router_auth.post("/forgot-password", response_model=MessageResponse,
    summary="Request a password reset email",
    description="Generates a reset_token (1h expiry) and emails a reset link. "
                "Always returns success to prevent email enumeration.")
async def forgot_password(data: ForgotPasswordRequest):
    # TODO: look up user, set reset_token + reset_expires, send email
    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router_auth.post("/reset-password", response_model=MessageResponse,
    summary="Reset password using emailed token",
    description="Validates reset_token is unexpired, hashes and stores the new password, "
                "clears reset_token, invalidates all active sessions.")
async def reset_password(data: ResetPasswordRequest):
    # TODO: validate token, bcrypt new password, update users, delete sessions
    return MessageResponse(message="Password updated. Please log in.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — USERS (Profile + Admin User Management)
#  Tables: users · login_logs
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_users = APIRouter(prefix="/users", tags=["Users"])

# ── Models ────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id:             int
    name:           str
    email:          str
    role:           UserRole
    is_verified:    bool
    is_active:      bool
    dark_mode:      bool
    two_fa_enabled: bool
    created_at:     datetime

class UpdateProfileRequest(BaseModel):
    name:      Optional[str] = Field(None, min_length=2, max_length=120)
    dark_mode: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str = Field(..., min_length=8)

class LoginLogOut(BaseModel):
    id:           int
    ip_address:   str
    country_code: Optional[str]
    user_agent:   Optional[str]
    status:       LoginStatus
    created_at:   datetime

class LoginLogsResponse(BaseModel):
    items: list[LoginLogOut]
    meta:  PaginationMeta

class UserListResponse(BaseModel):
    items: list[UserOut]
    meta:  PaginationMeta

class AdminUpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    role:      Optional[UserRole] = None

# ── Routes ────────────────────────────────────────────────────────────────────

@router_users.get("/me", response_model=UserOut,
    summary="Get own profile")
async def get_my_profile(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: decode JWT, fetch user row
    return UserOut(id=1, name="Sarah Khan", email="sarah@example.com",
                   role=UserRole.student, is_verified=True, is_active=True,
                   dark_mode=False, two_fa_enabled=True,
                   created_at=datetime.utcnow())


@router_users.patch("/me", response_model=UserOut,
    summary="Update own profile (name, dark_mode)")
async def update_my_profile(data: UpdateProfileRequest,
                             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: update users row
    return UserOut(id=1, name=data.name or "Sarah Khan", email="sarah@example.com",
                   role=UserRole.student, is_verified=True, is_active=True,
                   dark_mode=data.dark_mode or False, two_fa_enabled=True,
                   created_at=datetime.utcnow())


@router_users.post("/me/change-password", response_model=MessageResponse,
    summary="Change own password")
async def change_password(data: ChangePasswordRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: verify current_password, hash new_password, update users
    return MessageResponse(message="Password changed successfully.")


@router_users.get("/me/login-history", response_model=LoginLogsResponse,
    summary="Student: view own login history")
async def my_login_history(page: int = 1, per_page: int = 20,
                            credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: query login_logs WHERE user_id = current_user.id
    return LoginLogsResponse(
        items=[LoginLogOut(id=1, ip_address="203.0.113.1", country_code="PK",
                           user_agent="Chrome/125", status=LoginStatus.success,
                           created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


# ── Admin-only user management ────────────────────────────────────────────────

@router_users.get("", response_model=UserListResponse,
    summary="Admin: list all users",
    description="Requires admin role. Filterable by role and is_active.")
async def list_users(role: Optional[UserRole] = None, is_active: Optional[bool] = None,
                     page: int = 1, per_page: int = 20,
                     credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, query users with filters
    return UserListResponse(
        items=[UserOut(id=1, name="Sarah Khan", email="sarah@example.com",
                       role=UserRole.student, is_verified=True, is_active=True,
                       dark_mode=False, two_fa_enabled=True, created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_users.get("/{user_id}", response_model=UserOut,
    summary="Admin: get a specific user")
async def get_user(user_id: int,
                   credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, fetch user
    return UserOut(id=user_id, name="Sarah Khan", email="sarah@example.com",
                   role=UserRole.student, is_verified=True, is_active=True,
                   dark_mode=False, two_fa_enabled=True, created_at=datetime.utcnow())


@router_users.patch("/{user_id}", response_model=UserOut,
    summary="Admin: update user role or active status")
async def admin_update_user(user_id: int, data: AdminUpdateUserRequest,
                             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, update users row
    return UserOut(id=user_id, name="Sarah Khan", email="sarah@example.com",
                   role=UserRole.student, is_verified=True,
                   is_active=data.is_active if data.is_active is not None else True,
                   dark_mode=False, two_fa_enabled=True, created_at=datetime.utcnow())


@router_users.get("/{user_id}/login-history", response_model=LoginLogsResponse,
    summary="Admin: view any user's login history")
async def admin_user_login_history(user_id: int, page: int = 1, per_page: int = 20,
                                    credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, query login_logs
    return LoginLogsResponse(
        items=[LoginLogOut(id=1, ip_address="203.0.113.1", country_code="PK",
                           user_agent="Chrome/125", status=LoginStatus.success,
                           created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — SUBSCRIPTIONS & PLANS
#  Tables: plans · subscriptions
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_subscriptions = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# ── Models ────────────────────────────────────────────────────────────────────

class PlanOut(BaseModel):
    id:            int
    name:          str
    price_cents:   int
    currency:      str
    duration_days: int
    description:   Optional[str]
    is_active:     bool

class PlanCreateRequest(BaseModel):
    name:          str           = Field(..., example="3-Month Access")
    price_cents:   int           = Field(..., example=8999, description="$89.99 = 8999")
    currency:      str           = Field("USD", max_length=3)
    duration_days: int           = Field(..., example=90)
    description:   Optional[str] = None

class SubscriptionOut(BaseModel):
    id:           int
    user_id:      int
    plan:         PlanOut
    status:       SubStatus
    start_date:   datetime
    end_date:     datetime
    grace_until:  Optional[datetime]
    cancelled_at: Optional[datetime]
    created_at:   datetime

class SubscriptionCheckResponse(BaseModel):
    """Used on every protected page load to confirm access."""
    has_access:   bool
    status:       Optional[SubStatus]
    end_date:     Optional[datetime]
    days_remaining: Optional[int]

class AdminManageSubRequest(BaseModel):
    status:   Optional[SubStatus] = None
    end_date: Optional[datetime]  = None

# ── Routes ────────────────────────────────────────────────────────────────────

@router_subscriptions.get("/plans", response_model=list[PlanOut],
    summary="List all active subscription plans",
    description="Public endpoint — no auth required. Returns plans with is_active=TRUE.")
async def list_plans():
    # TODO: SELECT from plans WHERE is_active=TRUE
    return [PlanOut(id=1, name="1-Month Access", price_cents=2999,
                    currency="USD", duration_days=30,
                    description="Full access to the question bank for 30 days.",
                    is_active=True)]


@router_subscriptions.post("/plans", response_model=PlanOut, status_code=201,
    summary="Admin: create a new subscription plan")
async def create_plan(data: PlanCreateRequest,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, insert plans row
    return PlanOut(id=2, **data.model_dump(), is_active=True)


@router_subscriptions.patch("/plans/{plan_id}", response_model=PlanOut,
    summary="Admin: update a subscription plan")
async def update_plan(plan_id: int, data: PlanCreateRequest,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, update plans row
    return PlanOut(id=plan_id, **data.model_dump(), is_active=True)


@router_subscriptions.get("/check", response_model=SubscriptionCheckResponse,
    summary="Check own subscription / access status",
    description="Frontend calls this on every protected page load. "
                "Returns has_access=True only if status='active' AND end_date > NOW().")
async def check_subscription(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: query subscriptions for current user
    return SubscriptionCheckResponse(has_access=True, status=SubStatus.active,
                                      end_date=datetime.utcnow(), days_remaining=28)


@router_subscriptions.get("/me", response_model=list[SubscriptionOut],
    summary="Student: view own subscription history")
async def my_subscriptions(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: query subscriptions WHERE user_id = current_user
    fake_plan = PlanOut(id=1, name="1-Month Access", price_cents=2999, currency="USD",
                        duration_days=30, description=None, is_active=True)
    return [SubscriptionOut(id=1, user_id=1, plan=fake_plan, status=SubStatus.active,
                             start_date=datetime.utcnow(), end_date=datetime.utcnow(),
                             grace_until=None, cancelled_at=None, created_at=datetime.utcnow())]


@router_subscriptions.get("/{user_id}", response_model=list[SubscriptionOut],
    summary="Admin: view any user's subscription history")
async def admin_user_subscriptions(user_id: int,
                                    credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, query subscriptions WHERE user_id = user_id
    fake_plan = PlanOut(id=1, name="1-Month Access", price_cents=2999, currency="USD",
                        duration_days=30, description=None, is_active=True)
    return [SubscriptionOut(id=1, user_id=user_id, plan=fake_plan, status=SubStatus.active,
                             start_date=datetime.utcnow(), end_date=datetime.utcnow(),
                             grace_until=None, cancelled_at=None, created_at=datetime.utcnow())]


@router_subscriptions.patch("/{subscription_id}/admin", response_model=SubscriptionOut,
    summary="Admin: manually adjust a subscription (extend, cancel, force-activate)",
    description="Emergency override for failed webhook or support requests.")
async def admin_update_subscription(subscription_id: int, data: AdminManageSubRequest,
                                     credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, update subscriptions row
    fake_plan = PlanOut(id=1, name="1-Month Access", price_cents=2999, currency="USD",
                        duration_days=30, description=None, is_active=True)
    return SubscriptionOut(id=subscription_id, user_id=1, plan=fake_plan,
                            status=data.status or SubStatus.active,
                            start_date=datetime.utcnow(),
                            end_date=data.end_date or datetime.utcnow(),
                            grace_until=None, cancelled_at=None, created_at=datetime.utcnow())


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — PAYMENTS
#  Tables: payments
#  Flows:  Stripe Checkout, Stripe Webhook, PayPal (stub), Payment History
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_payments = APIRouter(prefix="/payments", tags=["Payments"])

# ── Models ────────────────────────────────────────────────────────────────────

class StripeCheckoutRequest(BaseModel):
    plan_id: int = Field(..., example=1)

class StripeCheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="Redirect the student to this Stripe-hosted URL.")
    session_id:   str

class PaymentOut(BaseModel):
    id:              int
    user_id:         int
    subscription_id: Optional[int]
    amount_cents:    int
    currency:        str
    method:          PayMethod
    status:          PayStatus
    provider_ref:    Optional[str]
    created_at:      datetime

class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    meta:  PaginationMeta

# ── Routes ────────────────────────────────────────────────────────────────────

@router_payments.post("/stripe-checkout", response_model=StripeCheckoutResponse,
    summary="Create a Stripe Checkout session",
    description="Student selects a plan and is redirected to Stripe's hosted checkout page. "
                "Zero card data touches our server. "
                "Access is granted by the webhook, NOT by this response.")
async def stripe_checkout(data: StripeCheckoutRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: check no existing active sub, call stripe.checkout.sessions.create(),
    #       return checkout_url
    return StripeCheckoutResponse(
        checkout_url="https://checkout.stripe.com/pay/cs_test_fake",
        session_id="cs_test_fake_session_id")


@router_payments.post("/stripe-webhook", status_code=200,
    summary="Stripe webhook receiver — DO NOT call from frontend",
    description="Stripe POSTs signed events here. "
                "Always verify the Stripe-Signature header before processing. "
                "Handles: checkout.session.completed → grant access. "
                "payment_intent.payment_failed → log failure. "
                "Must return 200 within 30s or Stripe retries.")
async def stripe_webhook(request: Request):
    # TODO: read raw body, stripe.webhooks.constructEvent(body, sig, secret),
    #       check provider_ref idempotency, insert subscriptions + payments rows
    return {"received": True}


@router_payments.post("/paypal-order", response_model=dict,
    summary="[Phase 1.1] Create a PayPal order — stub only",
    description="Not active in MVP. Returns 501 until PayPal is enabled.")
async def paypal_order(data: StripeCheckoutRequest,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: Phase 1.1 — paypalrestsdk or httpx call to PayPal Orders v2 API
    return {"status": "not_implemented", "message": "PayPal coming in Phase 1.1"}


@router_payments.post("/paypal-webhook", status_code=200,
    summary="[Phase 1.1] PayPal webhook receiver — stub only")
async def paypal_webhook(request: Request):
    # TODO: Phase 1.1 — verify PayPal-Transmission-Sig, grant access
    return {"received": True}


@router_payments.get("/me", response_model=PaymentListResponse,
    summary="Student: view own payment history")
async def my_payment_history(page: int = 1, per_page: int = 20,
                              credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: query payments WHERE user_id = current_user
    return PaymentListResponse(
        items=[PaymentOut(id=1, user_id=1, subscription_id=1, amount_cents=2999,
                          currency="USD", method=PayMethod.stripe, status=PayStatus.succeeded,
                          provider_ref="evt_stripe_fake", created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_payments.get("/{user_id}", response_model=PaymentListResponse,
    summary="Admin: view any user's payment history")
async def admin_payment_history(user_id: int, page: int = 1, per_page: int = 20,
                                 credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, query payments WHERE user_id = user_id
    return PaymentListResponse(
        items=[PaymentOut(id=1, user_id=user_id, subscription_id=1, amount_cents=2999,
                          currency="USD", method=PayMethod.stripe, status=PayStatus.succeeded,
                          provider_ref="evt_stripe_fake", created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — CATEGORIES
#  Table: categories
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_categories = APIRouter(prefix="/categories", tags=["Categories"])

class CategoryOut(BaseModel):
    id:             int
    name:           str
    description:    Optional[str]
    sort_order:     int
    question_count: Optional[int] = None  # included when listing for quiz setup

class CategoryCreateRequest(BaseModel):
    name:        str           = Field(..., example="Cardiovascular")
    description: Optional[str] = None
    sort_order:  int           = 0


@router_categories.get("", response_model=list[CategoryOut],
    summary="List all categories",
    description="Public endpoint. question_count included when ?include_count=true.")
async def list_categories(include_count: bool = False):
    # TODO: SELECT categories, optionally JOIN questions count
    return [CategoryOut(id=1, name="Cardiovascular", description=None,
                         sort_order=1, question_count=120 if include_count else None)]


@router_categories.post("", response_model=CategoryOut, status_code=201,
    summary="Admin: create a category")
async def create_category(data: CategoryCreateRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, insert categories row
    return CategoryOut(id=2, **data.model_dump(), question_count=0)


@router_categories.patch("/{category_id}", response_model=CategoryOut,
    summary="Admin: update a category")
async def update_category(category_id: int, data: CategoryCreateRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, update categories row
    return CategoryOut(id=category_id, **data.model_dump())


@router_categories.delete("/{category_id}", response_model=MessageResponse,
    summary="Admin: delete a category",
    description="Only allowed if no questions reference this category.")
async def delete_category(category_id: int,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, check FK constraints, delete
    return MessageResponse(message="Category deleted.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — QUESTIONS
#  Table: questions
#  Workflow: draft → in_review → published → archived
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_questions = APIRouter(prefix="/questions", tags=["Questions"])

# ── Models ────────────────────────────────────────────────────────────────────

class QuestionOption(BaseModel):
    text: str = Field(..., example="Administer oxygen immediately")

class QuestionOut(BaseModel):
    id:             int
    stem:           str
    options:        list[QuestionOption]   # always 4 items, index 0–3 = A–D
    correct_answer: Optional[int]          # None for students during active quiz
    rationale:      Optional[str]          # None for students during active quiz
    category_id:    int
    nclex_domain:   str
    difficulty:     Difficulty
    status:         QStatus
    reviewed_by:    Optional[int]
    reviewed_at:    Optional[datetime]
    created_by:     int
    created_at:     datetime
    updated_at:     datetime
    is_deleted:      Optional[bool] = False  # soft delete flag

class QuestionListResponse(BaseModel):
    items: list[QuestionOut]
    meta:  PaginationMeta

class QuestionCreateRequest(BaseModel):
    stem:           str               = Field(..., example="A nurse is caring for a patient...")
    options:        list[QuestionOption] = Field(..., min_length=4, max_length=4)
    correct_answer: int               = Field(..., ge=0, le=3, example=1)
    rationale:      str               = Field(..., example="Option B is correct because...")
    category_id:    int               = Field(..., example=1)
    nclex_domain:   str               = Field(..., example="Safe and Effective Care Environment")
    difficulty:     Difficulty        = Field(..., example=Difficulty.medium)

class QuestionUpdateRequest(BaseModel):
    stem:           Optional[str]                = None
    options:        Optional[list[QuestionOption]] = None
    correct_answer: Optional[int]               = Field(None, ge=0, le=3)
    rationale:      Optional[str]               = None
    category_id:    Optional[int]               = None
    nclex_domain:   Optional[str]               = None
    difficulty:     Optional[Difficulty]        = None

class QuestionStatusUpdateRequest(BaseModel):
    status: QStatus = Field(..., description="Target workflow state.")

class BulkImportResponse(BaseModel):
    imported: int
    errors:   list[dict[str, Any]]  # [{row: 3, error: "Missing rationale"}, ...]

# ── Routes ────────────────────────────────────────────────────────────────────

@router_questions.get("", response_model=QuestionListResponse,
    summary="List / filter questions",
    description="Students see only published questions. "
                "Admins/reviewers see all statuses. "
                "Filter by category_id, difficulty, status, nclex_domain.")
async def list_questions(
    category_id:  Optional[int]        = None,
    difficulty:   Optional[Difficulty] = None,
    status:       Optional[QStatus]    = None,
    nclex_domain: Optional[str]        = None,
    page:         int = 1,
    per_page:     int = 20,
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
):
    # TODO: subscription check for students, build filter query
    fake_q = QuestionOut(
        id=1, stem="A nurse is assessing a patient with chest pain...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=1, rationale="Option B is correct because...",
        category_id=1, nclex_domain="Safe Care", difficulty=Difficulty.medium,
        status=QStatus.published, reviewed_by=2, reviewed_at=datetime.utcnow(),
        created_by=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    return QuestionListResponse(items=[fake_q],
                                 meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_questions.post("", response_model=QuestionOut, status_code=201,
    summary="Admin/Reviewer: create a new question (starts as draft)")
async def create_question(data: QuestionCreateRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin/reviewer guard, insert questions row with status='draft'
    return QuestionOut(id=1, **data.model_dump(), correct_answer=data.correct_answer,
                        status=QStatus.draft, reviewed_by=None, reviewed_at=None,
                        created_by=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow())


@router_questions.get("/{question_id}", response_model=QuestionOut,
    summary="Get a single question",
    description="Students only see published questions and do NOT receive correct_answer or rationale "
                "outside of review mode. Those fields are stripped in the handler.")
async def get_question(question_id: int,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: fetch question, role-based field stripping
    return QuestionOut(
        id=question_id, stem="A nurse is assessing...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=None, rationale=None,
        category_id=1, nclex_domain="Safe Care", difficulty=Difficulty.medium,
        status=QStatus.published, reviewed_by=2, reviewed_at=datetime.utcnow(),
        created_by=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow())


@router_questions.patch("/{question_id}", response_model=QuestionOut,
    summary="Admin/Reviewer: edit a question",
    description="Edits are logged/versioned. Editing a published question sets status back to in_review.")
async def update_question(question_id: int, data: QuestionUpdateRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin/reviewer guard, update questions row, log change
    return QuestionOut(
        id=question_id, stem=data.stem or "Updated stem...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=data.correct_answer, rationale=data.rationale,
        category_id=data.category_id or 1, nclex_domain=data.nclex_domain or "Safe Care",
        difficulty=data.difficulty or Difficulty.medium,
        status=QStatus.in_review, reviewed_by=None, reviewed_at=None,
        created_by=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow())


@router_questions.patch("/{question_id}/status", response_model=QuestionOut,
    summary="Admin/Reviewer: advance or revert question workflow status",
    description="Enforces valid transitions: draft→in_review, in_review→published, "
                "published→archived. Sets reviewed_by and reviewed_at when publishing.")
async def update_question_status(question_id: int, data: QuestionStatusUpdateRequest,
                                  credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: check valid transition, set reviewed_by if publishing, update status
    return QuestionOut(
        id=question_id, stem="Some question...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=1, rationale="Because...",
        category_id=1, nclex_domain="Safe Care", difficulty=Difficulty.medium,
        status=data.status, reviewed_by=2, reviewed_at=datetime.utcnow(),
        created_by=2, created_at=datetime.utcnow(), updated_at=datetime.utcnow())


@router_questions.post("/bulk-import", response_model=BulkImportResponse,
    summary="Admin: bulk import questions from CSV",
    description="Validates every row before inserting any. "
                "Returns row-by-row errors on validation failure. "
                "All imported questions start as status='draft'.")
async def bulk_import_questions(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, parse CSV file upload, validate rows, batch insert
    # This will be a multipart/form-data upload — update once implementing
    return BulkImportResponse(imported=0, errors=[{"row": 1, "error": "Not yet implemented"}])


@router_questions.post("/{question_id}/bookmark", response_model=MessageResponse,
    summary="Student: bookmark a question",
    description="Idempotent — bookmarking an already-bookmarked question returns 200, not an error.")
async def bookmark_question(question_id: int,
                             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: INSERT INTO bookmarks ON CONFLICT DO NOTHING
    return MessageResponse(message="Bookmarked.")


@router_questions.delete("/{question_id}/bookmark", response_model=MessageResponse,
    summary="Student: remove a bookmark")
async def unbookmark_question(question_id: int,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: DELETE FROM bookmarks WHERE user_id AND question_id
    return MessageResponse(message="Bookmark removed.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — BOOKMARKS
#  Table: bookmarks
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_bookmarks = APIRouter(prefix="/bookmarks", tags=["Bookmarks"])

class BookmarkOut(BaseModel):
    id:          int
    question_id: int
    created_at:  datetime

class BookmarkListResponse(BaseModel):
    items: list[BookmarkOut]
    meta:  PaginationMeta


@router_bookmarks.get("", response_model=BookmarkListResponse,
    summary="Student: list own bookmarked questions")
async def list_bookmarks(page: int = 1, per_page: int = 20,
                          credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: SELECT FROM bookmarks WHERE user_id = current_user, JOIN questions if needed
    return BookmarkListResponse(
        items=[BookmarkOut(id=1, question_id=42, created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — QUIZ ENGINE
#  Table: quiz_attempts
#  Flows: Start quiz, answer per-question (auto-save), submit, results, resume
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_quizzes = APIRouter(prefix="/quizzes", tags=["Quizzes"])

# ── Models ────────────────────────────────────────────────────────────────────

class QuizStartRequest(BaseModel):
    category_id:      Optional[int]        = Field(None,  description="NULL = all categories")
    difficulty:       Optional[Difficulty] = Field(None,  description="NULL = mixed")
    question_count:   int                  = Field(25,    ge=5, le=100)
    timed:            bool                 = Field(False)
    time_limit_secs:  Optional[int]        = Field(None,  example=2700,
                                                   description="Required if timed=true. 2700=45min")

class QuizStartResponse(BaseModel):
    attempt_id:       int
    total_questions:  int
    time_limit_secs:  Optional[int]
    status:           AttemptStatus

class QuizQuestionResponse(BaseModel):
    """A single question as served during an active quiz — NO correct_answer or rationale."""
    attempt_id:      int
    question_index:  int             # 0-based position in this quiz
    total_questions: int
    question_id:     int
    stem:            str
    options:         list[QuestionOption]
    category_name:   str
    difficulty:      Difficulty
    is_bookmarked:   bool
    time_remaining_secs: Optional[int]  # None if untimed
    already_answered:    Optional[int]  # previously saved answer index, or None

class AnswerRequest(BaseModel):
    question_id:  int = Field(..., example=42)
    chosen_index: int = Field(..., ge=0, le=3, example=1)

class AnswerResponse(BaseModel):
    """Auto-save confirmation. No scoring info yet."""
    saved: bool

class QuizResumeResponse(BaseModel):
    attempt_id:          int
    status:              AttemptStatus
    answered_count:      int
    total_questions:     int
    time_remaining_secs: Optional[int]

class QuestionResult(BaseModel):
    question_id:    int
    stem:           str
    options:        list[QuestionOption]
    correct_answer: int
    chosen_answer:  Optional[int]
    is_correct:     bool
    rationale:      str
    category_name:  str
    difficulty:     Difficulty

class QuizResultResponse(BaseModel):
    attempt_id:      int
    score:           float             # 0.0–100.0
    correct_count:   int
    total_questions: int
    passed:          bool              # score >= 60 by default
    time_taken_secs: Optional[int]
    status:          AttemptStatus
    questions:       list[QuestionResult]

class AttemptSummaryOut(BaseModel):
    attempt_id:      int
    score:           Optional[float]
    correct_count:   Optional[int]
    total_questions: int
    status:          AttemptStatus
    time_taken_secs: Optional[int]
    started_at:      datetime
    finished_at:     Optional[datetime]
    category_name:   Optional[str]

class AttemptListResponse(BaseModel):
    items: list[AttemptSummaryOut]
    meta:  PaginationMeta

# ── Routes ────────────────────────────────────────────────────────────────────

@router_quizzes.post("", response_model=QuizStartResponse, status_code=201,
    summary="Start a new quiz or mock exam",
    description="Checks for in-progress attempts first. "
                "Generates question list with ORDER BY RANDOM(). "
                "Inserts quiz_attempts row with status='in_progress'.")
async def start_quiz(data: QuizStartRequest,
                      credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, check in-progress attempts, SELECT question ids,
    #       INSERT quiz_attempts
    return QuizStartResponse(attempt_id=1, total_questions=data.question_count,
                              time_limit_secs=data.time_limit_secs,
                              status=AttemptStatus.in_progress)


@router_quizzes.get("/{attempt_id}/question/{index}", response_model=QuizQuestionResponse,
    summary="Get a specific question in an active quiz",
    description="index is 0-based. Student can navigate forwards and backwards. "
                "Never returns correct_answer or rationale.")
async def get_quiz_question(attempt_id: int, index: int,
                             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: validate attempt belongs to user, fetch question at index from attempt.questions,
    #       compute time_remaining, check bookmark status
    return QuizQuestionResponse(
        attempt_id=attempt_id, question_index=index, total_questions=25,
        question_id=42, stem="A nurse is assessing a patient who...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        category_name="Cardiovascular", difficulty=Difficulty.medium,
        is_bookmarked=False, time_remaining_secs=None, already_answered=None)


@router_quizzes.post("/{attempt_id}/answer", response_model=AnswerResponse,
    summary="Auto-save an answer during a quiz",
    description="Called after every answer selection. "
                "Updates the answers JSONB column. "
                "Idempotent — calling again with a different answer overwrites.")
async def save_answer(attempt_id: int, data: AnswerRequest,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: validate attempt is in_progress and belongs to user, check timed expiry,
    #       UPDATE quiz_attempts SET answers = answers || {q_id: chosen}
    return AnswerResponse(saved=True)


@router_quizzes.post("/{attempt_id}/finish", response_model=QuizResultResponse,
    summary="Submit and score a quiz",
    description="Shows confirmation modal count on frontend before calling. "
                "Scores all questions, updates status='completed'. "
                "Returns full results including correct answers and rationales.")
async def finish_quiz(attempt_id: int,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: validate in_progress + ownership, score questions, UPDATE attempt to completed
    fake_result = QuestionResult(
        question_id=42, stem="A nurse is assessing...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=1, chosen_answer=1, is_correct=True,
        rationale="Option B is correct because...",
        category_name="Cardiovascular", difficulty=Difficulty.medium)
    return QuizResultResponse(attempt_id=attempt_id, score=84.0, correct_count=21,
                               total_questions=25, passed=True, time_taken_secs=1800,
                               status=AttemptStatus.completed, questions=[fake_result])


@router_quizzes.get("/{attempt_id}/resume", response_model=QuizResumeResponse,
    summary="Resume an in-progress quiz",
    description="Called on page reload or reconnect. "
                "Returns current state if within 30-minute window. "
                "Returns 409 if attempt has timed out or been abandoned.")
async def resume_quiz(attempt_id: int,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: validate in_progress, check 30-min window, return current state
    return QuizResumeResponse(attempt_id=attempt_id, status=AttemptStatus.in_progress,
                               answered_count=12, total_questions=25,
                               time_remaining_secs=1100)


@router_quizzes.get("/{attempt_id}/result", response_model=QuizResultResponse,
    summary="Get the full result for a completed attempt",
    description="For review mode — shows all answers, correct answers, and rationales. "
                "Students can only view their own attempts.")
async def get_quiz_result(attempt_id: int,
                           credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: validate attempt completed + ownership, return full result
    fake_result = QuestionResult(
        question_id=42, stem="A nurse is assessing...",
        options=[QuestionOption(text=f"Option {x}") for x in ["A","B","C","D"]],
        correct_answer=1, chosen_answer=1, is_correct=True,
        rationale="Option B is correct because...",
        category_name="Cardiovascular", difficulty=Difficulty.medium)
    return QuizResultResponse(attempt_id=attempt_id, score=84.0, correct_count=21,
                               total_questions=25, passed=True, time_taken_secs=1800,
                               status=AttemptStatus.completed, questions=[fake_result])


@router_quizzes.get("", response_model=AttemptListResponse,
    summary="List own quiz attempt history",
    description="Sortable by date. Shows score, category, status per attempt.")
async def list_my_attempts(page: int = 1, per_page: int = 20,
                            credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: SELECT from quiz_attempts WHERE user_id = current_user ORDER BY started_at DESC
    return AttemptListResponse(
        items=[AttemptSummaryOut(attempt_id=1, score=84.0, correct_count=21,
                                  total_questions=25, status=AttemptStatus.completed,
                                  time_taken_secs=1800, started_at=datetime.utcnow(),
                                  finished_at=datetime.utcnow(), category_name="Cardiovascular")],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_quizzes.get("/admin/{user_id}", response_model=AttemptListResponse,
    summary="Admin: list any user's quiz attempts")
async def admin_list_attempts(user_id: int, page: int = 1, per_page: int = 20,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, query quiz_attempts WHERE user_id = user_id
    return AttemptListResponse(
        items=[AttemptSummaryOut(attempt_id=1, score=84.0, correct_count=21,
                                  total_questions=25, status=AttemptStatus.completed,
                                  time_taken_secs=1800, started_at=datetime.utcnow(),
                                  finished_at=datetime.utcnow(), category_name=None)],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — VIDEOS
#  Tables: videos · video_progress
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_videos = APIRouter(prefix="/videos", tags=["Videos"])

# ── Models ────────────────────────────────────────────────────────────────────

class VideoOut(BaseModel):
    id:            int
    title:         str
    description:   Optional[str]
    category_id:   int
    thumbnail_url: Optional[str]
    duration_secs: Optional[int]
    sort_order:    int
    is_published:  bool
    created_at:    datetime

class VideoWithProgress(VideoOut):
    percent_watched: float  # 0.0–100.0
    stream_url:      str    # signed URL, expires in ~1h

class VideoListResponse(BaseModel):
    items: list[VideoOut]
    meta:  PaginationMeta

class VideoCreateRequest(BaseModel):
    title:         str           = Field(..., example="Cardiovascular Assessment")
    description:   Optional[str] = None
    category_id:   int
    storage_url:   str           = Field(..., description="Object storage path (not a public URL)")
    thumbnail_url: Optional[str] = None
    duration_secs: Optional[int] = None
    sort_order:    int           = 0

class VideoProgressRequest(BaseModel):
    percent_watched: float = Field(..., ge=0.0, le=100.0, example=45.5)

# ── Routes ────────────────────────────────────────────────────────────────────

@router_videos.get("", response_model=VideoListResponse,
    summary="List published videos",
    description="Requires active subscription for students. "
                "Filter by category_id. Results ordered by sort_order.")
async def list_videos(category_id: Optional[int] = None, page: int = 1, per_page: int = 20,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, SELECT videos WHERE is_published=TRUE
    return VideoListResponse(
        items=[VideoOut(id=1, title="Cardiovascular Assessment", description=None,
                         category_id=1, thumbnail_url=None, duration_secs=1800,
                         sort_order=1, is_published=True, created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_videos.get("/{video_id}", response_model=VideoWithProgress,
    summary="Get a video with a signed streaming URL and watch progress",
    description="Generates a time-limited signed URL for the video stream. "
                "Includes the student's current watch progress.")
async def get_video(video_id: int,
                     credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, fetch video, generate signed URL, fetch video_progress
    return VideoWithProgress(id=video_id, title="Cardiovascular Assessment",
                              description=None, category_id=1, thumbnail_url=None,
                              duration_secs=1800, sort_order=1, is_published=True,
                              created_at=datetime.utcnow(), percent_watched=0.0,
                              stream_url="https://storage.example.com/signed-url-here")


@router_videos.post("/{video_id}/progress", response_model=MessageResponse,
    summary="Update watch progress for a video",
    description="Called by the video player periodically. "
                "Uses INSERT ... ON CONFLICT DO UPDATE (upsert). "
                "One row per (user, video) pair in video_progress table.")
async def update_video_progress(video_id: int, data: VideoProgressRequest,
                                  credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: UPSERT into video_progress
    return MessageResponse(message="Progress saved.")


@router_videos.post("", response_model=VideoOut, status_code=201,
    summary="Admin: upload a new video record")
async def create_video(data: VideoCreateRequest,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, insert videos row (storage upload handled separately)
    return VideoOut(id=2, **data.model_dump(), is_published=False, created_at=datetime.utcnow())


@router_videos.patch("/{video_id}", response_model=VideoOut,
    summary="Admin: update video metadata or publish/unpublish")
async def update_video(video_id: int, data: VideoCreateRequest,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, UPDATE videos row
    return VideoOut(id=video_id, **data.model_dump(), is_published=True, created_at=datetime.utcnow())


@router_videos.delete("/{video_id}", response_model=MessageResponse,
    summary="Admin: delete a video")
async def delete_video(video_id: int,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, DELETE videos row (and storage object separately)
    return MessageResponse(message="Video deleted.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — PDFs / STUDY MATERIALS
#  Table: pdfs
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_pdfs = APIRouter(prefix="/pdfs", tags=["PDFs"])

class PDFOut(BaseModel):
    id:           int
    title:        str
    description:  Optional[str]
    category_id:  int
    sort_order:   int
    is_published: bool
    created_at:   datetime

class PDFDownloadResponse(BaseModel):
    """Signed, watermarked URL. Expires in 60 minutes."""
    download_url: str
    expires_at:   datetime
    filename:     str

class PDFCreateRequest(BaseModel):
    title:        str           = Field(..., example="Cardiovascular Pharmacology Notes")
    description:  Optional[str] = None
    category_id:  int
    storage_url:  str
    sort_order:   int           = 0

class PDFListResponse(BaseModel):
    items: list[PDFOut]
    meta:  PaginationMeta


@router_pdfs.get("", response_model=PDFListResponse,
    summary="List published PDFs",
    description="Requires active subscription. Filter by category_id.")
async def list_pdfs(category_id: Optional[int] = None, page: int = 1, per_page: int = 20,
                     credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, SELECT pdfs WHERE is_published=TRUE
    return PDFListResponse(
        items=[PDFOut(id=1, title="Cardiovascular Notes", description=None,
                       category_id=1, sort_order=1, is_published=True,
                       created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=20, pages=1))


@router_pdfs.get("/{pdf_id}/download", response_model=PDFDownloadResponse,
    summary="Get a signed download URL for a watermarked PDF",
    description="Generates a 60-minute signed URL. "
                "PDF is watermarked server-side with student name, email, and timestamp. "
                "Watermarking happens on first request and is cached.")
async def download_pdf(pdf_id: int,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, fetch pdf, watermark with student info, generate signed URL
    return PDFDownloadResponse(
        download_url="https://storage.example.com/signed-watermarked-pdf",
        expires_at=datetime.utcnow(),
        filename="cardiovascular-notes-sarah-khan.pdf")


@router_pdfs.post("", response_model=PDFOut, status_code=201,
    summary="Admin: create a PDF record")
async def create_pdf(data: PDFCreateRequest,
                      credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, INSERT pdfs row
    return PDFOut(id=2, **data.model_dump(), is_published=False, created_at=datetime.utcnow())


@router_pdfs.patch("/{pdf_id}", response_model=PDFOut,
    summary="Admin: update PDF metadata or publish/unpublish")
async def update_pdf(pdf_id: int, data: PDFCreateRequest,
                      credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, UPDATE pdfs row
    return PDFOut(id=pdf_id, **data.model_dump(), is_published=True, created_at=datetime.utcnow())


@router_pdfs.delete("/{pdf_id}", response_model=MessageResponse,
    summary="Admin: delete a PDF")
async def delete_pdf(pdf_id: int,
                      credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, DELETE pdfs row
    return MessageResponse(message="PDF deleted.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 11 — ANNOUNCEMENTS
#  Table: announcements
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_announcements = APIRouter(prefix="/announcements", tags=["Announcements"])

class AnnouncementOut(BaseModel):
    id:           int
    title:        str
    body:         str
    is_published: bool
    published_at: Optional[datetime]
    created_by:   int
    created_at:   datetime

class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementOut]
    meta:  PaginationMeta

class AnnouncementCreateRequest(BaseModel):
    title:        str  = Field(..., example="Platform Maintenance – June 22")
    body:         str  = Field(..., example="The platform will be unavailable for 2 hours...")
    is_published: bool = False


@router_announcements.get("", response_model=AnnouncementListResponse,
    summary="List published announcements",
    description="Students see only is_published=TRUE. Admins see all.")
async def list_announcements(page: int = 1, per_page: int = 10,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: role-based filter on is_published
    return AnnouncementListResponse(
        items=[AnnouncementOut(id=1, title="Welcome!", body="Platform is live.",
                                is_published=True, published_at=datetime.utcnow(),
                                created_by=2, created_at=datetime.utcnow())],
        meta=PaginationMeta(total=1, page=1, per_page=10, pages=1))


@router_announcements.post("", response_model=AnnouncementOut, status_code=201,
    summary="Admin: create an announcement")
async def create_announcement(data: AnnouncementCreateRequest,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, INSERT announcements row
    return AnnouncementOut(id=2, **data.model_dump(), published_at=datetime.utcnow() if data.is_published else None,
                            created_by=2, created_at=datetime.utcnow())


@router_announcements.patch("/{announcement_id}", response_model=AnnouncementOut,
    summary="Admin: edit or publish/unpublish an announcement")
async def update_announcement(announcement_id: int, data: AnnouncementCreateRequest,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, UPDATE announcements row
    return AnnouncementOut(id=announcement_id, **data.model_dump(),
                            published_at=datetime.utcnow(), created_by=2,
                            created_at=datetime.utcnow())


@router_announcements.delete("/{announcement_id}", response_model=MessageResponse,
    summary="Admin: delete an announcement")
async def delete_announcement(announcement_id: int,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, DELETE announcements row
    return MessageResponse(message="Announcement deleted.")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 12 — ADMIN DASHBOARD
#  Covers: analytics, security (IP whitelist, sessions), at-risk alerts
# ══════════════════════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────

router_admin = APIRouter(prefix="/admin", tags=["Admin"])

# ── Models ────────────────────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    total_students:      int
    active_subscribers:  int
    total_questions:     int
    published_questions: int
    total_attempts_today: int
    revenue_this_month_cents: int

class WeakAreaRow(BaseModel):
    category_name: str
    avg_score:     float
    attempt_count: int

class StudentAnalyticsResponse(BaseModel):
    user_id:          int
    avg_score:        float
    total_attempts:   int
    weak_areas:       list[WeakAreaRow]
    score_trend:      list[dict]  # [{date, score}, ...]
    is_at_risk:       bool       # avg_score < 60 on last 5 attempts

class AtRiskStudent(BaseModel):
    user_id:    int
    name:       str
    email:      str
    avg_score:  float
    last_attempt: datetime

class IPWhitelistEntry(BaseModel):
    id:         int
    ip_cidr:    str
    label:      Optional[str]
    created_by: int
    created_at: datetime

class IPWhitelistCreateRequest(BaseModel):
    ip_cidr: str  = Field(..., example="203.0.113.0/24")
    label:   Optional[str] = Field(None, example="Office Islamabad")

# ── Routes ────────────────────────────────────────────────────────────────────

@router_admin.get("/stats", response_model=DashboardStatsResponse,
    summary="Admin: platform-wide summary statistics")
async def admin_stats(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only guard, run aggregate queries
    return DashboardStatsResponse(
        total_students=142, active_subscribers=98, total_questions=1543,
        published_questions=1200, total_attempts_today=87,
        revenue_this_month_cents=285600)


@router_admin.get("/analytics/students", response_model=list[AtRiskStudent],
    summary="Admin: list at-risk students (avg score < 60 on last 5 attempts)")
async def at_risk_students(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, complex aggregate query across quiz_attempts
    return [AtRiskStudent(user_id=7, name="John Doe", email="john@example.com",
                           avg_score=42.5, last_attempt=datetime.utcnow())]


@router_admin.get("/analytics/students/{user_id}", response_model=StudentAnalyticsResponse,
    summary="Admin: detailed analytics for a specific student")
async def student_analytics(user_id: int,
                              credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, per-student analytics with category breakdown and trend
    return StudentAnalyticsResponse(
        user_id=user_id, avg_score=71.5, total_attempts=18,
        weak_areas=[WeakAreaRow(category_name="Pharmacology", avg_score=55.0, attempt_count=6)],
        score_trend=[{"date": "2026-06-01", "score": 68}, {"date": "2026-06-10", "score": 74}],
        is_at_risk=False)


@router_admin.get("/analytics/me", response_model=StudentAnalyticsResponse,
    summary="Student: view own performance analytics and weak areas")
async def my_analytics(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: subscription check, run analytics for current_user
    return StudentAnalyticsResponse(
        user_id=1, avg_score=71.5, total_attempts=18,
        weak_areas=[WeakAreaRow(category_name="Pharmacology", avg_score=55.0, attempt_count=6)],
        score_trend=[{"date": "2026-06-01", "score": 68}, {"date": "2026-06-10", "score": 74}],
        is_at_risk=False)


@router_admin.get("/security/ip-whitelist", response_model=list[IPWhitelistEntry],
    summary="Admin: list trusted IP ranges for admin login")
async def list_ip_whitelist(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, SELECT from ip_whitelist
    return [IPWhitelistEntry(id=1, ip_cidr="203.0.113.0/24",
                              label="Office Islamabad", created_by=2,
                              created_at=datetime.utcnow())]


@router_admin.post("/security/ip-whitelist", response_model=IPWhitelistEntry, status_code=201,
    summary="Admin: add a trusted IP range")
async def add_ip_whitelist(data: IPWhitelistCreateRequest,
                            credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, INSERT ip_whitelist row
    return IPWhitelistEntry(id=2, ip_cidr=data.ip_cidr, label=data.label,
                             created_by=2, created_at=datetime.utcnow())


@router_admin.delete("/security/ip-whitelist/{entry_id}", response_model=MessageResponse,
    summary="Admin: remove a trusted IP range")
async def remove_ip_whitelist(entry_id: int,
                               credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, DELETE ip_whitelist row
    return MessageResponse(message="IP range removed.")


@router_admin.delete("/security/sessions/{user_id}", response_model=MessageResponse,
    summary="Admin: force-logout all sessions for a user")
async def force_logout_user(user_id: int,
                             credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: admin-only, DELETE FROM sessions WHERE user_id = user_id
    return MessageResponse(message="All sessions terminated for user.")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER ALL ROUTERS
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(router_auth)
app.include_router(router_users)
app.include_router(router_subscriptions)
app.include_router(router_payments)
app.include_router(router_categories)
app.include_router(router_questions)
app.include_router(router_bookmarks)
app.include_router(router_quizzes)
app.include_router(router_videos)
app.include_router(router_pdfs)
app.include_router(router_announcements)
app.include_router(router_admin)


# uvicorn contract:app --reload --port 8001