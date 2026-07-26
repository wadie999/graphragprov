"""Prompts for graph-based question answering."""

from __future__ import annotations

from collections.abc import Sequence

from graphragprov.qaagent.config import QAAgentConfiguration
from graphragprov.qaagent.observation import QAAgentObservation


def build_tuple_qa_prompt(
    *,
    question: str,
    hop_count: int,
    observation: QAAgentObservation,
    configuration: QAAgentConfiguration,
    expected_answer: str | None = None,
    decomposition: Sequence[str] = (),
) -> str:
    """Build a deterministic prompt from semantic RDF observed in GraphDB."""

    if configuration.context_mode != "tuples":
        raise ValueError("tuple QA prompt requires context_mode='tuples'")

    if not question.strip():
        raise ValueError("QA question must not be empty")

    if hop_count <= 0:
        raise ValueError("QA hop count must be positive")

    metadata = [f"Question: {question}"]

    if configuration.decomposition_visibility == "hop_count":
        metadata.append(f"Expected reasoning depth: {hop_count} hops")
    elif configuration.decomposition_visibility == "gold_decomposition":
        if not decomposition:
            raise ValueError("gold decomposition visibility requires decomposition steps")

        metadata.append("Gold decomposition:")

        metadata.extend(f"{index}. {step}" for index, step in enumerate(decomposition, start=1))

    if configuration.answer_visibility == "oracle":
        if expected_answer is None or not expected_answer.strip():
            raise ValueError("oracle answer visibility requires an expected answer")

        metadata.append(f"Expected answer for oracle query synthesis: {expected_answer}")

    tuple_lines = [triple.to_ntriple() for triple in observation.triples]

    if not tuple_lines:
        tuple_lines = ["(no semantic triples were observed)"]

    return "\n".join(
        [
            "You are a graph-only SPARQL question-answering agent.",
            "",
            "The RDF tuples below were read directly from GraphDB.",
            "They are the only factual graph context available to you.",
            "",
            *metadata,
            "",
            "Semantic RDF triples:",
            *tuple_lines,
            "",
            "Determine whether the question can be answered from this graph.",
            "",
            "When it is answerable:",
            '- Return status "query".',
            "- Generate one complete read-only SPARQL SELECT query.",
            "- The answer variable must be named ?answer.",
            "- Use exact RDF IRIs and literal values shown above.",
            "- Do not include FROM, FROM NAMED, GRAPH, SERVICE, or updates.",
            "- Do not invent triples, entities, predicates, or facts.",
            "- Do not use the named-graph IRI inside the WHERE clause.",
            "",
            "When several materially different answers remain supported:",
            '- Return status "ambiguous" and sparql null.',
            "",
            "When the required relation or entity is absent:",
            '- Return status "unanswerable" and sparql null.',
            "",
            "Return exactly one JSON object with these fields:",
            "{",
            '  "status": "query | ambiguous | unanswerable",',
            '  "sparql": "complete SELECT query or null",',
            '  "rationale": "short explicit explanation",',
            '  "assumptions": ["explicit assumption", "..."]',
            "}",
            "",
            "Do not add Markdown fences or additional fields.",
        ]
    )
