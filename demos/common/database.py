"""Database safety and metadata helpers for destructive demo scenarios."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


PROTECTED_DATABASE_NAMES = {
    "postgres",
    "template0",
    "template1",
}


class DemoSafetyError(RuntimeError):
    """Raised when a destructive demo is not safe to run."""


def safe_database_url(engine: AsyncEngine) -> str:
    """Return the database URL without exposing its password."""
    return engine.url.render_as_string(
        hide_password=True,
    )


def require_demo_reset_confirmation(
    engine: AsyncEngine,
    *,
    confirmed: bool,
) -> None:
    """Protect the database against accidental table truncation."""

    if engine.dialect.name != "postgresql":
        raise DemoSafetyError(
            "This demonstration requires PostgreSQL; "
            f"configured dialect is {engine.dialect.name!r}."
        )

    database_name = engine.url.database

    if not database_name:
        raise DemoSafetyError(
            "DATABASE_URL does not contain a database name."
        )

    if database_name.lower() in PROTECTED_DATABASE_NAMES:
        raise DemoSafetyError(
            f"Refusing to truncate protected database {database_name!r}."
        )

    if not confirmed:
        raise DemoSafetyError(
            "The index-scan demo truncates the tasks table. "
            "Re-run it with --confirm-reset after checking DATABASE_URL."
        )


async def read_postgres_metadata(
    connection: AsyncConnection,
) -> dict[str, Any]:
    """Read information about the active PostgreSQL database."""

    result = await connection.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS database_user,
                current_setting('server_version') AS server_version
            """
        )
    )

    row = result.mappings().one()

    return dict(row)