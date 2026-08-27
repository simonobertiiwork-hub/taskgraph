"""Factories for versioned run artifacts used by unit tests."""

from __future__ import annotations

from pathlib import Path

from demos.common.reporting import (
    DemoRunContext,
    create_run_context,
    finalize_run,
    write_json,
    write_text,
)


def write_index_run(
    root: Path,
    *,
    before_summary_nodes: list[str] | None = None,
) -> DemoRunContext:
    """Write a minimal but internally consistent index-scan run."""
    context = create_run_context(root, "index_scan")
    metadata = {
        "schema_version": 1,
        "run_id": str(context.run_id),
        "case": "index_scan",
        "generated_at_utc": context.started_at_utc.isoformat(),
        "database_url": "postgresql+asyncpg://user:***@db:5432/taskgraph",
        "postgres": {
            "database_name": "taskgraph",
            "database_user": "user",
            "server_version": "15",
        },
        "dataset": {
            "rows": 200_000,
            "lookup_title": "task 150000",
            "runs": 2,
            "warmup_runs_per_phase": 1,
        },
        "query": "SELECT * FROM tasks WHERE title = :title",
        "index": {
            "name": "idx_tasks_title",
            "definition": "CREATE INDEX idx_tasks_title ON tasks(title)",
        },
    }
    before = [
        {
            "run": number,
            "explain": {
                "Plan": {"Node Type": "Seq Scan"},
                "Planning Time": 0.05,
                "Execution Time": execution_time,
            },
        }
        for number, execution_time in enumerate((14.0, 12.0), 1)
    ]
    after = [
        {
            "run": number,
            "explain": {
                "Plan": {
                    "Node Type": "Index Scan",
                    "Index Name": "idx_tasks_title",
                },
                "Planning Time": 0.04,
                "Execution Time": execution_time,
            },
        }
        for number, execution_time in enumerate((0.08, 0.06), 1)
    ]
    summary = {
        "status": "passed",
        "before": {
            "runs": 2,
            "execution_times_ms": [14.0, 12.0],
            "median_execution_time_ms": 13.0,
            "planning_times_ms": [0.05, 0.05],
            "median_planning_time_ms": 0.05,
            "node_types": before_summary_nodes or ["Seq Scan"],
            "index_names": [],
        },
        "after": {
            "runs": 2,
            "execution_times_ms": [0.08, 0.06],
            "median_execution_time_ms": 0.07,
            "planning_times_ms": [0.04, 0.04],
            "median_planning_time_ms": 0.04,
            "node_types": ["Index Scan"],
            "index_names": ["idx_tasks_title"],
        },
        "comparison": {
            "speedup": 185.71428571428572,
            "execution_time_reduction_percent": 99.46153846153847,
        },
        "verification": {
            "before_uses_seq_scan": True,
            "after_uses_index_plan": True,
            "after_uses_expected_index": True,
            "after_median_is_faster": True,
        },
    }
    write_json(context.result_dir / "metadata.json", metadata)
    write_json(context.result_dir / "before.json", before)
    write_json(context.result_dir / "after.json", after)
    write_json(context.result_dir / "summary.json", summary)
    write_text(context.result_dir / "report.md", "# Test index report")
    finalize_run(
        context,
        status="passed",
        artifact_names=(
            "metadata.json",
            "before.json",
            "after.json",
            "summary.json",
            "report.md",
        ),
    )
    return context


def write_race_run(root: Path) -> DemoRunContext:
    """Write the smallest valid non-index run for routing tests."""
    context = create_run_context(root, "race_condition")
    write_json(
        context.result_dir / "metadata.json",
        {
            "schema_version": 1,
            "run_id": str(context.run_id),
            "case": "race_condition",
        },
    )
    write_json(context.result_dir / "summary.json", {"status": "passed"})
    write_text(context.result_dir / "report.md", "# Test race report")
    finalize_run(
        context,
        status="passed",
        artifact_names=("metadata.json", "summary.json", "report.md"),
    )
    return context
