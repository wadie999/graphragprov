"""Reference graph construction for multi-hop fidelity experiments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from graphragprov.benchmarks.musique import MusiqueCase, MusiqueParagraph, MusiqueSourceUnit
from graphragprov.experiments.prompts import build_musique_graph_source_prompt
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionFailure,
    GroundedExtractionRun,
    run_grounded_extraction_outcome_with_prompt,
)

ReferenceGraphProgressSink: TypeAlias = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class ReferenceSourceExtraction:
    paragraph_index: int
    attempt_count: int
    run: GroundedExtractionRun

    def __post_init__(self) -> None:
        if self.attempt_count < 1:
            raise ValueError("attempt count must be at least 1")


@dataclass(frozen=True, slots=True)
class ReferenceGraphExtractionResult:
    items: tuple[ReferenceSourceExtraction, ...]

    @property
    def runs(self) -> tuple[GroundedExtractionRun, ...]:
        return tuple(item.run for item in self.items)

    @property
    def attempt_count(self) -> int:
        return sum(item.attempt_count for item in self.items)

    @property
    def retry_count(self) -> int:
        return sum(item.attempt_count - 1 for item in self.items)


@dataclass(frozen=True, slots=True)
class ReferenceGraphExtractionFailure:
    paragraph_index: int
    source_unit_id: str
    attempt_count: int
    failure: GroundedExtractionFailure
    completed_items: tuple[ReferenceSourceExtraction, ...]

    def __post_init__(self) -> None:
        if self.attempt_count < 1:
            raise ValueError("attempt count must be at least 1")

    @property
    def completed_runs(self) -> tuple[GroundedExtractionRun, ...]:
        return tuple(item.run for item in self.completed_items)


ReferenceGraphExtractionOutcome: TypeAlias = (
    ReferenceGraphExtractionResult | ReferenceGraphExtractionFailure
)


def reference_supporting_paragraphs(case: MusiqueCase) -> tuple[MusiqueParagraph, ...]:
    """Return supporting paragraphs in decomposition dependency order."""

    paragraphs_by_index = {paragraph.index: paragraph for paragraph in case.paragraphs}

    indices: list[int] = []

    for hop in case.decomposition:
        paragraph_index = hop.paragraph_support_index

        if paragraph_index is None:
            raise ValueError("every decomposition hop must have a supporting paragraph")

        if paragraph_index not in paragraphs_by_index:
            raise ValueError(f"supporting paragraph {paragraph_index} does not occur in the case")

        if paragraph_index not in indices:
            indices.append(paragraph_index)

    return tuple(paragraphs_by_index[index] for index in indices)


def construct_reference_extractions(
    *,
    case: MusiqueCase,
    sources: tuple[MusiqueSourceUnit, ...],
    generate_response: GenerateResponse,
    max_attempts: int,
    progress_sink: (ReferenceGraphProgressSink | None) = None,
) -> ReferenceGraphExtractionOutcome:
    """Construct reference extractions over gold supporting paragraphs."""

    if max_attempts < 1:
        raise ValueError("max attempts must be at least 1")

    sources_by_id: dict[str, MusiqueSourceUnit] = {}

    for candidate_source in sources:
        existing = sources_by_id.get(candidate_source.unit_id)

        if existing is not None and existing != candidate_source:
            raise ValueError("identical source-unit IDs refer to different content")

        sources_by_id[candidate_source.unit_id] = candidate_source

    support_paragraphs = reference_supporting_paragraphs(case)

    completed: list[ReferenceSourceExtraction] = []

    source_count = len(support_paragraphs)

    for source_position, paragraph in enumerate(support_paragraphs, start=1):
        support_source = sources_by_id.get(paragraph.unit_id)

        if support_source is None:
            raise ValueError(
                f"supporting source {paragraph.unit_id!r} is missing from supplied sources"
            )

        _emit_progress(
            progress_sink,
            "graph.source.started",
            {
                "source_position": (source_position),
                "source_count": (source_count),
                "paragraph_index": (paragraph.index),
                "source": support_source,
            },
        )

        previous_failure: GroundedExtractionFailure | None = None

        for attempt_index in range(1, max_attempts + 1):
            validation_error = (
                None
                if previous_failure is None
                else (f"{previous_failure.error_type}: {previous_failure.error_message}")
            )

            _emit_progress(
                progress_sink,
                "graph.source.attempt.started",
                {
                    "source_position": (source_position),
                    "source_count": (source_count),
                    "paragraph_index": (paragraph.index),
                    "source": (support_source),
                    "attempt_index": (attempt_index),
                    "max_attempts": (max_attempts),
                    "validation_error": (validation_error),
                },
            )

            prompt = build_musique_graph_source_prompt(
                case=case,
                source=support_source,
                paragraph_index=(paragraph.index),
                accepted_runs=[item.run for item in completed],
                validation_error=(validation_error),
            )

            outcome = run_grounded_extraction_outcome_with_prompt(
                support_source, prompt=prompt, generate_response=(generate_response)
            )

            if isinstance(outcome, GroundedExtractionRun):
                item = ReferenceSourceExtraction(
                    paragraph_index=(paragraph.index), attempt_count=(attempt_index), run=outcome
                )

                completed.append(item)

                _emit_progress(
                    progress_sink,
                    "graph.source.completed",
                    {
                        "source_position": (source_position),
                        "source_count": (source_count),
                        "paragraph_index": (paragraph.index),
                        "source": (support_source),
                        "attempt_index": (attempt_index),
                        "run": outcome,
                    },
                )

                break

            previous_failure = outcome

            _emit_progress(
                progress_sink,
                "graph.source.attempt.failed",
                {
                    "source_position": (source_position),
                    "source_count": (source_count),
                    "paragraph_index": (paragraph.index),
                    "source": (support_source),
                    "attempt_index": (attempt_index),
                    "failure": outcome,
                },
            )

        else:
            assert previous_failure is not None

            failure = ReferenceGraphExtractionFailure(
                paragraph_index=(paragraph.index),
                source_unit_id=(support_source.unit_id),
                attempt_count=(max_attempts),
                failure=(previous_failure),
                completed_items=tuple(completed),
            )

            _emit_progress(
                progress_sink,
                "graph.source.exhausted",
                {
                    "source_position": (source_position),
                    "source_count": (source_count),
                    "paragraph_index": (paragraph.index),
                    "source": (support_source),
                    "failure": failure,
                },
            )

            return failure

    return ReferenceGraphExtractionResult(items=tuple(completed))


def _emit_progress(
    sink: (ReferenceGraphProgressSink | None), event: str, payload: dict[str, object]
) -> None:
    if sink is not None:
        sink(event, payload)
