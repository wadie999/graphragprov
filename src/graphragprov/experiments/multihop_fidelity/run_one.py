"""Run one executable H0 MuSiQue case."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from graphragprov.benchmarks.musique import (
    MusiqueSourceUnit,
    collect_musique_source_units,
    load_case,
)
from graphragprov.config import musique_dataset_path
from graphragprov.experiments.multihop_fidelity.config import (
    ArtifactOrigin,
    ExperimentConfig,
    QueryScope,
)
from graphragprov.experiments.multihop_fidelity.measurements import (
    FrozenGraphMeasurements,
    ReferenceExtractionMeasurements,
)
from graphragprov.experiments.multihop_fidelity.query import ReferenceQueryGeneration
from graphragprov.experiments.multihop_fidelity.runner import (
    H0CaseFailure,
    H0CaseOutcome,
    H0CaseResult,
    run_h0_case,
)
from graphragprov.experiments.multihop_fidelity.telemetry import ExperimentTelemetryRecorder
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionFailure,
    GroundedExtractionRun,
)
from graphragprov.graphdb import GraphDBClient
from graphragprov.metrics import measure_source_coverage
from graphragprov.npcs import NPCSClient
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator
from graphragprov.qaagent import QAQueryAttempt

RUN_ARTIFACT_FORMAT = "multihop-fidelity-h0-run-v1"


@dataclass(frozen=True, slots=True)
class RunOneArguments:
    """Command-line configuration for one H0 execution."""

    case_id: str
    query_scope: QueryScope
    dataset_path: Path | None
    artifacts: Path
    model: str
    max_tokens: int
    max_source_attempts: int
    max_query_attempts: int
    reuse_llm_checkpoints: bool
    verbose: bool = False

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case ID must not be empty")

        if not self.model.strip():
            raise ValueError("model name must not be empty")

        if self.max_tokens < 1:
            raise ValueError("maximum token count must be positive")

        if self.max_source_attempts < 1:
            raise ValueError("maximum source attempts must be positive")

        if self.max_query_attempts < 1:
            raise ValueError("maximum query attempts must be positive")


class CheckpointedGenerateResponse:
    """Checkpoint paid LLM calls by call sequence and exact prompt."""

    def __init__(
        self, *, root: Path, generate_response: GenerateResponse, reuse_existing: bool
    ) -> None:
        self.root = root
        self.generate_response = generate_response
        self.reuse_existing = reuse_existing
        self.executed_count = 0
        self.reused_count = 0
        self._call_index = 0

    @property
    def call_count(self) -> int:
        return self._call_index

    def __call__(self, prompt: str) -> str:
        self._call_index += 1

        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        self.root.mkdir(parents=True, exist_ok=True)

        slot_prefix = f"{self._call_index:04d}-"

        expected_folder = self.root / f"{slot_prefix}{digest}"

        existing_slots = sorted(
            path
            for path in self.root.iterdir()
            if (path.is_dir() and path.name.startswith(slot_prefix))
        )

        if len(existing_slots) > 1:
            raise RuntimeError(f"multiple LLM checkpoints exist for call {self._call_index}")

        if existing_slots:
            existing_folder = existing_slots[0]

            if existing_folder != expected_folder:
                raise RuntimeError(
                    "LLM checkpoint sequence "
                    "diverged at call "
                    f"{self._call_index}: "
                    "the stored prompt does not "
                    "match the prompt produced "
                    "by this execution"
                )

        folder = expected_folder

        prompt_path = folder / "prompt.txt"

        response_path = folder / "response.txt"

        if folder.exists():
            if not prompt_path.is_file():
                raise RuntimeError("LLM checkpoint slot exists without its prompt")

            stored_prompt = prompt_path.read_text(encoding="utf-8")

            if stored_prompt != prompt:
                raise RuntimeError("LLM checkpoint contains a different prompt")

            if response_path.is_file():
                if not self.reuse_existing:
                    raise RuntimeError(
                        "an LLM response checkpoint "
                        "already exists for call "
                        f"{self._call_index}; use "
                        "--reuse-llm-checkpoints "
                        "to resume this execution "
                        "or choose a fresh "
                        "--artifacts directory"
                    )

                self.reused_count += 1

                return response_path.read_text(encoding="utf-8")

        else:
            folder.mkdir(parents=True, exist_ok=False)

            prompt_path.write_text(prompt, encoding="utf-8")

        response = self.generate_response(prompt)

        response_path.write_text(response, encoding="utf-8")

        self.executed_count += 1

        return response


class VerboseGenerateResponse:
    """Show one LLM call immediately after it completes."""

    def __init__(
        self,
        *,
        operation: str,
        generate_response: (CheckpointedGenerateResponse),
        telemetry: (ExperimentTelemetryRecorder),
        enabled: bool,
    ) -> None:
        self.operation = operation
        self.generate_response = generate_response
        self.telemetry = telemetry
        self.enabled = enabled

    def __call__(self, prompt: str) -> str:
        before = self.telemetry.snapshot()

        before_executed = self.generate_response.executed_count

        before_reused = self.generate_response.reused_count

        call_index = self.generate_response.call_count + 1

        if self.enabled:
            _print(f"    [LLM {self.operation} #{call_index}] sending...")

        try:
            response = self.generate_response(prompt)
        except Exception as error:
            after = self.telemetry.snapshot()

            if self.enabled:
                self._print_result(
                    before_call_count=len(before.llm_calls),
                    after=after,
                    before_executed=(before_executed),
                    before_reused=(before_reused),
                    error=error,
                )

            raise

        after = self.telemetry.snapshot()

        if self.enabled:
            self._print_result(
                before_call_count=len(before.llm_calls),
                after=after,
                before_executed=(before_executed),
                before_reused=(before_reused),
                error=None,
            )

        return response

    def _print_result(
        self,
        *,
        before_call_count: int,
        after: object,
        before_executed: int,
        before_reused: int,
        error: Exception | None,
    ) -> None:
        telemetry = self.telemetry.snapshot()

        if self.generate_response.reused_count > before_reused:
            _print("      checkpoint: reused")
            return

        new_calls = telemetry.llm_calls[before_call_count:]

        if new_calls:
            call = new_calls[-1]

            _print(f"      provider: {call.elapsed_seconds:.3f}s | model={call.model}")

            if call.usage is not None:
                usage = call.usage

                cache = ""

                if (
                    usage.cached_input_tokens is not None
                    and usage.uncached_input_tokens is not None
                ):
                    cache = (
                        " | cached="
                        f"{usage.cached_input_tokens}"
                        " | uncached="
                        f"{usage.uncached_input_tokens}"
                    )

                _print(
                    "      tokens:   "
                    f"in={usage.input_tokens}"
                    f" | out={usage.output_tokens}"
                    f" | total={usage.total_tokens}"
                    f"{cache}"
                )

            else:
                _print("      tokens:   provider usage unavailable")

            if not call.succeeded:
                _print(f"      provider failure: {call.error_type}: {call.error_message}")

        elif self.generate_response.executed_count > before_executed:
            _print("      provider call executed; no telemetry observation found")

        if error is not None:
            _print(f"      call failed: {type(error).__name__}: {error}")


class VerboseH0Reporter:
    """Render progress events from the H0 kernel."""

    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, event: str, payload: dict[str, object]) -> None:
        if not self.enabled:
            return

        if event == ("graph.extraction.started"):
            source_count = payload.get("source_count")

            _section("REFERENCE GRAPH EXTRACTION")

            _print(f"supporting sources: {source_count}")

            return

        if event == ("graph.source.started"):
            source = payload.get("source")

            if not isinstance(source, MusiqueSourceUnit):
                return

            position = payload.get("source_position")

            count = payload.get("source_count")

            paragraph_index = payload.get("paragraph_index")

            _print("")

            _print(f"[GRAPH {position}/{count}] paragraph={paragraph_index} title={source.title!r}")

            _print(f"  source unit: {source.unit_id}")

            _print(f"  text chars:  {len(source.text)}")

            return

        if event == ("graph.source.attempt.started"):
            attempt_index = payload.get("attempt_index")

            max_attempts = payload.get("max_attempts")

            _print(f"  whole-source attempt: {attempt_index}/{max_attempts}")

            validation_error = payload.get("validation_error")

            if isinstance(validation_error, str):
                _print(f"  previous failure: {validation_error}")

            return

        if event == ("graph.source.attempt.failed"):
            failure = payload.get("failure")

            if isinstance(failure, GroundedExtractionFailure):
                _print("  extraction attempt: FAILED")

                _print(f"    stage: {failure.stage}")

                _print(f"    error: {failure.error_type}: {failure.error_message}")

            return

        if event == ("graph.source.completed"):
            run = payload.get("run")

            if not isinstance(run, GroundedExtractionRun):
                return

            _print("  extraction: ACCEPTED")

            _print(f"  statements: {len(run.extraction.statements)}")

            if run.correction is None:
                _print("  targeted correction: none")

            else:
                correction = run.correction

                _print("  targeted correction:")

                _print(f"    rejected initially: {len(correction.requested_rejections)}")

                _print(f"    valid before correction: {correction.initial_valid_statement_count}")

                _print(f"    corrected valid: {correction.corrected_valid_statement_count}")

                _print(f"    remaining rejected: {len(correction.remaining_rejections)}")

            coverage = measure_source_coverage(
                source=run.source, extraction=(run.extraction)
            ).to_dict()

            _print("  coverage:")

            for metric_name in (
                "character_coverage",
                "sentence_coverage",
                "longest_uncovered_text_region",
                "statement_density",
                "title_reliance",
            ):
                if metric_name not in coverage:
                    continue

                _print(f"    {metric_name}: {_compact_json(coverage[metric_name])}")

            return

        if event == ("graph.extraction.measured"):
            measurements = payload.get("measurements")

            if not isinstance(measurements, ReferenceExtractionMeasurements):
                return

            _print("")

            _print("[REFERENCE EXTRACTION TOTALS]")

            _print(f"  sources: {measurements.source_count}")

            _print(f"  statement occurrences: {measurements.statement_occurrence_count}")

            _print(f"  whole-source attempts: {measurements.whole_source_attempt_count}")

            _print(f"  whole-source retries: {measurements.whole_source_retry_count}")

            _print(f"  targeted corrections: {measurements.targeted_correction_count}")

            _print(f"  initial rejections: {measurements.initial_rejection_count}")

            _print(f"  corrected valid: {measurements.corrected_valid_statement_count}")

            _print(f"  remaining rejections: {measurements.remaining_rejection_count}")

            return

        if event == ("graph.materialization.started"):
            _print("")

            _print("[MATERIALIZATION]")

            _print("  writing grounded extractions to GraphDB...")

            return

        if event == ("graph.materialization.completed"):
            _print("  materialization: COMPLETE")
            return

        if event == "graph.frozen":
            measurements = payload.get("measurements")

            graph_ntriples = payload.get("graph_ntriples")

            if not isinstance(measurements, FrozenGraphMeasurements):
                return

            _section("FROZEN SEMANTIC GRAPH")

            _print(f"named source graphs:   {measurements.named_graph_count}")

            _print(f"semantic triples:      {measurements.semantic_triple_count}")

            _print(f"resource nodes:        {measurements.resource_node_count}")

            _print(f"entity nodes:          {measurements.entity_node_count}")

            _print(f"literal values:        {measurements.literal_value_count}")

            _print(f"predicates:            {measurements.predicate_count}")

            if isinstance(graph_ntriples, str):
                _print("")
                _print("N-Triples:")

                for line in graph_ntriples.splitlines():
                    _print(f"  {line}")

            return

        if event == ("query.attempt.started"):
            attempt_index = payload.get("attempt_index")

            max_attempts = payload.get("max_attempts")

            _section(f"QUERY ATTEMPT {attempt_index}/{max_attempts}")

            if payload.get("has_feedback"):
                _print("retry includes feedback from previous attempt")

            return

        if event == ("query.validation.failed"):
            _print("deterministic validation: FAILED")

            _print(f"reason: {payload.get('error')}")

            _print("action: retrying with validator feedback")

            return

        if event == "query.generated":
            generation = payload.get("generation")

            execution_sparql = payload.get("execution_sparql")

            if not isinstance(generation, ReferenceQueryGeneration):
                return

            _print("deterministic validation: PASSED")

            _print("")
            _print("matched triples:")

            for triple in generation.plan.matched_triples:
                _print(f"  - {triple}")

            _print("")
            _print("semantic SPARQL:")

            for line in generation.plan.semantic_sparql.splitlines():
                _print(f"  {line}")

            if isinstance(execution_sparql, str):
                _print("")
                _print("execution SPARQL:")

                for line in execution_sparql.splitlines():
                    _print(f"  {line}")

            return

        if event == "query.executed":
            observed = payload.get("observed_answers")

            expected = payload.get("expected_answer")

            correct = payload.get("answer_correct")

            _print("")
            _print("GraphDB execution:")

            _print(f"  observed answers: {observed}")

            _print(f"  expected answer:  {expected!r}")

            _print(f"  answer correct:   {correct}")

            if correct is False:
                _print("  action: retrying with execution feedback")

            return

        if event == ("provenance.started"):
            _print("")
            _print("[PROVENANCE]")

            _print("  executing NPCS rewrite and provenance decoding...")

            return

        if event == ("provenance.completed"):
            provenance = payload.get("provenance")

            support_covered = payload.get("gold_support_covered")

            if not isinstance(provenance, QAQueryAttempt):
                return

            _print(f"  status: {provenance.provenance_status}")

            derivation_count = sum(
                len(answer.decoded.derivations) for answer in provenance.answer_provenances
            )

            _print(f"  derivations: {derivation_count}")

            source_titles = sorted(
                {
                    occurrence.source.title
                    for answer in provenance.answer_provenances
                    for derivation in answer.decoded.derivations
                    for occurrence in derivation.occurrences
                }
            )

            _print(f"  provenance sources: {source_titles}")

            _print(f"  gold support covered: {support_covered}")

            return

        if event == ("query.gold_support.missing"):
            _print("  answer is correct but gold support is incomplete")

            _print("  action: retrying query")


def parse_arguments(argv: Sequence[str] | None = None) -> RunOneArguments:
    parser = argparse.ArgumentParser(
        description=("Run one MuSiQue H0 reference graph/query/provenance case.")
    )

    parser.add_argument("--case-id", required=True)

    parser.add_argument(
        "--query-scope",
        choices=(QueryScope.SUPPORT.value, QueryScope.REPOSITORY.value),
        default=(QueryScope.SUPPORT.value),
    )

    parser.add_argument("--dataset-path", type=Path)

    parser.add_argument("--artifacts", type=Path, default=Path("runs/multihop_fidelity/h0"))

    parser.add_argument("--model", default=(DEFAULT_DEEPSEEK_MODEL))

    parser.add_argument("--max-tokens", type=int, default=16_384)

    parser.add_argument("--max-source-attempts", type=int, default=3)

    parser.add_argument("--max-query-attempts", type=int, default=5)

    parser.add_argument(
        "--reuse-llm-checkpoints",
        action="store_true",
        help=("Reuse sequence- and prompt-matched LLM responses from an interrupted execution."),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help=(
            "Print extraction progress, exact "
            "provider usage, coverage metrics, "
            "frozen graph, query attempts, "
            "answers, provenance, and stage "
            "timings in real time."
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
    )


def main() -> None:
    arguments = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    dataset_path = (
        arguments.dataset_path if arguments.dataset_path is not None else musique_dataset_path()
    )

    case = load_case(dataset_path, arguments.case_id)

    if not case.answerable:
        raise SystemExit("selected MuSiQue case is not answerable")

    configuration = ExperimentConfig(
        graph_origin=(ArtifactOrigin.REFERENCE),
        query_origin=(ArtifactOrigin.REFERENCE),
        query_scope=(arguments.query_scope),
        max_source_attempts=(arguments.max_source_attempts),
        max_query_attempts=(arguments.max_query_attempts),
    )

    root = arguments.artifacts / case.case_id / arguments.query_scope.value

    result_path = root / "result.json"

    if result_path.is_file():
        raise SystemExit(
            "result artifact already exists: "
            f"{result_path}. "
            "Choose a fresh --artifacts "
            "directory for a new "
            "scientific run."
        )

    root.mkdir(parents=True, exist_ok=True)

    run_configuration = _run_configuration_payload(
        case_id=case.case_id, dataset_path=dataset_path, arguments=arguments
    )

    _write_or_validate_configuration(root / "run-config.json", run_configuration)

    graphdb = GraphDBClient.from_environment()

    npcs = NPCSClient.from_environment()

    _print_plan(
        case_id=case.case_id,
        question=case.question,
        expected_answer=case.answer,
        hop_count=case.hop_count,
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
        max_tokens=(arguments.max_tokens),
        observe_call=(telemetry.deepseek_observer(operation=("graph.reference"))),
    )

    query_provider = deepseek_generator(
        api_key=api_key,
        model=arguments.model,
        max_tokens=(arguments.max_tokens),
        observe_call=(telemetry.deepseek_observer(operation=("query.reference"))),
    )

    graph_checkpoint = CheckpointedGenerateResponse(
        root=(root / "llm-checkpoints" / "graph"),
        generate_response=(graph_provider),
        reuse_existing=(arguments.reuse_llm_checkpoints),
    )

    query_checkpoint = CheckpointedGenerateResponse(
        root=(root / "llm-checkpoints" / "query"),
        generate_response=(query_provider),
        reuse_existing=(arguments.reuse_llm_checkpoints),
    )

    graph_generate = VerboseGenerateResponse(
        operation="graph.reference",
        generate_response=(graph_checkpoint),
        telemetry=telemetry,
        enabled=arguments.verbose,
    )

    query_generate = VerboseGenerateResponse(
        operation="query.reference",
        generate_response=(query_checkpoint),
        telemetry=telemetry,
        enabled=arguments.verbose,
    )

    reporter = VerboseH0Reporter(enabled=arguments.verbose)

    sources = collect_musique_source_units((case,))

    outcome = run_h0_case(
        case=case,
        sources=sources,
        configuration=configuration,
        graph_generate_response=(graph_generate),
        query_generate_response=(query_generate),
        graphdb=graphdb,
        npcs=npcs,
        telemetry=telemetry,
        progress_sink=(reporter if arguments.verbose else None),
    )

    artifact = _build_run_artifact(
        outcome=outcome,
        dataset_path=dataset_path,
        arguments=arguments,
        graph_generate=(graph_checkpoint),
        query_generate=(query_checkpoint),
        graphdb=graphdb,
        npcs=npcs,
    )

    _write_json(result_path, artifact)

    _print_outcome_summary(
        outcome=outcome,
        result_path=result_path,
        graph_generate=(graph_checkpoint),
        query_generate=(query_checkpoint),
        verbose=arguments.verbose,
    )

    if isinstance(outcome, H0CaseFailure):
        raise SystemExit(1)


def _preflight(*, graphdb: GraphDBClient, npcs: NPCSClient) -> None:
    graphdb.query("SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }")

    npcs.rewrite("SELECT ?s WHERE { ?s ?p ?o }")

    _print("preflight: GraphDB OK; NPCS OK")


def _run_configuration_payload(
    *, case_id: str, dataset_path: Path, arguments: RunOneArguments
) -> dict[str, object]:
    return {
        "format": (RUN_ARTIFACT_FORMAT),
        "case_id": case_id,
        "dataset_path": str(dataset_path.resolve()),
        "graph_origin": (ArtifactOrigin.REFERENCE.value),
        "query_origin": (ArtifactOrigin.REFERENCE.value),
        "query_scope": (arguments.query_scope.value),
        "model": arguments.model,
        "max_tokens": (arguments.max_tokens),
        "max_source_attempts": (arguments.max_source_attempts),
        "max_query_attempts": (arguments.max_query_attempts),
    }


def _write_or_validate_configuration(path: Path, configuration: dict[str, object]) -> None:
    if not path.is_file():
        _write_json(path, configuration)
        return

    existing = cast(object, json.loads(path.read_text(encoding="utf-8")))

    if existing != configuration:
        raise RuntimeError(
            "existing run-config.json does not match the requested execution configuration"
        )


def _build_run_artifact(
    *,
    outcome: H0CaseOutcome,
    dataset_path: Path,
    arguments: RunOneArguments,
    graph_generate: (CheckpointedGenerateResponse),
    query_generate: (CheckpointedGenerateResponse),
    graphdb: GraphDBClient,
    npcs: NPCSClient,
) -> dict[str, object]:
    return {
        "format": (RUN_ARTIFACT_FORMAT),
        "dataset_path": str(dataset_path.resolve()),
        "model": arguments.model,
        "max_tokens": (arguments.max_tokens),
        "graphdb_repository_endpoint": (graphdb.repository_endpoint),
        "npcs_rewrite_endpoint": (npcs.rewrite_endpoint),
        "llm_checkpoints": {
            "graph": {
                "executed": (graph_generate.executed_count),
                "reused": (graph_generate.reused_count),
            },
            "query": {
                "executed": (query_generate.executed_count),
                "reused": (query_generate.reused_count),
            },
        },
        "outcome": (outcome.to_dict()),
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _print_plan(
    *,
    case_id: str,
    question: str,
    expected_answer: str,
    hop_count: int,
    dataset_path: Path,
    arguments: RunOneArguments,
    root: Path,
    graphdb: GraphDBClient,
    npcs: NPCSClient,
) -> None:
    _print("")
    _print("H0 one-case execution")
    _print(f"  case:          {case_id}")
    _print(f"  hops:          {hop_count}")
    _print(f"  question:      {question}")
    _print(f"  expected:      {expected_answer}")
    _print(f"  query scope:   {arguments.query_scope.value}")
    _print(f"  model:         {arguments.model}")
    _print(f"  max tokens:    {arguments.max_tokens}")
    _print(f"  verbose:       {arguments.verbose}")
    _print(f"  dataset:       {dataset_path}")
    _print(f"  artifacts:     {root}")
    _print(f"  GraphDB:       {graphdb.repository_endpoint}")
    _print(f"  NPCS:          {npcs.rewrite_endpoint}")


def _print_outcome_summary(
    *,
    outcome: H0CaseOutcome,
    result_path: Path,
    graph_generate: (CheckpointedGenerateResponse),
    query_generate: (CheckpointedGenerateResponse),
    verbose: bool,
) -> None:
    telemetry = outcome.telemetry

    _print("")
    _print("=" * 72)

    if isinstance(outcome, H0CaseResult):
        _print("H0 CASE PASSED")
    else:
        _print("H0 CASE FAILED")

    _print("=" * 72)

    _print(f"case:                  {outcome.case_id}")

    _print(f"result:                {result_path}")

    _print(f"graph LLM executed:    {graph_generate.executed_count}")

    _print(f"graph LLM reused:      {graph_generate.reused_count}")

    _print(f"query LLM executed:    {query_generate.executed_count}")

    _print(f"query LLM reused:      {query_generate.reused_count}")

    _print(f"provider usage complete: {telemetry.usage_complete}")

    _print(f"input tokens:          {telemetry.input_tokens}")

    _print(f"output tokens:         {telemetry.output_tokens}")

    _print(f"total tokens:          {telemetry.total_tokens}")

    _print(f"cached input tokens:   {telemetry.cached_input_tokens}")

    _print(f"uncached input tokens: {telemetry.uncached_input_tokens}")

    _print(f"cumulative LLM seconds: {telemetry.cumulative_llm_seconds:.3f}")

    if graph_generate.reused_count or query_generate.reused_count:
        _print("")
        _print(
            "NOTE: token totals above "
            "describe provider calls made "
            "in this invocation only; reused "
            "checkpoints were not billed again."
        )

    if isinstance(outcome, H0CaseResult):
        _print("")

        _print(
            f"statement occurrences: {outcome.extraction_measurements.statement_occurrence_count}"
        )

        _print(f"semantic triples:      {outcome.graph_measurements.semantic_triple_count}")

        _print(f"entity nodes:          {outcome.graph_measurements.entity_node_count}")

        _print(f"literal values:        {outcome.graph_measurements.literal_value_count}")

        _print(f"predicates:            {outcome.graph_measurements.predicate_count}")

        _print(f"query attempts:        {len(outcome.query_attempts)}")

        _print(f"provenance status:     {outcome.final_provenance.provenance_status}")

        _print(f"gold support covered:  {outcome.query_attempts[-1].gold_support_covered}")

    else:
        _print("")

        _print(f"failure stage:         {outcome.stage}")

        _print(f"failure:               {outcome.error_type}: {outcome.error_message}")

    if verbose:
        _print("")
        _print("[STAGE TIMINGS]")

        for stage in telemetry.stages:
            _print(f"  {stage.stage} [attempt={stage.attempt_index}]: {stage.elapsed_seconds:.3f}s")


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))


def _section(title: str) -> None:
    _print("")
    _print("=" * 72)
    _print(title)
    _print("=" * 72)


def _print(text: str) -> None:
    print(text, flush=True)


if __name__ == "__main__":
    main()
