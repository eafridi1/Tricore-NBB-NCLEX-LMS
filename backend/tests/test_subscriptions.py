"""
Tests for /subscriptions plan routes (Slice 7, step 1).
Covers: list (public, active-only), create (admin), update (admin), guards, 404.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from models import Plan, Subscription, SubStatus
from datetime import datetime, timedelta, timezone



# ── helper ────────────────────────────────────────────────────────────────────
async def _seed_plan(
    db: AsyncSession,
    name: str = "1-Month Access",
    price_cents: int = 2999,
    duration_days: int = 30,
    is_active: bool = True,
) -> Plan:
    plan = Plan(
        name=name,
        price_cents=price_cents,
        currency="USD",
        duration_days=duration_days,
        description="Test plan.",
        is_active=is_active,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


# ── GET /subscriptions/plans (public, active-only) ────────────────────────────
@pytest.mark.asyncio
async def test_list_plans_public_returns_active_only(
    client: AsyncClient, db: AsyncSession
):
    await _seed_plan(db, name="Active Plan", is_active=True)
    await _seed_plan(db, name="Inactive Plan", is_active=False)

    resp = await client.get("/subscriptions/plans")  # no auth
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Active Plan" in names
    assert "Inactive Plan" not in names


@pytest.mark.asyncio
async def test_list_plans_shape(client: AsyncClient, db: AsyncSession):
    await _seed_plan(db, name="Shape Plan")
    resp = await client.get("/subscriptions/plans")
    assert resp.status_code == 200
    plan = resp.json()[0]
    # Contract PlanOut fields
    for field in ["id", "name", "price_cents", "currency", "duration_days", "description", "is_active"]:
        assert field in plan


# ── POST /subscriptions/plans (admin) ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_plan_as_admin(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    body = {
        "name": "3-Month Access",
        "price_cents": 8999,
        "currency": "USD",
        "duration_days": 90,
        "description": "Full access for 90 days.",
    }
    resp = await client.post(
        "/subscriptions/plans", json=body, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "3-Month Access"
    assert data["price_cents"] == 8999
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_plan_rejected_for_student(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    body = {
        "name": "Sneaky Plan",
        "price_cents": 100,
        "currency": "USD",
        "duration_days": 1,
    }
    resp = await client.post(
        "/subscriptions/plans", json=body, headers=auth_headers(student_token)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_plan_rejected_without_auth(
    client: AsyncClient, db: AsyncSession
):
    resp = await client.post("/subscriptions/plans", json={
        "name": "No Auth Plan", "price_cents": 100, "currency": "USD", "duration_days": 1,
    })
    assert resp.status_code == 401


# ── PATCH /subscriptions/plans/{plan_id} (admin) ──────────────────────────────
@pytest.mark.asyncio
async def test_update_plan_as_admin(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    plan = await _seed_plan(db, name="Old Name", price_cents=2999)
    body = {
        "name": "New Name",
        "price_cents": 7999,
        "currency": "USD",
        "duration_days": 60,
        "description": "Updated.",
    }
    resp = await client.patch(
        f"/subscriptions/plans/{plan.id}", json=body, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["price_cents"] == 7999
    assert data["duration_days"] == 60


@pytest.mark.asyncio
async def test_update_plan_404_for_missing(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    body = {
        "name": "Ghost", "price_cents": 100, "currency": "USD", "duration_days": 1,
    }
    resp = await client.patch(
        "/subscriptions/plans/999999", json=body, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 404

    # ── Payment model (Slice 7 step 2) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_payment_row_can_be_created(
    client: AsyncClient, db: AsyncSession, admin_user
):
    from models import Payment, PayMethod, PayStatus

    payment = Payment(
        user_id=admin_user.id,
        subscription_id=None,
        amount_cents=2999,
        currency="USD",
        method=PayMethod.stripe,
        status=PayStatus.succeeded,
        provider_ref="evt_test_123",
    )
    db.add(payment)
    await db.flush()
    await db.refresh(payment)

    assert payment.id is not None
    assert payment.method == PayMethod.stripe
    assert payment.status == PayStatus.succeeded
    assert payment.provider_ref == "evt_test_123"
    assert payment.amount_cents == 2999


    # ── Subscription check + grace logic (Slice 7 step 3) ─────────────────────────

async def _seed_subscription(
    db: AsyncSession,
    user_id: int,
    plan_id: int,
    status: SubStatus,
    end_date: datetime,
):
    sub = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        status=status,
        start_date=end_date - timedelta(days=30),
        end_date=end_date,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_check_no_subscription_denies_access(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    resp = await client.get("/subscriptions/check", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_access"] is False
    assert data["status"] is None


@pytest.mark.asyncio
async def test_check_active_grants_access(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.active, now + timedelta(days=10))

    resp = await client.get("/subscriptions/check", headers=auth_headers(student_token))
    data = resp.json()
    assert data["has_access"] is True
    assert data["status"] == "active"
    assert data["days_remaining"] >= 9  # ~10 days, allowing for clock


@pytest.mark.asyncio
async def test_check_within_grace_grants_access(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    # end_date was 1 day ago → inside the 3-day grace window
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.active, now - timedelta(days=1))

    resp = await client.get("/subscriptions/check", headers=auth_headers(student_token))
    data = resp.json()
    assert data["has_access"] is True
    assert data["status"] == "grace"


@pytest.mark.asyncio
async def test_check_past_grace_denies_access(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    # end_date was 5 days ago → past the 3-day grace window
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.active, now - timedelta(days=5))

    resp = await client.get("/subscriptions/check", headers=auth_headers(student_token))
    data = resp.json()
    assert data["has_access"] is False
    assert data["status"] == "expired"


@pytest.mark.asyncio
async def test_check_cancelled_denies_access(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.cancelled, now + timedelta(days=10))

    resp = await client.get("/subscriptions/check", headers=auth_headers(student_token))
    data = resp.json()
    assert data["has_access"] is False
    assert data["status"] == "cancelled"


@pytest.mark.asyncio
async def test_me_returns_subscription_history(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.active, now + timedelta(days=10))

    resp = await client.get("/subscriptions/me", headers=auth_headers(student_token))
    assert resp.status_code == 200
    subs = resp.json()
    assert len(subs) == 1
    assert subs[0]["plan"]["id"] == plan.id  # nested plan present
    assert subs[0]["status"] == "active"


@pytest.mark.asyncio
async def test_check_requires_auth(client: AsyncClient, db: AsyncSession):
    resp = await client.get("/subscriptions/check")  # no token
    assert resp.status_code == 401

# ── Gating dependency (Slice 7 step 4) ────────────────────────────────────────
@pytest.mark.asyncio
async def test_gated_endpoint_blocks_student_without_subscription(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    # student, no subscription → 402 on gated videos list
    resp = await client.get("/videos", headers=auth_headers(student_token))
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_gated_endpoint_allows_student_with_active_sub(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    plan = await _seed_plan(db)
    now = datetime.now(timezone.utc)
    await _seed_subscription(db, student_user.id, plan.id, SubStatus.active, now + timedelta(days=10))

    resp = await client.get("/videos", headers=auth_headers(student_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_gated_endpoint_allows_admin_bypass(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    # admin has no subscription but should bypass the gate
    resp = await client.get("/videos", headers=auth_headers(admin_token))
    assert resp.status_code == 200    