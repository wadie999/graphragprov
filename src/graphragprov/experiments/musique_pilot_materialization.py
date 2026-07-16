"""Materialize one 2-hop, 3-hop, and 4-hop MuSiQue case."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    collect_musique_source_units,
    select_cases,
)
from graphragprov.config import musique_dataset_path
from graphragprov.extraction import (
    GroundedExtractionBatchResult,
    load_or_run_grounded_extraction_batch,
)
from graphragprov.extraction.prompt import PROMPT_VERSION
from graphragprov.graphdb import (
    GraphDBClient,
    GraphMaterializationSummary,
    materialize_grounded_extractions,
)
from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    deepseek_generator,
)

_MANIFEST_FORMAT = "musique-pilot-materialization-v2"


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
    )

    materialization = materialize_grounded_extractions(
        batch.runs,
        graphdb=graphdb,
    )

    manifest = _build_manifest(
        dataset_path=dataset_path,
        cases=cases,
        batch=batch,
        materialization=materialization,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        cache_root=cache_root,
        graphdb=graphdb,
        existing_statement_count=(existing_statement_count),
    )

    _write_manifest(
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


def _build_manifest(
    *,
    dataset_path: Path,
    cases: tuple[MusiqueCase, ...],
    batch: GroundedExtractionBatchResult,
    materialization: GraphMaterializationSummary,
    model: str,
    max_tokens: int,
    cache_root: Path,
    graphdb: GraphDBClient,
    existing_statement_count: int,
) -> dict[str, object]:
    status = "complete" if not batch.failures else "partial"

    return {
        "format": _MANIFEST_FORMAT,
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(dataset_path),
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "max_tokens": max_tokens,
        "cache_root": str(cache_root),
        "graphdb": {
            "base_url": graphdb.base_url,
            "repository": graphdb.repository,
            "statements_before_run": (existing_statement_count),
        },
        "cases": [
            {
                "case_id": case.case_id,
                "hop_count": case.hop_count,
                "question": case.question,
                "answer": case.answer,
                "answer_aliases": list(case.answer_aliases),
                "answerable": case.answerable,
                "paragraph_indices": [paragraph.index for paragraph in case.paragraphs],
                "gold_support_indices": list(case.gold_support_indices),
            }
            for case in cases
        ],
        "paragraph_occurrence_count": sum(len(case.paragraphs) for case in cases),
        "requested_source_count": len(batch.items),
        "successful_extraction_count": len(batch.runs),
        "failed_extraction_count": len(batch.failures),
        "new_outcome_count": (batch.executed_count),
        "reused_outcome_count": (batch.reused_count),
        "source_unit_ids": [item.outcome.source.unit_id for item in batch.items],
        "failures": [
            {
                "unit_id": failure.source.unit_id,
                "title": failure.source.title,
                "stage": failure.stage,
                "error_type": (failure.error_type),
                "error_message": (failure.error_message),
                "response_available": (failure.response is not None),
                "response_path": str(cache_root / failure.source.unit_id / "response.txt"),
                "error_path": str(cache_root / failure.source.unit_id / "error.json"),
            }
            for failure in batch.failures
        ],
        "materialization": (materialization.to_dict()),
    }


def _write_manifest(
    path: Path,
    manifest: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            cast(object, manifest),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
