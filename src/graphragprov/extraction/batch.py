"""Batch execution and reuse of grounded extractions."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from graphragprov.domain import SourceUnit
from graphragprov.extraction.artifacts import (
    CachedGroundedExtraction,
    load_or_run_grounded_extraction,
)
from graphragprov.extraction.run import GenerateResponse


def load_or_run_grounded_extractions(
    sources: Iterable[SourceUnit],
    *,
    cache_root: Path,
    generate_response: GenerateResponse,
) -> tuple[CachedGroundedExtraction, ...]:
    """Extract each unique source unit once, preserving first-seen order."""

    sources_by_id: dict[str, SourceUnit] = {}
    results: list[CachedGroundedExtraction] = []

    for source in sources:
        existing = sources_by_id.get(source.unit_id)

        if existing is not None:
            if existing != source:
                raise ValueError("identical source-unit IDs refer to different content")

            continue

        sources_by_id[source.unit_id] = source

        results.append(
            load_or_run_grounded_extraction(
                source,
                cache_root=cache_root,
                generate_response=generate_response,
            )
        )

    return tuple(results)
