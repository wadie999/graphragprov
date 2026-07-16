"""Tests for graph QA-agent execution traces."""

import json
from typing import cast

import pytest

from graphragprov.provenance import DecodedProvenance
from graphragprov.qaagent import (
    QAAnswerProvenance,
    QAQueryAttempt,
)
from graphragprov.query import ProvenanceQueryExecution


class _DecodedProvenanceStub:
    def to_dict(self) -> dict[str, object]:
        return {
            "derivations": [
                {
                    "occurrences": [
                        {
                            "token": "token-1",
                        }
                    ]
                }
            ]
        }


def test_decoded_query_attempt_is_json_serializable() -> None:
    decoded = cast(
        DecodedProvenance,
        _DecodedProvenanceStub(),
    )

    answer_provenance = QAAnswerProvenance(
        binding={
            "answer": {
                "type": "uri",
                "value": "urn:answer",
            }
        },
        polynomial="⊕((⊗token-1,))",
        decoded=decoded,
    )

    attempt = QAQueryAttempt(
        turn_index=1,
        purpose="final",
        semantic_sparql=("SELECT ?answer WHERE { ?subject ?predicate ?answer }"),
        scoped_sparql=("SELECT ?answer FROM <urn:graph> WHERE { ?subject ?predicate ?answer }"),
        execution=_execution(),
        answer_provenances=(answer_provenance,),
        provenance_status="decoded",
    )

    payload = attempt.to_dict()

    assert (
        json.loads(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        == payload
    )

    assert payload["turn_index"] == 1
    assert payload["purpose"] == "final"
    assert payload["provenance_status"] == "decoded"
    assert payload["answer_provenances"] == [answer_provenance.to_dict()]


def test_answer_provenance_requires_binding() -> None:
    decoded = cast(
        DecodedProvenance,
        _DecodedProvenanceStub(),
    )

    with pytest.raises(
        ValueError,
        match="binding must not be empty",
    ):
        QAAnswerProvenance(
            binding={},
            polynomial="⊕((⊗token-1,))",
            decoded=decoded,
        )


def test_answer_provenance_requires_polynomial() -> None:
    decoded = cast(
        DecodedProvenance,
        _DecodedProvenanceStub(),
    )

    with pytest.raises(
        ValueError,
        match="polynomial must not be empty",
    ):
        QAAnswerProvenance(
            binding={
                "answer": {
                    "value": "urn:answer",
                }
            },
            polynomial="   ",
            decoded=decoded,
        )


def test_decoded_status_requires_answer_provenance() -> None:
    with pytest.raises(
        ValueError,
        match="requires answer provenances",
    ):
        QAQueryAttempt(
            turn_index=1,
            purpose="final",
            semantic_sparql="SELECT ?answer WHERE {}",
            scoped_sparql="SELECT ?answer FROM <urn:graph> WHERE {}",
            execution=_execution(),
            provenance_status="decoded",
        )


def test_answer_provenance_requires_decoded_status() -> None:
    decoded = cast(
        DecodedProvenance,
        _DecodedProvenanceStub(),
    )

    answer_provenance = QAAnswerProvenance(
        binding={
            "answer": {
                "value": "urn:answer",
            }
        },
        polynomial="⊕((⊗token-1,))",
        decoded=decoded,
    )

    with pytest.raises(
        ValueError,
        match="require decoded provenance status",
    ):
        QAQueryAttempt(
            turn_index=1,
            purpose="candidate",
            semantic_sparql="SELECT ?answer WHERE {}",
            scoped_sparql="SELECT ?answer FROM <urn:graph> WHERE {}",
            execution=_execution(),
            answer_provenances=(answer_provenance,),
            provenance_status="not_requested",
        )


def test_no_answers_status_requires_execution() -> None:
    with pytest.raises(
        ValueError,
        match="requires query execution",
    ):
        QAQueryAttempt(
            turn_index=1,
            purpose="inspection",
            semantic_sparql="SELECT ?answer WHERE {}",
            scoped_sparql="SELECT ?answer FROM <urn:graph> WHERE {}",
            provenance_status="no_answers",
        )


def test_failed_status_requires_error_message() -> None:
    with pytest.raises(
        ValueError,
        match="requires an error message",
    ):
        QAQueryAttempt(
            turn_index=1,
            purpose="final",
            semantic_sparql="SELECT ?answer WHERE {}",
            scoped_sparql="SELECT ?answer FROM <urn:graph> WHERE {}",
            provenance_status="failed",
        )


def test_turn_index_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="turn index must be positive",
    ):
        QAQueryAttempt(
            turn_index=0,
            purpose="inspection",
            semantic_sparql="SELECT ?answer WHERE {}",
            scoped_sparql="SELECT ?answer FROM <urn:graph> WHERE {}",
        )


def _execution() -> ProvenanceQueryExecution:
    return ProvenanceQueryExecution(
        original_query="SELECT ?answer FROM <urn:graph> WHERE {}",
        original_result={
            "results": {
                "bindings": [
                    {
                        "answer": {
                            "type": "uri",
                            "value": "urn:answer",
                        }
                    }
                ]
            }
        },
        rewritten_query=("SELECT ?answer ?finalprovennacevariable FROM <urn:graph> WHERE {}"),
        rewritten_result={
            "results": {
                "bindings": [
                    {
                        "answer": {
                            "type": "uri",
                            "value": "urn:answer",
                        },
                        "finalprovennacevariable": {
                            "type": "literal",
                            "value": "⊕((⊗token-1,))",
                        },
                    }
                ]
            }
        },
    )
