"""Command-line entry point for TaskGraph demonstration scenarios."""

import argparse


def select_index_scan(_: argparse.Namespace) -> int:
    """Confirm that the index-scan command was selected."""
    print("Selected demo: index-scan")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the demos command-line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m demos",
        description="Run reproducible TaskGraph engineering demonstrations.",
    )

    subparsers = parser.add_subparsers(
        dest="case",
        required=True,
    )

    index_parser = subparsers.add_parser(
        "index-scan",
        help="Compare PostgreSQL sequential and index lookup plans.",
    )
    index_parser.set_defaults(handler=select_index_scan)

    return parser


def main() -> int:
    """Parse arguments and run the selected command."""
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())