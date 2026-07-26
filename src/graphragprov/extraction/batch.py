"""Batch execution and reuse of grounded extractions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from graphragprov.domain import SourceUnit
from graphragprov.extraction.artifacts import (
    CachedGroundedExtraction,
    extraction_artifact_directory,
    has_grounded_extraction_outcome,
    load_grounded_extraction_outcome,
    load_or_run_grounded_extraction,
    save_grounded_extraction_outcome,
)
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionFailure,
    GroundedExtractionOutcome,
    GroundedExtractionRun,
    run_grounded_extraction_outcome,
)


@dataclass(frozen=True, slots=True)
class GroundedExtractionBatchItem:
    """One extraction outcome together with its cache status."""

    outcome: GroundedExtractionOutcome
    reused: bool


GroundedExtractionProgress = Callable[[int, int, GroundedExtractionBatchItem], None]


@dataclass(frozen=True, slots=True)
class GroundedExtractionBatchResult:
    """Ordered outcomes produced for one unique-source batch."""

    items: tuple[GroundedExtractionBatchItem, ...]

    @property
    def runs(self) -> tuple[GroundedExtractionRun, ...]:
        """Return all successful extraction runs."""

        return tuple(
            item.outcome for item in self.items if isinstance(item.outcome, GroundedExtractionRun)
        )

    @property
    def failures(self) -> tuple[GroundedExtractionFailure, ...]:
        """Return all failed extraction outcomes."""

        return tuple(
            item.outcome
            for item in self.items
            if isinstance(item.outcome, GroundedExtractionFailure)
        )

    @property
    def executed_count(self) -> int:
        """Return the number of outcomes created in this call."""

        return sum(not item.reused for item in self.items)

    @property
    def reused_count(self) -> int:
        """Return the number of outcomes loaded from artifacts."""

        return sum(item.reused for item in self.items)


def load_or_run_grounded_extractions(
    sources: Iterable[SourceUnit], *, cache_root: Path, generate_response: GenerateResponse
) -> tuple[CachedGroundedExtraction, ...]:
    """Strictly extract each unique source unit once.

    Provider and response-validation failures are propagated.
    """

    results: list[CachedGroundedExtraction] = []

    for source in _unique_sources(sources):
        results.append(
            load_or_run_grounded_extraction(
                source, cache_root=cache_root, generate_response=generate_response
            )
        )

    return tuple(results)


def load_or_run_grounded_extraction_batch(
    sources: Iterable[SourceUnit],
    *,
    cache_root: Path,
    generate_response: GenerateResponse,
    retry_failures: bool = False,
    progress: GroundedExtractionProgress | None = None,
) -> GroundedExtractionBatchResult:
    """Extract every unique source while preserving failures.

    Completed successes are always reused. Cached failures are reused unless
    ``retry_failures`` is true. Every newly executed outcome is persisted
    immediately.
    """

    unique_sources = _unique_sources(sources)

    items: list[GroundedExtractionBatchItem] = []

    total = len(unique_sources)

    for index, source in enumerate(unique_sources, start=1):
        directory = extraction_artifact_directory(cache_root, source)

        if has_grounded_extraction_outcome(directory):
            cached_outcome = load_grounded_extraction_outcome(source, directory)

            should_retry = retry_failures and isinstance(cached_outcome, GroundedExtractionFailure)

            if should_retry:
                outcome = run_grounded_extraction_outcome(source, generate_response)

                save_grounded_extraction_outcome(outcome, directory)

                reused = False
            else:
                outcome = cached_outcome
                reused = True
        else:
            outcome = run_grounded_extraction_outcome(source, generate_response)

            save_grounded_extraction_outcome(outcome, directory)

            reused = False

        item = GroundedExtractionBatchItem(outcome=outcome, reused=reused)

        items.append(item)

        if progress is not None:
            progress(index, total, item)

    return GroundedExtractionBatchResult(items=tuple(items))


def _unique_sources(sources: Iterable[SourceUnit]) -> tuple[SourceUnit, ...]:
    """Deduplicate sources while preserving first-seen order."""

    sources_by_id: dict[str, SourceUnit] = {}

    for source in sources:
        existing = sources_by_id.get(source.unit_id)

        if existing is not None:
            if existing != source:
                raise ValueError("identical source-unit IDs refer to different content")

            continue

        sources_by_id[source.unit_id] = source

    return tuple(sources_by_id.values())
