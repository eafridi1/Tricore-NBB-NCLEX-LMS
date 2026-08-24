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

# ── Payment history tests (Slice 7 step 8) ────────────────────────────────────
async def _seed_payment(db: AsyncSession, user_id: int, provider_ref: str):
    from models import Payment, PayMethod, PayStatus
    p = Payment(
        user_id=user_id,
        subscription_id=None,
        amount_cents=4999,
        currency="USD",
        method=PayMethod.stripe,
        status=PayStatus.succeeded,
        provider_ref=provider_ref,
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_payments_me_returns_own_history(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    await _seed_payment(db, student_user.id, "cs_1")
    await _seed_payment(db, student_user.id, "cs_2")

    resp = await client.get("/payments/me", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_payments_me_requires_auth(client: AsyncClient, db: AsyncSession):
    resp = await client.get("/payments/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_payments_me_only_sees_own(
    client: AsyncClient, db: AsyncSession, student_user, admin_user, student_token: str
):
    await _seed_payment(db, student_user.id, "cs_mine")
    await _seed_payment(db, admin_user.id, "cs_theirs")  # someone else's

    resp = await client.get("/payments/me", headers=auth_headers(student_token))
    data = resp.json()
    assert data["meta"]["total"] == 1  # only the student's own
    assert data["items"][0]["provider_ref"] == "cs_mine"


@pytest.mark.asyncio
async def test_payments_admin_can_view_any_user(
    client: AsyncClient, db: AsyncSession, student_user, admin_token: str
):
    await _seed_payment(db, student_user.id, "cs_admin_view")

    resp = await client.get(
        f"/payments/{student_user.id}", headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_payments_admin_route_rejects_student(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    resp = await client.get(
        f"/payments/{student_user.id}", headers=auth_headers(student_token)
    )
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_admin_stats_revenue_reflects_succeeded_payments(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    from datetime import datetime, timezone
    from models import Payment, PayMethod, PayStatus

    # Two succeeded payments this month + one failed (should be excluded).
    now = datetime.now(timezone.utc)
    for ref, status, amt in [
        ("cs_rev1", PayStatus.succeeded, 4999),
        ("cs_rev2", PayStatus.succeeded, 2999),
        ("cs_rev3", PayStatus.failed, 9999),  # excluded from revenue
    ]:
        db.add(Payment(
            user_id=admin_user.id, subscription_id=None,
            amount_cents=amt, currency="USD",
            method=PayMethod.stripe, status=status, provider_ref=ref,
        ))
    await db.flush()

    resp = await client.get("/admin/stats", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    # 4999 + 2999 = 7998; the failed 9999 is excluded
    assert resp.json()["revenue_this_month_cents"] == 7998

# ── Regression: webhook must handle StripeObject (not just plain dict) ─────────
class _FakeStripeObject:
    """
    Mimics a Stripe StripeObject: the real webhook event's data.object has a
    .to_dict() method and does NOT support .get() the way a plain dict does.
    This reproduces the shape that caused a 500 in production (unit tests had
    passed plain dicts and missed it).
    """
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return self._data

    # Deliberately NO .get() — accessing it raises, like a real StripeObject,
    # so if the handler forgets to call to_dict() the test fails.
    def get(self, *args, **kwargs):
        raise AttributeError("StripeObject has no .get() — must call to_dict() first")


@pytest.mark.asyncio
async def test_webhook_handles_stripe_object_not_just_dict(
    client: AsyncClient, db: AsyncSession, student_user
):
    plan = await _seed_plan(db)
    # Event whose data.object is a StripeObject-like thing (has to_dict, no usable get).
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": _FakeStripeObject({
                "id": "cs_stripeobj_test",
                "metadata": {"user_id": str(student_user.id), "plan_id": str(plan.id)},
                "amount_total": 4999,
                "currency": "usd",
            })
        },
    }

    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("routers.payments.WEBHOOK_SECRET", "whsec_test"):
        resp = await client.post(
            "/payments/stripe-webhook",
            content=b"{}",
            headers={"stripe-signature": "test"},
        )
    # Must succeed (200) and actually grant access — proving to_dict() was used.
    assert resp.status_code == 200

    subs = (await db.execute(
        select(Subscription).where(Subscription.user_id == student_user.id)
    )).scalars().all()
    assert len(subs) == 1
    assert subs[0].status == SubStatus.active

    pays = (await db.execute(
        select(Payment).where(Payment.provider_ref == "cs_stripeobj_test")
    )).scalars().all()
    assert len(pays) == 1            