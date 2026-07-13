# backend/tests/test_admin.py
"""
Integration tests for SECTION 12 — ADMIN (security + analytics routes)
GET/POST/DELETE /admin/security/ip-whitelist
DELETE /admin/security/sessions/{user_id}
GET /admin/analytics/students
GET /admin/analytics/students/{user_id}
"""

import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models import (
    IPWhitelist, Session, Category, Question, QuizAttempt,
    AttemptStatus, QStatus, Difficulty, User,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


# ── Seed helpers ──────────────────────────────────────────────────────────────

async def _seed_category(db: AsyncSession, name: str = "AdminCat") -> Category:
    cat = Category(name=name, sort_order=0)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def _seed_completed_attempt(
    db: AsyncSession,
    user_id: int,
    admin_id: int,
    category_id: int,
    score: float = 45.0,
) -> QuizAttempt:
    q = Question(
        stem="Test stem",
        options=[{"text": x} for x in ["A", "B", "C", "D"]],
        correct_answer=0, rationale="r",
        category_id=category_id, nclex_domain="Safe Care",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=False, created_by=admin_id,
    )
    db.add(q)
    await db.flush()

    attempt = QuizAttempt(
        user_id=user_id,
        question_ids=[q.id],
        answers={str(q.id): 0},
        status=AttemptStatus.completed,
        score=score,
        correct_count=1 if score >= 60 else 0,
        timed=False,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt


async def _seed_session(
    db: AsyncSession, user_id: int, token: str = "test-refresh-token"
) -> Session:
    session = Session(
        user_id=user_id,
        refresh_token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


# ── GET /admin/security/ip-whitelist ─────────────────────────────────────────

async def test_list_ip_whitelist_admin_success(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    db.add(IPWhitelist(
        ip_cidr="203.0.113.0/24",
        label="Test Office",
        created_by=admin_user.id,
    ))
    await db.flush()

    resp = await client.get(
        "/admin/security/ip-whitelist",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(e["ip_cidr"] == "203.0.113.0/24" for e in resp.json())


async def test_list_ip_whitelist_student_forbidden(
    client: AsyncClient, student_token: str
):
    resp = await client.get(
        "/admin/security/ip-whitelist",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_list_ip_whitelist_empty(
    client: AsyncClient, admin_token: str
):
    resp = await client.get(
        "/admin/security/ip-whitelist",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── POST /admin/security/ip-whitelist ────────────────────────────────────────

async def test_add_ip_whitelist_success(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "10.0.0.0/8", "label": "VPN"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["ip_cidr"] == "10.0.0.0/8"
    assert data["label"] == "VPN"
    assert data["id"] > 0


async def test_add_ip_whitelist_single_ip(
    client: AsyncClient, admin_token: str
):
    """Single IP address (no /prefix) should be accepted."""
    resp = await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "192.168.1.5"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201


async def test_add_ip_whitelist_invalid_cidr(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "not-an-ip"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 422


async def test_add_ip_whitelist_duplicate_returns_409(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    db.add(IPWhitelist(ip_cidr="172.16.0.0/12", created_by=admin_user.id))
    await db.flush()

    resp = await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "172.16.0.0/12"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 409


async def test_add_ip_whitelist_appears_in_list(
    client: AsyncClient, admin_token: str
):
    await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "198.51.100.0/24", "label": "Client office"},
        headers=auth_headers(admin_token),
    )
    list_resp = await client.get(
        "/admin/security/ip-whitelist",
        headers=auth_headers(admin_token),
    )
    cidrs = [e["ip_cidr"] for e in list_resp.json()]
    assert "198.51.100.0/24" in cidrs


async def test_add_ip_whitelist_student_forbidden(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/admin/security/ip-whitelist",
        json={"ip_cidr": "10.0.0.1"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── DELETE /admin/security/ip-whitelist/{id} ─────────────────────────────────

async def test_delete_ip_whitelist_success(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    entry = IPWhitelist(ip_cidr="10.10.10.0/24", created_by=admin_user.id)
    db.add(entry)
    await db.flush()

    resp = await client.delete(
        f"/admin/security/ip-whitelist/{entry.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200

    remaining = await db.get(IPWhitelist, entry.id)
    assert remaining is None


async def test_delete_ip_whitelist_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.delete(
        "/admin/security/ip-whitelist/99999",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_delete_ip_whitelist_student_forbidden(
    client: AsyncClient, db: AsyncSession, admin_user, student_token: str
):
    entry = IPWhitelist(ip_cidr="10.20.30.0/24", created_by=admin_user.id)
    db.add(entry)
    await db.flush()

    resp = await client.delete(
        f"/admin/security/ip-whitelist/{entry.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── DELETE /admin/security/sessions/{user_id} ────────────────────────────────

async def test_force_logout_deletes_sessions(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, admin_token: str
):
    # Give the student two active sessions
    await _seed_session(db, student_user.id, "token-one")
    await _seed_session(db, student_user.id, "token-two")

    resp = await client.delete(
        f"/admin/security/sessions/{student_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert "2" in resp.json()["message"]  # "2 session(s) invalidated"

    count = await db.scalar(
        select(func.count()).select_from(Session)
        .where(Session.user_id == student_user.id)
    )
    assert count == 0


async def test_force_logout_user_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.delete(
        "/admin/security/sessions/99999",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_force_logout_self_blocked(
    client: AsyncClient, admin_user, admin_token: str
):
    """Admin cannot force-logout their own session via this endpoint."""
    resp = await client.delete(
        f"/admin/security/sessions/{admin_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400
    assert "own" in resp.json()["detail"].lower()


async def test_force_logout_no_sessions_still_200(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, admin_token: str
):
    """Force-logout on a user with no sessions should succeed with 0 count."""
    resp = await client.delete(
        f"/admin/security/sessions/{student_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert "0" in resp.json()["message"]


async def test_force_logout_student_forbidden(
    client: AsyncClient, student_user, student_token: str
):
    resp = await client.delete(
        f"/admin/security/sessions/{student_user.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── GET /admin/analytics/students (at-risk) ───────────────────────────────────

async def test_at_risk_students_returns_list(
    client: AsyncClient, admin_token: str
):
    # PostgreSQL-only function — graceful degradation returns []
    # on SQLite. Test only verifies shape, not content.
    resp = await client.get(
        "/admin/analytics/students",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_at_risk_students_student_forbidden(
    client: AsyncClient, student_token: str
):
    resp = await client.get(
        "/admin/analytics/students",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_at_risk_students_unauthenticated(client: AsyncClient):
    resp = await client.get("/admin/analytics/students")
    assert resp.status_code in (401, 403)


# ── GET /admin/analytics/students/{user_id} ──────────────────────────────────

async def test_student_analytics_admin_can_view(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, admin_token: str
):
    cat = await _seed_category(db, "SAAdminCat")
    await _seed_completed_attempt(db, student_user.id, admin_user.id, cat.id, score=72.0)

    resp = await client.get(
        f"/admin/analytics/students/{student_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == student_user.id
    assert data["avg_score"] == 72.0
    assert data["total_attempts"] == 1
    assert isinstance(data["weak_areas"], list)
    assert isinstance(data["score_trend"], list)
    assert isinstance(data["is_at_risk"], bool)


async def test_student_analytics_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.get(
        "/admin/analytics/students/99999",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_student_analytics_student_forbidden(
    client: AsyncClient, student_user, student_token: str
):
    resp = await client.get(
        f"/admin/analytics/students/{student_user.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_student_analytics_period_weekly(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, admin_token: str
):
    cat = await _seed_category(db, "PeriodAdminCat")
    await _seed_completed_attempt(db, student_user.id, admin_user.id, cat.id, score=65.0)

    resp = await client.get(
        f"/admin/analytics/students/{student_user.id}?period=weekly",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["total_attempts"] >= 1