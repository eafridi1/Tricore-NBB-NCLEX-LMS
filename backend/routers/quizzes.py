"""
backend/routers/quizzes.py
============================
Real implementation of contract.py SECTION 8 — QUIZZES.
This file currently implements POST /quizzes only — the "start a quiz"
endpoint. The rest of SECTION 8 (answer, finish, result, resume, list) come
as separate implementation tasks per Week 2 Tasks 4.3–4.5.

Wire into main.py with:
    from routers import quizzes as quizzes_router
    app.include_router(quizzes_router.router, prefix="/quizzes", tags=["quizzes"])
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import cast, literal

from database import get_db
from dependencies import get_current_user, require_active_subscription, require_admin
from models import AttemptStatus, Bookmark, Category, Difficulty, Question, QStatus, QuizAttempt, User

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 8.

class QuizStartRequest(BaseModel):
    category_id: Optional[int] = Field(None, description="NULL = all categories")
    difficulty: Optional[Difficulty] = Field(None, description="NULL = mixed")
    question_count: int = Field(25, ge=5, le=100)
    timed: bool = Field(False)
    time_limit_secs: Optional[int] = Field(
        None, example=2700, description="Required if timed=true. 2700=45min"
    )


class QuizStartResponse(BaseModel):
    attempt_id: int
    total_questions: int
    time_limit_secs: Optional[int]
    status: AttemptStatus


class QuestionOption(BaseModel):
    """Mirrors questions.py's QuestionOption — duplicated here rather than
    imported across router files, since contract.py defines each section's
    models independently and importing across routers creates a coupling
    the contract itself doesn't have. If this drifts from questions.py's
    version, that's a sign the shared shape belongs in a models/schemas.py
    common module — not a problem to solve in this file."""
    text: str


class PaginationMeta(BaseModel):
    """Same duplication rationale as QuestionOption above — this shape is
    identical across questions.py, categories.py, and here. Worth
    promoting to a shared schemas.py once a 4th router needs it — three
    near-identical copies is a coincidence, four is a pattern worth
    consolidating."""
    total: int
    page: int
    per_page: int
    pages: int


class QuizQuestionResponse(BaseModel):
    """A single question as served during an active quiz — NO
    correct_answer or rationale fields exist on this model at all, unlike
    QuestionOut from questions.py which has them as Optional and strips by
    setting None. Here they're structurally absent — there's no way for
    this response to leak them even by a future bug, since the field
    doesn't exist on the Pydantic model to populate in the first place."""
    attempt_id: int
    question_index: int
    total_questions: int
    question_id: int
    stem: str
    options: list[QuestionOption]
    category_name: str
    difficulty: Difficulty
    is_bookmarked: bool
    time_remaining_secs: Optional[int]
    already_answered: Optional[int]


class AnswerRequest(BaseModel):
    question_id: int = Field(..., example=42)
    chosen_index: int = Field(..., ge=0, le=3, example=1)


class AnswerResponse(BaseModel):
    saved: bool


class QuestionResult(BaseModel):
    question_id: int
    stem: str
    options: list[QuestionOption]
    correct_answer: int
    chosen_answer: Optional[int]
    is_correct: bool
    rationale: str
    category_name: str
    difficulty: Difficulty


class QuizResultResponse(BaseModel):
    attempt_id: int
    score: float
    correct_count: int
    total_questions: int
    passed: bool
    time_taken_secs: Optional[int]
    status: AttemptStatus
    questions: list[QuestionResult]


class QuizResumeResponse(BaseModel):
    attempt_id: int
    status: AttemptStatus
    answered_count: int
    total_questions: int
    time_remaining_secs: Optional[int]


class AttemptSummaryOut(BaseModel):
    attempt_id: int
    score: Optional[float]
    correct_count: Optional[int]
    total_questions: int
    status: AttemptStatus
    time_taken_secs: Optional[int]
    started_at: datetime
    finished_at: Optional[datetime]
    category_name: Optional[str]


class AttemptListResponse(BaseModel):
    items: list[AttemptSummaryOut]
    meta: PaginationMeta


# ── Config constants ─────────────────────────────────────────────────────────
# 30-minute in-progress window matches Slice 3's resume/abandon logic
# (Task 4.5 — GET /quizzes/{id}/resume) so "is there already an in-progress
# attempt" and "has this attempt expired" use the same threshold everywhere
# rather than two different numbers that could drift out of sync.
IN_PROGRESS_WINDOW_MINUTES = 30

PASS_THRESHOLD = 60.0
AT_RISK_THRESHOLD = 60.0
# Same numeric value as PASS_THRESHOLD currently, but kept as a SEPARATE
# constant rather than reusing PASS_THRESHOLD in both places — these
# represent two conceptually different thresholds (per-quiz pass/fail vs.
# multi-quiz at-risk trend) that happen to share a value today but have no
# reason to be forced to match if either changes independently later.


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post("", response_model=QuizStartResponse, status_code=201)
async def start_quiz(
    data: QuizStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_subscription),
):
    # VALIDATION NOT IN THE CONTRACT SHAPE: QuizStartRequest's
    # time_limit_secs is Optional regardless of `timed`, so Pydantic alone
    # won't catch timed=true with no time_limit_secs — that combination
    # would silently create an attempt with a timer the frontend has
    # nothing to count down from. Added this check rather than letting it
    # through, since it's a request the contract's own field description
    # explicitly calls invalid ("Required if timed=true") but doesn't
    # enforce structurally. If you'd rather this be permissive (e.g.
    # default to some fallback duration), flag it — current behavior is to
    # reject with 422.
    if data.timed and data.time_limit_secs is None:
        raise HTTPException(
            status_code=422,
            detail="time_limit_secs is required when timed=true.",
        )

    # ── Step 1: check for an existing in-progress attempt ──────────────────
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=IN_PROGRESS_WINDOW_MINUTES)

    existing = await db.scalar(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.status == AttemptStatus.in_progress,
            QuizAttempt.started_at >= window_start,
        )
        .order_by(QuizAttempt.started_at.desc())
    )

    if existing:
        # NOTE: matching the exact detail shape your prompt specified
        # ({detail: 'quiz_in_progress', attempt_id: existing.id}) rather
        # than FastAPI's default HTTPException(detail="string") pattern
        # used elsewhere (auth.py, categories.py, questions.py). Those
        # other routes use a plain string detail because their errors are
        # terminal — the frontend just displays the message. This one is
        # different: detail is structured because the frontend needs to
        # programmatically extract attempt_id to build a "Resume" button,
        # not just show text. Worth being consistent about which error
        # shape your frontend's error-extraction helper expects — the
        # extractErrorMessage() helper from your auth pages assumes
        # detail is either a string or a Pydantic 422 array; it does NOT
        # handle this dict shape. Frontend will need a specific check for
        # status===409 on this endpoint to pull attempt_id out, not the
        # generic error extractor.
        raise HTTPException(
            status_code=409,
            detail={"detail": "quiz_in_progress", "attempt_id": existing.id},
        )

    # An in_progress attempt older than the window exists but is now
    # effectively stale — not blocking a new quiz on it, but also not
    # auto-marking it abandoned here. That's GET /quizzes/{id}/resume's
    # job (Task 4.5) when/if anyone ever looks at that specific attempt
    # again. Leaving it untouched here keeps this endpoint's one job
    # ("can I start a new quiz") separate from attempt lifecycle cleanup.

    # ── Step 2: select random published question IDs ───────────────────────
    # CRITICAL per Slice 2's soft-delete requirement: is_deleted == False
    # applies here too, even though contract.py's own SECTION 8 docstring
    # doesn't mention it — quiz generation is a question-reading operation
    # like any other and must respect the same filter, or a soft-deleted
    # question could get selected into a brand-new quiz attempt.
    query = select(Question.id).where(
        Question.status == QStatus.published,
        Question.is_deleted == False,  # noqa: E712
    )
    if data.category_id is not None:
        query = query.where(Question.category_id == data.category_id)
    if data.difficulty is not None:
        query = query.where(Question.difficulty == data.difficulty)

    # ORDER BY RANDOM() LIMIT n — exactly as specified. Worth knowing for
    # later: this does a full sequential scan + sort on every call, which
    # is fine at your current scale (hundreds to low thousands of
    # questions) but becomes a real cost at 100k+ rows. Not optimizing
    # prematurely — flagging so it's not a mystery slowdown investigated
    # cold in six months. The standard fix at that scale is TABLESAMPLE or
    # a pre-shuffled id pool refreshed periodically, not something to
    # build now.
    query = query.order_by(func.random()).limit(data.question_count)

    result = await db.execute(query)
    question_ids = [row[0] for row in result.all()]

    # ── Step 3: handle fewer available questions than requested ────────────
    # Per instructions: "if fewer questions exist than requested, use what's
    # available" — not an error, just a smaller quiz. total_questions in
    # the response reflects the actual count, so the frontend's progress
    # indicator ("Question X of Y") is correct even when Y < requested.
    actual_count = len(question_ids)

    if actual_count == 0:
        # Not explicitly covered by the "use what's available" instruction,
        # but zero questions matching the filter is a distinct case worth
        # its own error rather than silently creating an attempt with an
        # empty question_ids array that the Active Quiz screen would have
        # nothing to render. 422 since this is a request-shape problem
        # (filters that don't match anything), not a server error.
        raise HTTPException(
            status_code=422,
            detail=(
                "No published questions match the selected category and "
                "difficulty. Try a broader filter."
            ),
        )

    # ── Step 4: create the attempt ──────────────────────────────────────────
    attempt = QuizAttempt(
        user_id=current_user.id,
        question_ids=question_ids,
        answers={},
        status=AttemptStatus.in_progress,
        timed=data.timed,
        time_limit_secs=data.time_limit_secs if data.timed else None,
        category_id=data.category_id,
        difficulty=data.difficulty,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # ── Step 5: respond ──────────────────────────────────────────────────────
    return QuizStartResponse(
        attempt_id=attempt.id,
        total_questions=actual_count,
        time_limit_secs=attempt.time_limit_secs,
        status=attempt.status,
    )


# ── Shared helper ────────────────────────────────────────────────────────────

async def _get_owned_in_progress_attempt(
    db: AsyncSession, attempt_id: int, user: User
) -> QuizAttempt:
    """
    Used by both new endpoints below — centralizes the "does this attempt
    exist, belong to this user, and is it still in_progress" check so the
    two routes don't each reimplement slightly-different versions of the
    same guard (which is exactly how ownership-check bugs creep in over
    time — one route gets updated, the other doesn't).

    Returns 404 for "doesn't exist OR doesn't belong to you" — same
    anti-enumeration posture as questions.py's get_question: a student
    probing attempt_id=17 that belongs to someone else gets the identical
    response as attempt_id=99999 that doesn't exist at all. Never a 403
    here, which would confirm the ID is real but off-limits.
    """
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")

    if attempt.status != AttemptStatus.in_progress:
        # Distinct from 404 — the attempt is real and belongs to you, it's
        # just not active anymore (completed, timed_out, or abandoned).
        # 409 Conflict is the right semantic: the request conflicts with
        # the resource's current state, not "request was malformed" (422)
        # or "you can't access this" (403/404).
        raise HTTPException(
            status_code=409,
            detail={"detail": "attempt_not_in_progress", "status": attempt.status.value},
        )

    return attempt


# ── Datetime helpers ─────────────────────────────────────────────────────────

def _as_utc(dt: datetime) -> datetime:
    """
    Normalize a datetime to UTC-aware regardless of whether the DB returned
    it with or without tzinfo. SQLAlchemy + asyncpg returns TIMESTAMP WITH
    TIME ZONE columns as UTC-aware, but TIMESTAMP WITHOUT TIME ZONE (the
    Postgres default, used when server_default=func.now() is specified
    without explicit timezone=True on the column) comes back as naive.
    Rather than requiring every caller to handle both cases, centralise
    the normalization here: treat any naive datetime as UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _time_remaining_secs(attempt: QuizAttempt) -> Optional[int]:
    """
    None for untimed attempts (matches the contract's Optional field —
    "None if untimed" per its own docstring). For timed attempts, computed
    fresh on every call from started_at + time_limit_secs rather than
    stored and decremented anywhere — there's no background job ticking
    this down. The frontend's countdown timer runs its own local JS clock
    seeded by this value once, per your Week 2 Task 5.3 plan; this
    function is the server-side source of truth used to REJECT late
    answers, not to drive the visual timer.
    """
    if not attempt.timed or attempt.time_limit_secs is None:
        return None

    elapsed = (datetime.now(timezone.utc) - _as_utc(attempt.started_at)).total_seconds()
    remaining = attempt.time_limit_secs - elapsed
    return max(0, int(remaining))


# ── GET /quizzes/{attempt_id}/question/{index} ──────────────────────────────

@router.get("/{attempt_id}/question/{index}", response_model=QuizQuestionResponse)
async def get_quiz_question(
    attempt_id: int,
    index: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await _get_owned_in_progress_attempt(db, attempt_id, current_user)

    total_questions = len(attempt.question_ids)
    if index < 0 or index >= total_questions:
        # Not in the contract's docstring explicitly, but an out-of-range
        # index (frontend bug, manually edited URL, or a stale total_questions
        # value from before a "fewer questions than requested" case at
        # start_quiz) needs SOME response. 404 fits — there is no question
        # at this position, same semantic as a missing resource.
        raise HTTPException(
            status_code=404,
            detail=f"No question at index {index}. This attempt has {total_questions} questions.",
        )

    question_id = attempt.question_ids[index]

    question = await db.get(Question, question_id)
    if not question or question.is_deleted:
        # This is the scenario soft-deletes exist to prevent from being
        # fatal: a question referenced by an in-progress attempt's
        # question_ids array got soft-deleted by an admin mid-quiz. Hard
        # delete would make this a true 404 with no recovery. Soft delete
        # means the row still physically exists — so in practice this
        # branch should rarely fire — but defending it anyway in case a
        # question was hard-deleted some other way (manual DB edit,
        # pre-soft-delete legacy data, etc.). 409 rather than 404: the
        # attempt itself is fine, this one position in it is the problem,
        # and "conflict with current state" fits better than "not found"
        # for a question the student already started seeing options for.
        raise HTTPException(
            status_code=409,
            detail="This question is no longer available. Please skip to the next question.",
        )

    category = await db.get(Category, question.category_id)
    category_name = category.name if category else "Unknown"
    # Falling back to "Unknown" rather than raising — a missing category on
    # an existing question is a data integrity issue worth investigating
    # separately, but shouldn't block a student mid-quiz from seeing their
    # question. Worth a TODO to alert/log this case once you have real
    # logging infrastructure (not in scope for Week 2).

    options = [QuestionOption(text=opt["text"]) for opt in question.options]

    bookmark = await db.scalar(
        select(Bookmark).where(
            Bookmark.user_id == current_user.id,
            Bookmark.question_id == question_id,
        )
    )

    # JSONB KEY TYPE GOTCHA — flagged in Week 2 tasks.md's Day 4 note and
    # worth restating here at the actual point it bites: JSON object keys
    # are always strings on the wire and in Postgres JSONB storage, even
    # though question_id is an int everywhere else in this codebase. When
    # this attempt's answers column has {"42": 1} stored, looking it up
    # with the int key 42 will silently miss. Casting to str explicitly at
    # every read/write site rather than relying on Python's dict behavior
    # to paper over it — asyncpg returns JSONB as a plain dict with string
    # keys, it will NOT auto-coerce "42" to match an int 42 lookup.
    already_answered = attempt.answers.get(str(question_id))

    return QuizQuestionResponse(
        attempt_id=attempt.id,
        question_index=index,
        total_questions=total_questions,
        question_id=question.id,
        stem=question.stem,
        options=options,
        category_name=category_name,
        difficulty=question.difficulty,
        is_bookmarked=bookmark is not None,
        time_remaining_secs=_time_remaining_secs(attempt),
        already_answered=already_answered,
    )


# ── POST /quizzes/{attempt_id}/answer ───────────────────────────────────────

@router.post("/{attempt_id}/answer", response_model=AnswerResponse)
async def save_answer(
    attempt_id: int,
    data: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await _get_owned_in_progress_attempt(db, attempt_id, current_user)

    if data.question_id not in attempt.question_ids:
        # Defends against a tampered or stale request — e.g. a question_id
        # from a DIFFERENT attempt's question set being submitted against
        # this attempt_id. Not explicitly asked for, but letting this
        # through would let a client silently inject an answer keyed to a
        # question_id this attempt never showed, which would then show up
        # oddly in scoring (Task 4.4's finish endpoint) as a phantom
        # answer with no matching question in this attempt's set.
        raise HTTPException(
            status_code=400,
            detail="This question is not part of the current quiz attempt.",
        )

    if attempt.timed:
        remaining = _time_remaining_secs(attempt)
        if remaining is not None and remaining <= 0:
            # Per instructions: 409 timed_out. Deliberately NOT flipping
            # attempt.status to timed_out here — that's a meaningful state
            # transition that belongs to the finish/resume logic (Tasks
            # 4.4/4.5), which decide what "timed out" actually means for
            # the attempt as a whole (auto-score what's there? mark
            # abandoned?). This endpoint's only job is to refuse the LATE
            # ANSWER, not to decide the attempt's fate.
            raise HTTPException(
                status_code=409,
                detail={"detail": "timed_out", "time_remaining_secs": 0},
            )

    # JSONB merge via the || operator, exactly as instructed. Building the
    # merge with SQLAlchemy's func + cast rather than read-modify-write in
    # Python, so this is a single atomic UPDATE — two rapid answer saves
    # for different questions on the same attempt (e.g. fast clicking
    # through, or a retry after a flaky network response) can't race and
    # clobber each other's write the way a SELECT-then-UPDATE-the-whole-
    # dict pattern could.
    new_answer = cast(
        literal({str(data.question_id): data.chosen_index}, type_=JSONB), JSONB
    )

    stmt = (
        update(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .values(answers=QuizAttempt.answers.op("||")(new_answer))
    )
    await db.execute(stmt)
    await db.commit()

    return AnswerResponse(saved=True)


# ── Shared helper for completed-attempt routes ──────────────────────────────

async def _get_owned_attempt(db: AsyncSession, attempt_id: int, user: User) -> QuizAttempt:
    """
    Looser than _get_owned_in_progress_attempt above — only checks
    existence + ownership, NOT status. Used by finish (which needs to
    validate in_progress itself, with a different error) and result (which
    needs to validate completed, also with its own error). Splitting these
    into two helpers rather than one parameterized "expected_status" helper
    because the two callers want genuinely different status-mismatch
    behavior: finish on an already-completed attempt is a 409 (you can't
    re-finish something), while result on a not-yet-completed attempt is a
    403 per your explicit instruction — different status codes for
    "wrong state" depending on which direction the mismatch goes, so a
    single shared status-check isn't actually shared logic.
    """
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")
    return attempt


async def _build_quiz_result(db: AsyncSession, attempt: QuizAttempt) -> QuizResultResponse:
    """
    Shared between finish and result — both routes return the exact same
    QuizResultResponse shape per your instructions ("return same
    QuizResultResponse shape"), so the construction logic lives in one
    place rather than being duplicated and risking the two responses
    drifting apart over time (e.g. someone fixes a bug in finish's version
    and forgets result's copy).
    """
    questions_out: list[QuestionResult] = []

    for question_id in attempt.question_ids:
        question = await db.get(Question, question_id)

        if not question:
            # Soft-deleted (or, in theory, hard-deleted via a path outside
            # this codebase) question referenced by a now-completed
            # attempt. Unlike the active-quiz GET endpoint, there's no
            # "skip to next question" option here — this is a historical
            # record the student is reviewing after the fact, and it needs
            # SOME entry for every question_id or the array length stops
            # matching total_questions / the student's memory of how many
            # questions they answered. Synthesizing a placeholder entry
            # rather than silently omitting it from the array.
            questions_out.append(
                QuestionResult(
                    question_id=question_id,
                    stem="This question is no longer available.",
                    options=[QuestionOption(text="—") for _ in range(4)],
                    correct_answer=0,
                    chosen_answer=None,
                    is_correct=False,
                    rationale="This question was removed after the quiz was completed.",
                    category_name="Unknown",
                    difficulty=Difficulty.medium,
                )
            )
            continue

        # question.category_id can be None here: soft-deleted questions
        # (unlike live ones) are allowed to outlive their category — see
        # delete_category() in routers/categories.py.
        category = (
            await db.get(Category, question.category_id)
            if question.category_id is not None
            else None
        )
        category_name = category.name if category else "Unknown"

        # Same string-key cast as the answer/question endpoints — see the
        # JSONB key-type note on get_quiz_question above. Repeating the
        # str() cast here rather than only relying on it being correct at
        # write-time, since a bug anywhere upstream that wrote an int key
        # instead of a string key would otherwise silently show every
        # question as unanswered here, which is a much worse failure mode
        # (wrong score shown to a student) than a missed read elsewhere.
        chosen = attempt.answers.get(str(question_id))

        options = [QuestionOption(text=opt["text"]) for opt in question.options]

        questions_out.append(
            QuestionResult(
                question_id=question.id,
                stem=question.stem,
                options=options,
                correct_answer=question.correct_answer,
                chosen_answer=chosen,
                is_correct=(chosen == question.correct_answer),
                rationale=question.rationale,
                category_name=category_name,
                difficulty=question.difficulty,
            )
        )

    total_questions = len(attempt.question_ids)
    time_taken_secs: Optional[int] = None
    if attempt.finished_at:
        time_taken_secs = int((_as_utc(attempt.finished_at) - _as_utc(attempt.started_at)).total_seconds())

    return QuizResultResponse(
        attempt_id=attempt.id,
        score=float(attempt.score) if attempt.score is not None else 0.0,
        correct_count=attempt.correct_count or 0,
        total_questions=total_questions,
        passed=(attempt.score or 0) >= PASS_THRESHOLD,
        time_taken_secs=time_taken_secs,
        status=attempt.status,
        questions=questions_out,
    )


async def _check_at_risk(db: AsyncSession, user_id: int) -> None:
    """
    Per instructions: "if last 3 completed attempts for this user all have
    score < 60, print a warning to console — real email alert comes in
    Slice 4." Deliberately a no-op beyond the print() — not writing
    anything to the DB, not calling send_email(). The Slice 4 version of
    this will need an actual notification record/dedup mechanism (so the
    same student doesn't trigger a fresh alert email on every single quiz
    once they're already flagged at-risk) — that's real design work
    intentionally deferred, not something to half-build here.
    """
    result = await db.execute(
        select(QuizAttempt.score)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == AttemptStatus.completed,
        )
        .order_by(QuizAttempt.finished_at.desc())
        .limit(3)
    )
    last_three_scores = [row[0] for row in result.all()]

    if len(last_three_scores) == 3 and all(s is not None and s < AT_RISK_THRESHOLD for s in last_three_scores):
        # console-only per instructions — Slice 4 will replace this with
        # a real alert pipeline (email + admin dashboard flag).
        print(
            f"[AT-RISK WARNING] user_id={user_id} has scored below "
            f"{AT_RISK_THRESHOLD}% on their last 3 completed quizzes: "
            f"{last_three_scores}"
        )


# ── POST /quizzes/{attempt_id}/finish ───────────────────────────────────────

@router.post("/{attempt_id}/finish", response_model=QuizResultResponse)
async def finish_quiz(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await _get_owned_attempt(db, attempt_id, current_user)

    if attempt.status != AttemptStatus.in_progress:
        # Re-finishing an already-completed (or timed_out/abandoned)
        # attempt is a state conflict, not a missing resource — 409,
        # matching the same status-mismatch convention used in the
        # answer/question endpoints above.
        raise HTTPException(
            status_code=409,
            detail={"detail": "attempt_not_in_progress", "status": attempt.status.value},
        )

    # ── Score server-side, never trust any client-supplied score ───────────
    correct_count = 0
    total_questions = len(attempt.question_ids)

    for question_id in attempt.question_ids:
        question = await db.get(Question, question_id)
        if not question:
            # A soft/hard-deleted question mid-attempt counts as wrong,
            # not skipped from the denominator — total_questions stays
            # fixed at quiz-generation time (this is the contract the
            # student saw "Question X of Y" against throughout the quiz),
            # so silently shrinking the denominator here would make the
            # score not match what the student experienced answering.
            continue
        chosen = attempt.answers.get(str(question_id))  # see JSONB key note
        if chosen is not None and chosen == question.correct_answer:
            correct_count += 1

    score = (correct_count / total_questions * 100.0) if total_questions > 0 else 0.0

    attempt.score = round(score, 2)
    attempt.correct_count = correct_count
    attempt.status = AttemptStatus.completed
    attempt.finished_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(attempt)

    # Fire-and-forget per instructions ("print a warning to console") —
    # not awaited as a background task here since FastAPI's BackgroundTasks
    # wasn't requested for this and a synchronous DB read + print() is
    # cheap enough not to meaningfully delay the response. Worth revisiting
    # alongside the email_utils.py BackgroundTasks note from Slice 2 if
    # this check grows heavier (e.g. once it's a real query across more
    # than 3 rows).
    await _check_at_risk(db, current_user.id)

    return await _build_quiz_result(db, attempt)


# ── GET /quizzes/{attempt_id}/result ────────────────────────────────────────

@router.get("/{attempt_id}/result", response_model=QuizResultResponse)
async def get_quiz_result(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = await _get_owned_attempt(db, attempt_id, current_user)

    if attempt.status != AttemptStatus.completed:
        # Per explicit instruction: 403, not 409. Worth noting the
        # asymmetry with finish's 409 above for the same kind of
        # status-mismatch — that's not an inconsistency I introduced, it's
        # what was specified: finish treats "wrong state" as a conflict,
        # result treats "wrong state" as forbidden access. Matching both
        # exactly as given rather than normalizing them to match each
        # other, since contract.py's own docstrings draw this same
        # distinction ("403 if attempt not completed" for result vs. no
        # equivalent stated 403 case for finish).
        raise HTTPException(
            status_code=403,
            detail="This quiz attempt has not been completed yet.",
        )

    return await _build_quiz_result(db, attempt)


# ── GET /quizzes/{attempt_id}/resume ────────────────────────────────────────

@router.get("/{attempt_id}/resume", response_model=QuizResumeResponse)
async def resume_quiz(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # NOTE ON YOUR INSTRUCTION WORDING: you wrote "if status=in_progress
    # and started_at > 30 min ago — return current state." That's the
    # inverted condition — an attempt started MORE than 30 minutes ago is
    # the STALE one (gets abandoned below), not the resumable one. The
    # resumable case is started_at being WITHIN the last 30 minutes. This
    # matches your own Week 2 tasks.md wording exactly ("if started_at is
    # older than 30 min set status=abandoned") and the
    # IN_PROGRESS_WINDOW_MINUTES logic already in start_quiz above.
    # Implementing the correct direction here, not the literal phrasing —
    # flagging explicitly rather than silently "fixing" it without you
    # knowing the instruction text had it backwards.

    attempt = await _get_owned_attempt(db, attempt_id, current_user)

    if attempt.status != AttemptStatus.in_progress:
        # Already completed, already abandoned, or already timed_out —
        # nothing to resume. 409 matches the same status-mismatch
        # convention as finish/answer above (state conflict, not missing
        # resource, not forbidden).
        raise HTTPException(
            status_code=409,
            detail={"detail": "attempt_not_in_progress", "status": attempt.status.value},
        )

    now = datetime.now(timezone.utc)
    age_minutes = (now - _as_utc(attempt.started_at)).total_seconds() / 60

    if age_minutes > IN_PROGRESS_WINDOW_MINUTES:
        # Stale — flip to abandoned and tell the caller why, per your
        # instruction's exact error shape.
        attempt.status = AttemptStatus.abandoned
        await db.commit()

        raise HTTPException(
            status_code=409,
            detail={"detail": "session_expired"},
        )

    # Still within the resumable window — return current progress.
    answered_count = len(attempt.answers)
    total_questions = len(attempt.question_ids)

    return QuizResumeResponse(
        attempt_id=attempt.id,
        status=attempt.status,
        answered_count=answered_count,
        total_questions=total_questions,
        time_remaining_secs=_time_remaining_secs(attempt),
    )


# ── GET /quizzes — list attempts ────────────────────────────────────────────

@router.get("", response_model=AttemptListResponse)
async def list_attempts(
    user_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ROLE GUARD: ?user_id= is admin-only per your instruction ("admins
    # can pass ?user_id= to see any student's attempts"). A student
    # passing ?user_id= for someone else's id should NOT see another
    # student's quiz history — not explicitly stated what should happen in
    # that case, so treating it the same as questions.py's anti-
    # enumeration posture: silently ignore the param rather than 403,
    # falling back to "show your own attempts" rather than confirming or
    # denying that the other user_id exists. A 403 here would leak that
    # the endpoint distinguishes "wrong role" from "wrong attempt" in a
    # way that isn't otherwise informative to an attacker, so the quieter
    # fallback seemed more consistent with the rest of this codebase's
    # error posture. Flag if you'd rather this 403 explicitly instead.
    target_user_id = current_user.id
    if user_id is not None and current_user.role.value == "admin":
        target_user_id = user_id

    query = select(QuizAttempt).where(QuizAttempt.user_id == target_user_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    page = max(1, page)
    per_page = max(1, min(per_page, 100))  # same ceiling rationale as
    # questions.py's list endpoint — no contract-specified max, capping to
    # prevent an unbounded pull.

    query = (
        query.order_by(QuizAttempt.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    attempts = result.scalars().all()

    items: list[AttemptSummaryOut] = []
    for attempt in attempts:
        category_name: Optional[str] = None
        if attempt.category_id is not None:
            category = await db.get(Category, attempt.category_id)
            category_name = category.name if category else None
            # None here (not "Unknown") is deliberate, unlike the
            # _build_quiz_result fallback above — AttemptSummaryOut's
            # category_name field is Optional in the contract specifically
            # to represent "this was an all-categories mixed quiz" (when
            # attempt.category_id is None) as well as "category got
            # deleted since" (when the lookup misses). Using "Unknown" here
            # would conflate those two genuinely different cases in a list
            # view where the distinction matters more than in a single
            # result detail view.

        time_taken_secs: Optional[int] = None
        if attempt.finished_at:
            time_taken_secs = int(
                (_as_utc(attempt.finished_at) - _as_utc(attempt.started_at)).total_seconds()
            )

        items.append(
            AttemptSummaryOut(
                attempt_id=attempt.id,
                score=float(attempt.score) if attempt.score is not None else None,
                correct_count=attempt.correct_count,
                total_questions=len(attempt.question_ids),
                status=attempt.status,
                time_taken_secs=time_taken_secs,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
                category_name=category_name,
            )
        )

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return AttemptListResponse(
        items=items,
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )

@router.get("/admin/{user_id}", response_model=AttemptListResponse)
async def admin_list_attempts(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: list any student's quiz attempt history by user_id path param.
    Distinct from GET /quizzes?user_id= — this is the contract-defined
    admin-specific route at /quizzes/admin/{user_id}."""
    from dependencies import require_admin as _require_admin

    query = select(QuizAttempt).where(QuizAttempt.user_id == user_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    query = (
        query.order_by(QuizAttempt.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    attempts = result.scalars().all()

    items = []
    for attempt in attempts:
        category_name = None
        if attempt.category_id is not None:
            category = await db.get(Category, attempt.category_id)
            category_name = category.name if category else None

        time_taken_secs = None
        if attempt.finished_at:
            time_taken_secs = int(
                (attempt.finished_at - attempt.started_at).total_seconds()
            )

        items.append(AttemptSummaryOut(
            attempt_id=attempt.id,
            score=float(attempt.score) if attempt.score is not None else None,
            correct_count=attempt.correct_count,
            total_questions=len(attempt.question_ids),
            status=attempt.status,
            time_taken_secs=time_taken_secs,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            category_name=category_name,
        ))

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return AttemptListResponse(
        items=items,
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )