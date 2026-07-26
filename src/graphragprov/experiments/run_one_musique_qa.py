"""Run one MuSiQue case through the graph QA pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from graphragprov.benchmarks.musique import MusiqueCase, collect_musique_source_units, select_cases
from graphragprov.config import musique_dataset_path
from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator
from graphragprov.qaagent import QAAgentConfiguration, QAAgentRunResult, run_tuple_qa_agent

_RESULT_FORMAT = "musique-multi-turn-qa-v1"
_DEFAULT_MAX_TOKENS = 16_384
_DEFAULT_MAX_TURNS = 5

MusiqueQueryScope = Literal["case_graphs", "whole_repository"]

_QUERY_SCOPES: tuple[MusiqueQueryScope, ...] = ("case_graphs", "whole_repository")

GenerateResponse = Callable[[str], str]
QARunEventSink = Callable[[dict[str, object]], None]


def run_musique_case_qa(
    *,
    case: MusiqueCase,
    question: str | None = None,
    max_turns: int = _DEFAULT_MAX_TURNS,
    query_scope: MusiqueQueryScope = "case_graphs",
    include_oracle_tuples: bool = False,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    graphdb: GraphDBClient | None = None,
    npcs: NPCSClient | None = None,
    generate_response: GenerateResponse | None = None,
    provenance_registry: SourceRegistry | None = None,
    event_sink: QARunEventSink | None = None,
) -> QAAgentRunResult:
    """Run one benchmark case through the graph QA instrument.

    Query scope and prompt tuple visibility are independent.

    ``query_scope`` controls the named graphs available to SPARQL.

    ``include_oracle_tuples`` controls whether tuples extracted from the
    gold supporting paragraphs are included in the initial LLM prompt.
    """

    if max_turns <= 0:
        raise ValueError("max_turns must be positive")

    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")

    if query_scope not in _QUERY_SCOPES:
        raise ValueError("query_scope must be one of: " + ", ".join(_QUERY_SCOPES))

    resolved_question = case.question if question is None else question.strip()

    if not resolved_question:
        raise ValueError("question must not be empty")

    case_source_units = collect_musique_source_units((case,))

    case_source_unit_ids = tuple(source.unit_id for source in case_source_units)

    gold_support_unit_ids = tuple(
        paragraph.unit_id for paragraph in case.paragraphs if case.is_supporting(paragraph.index)
    )

    if include_oracle_tuples and not gold_support_unit_ids:
        raise ValueError("oracle tuple context requires at least one gold supporting paragraph")

    query_source_unit_ids = case_source_unit_ids if query_scope == "case_graphs" else None

    prompt_source_unit_ids = gold_support_unit_ids if include_oracle_tuples else None

    if query_scope == "whole_repository" and provenance_registry is None:
        raise ValueError(
            "whole_repository query scope requires an experiment-wide provenance registry"
        )

    resolved_registry = (
        provenance_registry
        if provenance_registry is not None
        else SourceRegistry(case_source_units)
    )

    try:
        resolved_graphdb = graphdb if graphdb is not None else GraphDBClient.from_environment()

        resolved_npcs = npcs if npcs is not None else NPCSClient.from_environment()
    except ValueError as error:
        raise RuntimeError(f"QA infrastructure is not configured: {error}") from error

    if generate_response is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")

        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")

        resolved_generate_response = deepseek_generator(
            api_key=api_key, model=model, max_tokens=max_tokens
        )
    else:
        resolved_generate_response = generate_response

    configuration = QAAgentConfiguration(
        context_mode=("tuples" if include_oracle_tuples else "graph_agent"),
        graph_scope=("case_all" if query_scope == "case_graphs" else "repository_all"),
        answer_visibility="hidden",
        decomposition_visibility="hop_count",
        max_turns=max_turns,
    )

    return run_tuple_qa_agent(
        question=resolved_question,
        hop_count=case.hop_count,
        configuration=configuration,
        query_source_unit_ids=query_source_unit_ids,
        prompt_source_unit_ids=prompt_source_unit_ids,
        graphdb=resolved_graphdb,
        npcs=resolved_npcs,
        registry=resolved_registry,
        generate_response=resolved_generate_response,
        event_sink=event_sink,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one materialized MuSiQue case through "
            "DeepSeek, GraphDB, NPCS, and provenance decoding."
        )
    )

    parser.add_argument("--hop-count", type=int, choices=(2, 3, 4), default=2)

    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)

    parser.add_argument("--max-tokens", type=int, default=_DEFAULT_MAX_TOKENS)

    parser.add_argument(
        "--max-turns",
        type=int,
        default=_DEFAULT_MAX_TURNS,
        help=(
            "Maximum number of QA-agent turns. Every query is "
            "executed through GraphDB, NPCS, and provenance decoding."
        ),
    )

    parser.add_argument(
        "--include-oracle-tuples",
        action="store_true",
        help=(
            "Include tuples extracted from the gold supporting "
            "paragraphs in the initial LLM prompt."
        ),
    )

    parser.add_argument("--output", type=Path)

    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute the case even when its result already exists.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    if arguments.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive")

    if arguments.max_turns <= 0:
        raise SystemExit("--max-turns must be positive")

    dataset_path = musique_dataset_path()

    case = _select_case(dataset_path, hop_count=arguments.hop_count)

    output_path = arguments.output if arguments.output is not None else _default_output_path(case)

    if output_path.exists() and not arguments.force:
        print("Result already exists; no computation was performed:")
        print(f"  {output_path}")
        return

    print("Running MuSiQue graph QA")
    print(f"Case:          {case.case_id}")
    print(f"Hop count:     {case.hop_count}")
    print(f"Question:      {case.question}")
    print(f"Expected:      {case.answer}")
    print(f"Paragraphs:    {len(case.paragraphs)}")
    print("Query scope:   case graphs")
    print(f"Oracle tuples: {arguments.include_oracle_tuples}")
    print(f"Max turns:     {arguments.max_turns}")
    print(f"Model:         {arguments.model}")
    print()

    try:
        result = run_musique_case_qa(
            case=case,
            max_turns=arguments.max_turns,
            query_scope="case_graphs",
            include_oracle_tuples=(arguments.include_oracle_tuples),
            model=arguments.model,
            max_tokens=arguments.max_tokens,
        )
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    payload = _build_result_payload(
        case=case,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        max_turns=arguments.max_turns,
        result=result,
    )

    _write_result(output_path, payload)

    _print_result(result, output_path=output_path)


def _select_case(dataset_path: Path, *, hop_count: int) -> MusiqueCase:
    selected = select_cases(dataset_path, hop_count=hop_count, limit=1)

    if len(selected) != 1:
        raise ValueError(f"could not select one answerable {hop_count}-hop MuSiQue case")

    return selected[0]


def _default_output_path(case: MusiqueCase) -> Path:
    case_component = re.sub(r"[^A-Za-z0-9._-]+", "_", case.case_id).strip("_")

    if not case_component:
        raise ValueError("case ID cannot produce an empty output path")

    return Path("runs") / "musique_qa" / case_component / "result.json"


def _build_result_payload(
    *, case: MusiqueCase, model: str, max_tokens: int, max_turns: int, result: QAAgentRunResult
) -> dict[str, object]:
    return {
        "format": _RESULT_FORMAT,
        "case": {
            "case_id": case.case_id,
            "hop_count": case.hop_count,
            "question": case.question,
            "expected_answer": case.answer,
            "answer_aliases": list(case.answer_aliases),
            "answerable": case.answerable,
            "paragraph_indices": [paragraph.index for paragraph in case.paragraphs],
            "gold_support_indices": list(case.gold_support_indices),
        },
        "model": {"name": model, "max_tokens": max_tokens},
        "execution": {"max_turns": max_turns, "executed_query_count": len(result.query_attempts)},
        "qa_agent": result.to_dict(),
    }


def _write_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _print_result(result: QAAgentRunResult, *, output_path: Path) -> None:
    print("Final DeepSeek decision")
    print(f"Status:      {result.decision.status}")
    print(f"Rationale:   {result.decision.rationale}")

    if result.observation is None:
        print("Observed:    no initial tuples")
    else:
        print(f"Observed:    {len(result.observation.triples)} semantic triples")

    print(f"Queries run: {len(result.query_attempts)}")

    if result.decision.assumptions:
        print("Final assumptions:")

        for assumption in result.decision.assumptions:
            print(f"  - {assumption}")

    if not result.query_attempts:
        print()
        print("No SPARQL query was executed.")

    for attempt in result.query_attempts:
        print()
        print("=" * 72)
        print(f"Turn {attempt.turn_index} ({attempt.purpose})")
        print("=" * 72)
        print()
        print("Generated semantic SPARQL:")
        print(attempt.semantic_sparql)
        print()
        print("Backend-scoped SPARQL:")
        print(attempt.scoped_sparql)

        if attempt.execution is not None:
            print()
            print("NPCS-rewritten SPARQL:")
            print(attempt.execution.rewritten_query)
            print()
            print("Original GraphDB result:")
            print(
                json.dumps(
                    attempt.execution.original_result, ensure_ascii=False, indent=2, sort_keys=True
                )
            )

        print()
        print(f"Provenance status: {attempt.provenance_status}")

        if attempt.answer_provenances:
            print()
            print(f"Decoded result provenance records: {len(attempt.answer_provenances)}")

            for index, provenance in enumerate(attempt.answer_provenances, start=1):
                derivation_count = len(provenance.decoded.derivations)

                print(f"  Result {index}: {derivation_count} derivation(s)")
                print(f"    Binding: {provenance.binding}")
                print(f"    Polynomial: {provenance.polynomial}")

        if attempt.error_message:
            print()
            print(f"Query/provenance failure: {attempt.error_type}: {attempt.error_message}")

    print()
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
