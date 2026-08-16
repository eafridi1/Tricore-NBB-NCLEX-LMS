"""
Tests for /payments/stripe-checkout.
Logic tests use no real Stripe. The live test actually calls Stripe test mode
and is marked so it can be skipped when offline / no key.
"""
import os
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import auth_headers
from models import Plan, Subscription, SubStatus
from sqlalchemy import select


async def _seed_plan(db: AsyncSession, is_active: bool = True) -> Plan:
    plan = Plan(
        name="Checkout Test Plan",
        price_cents=4999,
        currency="USD",
        duration_days=30,
        is_active=is_active,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


# ── Logic tests (no real Stripe needed for these paths) ───────────────────────
@pytest.mark.asyncio
async def test_checkout_requires_auth(client: AsyncClient, db: AsyncSession):
    resp = await client.post("/payments/stripe-checkout", json={"plan_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_checkout_plan_not_found(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    resp = await client.post(
        "/payments/stripe-checkout",
        json={"plan_id": 999999},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_checkout_rejects_if_already_active(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    from datetime import datetime, timedelta, timezone

    plan = await _seed_plan(db)
    # give the student an active sub already
    sub = Subscription(
        user_id=student_user.id,
        plan_id=plan.id,
        status=SubStatus.active,
        start_date=datetime.now(timezone.utc) - timedelta(days=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=29),
    )
    db.add(sub)
    await db.flush()

    resp = await client.post(
        "/payments/stripe-checkout",
        json={"plan_id": plan.id},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 409


# ── Live Stripe integration test (real test-mode call) ────────────────────────
@pytest.mark.skipif(
    not os.getenv("STRIPE_SECRET_KEY"),
    reason="STRIPE_SECRET_KEY not set — skipping live Stripe call",
)
@pytest.mark.asyncio
async def test_checkout_creates_real_session(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    resp = await client.post(
        "/payments/stripe-checkout",
        json={"plan_id": plan.id},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com")
    assert data["session_id"].startswith("cs_")

# ── Webhook tests (Slice 7 step 7) ────────────────────────────────────────────
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from models import Payment, PayStatus, SubStatus, Subscription


def _completed_event(user_id: int, plan_id: int, session_id: str = "cs_test_abc"):
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "metadata": {"user_id": str(user_id), "plan_id": str(plan_id)},
                "amount_total": 4999,
                "currency": "usd",
            }
        },
    }


@pytest.mark.asyncio
async def test_webhook_grants_access_on_completed(
    client: AsyncClient, db: AsyncSession, student_user
):
    plan = await _seed_plan(db)
    event = _completed_event(student_user.id, plan.id)

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("routers.payments.WEBHOOK_SECRET", "whsec_test"):
        resp = await client.post(
            "/payments/stripe-webhook",
            content=b"{}",
            headers={"stripe-signature": "test"},
        )
    assert resp.status_code == 200

    # A subscription and payment should now exist for the user.
    subs = (await db.execute(
        select(Subscription).where(Subscription.user_id == student_user.id)
    )).scalars().all()
    assert len(subs) == 1
    assert subs[0].status == SubStatus.active

    pays = (await db.execute(
        select(Payment).where(Payment.provider_ref == "cs_test_abc")
    )).scalars().all()
    assert len(pays) == 1
    assert pays[0].status == PayStatus.succeeded


@pytest.mark.asyncio
async def test_webhook_is_idempotent(
    client: AsyncClient, db: AsyncSession, student_user
):
    plan = await _seed_plan(db)
    event = _completed_event(student_user.id, plan.id)

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("routers.payments.WEBHOOK_SECRET", "whsec_test"):
        # Deliver the SAME event twice.
        await client.post("/payments/stripe-webhook", content=b"{}",
                          headers={"stripe-signature": "test"})
        await client.post("/payments/stripe-webhook", content=b"{}",
                          headers={"stripe-signature": "test"})

    # Only ONE subscription + ONE payment despite two deliveries.
    subs = (await db.execute(
        select(Subscription).where(Subscription.user_id == student_user.id)
    )).scalars().all()
    assert len(subs) == 1

    pays = (await db.execute(
        select(Payment).where(Payment.provider_ref == "cs_test_abc")
    )).scalars().all()
    assert len(pays) == 1


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(
    client: AsyncClient, db: AsyncSession
):
    import stripe as stripe_mod
    with patch("stripe.Webhook.construct_event",
               side_effect=stripe_mod.error.SignatureVerificationError("bad", "sig")), \
         patch("routers.payments.WEBHOOK_SECRET", "whsec_test"):
        resp = await client.post(
            "/payments/stripe-webhook",
            content=b"{}",
            headers={"stripe-signature": "bad"},
        )
    assert resp.status_code == 400