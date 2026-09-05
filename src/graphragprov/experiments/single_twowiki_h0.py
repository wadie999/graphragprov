"""Run one complete 2Wiki graph/query/provenance smoke case."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.benchmarks.twowiki.reader import load_case
from graphragprov.benchmarks.twowiki.selection import supporting_paragraphs
from graphragprov.config import twowiki_dataset_path
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.graph import ReferenceGraphExtractionFailure
from graphragprov.experiments.multihop_fidelity.query import (
    ReferenceQueryValidationError,
    answer_terms,
    compile_reference_query,
    display_answer_term,
    validation_feedback,
)
from graphragprov.experiments.multihop_fidelity.twowiki_graph import (
    construct_twowiki_reference_extractions,
)
from graphragprov.experiments.multihop_fidelity.twowiki_query import (
    TWOWIKI_QUERY_PROMPT_VERSION,
    answer_matches_twowiki_case,
    generate_twowiki_reference_query,
    twowiki_execution_feedback,
)
from graphragprov.graphdb import GraphDBClient, materialize_grounded_extractions
from graphragprov.npcs import SparqlProvClient
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
    deepseek_generator,
)
from graphragprov.qaagent import QAQueryAttempt, execute_qa_query_attempt, observe_semantic_triples
from graphragprov.rdf.terms import unit_graph_iri

DEFAULT_CASE_ID = "586507fa0bd911eba7f7acde48001122"


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run one complete 2Wiki graph, SPARQL, GraphDB and provenance smoke case.")
    )

    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)

    parser.add_argument("--dataset-path", type=Path)

    parser.add_argument(
        "--query-scope",
        choices=(QueryScope.SUPPORT.value, QueryScope.REPOSITORY.value),
        default=QueryScope.SUPPORT.value,
    )

    parser.add_argument("--artifacts", type=Path, default=Path("runs/twowiki_h0"))

    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)

    parser.add_argument("--max-tokens", type=int, default=16_384)

    parser.add_argument("--max-source-attempts", type=int, default=3)

    parser.add_argument("--max-query-attempts", type=int, default=5)

    parser.add_argument(
        "--llm-timeout-seconds", type=float, default=DEFAULT_DEEPSEEK_TIMEOUT_SECONDS
    )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    dataset_path = (
        args.dataset_path if isinstance(args.dataset_path, Path) else twowiki_dataset_path()
    )

    case = load_case(dataset_path, str(args.case_id))

    if case.answer is None:
        raise SystemExit("selected 2Wiki case does not contain a gold answer")

    query_scope = QueryScope(str(args.query_scope))

    root = args.artifacts / case.case_id / query_scope.value

    result_path = root / "result.json"

    if result_path.is_file():
        raise SystemExit(f"result already exists: {result_path}")

    root.mkdir(parents=True, exist_ok=True)

    graphdb = GraphDBClient.from_environment()
    npcs = SparqlProvClient.from_environment()

    _preflight(graphdb=graphdb, npcs=npcs)

    print()
    print("2Wiki executable provenance smoke run")
    print(f"  case:      {case.case_id}")
    print(f"  question:  {case.question}")
    print(f"  expected:  {case.answer}")
    print(f"  scope:     {query_scope.value}")
    print(f"  model:     {args.model}")
    print(f"  query prompt: {TWOWIKI_QUERY_PROMPT_VERSION}")
    print()

    all_sources = collect_twowiki_source_units((case,))

    source_by_id = {source.unit_id: source for source in all_sources}

    support_paragraphs = supporting_paragraphs(case)

    support_sources = tuple(source_by_id[paragraph.unit_id] for paragraph in support_paragraphs)

    support_source_ids = tuple(source.unit_id for source in support_sources)

    registry = SourceRegistry(all_sources)

    generate = deepseek_generator(
        api_key=api_key,
        model=str(args.model),
        max_tokens=int(args.max_tokens),
        timeout_seconds=float(args.llm_timeout_seconds),
    )

    print("[1] Constructing grounded 2Wiki reference graph...")

    graph_outcome = construct_twowiki_reference_extractions(
        case=case,
        sources=all_sources,
        generate_response=generate,
        max_attempts=int(args.max_source_attempts),
    )

    if isinstance(graph_outcome, ReferenceGraphExtractionFailure):
        raise SystemExit(
            "graph extraction failed: "
            f"{graph_outcome.failure.error_type}: "
            f"{graph_outcome.failure.error_message}"
        )

    for item in graph_outcome.items:
        for statement in item.run.extraction.statements:
            print(
                "    "
                f"{statement.subject.value} "
                f"--{statement.predicate.value}--> "
                f"{statement.object.value}"
            )

    print()
    print("[2] Replacing current support graphs in GraphDB...")

    for source_id in support_source_ids:
        graphdb.update(f"CLEAR SILENT GRAPH {unit_graph_iri(source_id).n3()}")

    materialization = materialize_grounded_extractions(graph_outcome.runs, graphdb=graphdb)

    print(f"    materialized {materialization.statement_count} statements")

    print()
    print("[3] Freezing semantic support graph...")

    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=support_source_ids)

    expected_graphs = {str(unit_graph_iri(source_id)) for source_id in support_source_ids}

    if set(observation.graph_iris) != expected_graphs:
        raise RuntimeError("observed support graphs do not match the expected 2Wiki source graphs")

    if not observation.triples:
        raise RuntimeError("materialized support graph contains no semantic triples")

    graph_ntriples = "\n".join(triple.to_ntriple() for triple in observation.triples)

    print()
    print("Frozen graph:")

    for line in graph_ntriples.splitlines():
        print(f"    {line}")

    feedback: str | None = None
    final_attempt: QAQueryAttempt | None = None
    final_generation = None
    final_execution_sparql: str | None = None
    final_original_result: dict[str, object] | None = None

    for attempt_index in range(1, int(args.max_query_attempts) + 1):
        print()
        print(f"[4] Query attempt {attempt_index}/{args.max_query_attempts}...")

        try:
            generation = generate_twowiki_reference_query(
                case=case,
                graph_ntriples=graph_ntriples,
                feedback=feedback,
                generate_response=generate,
            )
        except ReferenceQueryValidationError as error:
            print(f"    deterministic query validation failed: {error.validation_error}")

            feedback = validation_feedback(response=error.response, error=error.validation_error)

            continue

        execution_sparql = compile_reference_query(
            generation.plan, scope=query_scope, support_source_ids=support_source_ids
        )

        print()
        print("Matched graph evidence:")

        for triple in generation.plan.matched_triples:
            print(f"    {triple}")

        print()
        print("Semantic SPARQL:")

        for line in generation.plan.semantic_sparql.splitlines():
            print(f"    {line}")

        print()
        print("Execution SPARQL:")

        for line in execution_sparql.splitlines():
            print(f"    {line}")

        original_result = graphdb.query(execution_sparql)

        terms = answer_terms(original_result)

        observed_answers = tuple(display_answer_term(term) for term in terms)

        print()
        print(f"GraphDB answers: {observed_answers}")

        if not answer_matches_twowiki_case(case, terms):
            print(f"    expected {case.answer!r}; retrying query")

            feedback = twowiki_execution_feedback(
                case=case,
                scope=query_scope,
                generation=generation,
                execution_sparql=execution_sparql,
                result=original_result,
                terms=terms,
            )

            continue

        print("    ordinary database answer is correct")

        print()
        print("[5] Executing NPCS provenance...")

        provenance_attempt = execute_qa_query_attempt(
            turn_index=attempt_index,
            purpose="final",
            semantic_sparql=(generation.plan.semantic_sparql),
            scoped_sparql=execution_sparql,
            graphdb=graphdb,
            npcs=npcs,
            registry=registry,
        )

        print(f"    provenance status: {provenance_attempt.provenance_status}")

        if provenance_attempt.provenance_status != "decoded":
            raise RuntimeError(
                "ordinary answer was correct but provenance "
                "did not decode: "
                f"{provenance_attempt.error_type}: "
                f"{provenance_attempt.error_message}"
            )

        support_covered = _covers_support(support_source_ids, provenance_attempt)

        source_titles = sorted(
            {
                occurrence.source.title
                for answer in provenance_attempt.answer_provenances
                for derivation in answer.decoded.derivations
                for occurrence in derivation.occurrences
            }
        )

        print(f"    provenance sources: {source_titles}")
        print(f"    all support sources in one derivation: {support_covered}")

        if not support_covered:
            feedback = _support_feedback(
                support_source_ids=support_source_ids,
                generation=generation,
                provenance_attempt=provenance_attempt,
                query_scope=query_scope,
            )

            print(
                "    answer is correct but provenance "
                "does not cover the full evidence chain; "
                "retrying query"
            )

            continue

        final_attempt = provenance_attempt
        final_generation = generation
        final_execution_sparql = execution_sparql
        final_original_result = original_result
        break

    if (
        final_attempt is None
        or final_generation is None
        or final_execution_sparql is None
        or final_original_result is None
    ):
        raise SystemExit(
            "no query satisfied answer and provenance "
            f"criteria after {args.max_query_attempts} attempts"
        )

    artifact = {
        "status": "success",
        "case_id": case.case_id,
        "question": case.question,
        "expected_answer": case.answer,
        "query_scope": query_scope.value,
        "support_source_ids": list(support_source_ids),
        "supporting_paragraphs": [
            {"index": paragraph.index, "title": paragraph.title} for paragraph in support_paragraphs
        ],
        "graph": {
            "extractions": [
                {
                    "paragraph_index": item.paragraph_index,
                    "attempt_count": item.attempt_count,
                    "source": {
                        "unit_id": item.run.source.unit_id,
                        "title": item.run.source.title,
                        "text": item.run.source.text,
                    },
                    "extraction": (item.run.extraction.to_dict()),
                }
                for item in graph_outcome.items
            ],
            "materialization": (materialization.to_dict()),
            "observation": observation.to_dict(),
        },
        "query": {
            "prompt_version": (TWOWIKI_QUERY_PROMPT_VERSION),
            "generation": final_generation.to_dict(),
            "execution_sparql": (final_execution_sparql),
            "original_result": (final_original_result),
        },
        "provenance": final_attempt.to_dict(),
    }

    result_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print()
    print("=" * 72)
    print("2WIKI END-TO-END CASE PASSED")
    print("=" * 72)
    print(f"answer:     {case.answer}")
    print(f"provenance: {final_attempt.provenance_status}")
    print(f"result:     {result_path}")


def _covers_support(support_source_ids: tuple[str, ...], attempt: QAQueryAttempt) -> bool:
    expected = set(support_source_ids)

    return any(
        expected <= {occurrence.source.unit_id for occurrence in derivation.occurrences}
        for answer in attempt.answer_provenances
        for derivation in answer.decoded.derivations
    )


def _support_feedback(
    *,
    support_source_ids: tuple[str, ...],
    generation: object,
    provenance_attempt: QAQueryAttempt,
    query_scope: QueryScope,
) -> str:
    from graphragprov.experiments.multihop_fidelity.query import ReferenceQueryGeneration

    if not isinstance(generation, ReferenceQueryGeneration):
        raise TypeError("unexpected query-generation object")

    return json.dumps(
        {
            "message": (
                "The ordinary answer is correct, but no decoded "
                "provenance derivation uses every required 2Wiki "
                "support source. Re-select the exact frozen-graph "
                "triples required by the benchmark evidence chain "
                "and rebuild the query from them."
            ),
            "query_scope": query_scope.value,
            "required_support_source_ids": list(support_source_ids),
            "previous_matched_triples": list(generation.plan.matched_triples),
            "semantic_sparql": (generation.plan.semantic_sparql),
            "provenance_attempt": (provenance_attempt.to_dict()),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _preflight(*, graphdb: GraphDBClient, npcs: SparqlProvClient) -> None:
    graphdb.query("SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }")

    npcs.rewrite("SELECT ?s WHERE { ?s ?p ?o }")

    print("preflight: GraphDB OK; NPCS OK")


if __name__ == "__main__":
    main()
