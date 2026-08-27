"""Reproducible PostgreSQL Seq Scan to Index Scan demonstration."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from demos.common.database import (
    read_postgres_metadata,
    require_demo_reset_confirmation,
    safe_database_url,
)
from demos.common.reporting import create_result_directory, write_json, write_text

CASE_NAME = "index_scan"
INDEX_NAME = "idx_tasks_title"
LOOKUP_QUERY = "SELECT * FROM tasks WHERE title = :title"
INDEX_NODE_TYPES = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}


@dataclass(frozen=True, slots=True)
class IndexScanConfig:
    """Runtime parameters for the index-scan demonstration."""

    rows: int = 200_000
    target: int = 150_000
    runs: int = 5
    output_dir: Path = Path("demos/results")
    confirm_reset: bool = False

    def validate(self) -> None:
        if self.rows <= 0:
            raise ValueError("rows must be greater than zero")
        if not 1 <= self.target <= self.rows:
            raise ValueError("target must be between 1 and rows")
        if self.runs <= 0:
            raise ValueError("runs must be greater than zero")


def normalize_explain_payload(raw_payload: Any) -> dict[str, Any]:
    """Normalize PostgreSQL FORMAT JSON output to its top-level object."""
    if isinstance(raw_payload, str):
        raw_payload = json.loads(raw_payload)

    if isinstance(raw_payload, dict):
        raw_payload = [raw_payload]

    if (
        not isinstance(raw_payload, list)
        or len(raw_payload) != 1
        or not isinstance(raw_payload[0], dict)
        or "Plan" not in raw_payload[0]
    ):
        raise ValueError("Unexpected PostgreSQL EXPLAIN JSON payload")

    return raw_payload[0]


def iter_plan_nodes(plan: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield the root and every nested PostgreSQL execution-plan node."""
    yield plan
    for child in plan.get("Plans", []):
        yield from iter_plan_nodes(child)


def plan_node_types(explain: dict[str, Any]) -> list[str]:
    """Return execution node types in traversal order."""
    return [
        str(node["Node Type"])
        for node in iter_plan_nodes(explain["Plan"])
        if "Node Type" in node
    ]


def plan_index_names(explain: dict[str, Any]) -> list[str]:
    """Return index names referenced anywhere in an execution plan."""
    return [
        str(node["Index Name"])
        for node in iter_plan_nodes(explain["Plan"])
        if "Index Name" in node
    ]


def summarize_plans(plans: list[dict[str, Any]]) -> dict[str, Any]:
    """Build stable aggregate metrics from measured EXPLAIN results."""
    if not plans:
        raise ValueError("At least one execution plan is required")

    execution_times = [float(plan["Execution Time"]) for plan in plans]
    planning_times = [float(plan["Planning Time"]) for plan in plans]
    node_types = sorted({node for plan in plans for node in plan_node_types(plan)})
    index_names = sorted({name for plan in plans for name in plan_index_names(plan)})

    return {
        "runs": len(plans),
        "execution_times_ms": execution_times,
        "median_execution_time_ms": median(execution_times),
        "planning_times_ms": planning_times,
        "median_planning_time_ms": median(planning_times),
        "node_types": node_types,
        "index_names": index_names,
    }


def build_summary(
    before_plans: list[dict[str, Any]],
    after_plans: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare both phases and verify the expected plan transition."""
    before = summarize_plans(before_plans)
    after = summarize_plans(after_plans)

    before_is_sequential = all(
        "Seq Scan" in plan_node_types(plan) for plan in before_plans
    )
    after_uses_index = all(
        any(node in INDEX_NODE_TYPES for node in plan_node_types(plan))
        for plan in after_plans
    )
    after_uses_expected_index = all(
        INDEX_NAME in plan_index_names(plan) for plan in after_plans
    )

    before_median = before["median_execution_time_ms"]
    after_median = after["median_execution_time_ms"]
    after_is_faster = after_median < before_median

    speedup = before_median / after_median if after_median > 0 else None
    reduction_percent = (
        (1 - after_median / before_median) * 100 if before_median > 0 else None
    )

    verification = {
        "before_uses_seq_scan": before_is_sequential,
        "after_uses_index_plan": after_uses_index,
        "after_uses_expected_index": after_uses_expected_index,
        "after_median_is_faster": after_is_faster,
    }
    passed = all(verification.values())

    return {
        "status": "passed" if passed else "failed",
        "before": before,
        "after": after,
        "comparison": {
            "speedup": speedup,
            "execution_time_reduction_percent": reduction_percent,
        },
        "verification": verification,
    }


async def explain_lookup(
    conn: AsyncConnection,
    *,
    title: str,
) -> dict[str, Any]:
    """Execute the lookup and return one normalized EXPLAIN JSON object."""
    result = await conn.execute(
        text(
            """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT *
            FROM tasks
            WHERE title = :title
            """
        ),
        {"title": title},
    )
    return normalize_explain_payload(result.scalar_one())


async def measure_lookup(
    conn: AsyncConnection,
    *,
    title: str,
    runs: int,
) -> list[dict[str, Any]]:
    """Warm up once, then collect the requested number of plans."""
    await explain_lookup(conn, title=title)
    return [await explain_lookup(conn, title=title) for _ in range(runs)]


async def prepare_dataset(conn: AsyncConnection, *, rows: int) -> None:
    """Reset only tasks and generate a deterministic dataset."""
    await conn.execute(text(f'DROP INDEX IF EXISTS "{INDEX_NAME}"'))
    await conn.execute(text("TRUNCATE TABLE tasks RESTART IDENTITY"))
    await conn.execute(
        text(
            """
            INSERT INTO tasks(title, status, version)
            SELECT
                'task ' || generated_number,
                'new',
                1
            FROM generate_series(1, :rows) AS generated(generated_number)
            """
        ),
        {"rows": rows},
    )
    await conn.execute(text("ANALYZE tasks"))


async def create_index(conn: AsyncConnection) -> None:
    """Create and analyze the index used by the fixed lookup."""
    await conn.execute(text(f'CREATE INDEX "{INDEX_NAME}" ON tasks(title)'))
    await conn.execute(text("ANALYZE tasks"))


def render_report(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render a concise Markdown report from actual measurements."""
    before = summary["before"]
    after = summary["after"]
    comparison = summary["comparison"]
    verification = summary["verification"]

    speedup = comparison["speedup"]
    reduction = comparison["execution_time_reduction_percent"]
    speedup_text = f"{speedup:.2f}x" if speedup is not None else "n/a"
    reduction_text = f"{reduction:.2f}%" if reduction is not None else "n/a"

    verification_rows = "\n".join(
        f"| `{name}` | {'PASS' if value else 'FAIL'} |"
        for name, value in verification.items()
    )

    return f"""# Case #1: PostgreSQL Seq Scan to Index Scan

Generated at: `{metadata["generated_at_utc"]}`

## Environment

- Database: `{metadata["postgres"]["database_name"]}`
- PostgreSQL: `{metadata["postgres"]["server_version"]}`
- Rows: `{metadata["dataset"]["rows"]}`
- Lookup title: `{metadata["dataset"]["lookup_title"]}`
- Measured runs per phase: `{metadata["dataset"]["runs"]}`

## Query

```sql
{metadata["query"]}
```

## Result

| Phase | Median execution time | Plan nodes | Indexes |
| --- | ---: | --- | --- |
| Before | {before["median_execution_time_ms"]:.6f} ms | {", ".join(before["node_types"])} | {", ".join(before["index_names"]) or "none"} |
| After | {after["median_execution_time_ms"]:.6f} ms | {", ".join(after["node_types"])} | {", ".join(after["index_names"]) or "none"} |

- Speedup: **{speedup_text}**
- Execution-time reduction: **{reduction_text}**

## Verification

| Check | Result |
| --- | --- |
{verification_rows}

Overall status: **{summary["status"].upper()}**

Raw PostgreSQL plans are stored in `before.json` and `after.json`.
"""


async def run_index_scan(
    engine: AsyncEngine,
    config: IndexScanConfig,
) -> dict[str, Any]:
    """Run the complete index demonstration and persist its evidence."""
    config.validate()
    require_demo_reset_confirmation(engine, confirmed=config.confirm_reset)

    result_dir = create_result_directory(config.output_dir, CASE_NAME)
    lookup_title = f"task {config.target}"

    print("TaskGraph demo: PostgreSQL Seq Scan to Index Scan")
    print(f"Database: {safe_database_url(engine)}")
    print(f"Result directory: {result_dir}")
    print(f"Preparing {config.rows} deterministic tasks...")

    async with engine.begin() as conn:
        postgres_metadata = await read_postgres_metadata(conn)
        await prepare_dataset(conn, rows=config.rows)

    print("Measuring the lookup without the title index...")
    async with engine.connect() as conn:
        before_plans = await measure_lookup(
            conn,
            title=lookup_title,
            runs=config.runs,
        )

    print(f"Creating {INDEX_NAME}...")
    async with engine.begin() as conn:
        await create_index(conn)

    print("Repeating the same lookup with the title index...")
    async with engine.connect() as conn:
        after_plans = await measure_lookup(
            conn,
            title=lookup_title,
            runs=config.runs,
        )

    summary = build_summary(before_plans, after_plans)
    metadata = {
        "case": CASE_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_url": safe_database_url(engine),
        "postgres": postgres_metadata,
        "dataset": {
            "rows": config.rows,
            "lookup_title": lookup_title,
            "runs": config.runs,
            "warmup_runs_per_phase": 1,
        },
        "query": LOOKUP_QUERY,
        "index": {
            "name": INDEX_NAME,
            "definition": f"CREATE INDEX {INDEX_NAME} ON tasks(title)",
        },
    }

    write_json(result_dir / "metadata.json", metadata)
    write_json(
        result_dir / "before.json",
        [
            {"run": number, "explain": plan}
            for number, plan in enumerate(before_plans, 1)
        ],
    )
    write_json(
        result_dir / "after.json",
        [
            {"run": number, "explain": plan}
            for number, plan in enumerate(after_plans, 1)
        ],
    )
    write_json(result_dir / "summary.json", summary)
    report_path = result_dir / "report.md"
    write_text(report_path, render_report(metadata, summary))

    print(
        "Median execution time: "
        f"{summary['before']['median_execution_time_ms']:.6f} ms -> "
        f"{summary['after']['median_execution_time_ms']:.6f} ms"
    )

    return {
        "status": summary["status"],
        "result_dir": result_dir,
        "report_path": report_path,
        "summary": summary,
    }
