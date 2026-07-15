"""Execution of one grounded extraction."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.parser import parse_extraction_response
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.result import ExtractionResult

GenerateResponse = Callable[[str], str]

ExtractionFailureStage = Literal[
    "provider",
    "response_validation",
]


@dataclass(frozen=True, slots=True)
class GroundedExtractionRun:
    """Complete inspectable result of one successful extraction call."""

    source: SourceUnit
    prompt: str
    response: str
    extraction: ExtractionResult


@dataclass(frozen=True, slots=True)
class GroundedExtractionFailure:
    """Inspectable failure produced while running one extraction."""

    source: SourceUnit
    prompt: str
    response: str | None
    stage: ExtractionFailureStage
    error_type: str
    error_message: str


GroundedExtractionOutcome = GroundedExtractionRun | GroundedExtractionFailure


def run_grounded_extraction(
    source: SourceUnit,
    generate_response: GenerateResponse,
) -> GroundedExtractionRun:
    """Run one model call and validate its grounded response.

    Provider and response-validation errors are propagated.
    """

    prompt = build_extraction_prompt(source)
    response = generate_response(prompt)
    extraction = parse_extraction_response(source, response)

    return GroundedExtractionRun(
        source=source,
        prompt=prompt,
        response=response,
        extraction=extraction,
    )


def run_grounded_extraction_outcome(
    source: SourceUnit,
    generate_response: GenerateResponse,
) -> GroundedExtractionOutcome:
    """Run one extraction and represent failures as inspectable outcomes."""

    prompt = build_extraction_prompt(source)

    try:
        response = generate_response(prompt)
    except Exception as error:
        return GroundedExtractionFailure(
            source=source,
            prompt=prompt,
            response=None,
            stage="provider",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    try:
        extraction = parse_extraction_response(
            source,
            response,
        )
    except Exception as error:
        return GroundedExtractionFailure(
            source=source,
            prompt=prompt,
            response=response,
            stage="response_validation",
            error_type=type(error).__name__,
            error_message=str(error),
        )

    return GroundedExtractionRun(
        source=source,
        prompt=prompt,
        response=response,
        extraction=extraction,
    )
