"""Run one real MuSiQue question through the graph QA pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    collect_musique_source_units,
    select_cases,
)
from graphragprov.config import musique_dataset_path
from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.provenance import SourceRegistry
from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    deepseek_generator,
)
from graphragprov.qaagent import (
    QAAgentConfiguration,
    QAAgentRunResult,
    run_tuple_qa_agent,
)

_RESULT_FORMAT = "musique-multi-turn-qa-v1"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one materialized MuSiQue case through "
            "DeepSeek, GraphDB, NPCS, and provenance decoding."
        )
    )

    parser.add_argument(
        "--hop-count",
        type=int,
        choices=(2, 3, 4),
        default=2,
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_DEEPSEEK_MODEL,
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=16_384,
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=5,
        help=(
            "Maximum number of QA-agent turns. "
            "Each unsuccessful query response is shown "
            "to the agent on the following turn."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=("Recompute the case even when its result already exists."),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    if arguments.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive")

    if arguments.max_turns <= 0:
        raise SystemExit("--max-turns must be positive")

    dataset_path = musique_dataset_path()

    case = _select_case(
        dataset_path,
        hop_count=arguments.hop_count,
    )

    output_path = arguments.output if arguments.output is not None else _default_output_path(case)

    if output_path.exists() and not arguments.force:
        print("Result already exists; no computation was performed:")
        print(f"  {output_path}")
        return

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    source_units = collect_musique_source_units((case,))

    source_unit_ids = tuple(source.unit_id for source in source_units)

    graphdb = GraphDBClient.from_environment()
    npcs = NPCSClient.from_environment()

    generate_response = deepseek_generator(
        api_key=api_key,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
    )

    configuration = QAAgentConfiguration(
        context_mode="tuples",
        graph_scope="case_all",
        answer_visibility="hidden",
        decomposition_visibility="hop_count",
        max_turns=arguments.max_turns,
    )

    print("Running MuSiQue graph QA")
    print(f"Case:          {case.case_id}")
    print(f"Hop count:     {case.hop_count}")
    print(f"Question:      {case.question}")
    print(f"Expected:      {case.answer}")
    print(f"Paragraphs:    {len(case.paragraphs)}")
    print(f"Scoped graphs: {len(source_units)}")
    print(f"Max turns:     {arguments.max_turns}")
    print(f"Model:         {arguments.model}")
    print()

    result = run_tuple_qa_agent(
        question=case.question,
        hop_count=case.hop_count,
        configuration=configuration,
        source_unit_ids=source_unit_ids,
        graphdb=graphdb,
        npcs=npcs,
        registry=SourceRegistry(source_units),
        generate_response=generate_response,
    )

    payload = _build_result_payload(
        case=case,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        max_turns=arguments.max_turns,
        result=result,
    )

    _write_result(
        output_path,
        payload,
    )

    _print_result(
        result,
        output_path=output_path,
    )


def _select_case(
    dataset_path: Path,
    *,
    hop_count: int,
) -> MusiqueCase:
    selected = select_cases(
        dataset_path,
        hop_count=hop_count,
        limit=1,
    )

    if len(selected) != 1:
        raise ValueError(f"could not select one answerable {hop_count}-hop MuSiQue case")

    return selected[0]


def _default_output_path(
    case: MusiqueCase,
) -> Path:
    case_component = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        case.case_id,
    ).strip("_")

    if not case_component:
        raise ValueError("case ID cannot produce an empty output path")

    return Path("runs") / "musique_qa" / case_component / "result.json"


def _build_result_payload(
    *,
    case: MusiqueCase,
    model: str,
    max_tokens: int,
    max_turns: int,
    result: QAAgentRunResult,
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
        "model": {
            "name": model,
            "max_tokens": max_tokens,
        },
        "execution": {
            "max_turns": max_turns,
            "executed_query_count": len(result.query_attempts),
        },
        "qa_agent": result.to_dict(),
    }


def _write_result(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _print_result(
    result: QAAgentRunResult,
    *,
    output_path: Path,
) -> None:
    print("Final DeepSeek decision")
    print(f"Status:     {result.decision.status}")
    print(f"Rationale:  {result.decision.rationale}")
    print(f"Observed:   {len(result.observation.triples)} semantic triples")
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
        print(f"Turn {attempt.turn_index}")
        print("=" * 72)
        print()
        print("Generated semantic SPARQL:")
        print(attempt.semantic_sparql)
        print()
        print("Backend-scoped SPARQL:")
        print(attempt.scoped_sparql)
        print()
        print(f"Provenance status: {attempt.provenance_status}")

        if attempt.execution is not None:
            print()
            print("Original GraphDB result:")
            print(
                json.dumps(
                    attempt.execution.original_result,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )

        if attempt.answer_provenances:
            print()
            print(f"Decoded answer provenance records: {len(attempt.answer_provenances)}")

            for index, provenance in enumerate(
                attempt.answer_provenances,
                start=1,
            ):
                derivation_count = len(provenance.decoded.derivations)

                print(f"  Answer {index}: {derivation_count} derivation(s)")
                print(f"    Binding: {provenance.binding}")
                print(f"    Polynomial: {provenance.polynomial}")

        if attempt.error_message:
            print()
            print(f"Query/provenance failure: {attempt.error_type}: {attempt.error_message}")

    print()
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
