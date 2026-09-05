"""Run one executable H0 2WikiMultiHopQA case."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from graphragprov.benchmarks.twowiki import load_case
from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.config import twowiki_dataset_path
from graphragprov.experiments.multihop_fidelity.config import (
    ArtifactOrigin,
    ExperimentConfig,
    QueryScope,
)
from graphragprov.experiments.multihop_fidelity.run_one import (
    RUN_ARTIFACT_FORMAT,
    CheckpointedGenerateResponse,
    RunOneArguments,
    VerboseGenerateResponse,
    VerboseH0Reporter,
    _build_run_artifact,
    _preflight,
    _print_outcome_summary,
    _print_plan,
    _write_json,
    _write_or_validate_configuration,
    ensure_result_artifact_target,
)
from graphragprov.experiments.multihop_fidelity.runner import H0CaseFailure, run_twowiki_h0_case
from graphragprov.experiments.multihop_fidelity.telemetry import ExperimentTelemetryRecorder
from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import SparqlProvClient
from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
    deepseek_generator,
)

DEFAULT_ARTIFACT_ROOT = Path("runs/multihop_fidelity/twowiki_h0")


def parse_arguments(argv: Sequence[str] | None = None) -> RunOneArguments:
    parser = argparse.ArgumentParser(
        description="Run one 2Wiki H0 reference graph/query/provenance case."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--query-scope",
        choices=(QueryScope.SUPPORT.value, QueryScope.REPOSITORY.value),
        default=QueryScope.SUPPORT.value,
    )
    parser.add_argument("--dataset-path", type=Path)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=16_384)
    parser.add_argument("--max-source-attempts", type=int, default=3)
    parser.add_argument("--max-query-attempts", type=int, default=5)
    parser.add_argument(
        "--llm-timeout-seconds",
        type=float,
        default=DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
        help="Maximum duration of one DeepSeek API request. Transport retries are disabled.",
    )
    parser.add_argument(
        "--reuse-llm-checkpoints",
        action="store_true",
        help="Reuse sequence- and prompt-matched responses from an interrupted execution.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Print extraction progress, provider usage, readable coverage metrics, "
            "frozen graph, query attempts, provenance, and stage timings."
        ),
    )

    namespace = parser.parse_args(argv)
    dataset_path = namespace.dataset_path if isinstance(namespace.dataset_path, Path) else None
    artifacts = namespace.artifacts

    if not isinstance(artifacts, Path):
        raise ValueError("artifact root must be a path")

    return RunOneArguments(
        case_id=str(namespace.case_id),
        query_scope=QueryScope(str(namespace.query_scope)),
        dataset_path=dataset_path,
        artifacts=artifacts,
        model=str(namespace.model),
        max_tokens=int(namespace.max_tokens),
        max_source_attempts=int(namespace.max_source_attempts),
        max_query_attempts=int(namespace.max_query_attempts),
        reuse_llm_checkpoints=bool(namespace.reuse_llm_checkpoints),
        verbose=bool(namespace.verbose),
        llm_timeout_seconds=float(namespace.llm_timeout_seconds),
    )


def main() -> None:
    arguments = parse_arguments()
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    dataset_path = (
        arguments.dataset_path if arguments.dataset_path is not None else twowiki_dataset_path()
    )
    case = load_case(dataset_path, arguments.case_id)

    if case.answer is None or not case.answer.strip():
        raise SystemExit("selected 2Wiki case does not contain a non-empty gold answer")

    if not case.evidences:
        raise SystemExit("selected 2Wiki case does not contain benchmark evidence relations")

    configuration = ExperimentConfig(
        graph_origin=ArtifactOrigin.REFERENCE,
        query_origin=ArtifactOrigin.REFERENCE,
        query_scope=arguments.query_scope,
        max_source_attempts=arguments.max_source_attempts,
        max_query_attempts=arguments.max_query_attempts,
    )

    root = arguments.artifacts / case.case_id / arguments.query_scope.value
    result_path = root / "result.json"
    try:
        ensure_result_artifact_target(
            result_path, reuse_llm_checkpoints=arguments.reuse_llm_checkpoints
        )
    except (FileExistsError, ValueError) as error:
        raise SystemExit(str(error)) from error
    root.mkdir(parents=True, exist_ok=True)
    run_configuration = _run_configuration_payload(
        case_id=case.case_id, dataset_path=dataset_path, arguments=arguments
    )
    _write_or_validate_configuration(root / "run-config.json", run_configuration)

    graphdb = GraphDBClient.from_environment()
    npcs = SparqlProvClient.from_environment()

    _print_plan(
        case_id=case.case_id,
        question=case.question,
        expected_answer=case.answer,
        hop_count=len(case.evidences),
        dataset_path=dataset_path,
        arguments=arguments,
        root=root,
        graphdb=graphdb,
        npcs=npcs,
    )
    _preflight(graphdb=graphdb, npcs=npcs)

    telemetry = ExperimentTelemetryRecorder()

    graph_provider = deepseek_generator(
        api_key=api_key,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        observe_call=telemetry.deepseek_observer(operation="graph.reference"),
        timeout_seconds=arguments.llm_timeout_seconds,
    )
    query_provider = deepseek_generator(
        api_key=api_key,
        model=arguments.model,
        max_tokens=arguments.max_tokens,
        observe_call=telemetry.deepseek_observer(operation="query.reference"),
        timeout_seconds=arguments.llm_timeout_seconds,
    )

    graph_checkpoint = CheckpointedGenerateResponse(
        root=root / "llm-checkpoints" / "graph",
        generate_response=graph_provider,
        reuse_existing=arguments.reuse_llm_checkpoints,
    )
    query_checkpoint = CheckpointedGenerateResponse(
        root=root / "llm-checkpoints" / "query",
        generate_response=query_provider,
        reuse_existing=arguments.reuse_llm_checkpoints,
    )

    graph_generate = VerboseGenerateResponse(
        operation="graph.reference",
        generate_response=graph_checkpoint,
        telemetry=telemetry,
        enabled=arguments.verbose,
    )
    query_generate = VerboseGenerateResponse(
        operation="query.reference",
        generate_response=query_checkpoint,
        telemetry=telemetry,
        enabled=arguments.verbose,
    )
    reporter = VerboseH0Reporter(enabled=arguments.verbose)
    sources = collect_twowiki_source_units((case,))

    outcome = run_twowiki_h0_case(
        case=case,
        sources=sources,
        configuration=configuration,
        graph_generate_response=graph_generate,
        query_generate_response=query_generate,
        graphdb=graphdb,
        npcs=npcs,
        telemetry=telemetry,
        progress_sink=reporter if arguments.verbose else None,
    )

    artifact = _build_run_artifact(
        outcome=outcome,
        dataset_path=dataset_path,
        arguments=arguments,
        graph_generate=graph_checkpoint,
        query_generate=query_checkpoint,
        graphdb=graphdb,
        npcs=npcs,
    )
    artifact["benchmark"] = "2wiki"

    _write_json(result_path, artifact)

    _print_outcome_summary(
        outcome=outcome,
        result_path=result_path,
        graph_generate=graph_checkpoint,
        query_generate=query_checkpoint,
        verbose=arguments.verbose,
    )

    if isinstance(outcome, H0CaseFailure):
        raise SystemExit(1)


def _run_configuration_payload(
    *, case_id: str, dataset_path: Path, arguments: RunOneArguments
) -> dict[str, object]:
    return {
        "format": RUN_ARTIFACT_FORMAT,
        "benchmark": "2wiki",
        "case_id": case_id,
        "dataset_path": str(dataset_path.resolve()),
        "graph_origin": ArtifactOrigin.REFERENCE.value,
        "query_origin": ArtifactOrigin.REFERENCE.value,
        "query_scope": arguments.query_scope.value,
        "model": arguments.model,
        "max_tokens": arguments.max_tokens,
        "max_source_attempts": arguments.max_source_attempts,
        "max_query_attempts": arguments.max_query_attempts,
        "llm_timeout_seconds": arguments.llm_timeout_seconds,
    }


if __name__ == "__main__":
    main()
