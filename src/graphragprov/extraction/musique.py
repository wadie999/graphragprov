"""MuSiQue adapter for grounded extraction."""

from pathlib import Path

from graphragprov.benchmarks.musique import load_case
from graphragprov.config import musique_dataset_path
from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionRun,
    run_grounded_extraction,
)


def run_musique_grounded_extraction(
    *,
    case_id: str,
    paragraph_index: int,
    expected_hops: int,
    generate_response: GenerateResponse,
    path: Path | None = None,
) -> GroundedExtractionRun:
    """Run grounded extraction on one MuSiQue paragraph."""

    source = load_musique_source_unit(
        case_id=case_id,
        paragraph_index=paragraph_index,
        expected_hops=expected_hops,
        path=path,
    )

    return run_grounded_extraction(
        source,
        generate_response,
    )


def load_musique_source_unit(
    *,
    case_id: str,
    paragraph_index: int,
    expected_hops: int,
    path: Path | None = None,
) -> SourceUnit:
    """Load one MuSiQue paragraph as an immutable source unit."""

    if expected_hops not in {2, 3, 4}:
        raise ValueError("expected_hops must be 2, 3, or 4")

    dataset_path = path if path is not None else musique_dataset_path()
    case = load_case(dataset_path, case_id)

    if case.hop_count != expected_hops:
        raise ValueError(f"case {case_id!r} has {case.hop_count} hops, not {expected_hops}")

    paragraph = next(
        (paragraph for paragraph in case.paragraphs if paragraph.index == paragraph_index),
        None,
    )

    if paragraph is None:
        raise ValueError(f"case {case_id!r} has no paragraph with index {paragraph_index}")

    return SourceUnit(
        unit_id=paragraph.unit_id,
        title=paragraph.title,
        text=paragraph.text,
    )


def build_musique_extraction_prompt(
    *,
    case_id: str,
    paragraph_index: int,
    expected_hops: int,
    path: Path | None = None,
) -> str:
    """Build an extraction prompt for one MuSiQue paragraph."""

    source = load_musique_source_unit(
        case_id=case_id,
        paragraph_index=paragraph_index,
        expected_hops=expected_hops,
        path=path,
    )

    return build_extraction_prompt(source)
