# backend/tests/test_categories.py
"""
Integration tests for SECTION 5 — CATEGORIES
GET /categories, POST /categories, PATCH /categories/{id},
DELETE /categories/{id}
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, Question, QStatus, Difficulty
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_category(db: AsyncSession, name: str = "Cardiovascular") -> Category:
    cat = Category(name=name, sort_order=0)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


# ── GET /categories ──────────────────────────────────────────────────────────

async def test_list_categories_no_auth_required(client: AsyncClient, db: AsyncSession):
    """Contract says public endpoint."""
    await _seed_category(db, "PublicCat")
    resp = await client.get("/categories")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_categories_returns_all(client: AsyncClient, db: AsyncSession):
    await _seed_category(db, "Cat1")
    await _seed_category(db, "Cat2")
    resp = await client.get("/categories")
    assert len(resp.json()) >= 2


async def test_list_categories_without_count(client: AsyncClient, db: AsyncSession):
    await _seed_category(db, "NoCnt")
    resp = await client.get("/categories")
    for item in resp.json():
        assert item["question_count"] is None


async def test_list_categories_with_count(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "WithCnt")

    # Add a published, non-deleted question in this category
    q = Question(
        stem="A nurse is...",
        options=[{"text": f"Option {x}"} for x in "ABCD"],
        correct_answer=0,
        rationale="Because...",
        category_id=cat.id,
        nclex_domain="Safe Care",
        difficulty=Difficulty.easy,
        status=QStatus.published,
        is_deleted=False,
        created_by=admin_user.id,
    )
    db.add(q)
    await db.flush()

    resp = await client.get("/categories?include_count=true")
    assert resp.status_code == 200
    match = next((c for c in resp.json() if c["id"] == cat.id), None)
    assert match is not None
    assert match["question_count"] == 1


async def test_list_categories_count_excludes_deleted(
    client: AsyncClient, db: AsyncSession, admin_user
):
    cat = await _seed_category(db, "DeletedQ")
    q = Question(
        stem="stem", options=[{"text": x} for x in "ABCD"], correct_answer=0,
        rationale="r", category_id=cat.id, nclex_domain="d",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=True, created_by=admin_user.id,
    )
    db.add(q)
    await db.flush()

    resp = await client.get("/categories?include_count=true")
    match = next((c for c in resp.json() if c["id"] == cat.id), None)
    assert match["question_count"] == 0


# ── POST /categories ─────────────────────────────────────────────────────────

async def test_create_category_admin_success(
    client: AsyncClient, admin_token: str
):
    resp = await client.post("/categories", json={
        "name": "NewCategory", "sort_order": 5,
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "NewCategory"
    assert data["id"] > 0
    assert data["question_count"] == 0


async def test_create_category_student_forbidden(
    client: AsyncClient, student_token: str
):
    resp = await client.post("/categories", json={
        "name": "StudentCat",
    }, headers=auth_headers(student_token))
    assert resp.status_code == 403


async def test_create_category_unauthenticated(client: AsyncClient):
    resp = await client.post("/categories", json={"name": "Anon"})
    assert resp.status_code == 403


async def test_create_category_duplicate_name(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    await _seed_category(db, "DupCat")
    resp = await client.post("/categories", json={
        "name": "DupCat",
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 409


# ── PATCH /categories/{id} ───────────────────────────────────────────────────

async def test_update_category_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "OldName")
    resp = await client.patch(f"/categories/{cat.id}", json={
        "name": "NewName", "sort_order": 2,
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "NewName"


async def test_update_category_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.patch("/categories/99999", json={
        "name": "X",
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 404


async def test_update_category_name_clash(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    await _seed_category(db, "AlreadyExists")
    cat2 = await _seed_category(db, "ToRename")
    resp = await client.patch(f"/categories/{cat2.id}", json={
        "name": "AlreadyExists",
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 409


# ── DELETE /categories/{id} ──────────────────────────────────────────────────

async def test_delete_category_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "ToDelete")
    resp = await client.delete(
        f"/categories/{cat.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"].lower()


async def test_delete_category_with_active_questions_blocked(
    client: AsyncClient, db: AsyncSession, admin_token: str, admin_user
):
    """Cannot delete a category that has non-deleted questions."""
    cat = await _seed_category(db, "HasQuestions")
    q = Question(
        stem="s", options=[{"text": x} for x in "ABCD"], correct_answer=0,
        rationale="r", category_id=cat.id, nclex_domain="d",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=False, created_by=admin_user.id,
    )
    db.add(q)
    await db.flush()

    resp = await client.delete(
        f"/categories/{cat.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 409


async def test_delete_category_ok_when_all_questions_soft_deleted(
    client: AsyncClient, db: AsyncSession, admin_token: str, admin_user
):
    """Soft-deleted questions don't block category deletion."""
    cat = await _seed_category(db, "OnlyDeleted")
    q = Question(
        stem="s", options=[{"text": x} for x in "ABCD"], correct_answer=0,
        rationale="r", category_id=cat.id, nclex_domain="d",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=True, created_by=admin_user.id,
    )
    db.add(q)
    await db.flush()

    resp = await client.delete(
        f"/categories/{cat.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200


async def test_delete_category_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.delete(
        "/categories/99999",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404