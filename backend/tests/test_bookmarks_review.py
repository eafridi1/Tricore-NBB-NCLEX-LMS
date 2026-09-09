"""Tests for the hydrated bookmarks review endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers
from models import Question, Bookmark, QStatus, Difficulty


async def _seed_question(db: AsyncSession, created_by: int, category_id: int | None = None) -> Question:
    q = Question(
        stem="A client with heart failure should be monitored for which sign?",
        options=[{"text": "Bradycardia"}, {"text": "Crackles in the lungs"},
                 {"text": "Dry skin"}, {"text": "Hypotension only"}],
        correct_answer=1,
        rationale="Crackles indicate pulmonary congestion, a hallmark of heart failure.",
        category_id=category_id,
        nclex_domain="Physiological Integrity",
        difficulty=Difficulty.medium,
        status=QStatus.published,
        is_deleted=False,
        created_by=created_by,
    )
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return q


@pytest.mark.asyncio
async def test_review_returns_hydrated_bookmark(
    client: AsyncClient, db: AsyncSession, student_user, admin_user, student_token: str
):
    q = await _seed_question(db, created_by=admin_user.id)
    db.add(Bookmark(user_id=student_user.id, question_id=q.id))
    await db.flush()

    resp = await client.get("/bookmarks/review", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    item = data["items"][0]
    assert item["question_id"] == q.id
    assert item["stem"].startswith("A client with heart failure")
    assert len(item["options"]) == 4
    assert item["correct_answer"] == 1           # answer included (review context)
    assert "pulmonary congestion" in item["rationale"]


@pytest.mark.asyncio
async def test_review_only_own_bookmarks(
    client: AsyncClient, db: AsyncSession, student_user, admin_user, student_token: str
):
    q1 = await _seed_question(db, created_by=admin_user.id)
    q2 = await _seed_question(db, created_by=admin_user.id)
    db.add(Bookmark(user_id=student_user.id, question_id=q1.id))
    db.add(Bookmark(user_id=admin_user.id, question_id=q2.id))  # someone else's
    await db.flush()

    resp = await client.get("/bookmarks/review", headers=auth_headers(student_token))
    data = resp.json()
    assert data["meta"]["total"] == 1  # only the student's own
    assert data["items"][0]["question_id"] == q1.id


@pytest.mark.asyncio
async def test_review_requires_auth(client: AsyncClient, db: AsyncSession):
    resp = await client.get("/bookmarks/review")
    assert resp.status_code == 401