"""Общие фикстуры для тестов."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from main import app


# создаём асинхронную тестовую БД (SQLite in-memory)
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# переопределяем зависимость get_db для тестов
async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Тестовый клиент FastAPI (с тестовой БД)."""
    import asyncio

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())

    yield TestClient(app)

    async def drop_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    loop.run_until_complete(drop_db())
    loop.close()


@pytest.fixture
def db_session():
    """Тестовая сессия БД (SQLite in-memory)."""
    import asyncio

    async def get_session():
        async with TestingSessionLocal() as session:
            return session

    loop = asyncio.new_event_loop()
    db = loop.run_until_complete(get_session())
    try:
        yield db
    finally:
        loop.run_until_complete(db.close())
        loop.close()