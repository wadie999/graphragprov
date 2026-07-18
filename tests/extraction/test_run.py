import json

from graphragprov.domain import SourceUnit
from graphragprov.extraction.run import (
    GroundedExtractionFailure,
    GroundedExtractionRun,
    run_grounded_extraction,
    run_grounded_extraction_outcome,
)

SOURCE = SourceUnit(
    unit_id="u_system_owned",
    title="Albert Einstein",
    text="He was born in Ulm.",
)

MODEL_RESPONSE = json.dumps(
    {
        "statements": [
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {
                            "segment": "title",
                            "quote": "Albert Einstein",
                            "occurrence": 1,
                        },
                        {
                            "segment": "text",
                            "quote": "He",
                            "occurrence": 1,
                        },
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "born in",
                            "occurrence": 1,
                        }
                    ],
                },
                "object": {
                    "value": "Ulm",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "Ulm",
                            "occurrence": 1,
                        }
                    ],
                },
            }
        ]
    }
)

INVALID_EVIDENCE_RESPONSE = MODEL_RESPONSE.replace(
    '"quote": "Ulm"',
    '"quote": "1955"',
)


def test_runs_one_grounded_extraction() -> None:
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)
        return MODEL_RESPONSE

    run = run_grounded_extraction(
        SOURCE,
        generate_response=fake_model,
    )

    assert received_prompts == [run.prompt]
    assert SOURCE.title in run.prompt
    assert SOURCE.text in run.prompt
    assert SOURCE.unit_id not in run.prompt

    assert run.source == SOURCE
    assert run.response == MODEL_RESPONSE
    assert run.extraction.unit_id == SOURCE.unit_id

    statement = run.extraction.statements[0]

    assert statement.subject.value == "Albert Einstein"
    assert statement.predicate.value == "bornIn"
    assert statement.object.value == "Ulm"
    assert statement.object.evidence[0].start == 15
    assert statement.object.evidence[0].end == 18


def test_returns_successful_extraction_outcome() -> None:
    outcome = run_grounded_extraction_outcome(
        SOURCE,
        generate_response=lambda _: MODEL_RESPONSE,
    )

    assert isinstance(
        outcome,
        GroundedExtractionRun,
    )
    assert outcome.source == SOURCE
    assert outcome.response == MODEL_RESPONSE
    assert outcome.extraction.unit_id == SOURCE.unit_id


def test_preserves_provider_failure_as_outcome() -> None:
    def failing_model(_: str) -> str:
        raise RuntimeError("provider unavailable")

    outcome = run_grounded_extraction_outcome(
        SOURCE,
        generate_response=failing_model,
    )

    assert isinstance(
        outcome,
        GroundedExtractionFailure,
    )
    assert outcome.source == SOURCE
    assert SOURCE.title in outcome.prompt
    assert SOURCE.text in outcome.prompt
    assert outcome.response is None
    assert outcome.stage == "provider"
    assert outcome.error_type == "RuntimeError"
    assert outcome.error_message == "provider unavailable"


def test_preserves_invalid_raw_response_and_drops_invalid_statement() -> None:
    outcome = run_grounded_extraction_outcome(
        SOURCE,
        generate_response=lambda _: INVALID_EVIDENCE_RESPONSE,
    )

    assert isinstance(
        outcome,
        GroundedExtractionRun,
    )

    assert outcome.response == INVALID_EVIDENCE_RESPONSE
    assert outcome.extraction.statements == ()

    assert outcome.correction is not None
    assert outcome.correction.response == INVALID_EVIDENCE_RESPONSE
    assert len(outcome.correction.requested_rejections) == 1
    assert len(outcome.correction.remaining_rejections) == 1

    rejection = outcome.correction.remaining_rejections[0]

    assert rejection.statement_index == 0
    assert "quote '1955' does not occur" in rejection.error_message
