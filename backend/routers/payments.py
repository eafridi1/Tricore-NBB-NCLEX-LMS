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


router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/subscription/success")
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/subscription/cancel")


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