"""Tests for structured graph QA-agent responses."""

import json

import pytest

from graphragprov.qaagent import (
    QAAgentDecision,
    parse_qa_agent_response,
)


def test_query_decision_is_parsed() -> None:
    payload = json.dumps(
        {
            "status": "query",
            "sparql": ("SELECT DISTINCT ?answer WHERE { ?subject ?predicate ?answer . }"),
            "rationale": ("The graph contains a direct relation matching the question."),
            "assumptions": ["The requested answer is represented by ?answer."],
        }
    )

    decision = parse_qa_agent_response(payload)

    assert decision == QAAgentDecision(
        status="query",
        sparql=("SELECT DISTINCT ?answer WHERE { ?subject ?predicate ?answer . }"),
        rationale=("The graph contains a direct relation matching the question."),
        assumptions=("The requested answer is represented by ?answer.",),
    )

    assert decision.to_dict() == {
        "status": "query",
        "sparql": ("SELECT DISTINCT ?answer WHERE { ?subject ?predicate ?answer . }"),
        "rationale": ("The graph contains a direct relation matching the question."),
        "assumptions": ["The requested answer is represented by ?answer."],
    }


@pytest.mark.parametrize(
    "status",
    [
        "ambiguous",
        "unanswerable",
    ],
)
def test_non_query_decision_is_parsed(
    status: str,
) -> None:
    payload = json.dumps(
        {
            "status": status,
            "sparql": None,
            "rationale": ("The supplied graph does not determine one supported answer."),
            "assumptions": [],
        }
    )

    decision = parse_qa_agent_response(payload)

    assert decision.status == status
    assert decision.sparql is None


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="valid JSON",
    ):
        parse_qa_agent_response("{invalid")


def test_non_object_response_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="JSON object",
    ):
        parse_qa_agent_response("[]")


def test_missing_field_is_rejected() -> None:
    payload = json.dumps(
        {
            "status": "query",
            "sparql": "SELECT ?answer WHERE {}",
            "rationale": "A query is possible.",
        }
    )

    with pytest.raises(
        ValueError,
        match="missing fields: assumptions",
    ):
        parse_qa_agent_response(payload)


def test_unexpected_field_is_rejected() -> None:
    payload = json.dumps(
        {
            "status": "query",
            "sparql": "SELECT ?answer WHERE {}",
            "rationale": "A query is possible.",
            "assumptions": [],
            "answer": "oracle leakage",
        }
    )

    with pytest.raises(
        ValueError,
        match="unexpected fields: answer",
    ):
        parse_qa_agent_response(payload)


def test_query_decision_requires_sparql() -> None:
    payload = json.dumps(
        {
            "status": "query",
            "sparql": None,
            "rationale": "A query should have been produced.",
            "assumptions": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="requires non-empty SPARQL",
    ):
        parse_qa_agent_response(payload)


def test_non_query_decision_rejects_sparql() -> None:
    payload = json.dumps(
        {
            "status": "unanswerable",
            "sparql": "SELECT ?answer WHERE {}",
            "rationale": "The graph is insufficient.",
            "assumptions": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="must not contain SPARQL",
    ):
        parse_qa_agent_response(payload)


def test_rationale_must_not_be_empty() -> None:
    payload = json.dumps(
        {
            "status": "ambiguous",
            "sparql": None,
            "rationale": "   ",
            "assumptions": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="rationale must not be empty",
    ):
        parse_qa_agent_response(payload)


def test_assumptions_must_contain_strings() -> None:
    payload = json.dumps(
        {
            "status": "query",
            "sparql": "SELECT ?answer WHERE {}",
            "rationale": "A query is possible.",
            "assumptions": [
                42,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="assumption 0 must be a string",
    ):
        parse_qa_agent_response(payload)
