"""Run one real supervised 2Wiki graph extraction with DeepSeek."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.benchmarks.twowiki.reader import load_case
from graphragprov.config import twowiki_dataset_path
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionFailure,
    ReferenceGraphExtractionResult,
)
from graphragprov.experiments.multihop_fidelity.twowiki_graph import (
    construct_twowiki_reference_extractions,
)
from graphragprov.extraction.run import GroundedExtractionCorrection, GroundedExtractionRun
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator

DEFAULT_CASE_ID = "586507fa0bd911eba7f7acde48001122"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct one supervised 2Wiki reference graph with DeepSeek."
    )

    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=16_384)
    parser.add_argument("--max-source-attempts", type=int, default=3)
    parser.add_argument(
        "--artifacts", type=Path, default=Path("runs/single_twowiki_graph_extraction")
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    case = load_case(twowiki_dataset_path(), arguments.case_id)
    sources = collect_twowiki_source_units((case,))

    generate_response = deepseek_generator(
        api_key=api_key, model=arguments.model, max_tokens=arguments.max_tokens
    )

    print(f"Case:     {case.case_id}")
    print(f"Question: {case.question}")
    print(f"Answer:   {case.answer}")
    print()

    outcome = construct_twowiki_reference_extractions(
        case=case,
        sources=sources,
        generate_response=generate_response,
        max_attempts=arguments.max_source_attempts,
    )

    run_directory = arguments.artifacts / case.case_id
    run_directory.mkdir(parents=True, exist_ok=True)

    result_path = run_directory / "result.json"
    result_path.write_text(
        json.dumps(_outcome_to_dict(outcome), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if isinstance(outcome, ReferenceGraphExtractionFailure):
        print("GRAPH EXTRACTION FAILED")
        print(f"Source:   {outcome.source_unit_id}")
        print(f"Attempts: {outcome.attempt_count}")
        print(f"Error:    {outcome.failure.error_type}: {outcome.failure.error_message}")
        print(f"Artifact: {result_path}")

        raise SystemExit(1)

    print("GRAPH EXTRACTION SUCCEEDED")
    print()

    for item in outcome.items:
        print(
            f"Paragraph {item.paragraph_index}: "
            f"{item.run.source.title} "
            f"({len(item.run.extraction.statements)} statements, "
            f"{item.attempt_count} attempts)"
        )

        for statement in item.run.extraction.statements:
            print(
                "  "
                f"{statement.subject.value} "
                f"--{statement.predicate.value}--> "
                f"{statement.object.value}"
            )

        print()

    print(f"Total attempts: {outcome.attempt_count}")
    print(f"Retries:        {outcome.retry_count}")
    print(f"Artifact:       {result_path}")


def _outcome_to_dict(
    outcome: ReferenceGraphExtractionResult | ReferenceGraphExtractionFailure,
) -> dict[str, object]:
    if isinstance(outcome, ReferenceGraphExtractionFailure):
        return {
            "status": "failure",
            "paragraph_index": outcome.paragraph_index,
            "source_unit_id": outcome.source_unit_id,
            "attempt_count": outcome.attempt_count,
            "failure": {
                "source": {
                    "unit_id": outcome.failure.source.unit_id,
                    "title": outcome.failure.source.title,
                    "text": outcome.failure.source.text,
                },
                "prompt": outcome.failure.prompt,
                "response": outcome.failure.response,
                "stage": outcome.failure.stage,
                "error_type": outcome.failure.error_type,
                "error_message": outcome.failure.error_message,
            },
            "completed_items": [_run_item_to_dict(item) for item in outcome.completed_items],
        }

    return {
        "status": "success",
        "attempt_count": outcome.attempt_count,
        "retry_count": outcome.retry_count,
        "items": [_run_item_to_dict(item) for item in outcome.items],
    }


def _run_item_to_dict(item: object) -> dict[str, object]:
    from graphragprov.experiments.multihop_fidelity.graph import ReferenceSourceExtraction

    if not isinstance(item, ReferenceSourceExtraction):
        raise TypeError(f"unexpected reference extraction item: {type(item).__name__}")

    return {
        "paragraph_index": item.paragraph_index,
        "attempt_count": item.attempt_count,
        "run": _run_to_dict(item.run),
    }


def _run_to_dict(run: GroundedExtractionRun) -> dict[str, object]:
    return {
        "source": {
            "unit_id": run.source.unit_id,
            "title": run.source.title,
            "text": run.source.text,
        },
        "prompt": run.prompt,
        "response": run.response,
        "extraction": run.extraction.to_dict(),
        "correction": (_correction_to_dict(run.correction) if run.correction is not None else None),
    }


def _correction_to_dict(correction: GroundedExtractionCorrection) -> dict[str, object]:
    return {
        "prompt": correction.prompt,
        "response": correction.response,
        "requested_rejections": [
            rejection.to_dict() for rejection in correction.requested_rejections
        ],
        "initial_valid_statement_count": correction.initial_valid_statement_count,
        "corrected_valid_statement_count": correction.corrected_valid_statement_count,
        "remaining_rejections": [
            rejection.to_dict() for rejection in correction.remaining_rejections
        ],
        "error_type": correction.error_type,
        "error_message": correction.error_message,
    }


if __name__ == "__main__":
    main()
