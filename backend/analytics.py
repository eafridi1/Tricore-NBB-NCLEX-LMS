"""
backend/analytics.py
======================
Shared async query functions for student performance analytics.
Called from both routers/admin.py and routers/users.py (via
GET /admin/analytics/me and GET /admin/analytics/students/{user_id}).

IMPORTANT — PostgreSQL-only functions:
  get_weak_areas() and get_at_risk_students() use PostgreSQL-specific
  features (jsonb_array_elements, CAST to JSONB, ROW_NUMBER OVER).
  They will raise errors against the in-memory SQLite test database.
  Use separate pytest marks for these:

      @pytest.mark.postgres_only
      async def test_weak_areas(...):
          ...  # requires a real PostgreSQL connection

  get_avg_score(), get_score_trend(), and get_total_attempts() are
  standard SQL and work fine against SQLite in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import AttemptStatus, Category, Question, QuizAttempt, User


# ── Return types ─────────────────────────────────────────────────────────────

@dataclass
class WeakAreaRow:
    category_id: int
    category_name: str
    avg_score: float
    attempt_count: int


@dataclass
class AtRiskStudent:
    user_id: int
    name: str
    email: str
    avg_score: float        # average of the last `consecutive` attempts
    last_attempt: datetime


# ── 1. get_avg_score ─────────────────────────────────────────────────────────

async def get_avg_score(db: AsyncSession, user_id: int) -> float:
    """
    Average score (0.0–100.0) across ALL completed quiz attempts for a user.
    Returns 0.0 if no completed attempts exist.

    Standard SQL — works against SQLite in tests.
    """
    result = await db.execute(
        select(func.avg(QuizAttempt.score))
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == AttemptStatus.completed,
            QuizAttempt.score.is_not(None),
        )
    )
    avg = result.scalar_one_or_none()
    return round(float(avg), 2) if avg is not None else 0.0


# ── 2. get_weak_areas ────────────────────────────────────────────────────────

async def get_weak_areas(
    db: AsyncSession,
    user_id: int,
    threshold: float = 60.0,
) -> list[WeakAreaRow]:
    """
    Per-category average score for a student, returning only categories
    where avg < threshold.

    How the scoring works per category:
      - A quiz attempt has `question_ids` (JSONB array of ints) and
        `answers` (JSONB dict {str(question_id): chosen_index}).
      - We unnest question_ids to get each question_id per attempt,
        join to questions to get category_id, then check whether the
        student's chosen_index matches that question's correct_answer.
      - Per-category average = (correct answers in category /
                                total answered questions in category) * 100

    POSTGRESQL-ONLY — uses jsonb_array_elements and CAST.
    Will not run against SQLite test database.
    """

    # The raw SQL here is intentional, not laziness. SQLAlchemy's ORM
    # layer has no clean abstraction for JSONB unnesting + lateral joins.
    # The equivalent Python-side approach would require loading every
    # completed attempt's full question_ids and answers into memory
    # before computing the aggregate — at 10k+ attempts that becomes a
    # meaningful memory issue. The SQL stays in the DB engine where it
    # belongs, with the computation close to the data.
    sql = text("""
        WITH unnested AS (
            -- Step 1: expand each attempt's question_ids JSONB array
            -- into one row per (attempt, question_id)
            SELECT
                qa.id                                      AS attempt_id,
                qa.answers                                 AS answers,
                (elem.value::text)::int                    AS question_id
            FROM quiz_attempts qa,
                 jsonb_array_elements(qa.question_ids) AS elem(value)
            WHERE qa.user_id     = :user_id
              AND qa.status      = 'completed'
        ),
        with_category AS (
            -- Step 2: join to questions to get category_id and correct_answer
            SELECT
                u.attempt_id,
                u.answers,
                u.question_id,
                q.category_id,
                q.correct_answer
            FROM unnested u
            JOIN questions q ON q.id = u.question_id
            WHERE q.is_deleted = FALSE
        ),
        scored AS (
            -- Step 3: check whether the student's answer was correct.
            -- answers JSONB keys are always strings (the JSONB string-key
            -- gotcha documented in quizzes.py) so we cast question_id to
            -- text before the lookup.
            SELECT
                wc.category_id,
                CASE
                    WHEN (wc.answers ->> wc.question_id::text)::int = wc.correct_answer
                    THEN 1.0
                    ELSE 0.0
                END AS is_correct
            FROM with_category wc
            -- Only score questions the student actually answered.
            -- Unanswered questions (key absent from answers dict) are
            -- excluded from the average rather than counted as wrong —
            -- consistent with how finish_quiz.py handles unanswered
            -- questions (they're still in the denominator there, but
            -- in per-CATEGORY analytics, excluding them gives a fairer
            -- picture of "how did you do in Cardiovascular" vs
            -- "how many Cardiovascular questions did you skip").
            WHERE wc.answers ? wc.question_id::text
        ),
        category_avg AS (
            -- Step 4: per-category aggregate
            SELECT
                s.category_id,
                AVG(s.is_correct) * 100.0 AS avg_score,
                COUNT(*)                   AS attempt_count
            FROM scored s
            GROUP BY s.category_id
        )
        -- Step 5: filter to weak areas and join category names
        SELECT
            ca.category_id,
            c.name          AS category_name,
            ca.avg_score,
            ca.attempt_count
        FROM category_avg ca
        JOIN categories c ON c.id = ca.category_id
        WHERE ca.avg_score < :threshold
        ORDER BY ca.avg_score ASC
    """)

    result = await db.execute(sql, {"user_id": user_id, "threshold": threshold})
    rows = result.fetchall()

    return [
        WeakAreaRow(
            category_id=row.category_id,
            category_name=row.category_name,
            avg_score=round(float(row.avg_score), 2),
            attempt_count=int(row.attempt_count),
        )
        for row in rows
    ]


# ── 3. get_score_trend ───────────────────────────────────────────────────────

async def get_score_trend(
    db: AsyncSession,
    user_id: int,
    period: str = "all",
) -> list[dict]:
    """
    Time-series of quiz scores for a student.
    Returns list of {date: "YYYY-MM-DD", score: float} ordered
    chronologically (oldest first) for charting.

    period values: "weekly" (last 7 days), "monthly" (last 30 days),
                   "all" (no date filter).

    Standard SQL — works against SQLite in tests.
    """
    query = (
        select(QuizAttempt.finished_at, QuizAttempt.score)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == AttemptStatus.completed,
            QuizAttempt.score.is_not(None),
            QuizAttempt.finished_at.is_not(None),
        )
        .order_by(QuizAttempt.finished_at.asc())
    )

    now = datetime.now(timezone.utc)
    if period == "weekly":
        query = query.where(
            QuizAttempt.finished_at >= now - timedelta(days=7)
        )
    elif period == "monthly":
        query = query.where(
            QuizAttempt.finished_at >= now - timedelta(days=30)
        )
    # "all" — no additional filter

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "date": row.finished_at.strftime("%Y-%m-%d"),
            "score": round(float(row.score), 2),
        }
        for row in rows
    ]


# ── 4. get_at_risk_students ──────────────────────────────────────────────────

async def get_at_risk_students(
    db: AsyncSession,
    threshold: float = 60.0,
    consecutive: int = 3,
) -> list[AtRiskStudent]:
    """
    Platform-wide at-risk detection: returns students whose last
    `consecutive` completed quiz attempts ALL had score < threshold.

    Uses ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY finished_at DESC)
    to rank each user's attempts from newest to oldest, then filters to
    the top N and checks whether all of them are below threshold.

    POSTGRESQL-ONLY — uses window functions and subquery structure
    that SQLite handles differently. Will not run against SQLite tests.
    """
    sql = text("""
        WITH ranked AS (
            -- Rank each user's completed attempts newest-first
            SELECT
                user_id,
                score,
                finished_at,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY finished_at DESC
                ) AS rn
            FROM quiz_attempts
            WHERE status = 'completed'
              AND score  IS NOT NULL
        ),
        last_n AS (
            -- Keep only the last `consecutive` attempts per user
            SELECT user_id, score, finished_at
            FROM ranked
            WHERE rn <= :consecutive
        ),
        at_risk AS (
            -- A student is at-risk only if they have exactly `consecutive`
            -- recent attempts AND every one of them is below threshold.
            -- The COUNT(*) = :consecutive check prevents flagging a student
            -- who has taken only 1 or 2 quizzes (fewer than `consecutive`)
            -- from being flagged just because that one attempt was low.
            SELECT
                user_id,
                AVG(score)    AS avg_score,
                MAX(finished_at) AS last_attempt
            FROM last_n
            GROUP BY user_id
            HAVING COUNT(*) = :consecutive
               AND MAX(score) < :threshold
        )
        SELECT
            ar.user_id,
            u.name,
            u.email,
            ar.avg_score,
            ar.last_attempt
        FROM at_risk ar
        JOIN users u ON u.id = ar.user_id
        ORDER BY ar.avg_score ASC
    """)

    result = await db.execute(
        sql,
        {"threshold": threshold, "consecutive": consecutive},
    )
    rows = result.fetchall()

    return [
        AtRiskStudent(
            user_id=row.user_id,
            name=row.name,
            email=row.email,
            avg_score=round(float(row.avg_score), 2),
            last_attempt=row.last_attempt,
        )
        for row in rows
    ]


# ── 5. get_total_attempts ────────────────────────────────────────────────────

async def get_total_attempts(db: AsyncSession, user_id: int) -> int:
    """
    Total number of completed quiz attempts for a user.
    Standard SQL — works against SQLite in tests.
    """
    result = await db.execute(
        select(func.count())
        .select_from(QuizAttempt)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == AttemptStatus.completed,
        )
    )
    return result.scalar_one()