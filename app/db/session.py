from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)

from app.core.config import settings

# создаём асинхронный движок с ограничением пула соединений
engine = create_async_engine(
    settings.database_url,
    echo=False,                             # SQL-логи (включать только для отладки)
    pool_size=settings.pool_size,           # сколько соединений держать открытыми
    max_overflow=settings.max_overflow,     # сколько дополнительных можно открыть при пике
)

# фабрика сессий (1 сессия = 1 транзакция, объекты живут после коммита)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Создать асинхронную сессию БД для запроса (FastAPI сам закроет)."""
    async with AsyncSessionLocal() as session:
        yield session  # передаём сессию