# backend/tests/test_content.py
"""
Integration tests for Week 3 content endpoints:
GET/POST /announcements, GET /videos, POST /videos/{id}/progress,
GET /admin/analytics/me, GET /admin/stats
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import (
    Announcement, Video, VideoProgress, Category,
    QuizAttempt, AttemptStatus, Question, QStatus, Difficulty,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


# ── Seed helpers ──────────────────────────────────────────────────────────────

async def _seed_category(db: AsyncSession, name: str = "Cardio") -> Category:
    cat = Category(name=name, sort_order=0)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def _seed_announcement(
    db: AsyncSession, admin_id: int,
    title: str = "Test Announcement",
    is_published: bool = True,
) -> Announcement:
    a = Announcement(
        title=title,
        body="Test body content.",
        is_published=is_published,
        published_at=datetime.now(timezone.utc) if is_published else None,
        created_by=admin_id,
    )
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


async def _seed_video(
    db: AsyncSession, category_id: int,
    is_published: bool = True,
) -> Video:
    v = Video(
        title="Test Video",
        description="A test lecture.",
        category_id=category_id,
        storage_url="videos/test.mp4",
        duration_secs=900,
        sort_order=0,
        is_published=is_published,
    )
    db.add(v)
    await db.flush()
    await db.refresh(v)
    return v


async def _seed_completed_attempt(
    db: AsyncSession,
    user_id: int,
    admin_id: int,
    category_id: int,
    score: float = 80.0,
) -> QuizAttempt:
    """Seed a question and a completed quiz attempt for analytics tests."""
    q = Question(
        stem="A nurse is assessing...",
        options=[{"text": x} for x in ["A", "B", "C", "D"]],
        correct_answer=1,
        rationale="Because...",
        category_id=category_id,
        nclex_domain="Safe Care",
        difficulty=Difficulty.medium,
        status=QStatus.published,
        is_deleted=False,
        created_by=admin_id,
    )
    db.add(q)
    await db.flush()

    attempt = QuizAttempt(
        user_id=user_id,
        question_ids=[q.id],
        answers={str(q.id): 1},  # correct answer
        status=AttemptStatus.completed,
        score=score,
        correct_count=1,
        timed=False,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt


# ── GET /announcements ────────────────────────────────────────────────────────

async def test_announcements_student_sees_published_only(
    client: AsyncClient, db: AsyncSession, admin_user, student_token: str
):
    await _seed_announcement(db, admin_user.id, "Published One", is_published=True)
    await _seed_announcement(db, admin_user.id, "Draft One", is_published=False)

    resp = await client.get("/announcements", headers=auth_headers(student_token))
    assert resp.status_code == 200
    items = resp.json()["items"]

    titles = [i["title"] for i in items]
    assert "Published One" in titles
    assert "Draft One" not in titles


async def test_announcements_admin_sees_all(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    await _seed_announcement(db, admin_user.id, "Published Two", is_published=True)
    await _seed_announcement(db, admin_user.id, "Draft Two", is_published=False)

    resp = await client.get("/announcements", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    titles = [i["title"] for i in items]
    assert "Published Two" in titles
    assert "Draft Two" in titles


async def test_announcements_requires_auth(client: AsyncClient):
    resp = await client.get("/announcements")
    assert resp.status_code in (401, 403)


async def test_announcements_pagination(
    client: AsyncClient, db: AsyncSession, admin_user, student_token: str
):
    for i in range(5):
        await _seed_announcement(db, admin_user.id, f"Ann {i}", is_published=True)

    resp = await client.get(
        "/announcements?page=1&per_page=2",
        headers=auth_headers(student_token),
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["meta"]["per_page"] == 2


# ── POST /announcements ───────────────────────────────────────────────────────

async def test_create_announcement_admin_published(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/announcements",
        json={"title": "New Ann", "body": "Body text.", "is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "New Ann"
    assert data["is_published"] is True
    assert data["published_at"] is not None


async def test_create_announcement_admin_draft(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/announcements",
        json={"title": "Draft Ann", "body": "Draft body.", "is_published": False},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_published"] is False
    assert data["published_at"] is None


async def test_create_announcement_student_forbidden(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/announcements",
        json={"title": "Hack", "body": "...", "is_published": True},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_create_announcement_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/announcements",
        json={"title": "Anon", "body": "..."},
    )
    assert resp.status_code in (401, 403)


async def test_published_announcement_appears_in_student_list(
    client: AsyncClient, admin_token: str, student_token: str
):
    """Create via admin, then confirm student can see it immediately."""
    create_resp = await client.post(
        "/announcements",
        json={"title": "Live Now", "body": "Students see this.", "is_published": True},
        headers=auth_headers(admin_token),
    )
    assert create_resp.status_code == 201

    list_resp = await client.get("/announcements", headers=auth_headers(student_token))
    titles = [i["title"] for i in list_resp.json()["items"]]
    assert "Live Now" in titles


# ── GET /videos ───────────────────────────────────────────────────────────────

async def test_list_videos_student_sees_published_only(
    client: AsyncClient, db: AsyncSession, student_token: str, active_subscription
):
    cat = await _seed_category(db, "VideoTest")
    await _seed_video(db, cat.id, is_published=True)
    await _seed_video(db, cat.id, is_published=False)

    resp = await client.get("/videos", headers=auth_headers(student_token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["is_published"] is True


async def test_list_videos_admin_sees_unpublished(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "AdminVideo")
    unpublished = await _seed_video(db, cat.id, is_published=False)

    resp = await client.get("/videos", headers=auth_headers(admin_token))
    ids = [i["id"] for i in resp.json()["items"]]
    assert unpublished.id in ids


async def test_list_videos_filter_by_category(
    client: AsyncClient, db: AsyncSession, student_token: str, active_subscription
):
    cat1 = await _seed_category(db, "FilterVid1")
    cat2 = await _seed_category(db, "FilterVid2")
    v1 = await _seed_video(db, cat1.id)
    await _seed_video(db, cat2.id)

    resp = await client.get(
        f"/videos?category_id={cat1.id}",
        headers=auth_headers(student_token),
    )
    ids = [i["id"] for i in resp.json()["items"]]
    assert v1.id in ids
    for item in resp.json()["items"]:
        assert item["category_id"] == cat1.id


async def test_list_videos_empty_returns_valid_response(
    client: AsyncClient, student_token: str, active_subscription
):
    resp = await client.get("/videos", headers=auth_headers(student_token))
    assert resp.status_code == 200
    assert "items" in resp.json()
    assert "meta" in resp.json()


async def test_list_videos_requires_auth(client: AsyncClient):
    resp = await client.get("/videos")
    assert resp.status_code in (401, 403)


# ── POST /videos/{video_id}/progress ─────────────────────────────────────────

async def test_video_progress_upsert_creates_row(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    cat = await _seed_category(db, "ProgressCat")
    video = await _seed_video(db, cat.id)

    resp = await client.post(
        f"/videos/{video.id}/progress",
        json={"percent_watched": 45.0},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Progress saved."

    # Verify DB row was created
    progress = await db.scalar(
        select(VideoProgress).where(
            VideoProgress.user_id == student_user.id,
            VideoProgress.video_id == video.id,
        )
    )
    assert progress is not None
    assert progress.percent_watched == 45


async def test_video_progress_upsert_second_call_updates_not_inserts(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    """Second call with different percent must UPDATE, not create a second row."""
    cat = await _seed_category(db, "UpsertCat")
    video = await _seed_video(db, cat.id)

    await client.post(
        f"/videos/{video.id}/progress",
        json={"percent_watched": 30.0},
        headers=auth_headers(student_token),
    )
    await client.post(
        f"/videos/{video.id}/progress",
        json={"percent_watched": 75.0},
        headers=auth_headers(student_token),
    )

    # Must still be only ONE row in video_progress for this (user, video) pair
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count()).select_from(VideoProgress).where(
            VideoProgress.user_id == student_user.id,
            VideoProgress.video_id == video.id,
        )
    )
    assert count == 1

    # And the value must be the latest one
    progress = await db.scalar(
        select(VideoProgress).where(
            VideoProgress.user_id == student_user.id,
            VideoProgress.video_id == video.id,
        )
    )
    assert progress.percent_watched == 75


async def test_video_progress_video_not_found(
    client: AsyncClient, student_token: str
):
    resp = await client.post(
        "/videos/99999/progress",
        json={"percent_watched": 50.0},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404


async def test_video_progress_requires_auth(
    client: AsyncClient, db: AsyncSession
):
    cat = await _seed_category(db, "AuthCat")
    video = await _seed_video(db, cat.id)

    resp = await client.post(
        f"/videos/{video.id}/progress",
        json={"percent_watched": 50.0},
    )
    assert resp.status_code in (401, 403)


# ── GET /admin/analytics/me ──────────────────────────────────────────────────

async def test_analytics_me_returns_own_data(
    client: AsyncClient, db: AsyncSession, student_user, admin_user, student_token: str
):
    """After seeding a completed attempt, analytics/me returns real data."""
    cat = await _seed_category(db, "AnalyticsCat")
    await _seed_completed_attempt(db, student_user.id, admin_user.id, cat.id, score=80.0)

    resp = await client.get(
        "/admin/analytics/me",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == student_user.id
    assert data["avg_score"] == 80.0
    assert data["total_attempts"] == 1
    assert isinstance(data["score_trend"], list)
    assert len(data["score_trend"]) == 1
    assert data["score_trend"][0]["score"] == 80.0
    assert isinstance(data["weak_areas"], list)
    assert isinstance(data["is_at_risk"], bool)


async def test_analytics_me_no_attempts_returns_zeros(
    client: AsyncClient, student_token: str
):
    resp = await client.get(
        "/admin/analytics/me",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_score"] == 0.0
    assert data["total_attempts"] == 0
    assert data["score_trend"] == []


async def test_analytics_me_requires_auth(client: AsyncClient):
    resp = await client.get("/admin/analytics/me")
    assert resp.status_code in (401, 403)


async def test_analytics_me_period_filter(
    client: AsyncClient, db: AsyncSession, student_user, admin_user, student_token: str
):
    """period=weekly should only include recent attempts — basic shape check."""
    cat = await _seed_category(db, "PeriodCat")
    await _seed_completed_attempt(db, student_user.id, admin_user.id, cat.id, score=72.0)

    resp = await client.get(
        "/admin/analytics/me?period=weekly",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    # The attempt was just seeded (now), so it should appear in weekly
    assert resp.json()["total_attempts"] >= 1


# ── GET /admin/stats ──────────────────────────────────────────────────────────

async def test_admin_stats_returns_counts(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, admin_token: str
):
    """Stats should at minimum reflect the seeded admin + student users."""
    cat = await _seed_category(db, "StatsCat")

    resp = await client.get("/admin/stats", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()

    # Verify all required fields are present
    assert "total_students" in data
    assert "active_subscribers" in data
    assert "total_questions" in data
    assert "published_questions" in data
    assert "total_attempts_today" in data
    assert "revenue_this_month_cents" in data

    # student_user exists so total_students >= 1
    assert data["total_students"] >= 1
    # revenue is 0 until Slice 7
    assert data["revenue_this_month_cents"] == 0


async def test_admin_stats_student_gets_403(
    client: AsyncClient, student_token: str
):
    resp = await client.get("/admin/stats", headers=auth_headers(student_token))
    assert resp.status_code == 403


async def test_admin_stats_unauthenticated(client: AsyncClient):
    resp = await client.get("/admin/stats")
    assert resp.status_code in (401, 403)


async def test_admin_stats_counts_match_seeded_data(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    """Published questions count increases after seeding a published question."""
    cat = await _seed_category(db, "StatsQCat")
    q = Question(
        stem="Stats test question",
        options=[{"text": x} for x in ["A", "B", "C", "D"]],
        correct_answer=0, rationale="r",
        category_id=cat.id, nclex_domain="Safe Care",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=False, created_by=admin_user.id,
    )
    db.add(q)
    await db.flush()

    resp = await client.get("/admin/stats", headers=auth_headers(admin_token))
    data = resp.json()
    assert data["total_questions"] >= 1
    assert data["published_questions"] >= 1
    # published_questions must never exceed total_questions
    assert data["published_questions"] <= data["total_questions"]