"""Command-line entry point for TaskGraph demonstration scenarios."""

from __future__ import annotations

import argparse
import asyncio

from demos.cases.index_scan import IndexScanConfig
from demos.common.database import (
    DemoSafetyError,
    require_demo_reset_confirmation,
    safe_database_url,
)


def positive_int(value: str) -> int:
    """Parse a positive integer CLI parameter."""

    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be an integer"
        ) from exc

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(
            "value must be greater than zero"
        )

    return parsed_value


async def check_index_scan_configuration(
    args: argparse.Namespace,
) -> int:
    """Validate configuration and database safety."""

    config = IndexScanConfig(
        rows=args.rows,
        target=args.target,
        runs=args.runs,
        confirm_reset=args.confirm_reset,
    )

    config.validate()

    from app.db.session import engine

    try:
        print(
            f"Database: {safe_database_url(engine)}"
        )

        require_demo_reset_confirmation(
            engine,
            confirmed=config.confirm_reset,
        )

        print("Configuration:")
        print(f"  rows: {config.rows}")
        print(f"  target: {config.target}")
        print(f"  runs: {config.runs}")

        print("Safety checks passed.")
        print("No database query was executed.")

        return 0
    finally:
        await engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    """Build the demos command-line parser."""

    parser = argparse.ArgumentParser(
        prog="python -m demos",
        description=(
            "Run reproducible TaskGraph "
            "engineering demonstrations."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="case",
        required=True,
    )

    index_parser = subparsers.add_parser(
        "index-scan",
        help=(
            "Compare PostgreSQL sequential "
            "and index lookup plans."
        ),
    )

    index_parser.add_argument(
        "--rows",
        type=positive_int,
        default=200_000,
        help="Number of generated tasks.",
    )

    index_parser.add_argument(
        "--target",
        type=positive_int,
        default=150_000,
        help="Task number used by the lookup query.",
    )

    index_parser.add_argument(
        "--runs",
        type=positive_int,
        default=5,
        help="Number of measured query executions.",
    )

    index_parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Allow the demo to truncate the tasks table.",
    )

    index_parser.set_defaults(
        handler=check_index_scan_configuration,
    )

    return parser


def main() -> int:
    """Parse arguments and run the selected command."""

    parser = build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(
            args.handler(args)
        )
    except (DemoSafetyError, ValueError) as exc:
        parser.exit(
            status=2,
            message=f"error: {exc}\n",
        )


if __name__ == "__main__":
    raise SystemExit(main())