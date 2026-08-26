"""Integration-style tests for one complete H0 case runner."""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import Mock

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueHop,
    MusiqueParagraph,
    collect_musique_source_units,
)
from graphragprov.experiments.multihop_fidelity.config import (
    ArtifactOrigin,
    ExperimentConfig,
    QueryScope,
)
from graphragprov.experiments.multihop_fidelity.runner import (
    H0CaseFailure,
    H0CaseResult,
    run_h0_case,
)
from graphragprov.experiments.multihop_fidelity.telemetry import ExperimentTelemetryRecorder
from graphragprov.extraction import parse_extraction_response
from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.query import PROVENANCE_VARIABLE
from graphragprov.rdf.provenance import occurrence_token
from graphragprov.rdf.terms import entity_iri, predicate_iri, unit_graph_iri


def _case() -> MusiqueCase:
    return MusiqueCase(
        case_id="2hop__runner_test",
        question=("Where was the performer of Album Alpha born?"),
        answer="City Gamma",
        answer_aliases=(),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(index=0, title="Distractor", text=("This paragraph is irrelevant.")),
            MusiqueParagraph(
                index=2, title="Artist Beta", text=("Artist Beta was born in City Gamma.")
            ),
            MusiqueParagraph(
                index=7, title="Album Alpha", text=("Album Alpha was performed by Artist Beta.")
            ),
        ),
        decomposition=(
            MusiqueHop(
                hop_id=0,
                question=("Album Alpha >> performer"),
                answer="Artist Beta",
                paragraph_support_index=7,
            ),
            MusiqueHop(
                hop_id=1,
                question=("#1 >> place of birth"),
                answer="City Gamma",
                paragraph_support_index=2,
            ),
        ),
        gold_support_indices=(7, 2),
    )


def _configuration(*, max_query_attempts: int = 3) -> ExperimentConfig:
    return ExperimentConfig(
        graph_origin=(ArtifactOrigin.REFERENCE),
        query_origin=(ArtifactOrigin.REFERENCE),
        query_scope=(QueryScope.SUPPORT),
        max_source_attempts=2,
        max_query_attempts=(max_query_attempts),
    )


def _grounded_value(value: str, *, segment: str, quote: str) -> dict[str, object]:
    return {"value": value, "evidence": [{"segment": segment, "quote": quote, "occurrence": 1}]}


def _album_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Album Alpha", segment="title", quote="Album Alpha"),
                    "predicate": _grounded_value("performer", segment="text", quote="performed by"),
                    "object": _grounded_value("Artist Beta", segment="text", quote="Artist Beta"),
                }
            ]
        }
    )


def _artist_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Artist Beta", segment="title", quote="Artist Beta"),
                    "predicate": _grounded_value("placeOfBirth", segment="text", quote="born in"),
                    "object": _grounded_value("City Gamma", segment="text", quote="City Gamma"),
                }
            ]
        }
    )


def _graph_generator(prompt: str) -> str:
    if "Album Alpha was performed by Artist Beta." in prompt:
        return _album_response()

    if "Artist Beta was born in City Gamma." in prompt:
        return _artist_response()

    raise AssertionError(f"unexpected graph prompt:\n{prompt}")


def _semantic_triples() -> tuple[str, str]:
    performer = (
        f"{entity_iri('Album Alpha').n3()} "
        f"{predicate_iri('performer').n3()} "
        f"{entity_iri('Artist Beta').n3()} ."
    )

    birth = (
        f"{entity_iri('Artist Beta').n3()} "
        f"{predicate_iri('placeOfBirth').n3()} "
        f"{entity_iri('City Gamma').n3()} ."
    )

    return performer, birth


def _valid_query_response() -> str:
    performer, birth = _semantic_triples()

    semantic_sparql = (
        "SELECT ?answer WHERE {\n"
        f"  {entity_iri('Album Alpha').n3()} "
        f"{predicate_iri('performer').n3()} "
        "?performer .\n"
        "  ?performer "
        f"{predicate_iri('placeOfBirth').n3()} "
        "?answer .\n"
        "}"
    )

    return json.dumps({"matched_triples": [performer, birth], "sparql": semantic_sparql})


def _observation_result(case: MusiqueCase) -> dict[str, object]:
    sources = collect_musique_source_units((case,))

    by_title = {source.title: source for source in sources}

    return {
        "head": {"vars": ["graph", "subject", "predicate", "object"]},
        "results": {
            "bindings": [
                {
                    "graph": {
                        "type": "uri",
                        "value": str(unit_graph_iri(by_title["Album Alpha"].unit_id)),
                    },
                    "subject": {"type": "uri", "value": str(entity_iri("Album Alpha"))},
                    "predicate": {"type": "uri", "value": str(predicate_iri("performer"))},
                    "object": {"type": "uri", "value": str(entity_iri("Artist Beta"))},
                },
                {
                    "graph": {
                        "type": "uri",
                        "value": str(unit_graph_iri(by_title["Artist Beta"].unit_id)),
                    },
                    "subject": {"type": "uri", "value": str(entity_iri("Artist Beta"))},
                    "predicate": {"type": "uri", "value": str(predicate_iri("placeOfBirth"))},
                    "object": {"type": "uri", "value": str(entity_iri("City Gamma"))},
                },
            ]
        },
    }


def _answer_result(value: str) -> dict[str, object]:
    return {
        "head": {"vars": ["answer"]},
        "results": {"bindings": [{"answer": {"type": "uri", "value": str(entity_iri(value))}}]},
    }


def _provenance_polynomial(case: MusiqueCase) -> str:
    sources = collect_musique_source_units((case,))

    by_title = {source.title: source for source in sources}

    album_source = by_title["Album Alpha"]

    artist_source = by_title["Artist Beta"]

    album_extraction = parse_extraction_response(album_source, _album_response())

    artist_extraction = parse_extraction_response(artist_source, _artist_response())

    album_token = occurrence_token(
        unit_id=album_source.unit_id, statement=(album_extraction.statements[0])
    )

    artist_token = occurrence_token(
        unit_id=artist_source.unit_id, statement=(artist_extraction.statements[0])
    )

    tokens = sorted((album_token, artist_token))

    return "⊕((⊗" + ",".join(tokens) + ",))"


def _rewritten_result(case: MusiqueCase, answer_value: str) -> dict[str, object]:
    return {
        "head": {"vars": ["answer", PROVENANCE_VARIABLE]},
        "results": {
            "bindings": [
                {
                    "answer": {"type": "uri", "value": str(entity_iri(answer_value))},
                    PROVENANCE_VARIABLE: {
                        "type": "literal",
                        "value": (_provenance_polynomial(case)),
                    },
                }
            ]
        },
    }


def _clients_for_success(case: MusiqueCase, *, semantic_answers: list[str]) -> tuple[Mock, Mock]:
    if not semantic_answers:
        raise ValueError("semantic_answers must not be empty")

    graphdb = Mock(spec=GraphDBClient)
    npcs = Mock(spec=NPCSClient)

    npcs.rewrite.return_value = "REWRITTEN PROVENANCE QUERY"

    semantic_calls = 0
    last_semantic_answer: str | None = None

    def query(sparql: str) -> dict[str, object]:
        nonlocal semantic_calls
        nonlocal last_semantic_answer

        if "SELECT DISTINCT ?graph ?subject ?predicate ?object" in sparql:
            return _observation_result(case)

        if sparql == "REWRITTEN PROVENANCE QUERY":
            answer = (
                last_semantic_answer if last_semantic_answer is not None else semantic_answers[0]
            )
            return _rewritten_result(case, answer)

        if "?answer" in sparql:
            answer_index = min(semantic_calls, len(semantic_answers) - 1)
            answer = semantic_answers[answer_index]
            semantic_calls += 1
            last_semantic_answer = answer
            return _answer_result(answer)

        raise AssertionError(f"unexpected GraphDB query:\n{sparql}")

    graphdb.query.side_effect = query

    return graphdb, npcs


def test_h0_runner_executes_complete_answer_to_source_provenance_path() -> None:
    case = _case()

    sources = collect_musique_source_units((case,))

    graphdb, npcs = _clients_for_success(case, semantic_answers=["City Gamma"])

    query_calls = 0

    def query_generate(prompt: str) -> str:
        nonlocal query_calls

        query_calls += 1

        assert case.question in prompt

        return _valid_query_response()

    telemetry = ExperimentTelemetryRecorder()

    outcome = run_h0_case(
        case=case,
        sources=sources,
        configuration=_configuration(),
        graph_generate_response=(_graph_generator),
        query_generate_response=(query_generate),
        graphdb=cast(GraphDBClient, graphdb),
        npcs=cast(NPCSClient, npcs),
        telemetry=telemetry,
    )

    assert isinstance(outcome, H0CaseResult)

    assert outcome.case_id == (case.case_id)

    assert outcome.hop_count == 2

    assert outcome.extraction_measurements.statement_occurrence_count == 2

    assert outcome.graph_measurements.semantic_triple_count == 2

    assert outcome.graph_measurements.entity_node_count == 3

    assert len(outcome.query_attempts) == 1

    final_query = outcome.query_attempts[0]

    assert final_query.observed_answers == ("City Gamma",)

    # Scientific evaluation is deliberately absent from collection.
    assert final_query.answer_correct is None
    assert final_query.gold_support_covered is None

    assert outcome.final_provenance.provenance_status == "decoded"

    derivations = outcome.final_provenance.answer_provenances[0].decoded.derivations

    assert len(derivations) == 1

    occurrence_sources = {occurrence.source.title for occurrence in derivations[0].occurrences}

    assert occurrence_sources == {"Album Alpha", "Artist Beta"}

    assert query_calls == 1

    assert graphdb.update.call_count == 2
    assert graphdb.upload_trig_star.call_count == 2

    stage_names = {stage.stage for stage in outcome.telemetry.stages}

    assert {
        "graph.reference.extraction",
        "graph.reference.measurements",
        "graph.clear_support",
        "graph.materialization",
        "graph.observation",
        "graph.frozen.measurements",
        "query.reference.generation",
        "graphdb.semantic",
        "provenance.execution",
    } <= stage_names


def test_h0_runner_collects_non_gold_answer_without_retry() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))

    graphdb, npcs = _clients_for_success(case, semantic_answers=["Wrong City", "City Gamma"])

    query_calls = 0

    def query_generate(prompt: str) -> str:
        nonlocal query_calls
        query_calls += 1

        assert case.question in prompt
        return _valid_query_response()

    outcome = run_h0_case(
        case=case,
        sources=sources,
        configuration=_configuration(),
        graph_generate_response=_graph_generator,
        query_generate_response=query_generate,
        graphdb=cast(GraphDBClient, graphdb),
        npcs=cast(NPCSClient, npcs),
        telemetry=ExperimentTelemetryRecorder(),
    )

    assert isinstance(outcome, H0CaseResult)

    # One mechanically valid query is collected exactly once.
    assert query_calls == 1
    assert len(outcome.query_attempts) == 1

    attempt = outcome.query_attempts[0]

    # The raw observation survives exactly as produced.
    assert attempt.observed_answers == ("Wrong City",)
    assert attempt.original_result is not None

    # No benchmark-equivalence judgment is made during collection.
    assert attempt.answer_correct is None
    assert attempt.gold_support_covered is None
    assert attempt.feedback is None

    # Provenance is still attempted even though the observed answer
    # differs from the benchmark gold string.
    assert attempt.provenance is not None
    assert outcome.final_provenance.provenance_status == "decoded"


def test_h0_runner_retries_only_mechanically_invalid_query_response() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))

    graphdb, npcs = _clients_for_success(case, semantic_answers=["City Gamma"])

    prompts: list[str] = []

    def query_generate(prompt: str) -> str:
        prompts.append(prompt)

        if len(prompts) == 1:
            return "not valid JSON"

        assert "query response must be valid JSON" in prompt
        return _valid_query_response()

    outcome = run_h0_case(
        case=case,
        sources=sources,
        configuration=_configuration(),
        graph_generate_response=_graph_generator,
        query_generate_response=query_generate,
        graphdb=cast(GraphDBClient, graphdb),
        npcs=cast(NPCSClient, npcs),
        telemetry=ExperimentTelemetryRecorder(),
    )

    assert isinstance(outcome, H0CaseResult)

    assert len(prompts) == 2
    assert len(outcome.query_attempts) == 2

    first = outcome.query_attempts[0]

    assert first.validation_error is not None
    assert "valid JSON" in first.validation_error
    assert first.plan is None
    assert first.original_result is None
    assert first.provenance is None

    second = outcome.query_attempts[1]

    assert second.observed_answers == ("City Gamma",)
    assert second.answer_correct is None
    assert second.gold_support_covered is None
    assert second.provenance is not None
    assert second.execution_sparql is not None

    semantic_queries = [
        call.args[0]
        for call in graphdb.query.call_args_list
        if call.args and call.args[0] == second.execution_sparql
    ]

    # The malformed first response never reached GraphDB.
    #
    # The valid semantic query is executed once by the H0 collector and
    # once again by the provenance executor before NPCS rewriting.
    assert len(semantic_queries) == 2


def test_h0_runner_returns_structured_graph_extraction_failure() -> None:
    case = _case()

    sources = collect_musique_source_units((case,))

    graphdb = Mock(spec=GraphDBClient)

    npcs = Mock(spec=NPCSClient)

    def invalid_graph_generate(prompt: str) -> str:
        assert "Album Alpha was performed by Artist Beta." in prompt

        return "not valid JSON"

    outcome = run_h0_case(
        case=case,
        sources=sources,
        configuration=_configuration(),
        graph_generate_response=(invalid_graph_generate),
        query_generate_response=(lambda prompt: _valid_query_response()),
        graphdb=cast(GraphDBClient, graphdb),
        npcs=cast(NPCSClient, npcs),
        telemetry=(ExperimentTelemetryRecorder()),
    )

    assert isinstance(outcome, H0CaseFailure)

    assert outcome.stage == ("graph_extraction")

    assert outcome.error_type == ("ValueError")

    assert "invalid extraction JSON" in outcome.error_message

    assert graphdb.upload_trig_star.call_count == 0

    assert graphdb.query.call_count == 0

    assert "graph_extraction" in outcome.partial
