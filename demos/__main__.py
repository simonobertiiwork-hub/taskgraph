"""Command-line entry point for TaskGraph demonstration scenarios."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from demos.cases.index_scan import IndexScanConfig, run_index_scan
from demos.common.database import DemoSafetyError


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def positive_int(value: str) -> int:
    """Parse an integer CLI option that must be greater than zero."""
    parsed = int(value)
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
    print(f"Report: {result['report_path']}")
    return 0 if result["status"] == "passed" else 1


def main() -> int:
    """Parse arguments and run the requested demo."""
    parser = build_parser()
    args = parser.parse_args()

    if args.case == "index-scan":
        try:
            return asyncio.run(run_index_scan_command(args))
        except (DemoSafetyError, ValueError) as exc:
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

    parser.error(f"Unknown demo case: {args.case}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
