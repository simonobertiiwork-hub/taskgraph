"""Command-line entry point for TaskGraph demonstration scenarios."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.ai.repositories.runs import FileRunRepository, RunRepositoryError
from app.ai.schemas import RunScenario, RunStatus
from app.ai.tools.index_scan import IndexScanTools
from demos.cases.index_scan import IndexScanConfig, run_index_scan
from demos.cases.race_condition import RaceConditionConfig, run_race_condition
from demos.cases.pool_exhaustion import PoolExhaustionConfig, run_pool_exhaustion
from demos.common.database import DemoSafetyError

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def positive_int(value: str) -> int:
    """Parse an integer CLI option that must be greater than zero."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def positive_float(value: str) -> float:
    """Parse a floating-point CLI option that must be greater than zero."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the demos command-line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m demos",
        description="Run reproducible TaskGraph engineering demonstrations.",
    )
    subparsers = parser.add_subparsers(dest="case", required=True)

    index_parser = subparsers.add_parser(
        "index-scan",
        help="Compare PostgreSQL sequential and index lookup plans.",
    )
    index_parser.add_argument(
        "--rows",
        type=positive_int,
        default=200_000,
        help="Number of tasks to generate (default: 200000).",
    )
    index_parser.add_argument(
        "--target",
        type=positive_int,
        default=150_000,
        help="Task number used by the lookup query (default: 150000).",
    )
    index_parser.add_argument(
        "--runs",
        type=positive_int,
        default=5,
        help="Measured EXPLAIN ANALYZE runs per phase (default: 5).",
    )
    index_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for raw plans and generated reports.",
    )
    index_parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Allow the demo to truncate the tasks table.",
    )

    race_parser = subparsers.add_parser(
        "race-condition",
        help="Compare unsafe, pessimistic, and optimistic concurrent writes.",
    )
    race_parser.add_argument(
        "--hold-seconds",
        type=positive_float,
        default=1.0,
        help="How long transaction A holds the row lock (default: 1.0).",
    )
    race_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for generated evidence reports.",
    )
    race_parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="Allow the demo to create, update, and delete one task fixture.",
    )

    pool_parser = subparsers.add_parser(
        "pool-exhaustion",
        help="Compare undersized and correctly sized SQLAlchemy pools.",
    )
    pool_parser.add_argument("--concurrency", type=positive_int, default=5)
    pool_parser.add_argument("--hold-seconds", type=positive_float, default=0.35)
    pool_parser.add_argument("--pool-timeout", type=positive_float, default=0.20)
    pool_parser.add_argument("--before-pool-size", type=positive_int, default=2)
    pool_parser.add_argument("--after-pool-size", type=positive_int, default=5)
    pool_parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    pool_parser.add_argument("--confirm-load", action="store_true")

    inspect_parser = subparsers.add_parser(
        "inspect-index-run",
        help="Validate one index-scan run and print grounded tool outputs.",
    )
    inspect_parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Root containing versioned run manifests.",
    )
    inspect_parser.add_argument(
        "--run-id",
        type=UUID,
        help="Specific run UUID; defaults to the latest index-scan run.",
    )

    ai_parser = subparsers.add_parser(
        "ai-incident-analyst",
        help="Analyze one verified run through LangGraph and a live LLM.",
    )
    ai_parser.add_argument(
        "--run-id",
        type=UUID,
        help="Specific run UUID; defaults to the latest index-scan run.",
    )
    ai_parser.add_argument(
        "--scenario",
        choices=("index-scan", "race-condition", "pool-exhaustion"),
        default="index-scan",
        help="Scenario used when --run-id is omitted.",
    )

    rag_parser = subparsers.add_parser(
        "rag-index",
        help="Incrementally index TaskGraph Markdown documentation in pgvector.",
    )
    rag_parser.add_argument(
        "--project-root", type=Path, default=Path("."),
        help="TaskGraph project root (default: current directory).",
    )
    eval_parser = subparsers.add_parser(
        "ai-evals",
        help="Run 20 offline grounded-agent regression evaluations.",
    )
    eval_parser.add_argument(
        "--dataset", type=Path, default=Path("demos/evals/incident_cases.json")
    )
    eval_parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    eval_parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    ai_parser.add_argument(
        "--question",
        default=None,
        help="Technical question passed to the agent as untrusted data.",
    )
    ai_parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Root containing versioned TaskGraph run manifests.",
    )
    ai_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Root for generated AI analysis artifacts.",
    )

    return parser


async def run_index_scan_command(args: argparse.Namespace) -> int:
    """Run the index-scan command using the application's database engine."""
    # Import lazily so pure demo helpers can be tested without application settings.
    from app.db.session import engine

    config = IndexScanConfig(
        rows=args.rows,
        target=args.target,
        runs=args.runs,
        output_dir=args.output_dir,
        confirm_reset=args.confirm_reset,
    )

    try:
        result = await run_index_scan(engine, config)
    finally:
        await engine.dispose()

    print()
    print(f"Result: {result['status'].upper()}")
    print(f"Run ID: {result['run_id']}")
    print(f"Report: {result['report_path']}")
    return 0 if result["status"] == "passed" else 1


async def run_race_condition_command(args: argparse.Namespace) -> int:
    """Run the race-condition command using the application database."""
    from app.db.session import engine

    config = RaceConditionConfig(
        hold_seconds=args.hold_seconds,
        output_dir=args.output_dir,
        confirm_write=args.confirm_write,
    )

    try:
        result = await run_race_condition(engine, config)
    finally:
        await engine.dispose()

    print()
    print(f"Result: {result['status'].upper()}")
    print(f"Run ID: {result['run_id']}")
    print(f"Report: {result['report_path']}")
    return 0 if result["status"] == "passed" else 1


async def run_pool_exhaustion_command(args: argparse.Namespace) -> int:
    from app.db.session import engine

    config = PoolExhaustionConfig(
        concurrency=args.concurrency,
        hold_seconds=args.hold_seconds,
        pool_timeout_seconds=args.pool_timeout,
        before_pool_size=args.before_pool_size,
        after_pool_size=args.after_pool_size,
        output_dir=args.output_dir,
        confirm_load=args.confirm_load,
    )
    try:
        result = await run_pool_exhaustion(engine, config)
    finally:
        await engine.dispose()
    print()
    print(f"Before pool timeouts: {result['summary']['before']['pool_timeouts']}")
    print(f"After pool timeouts: {result['summary']['after']['pool_timeouts']}")
    print(f"Result: {result['status'].upper()}")
    print(f"Run ID: {result['run_id']}")
    print(f"Report: {result['report_path']}")
    return 0 if result["status"] == "passed" else 1


async def run_inspect_index_run_command(args: argparse.Namespace) -> int:
    """Exercise the future agent tools without making any LLM call."""
    repository = FileRunRepository(args.results_dir)
    run = (
        repository.get(args.run_id)
        if args.run_id is not None
        else repository.latest(RunScenario.INDEX_SCAN)
    )
    tools = IndexScanTools(repository)
    summary = tools.get_run_summary(run.manifest.run_id)
    plans = tools.get_query_plan(run.manifest.run_id)

    print("TaskGraph AI evidence contract: Index Scan")
    print(f"Run ID: {summary.run_id}")
    print(f"Schema version: {summary.schema_version}")
    print(f"Dataset rows: {summary.dataset_rows}")
    print(
        "Median execution time: "
        f"{summary.before_execution_time_ms:.6f} ms -> "
        f"{summary.after_execution_time_ms:.6f} ms"
    )
    print(
        "Plan transition: "
        f"{', '.join(plans.before.node_types)} -> "
        f"{', '.join(plans.after.node_types)}"
    )
    print(f"Evidence references: {len(summary.evidence) + len(plans.evidence)}")
    passed = summary.status == RunStatus.PASSED and plans.transition_verified is True
    print()
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


async def run_ai_incident_analyst_command(args: argparse.Namespace) -> int:
    """Run the live-provider LangGraph case without importing it for other demos."""
    from app.core.config import settings
    from demos.cases.ai_incident_analyst import (
        AIIncidentDemoConfig,
        run_ai_incident_analyst,
    )

    result = await run_ai_incident_analyst(
        settings,
        AIIncidentDemoConfig(
            results_dir=args.results_dir,
            output_dir=args.output_dir,
            run_id=args.run_id,
            question=(
                args.question
                or (
                    "Почему возник lost update и как optimistic locking с version predicate обнаруживает конфликт?"
                    if args.scenario == "race-condition"
                    else (
                        "Почему возникли connection pool timeout и как изменение pool_size устранило ошибки?"
                        if args.scenario == "pool-exhaustion"
                        else "Почему запрос выполнялся медленно, что было причиной и какое изменение исправило проблему?"
                    )
                )
            ),
            scenario={
                "index-scan": RunScenario.INDEX_SCAN,
                "race-condition": RunScenario.RACE_CONDITION,
                "pool-exhaustion": RunScenario.CONNECTION_POOL_EXHAUSTION,
            }[args.scenario],
        ),
    )
    print()
    print(f"Result: {'PASSED' if result['passed'] else 'FAILED'}")
    print(f"Analysis ID: {result['analysis_id']}")
    print(f"Report: {result['report_path']}")
    return 0 if result["passed"] else 1


async def run_rag_index_command(args: argparse.Namespace) -> int:
    from app.ai.rag.embeddings import HashEmbeddingProvider
    from app.ai.rag.repository import PgVectorDocumentRepository
    from app.ai.rag.service import RAGService
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal, engine

    service = RAGService(
        PgVectorDocumentRepository(AsyncSessionLocal),
        HashEmbeddingProvider(model=settings.embedding_model, dimensions=settings.embedding_dimensions),
        top_k=settings.rag_top_k,
        threshold=settings.rag_score_threshold,
    )
    try:
        result = await service.index_project(args.project_root.resolve())
    finally:
        await engine.dispose()
    print("TaskGraph RAG index: pgvector")
    for key, value in result.items():
        print(f"{key}: {value}")
    print("Result: PASSED")
    return 0


async def run_ai_evals_command(args: argparse.Namespace) -> int:
    from demos.cases.ai_evals import AIEvalConfig, run_ai_evals

    result = await run_ai_evals(
        AIEvalConfig(
            dataset_path=args.dataset,
            results_dir=args.results_dir,
            output_dir=args.output_dir,
        )
    )
    metrics = result["metrics"]
    print("TaskGraph AI offline evals")
    print(f"Cases: {metrics['total_cases']}")
    print(f"Tool selection accuracy: {metrics['tool_selection_accuracy_percent']}%")
    print(f"Completion rate: {metrics['completion_rate_percent']}%")
    print(f"Grounding rate: {metrics['grounding_rate_percent']}%")
    print(f"Result: {'PASSED' if result['passed'] else 'FAILED'}")
    print(f"Report: {result['report_path']}")
    return 0 if result["passed"] else 1


def run_command(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Dispatch one parsed demo command with consistent error handling."""
    command = {
        "index-scan": run_index_scan_command,
        "race-condition": run_race_condition_command,
        "pool-exhaustion": run_pool_exhaustion_command,
        "inspect-index-run": run_inspect_index_run_command,
        "ai-incident-analyst": run_ai_incident_analyst_command,
        "rag-index": run_rag_index_command,
        "ai-evals": run_ai_evals_command,
    }.get(args.case)

    if command is None:
        parser.error(f"Unknown demo case: {args.case}")

    try:
        return asyncio.run(command(args))
    except (DemoSafetyError, RunRepositoryError, ValueError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")
    except SQLAlchemyError:
        parser.exit(
            status=2,
            message=(
                "error: Could not execute the PostgreSQL demo. "
                "Check docker compose ps and run the command "
                "inside the app container.\n"
            ),
        )


def main() -> int:
    """Parse arguments and run the requested demo."""
    parser = build_parser()
    args = parser.parse_args()
    return run_command(parser, args)


if __name__ == "__main__":
    raise SystemExit(main())
