"""Execution of one grounded extraction."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.parser import (
    ParsedExtractionResponse,
    RejectedExtractionStatement,
    parse_extraction_response_partially,
)
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.statement import GroundedStatement

GenerateResponse = Callable[[str], str]

ExtractionFailureStage = Literal["provider", "response_validation"]


@dataclass(frozen=True, slots=True)
class GroundedExtractionCorrection:
    """One correction call over independently rejected statements."""

    prompt: str
    response: str | None
    requested_rejections: tuple[RejectedExtractionStatement, ...]
    initial_valid_statement_count: int
    corrected_valid_statement_count: int = 0
    remaining_rejections: tuple[RejectedExtractionStatement, ...] = ()
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class GroundedExtractionRun:
    """Complete inspectable result of one successful extraction call."""

    source: SourceUnit
    prompt: str
    response: str
    extraction: ExtractionResult
    correction: GroundedExtractionCorrection | None = None


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
    source: SourceUnit, generate_response: GenerateResponse
) -> GroundedExtractionRun:
    """Run extraction, correct rejected statements, and retain valid ones.

    Initial provider and response-structure errors are propagated. Individual
    invalid statements and correction failures do not discard valid original
    statements.
    """

    prompt = build_extraction_prompt(source)
    response = generate_response(prompt)

    return _build_successful_run(
        source=source, prompt=prompt, response=response, generate_response=generate_response
    )


def run_grounded_extraction_outcome(
    source: SourceUnit, generate_response: GenerateResponse
) -> GroundedExtractionOutcome:
    """Run extraction and represent unrecoverable failures as outcomes."""

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
        return _build_successful_run(
            source=source, prompt=prompt, response=response, generate_response=generate_response
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


def _build_successful_run(
    *, source: SourceUnit, prompt: str, response: str, generate_response: GenerateResponse
) -> GroundedExtractionRun:
    initial = parse_extraction_response_partially(source, response)

    if not initial.rejected_statements:
        return GroundedExtractionRun(
            source=source, prompt=prompt, response=response, extraction=initial.extraction
        )

    correction_prompt = _build_correction_prompt(
        source=source, rejected_statements=initial.rejected_statements
    )

    try:
        correction_response = generate_response(correction_prompt)
    except Exception as error:
        return GroundedExtractionRun(
            source=source,
            prompt=prompt,
            response=response,
            extraction=initial.extraction,
            correction=GroundedExtractionCorrection(
                prompt=correction_prompt,
                response=None,
                requested_rejections=initial.rejected_statements,
                initial_valid_statement_count=len(initial.extraction.statements),
                remaining_rejections=initial.rejected_statements,
                error_type=type(error).__name__,
                error_message=str(error),
            ),
        )

    try:
        corrected = parse_extraction_response_partially(source, correction_response)
    except Exception as error:
        return GroundedExtractionRun(
            source=source,
            prompt=prompt,
            response=response,
            extraction=initial.extraction,
            correction=GroundedExtractionCorrection(
                prompt=correction_prompt,
                response=correction_response,
                requested_rejections=initial.rejected_statements,
                initial_valid_statement_count=len(initial.extraction.statements),
                remaining_rejections=initial.rejected_statements,
                error_type=type(error).__name__,
                error_message=str(error),
            ),
        )

    extraction = _merge_extractions(source=source, initial=initial, corrected=corrected)

    return GroundedExtractionRun(
        source=source,
        prompt=prompt,
        response=response,
        extraction=extraction,
        correction=GroundedExtractionCorrection(
            prompt=correction_prompt,
            response=correction_response,
            requested_rejections=initial.rejected_statements,
            initial_valid_statement_count=len(initial.extraction.statements),
            corrected_valid_statement_count=len(corrected.extraction.statements),
            remaining_rejections=corrected.rejected_statements,
        ),
    )


def _merge_extractions(
    *, source: SourceUnit, initial: ParsedExtractionResponse, corrected: ParsedExtractionResponse
) -> ExtractionResult:
    statements: list[GroundedStatement] = []

    for statement in (*initial.extraction.statements, *corrected.extraction.statements):
        if statement not in statements:
            statements.append(statement)

    extraction = ExtractionResult(unit_id=source.unit_id, statements=tuple(statements))

    extraction.validate_against(source)

    return extraction


def _build_correction_prompt(
    *, source: SourceUnit, rejected_statements: tuple[RejectedExtractionStatement, ...]
) -> str:
    rejected_payload = [
        {
            "statement_index": rejection.statement_index,
            "statement": rejection.raw_statement,
            "validator_error": rejection.error_message,
        }
        for rejection in rejected_statements
    ]

    return "\n".join(
        [
            (
                "You are correcting invalid grounded RDF "
                "statements produced by another extraction agent."
            ),
            "",
            ("Return the same extraction JSON schema used by the original extraction agent."),
            "",
            f"Source unit ID: {source.unit_id}",
            f"Title: {source.title}",
            "Text:",
            source.text,
            "",
            "Rejected statements and validator errors:",
            json.dumps(rejected_payload, ensure_ascii=False, indent=2),
            "",
            "Correction rules:",
            ("- Return only corrected replacements for the rejected statements."),
            ("- Do not repeat statements that were already valid."),
            ("- Every evidence quote must occur verbatim in the declared title or text segment."),
            ("- Use the correct 1-based occurrence of each evidence quote."),
            ("- Keep a statement only when its semantic claim is supported by the source."),
            (
                "- Omit a statement when it cannot be corrected "
                "without inventing evidence or meaning."
            ),
            ("- Do not add unrelated statements or facts."),
            "",
            "Return exactly one JSON object:",
            "{",
            '  "statements": [',
            "    {",
            ('      "subject": {"value": "...", "evidence": [...]},'),
            ('      "predicate": {"value": "...", "evidence": [...]},'),
            ('      "object": {"value": "...", "evidence": [...]}'),
            "    }",
            "  ]",
            "}",
            "",
            ("Object datatype is optional and uses the same original extraction contract."),
            (
                "Do not return Markdown fences, commentary, "
                "repair actions, indices, or additional fields."
            ),
        ]
    )
