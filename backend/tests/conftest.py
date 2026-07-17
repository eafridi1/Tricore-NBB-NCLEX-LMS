"""
Shared fixtures for the TriCore test suite.
Compatible with: Python 3.14, pytest-asyncio 1.x, asyncpg, SQLAlchemy 2.x
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import patch

load_dotenv()

_dev_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/tricore",
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    _dev_url.replace("/tricore", "/tricore_test")
             .replace("/tricore_lms", "/tricore_test"),
)

_TRUNCATE_SQL = (
    "TRUNCATE TABLE login_logs, sessions, bookmarks, "
    "quiz_attempts, questions, categories, users "
    "RESTART IDENTITY CASCADE"
)


# ── One-time table setup (sync, no loop sharing) ──────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_tables():
    from database import Base

    async def _run():
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(_run())
    yield


# ── Per-test engine ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Fresh engine + session per test. Truncates all tables on teardown."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_size=1, max_overflow=0)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        # Always close the session first, then truncate on a fresh connection
        await session.close()
        async with engine.begin() as conn:
            await conn.execute(text(_TRUNCATE_SQL))
        await engine.dispose()


# ── Simple client fixture — no DB needed ──────────────────────────────────────

@pytest_asyncio.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """
    A test client with NO database wiring. Use this for tests that only
    need to hit endpoints that fail at validation (422s) before touching
    the DB — it's faster and won't hang on connection setup/teardown.
    """
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Full test client wired to the per-test DB session."""
    from database import get_db
    from main import app

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def student_user(db: AsyncSession):
    from models import User, UserRole
    from auth_utils import hash_password

    user = User(
        name="Test Student",
        email="student@test.com",
        password_hash=hash_password("Student123!"),
        role=UserRole.student,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession):
    from models import User, UserRole
    from auth_utils import hash_password

    user = User(
        name="Test Admin",
        email="admin@test.com",
        password_hash=hash_password("Admin123!"),
        role=UserRole.admin,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def student_token(student_user) -> str:
    from auth_utils import create_access_token
    return create_access_token(student_user.id, student_user.role.value)


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    from auth_utils import create_access_token
    return create_access_token(admin_user.id, admin_user.role.value)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

# Patch send_email for the entire test session
# This ensures no real emails are ever sent during pytest
# regardless of whether RESEND_API_KEY is set in .env
@pytest.fixture(autouse=True, scope='session')
def mock_email():
    with patch('email_utils.send_email') as mock:
        yield mock