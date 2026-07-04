import argparse
import sys
from collections.abc import Callable, Sequence
from typing import cast

from graphragprov.cli.benchmark import add_benchmark_commands

CommandHandler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphragprov",
        description="GraphRAGProv research tools.",
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    benchmark_parser = commands.add_parser(
        "benchmark",
        help="Inspect supported benchmarks.",
    )
    add_benchmark_commands(benchmark_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    handler = cast(CommandHandler, arguments.handler)

    try:
        return handler(arguments)
    except (FileNotFoundError, KeyError, ValueError) as error:
        message = error.args[0] if isinstance(error, KeyError) else str(error)
        print(f"error: {message}", file=sys.stderr)
        return 2
