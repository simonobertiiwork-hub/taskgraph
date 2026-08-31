"""Fast reproducible SQLAlchemy connection-pool exhaustion demonstration."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from demos.common.database import (
    read_postgres_metadata,
    require_demo_load_confirmation,
    safe_database_url,
)
from demos.common.reporting import create_run_context, finalize_run, write_json, write_text

CASE_NAME = "connection_pool_exhaustion"


@dataclass(frozen=True, slots=True)
class PoolExhaustionConfig:
    concurrency: int = 5
    hold_seconds: float = 0.35
    pool_timeout_seconds: float = 0.20
    before_pool_size: int = 2
    after_pool_size: int = 5
    output_dir: Path = Path("demos/results")
    confirm_load: bool = False

    def validate(self) -> None:
        if not 3 <= self.concurrency <= 20:
            raise ValueError("concurrency must be between 3 and 20")
        if not 0.1 <= self.hold_seconds <= 2:
            raise ValueError("hold-seconds must be between 0.1 and 2")
        if not 0.05 <= self.pool_timeout_seconds < self.hold_seconds:
            raise ValueError("pool-timeout must be positive and lower than hold-seconds")
        if not 1 <= self.before_pool_size < self.after_pool_size <= self.concurrency:
            raise ValueError("pool sizes must satisfy 1 <= before < after <= concurrency")


async def _one_request(engine: AsyncEngine, request_id: int, hold_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        async with engine.connect() as connection:
            acquired_ms = (time.perf_counter() - started) * 1_000
            await connection.execute(text("SELECT pg_sleep(:hold)"), {"hold": hold_seconds})
        return {
            "request_id": request_id,
            "status": "completed",
            "connection_acquired_ms": round(acquired_ms, 3),
            "elapsed_ms": round((time.perf_counter() - started) * 1_000, 3),
            "error_type": None,
        }
    except SQLAlchemyTimeoutError:
        return {
            "request_id": request_id,
            "status": "pool_timeout",
            "connection_acquired_ms": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1_000, 3),
            "error_type": "sqlalchemy.exc.TimeoutError",
        }


async def measure_pool(
    database_url: str,
    *,
    pool_size: int,
    concurrency: int,
    hold_seconds: float,
    pool_timeout_seconds: float,
) -> dict[str, Any]:
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout=pool_timeout_seconds,
    )
    try:
        started = time.perf_counter()
        requests = await asyncio.gather(
            *(
                _one_request(engine, request_id, hold_seconds)
                for request_id in range(1, concurrency + 1)
            )
        )
        elapsed_ms = (time.perf_counter() - started) * 1_000
    finally:
        await engine.dispose()
    completed = sum(item["status"] == "completed" for item in requests)
    timeouts = sum(item["status"] == "pool_timeout" for item in requests)
    return {
        "pool_size": pool_size,
        "max_overflow": 0,
        "pool_timeout_seconds": pool_timeout_seconds,
        "concurrency": concurrency,
        "hold_seconds": hold_seconds,
        "completed_requests": completed,
        "pool_timeouts": timeouts,
        "failure_rate_percent": round(timeouts / concurrency * 100, 3),
        "elapsed_ms": round(elapsed_ms, 3),
        "requests": requests,
    }


def build_pool_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    verification = {
        "before_pool_saturated": before["pool_timeouts"] > 0,
        "before_capacity_was_lower_than_concurrency": before["pool_size"] < before["concurrency"],
        "after_used_identical_load": all(before[key] == after[key] for key in ("concurrency", "hold_seconds", "pool_timeout_seconds")),
        "after_pool_matches_concurrency": after["pool_size"] >= after["concurrency"],
        "after_has_no_pool_timeouts": after["pool_timeouts"] == 0,
        "completed_requests_increased": after["completed_requests"] > before["completed_requests"],
    }
    return {
        "status": "passed" if all(verification.values()) else "failed",
        "before": {key: value for key, value in before.items() if key != "requests"},
        "after": {key: value for key, value in after.items() if key != "requests"},
        "comparison": {
            "timeouts_removed": before["pool_timeouts"] - after["pool_timeouts"],
            "completed_requests_added": after["completed_requests"] - before["completed_requests"],
            "failure_rate_reduction_percentage_points": round(before["failure_rate_percent"] - after["failure_rate_percent"], 3),
        },
        "verification": verification,
    }


def render_pool_report(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    before, after = summary["before"], summary["after"]
    checks = "\n".join(
        f"| `{name}` | {'PASS' if value else 'FAIL'} |"
        for name, value in summary["verification"].items()
    )
    return f"""# Case #3: SQLAlchemy Connection Pool Exhaustion

Run ID: `{metadata['run_id']}`
Database: `{metadata['database_url']}`

## Identical load

- Concurrent requests: `{before['concurrency']}`
- Each connection held for: `{before['hold_seconds']}` s
- Pool timeout: `{before['pool_timeout_seconds']}` s
- `max_overflow`: `0`

## Result

| Phase | pool_size | Completed | Pool timeouts | Failure rate |
| --- | ---: | ---: | ---: | ---: |
| Before | {before['pool_size']} | {before['completed_requests']} | {before['pool_timeouts']} | {before['failure_rate_percent']}% |
| After | {after['pool_size']} | {after['completed_requests']} | {after['pool_timeouts']} | {after['failure_rate_percent']}% |

## Verification

| Check | Result |
| --- | --- |
{checks}

Overall status: **{summary['status'].upper()}**
"""


async def run_pool_exhaustion(engine: AsyncEngine, config: PoolExhaustionConfig) -> dict[str, Any]:
    config.validate()
    require_demo_load_confirmation(engine, confirmed=config.confirm_load)
    context = create_run_context(config.output_dir, CASE_NAME)
    async with engine.connect() as connection:
        postgres = await read_postgres_metadata(connection)
    database_url = engine.url.render_as_string(hide_password=False)
    print("TaskGraph demo: SQLAlchemy connection pool exhaustion")
    print(f"Database: {safe_database_url(engine)}")
    print(f"Before: pool_size={config.before_pool_size}, concurrency={config.concurrency}")
    before = await measure_pool(
        database_url,
        pool_size=config.before_pool_size,
        concurrency=config.concurrency,
        hold_seconds=config.hold_seconds,
        pool_timeout_seconds=config.pool_timeout_seconds,
    )
    print(f"After: pool_size={config.after_pool_size}, concurrency={config.concurrency}")
    after = await measure_pool(
        database_url,
        pool_size=config.after_pool_size,
        concurrency=config.concurrency,
        hold_seconds=config.hold_seconds,
        pool_timeout_seconds=config.pool_timeout_seconds,
    )
    summary = build_pool_summary(before, after)
    metadata = {
        "schema_version": 1,
        "run_id": str(context.run_id),
        "case": CASE_NAME,
        "generated_at_utc": context.started_at_utc.isoformat(),
        "database_url": safe_database_url(engine),
        "postgres": postgres,
    }
    write_json(context.result_dir / "metadata.json", metadata)
    write_json(context.result_dir / "before.json", before)
    write_json(context.result_dir / "after.json", after)
    write_json(context.result_dir / "summary.json", summary)
    report_path = context.result_dir / "report.md"
    write_text(report_path, render_pool_report(metadata, summary))
    manifest_path = finalize_run(
        context,
        status=summary["status"],
        artifact_names=("metadata.json", "before.json", "after.json", "summary.json", "report.md"),
    )
    return {
        "status": summary["status"],
        "run_id": context.run_id,
        "result_dir": context.result_dir,
        "manifest_path": manifest_path,
        "report_path": report_path,
        "summary": summary,
    }
