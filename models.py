from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as PgEnum, Text, JSON, ForeignKey
from sqlalchemy import JSON
# from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base
import enum

class UserRole(str, enum.Enum):
    student  = "student"
    admin    = "admin"
    reviewer = "reviewer"

class LoginStatus(str, enum.Enum):
    success         = "success"
    failed_password = "failed_password"
    failed_2fa      = "failed_2fa"
    blocked_ip      = "blocked_ip"
    blocked_geo     = "blocked_geo"
    account_locked  = "account_locked"

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    name            = Column(String(120), nullable=False)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    password_hash   = Column(String(255), nullable=False)
    role            = Column(PgEnum(UserRole), default=UserRole.student, nullable=False)
    is_verified     = Column(Boolean, default=False, nullable=False)
    is_active       = Column(Boolean, default=True, nullable=False)
    dark_mode       = Column(Boolean, default=False, nullable=False)
    two_fa_enabled  = Column(Boolean, default=True, nullable=False)
    verify_token    = Column(String(128), nullable=True)
    verify_expires  = Column(DateTime(timezone=True), nullable=True)
    reset_token     = Column(String(128), nullable=True)
    reset_expires   = Column(DateTime(timezone=True), nullable=True)
    otp_hash        = Column(String(255), nullable=True)
    otp_expires     = Column(DateTime(timezone=True), nullable=True)
    otp_attempts    = Column(Integer, default=0, nullable=False)
    failed_logins   = Column(Integer, default=0, nullable=False)
    locked_until    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=False)
    ip_address    = Column(String(45), nullable=True)
    user_agent    = Column(String(500), nullable=True)
    last_used_at  = Column(DateTime(timezone=True), server_default=func.now())
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

class LoginLog(Base):
    __tablename__ = "login_logs"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, nullable=True)
    ip_address    = Column(String(45), nullable=True)
    country_code  = Column(String(2), nullable=True)
    user_agent    = Column(String(500), nullable=True)
    status        = Column(PgEnum(LoginStatus), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    sort_order  = Column(Integer, default=0, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class QStatus(str, enum.Enum):
    draft      = "draft"
    in_review  = "in_review"
    published  = "published"
    archived   = "archived"

class Difficulty(str, enum.Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"

class Question(Base):
    __tablename__ = "questions"
    id             = Column(Integer, primary_key=True)
    stem           = Column(Text, nullable=False)
    # options stored as JSONB array: [{text: "..."}, {text: "..."}, ...]
    # Always 4 items, index 0-3 = A-D. Matches contract's list[QuestionOption].
    options        = Column(JSON, nullable=False)
    correct_answer = Column(Integer, nullable=False)  # 0–3
    rationale      = Column(Text, nullable=False)
    category_id    = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    nclex_domain   = Column(String(120), nullable=False)
    difficulty     = Column(PgEnum(Difficulty), nullable=False)
    status         = Column(PgEnum(QStatus), default=QStatus.draft, nullable=False, index=True)
    # Soft delete — see note above Task 2.1. Every GET /questions and
    # GET /questions/{id} query must add .where(Question.is_deleted == False).
    # "Deleting" a question from the admin UI later (Slice 6) sets this
    # True instead of issuing a DELETE — keeps quiz_attempts.question_ids
    # resolvable forever, even for questions an admin has since removed
    # from circulation.
    is_deleted     = Column(Boolean, default=False, nullable=False, index=True)
    reviewed_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at    = Column(DateTime(timezone=True), nullable=True)
    created_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    # Unique constraint: one bookmark per (user, question)
    # ON CONFLICT DO NOTHING in the endpoint uses this constraint.
    __table_args__ = (
        __import__('sqlalchemy').UniqueConstraint('user_id', 'question_id', name='uq_bookmark'),
    )

class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed   = "completed"
    timed_out   = "timed_out"
    abandoned   = "abandoned"

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # question_ids: ordered list of question IDs for this attempt
    # e.g. [42, 7, 99, 3, ...] — order is fixed at generation time
    question_ids     = Column(JSON, nullable=False)
    # answers: dict of {question_id: chosen_index}
    # e.g. {"42": 1, "7": 3} — updated on every auto-save
    answers          = Column(JSON, nullable=False, default=dict)
    status           = Column(PgEnum(AttemptStatus), default=AttemptStatus.in_progress, nullable=False)
    score            = Column(Integer, nullable=True)       # 0–100, set on finish
    correct_count    = Column(Integer, nullable=True)       # set on finish
    timed            = Column(Boolean, default=False, nullable=False)
    time_limit_secs  = Column(Integer, nullable=True)       # None if untimed
    category_id      = Column(Integer, ForeignKey("categories.id"), nullable=True)  # None = all
    difficulty       = Column(PgEnum(Difficulty), nullable=True)                    # None = mixed
    started_at       = Column(DateTime(timezone=True), server_default=func.now())
    finished_at      = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())