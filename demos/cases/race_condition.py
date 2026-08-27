"""Reproducible PostgreSQL lost-update and locking demonstration."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.models.task import Task
from demos.common.database import (
    read_postgres_metadata,
    require_demo_write_confirmation,
    safe_database_url,
)
from demos.common.reporting import (
    create_run_context,
    finalize_run,
    write_json,
    write_text,
)

CASE_NAME = "race_condition"
ORIGINAL_TITLE = "race demo original"
TASK_A_TITLE = "race demo task A"
TASK_B_TITLE = "race demo task B"


@dataclass(frozen=True, slots=True)
class RaceConditionConfig:
    """Runtime parameters for the race-condition demonstration."""

    hold_seconds: float = 1.0
    output_dir: Path = Path("demos/results")
    confirm_write: bool = False

    def validate(self) -> None:
        if not 0.1 <= self.hold_seconds <= 10:
            raise ValueError("hold-seconds must be between 0.1 and 10")


async def fetch_task(conn: AsyncConnection, task_id: int) -> dict[str, Any]:
    """Read the fields used by the concurrency scenarios."""
    result = await conn.execute(
        select(Task.title, Task.version).where(Task.id == task_id)
    )
    row = result.mappings().one()
    return dict(row)


async def read_backend_pid(conn: AsyncConnection) -> int:
    """Identify the PostgreSQL connection running one transaction."""
    result = await conn.execute(select(func.pg_backend_pid()))
    return int(result.scalar_one())


async def create_fixture(engine: AsyncEngine) -> int:
    """Create one task owned by this demonstration."""
    async with engine.begin() as conn:
        result = await conn.execute(
            insert(Task)
            .values(title=ORIGINAL_TITLE, status="new", version=1)
            .returning(Task.id)
        )
        return int(result.scalar_one())


async def reset_fixture(engine: AsyncEngine, task_id: int) -> None:
    """Restore the demonstration task before an isolated scenario."""
    async with engine.begin() as conn:
        result = await conn.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(title=ORIGINAL_TITLE, version=1)
        )
        if result.rowcount != 1:
            raise RuntimeError("Could not reset the race-condition fixture")


async def delete_fixture(engine: AsyncEngine, task_id: int) -> None:
    """Remove the task created by this demonstration."""
    async with engine.begin() as conn:
        await conn.execute(delete(Task).where(Task.id == task_id))


async def rollback_if_active(transaction: Any) -> None:
    """Roll back a transaction only when it has not already completed."""
    if transaction.is_active:
        await transaction.rollback()


async def run_last_write_wins(
    engine: AsyncEngine,
    task_id: int,
) -> dict[str, Any]:
    """Reproduce a deterministic stale overwrite with two transactions."""
    await reset_fixture(engine, task_id)

    async with engine.connect() as conn_a, engine.connect() as conn_b:
        tx_a = await conn_a.begin()
        tx_b = await conn_b.begin()
        try:
            backend_pid_a = await read_backend_pid(conn_a)
            backend_pid_b = await read_backend_pid(conn_b)
            read_a = await fetch_task(conn_a, task_id)
            read_b = await fetch_task(conn_b, task_id)

            await conn_a.execute(
                update(Task).where(Task.id == task_id).values(title=TASK_A_TITLE)
            )
            await tx_a.commit()

            await conn_b.execute(
                update(Task).where(Task.id == task_id).values(title=TASK_B_TITLE)
            )
            await tx_b.commit()
        except BaseException:
            await rollback_if_active(tx_a)
            await rollback_if_active(tx_b)
            raise

    async with engine.connect() as conn:
        final = await fetch_task(conn, task_id)

    return {
        "strategy": "last_write_wins",
        "transaction_a_backend_pid": backend_pid_a,
        "transaction_b_backend_pid": backend_pid_b,
        "transaction_a_read": read_a,
        "transaction_b_read": read_b,
        "transaction_a_write": TASK_A_TITLE,
        "transaction_b_write": TASK_B_TITLE,
        "final": final,
    }


async def run_pessimistic_lock(
    engine: AsyncEngine,
    task_id: int,
    *,
    hold_seconds: float,
) -> dict[str, Any]:
    """Show that SELECT FOR UPDATE makes the second writer wait and re-read."""
    await reset_fixture(engine, task_id)
    lock_acquired = asyncio.Event()
    second_attempt_started = asyncio.Event()

    async def transaction_a() -> dict[str, Any]:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                backend_pid = await read_backend_pid(conn)
                result = await conn.execute(
                    select(Task.title, Task.version)
                    .where(Task.id == task_id)
                    .with_for_update()
                )
                observed = dict(result.mappings().one())
                lock_acquired.set()
                await second_attempt_started.wait()
                await asyncio.sleep(hold_seconds)
                await conn.execute(
                    update(Task).where(Task.id == task_id).values(title=TASK_A_TITLE)
                )
                await tx.commit()
                return {
                    "backend_pid": backend_pid,
                    "observed": observed,
                    "write": TASK_A_TITLE,
                }
            except BaseException:
                lock_acquired.set()
                await rollback_if_active(tx)
                raise

    async def transaction_b() -> dict[str, Any]:
        await lock_acquired.wait()
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                backend_pid = await read_backend_pid(conn)
                started = time.perf_counter()
                second_attempt_started.set()
                result = await conn.execute(
                    select(Task.title, Task.version)
                    .where(Task.id == task_id)
                    .with_for_update()
                )
                waited_seconds = time.perf_counter() - started
                observed = dict(result.mappings().one())
                await conn.execute(
                    update(Task).where(Task.id == task_id).values(title=TASK_B_TITLE)
                )
                await tx.commit()
                return {
                    "backend_pid": backend_pid,
                    "observed_after_lock": observed,
                    "write": TASK_B_TITLE,
                    "lock_wait_seconds": waited_seconds,
                }
            except BaseException:
                second_attempt_started.set()
                await rollback_if_active(tx)
                raise

    result_a, result_b = await asyncio.gather(transaction_a(), transaction_b())

    async with engine.connect() as conn:
        final = await fetch_task(conn, task_id)

    return {
        "strategy": "pessimistic_lock",
        "configured_hold_seconds": hold_seconds,
        "transaction_a": result_a,
        "transaction_b": result_b,
        "final": final,
    }


async def run_optimistic_lock(
    engine: AsyncEngine,
    task_id: int,
) -> dict[str, Any]:
    """Show that a version predicate rejects the second stale writer."""
    await reset_fixture(engine, task_id)

    async with engine.connect() as conn_a, engine.connect() as conn_b:
        tx_a = await conn_a.begin()
        tx_b = await conn_b.begin()
        try:
            backend_pid_a = await read_backend_pid(conn_a)
            backend_pid_b = await read_backend_pid(conn_b)
            read_a = await fetch_task(conn_a, task_id)
            read_b = await fetch_task(conn_b, task_id)

            result_a = await conn_a.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.version == read_a["version"],
                )
                .values(
                    title=TASK_A_TITLE,
                    version=read_a["version"] + 1,
                )
            )
            await tx_a.commit()

            result_b = await conn_b.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.version == read_b["version"],
                )
                .values(
                    title=TASK_B_TITLE,
                    version=read_b["version"] + 1,
                )
            )
            await tx_b.commit()
        except BaseException:
            await rollback_if_active(tx_a)
            await rollback_if_active(tx_b)
            raise

    async with engine.connect() as conn:
        final = await fetch_task(conn, task_id)

    return {
        "strategy": "optimistic_lock",
        "transaction_a_backend_pid": backend_pid_a,
        "transaction_b_backend_pid": backend_pid_b,
        "transaction_a_read": read_a,
        "transaction_b_read": read_b,
        "transaction_a_rows_updated": int(result_a.rowcount),
        "transaction_b_rows_updated": int(result_b.rowcount),
        "transaction_b_conflict_detected": result_b.rowcount == 0,
        "final": final,
    }


def build_race_summary(
    last_write_wins: dict[str, Any],
    pessimistic_lock: dict[str, Any],
    optimistic_lock: dict[str, Any],
) -> dict[str, Any]:
    """Verify the expected outcome of all three concurrency strategies."""
    lww_verification = {
        "transactions_used_distinct_connections": (
            last_write_wins["transaction_a_backend_pid"]
            != last_write_wins["transaction_b_backend_pid"]
        ),
        "both_transactions_read_original": (
            last_write_wins["transaction_a_read"]["title"] == ORIGINAL_TITLE
            and last_write_wins["transaction_b_read"]["title"] == ORIGINAL_TITLE
        ),
        "first_write_was_lost": (last_write_wins["final"]["title"] == TASK_B_TITLE),
    }
    pessimistic_verification = {
        "transactions_used_distinct_connections": (
            pessimistic_lock["transaction_a"]["backend_pid"]
            != pessimistic_lock["transaction_b"]["backend_pid"]
        ),
        "second_writer_observed_first_commit": (
            pessimistic_lock["transaction_b"]["observed_after_lock"]["title"]
            == TASK_A_TITLE
        ),
        "second_writer_waited_for_lock": (
            pessimistic_lock["transaction_b"]["lock_wait_seconds"]
            >= pessimistic_lock["configured_hold_seconds"] * 0.5
        ),
        "writes_completed_in_lock_order": (
            pessimistic_lock["final"]["title"] == TASK_B_TITLE
        ),
    }
    optimistic_verification = {
        "transactions_used_distinct_connections": (
            optimistic_lock["transaction_a_backend_pid"]
            != optimistic_lock["transaction_b_backend_pid"]
        ),
        "first_writer_updated_one_row": (
            optimistic_lock["transaction_a_rows_updated"] == 1
        ),
        "stale_second_writer_updated_no_rows": (
            optimistic_lock["transaction_b_rows_updated"] == 0
        ),
        "conflict_was_detected": (
            optimistic_lock["transaction_b_conflict_detected"] is True
        ),
        "first_write_and_incremented_version_remain": (
            optimistic_lock["final"]["title"] == TASK_A_TITLE
            and optimistic_lock["final"]["version"] == 2
        ),
    }

    verification = {
        "last_write_wins": lww_verification,
        "pessimistic_lock": pessimistic_verification,
        "optimistic_lock": optimistic_verification,
    }
    passed = all(
        value for scenario in verification.values() for value in scenario.values()
    )

    return {
        "status": "passed" if passed else "failed",
        "scenarios": {
            "last_write_wins": last_write_wins,
            "pessimistic_lock": pessimistic_lock,
            "optimistic_lock": optimistic_lock,
        },
        "verification": verification,
    }


def render_race_report(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render a human-readable report from measured scenario results."""
    lww = summary["scenarios"]["last_write_wins"]
    pessimistic = summary["scenarios"]["pessimistic_lock"]
    optimistic = summary["scenarios"]["optimistic_lock"]
    verification_rows = "\n".join(
        f"| {scenario} / `{name}` | {'PASS' if value else 'FAIL'} |"
        for scenario, checks in summary["verification"].items()
        for name, value in checks.items()
    )

    return f"""# Case #2: PostgreSQL Race Condition

Generated at: `{metadata["generated_at_utc"]}`
Run ID: `{metadata["run_id"]}`

## Environment

- Database: `{metadata["postgres"]["database_name"]}`
- PostgreSQL: `{metadata["postgres"]["server_version"]}`
- Fixture task id: `{metadata["fixture_task_id"]}`
- Configured lock hold: `{metadata["hold_seconds"]:.3f} s`
- Transaction isolation: `{metadata["postgres"]["transaction_isolation"]}`

## Results

| Strategy | Second transaction observed | Final state | Evidence |
| --- | --- | --- | --- |
| Last write wins | `{lww["transaction_b_read"]["title"]}`, version {lww["transaction_b_read"]["version"]} | `{lww["final"]["title"]}`, version {lww["final"]["version"]} | stale write overwrote task A |
| `SELECT FOR UPDATE` | `{pessimistic["transaction_b"]["observed_after_lock"]["title"]}` | `{pessimistic["final"]["title"]}`, version {pessimistic["final"]["version"]} | waited {pessimistic["transaction_b"]["lock_wait_seconds"]:.6f} s and re-read committed state |
| Version predicate | version {optimistic["transaction_b_read"]["version"]} | `{optimistic["final"]["title"]}`, version {optimistic["final"]["version"]} | stale update affected {optimistic["transaction_b_rows_updated"]} rows |

## Verification

| Check | Result |
| --- | --- |
{verification_rows}

Overall status: **{summary["status"].upper()}**

Machine-readable scenario details and verification checks are stored in
`summary.json`. The fixture is deleted after the run.
"""


async def run_race_condition(
    engine: AsyncEngine,
    config: RaceConditionConfig,
) -> dict[str, Any]:
    """Run all concurrency strategies and persist their evidence."""
    config.validate()
    require_demo_write_confirmation(engine, confirmed=config.confirm_write)

    run_context = create_run_context(config.output_dir, CASE_NAME)
    result_dir = run_context.result_dir
    task_id: int | None = None

    print("TaskGraph demo: PostgreSQL race condition and locking")
    print(f"Database: {safe_database_url(engine)}")
    print(f"Result directory: {result_dir}")

    try:
        async with engine.connect() as conn:
            postgres_metadata = await read_postgres_metadata(conn)

        task_id = await create_fixture(engine)
        print(f"Created temporary task fixture: id={task_id}")

        print("1/3 Reproducing last-write-wins data loss...")
        last_write_wins = await run_last_write_wins(engine, task_id)

        print("2/3 Serializing writers with SELECT FOR UPDATE...")
        pessimistic_lock = await run_pessimistic_lock(
            engine,
            task_id,
            hold_seconds=config.hold_seconds,
        )

        print("3/3 Rejecting a stale writer with a version predicate...")
        optimistic_lock = await run_optimistic_lock(engine, task_id)
        summary = build_race_summary(
            last_write_wins,
            pessimistic_lock,
            optimistic_lock,
        )

        metadata = {
            "schema_version": 1,
            "run_id": str(run_context.run_id),
            "case": CASE_NAME,
            "generated_at_utc": run_context.started_at_utc.isoformat(),
            "database_url": safe_database_url(engine),
            "postgres": postgres_metadata,
            "fixture_task_id": task_id,
            "hold_seconds": config.hold_seconds,
        }
        write_json(result_dir / "metadata.json", metadata)
        write_json(result_dir / "summary.json", summary)
        report_path = result_dir / "report.md"
        write_text(report_path, render_race_report(metadata, summary))
        manifest_path = finalize_run(
            run_context,
            status=summary["status"],
            artifact_names=("metadata.json", "summary.json", "report.md"),
        )

        wait_seconds = pessimistic_lock["transaction_b"]["lock_wait_seconds"]
        conflict = optimistic_lock["transaction_b_conflict_detected"]
        print(f"Pessimistic lock wait: {wait_seconds:.6f} s")
        print(f"Optimistic conflict detected: {conflict}")

        return {
            "status": summary["status"],
            "run_id": run_context.run_id,
            "result_dir": result_dir,
            "manifest_path": manifest_path,
            "report_path": report_path,
            "summary": summary,
        }
    finally:
        if task_id is not None:
            await delete_fixture(engine, task_id)
            print(f"Deleted temporary task fixture: id={task_id}")
