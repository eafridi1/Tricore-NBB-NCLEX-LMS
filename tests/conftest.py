# backend/tests/conftest.py
"""
Shared fixtures for the TriCore test suite.

Stack:
  pytest + pytest-asyncio   — async test runner
  httpx.AsyncClient         — ASGI test client (no real HTTP, hits FastAPI directly)
  SQLAlchemy async + aiosqlite — in-memory SQLite database per test session
                                 (fast, isolated, no external dependency)

Install test deps:
  pip install pytest pytest-asyncio httpx aiosqlite

Run all tests:
  cd backend
  pytest tests/ -v

Run one file:
  pytest tests/test_auth.py -v

Run one test:
  pytest tests/test_auth.py::test_register_success -v
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from models import User, UserRole
from auth_utils import hash_password

# ── In-memory SQLite database ─────────────────────────────────────────────
# One engine per test SESSION (not per test) — fast, and SQLite's :memory:
# with StaticPool keeps a single connection so all async operations see
# the same data without connection-per-coroutine isolation problems.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test database session. Wraps each test in a transaction that is
    rolled back after the test finishes — tests never see each other's
    data, no cleanup code needed.
    """
    async with engine.begin() as conn:
        async with TestSessionLocal(bind=conn) as session:
            yield session
            await session.flush()
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    ASGI test client that uses the test DB session — overrides the
    get_db dependency so every request in a test sees the same
    rolled-back transaction.
    """
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── Convenience fixtures ──────────────────────────────────────────────────

@pytest_asyncio.fixture
async def student_user(db: AsyncSession) -> User:
    """A verified, active student user."""
    user = User(
        name="Test Student",
        email="student@test.com",
        password_hash=hash_password("Student123"),
        role=UserRole.student,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    """A verified, active admin user."""
    user = User(
        name="Test Admin",
        email="admin@test.com",
        password_hash=hash_password("Admin123"),
        role=UserRole.admin,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def student_token(client: AsyncClient, student_user: User, db: AsyncSession) -> str:
    """
    Full login flow for a student — returns a valid access token.
    Reads the OTP from the user row directly (since email_utils.py is
    console-only in test mode, the real OTP was never sent anywhere) and
    patches the OTP hash check. Simpler alternative used here: create the
    token directly via auth_utils, bypassing the full login flow.
    This is appropriate for integration tests that are testing OTHER
    endpoints (not auth itself) and just need a valid token to get past
    the auth guard. Tests in test_auth.py go through the real login flow.
    """
    from auth_utils import create_access_token
    return create_access_token(student_user.id, student_user.role.value)


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    from auth_utils import create_access_token
    return create_access_token(admin_user.id, admin_user.role.value)


def auth_headers(token: str) -> dict:
    """Helper — returns Authorization header dict for use in client calls."""
    return {"Authorization": f"Bearer {token}"}