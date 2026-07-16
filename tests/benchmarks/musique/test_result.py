import json

import pytest

from graphragprov.benchmarks.musique.result import (
    MusiqueCaseResult,
)


def test_completed_result_is_json_serializable() -> None:
    result = MusiqueCaseResult(
        status="completed",
        case_id="2hop__example",
        hop_count=2,
        question="Who designed the building?",
        expected_answer="Frank Lloyd Wright",
        answer_aliases=("F. L. Wright",),
        source_unit_ids=(
            "u_first",
            "u_second",
        ),
        gold_support_indices=(1, 7),
        extraction_failures=(
            {
                "unit_id": "u_second",
                "stage": "response_validation",
                "message": "invalid quote",
            },
        ),
        materialization={
            "source_count": 1,
            "statement_count": 5,
        },
        sparql=("SELECT ?answer WHERE { ?building ?p ?answer }"),
        query_execution={
            "original_result": {
                "results": {
                    "bindings": [],
                }
            }
        },
        provenance_polynomial=("⊕((⊗token,))"),
        decoded_provenance={
            "derivations": [
                {
                    "occurrences": [],
                }
            ]
        },
    )

    payload = json.loads(result.to_json())

    assert payload == result.to_dict()
    assert payload["status"] == "completed"
    assert payload["format"] == ("musique-case-result-v1")
    assert payload["extraction_failures"] == [
        {
            "unit_id": "u_second",
            "stage": "response_validation",
            "message": "invalid quote",
        }
    ]


def test_completed_result_requires_full_pipeline() -> None:
    with pytest.raises(
        ValueError,
        match="missing:",
    ):
        MusiqueCaseResult(
            status="completed",
            case_id="2hop__example",
            hop_count=2,
            question="Question",
            expected_answer="Answer",
            answer_aliases=(),
            source_unit_ids=("u_first",),
            gold_support_indices=(0,),
        )


def test_failed_result_requires_error_message() -> None:
    with pytest.raises(
        ValueError,
        match="must contain an error message",
    ):
        MusiqueCaseResult(
            status="query_failed",
            case_id="2hop__example",
            hop_count=2,
            question="Question",
            expected_answer="Answer",
            answer_aliases=(),
            source_unit_ids=("u_first",),
            gold_support_indices=(0,),
        )


def test_failed_result_preserves_completed_stages() -> None:
    result = MusiqueCaseResult(
        status="provenance_decoding_failed",
        case_id="3hop__example",
        hop_count=3,
        question="Question",
        expected_answer="Answer",
        answer_aliases=(),
        source_unit_ids=("u_first",),
        gold_support_indices=(0,),
        materialization={
            "source_count": 1,
            "statement_count": 4,
        },
        sparql="SELECT ?answer WHERE {}",
        query_execution={
            "original_result": {},
            "rewritten_result": {},
        },
        provenance_polynomial=("invalid polynomial"),
        error_type="ValueError",
        error_message="invalid provenance polynomial",
    )

    payload = result.to_dict()

    assert payload["status"] == ("provenance_decoding_failed")
    assert payload["sparql"] == ("SELECT ?answer WHERE {}")
    assert payload["provenance_polynomial"] == ("invalid polynomial")
    assert payload["decoded_provenance"] is None
