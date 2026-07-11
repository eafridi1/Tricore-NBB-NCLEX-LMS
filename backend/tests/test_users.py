# backend/tests/test_users.py
"""
Integration tests for SECTION 2 — USERS
GET /users/me, PATCH /users/me, POST /users/me/change-password,
GET /users/me/login-history, GET /users, GET /users/{id},
PATCH /users/{id}
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import User, LoginLog, LoginStatus
from auth_utils import hash_password
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


# ── GET /users/me ────────────────────────────────────────────────────────────

async def test_get_my_profile_returns_own_data(
    client: AsyncClient, student_user: User, student_token: str
):
    resp = await client.get("/users/me", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == student_user.id
    assert data["email"] == student_user.email
    assert data["name"] == student_user.name
    assert data["role"] == "student"
    assert data["is_verified"] is True


async def test_get_my_profile_requires_auth(client: AsyncClient):
    resp = await client.get("/users/me")
    assert resp.status_code in (401, 403)


async def test_get_my_profile_admin(
    client: AsyncClient, admin_user: User, admin_token: str
):
    resp = await client.get("/users/me", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


# ── PATCH /users/me ──────────────────────────────────────────────────────────

async def test_patch_me_dark_mode_persists(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    assert student_user.dark_mode is False

    resp = await client.patch(
        "/users/me",
        json={"dark_mode": True},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["dark_mode"] is True

    # Verify it actually persisted in the DB
    await db.refresh(student_user)
    assert student_user.dark_mode is True


async def test_patch_me_name_update(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    resp = await client.patch(
        "/users/me",
        json={"name": "Updated Name"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"

    await db.refresh(student_user)
    assert student_user.name == "Updated Name"


async def test_patch_me_partial_does_not_clear_other_fields(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    """Sending only dark_mode should not clear the user's name."""
    original_name = student_user.name

    await client.patch(
        "/users/me",
        json={"dark_mode": True},
        headers=auth_headers(student_token),
    )

    await db.refresh(student_user)
    assert student_user.name == original_name  # untouched


async def test_patch_me_requires_auth(client: AsyncClient):
    resp = await client.patch("/users/me", json={"dark_mode": True})
    assert resp.status_code in (401, 403)


# ── POST /users/me/change-password ──────────────────────────────────────────

async def test_change_password_wrong_current_returns_400(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "WrongPassword1", "new_password": "NewSecure456!"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


async def test_change_password_correct_returns_200(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    # Capture BEFORE the request — not after
    old_hash = student_user.password_hash

    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "NewSecure456!"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200

    # expire() discards SQLAlchemy's in-memory cache so refresh()
    # actually re-queries the DB instead of returning the stale object.
    db.expire(student_user)
    await db.refresh(student_user)
    assert student_user.password_hash != old_hash


async def test_change_password_new_too_short(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "short"},
        headers=auth_headers(student_token),
    )
    # Pydantic min_length=8 should catch this
    assert resp.status_code == 422


async def test_change_password_no_uppercase_returns_422(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "nouppercase1"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 422


async def test_change_password_no_digit_returns_422(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "NoDigitHere"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 422


async def test_change_password_no_lowercase_returns_422(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "NOLOWER123!"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 422


async def test_change_password_no_special_char_returns_422(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "NoSpecial123"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 422


async def test_change_password_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/users/me/change-password",
        json={"current_password": "Student123!", "new_password": "NewSecure456!"},
    )
    assert resp.status_code in (401, 403)


# ── GET /users/me/login-history ──────────────────────────────────────────────

async def test_login_history_returns_list(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    # Seed a login log entry for this user
    db.add(LoginLog(
        user_id=student_user.id,
        ip_address="203.0.113.1",
        country_code="PK",
        user_agent="Chrome/125",
        status=LoginStatus.success,
    ))
    await db.flush()

    resp = await client.get(
        "/users/me/login-history",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "meta" in data
    assert data["meta"]["total"] >= 1
    assert data["items"][0]["ip_address"] == "203.0.113.1"


async def test_login_history_empty_for_new_user(
    client: AsyncClient, student_token: str
):
    resp = await client.get(
        "/users/me/login-history",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 0


async def test_login_history_only_own_logs(
    client: AsyncClient, db: AsyncSession,
    student_user: User, admin_user: User, student_token: str
):
    """Student should only see their own login logs, not admin's."""
    db.add(LoginLog(
        user_id=admin_user.id,
        ip_address="10.0.0.1",
        status=LoginStatus.success,
    ))
    db.add(LoginLog(
        user_id=student_user.id,
        ip_address="203.0.113.1",
        status=LoginStatus.success,
    ))
    await db.flush()

    resp = await client.get(
        "/users/me/login-history",
        headers=auth_headers(student_token),
    )
    items = resp.json()["items"]
    for item in items:
        assert item["ip_address"] != "10.0.0.1"  # admin's IP not visible


async def test_login_history_pagination(
    client: AsyncClient, db: AsyncSession, student_user: User, student_token: str
):
    for i in range(5):
        db.add(LoginLog(
            user_id=student_user.id,
            ip_address=f"10.0.0.{i}",
            status=LoginStatus.success,
        ))
    await db.flush()

    resp = await client.get(
        "/users/me/login-history?page=1&per_page=2",
        headers=auth_headers(student_token),
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["meta"]["per_page"] == 2
    assert data["meta"]["total"] >= 5


# ── GET /users (admin only) ──────────────────────────────────────────────────

async def test_list_users_student_gets_403(
    client: AsyncClient, student_token: str
):
    resp = await client.get("/users", headers=auth_headers(student_token))
    assert resp.status_code == 403


async def test_list_users_admin_success(
    client: AsyncClient, admin_token: str, student_user: User
):
    resp = await client.get("/users", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["meta"]["total"] >= 1


async def test_list_users_filter_by_role(
    client: AsyncClient, admin_token: str, student_user: User, admin_user: User
):
    resp = await client.get(
        "/users?role=student",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["role"] == "student"


async def test_list_users_filter_by_is_active(
    client: AsyncClient, db: AsyncSession, admin_token: str, student_user: User
):
    student_user.is_active = False
    await db.flush()

    resp = await client.get(
        "/users?is_active=false",
        headers=auth_headers(admin_token),
    )
    items = resp.json()["items"]
    assert any(i["id"] == student_user.id for i in items)
    for item in items:
        assert item["is_active"] is False


async def test_list_users_unauthenticated(client: AsyncClient):
    resp = await client.get("/users")
    assert resp.status_code in (401, 403)


# ── GET /users/{user_id} ─────────────────────────────────────────────────────

async def test_get_user_admin_success(
    client: AsyncClient, admin_token: str, student_user: User
):
    resp = await client.get(
        f"/users/{student_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == student_user.id
    assert resp.json()["email"] == student_user.email


async def test_get_user_student_gets_403(
    client: AsyncClient, student_token: str, admin_user: User
):
    resp = await client.get(
        f"/users/{admin_user.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_get_user_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get("/users/99999", headers=auth_headers(admin_token))
    assert resp.status_code == 404


# ── PATCH /users/{user_id} ───────────────────────────────────────────────────

async def test_admin_deactivate_student(
    client: AsyncClient, db: AsyncSession, admin_token: str, student_user: User
):
    assert student_user.is_active is True

    resp = await client.patch(
        f"/users/{student_user.id}",
        json={"is_active": False},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    await db.refresh(student_user)
    assert student_user.is_active is False


async def test_admin_cannot_modify_own_account(
    client: AsyncClient, admin_user: User, admin_token: str
):
    """Admin modifying their own role/active status is blocked."""
    resp = await client.patch(
        f"/users/{admin_user.id}",
        json={"is_active": False},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400
    assert "own" in resp.json()["detail"].lower()


async def test_patch_user_student_gets_403(
    client: AsyncClient, student_token: str, admin_user: User
):
    resp = await client.patch(
        f"/users/{admin_user.id}",
        json={"is_active": False},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_patch_user_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        "/users/99999",
        json={"is_active": False},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404