"""Command-line entry point for TaskGraph demonstration scenarios."""

from __future__ import annotations

import argparse
import asyncio

from demos.common.database import (
    DemoSafetyError,
    require_demo_reset_confirmation,
    safe_database_url,
)


async def check_index_scan_safety(
    args: argparse.Namespace,
) -> int:
    """Check whether the index-scan demo may reset its data."""

    from app.db.session import engine

    try:
        print(
            f"Database: {safe_database_url(engine)}"
        )

        require_demo_reset_confirmation(
            engine,
            confirmed=args.confirm_reset,
        )

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
        "--confirm-reset",
        action="store_true",
        help="Allow the demo to truncate the tasks table.",
    )

    index_parser.set_defaults(
        handler=check_index_scan_safety,
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
    except DemoSafetyError as exc:
        parser.exit(
            status=2,
            message=f"error: {exc}\n",
        )


if __name__ == "__main__":
    raise SystemExit(main())