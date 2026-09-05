"""H0 MuSiQue reference graph/query/provenance experiment."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TypeAlias, cast
from urllib.parse import unquote

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueParagraph,
    MusiqueSourceUnit,
    collect_musique_source_units,
    load_case,
)
from graphragprov.config import musique_dataset_path
from graphragprov.experiments.prompts import (
    H0_QUERY_PROMPT_VERSION,
    build_musique_graph_source_prompt,
    build_musique_sparql_prompt,
)
from graphragprov.extraction import parse_extraction_response
from graphragprov.extraction.run import GenerateResponse, GroundedExtractionRun
from graphragprov.graphdb import GraphDBClient, materialize_grounded_extractions
from graphragprov.npcs import SparqlProvClient
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator
from graphragprov.qaagent import (
    QAQueryAttempt,
    compile_scoped_select_query,
    execute_qa_query_attempt,
)
from graphragprov.qaagent.observation import observe_semantic_triples
from graphragprov.rdf.terms import ENTITY_NAMESPACE, entity_iri, unit_graph_iri

SPARQLTerm: TypeAlias = dict[str, object]
SPARQLResult: TypeAlias = dict[str, object]

SCRIPT_VERSION = "H0_FINAL_V1_2026_08_15"
BAR = "=" * 100
VERBOSE = False


def log(title: str, value: object | None = None, *, verbose_only: bool = False) -> None:
    if verbose_only and not VERBOSE:
        return

    print(f"\n{BAR}\n{title}\n{BAR}")

    if value is None:
        return

    if isinstance(value, str):
        print(value)
        return

    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def cached_response(folder: Path, prompt: str, generate: GenerateResponse) -> tuple[str, bool]:
    """Reuse an exact paid LLM call.

    If the exact prompt has already been executed, return the stored response.
    Otherwise call the model and checkpoint the response immediately.
    """

    prompt_path = folder / "prompt.txt"
    response_path = folder / "response.txt"

    if (
        prompt_path.is_file()
        and response_path.is_file()
        and prompt_path.read_text(encoding="utf-8") == prompt
    ):
        return response_path.read_text(encoding="utf-8"), True

    # deepseek_generator uses response_format={"type": "json_object"}.
    if "json" not in prompt.casefold():
        raise RuntimeError(
            "deepseek_generator uses JSON response mode, "
            "but this prompt does not explicitly request JSON"
        )

    folder.mkdir(parents=True, exist_ok=True)

    prompt_path.write_text(prompt, encoding="utf-8")

    response = generate(prompt)

    response_path.write_text(response, encoding="utf-8")

    return response, False


def supporting_paragraphs(case: MusiqueCase) -> tuple[MusiqueParagraph, ...]:
    """Return gold supporting paragraphs in decomposition order.

    Duplicate support paragraphs are retained only once.
    """

    by_index = {paragraph.index: paragraph for paragraph in case.paragraphs}

    indices: list[int] = []

    for hop in case.decomposition:
        index = hop.paragraph_support_index

        if index is None:
            raise ValueError("every decomposition hop must have a supporting paragraph")

        if index not in indices:
            indices.append(index)

    return tuple(by_index[index] for index in indices)


def construct_graph(
    *,
    case: MusiqueCase,
    all_sources: Iterable[MusiqueSourceUnit],
    generate: GenerateResponse,
    root: Path,
    max_attempts: int,
) -> tuple[GroundedExtractionRun, ...]:
    """Construct H0's graph using only gold supporting paragraphs.

    Python owns source identity.

    Each successive source sees the semantic statements accepted from previous
    sources through build_musique_graph_source_prompt().
    """

    source_by_id = {source.unit_id: source for source in all_sources}

    runs: list[GroundedExtractionRun] = []

    for paragraph in supporting_paragraphs(case):
        source = source_by_id[paragraph.unit_id]

        error: str | None = None

        for attempt in range(1, max_attempts + 1):
            prompt = build_musique_graph_source_prompt(
                case=case,
                source=source,
                paragraph_index=paragraph.index,
                accepted_runs=runs,
                validation_error=error,
            )

            folder = root / "sources" / f"{paragraph.index:02d}" / f"{attempt:02d}"

            log(
                (f"SOURCE {paragraph.index} / ATTEMPT {attempt} / PROMPT"),
                prompt,
                verbose_only=True,
            )

            response, reused = cached_response(folder, prompt, generate)

            log(
                (
                    f"SOURCE {paragraph.index} "
                    f"/ ATTEMPT {attempt} "
                    "/ RESPONSE" + (" [CACHED]" if reused else "")
                ),
                response,
                verbose_only=True,
            )

            try:
                extraction = parse_extraction_response(source, response)
            except ValueError as exc:
                error = f"{type(exc).__name__}: {exc}"

                (folder / "error.txt").write_text(error, encoding="utf-8")

                log(f"SOURCE {paragraph.index} / REJECTED", error)

                continue

            runs.append(GroundedExtractionRun(source, prompt, response, extraction))

            log(
                f"SOURCE {paragraph.index} / ACCEPTED",
                {
                    "cached": reused,
                    "statement_count": len(extraction.statements),
                    "source_unit_id": source.unit_id,
                },
            )

            log(
                (f"SOURCE {paragraph.index} / ACCEPTED / FULL"),
                extraction.to_dict(),
                verbose_only=True,
            )

            break

        else:
            raise RuntimeError(
                f"paragraph {paragraph.index} failed after {max_attempts} attempts: {error}"
            )

    return tuple(runs)


def parse_query_plan(response: str, graph_ntriples: str) -> tuple[tuple[str, ...], str]:
    """Parse the evidence-first query response.

    matched_triples must literally exist in the frozen support graph.
    """

    try:
        decoded: object = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("response must be valid JSON") from exc

    data = _string_keyed_dict(decoded)

    if data is None or set(data) != {"matched_triples", "sparql"}:
        raise ValueError("response must contain exactly 'matched_triples' and 'sparql'")

    raw_matched = data["matched_triples"]

    if not isinstance(raw_matched, list) or not raw_matched:
        raise ValueError("matched_triples must be a non-empty JSON array")

    matched_items: list[str] = []

    for item in raw_matched:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("every matched_triples item must be a non-empty string")

        matched_items.append(item.strip())

    matched = tuple(matched_items)

    graph_lines = {line.strip() for line in graph_ntriples.splitlines() if line.strip()}

    missing = [triple for triple in matched if triple not in graph_lines]

    if missing:
        raise ValueError(
            "matched_triples must be copied exactly "
            "from the frozen RDF graph; "
            f"not found: {missing!r}"
        )

    if len(set(matched)) != len(matched):
        raise ValueError("matched_triples must not contain duplicates")

    raw_sparql = data["sparql"]

    if not isinstance(raw_sparql, str) or not raw_sparql.strip():
        raise ValueError("sparql must be a non-empty string")

    sparql = raw_sparql.strip()

    normalized = " ".join(sparql.casefold().split())

    # Current NPCS implementation does not correctly
    # rewrite SELECT DISTINCT while preserving provenance.
    if "select distinct" in normalized:
        raise ValueError(
            "DISTINCT is not allowed in H0 because "
            "the current NPCS rewrite path does not "
            "correctly preserve provenance for "
            "SELECT DISTINCT"
        )

    if "?answer" not in sparql:
        raise ValueError("SPARQL must project the final answer as ?answer")

    return matched, sparql


def _string_keyed_dict(value: object) -> dict[str, object] | None:
    """Return a string-keyed object when the value has that shape."""

    if not isinstance(value, dict):
        return None

    if not all(isinstance(key, str) for key in value):
        return None

    return cast(dict[str, object], value)


def _result_bindings(result: SPARQLResult) -> tuple[dict[str, object], ...]:
    """Read valid object bindings from a SPARQL JSON result."""

    raw_results = _string_keyed_dict(result.get("results"))

    if raw_results is None:
        return ()

    raw_bindings = raw_results.get("bindings")

    if not isinstance(raw_bindings, list):
        return ()

    bindings: list[dict[str, object]] = []

    for row in raw_bindings:
        binding = _string_keyed_dict(row)

        if binding is not None:
            bindings.append(binding)

    return tuple(bindings)


def answer_terms(result: SPARQLResult) -> tuple[SPARQLTerm, ...]:
    """Return unique ?answer RDF terms.

    SPARQL bag duplicates are collapsed here for answer evaluation.
    Provenance is still computed over the actual query execution.
    """

    terms: list[SPARQLTerm] = []

    seen: set[tuple[object, object, object, object]] = set()

    for row in _result_bindings(result):
        term = _string_keyed_dict(row.get("answer"))

        if term is None:
            continue

        key = (term.get("type"), term.get("value"), term.get("datatype"), term.get("xml:lang"))

        if key in seen:
            continue

        seen.add(key)
        terms.append(term)

    return tuple(terms)


def display(term: SPARQLTerm) -> str:
    value = term.get("value")

    if not isinstance(value, str):
        return repr(term)

    if value.startswith(ENTITY_NAMESPACE):
        return unquote(value[len(ENTITY_NAMESPACE) :])

    return value


def answer_ok(case: MusiqueCase, terms: tuple[SPARQLTerm, ...]) -> bool:
    """Require exactly one unique answer.

    URI answers are compared using the same deterministic entity IRI
    construction used by GraphRAGProv.
    """

    if len(terms) != 1:
        return False

    value = terms[0].get("value")

    if not isinstance(value, str):
        return False

    gold = (case.answer, *case.answer_aliases)

    if terms[0].get("type") == "uri":
        expected_iris = {str(entity_iri(candidate)) for candidate in gold}

        return value in expected_iris

    def normalize(text: str) -> str:
        return " ".join(text.split()).casefold()

    return normalize(value) in {normalize(candidate) for candidate in gold}


def covers_gold_support(case: MusiqueCase, attempt: QAQueryAttempt) -> bool:
    """Require one decoded derivation to cover every gold support source."""

    expected = {paragraph.unit_id for paragraph in supporting_paragraphs(case)}

    return any(
        expected <= {occurrence.source.unit_id for occurrence in derivation.occurrences}
        for answer in attempt.answer_provenances
        for derivation in answer.decoded.derivations
    )


def execution_query(
    *, semantic_sparql: str, query_scope: str, support_source_ids: Iterable[str]
) -> str:
    """Apply the experimental query-scope policy.

    support:
        add FROM clauses for only gold supporting source graphs.

    repository:
        leave the semantic query unscoped. It is evaluated against the
        repository dataset configured by GraphDB.

    The LLM never chooses this policy.
    """

    if query_scope == "support":
        return compile_scoped_select_query(semantic_sparql, source_unit_ids=support_source_ids)

    if query_scope == "repository":
        return semantic_sparql

    raise ValueError(f"unsupported query scope: {query_scope!r}")


def repository_named_graphs(graphdb: GraphDBClient) -> tuple[str, ...]:
    """Observe the current GraphDB named-graph population for traceability."""

    result = graphdb.query(
        """
        SELECT DISTINCT ?graph
        WHERE {
          GRAPH ?graph {
            ?s ?p ?o
          }
        }
        ORDER BY ?graph
        """
    )

    graphs: list[str] = []

    for row in _result_bindings(result):
        term = _string_keyed_dict(row.get("graph"))

        if term is None or term.get("type") != "uri":
            continue

        value = term.get("value")

        if isinstance(value, str):
            graphs.append(value)

    return tuple(graphs)


def query_feedback(
    *,
    case: MusiqueCase,
    query_scope: str,
    matched_triples: tuple[str, ...],
    semantic: str,
    execution_sparql: str,
    result: SPARQLResult,
    terms: tuple[SPARQLTerm, ...],
) -> str:
    """Exact execution feedback for the next query-generation turn."""

    return json.dumps(
        {
            "message": (
                "The previous query was executed "
                f"with query_scope={query_scope!r} "
                "and did not return exactly the expected "
                "?answer. Re-check the evidence selection "
                "first, then rebuild SPARQL only from exact "
                "frozen-graph triples. Preserve each "
                "selected triple's subject/predicate/object "
                "orientation."
            ),
            "query_scope": query_scope,
            "expected_answer": case.answer,
            "observed_answers": [display(term) for term in terms],
            "previous_matched_triples": list(matched_triples),
            "previous_semantic_sparql": semantic,
            "previous_execution_sparql": (execution_sparql),
            "graphdb_result": result,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def construct_query(
    *,
    case: MusiqueCase,
    graph_text: str,
    support_source_ids: tuple[str, ...],
    query_scope: str,
    graphdb: GraphDBClient,
    npcs: SparqlProvClient,
    registry: SourceRegistry,
    generate: GenerateResponse,
    root: Path,
    max_attempts: int,
) -> QAQueryAttempt:
    """Generate, execute, validate, and provenance-check one reference query."""

    feedback: str | None = None

    for turn in range(1, max_attempts + 1):
        folder = root / "query" / query_scope / f"{turn:02d}"

        prompt = build_musique_sparql_prompt(
            case=case, graph_ntriples=graph_text, feedback=feedback
        )

        log(f"QUERY {turn} / PROMPT", prompt, verbose_only=True)

        response, reused = cached_response(folder, prompt, generate)

        log(
            (f"QUERY {turn} / RESPONSE" + (" [CACHED]" if reused else "")),
            response,
            verbose_only=True,
        )

        try:
            (matched_triples, semantic) = parse_query_plan(response, graph_text)

            execution_sparql = execution_query(
                semantic_sparql=semantic,
                query_scope=query_scope,
                support_source_ids=(support_source_ids),
            )

        except ValueError as exc:
            feedback = json.dumps(
                {
                    "message": (
                        "The previous JSON response "
                        "was rejected by the deterministic "
                        "validator. Return exact frozen-graph "
                        "triples and compile only those "
                        "triples into a plain "
                        "SELECT ?answer query."
                    ),
                    "error_type": (type(exc).__name__),
                    "error_message": str(exc),
                    "previous_response": response,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

            folder.mkdir(parents=True, exist_ok=True)

            (folder / "feedback.txt").write_text(feedback, encoding="utf-8")

            log((f"QUERY {turn} / VALIDATION ERROR"), feedback)

            continue

        dump(folder / "matched_triples.json", list(matched_triples))

        (folder / "semantic.sparql").write_text(semantic, encoding="utf-8")

        (folder / "execution.sparql").write_text(execution_sparql, encoding="utf-8")

        log(
            f"QUERY {turn} / PLAN",
            {
                "cached": reused,
                "query_scope": query_scope,
                "matched_triple_count": len(matched_triples),
                "semantic_sparql": semantic,
            },
        )

        log((f"QUERY {turn} / MATCHED GRAPH EVIDENCE"), list(matched_triples), verbose_only=True)

        log((f"QUERY {turn} / EXECUTION SPARQL"), execution_sparql, verbose_only=True)

        result = graphdb.query(execution_sparql)

        dump(folder / "original_result.json", result)

        log((f"QUERY {turn} / GRAPHDB RESULT"), result, verbose_only=True)

        terms = answer_terms(result)

        correct = answer_ok(case, terms)

        log(
            (f"QUERY {turn} / ANSWER CHECK"),
            {
                "observed": [display(term) for term in terms],
                "expected": case.answer,
                "correct": correct,
            },
        )

        if not correct:
            feedback = query_feedback(
                case=case,
                query_scope=query_scope,
                matched_triples=(matched_triples),
                semantic=semantic,
                execution_sparql=(execution_sparql),
                result=result,
                terms=terms,
            )

            (folder / "feedback.txt").write_text(feedback, encoding="utf-8")

            log((f"QUERY {turn} / FEEDBACK FOR NEXT TURN"), feedback, verbose_only=True)

            continue

        log(
            (f"QUERY {turn} / ANSWER CORRECT"),
            ("Starting existing NPCS/provenance execution path."),
        )

        def event_sink(event: dict[str, object], *, query_turn: int = turn) -> None:
            event_type = event.get("type", "unknown")

            payload = {key: value for key, value in event.items() if key != "type"}

            log(
                (f"QUERY {query_turn} / PROVENANCE EVENT / {event_type}"),
                payload,
                verbose_only=True,
            )

        attempt = execute_qa_query_attempt(
            turn_index=turn,
            purpose="final",
            semantic_sparql=semantic,
            scoped_sparql=(execution_sparql),
            graphdb=graphdb,
            npcs=npcs,
            registry=registry,
            event_sink=event_sink,
        )

        dump((folder / "provenance_attempt.json"), attempt.to_dict())

        log(
            (f"QUERY {turn} / PROVENANCE STATUS"),
            {
                "status": (attempt.provenance_status),
                "error_type": (attempt.error_type),
                "error_message": (attempt.error_message),
                "answer_provenance_count": (len(attempt.answer_provenances)),
            },
        )

        log((f"QUERY {turn} / PROVENANCE ATTEMPT / FULL"), attempt.to_dict(), verbose_only=True)

        if attempt.provenance_status == "failed":
            raise RuntimeError(
                "correct ordinary answer, "
                "but provenance failed: "
                f"{attempt.error_type}: "
                f"{attempt.error_message}"
            )

        if attempt.provenance_status != "decoded":
            raise RuntimeError(
                f"correct ordinary answer, but provenance status={attempt.provenance_status}"
            )

        if covers_gold_support(case, attempt):
            return attempt

        feedback = json.dumps(
            {
                "message": (
                    "The answer is correct, but "
                    "no decoded derivation uses all "
                    "gold supporting paragraphs. "
                    "Re-select the exact triples "
                    "required by the full decomposition "
                    "and rebuild the query from them."
                ),
                "query_scope": query_scope,
                "previous_matched_triples": (list(matched_triples)),
                "semantic_sparql": semantic,
                "provenance_attempt": (attempt.to_dict()),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

        (folder / "feedback.txt").write_text(feedback, encoding="utf-8")

        log((f"QUERY {turn} / FEEDBACK FOR NEXT TURN"), feedback, verbose_only=True)

    raise RuntimeError(
        f"no valid query after {max_attempts} attempts for query_scope={query_scope!r}"
    )


def main() -> None:
    global VERBOSE

    args = arguments()

    VERBOSE = args.verbose

    print(f"script version: {SCRIPT_VERSION}")

    print(f"query prompt version: {H0_QUERY_PROMPT_VERSION}")

    print(f"query scope: {args.query_scope}")

    case = load_case(musique_dataset_path(), args.case_id)

    if not case.answerable:
        raise SystemExit("case is not answerable")

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    graphdb = GraphDBClient.from_environment()

    npcs = SparqlProvClient.from_environment()

    log(
        "PREFLIGHT",
        {
            "graphdb": (graphdb.repository_endpoint),
            "npcs": (npcs.rewrite_endpoint),
            "query_scope": (args.query_scope),
        },
    )

    log(
        "PREFLIGHT / GRAPHDB",
        graphdb.query("SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"),
        verbose_only=True,
    )

    test_query = "SELECT ?s WHERE { ?s ?p ?o }"

    log(
        "PREFLIGHT / NPCS",
        {"input": test_query, "rewritten": (npcs.rewrite(test_query))},
        verbose_only=True,
    )

    # All source units belonging to this MuSiQue case.
    all_sources = collect_musique_source_units((case,))

    source_by_id = {source.unit_id: source for source in all_sources}

    paragraphs = supporting_paragraphs(case)

    support_sources = tuple(source_by_id[paragraph.unit_id] for paragraph in paragraphs)

    support_source_ids = tuple(source.unit_id for source in support_sources)

    # Important:
    #
    # Support-scope execution only needs the gold support sources.
    #
    # Repository-scope execution may encounter an already-materialized
    # paragraph from the same MuSiQue case. Registering all current-case
    # sources lets the existing provenance decoder resolve those occurrences
    # without changing SourceRegistry itself.
    registry = SourceRegistry(all_sources)

    root = args.artifacts / case.case_id

    root.mkdir(parents=True, exist_ok=True)

    if args.retry_queries:
        query_root = root / "query" / args.query_scope

        if query_root.exists():
            shutil.rmtree(query_root)

        log("QUERY CACHE", (f"Cleared cached {args.query_scope!r} query attempts."))

    log(
        "CASE",
        {
            "case_id": (case.case_id),
            "question": (case.question),
            "expected_answer": (case.answer),
            "hop_count": (len(case.decomposition)),
            "query_scope": (args.query_scope),
            "supporting_paragraphs": [paragraph.index for paragraph in paragraphs],
            "artifacts": (str(root)),
        },
    )

    log(
        "CASE / FULL DECOMPOSITION",
        [
            {
                "question": (hop.question),
                "answer": (hop.answer),
                "support_paragraph": (hop.paragraph_support_index),
            }
            for hop in case.decomposition
        ],
        verbose_only=True,
    )

    generate = deepseek_generator(api_key=api_key, model=args.model, max_tokens=args.max_tokens)

    if args.reuse_graph:
        log("GRAPH", ("Reusing supporting named graphs. No extraction LLM calls."))

    else:
        runs = construct_graph(
            case=case,
            all_sources=all_sources,
            generate=generate,
            root=root,
            max_attempts=(args.max_source_attempts),
        )

        # Replace only the current case's gold supporting graphs.
        # Never clear the whole repository here.
        for source_id in support_source_ids:
            graphdb.update(f"CLEAR SILENT GRAPH {unit_graph_iri(source_id).n3()}")

        summary = materialize_grounded_extractions(runs, graphdb=graphdb)

        dump(root / "materialization.json", summary.to_dict())

        log("MATERIALIZATION", summary.to_dict(), verbose_only=True)

    # The frozen graph shown to the query-construction LLM is ALWAYS the
    # gold-support graph. Query scope is applied later by Python.
    #
    # This keeps semantic query construction separate from the experimental
    # execution-dataset condition.
    observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=(support_source_ids))

    expected_graphs = {str(unit_graph_iri(source_id)) for source_id in support_source_ids}

    if set(observation.graph_iris) != expected_graphs:
        raise RuntimeError(
            "supporting graph mismatch: "
            f"expected="
            f"{sorted(expected_graphs)}, "
            f"observed="
            f"{list(observation.graph_iris)}"
        )

    if not observation.triples:
        raise RuntimeError("supporting graphs contain no semantic triples")

    dump(root / "graph_observation.json", observation.to_dict())

    graph_text = "\n".join(triple.to_ntriple() for triple in observation.triples)

    log(
        "FROZEN SUPPORT GRAPH",
        {
            "named_graphs": (list(observation.graph_iris)),
            "semantic_triple_count": (len(observation.triples)),
        },
    )

    log("FROZEN SUPPORT GRAPH / FULL", graph_text, verbose_only=True)

    # Observe repository state regardless of chosen scope.
    # This makes later support-vs-repository comparisons auditable.
    repo_graphs = repository_named_graphs(graphdb)

    dump(
        root / "repository_named_graphs.json",
        {"query_scope": (args.query_scope), "named_graphs": (list(repo_graphs))},
    )

    log(
        "REPOSITORY DATASET",
        {
            "named_graph_count": (len(repo_graphs)),
            "support_graph_count": (len(observation.graph_iris)),
            "query_scope": (args.query_scope),
        },
    )

    log(("REPOSITORY DATASET / NAMED GRAPHS"), list(repo_graphs), verbose_only=True)

    if args.query_scope == "repository":
        known_case_graphs = {str(unit_graph_iri(source.unit_id)) for source in all_sources}

        foreign_graphs = sorted(set(repo_graphs) - known_case_graphs)

        if foreign_graphs:
            log(
                "REPOSITORY SCOPE / NOTE",
                {
                    "foreign_named_graph_count": (len(foreign_graphs)),
                    "message": (
                        "Repository execution can use "
                        "these graphs. If a returned "
                        "provenance derivation depends "
                        "on a source outside the current "
                        "MuSiQue case, this case-local "
                        "SourceRegistry cannot decode it."
                    ),
                },
            )

            log(("REPOSITORY SCOPE / FOREIGN NAMED GRAPHS"), foreign_graphs, verbose_only=True)

    final = construct_query(
        case=case,
        graph_text=graph_text,
        support_source_ids=(support_source_ids),
        query_scope=(args.query_scope),
        graphdb=graphdb,
        npcs=npcs,
        registry=registry,
        generate=generate,
        root=root,
        max_attempts=(args.max_query_attempts),
    )

    result = {
        "case_id": (case.case_id),
        "question": (case.question),
        "expected_answer": (case.answer),
        "query_scope": (args.query_scope),
        "supporting_paragraphs": [paragraph.index for paragraph in paragraphs],
        "query_prompt_version": (H0_QUERY_PROMPT_VERSION),
        "query": (final.to_dict()),
    }

    result_path = root / (f"result-{args.query_scope}.json")

    dump(result_path, result)

    log(
        "H0 CASE PASSED",
        {
            "case_id": (case.case_id),
            "hop_count": (len(case.decomposition)),
            "query_scope": (args.query_scope),
            "provenance_status": (final.provenance_status),
            "result": (str(result_path)),
        },
    )

    log("H0 CASE PASSED / FULL RESULT", result, verbose_only=True)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--case-id", required=True)

    parser.add_argument(
        "--query-scope",
        choices=("support", "repository"),
        default="support",
        help=(
            "'support': query only the gold "
            "supporting source named graphs. "
            "'repository': run the semantic query "
            "without FROM clauses over GraphDB's "
            "repository-wide dataset."
        ),
    )

    parser.add_argument("--model", default=(DEFAULT_DEEPSEEK_MODEL))

    parser.add_argument("--max-tokens", type=int, default=16_384)

    parser.add_argument("--max-source-attempts", type=int, default=3)

    parser.add_argument("--max-query-attempts", type=int, default=5)

    parser.add_argument("--artifacts", type=Path, default=Path("runs/H0_musique_benchmark_graphs"))

    parser.add_argument(
        "--reuse-graph",
        action="store_true",
        help=("Reuse already materialized gold supporting named graphs."),
    )

    parser.add_argument(
        "--retry-queries",
        action="store_true",
        help=("Clear only cached query attempts for the selected query scope."),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Print full prompts, responses, "
            "graph triples, GraphDB results, "
            "NPCS events, and decoded provenance. "
            "Artifacts are persisted either way."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
