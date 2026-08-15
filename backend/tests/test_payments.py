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