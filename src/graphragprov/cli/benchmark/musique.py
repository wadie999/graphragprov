import argparse
from pathlib import Path

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueSourceUnit,
    find_unit,
    load_case,
    select_cases,
)
from graphragprov.config import musique_dataset_path


def configure_musique_parser(parser: argparse.ArgumentParser) -> None:
    """Register MuSiQue inspection commands."""

    commands = parser.add_subparsers(
        dest="musique_command",
        required=True,
    )

    list_parser = commands.add_parser(
        "list",
        help="List MuSiQue cases.",
    )
    list_parser.add_argument(
        "--hops",
        type=int,
        choices=(2, 3, 4),
        required=True,
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_parser.add_argument(
        "--answerable-only",
        action="store_true",
    )
    list_parser.set_defaults(handler=_handle_list)

    case_parser = commands.add_parser(
        "case",
        help="Inspect one MuSiQue case.",
    )
    case_parser.add_argument("case_id")
    case_parser.add_argument(
        "--supports-only",
        action="store_true",
    )
    case_parser.set_defaults(handler=_handle_case)

    unit_parser = commands.add_parser(
        "unit",
        help="Inspect one MuSiQue source unit.",
    )
    unit_parser.add_argument("unit_reference")
    unit_parser.set_defaults(handler=_handle_unit)


def _handle_list(arguments: argparse.Namespace) -> int:
    cases = select_cases(
        path=_require_dataset(),
        hop_count=arguments.hops,
        limit=arguments.limit,
        answerable_only=arguments.answerable_only,
    )

    for case in cases:
        print(case.case_id)
        print(f"  Hops: {case.hop_count}")
        print(f"  Answerable: {case.answerable}")
        print(f"  Question: {case.question}")
        print()

    return 0


def _handle_case(arguments: argparse.Namespace) -> int:
    case = load_case(
        path=_require_dataset(),
        case_id=arguments.case_id,
    )

    _print_case(
        case,
        supports_only=arguments.supports_only,
    )

    return 0


def _handle_unit(arguments: argparse.Namespace) -> int:
    unit = find_unit(
        path=_require_dataset(),
        unit_reference=arguments.unit_reference,
    )

    _print_unit(unit)
    return 0


def _require_dataset() -> Path:
    path = musique_dataset_path()

    if not path.is_file():
        raise FileNotFoundError(f"MuSiQue dataset not found: {path}")

    return path


def _print_case(
    case: MusiqueCase,
    *,
    supports_only: bool,
) -> None:
    print(f"Case: {case.case_id}")
    print(f"Hops: {case.hop_count}")
    print(f"Answerable: {case.answerable}")
    print(f"Question: {case.question}")
    print(f"Answer: {case.answer}")

    aliases = ", ".join(case.answer_aliases) or "None"
    print(f"Answer aliases: {aliases}")

    print("\nDecomposition")

    for position, hop in enumerate(case.decomposition, start=1):
        print(f"\nHop {position}")
        print(f"  ID: {hop.hop_id}")
        print(f"  Question: {hop.question}")
        print(f"  Answer: {hop.answer}")
        print(f"  Paragraph index: {hop.paragraph_support_index}")

    paragraphs = case.supporting_paragraphs if supports_only else case.paragraphs

    print("\nParagraphs")

    for paragraph in paragraphs:
        print("\n" + "-" * 80)
        print(f"Index: {paragraph.index}")
        print(f"Supporting: {case.is_supporting(paragraph.index)}")
        print(f"Unit: {paragraph.short_unit_id}")
        print(f"Full unit ID: {paragraph.unit_id}")
        print(f"Title: {paragraph.title}")
        print("Text:")
        print(paragraph.text)


def _print_unit(unit: MusiqueSourceUnit) -> None:
    print(f"Unit: {unit.unit_id[:14]}")
    print(f"Full unit ID: {unit.unit_id}")
    print(f"Occurrences: {len(unit.occurrences)}")

    print("\nText:")
    print(unit.text)

    print("\nOccurrences")

    for occurrence in unit.occurrences:
        print("\n" + "-" * 80)
        print(f"Case: {occurrence.case_id}")
        print(f"Paragraph index: {occurrence.paragraph_index}")
        print(f"Title: {occurrence.title}")
        print(f"Supporting: {occurrence.is_supporting}")
