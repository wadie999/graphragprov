"""Prompts for graph-based question answering."""

from __future__ import annotations

from collections.abc import Sequence

from graphragprov.qaagent.config import QAAgentConfiguration
from graphragprov.qaagent.observation import QAAgentObservation


def build_tuple_qa_prompt(
    *,
    question: str,
    hop_count: int,
    observation: QAAgentObservation | None,
    configuration: QAAgentConfiguration,
    expected_answer: str | None = None,
    decomposition: Sequence[str] = (),
) -> str:
    """Build a deterministic multi-turn graph QA prompt."""

    if not question.strip():
        raise ValueError("QA question must not be empty")

    if hop_count <= 0:
        raise ValueError("QA hop count must be positive")

    metadata = [
        f"Question: {question}",
        f"Expected reasoning depth: {hop_count} hops",
        f"Maximum SPARQL turns: {configuration.max_turns}",
    ]

    if configuration.decomposition_visibility == "gold_decomposition":
        if not decomposition:
            raise ValueError("gold decomposition visibility requires decomposition steps")

        metadata.append("Gold decomposition:")

        metadata.extend(f"{index}. {step}" for index, step in enumerate(decomposition, start=1))

    if configuration.answer_visibility == "oracle":
        if expected_answer is None or not expected_answer.strip():
            raise ValueError("oracle answer visibility requires an expected answer")

        metadata.append("Expected answer for oracle query synthesis: " + expected_answer)

    context_lines = _build_context_lines(observation=observation, configuration=configuration)

    return "\n".join(
        [
            "You are a multi-turn graph-only SPARQL question-answering agent.",
            "",
            *metadata,
            "",
            *context_lines,
            "",
            "You may issue several SPARQL queries before producing a final answer query.",
            "",
            "Every SPARQL query you produce will be:",
            "1. restricted by the backend to the configured graph scope;",
            "2. executed against GraphDB;",
            "3. rewritten by NPCS for semiring provenance;",
            "4. executed again with provenance;",
            "5. returned to you as feedback on the next turn.",
            "",
            "Choose one query purpose:",
            "",
            '- "inspection": explore entities, predicates, types, '
            "or graph structure. The run must continue afterward.",
            "",
            '- "candidate": test a plausible reasoning path or '
            "candidate answer. The run must continue afterward so "
            "you can validate or refine it.",
            "",
            '- "final": issue the query that you consider sufficient '
            "to answer the question. A successful provenance-decoded "
            "result may terminate the run.",
            "",
            "SPARQL requirements:",
            "- Return one complete read-only SPARQL SELECT query.",
            "- Inspection and candidate queries may expose any meaningful variables.",
            "- A final query must expose the answer as ?answer.",
            "- Do not include FROM, FROM NAMED, GRAPH, SERVICE, or update operations.",
            "- Dataset scope is controlled exclusively by the backend.",
            "- Do not invent entities, predicates, triples, or facts.",
            "- Generic inspection queries are allowed when exact IRIs are not yet known.",
            "",
            "Do not declare the question unanswerable merely because an early query failed.",
            "",
            "Return status ambiguous or unanswerable only when you are "
            "ready to terminate the run without another query.",
            "",
            "Return exactly one JSON object with these fields:",
            "{",
            '  "status": "query | ambiguous | unanswerable",',
            '  "purpose": "inspection | candidate | final | null",',
            '  "sparql": "complete SELECT query or null",',
            '  "rationale": "short explicit explanation",',
            '  "assumptions": ["explicit assumption", "..."]',
            "}",
            "",
            "Rules for null values:",
            '- When status is "query", purpose and sparql must not be null.',
            '- When status is "ambiguous" or "unanswerable", purpose and sparql must be null.',
            "",
            "Do not add Markdown fences or additional fields.",
        ]
    )


def _build_context_lines(
    *, observation: QAAgentObservation | None, configuration: QAAgentConfiguration
) -> list[str]:
    if configuration.context_mode == "tuples":
        if observation is None:
            raise ValueError("tuple context requires a semantic graph observation")

        tuple_lines = [triple.to_ntriple() for triple in observation.triples]

        if not tuple_lines:
            tuple_lines = ["(no semantic triples were observed)"]

        return [
            "ORACLE TUPLE CONTEXT",
            "",
            "The RDF tuples below were extracted from the benchmark's gold supporting paragraphs.",
            "",
            "This oracle context is provided to evaluate whether the "
            "graph extractor constructed enough semantic information.",
            "",
            "The tuples may still contain extraction or identity errors.",
            "",
            "Semantic RDF triples:",
            *tuple_lines,
        ]

    if configuration.context_mode == "graph_agent":
        if observation is not None:
            raise ValueError("graph-agent context must not receive tuple observations")

        return [
            "NO INITIAL TUPLES",
            "",
            "No extracted tuples are included in this prompt.",
            "",
            "Discover the relevant graph structure through inspection "
            "and candidate SPARQL queries.",
        ]

    raise NotImplementedError("hybrid prompt context is not implemented")
