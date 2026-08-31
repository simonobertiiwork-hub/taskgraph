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
    """Write a compact, internally consistent race-condition run."""
    context = create_run_context(root, "race_condition")
    write_json(
        context.result_dir / "metadata.json",
        {
            "schema_version": 1,
            "run_id": str(context.run_id),
            "case": "race_condition",
        },
    )
    write_json(
        context.result_dir / "summary.json",
        {
            "status": "passed",
            "scenarios": {
                "last_write_wins": {
                    "transaction_a_read": {"title": "original", "version": 1},
                    "transaction_b_read": {"title": "original", "version": 1},
                    "final": {"title": "task B", "version": 1},
                },
                "pessimistic_lock": {
                    "transaction_b": {"lock_wait_seconds": 1.01},
                },
                "optimistic_lock": {
                    "transaction_b_rows_updated": 0,
                    "transaction_b_conflict_detected": True,
                    "final": {"title": "task A", "version": 2},
                },
            },
            "verification": {
                "last_write_wins": {
                    "both_transactions_read_original": True,
                    "first_write_was_lost": True,
                },
                "pessimistic_lock": {"second_writer_waited_for_lock": True},
                "optimistic_lock": {
                    "stale_second_writer_updated_no_rows": True,
                    "conflict_was_detected": True,
                },
            },
        },
    )
    write_text(context.result_dir / "report.md", "# Test race report")
    finalize_run(
        context,
        status="passed",
        artifact_names=("metadata.json", "summary.json", "report.md"),
    )
    return context


def write_pool_run(root: Path) -> DemoRunContext:
    """Write a compact, internally consistent pool-exhaustion run."""
    context = create_run_context(root, "connection_pool_exhaustion")
    metadata = {
        "schema_version": 1,
        "run_id": str(context.run_id),
        "case": "connection_pool_exhaustion",
    }
    before = {
        "pool_size": 2,
        "max_overflow": 0,
        "pool_timeout_seconds": 0.2,
        "concurrency": 5,
        "hold_seconds": 0.35,
        "completed_requests": 2,
        "pool_timeouts": 3,
        "failure_rate_percent": 60.0,
        "elapsed_ms": 360.0,
        "requests": [],
    }
    after = {
        **before,
        "pool_size": 5,
        "completed_requests": 5,
        "pool_timeouts": 0,
        "failure_rate_percent": 0.0,
    }
    summary = {
        "status": "passed",
        "before": {key: value for key, value in before.items() if key != "requests"},
        "after": {key: value for key, value in after.items() if key != "requests"},
        "comparison": {
            "timeouts_removed": 3,
            "completed_requests_added": 3,
            "failure_rate_reduction_percentage_points": 60.0,
        },
        "verification": {
            "before_pool_saturated": True,
            "before_capacity_was_lower_than_concurrency": True,
            "after_used_identical_load": True,
            "after_pool_matches_concurrency": True,
            "after_has_no_pool_timeouts": True,
            "completed_requests_increased": True,
        },
    }
    write_json(context.result_dir / "metadata.json", metadata)
    write_json(context.result_dir / "before.json", before)
    write_json(context.result_dir / "after.json", after)
    write_json(context.result_dir / "summary.json", summary)
    write_text(context.result_dir / "report.md", "# Test pool report")
    finalize_run(
        context,
        status="passed",
        artifact_names=("metadata.json", "before.json", "after.json", "summary.json", "report.md"),
    )
    return context
