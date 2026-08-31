"""Database safety and metadata helpers for destructive demo scenarios."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

PROTECTED_DATABASE_NAMES = {"postgres", "template0", "template1"}


class DemoSafetyError(RuntimeError):
    """Raised when a destructive demo is not safe to run."""


def safe_database_url(engine: AsyncEngine) -> str:
    """Return the configured URL without exposing the database password."""
    return engine.url.render_as_string(hide_password=True)


def require_demo_reset_confirmation(
    engine: AsyncEngine,
    *,
    confirmed: bool,
) -> None:
    """Protect the index demo against accidental table truncation."""
    require_demo_confirmation(
        engine,
        confirmed=confirmed,
        operation="The index-scan demo truncates the tasks table",
        confirmation_flag="--confirm-reset",
    )


def require_demo_write_confirmation(
    engine: AsyncEngine,
    *,
    confirmed: bool,
) -> None:
    """Protect the race demo against unconfirmed fixture writes."""
    require_demo_confirmation(
        engine,
        confirmed=confirmed,
        operation=(
            "The race-condition demo creates, updates, and deletes one task fixture"
        ),
        confirmation_flag="--confirm-write",
    )


def require_demo_load_confirmation(
    engine: AsyncEngine,
    *,
    confirmed: bool,
) -> None:
    """Protect the pool demo against unconfirmed concurrent DB load."""
    require_demo_confirmation(
        engine,
        confirmed=confirmed,
        operation="The connection-pool demo opens concurrent PostgreSQL connections",
        confirmation_flag="--confirm-load",
    )


def require_demo_confirmation(
    engine: AsyncEngine,
    *,
    confirmed: bool,
    operation: str,
    confirmation_flag: str,
) -> None:
    """Validate the target database and require an explicit confirmation."""
    if engine.dialect.name != "postgresql":
        raise DemoSafetyError(
            "This demonstration requires PostgreSQL; "
            f"configured dialect is {engine.dialect.name!r}."
        )

    database_name = engine.url.database
    if not database_name:
        raise DemoSafetyError("DATABASE_URL does not contain a database name.")

    if database_name.lower() in PROTECTED_DATABASE_NAMES:
        raise DemoSafetyError(
            f"Refusing to run a write demo against protected database "
            f"{database_name!r}."
        )

    if not confirmed:
        raise DemoSafetyError(
            f"{operation}. Re-run it with {confirmation_flag} "
            "after checking DATABASE_URL."
        )


async def read_postgres_metadata(conn: AsyncConnection) -> dict[str, Any]:
    """Read reproducibility metadata from the active PostgreSQL connection."""
    result = await conn.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS database_user,
                current_setting('server_version') AS server_version,
                current_setting('transaction_isolation') AS transaction_isolation
            """
        )
    )
    row = result.mappings().one()
    return dict(row)
