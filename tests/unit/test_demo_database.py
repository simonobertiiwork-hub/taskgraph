import pytest
from sqlalchemy.engine import make_url

from demos.common.database import (
    DemoSafetyError,
    require_demo_reset_confirmation,
    safe_database_url,
)


class FakeDialect:
    def __init__(self, name: str):
        self.name = name


class FakeEngine:
    def __init__(
        self,
        url: str,
        dialect: str = "postgresql",
    ):
        self.url = make_url(url)
        self.dialect = FakeDialect(dialect)


def test_safe_database_url_hides_password():
    engine = FakeEngine(
        "postgresql+asyncpg://user:secret@db:5432/taskgraph"
    )

    rendered_url = safe_database_url(engine)

    assert "secret" not in rendered_url
    assert "***" in rendered_url


def test_reset_requires_explicit_confirmation():
    engine = FakeEngine(
        "postgresql+asyncpg://user:secret@db:5432/taskgraph"
    )

    with pytest.raises(
        DemoSafetyError,
        match="--confirm-reset",
    ):
        require_demo_reset_confirmation(
            engine,
            confirmed=False,
        )


def test_reset_refuses_protected_database():
    engine = FakeEngine(
        "postgresql+asyncpg://user:secret@db:5432/postgres"
    )

    with pytest.raises(
        DemoSafetyError,
        match="protected database",
    ):
        require_demo_reset_confirmation(
            engine,
            confirmed=True,
        )


def test_reset_refuses_non_postgresql_database():
    engine = FakeEngine(
        "sqlite+aiosqlite:///:memory:",
        dialect="sqlite",
    )

    with pytest.raises(
        DemoSafetyError,
        match="requires PostgreSQL",
    ):
        require_demo_reset_confirmation(
            engine,
            confirmed=True,
        )


def test_reset_allows_confirmed_taskgraph_database():
    engine = FakeEngine(
        "postgresql+asyncpg://user:secret@db:5432/taskgraph"
    )

    require_demo_reset_confirmation(
        engine,
        confirmed=True,
    )