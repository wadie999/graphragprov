import argparse

from graphragprov.cli.benchmark.musique import configure_musique_parser


def add_benchmark_commands(parser: argparse.ArgumentParser) -> None:
    """Register benchmark-specific command groups."""

    benchmarks = parser.add_subparsers(
        dest="benchmark",
        required=True,
    )

    musique_parser = benchmarks.add_parser(
        "musique",
        help="Inspect the MuSiQue benchmark.",
    )
    configure_musique_parser(musique_parser)
