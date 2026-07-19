"""Materialize one 2-hop, 3-hop, and 4-hop MuSiQue case."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    collect_musique_source_units,
    select_cases,
)

from graphragprov.config import musique_dataset_path
from graphragprov.experiments import (
    MusiqueMaterializationManifest,
    write_musique_materialization_manifest,
)

from graphragprov.extraction import load_or_run_grounded_extraction_batch
from graphragprov.extraction.batch import GroundedExtractionBatchItem
from graphragprov.extraction.prompt import PROMPT_VERSION
from graphragprov.extraction.run import GroundedExtractionFailure
from graphragprov.graphdb import (
    GraphDBClient,
    materialize_grounded_extractions,
)

from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    deepseek_generator,
)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract and materialize every paragraph from one "
            "answerable 2-hop, 3-hop, and 4-hop MuSiQue case."
        )
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
        "--cache-root",
        type=Path,
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("runs/musique_pilot/materialization.json"),
    )
    parser.add_argument(
        "--allow-existing-statements",
        action="store_true",
        help=(
            "Allow idempotent upload into a non-empty repository. "
            "Use this only when resuming the same materialization."
        ),
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help=("Rerun cached failed extractions while continuing to reuse cached successes."),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=("Print statement validation and correction progress for every source unit."),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    if arguments.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive")

    dataset_path = musique_dataset_path()
    cases = _select_pilot_cases(dataset_path)
    source_units = collect_musique_source_units(cases)

    cache_root = (
        arguments.cache_root
        if arguments.cache_root is not None
        else _default_cache_root(arguments.model)
    )

    graphdb = GraphDBClient.from_environment()
    existing_statement_count = _repository_statement_count(graphdb)

    if existing_statement_count > 0 and not arguments.allow_existing_statements:
        raise SystemExit(
            "GraphDB repository is not empty "
            f"({existing_statement_count} statements). "
            "Clear it first, or use "
            "--allow-existing-statements only to resume "
            "this same pilot materialization."
        )

    print("Selected MuSiQue cases:")

    for case in cases:
        print(f"  {case.hop_count}-hop: {case.case_id} ({len(case.paragraphs)} paragraphs)")

    total_paragraphs = sum(len(case.paragraphs) for case in cases)

    print(f"Paragraph occurrences: {total_paragraphs}")
    print(f"Unique source units:   {len(source_units)}")
    print(f"Extraction cache:      {cache_root}")
    print(f"GraphDB repository:    {graphdb.repository}")

    generate_response = deepseek_generator(
        api_key=api_key,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
    )

    batch = load_or_run_grounded_extraction_batch(
        source_units,
        cache_root=cache_root,
        generate_response=generate_response,
        retry_failures=arguments.retry_failures,
        progress=(_print_extraction_progress if arguments.verbose else None),
    )

    materialization = materialize_grounded_extractions(
        batch.runs,
        graphdb=graphdb,
    )

    manifest = MusiqueMaterializationManifest.from_execution(
        dataset_path=dataset_path,
        cases=cases,
        batch=batch,
        materialization=materialization,
        prompt_version=PROMPT_VERSION,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        cache_root=cache_root,
        graphdb=graphdb,
        existing_statement_count=existing_statement_count,
    )

    write_musique_materialization_manifest(
        arguments.manifest,
        manifest,
    )

    status = "complete" if not batch.failures else "partial"

    print()
    print(f"Materialization {status}")
    print(f"Requested sources:     {len(batch.items)}")
    print(f"Successful extractions:{len(batch.runs):>6}")
    print(f"Failed extractions:    {len(batch.failures):>6}")
    print(f"New outcomes:          {batch.executed_count:>6}")
    print(f"Reused outcomes:       {batch.reused_count:>6}")
    print(f"Grounded statements:  {materialization.statement_count:>6}")
    print(f"Named graphs:          {materialization.source_count:>6}")

    if batch.failures:
        print()
        print("Extraction failures:")

        for failure in batch.failures:
            response_path = cache_root / failure.source.unit_id / "response.txt"
            error_path = cache_root / failure.source.unit_id / "error.json"

            print(f"  {failure.source.unit_id}")
            print(f"    title: {failure.source.title}")
            print(f"    stage: {failure.stage}")
            print(f"    error: {failure.error_type}: {failure.error_message}")
            print(f"    response: {response_path}")
            print(f"    report:   {error_path}")

    print()
    print(f"Manifest:              {arguments.manifest}")


def _select_pilot_cases(
    dataset_path: Path,
) -> tuple[MusiqueCase, ...]:
    cases: list[MusiqueCase] = []

    for hop_count in (2, 3, 4):
        selected = select_cases(
            dataset_path,
            hop_count=hop_count,
            limit=1,
        )

        if len(selected) != 1:
            raise ValueError(f"could not select one answerable {hop_count}-hop MuSiQue case")

        cases.append(selected[0])

    return tuple(cases)


def _default_cache_root(
    model: str,
) -> Path:
    model_component = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        model,
    ).strip("_")

    if not model_component:
        raise ValueError("model name cannot produce an empty cache directory name")

    return Path("runs") / "musique_pilot" / "extractions" / PROMPT_VERSION / model_component


def _repository_statement_count(
    graphdb: GraphDBClient,
) -> int:
    result = graphdb.query(
        """
        SELECT (COUNT(*) AS ?count)
        WHERE {
          GRAPH ?graph {
            ?subject ?predicate ?object .
          }
        }
        """
    )

    results = result.get("results")

    if not isinstance(results, dict):
        raise ValueError("GraphDB count result has no results object")

    bindings = results.get("bindings")

    if not isinstance(bindings, list):
        raise ValueError("GraphDB count result has no bindings list")

    if len(bindings) != 1:
        raise ValueError("GraphDB count query must return one row")

    row = bindings[0]

    if not isinstance(row, dict):
        raise ValueError("GraphDB count binding must be an object")

    count = row.get("count")

    if not isinstance(count, dict):
        raise ValueError("GraphDB count binding has no count value")

    value = count.get("value")

    if not isinstance(value, str):
        raise ValueError("GraphDB count value must be a string")

    return int(value)


def _print_extraction_progress(
    index: int,
    total: int,
    item: GroundedExtractionBatchItem,
) -> None:
    outcome = item.outcome
    cache_status = "cached" if item.reused else "executed"

    print()
    print(f"[{index:02d}/{total:02d}] {outcome.source.title}")
    print(f"  unit:    {outcome.source.unit_id}")

    if isinstance(
        outcome,
        GroundedExtractionFailure,
    ):
        print(f"  outcome: {cache_status} failure")
        print(f"  stage:   {outcome.stage}")
        print(f"  error:   {outcome.error_type}: {outcome.error_message}")
        return

    print(f"  outcome: {cache_status} success")

    correction = outcome.correction

    if correction is None:
        print("  rejected initially: 0")
        print(f"  final statements:   {len(outcome.extraction.statements)}")
        return

    print(f"  valid initially:      {correction.initial_valid_statement_count}")
    print(f"  rejected initially:   {len(correction.requested_rejections)}")

    for rejection in correction.requested_rejections:
        print(f"    [{rejection.statement_index}] {rejection.error_message}")

    print(
        "  correction response:  "
        + ("received" if correction.response is not None else "unavailable")
    )
    print(f"  corrected valid:      {correction.corrected_valid_statement_count}")
    print(f"  still invalid:        {len(correction.remaining_rejections)}")

    for rejection in correction.remaining_rejections:
        print(f"    [{rejection.statement_index}] {rejection.error_message}")

    if correction.error_message is not None:
        print(f"  correction error:    {correction.error_type}: {correction.error_message}")

    print(f"  final statements:     {len(outcome.extraction.statements)}")


if __name__ == "__main__":
    main()
