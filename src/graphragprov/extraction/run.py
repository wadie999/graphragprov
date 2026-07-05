"""Execution of one grounded extraction."""

from collections.abc import Callable
from dataclasses import dataclass

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.parser import parse_extraction_response
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.result import ExtractionResult

GenerateResponse = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class GroundedExtractionRun:
    """Complete inspectable result of one extraction call."""

    source: SourceUnit
    prompt: str
    response: str
    extraction: ExtractionResult


def run_grounded_extraction(
    source: SourceUnit,
    generate_response: GenerateResponse,
) -> GroundedExtractionRun:
    """Run one model call and validate its grounded response."""

    prompt = build_extraction_prompt(source)
    response = generate_response(prompt)
    extraction = parse_extraction_response(source, response)

    return GroundedExtractionRun(
        source=source,
        prompt=prompt,
        response=response,
        extraction=extraction,
    )
