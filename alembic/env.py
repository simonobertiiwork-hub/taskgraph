"""Alembic environment configuration for async PostgreSQL."""

import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# добавляем путь к проекту, чтобы импорты работали
# TODO: перейти на нормальную установку пакета
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.db.base import Base
from app.models.task import Task  # для автогенерации
from app.models.graph import GraphNode, GraphEdge  # для автогенерации

# конфиг из alembic.ini
config = context.config

# включаем логирование, чтобы видеть, что происходит
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# метаданные для автогенерации миграций
target_metadata = Base.metadata

# подставляем URL из .env, потому что в alembic.ini лежит заглушка
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    # выполняем миграцию в транзакции (откат при ошибке)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Подключение к БД и выполнение миграций."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # выполняем миграцию синхронно (Alembic не умеет в async)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection: Connection) -> None:
    """Запуск миграций с переданным соединением."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    # выполняем миграцию в транзакции (откат при ошибке)
    with context.begin_transaction():
        context.run_migrations()


# выбираем режим миграции
if context.is_offline_mode():
    run_migrations_offline()  # генерируем SQL
else:
    asyncio.run(run_migrations_online())  # подключаемся к БД
