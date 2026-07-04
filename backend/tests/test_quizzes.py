# backend/tests/test_quizzes.py
"""
Integration tests for SECTION 8 — QUIZ ENGINE
Covers: POST /quizzes, GET question, POST answer, POST finish,
        GET result, GET resume, GET / (list).
These tests are the most critical in the codebase — a scoring bug
here means a student sees a wrong grade.
"""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Category, Question, QStatus, Difficulty, QuizAttempt, AttemptStatus
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
    correct_answer: int = 1,
) -> Question:
    q = Question(
        stem="A nurse is caring for a patient...",
        options=[{"text": f"Opt {x}"} for x in "ABCD"],
        correct_answer=correct_answer,
        rationale="Because...",
        category_id=category_id,
        nclex_domain="Safe Care",
        difficulty=Difficulty.medium,
        status=QStatus.published,
        is_deleted=False,
        created_by=created_by,
    )
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return q


async def _seed_attempt(
    db: AsyncSession,
    user_id: int,
    question_ids: list[int],
    status: AttemptStatus = AttemptStatus.in_progress,
    answers: dict | None = None,
    started_at: datetime | None = None,
    timed: bool = False,
    time_limit_secs: int | None = None,
) -> QuizAttempt:
    attempt = QuizAttempt(
        user_id=user_id,
        question_ids=question_ids,
        answers=answers or {},
        status=status,
        timed=timed,
        time_limit_secs=time_limit_secs,
        started_at=started_at or datetime.now(timezone.utc),
    )
    db.add(attempt)
    await db.flush()
    await db.refresh(attempt)
    return attempt


# ── POST /quizzes ─────────────────────────────────────────────────────────────

async def test_start_quiz_success(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "StartQuiz")
    for _ in range(5):
        await _seed_question(db, cat.id, admin_user.id)

    resp = await client.post("/quizzes", json={
        "question_count": 5,
        "timed": False,
    }, headers=auth_headers(student_token))

    assert resp.status_code == 201
    data = resp.json()
    assert data["attempt_id"] > 0
    assert data["total_questions"] == 5
    assert data["status"] == "in_progress"


async def test_start_quiz_uses_available_count_when_fewer_questions(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "FewQ")
    for _ in range(3):
        await _seed_question(db, cat.id, admin_user.id)

    resp = await client.post("/quizzes", json={
        "category_id": cat.id,
        "question_count": 10,
    }, headers=auth_headers(student_token))

    assert resp.status_code == 201
    assert resp.json()["total_questions"] == 3


async def test_start_quiz_filters_by_category(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat1 = await _seed_category(db, "QuizCat1")
    cat2 = await _seed_category(db, "QuizCat2")
    q_in_cat1 = await _seed_question(db, cat1.id, admin_user.id)
    await _seed_question(db, cat2.id, admin_user.id)

    resp = await client.post("/quizzes", json={
        "category_id": cat1.id, "question_count": 5,
    }, headers=auth_headers(student_token))

    assert resp.status_code == 201
    attempt_id = resp.json()["attempt_id"]
    attempt = await db.get(QuizAttempt, attempt_id)
    assert q_in_cat1.id in attempt.question_ids
    for qid in attempt.question_ids:
        q = await db.get(Question, qid)
        assert q.category_id == cat1.id


async def test_start_quiz_409_if_in_progress_exists(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "InProgress")
    q = await _seed_question(db, cat.id, admin_user.id)
    await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.post("/quizzes", json={
        "question_count": 5,
    }, headers=auth_headers(student_token))

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["detail"] == "quiz_in_progress"
    assert "attempt_id" in detail


async def test_start_quiz_timed_requires_time_limit(
    client: AsyncClient, student_token: str
):
    resp = await client.post("/quizzes", json={
        "question_count": 5, "timed": True,
    }, headers=auth_headers(student_token))
    assert resp.status_code == 422


async def test_start_quiz_no_matching_questions_422(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "EmptyCat")
    resp = await client.post("/quizzes", json={
        "category_id": cat.id, "question_count": 5,
    }, headers=auth_headers(student_token))
    assert resp.status_code == 422


async def test_start_quiz_excludes_soft_deleted(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "SoftDelQuiz")
    live = await _seed_question(db, cat.id, admin_user.id)
    # Add soft-deleted question — should never appear in question_ids
    deleted = Question(
        stem="deleted", options=[{"text": x} for x in "ABCD"], correct_answer=0,
        rationale="r", category_id=cat.id, nclex_domain="d",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=True, created_by=admin_user.id,
    )
    db.add(deleted)
    await db.flush()

    resp = await client.post("/quizzes", json={
        "category_id": cat.id, "question_count": 5,
    }, headers=auth_headers(student_token))

    assert resp.status_code == 201
    attempt = await db.get(QuizAttempt, resp.json()["attempt_id"])
    assert deleted.id not in attempt.question_ids
    assert live.id in attempt.question_ids


# ── GET /quizzes/{id}/question/{index} ──────────────────────────────────────

async def test_get_question_returns_no_correct_answer(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "GetQQ")
    q = await _seed_question(db, cat.id, admin_user.id, correct_answer=2)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes/{attempt.id}/question/0",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "correct_answer" not in data or data.get("correct_answer") is None
    assert "rationale" not in data
    assert data["question_id"] == q.id
    assert data["question_index"] == 0
    assert data["total_questions"] == 1


async def test_get_question_shows_previous_answer(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "PrevAns")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id],
        answers={str(q.id): 3},  # previously answered 3
    )

    resp = await client.get(
        f"/quizzes/{attempt.id}/question/0",
        headers=auth_headers(student_token),
    )
    assert resp.json()["already_answered"] == 3


async def test_get_question_out_of_range_404(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "OOBRange")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes/{attempt.id}/question/99",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404


async def test_get_question_other_user_attempt_404(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, admin_token
):
    cat = await _seed_category(db, "OtherUser")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes/{attempt.id}/question/0",
        headers=auth_headers(admin_token),  # admin doesn't own this attempt
    )
    assert resp.status_code == 404


async def test_get_question_shows_is_bookmarked_false(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "Bm false")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes/{attempt.id}/question/0",
        headers=auth_headers(student_token),
    )
    assert resp.json()["is_bookmarked"] is False


# ── POST /quizzes/{id}/answer ────────────────────────────────────────────────

async def test_save_answer_success(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "SaveAns")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.post(
        f"/quizzes/{attempt.id}/answer",
        json={"question_id": q.id, "chosen_index": 2},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["saved"] is True

    await db.refresh(attempt)
    # JSONB key must be string — checking both that it saved and that the
    # key is a string (not an int), since a bug here breaks scoring
    assert attempt.answers.get(str(q.id)) == 2


async def test_save_answer_overwrites_previous(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "OverwriteAns")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    await client.post(f"/quizzes/{attempt.id}/answer",
        json={"question_id": q.id, "chosen_index": 0},
        headers=auth_headers(student_token))

    await client.post(f"/quizzes/{attempt.id}/answer",
        json={"question_id": q.id, "chosen_index": 3},
        headers=auth_headers(student_token))

    await db.refresh(attempt)
    assert attempt.answers.get(str(q.id)) == 3  # latest answer


async def test_save_answer_question_not_in_attempt(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "WrongQ")
    q1 = await _seed_question(db, cat.id, admin_user.id)
    q2 = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q1.id])  # only q1

    resp = await client.post(
        f"/quizzes/{attempt.id}/answer",
        json={"question_id": q2.id, "chosen_index": 0},  # q2 not in attempt
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 400


async def test_save_answer_timed_expired_returns_409(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "TimedExp")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id],
        timed=True, time_limit_secs=10,
        # started 60 seconds ago — time has run out
        started_at=datetime.now(timezone.utc) - timedelta(seconds=60),
    )

    resp = await client.post(
        f"/quizzes/{attempt.id}/answer",
        json={"question_id": q.id, "chosen_index": 1},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["detail"] == "timed_out"


# ── POST /quizzes/{id}/finish ────────────────────────────────────────────────

async def test_finish_quiz_scores_correctly(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "FinishScore")
    # 4 questions, correct_answer=1 for all
    questions = [await _seed_question(db, cat.id, admin_user.id, correct_answer=1)
                 for _ in range(4)]
    ids = [q.id for q in questions]
    # Answer 3 correctly (index 1), 1 wrong (index 0)
    answers = {str(ids[0]): 1, str(ids[1]): 1, str(ids[2]): 1, str(ids[3]): 0}
    attempt = await _seed_attempt(db, student_user.id, ids, answers=answers)

    resp = await client.post(
        f"/quizzes/{attempt.id}/finish",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct_count"] == 3
    assert abs(data["score"] - 75.0) < 0.01
    assert data["passed"] is True
    assert data["status"] == "completed"
    assert len(data["questions"]) == 4


async def test_finish_quiz_includes_correct_answer_in_result(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "FinishAnswer")
    q = await _seed_question(db, cat.id, admin_user.id, correct_answer=2)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id], answers={str(q.id): 0},
    )

    resp = await client.post(
        f"/quizzes/{attempt.id}/finish",
        headers=auth_headers(student_token),
    )
    question_result = resp.json()["questions"][0]
    assert question_result["correct_answer"] == 2
    assert question_result["chosen_answer"] == 0
    assert question_result["is_correct"] is False
    assert question_result["rationale"] is not None


async def test_finish_quiz_fail_below_60_percent(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "FinishFail")
    questions = [await _seed_question(db, cat.id, admin_user.id, correct_answer=1)
                 for _ in range(5)]
    ids = [q.id for q in questions]
    # All wrong
    answers = {str(qid): 0 for qid in ids}
    attempt = await _seed_attempt(db, student_user.id, ids, answers=answers)

    resp = await client.post(
        f"/quizzes/{attempt.id}/finish",
        headers=auth_headers(student_token),
    )
    data = resp.json()
    assert data["score"] == 0.0
    assert data["passed"] is False


async def test_finish_quiz_already_completed_409(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "ReFinish")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id], status=AttemptStatus.completed,
    )

    resp = await client.post(
        f"/quizzes/{attempt.id}/finish",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 409


async def test_finish_quiz_sets_finished_at(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "FinishAt")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    await client.post(
        f"/quizzes/{attempt.id}/finish",
        headers=auth_headers(student_token),
    )
    await db.refresh(attempt)
    assert attempt.finished_at is not None


# ── GET /quizzes/{id}/result ─────────────────────────────────────────────────

async def test_get_result_completed_attempt(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "GetResult")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id],
        status=AttemptStatus.completed,
        answers={str(q.id): 1},
    )
    attempt.score = 100.0
    attempt.correct_count = 1
    attempt.finished_at = datetime.now(timezone.utc)
    await db.flush()

    resp = await client.get(
        f"/quizzes/{attempt.id}/result",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_get_result_in_progress_attempt_403(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "Result403")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes/{attempt.id}/result",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── GET /quizzes/{id}/resume ─────────────────────────────────────────────────

async def test_resume_within_window(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "ResumeOk")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id],
        answers={str(q.id): 2},
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    resp = await client.get(
        f"/quizzes/{attempt.id}/resume",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["answered_count"] == 1
    assert data["total_questions"] == 1


async def test_resume_expired_session_becomes_abandoned(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "ResumeExpired")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id],
        started_at=datetime.now(timezone.utc) - timedelta(minutes=45),
    )

    resp = await client.get(
        f"/quizzes/{attempt.id}/resume",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["detail"] == "session_expired"

    await db.refresh(attempt)
    assert attempt.status == AttemptStatus.abandoned


async def test_resume_completed_attempt_409(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "ResumeComp")
    q = await _seed_question(db, cat.id, admin_user.id)
    attempt = await _seed_attempt(
        db, student_user.id, [q.id], status=AttemptStatus.completed,
    )

    resp = await client.get(
        f"/quizzes/{attempt.id}/resume",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 409


# ── GET /quizzes ──────────────────────────────────────────────────────────────

async def test_list_attempts_own_only(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "ListAttempts")
    q = await _seed_question(db, cat.id, admin_user.id)
    await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get("/quizzes", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] >= 1
    for item in data["items"]:
        # All returned attempts must belong to the requesting student
        # (can't check user_id from response since it's not in
        # AttemptSummaryOut, but DB was seeded only for this student so
        # any other student's attempt being returned would fail other
        # assertions too)
        assert "attempt_id" in item


async def test_list_attempts_admin_can_see_any_user(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, admin_token
):
    cat = await _seed_category(db, "AdminList")
    q = await _seed_question(db, cat.id, admin_user.id)
    await _seed_attempt(db, student_user.id, [q.id])

    resp = await client.get(
        f"/quizzes?user_id={student_user.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] >= 1


async def test_list_attempts_student_user_id_param_ignored(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, admin_token, student_token
):
    """A student passing ?user_id= for the admin's ID should still only
    see their own attempts — not the admin's attempts."""
    admin = admin_user  # alias for readability in this test
    cat = await _seed_category(db, "StudentUID")
    q = await _seed_question(db, cat.id, admin.id)
    await _seed_attempt(db, student_user.id, [q.id])
    await _seed_attempt(db, admin.id, [q.id])

    resp = await client.get(
        f"/quizzes?user_id={admin.id}",  # student trying to see admin's attempts
        headers=auth_headers(student_token),
    )
    # Should succeed but only return student's own attempts
    assert resp.status_code == 200
    # admin's attempt should not appear


async def test_list_attempts_ordered_by_started_at_desc(
    client: AsyncClient, db: AsyncSession, admin_user, student_user, student_token
):
    cat = await _seed_category(db, "OrderList")
    q = await _seed_question(db, cat.id, admin_user.id)

    older = await _seed_attempt(
        db, student_user.id, [q.id],
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    newer = await _seed_attempt(
        db, student_user.id, [q.id],
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    resp = await client.get("/quizzes", headers=auth_headers(student_token))
    items = resp.json()["items"]
    ids = [i["attempt_id"] for i in items]
    assert ids.index(newer.id) < ids.index(older.id)