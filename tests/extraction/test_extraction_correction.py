"""Tests for statement-level extraction correction."""

from __future__ import annotations

import json

from graphragprov.domain import SourceUnit
from graphragprov.extraction.run import (
    run_grounded_extraction,
)
from graphragprov.hashing import source_unit_id

TITLE = "Lloyd Dane"
TEXT = "Lloyd Dane was a driver from Eldon, Missouri."

SOURCE = SourceUnit(
    unit_id=source_unit_id(
        title=TITLE,
        text=TEXT,
    ),
    title=TITLE,
    text=TEXT,
)


def test_invalid_statement_is_corrected_without_losing_valid_statement() -> None:
    prompts: list[str] = []

    responses = iter(
        [
            json.dumps(
                {
                    "statements": [
                        _valid_driver_statement(),
                        _invalid_birthplace_statement(),
                    ]
                }
            ),
            json.dumps(
                {
                    "statements": [
                        _corrected_birthplace_statement(),
                    ]
                }
            ),
        ]
    )

    def generate_response(
        prompt: str,
    ) -> str:
        prompts.append(prompt)
        return next(responses)

    run = run_grounded_extraction(
        SOURCE,
        generate_response,
    )

    assert len(prompts) == 2
    assert len(run.extraction.statements) == 2
    assert run.correction is not None

    assert tuple(
        (
            statement.subject.value,
            statement.predicate.value,
            statement.object.value,
        )
        for statement in run.extraction.statements
    ) == (
        (
            "Lloyd Dane",
            "instanceOf",
            "driver",
        ),
        (
            "Lloyd Dane",
            "bornIn",
            "Eldon, Missouri",
        ),
    )

    assert run.correction.requested_rejections[0].statement_index == 1

    assert run.correction.remaining_rejections == ()


def test_invalid_correction_is_dropped_but_valid_original_survives() -> None:
    responses = iter(
        [
            json.dumps(
                {
                    "statements": [
                        _valid_driver_statement(),
                        _invalid_birthplace_statement(),
                    ]
                }
            ),
            json.dumps(
                {
                    "statements": [
                        _invalid_birthplace_statement(),
                    ]
                }
            ),
        ]
    )

    run = run_grounded_extraction(
        SOURCE,
        lambda prompt: next(responses),
    )

    assert len(run.extraction.statements) == 1

    statement = run.extraction.statements[0]

    assert statement.predicate.value == "instanceOf"
    assert run.correction is not None
    assert len(run.correction.remaining_rejections) == 1


def test_correction_provider_failure_does_not_discard_valid_original() -> None:
    call_count = 0

    def generate_response(
        prompt: str,
    ) -> str:
        nonlocal call_count
        del prompt

        call_count += 1

        if call_count == 1:
            return json.dumps(
                {
                    "statements": [
                        _valid_driver_statement(),
                        _invalid_birthplace_statement(),
                    ]
                }
            )

        raise RuntimeError("correction provider unavailable")

    run = run_grounded_extraction(
        SOURCE,
        generate_response,
    )

    assert len(run.extraction.statements) == 1
    assert run.correction is not None
    assert run.correction.error_type == "RuntimeError"
    assert run.correction.error_message == "correction provider unavailable"


def _valid_driver_statement() -> dict[str, object]:
    return {
        "subject": {
            "value": "Lloyd Dane",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "Lloyd Dane",
                    "occurrence": 1,
                }
            ],
        },
        "predicate": {
            "value": "instanceOf",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "was",
                    "occurrence": 1,
                }
            ],
        },
        "object": {
            "value": "driver",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "driver",
                    "occurrence": 1,
                }
            ],
        },
    }


def _invalid_birthplace_statement() -> dict[str, object]:
    return {
        "subject": {
            "value": "Lloyd Dane",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "Lloyd Dane",
                    "occurrence": 1,
                }
            ],
        },
        "predicate": {
            "value": "bornIn",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "born",
                    "occurrence": 1,
                }
            ],
        },
        "object": {
            "value": "Eldon, Missouri",
            "evidence": [
                {
                    "segment": "text",
                    "quote": "Eldon, Missouri",
                    "occurrence": 1,
                }
            ],
        },
    }


def _corrected_birthplace_statement() -> dict[str, object]:
    statement = _invalid_birthplace_statement()

    predicate = statement["predicate"]
    assert isinstance(predicate, dict)

    predicate["evidence"] = [
        {
            "segment": "text",
            "quote": "from",
            "occurrence": 1,
        }
    ]

    return statement
