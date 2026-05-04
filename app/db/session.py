from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)

from app.core.config import settings

# создаём асинхронный движок с ограничением пула соединений
engine = create_async_engine(
    settings.database_url,
    echo=True,          # SQL-логи (полезно для отладки)
    pool_size=5,        # сколько соединений держать открытыми
    max_overflow=0,     # сколько дополнительных можно открыть при пике
)

# фабрика сессий (1 сессия = 1 транзакция, объекты живут после коммита)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Создать асинхронную сессию БД для запроса (FastAPI сам закроет)."""
    async with AsyncSessionLocal() as session:
        yield session  # передаём сессию