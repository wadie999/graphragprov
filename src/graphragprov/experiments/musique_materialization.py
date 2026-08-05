"""Run configurable MuSiQue graph-materialization experiments."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from graphragprov.benchmarks.musique import MusiqueCase, collect_musique_source_units, select_cases
from graphragprov.config import musique_dataset_path
from graphragprov.experiments import (
    MUSIQUE_SOURCE_CATALOG_FILENAME,
    MusiqueMaterializationManifest,
    MusiqueSourceCatalog,
    validate_experiment_id,
    write_musique_materialization_manifest,
    write_musique_source_catalog,
)
from graphragprov.experiments.activation import (
    MusiqueExperimentActivation,
    clear_musique_experiment_activation,
    write_musique_experiment_activation,
)
from graphragprov.extraction import (
    GroundedExtractionBatchResult,
    load_or_run_grounded_extraction_batch,
)
from graphragprov.extraction.batch import GroundedExtractionBatchItem, GroundedExtractionProgress
from graphragprov.extraction.prompt import PROMPT_VERSION
from graphragprov.extraction.run import GenerateResponse, GroundedExtractionFailure
from graphragprov.graphdb import GraphDBClient, materialize_grounded_extractions
from graphragprov.metrics import measure_source_coverage
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator


@dataclass(frozen=True, slots=True)
class MusiqueExperimentConfiguration:
    """Configuration of one reproducible MuSiQue experiment."""

    experiment_id: str
    dataset_path: Path
    runs_root: Path
    hop_count: int
    limit: int
    answerable_only: bool
    model: str
    max_tokens: int
    cache_root: Path | None
    retry_failures: bool
    replace_repository: bool
    verbose: bool

    def __post_init__(self) -> None:
        validate_experiment_id(self.experiment_id)

        if self.hop_count <= 0:
            raise ValueError("hop count must be positive")

        if self.limit <= 0:
            raise ValueError("case limit must be positive")

        if self.max_tokens <= 0:
            raise ValueError("maximum token count must be positive")

        if not self.model.strip():
            raise ValueError("model name must not be empty")

    @property
    def run_root(self) -> Path:
        """Return the standard directory for this experiment."""

        return self.runs_root / self.experiment_id

    @property
    def manifest_path(self) -> Path:
        """Return the standard materialization-manifest path."""

        return self.run_root / "materialization.json"

    @property
    def source_catalog_path(self) -> Path:
        """Return the standard source-catalog path."""

        return self.run_root / MUSIQUE_SOURCE_CATALOG_FILENAME

    @property
    def resolved_cache_root(self) -> Path:
        """Return the explicit or standard extraction cache."""

        if self.cache_root is not None:
            return self.cache_root

        model_component = _safe_path_component(self.model)

        return self.run_root / "extractions" / PROMPT_VERSION / model_component


@dataclass(frozen=True, slots=True)
class MusiqueExperimentExecution:
    """Completed configurable experiment execution."""

    configuration: MusiqueExperimentConfiguration
    cases: tuple[MusiqueCase, ...]
    batch: GroundedExtractionBatchResult
    manifest: MusiqueMaterializationManifest


def parse_arguments() -> argparse.Namespace:
    """Parse the command-line adapter configuration."""

    parser = argparse.ArgumentParser(
        description=(
            "Select MuSiQue cases by hop count, extract their "
            "paragraphs, report provenance-grounded coverage, "
            "and materialize one discoverable experiment."
        )
    )
    parser.add_argument(
        "--experiment-id",
        required=True,
        help=(
            "Identifier used under runs/<experiment-id>. "
            "The existing API and interface discover this directory."
        ),
    )
    parser.add_argument(
        "--hop-count", required=True, type=int, help="Select cases with exactly this hop count."
    )
    parser.add_argument("--limit", type=int, default=5, help="Number of matching cases to select.")
    parser.add_argument(
        "--include-unanswerable",
        action="store_true",
        help=("Include unanswerable MuSiQue cases. The default selects answerable cases only."),
    )
    parser.add_argument(
        "--dataset-path", type=Path, help="Override the configured MuSiQue dataset path."
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Root containing discoverable experiment directories.",
    )
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=16_384)
    parser.add_argument(
        "--cache-root", type=Path, help=("Override the standard experiment extraction cache.")
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help=("Rerun cached failures while continuing to reuse cached successful extractions."),
    )
    parser.add_argument(
        "--replace-repository",
        action="store_true",
        help=(
            "Explicitly clear the current GraphDB repository before materializing this experiment."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Print extraction validation, correction, and complete "
            "coverage measurements after every source unit."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run one experiment through the command-line adapter."""

    arguments = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    try:
        configuration = MusiqueExperimentConfiguration(
            experiment_id=arguments.experiment_id,
            dataset_path=(
                arguments.dataset_path
                if arguments.dataset_path is not None
                else musique_dataset_path()
            ),
            runs_root=arguments.runs_root,
            hop_count=arguments.hop_count,
            limit=arguments.limit,
            answerable_only=not arguments.include_unanswerable,
            model=arguments.model,
            max_tokens=arguments.max_tokens,
            cache_root=arguments.cache_root,
            retry_failures=arguments.retry_failures,
            replace_repository=arguments.replace_repository,
            verbose=arguments.verbose,
        )

        graphdb = GraphDBClient.from_environment()

        generate_response = deepseek_generator(
            api_key=api_key, model=configuration.model, max_tokens=configuration.max_tokens
        )

        execution = run_musique_experiment(
            configuration, generate_response=generate_response, graphdb=graphdb
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    _print_execution_summary(execution)


def run_musique_experiment(
    configuration: MusiqueExperimentConfiguration,
    *,
    generate_response: GenerateResponse,
    graphdb: GraphDBClient,
) -> MusiqueExperimentExecution:
    """Execute and persist one configured MuSiQue experiment."""

    cases = select_cases(
        configuration.dataset_path,
        hop_count=configuration.hop_count,
        limit=configuration.limit,
        answerable_only=configuration.answerable_only,
    )

    if len(cases) != configuration.limit:
        raise ValueError(
            "requested "
            f"{configuration.limit} matching "
            f"{configuration.hop_count}-hop MuSiQue cases, "
            f"but found {len(cases)}"
        )

    source_units = collect_musique_source_units(cases)
    cache_root = configuration.resolved_cache_root

    existing_statement_count = _repository_statement_count(graphdb)

    if existing_statement_count > 0 and not configuration.replace_repository:
        raise ValueError(
            "GraphDB repository is not empty "
            f"({existing_statement_count} statements). "
            "Use --replace-repository to explicitly replace "
            "the currently materialized experiment."
        )

    _print_experiment_plan(
        configuration=configuration,
        cases=cases,
        unique_source_count=len(source_units),
        graphdb=graphdb,
    )

    references = _source_references(cases)

    batch = load_or_run_grounded_extraction_batch(
        source_units,
        cache_root=cache_root,
        generate_response=generate_response,
        retry_failures=configuration.retry_failures,
        progress=(_progress_printer(references) if configuration.verbose else None),
    )

    # From this point until the new marker is written, no experiment
    # is declared active. A failed replacement therefore cannot leave
    # an old marker pointing at partially replaced GraphDB contents.
    clear_musique_experiment_activation(configuration.runs_root)

    if existing_statement_count > 0:
        graphdb.clear_repository()

    materialization = materialize_grounded_extractions(batch.runs, graphdb=graphdb)

    manifest = MusiqueMaterializationManifest.from_execution(
        dataset_path=configuration.dataset_path,
        cases=cases,
        batch=batch,
        materialization=materialization,
        prompt_version=PROMPT_VERSION,
        model=configuration.model,
        max_tokens=configuration.max_tokens,
        cache_root=cache_root,
        graphdb=graphdb,
        existing_statement_count=existing_statement_count,
    )

    source_catalog = MusiqueSourceCatalog(sources=source_units)

    write_musique_source_catalog(configuration.source_catalog_path, source_catalog)
    write_musique_materialization_manifest(configuration.manifest_path, manifest)

    activation = MusiqueExperimentActivation.from_manifest(
        experiment_id=configuration.experiment_id, manifest=manifest
    )
    write_musique_experiment_activation(configuration.runs_root, activation)

    return MusiqueExperimentExecution(
        configuration=configuration, cases=cases, batch=batch, manifest=manifest
    )


def _print_experiment_plan(
    *,
    configuration: MusiqueExperimentConfiguration,
    cases: tuple[MusiqueCase, ...],
    unique_source_count: int,
    graphdb: GraphDBClient,
) -> None:
    print("Selected MuSiQue experiment:")
    print(f"  experiment:       {configuration.experiment_id}")
    print(f"  hop count:        {configuration.hop_count}")
    print(f"  answerable only:  {configuration.answerable_only}")
    print(f"  cases:            {len(cases)}")

    for case in cases:
        print(f"    {case.case_id} ({len(case.paragraphs)} paragraphs)")

    paragraph_count = sum(len(case.paragraphs) for case in cases)

    print(f"  paragraph uses:   {paragraph_count}")
    print(f"  unique sources:   {unique_source_count}")
    print(f"  extraction cache: {configuration.resolved_cache_root}")
    print(f"  GraphDB repository: {graphdb.repository}")


def _source_references(cases: tuple[MusiqueCase, ...]) -> dict[str, tuple[str, ...]]:
    references: defaultdict[str, list[str]] = defaultdict(list)

    for case in cases:
        for paragraph in case.paragraphs:
            references[paragraph.unit_id].append(f"{case.case_id}[paragraph={paragraph.index}]")

    return {unit_id: tuple(values) for unit_id, values in references.items()}


def _progress_printer(references: dict[str, tuple[str, ...]]) -> GroundedExtractionProgress:
    def print_progress(index: int, total: int, item: GroundedExtractionBatchItem) -> None:
        outcome = item.outcome
        cache_status = "cached" if item.reused else "executed"

        print()
        print(f"[{index:03d}/{total:03d}] {outcome.source.title}")
        print(f"  unit:       {outcome.source.unit_id}")

        source_references = references.get(outcome.source.unit_id, ())

        if source_references:
            print("  referenced: " + ", ".join(source_references))

        if isinstance(outcome, GroundedExtractionFailure):
            print(f"  outcome:    {cache_status} failure")
            print(f"  stage:      {outcome.stage}")
            print(f"  error:      {outcome.error_type}: {outcome.error_message}")
            return

        print(f"  outcome:    {cache_status} success")

        correction = outcome.correction

        if correction is None:
            print("  rejected initially: 0")
        else:
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

        coverage = measure_source_coverage(source=outcome.source, extraction=outcome.extraction)
        payload = coverage.to_dict()

        print("  coverage:")

        for key in (
            "character_coverage",
            "sentence_coverage",
            "longest_uncovered_text_region",
            "statement_density",
            "title_reliance",
        ):
            serialized = json.dumps(
                payload[key], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )

            print(f"    {key}: {serialized}")

    return print_progress


def _print_execution_summary(execution: MusiqueExperimentExecution) -> None:
    batch = execution.batch
    manifest = execution.manifest
    configuration = execution.configuration
    materialization = manifest.materialization

    print()
    print(f"Experiment {manifest.status}")
    print(f"Experiment ID:         {configuration.experiment_id}")
    print(f"Requested sources:     {len(batch.items):>6}")
    print(f"Successful extractions:{len(batch.runs):>6}")
    print(f"Failed extractions:    {len(batch.failures):>6}")
    print(f"New outcomes:          {batch.executed_count:>6}")
    print(f"Reused outcomes:       {batch.reused_count:>6}")
    print(f"Grounded statements:   {materialization.statement_count:>6}")
    print(f"Named graphs:          {materialization.source_count:>6}")

    if batch.failures:
        print()
        print("Extraction failures:")

        for failure in batch.failures:
            directory = configuration.resolved_cache_root / failure.source.unit_id

            print(f"  {failure.source.unit_id}")
            print(f"    title:    {failure.source.title}")
            print(f"    stage:    {failure.stage}")
            print(f"    error:    {failure.error_type}: {failure.error_message}")
            print(f"    response: {directory / 'response.txt'}")
            print(f"    report:   {directory / 'error.json'}")

    print()
    print(f"Source catalog:        {configuration.source_catalog_path}")
    print(f"Manifest:              {configuration.manifest_path}")
    print(f"Active experiment:     {configuration.runs_root / 'active_experiment.json'}")


def _safe_path_component(value: str) -> str:
    component = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")

    if not component:
        raise ValueError("model name cannot produce an empty cache-directory component")

    return component


def _repository_statement_count(graphdb: GraphDBClient) -> int:
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


if __name__ == "__main__":
    main()
