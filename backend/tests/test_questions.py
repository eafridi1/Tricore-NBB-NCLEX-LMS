# backend/tests/test_questions.py
"""
Integration tests for SECTION 6 — QUESTIONS + SECTION 7 — BOOKMARKS
Covers: list, create, get, update, status workflow, bookmarks.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, Question, QStatus, Difficulty, Bookmark
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


# ── Fixtures ─────────────────────────────────────────────────────────────────

async def _seed_category(db: AsyncSession, name: str = "Cardio") -> Category:
    cat = Category(name=name, sort_order=0)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def _seed_question(
    db: AsyncSession, category_id: int, created_by: int,
    status: QStatus = QStatus.published,
    difficulty: Difficulty = Difficulty.medium,
    is_deleted: bool = False,
) -> Question:
    q = Question(
        stem="A nurse is assessing a patient with chest pain. What is the priority?",
        options=[{"text": "Option A"}, {"text": "Option B"},
                 {"text": "Option C"}, {"text": "Option D"}],
        correct_answer=1,
        rationale="Option B is correct because...",
        category_id=category_id,
        nclex_domain="Safe and Effective Care",
        difficulty=difficulty,
        status=status,
        is_deleted=is_deleted,
        created_by=created_by,
    )
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return q


# ── GET /questions ────────────────────────────────────────────────────────────

async def test_list_questions_student_sees_only_published(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "ListTest")
    await _seed_question(db, cat.id, admin_user.id, status=QStatus.published)
    await _seed_question(db, cat.id, admin_user.id, status=QStatus.draft)

    resp = await client.get("/questions", headers=auth_headers(student_token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["status"] == "published"


async def test_list_questions_admin_sees_all_statuses(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "AdminList")
    await _seed_question(db, cat.id, admin_user.id, status=QStatus.published)
    await _seed_question(db, cat.id, admin_user.id, status=QStatus.draft)

    resp = await client.get(
        f"/questions?status=draft",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["status"] == "draft" for i in items)


async def test_list_questions_excludes_soft_deleted(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "SoftDelList")
    live = await _seed_question(db, cat.id, admin_user.id, is_deleted=False)
    await _seed_question(db, cat.id, admin_user.id, is_deleted=True)

    resp = await client.get("/questions", headers=auth_headers(student_token))
    ids = [i["id"] for i in resp.json()["items"]]
    assert live.id in ids
    # soft-deleted question must not appear regardless of user role
    for item in resp.json()["items"]:
        assert not item.get("is_deleted", False)


async def test_list_questions_admin_also_excludes_soft_deleted(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "AdminSoftDel")
    deleted = await _seed_question(db, cat.id, admin_user.id, is_deleted=True)

    resp = await client.get("/questions", headers=auth_headers(admin_token))
    ids = [i["id"] for i in resp.json()["items"]]
    assert deleted.id not in ids


async def test_list_questions_filter_by_category(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat1 = await _seed_category(db, "FilterCat1")
    cat2 = await _seed_category(db, "FilterCat2")
    q1 = await _seed_question(db, cat1.id, admin_user.id)
    await _seed_question(db, cat2.id, admin_user.id)

    resp = await client.get(
        f"/questions?category_id={cat1.id}",
        headers=auth_headers(student_token),
    )
    ids = [i["id"] for i in resp.json()["items"]]
    assert q1.id in ids
    for item in resp.json()["items"]:
        assert item["category_id"] == cat1.id


async def test_list_questions_filter_by_difficulty(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "DiffFilter")
    easy = await _seed_question(db, cat.id, admin_user.id, difficulty=Difficulty.easy)
    await _seed_question(db, cat.id, admin_user.id, difficulty=Difficulty.hard)

    resp = await client.get(
        "/questions?difficulty=easy",
        headers=auth_headers(student_token),
    )
    ids = [i["id"] for i in resp.json()["items"]]
    assert easy.id in ids
    for item in resp.json()["items"]:
        assert item["difficulty"] == "easy"


async def test_list_questions_student_no_correct_answer(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "NoAnswer")
    await _seed_question(db, cat.id, admin_user.id)

    resp = await client.get("/questions", headers=auth_headers(student_token))
    for item in resp.json()["items"]:
        assert item["correct_answer"] is None
        assert item["rationale"] is None


async def test_list_questions_admin_sees_correct_answer(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "AdminAnswer")
    await _seed_question(db, cat.id, admin_user.id)

    resp = await client.get("/questions", headers=auth_headers(admin_token))
    for item in resp.json()["items"]:
        assert item["correct_answer"] is not None
        assert item["rationale"] is not None


async def test_list_questions_requires_auth(client: AsyncClient):
    resp = await client.get("/questions")
    assert resp.status_code in (401, 403)


async def test_list_questions_pagination(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "PageCat")
    for _ in range(5):
        await _seed_question(db, cat.id, admin_user.id)

    resp = await client.get(
        f"/questions?category_id={cat.id}&per_page=2&page=1",
        headers=auth_headers(student_token),
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["meta"]["per_page"] == 2
    assert data["meta"]["total"] >= 5


# ── GET /questions/{id} ──────────────────────────────────────────────────────

async def test_get_question_student_no_answer_rationale(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "GetQ")
    q = await _seed_question(db, cat.id, admin_user.id)

    resp = await client.get(f"/questions/{q.id}", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct_answer"] is None
    assert data["rationale"] is None


async def test_get_question_admin_full_fields(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "GetQAdmin")
    q = await _seed_question(db, cat.id, admin_user.id)

    resp = await client.get(f"/questions/{q.id}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["correct_answer"] == 1
    assert resp.json()["rationale"] is not None


async def test_get_question_soft_deleted_returns_404(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "DelQ")
    q = await _seed_question(db, cat.id, admin_user.id, is_deleted=True)

    resp = await client.get(f"/questions/{q.id}", headers=auth_headers(admin_token))
    assert resp.status_code == 404


async def test_get_draft_question_as_student_returns_404(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    """Student probing a draft question ID gets 404, not 403 — anti-enumeration."""
    cat = await _seed_category(db, "DraftQ")
    q = await _seed_question(db, cat.id, admin_user.id, status=QStatus.draft)

    resp = await client.get(f"/questions/{q.id}", headers=auth_headers(student_token))
    assert resp.status_code == 404


# ── POST /questions ──────────────────────────────────────────────────────────

async def test_create_question_admin_success(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "CreateQ")

    resp = await client.post("/questions", json={
        "stem": "A nurse is caring for...",
        "options": [{"text": "A"}, {"text": "B"}, {"text": "C"}, {"text": "D"}],
        "correct_answer": 2,
        "rationale": "C is correct because...",
        "category_id": cat.id,
        "nclex_domain": "Safe Care",
        "difficulty": "medium",
    }, headers=auth_headers(admin_token))

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["correct_answer"] == 2


async def test_create_question_student_forbidden(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "StudentCreate")
    resp = await client.post("/questions", json={
        "stem": "...", "options": [{"text": x} for x in "ABCD"],
        "correct_answer": 0, "rationale": "r", "category_id": cat.id,
        "nclex_domain": "d", "difficulty": "easy",
    }, headers=auth_headers(student_token))
    assert resp.status_code in (401, 403)


async def test_create_question_invalid_category(
    client: AsyncClient, admin_token: str
):
    resp = await client.post("/questions", json={
        "stem": "...", "options": [{"text": x} for x in "ABCD"],
        "correct_answer": 0, "rationale": "r", "category_id": 99999,
        "nclex_domain": "d", "difficulty": "easy",
    }, headers=auth_headers(admin_token))
    assert resp.status_code == 400


# ── PATCH /questions/{id}/status ─────────────────────────────────────────────

async def test_status_workflow_draft_to_in_review(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "WF1")
    q = await _seed_question(db, cat.id, admin_user.id, status=QStatus.draft)

    resp = await client.patch(
        f"/questions/{q.id}/status",
        json={"status": "in_review"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


async def test_status_workflow_in_review_to_published(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "WF2")
    q = await _seed_question(db, cat.id, admin_user.id, status=QStatus.in_review)

    resp = await client.patch(
        f"/questions/{q.id}/status",
        json={"status": "published"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "published"
    assert data["reviewed_by"] is not None


async def test_status_workflow_invalid_transition_400(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    """draft → published is not an allowed transition."""
    cat = await _seed_category(db, "WF3")
    q = await _seed_question(db, cat.id, admin_user.id, status=QStatus.draft)

    resp = await client.patch(
        f"/questions/{q.id}/status",
        json={"status": "published"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "invalid_transition"
    assert "draft" in detail["current_status"]
    assert "allowed" in detail


async def test_edit_published_question_resets_to_in_review(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token
):
    cat = await _seed_category(db, "EditPub")
    q = await _seed_question(db, cat.id, admin_user.id, status=QStatus.published)

    resp = await client.patch(
        f"/questions/{q.id}",
        json={"stem": "Updated stem text"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


# ── Bookmarks ────────────────────────────────────────────────────────────────

async def test_bookmark_question_success(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "BookmarkCat")
    q = await _seed_question(db, cat.id, admin_user.id)

    resp = await client.post(
        f"/questions/{q.id}/bookmark",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200

    bm = await db.scalar(
        __import__("sqlalchemy", fromlist=["select"]).select(Bookmark).where(
            Bookmark.user_id == student_user.id,
            Bookmark.question_id == q.id,
        )
    )
    assert bm is not None


async def test_bookmark_idempotent(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    """Bookmarking twice should not error — ON CONFLICT DO NOTHING."""
    cat = await _seed_category(db, "BmIdempotent")
    q = await _seed_question(db, cat.id, admin_user.id)

    await client.post(f"/questions/{q.id}/bookmark", headers=auth_headers(student_token))
    resp = await client.post(f"/questions/{q.id}/bookmark", headers=auth_headers(student_token))
    assert resp.status_code == 200


async def test_unbookmark_question(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    from sqlalchemy import select as sa_select
    cat = await _seed_category(db, "UnbookmarkCat")
    q = await _seed_question(db, cat.id, admin_user.id)

    await client.post(f"/questions/{q.id}/bookmark", headers=auth_headers(student_token))

    resp = await client.delete(
        f"/questions/{q.id}/bookmark",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200

    bm = await db.scalar(
        sa_select(Bookmark).where(
            Bookmark.user_id == student_user.id,
            Bookmark.question_id == q.id,
        )
    )
    assert bm is None


async def test_unbookmark_idempotent(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    """Deleting a non-existent bookmark should not error."""
    cat = await _seed_category(db, "UnbmIdempotent")
    q = await _seed_question(db, cat.id, admin_user.id)

    resp = await client.delete(
        f"/questions/{q.id}/bookmark",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200


async def test_bookmark_soft_deleted_question_404(
    client: AsyncClient, db: AsyncSession, admin_user, student_token
):
    cat = await _seed_category(db, "BmSoftDel")
    q = await _seed_question(db, cat.id, admin_user.id, is_deleted=True)

    resp = await client.post(
        f"/questions/{q.id}/bookmark",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404