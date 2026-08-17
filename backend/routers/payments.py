"""
backend/routers/payments.py
============================
Stripe payments. Paths/schemas match contract.py.

Checkout creates a Stripe-hosted session and returns its URL — it does
NOT grant access. Access is granted by the webhook (stripe-webhook) when
Stripe confirms payment. This separation is deliberate and load-bearing:
never grant access from the checkout response.
"""

from __future__ import annotations
import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from dependencies import get_current_user
from models import Plan, Subscription, SubStatus, User
from datetime import datetime, timedelta, timezone
from models import Payment, PayMethod, PayStatus
from sqlalchemy import select, func   # extend existing (you have select; add func)
from dependencies import get_current_user, require_admin   # extend (add require_admin)


router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/subscription/success")
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/subscription/cancel")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# ── Schemas (from contract) ───────────────────────────────────────────────────
class StripeCheckoutRequest(BaseModel):
    plan_id: int = Field(..., example=1)


class StripeCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


# ── POST /payments/stripe-checkout ────────────────────────────────────────────
@router.post("/stripe-checkout", response_model=StripeCheckoutResponse)
async def stripe_checkout(
    data: StripeCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for a plan. Returns the hosted URL.
    Does NOT grant access — the webhook does that on payment confirmation.
    """
    # 1. Plan must exist and be active.
    plan = await db.get(Plan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan not found or inactive.")

    # 2. Reject if the user already has an active subscription.
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubStatus.active,
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="You already have an active subscription.")

    # 3. Create the Stripe Checkout session (one-time payment).
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured.")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            line_items=[
                {
                    "price_data": {
                        "currency": plan.currency.lower(),
                        "unit_amount": plan.price_cents,
                        "product_data": {"name": plan.name},
                    },
                    "quantity": 1,
                }
            ],
            # The webhook reads this metadata to know who paid for what.
            metadata={
                "user_id": str(current_user.id),
                "plan_id": str(plan.id),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return StripeCheckoutResponse(
        checkout_url=session.url,
        session_id=session.id,
    )
# ── Webhook helpers ───────────────────────────────────────────────────────────
async def _grant_access_from_session(db: AsyncSession, session: dict) -> None:
    """
    Idempotently grant access for a completed checkout session.
    Writes a Subscription (active) + Payment (succeeded), keyed on the
    Stripe session id (provider_ref) so repeated deliveries don't double-grant.
    """
    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    plan_id = metadata.get("plan_id")

    # Without metadata we can't link the payment — skip safely.
    if not (session_id and user_id and plan_id):
        return

    # IDEMPOTENCY: if we've already recorded this session, do nothing.
    existing = await db.execute(
        select(Payment).where(Payment.provider_ref == session_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    plan = await db.get(Plan, int(plan_id))
    if plan is None:
        return

    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=int(user_id),
        plan_id=plan.id,
        status=SubStatus.active,
        start_date=now,
        end_date=now + timedelta(days=plan.duration_days),
    )
    db.add(sub)
    await db.flush()  # get sub.id for the payment link

    payment = Payment(
        user_id=int(user_id),
        subscription_id=sub.id,
        amount_cents=session.get("amount_total") or plan.price_cents,
        currency=(session.get("currency") or plan.currency).upper(),
        method=PayMethod.stripe,
        status=PayStatus.succeeded,
        provider_ref=session_id,
    )
    db.add(payment)
    await db.commit()


async def _log_failed_payment(db: AsyncSession, intent: dict) -> None:
    """Record a failed payment_intent for audit. Idempotent on provider_ref."""
    ref = intent.get("id")
    if not ref:
        return
    existing = await db.execute(
        select(Payment).where(Payment.provider_ref == ref).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    metadata = intent.get("metadata") or {}
    user_id = metadata.get("user_id")
    if not user_id:
        return  # can't attribute; skip

    payment = Payment(
        user_id=int(user_id),
        subscription_id=None,
        amount_cents=intent.get("amount") or 0,
        currency=(intent.get("currency") or "usd").upper(),
        method=PayMethod.stripe,
        status=PayStatus.failed,
        provider_ref=ref,
    )
    db.add(payment)
    await db.commit()


# ── POST /payments/stripe-webhook ─────────────────────────────────────────────
@router.post("/stripe-webhook", status_code=200)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stripe posts signed events here. We verify the signature, then handle:
      - checkout.session.completed  → grant access (subscription + payment)
      - payment_intent.payment_failed → log the failure
    Always returns 200 quickly so Stripe doesn't retry.
    DO NOT call from the frontend.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        # Malformed payload
        raise HTTPException(status_code=400, detail="Invalid payload.")
    except stripe.error.SignatureVerificationError:
        # Forged / bad signature
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _grant_access_from_session(db, data_object)
    elif event_type == "payment_intent.payment_failed":
        await _log_failed_payment(db, data_object)
    # Other event types: acknowledge without action.

    return {"received": True}

# ── Payment history (Slice 7 step 8) ──────────────────────────────────────────
from datetime import datetime  # (if not already imported)


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class PaymentOut(BaseModel):
    id: int
    user_id: int
    subscription_id: int | None
    amount_cents: int
    currency: str
    method: PayMethod
    status: PayStatus
    provider_ref: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    meta: PaginationMeta


async def _paginate_payments(db: AsyncSession, user_id: int, page: int, per_page: int):
    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    count_q = select(func.count()).select_from(Payment).where(Payment.user_id == user_id)
    total = (await db.execute(count_q)).scalar_one()

    rows_q = (
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = (await db.execute(rows_q)).scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0
    return PaymentListResponse(
        items=items,
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


# ── GET /payments/me ──────────────────────────────────────────────────────────
@router.get("/me", response_model=PaymentListResponse)
async def my_payment_history(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _paginate_payments(db, current_user.id, page, per_page)


# ── GET /payments/{user_id} (admin) ───────────────────────────────────────────
@router.get("/{user_id}", response_model=PaymentListResponse)
async def admin_payment_history(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await _paginate_payments(db, user_id, page, per_page)