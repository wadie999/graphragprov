"""Reference graph construction for 2WikiMultiHopQA cases."""

from __future__ import annotations

from graphragprov.benchmarks.twowiki.case import TwoWikiCase
from graphragprov.benchmarks.twowiki.selection import supporting_paragraphs
from graphragprov.benchmarks.twowiki.source_unit import TwoWikiSourceUnit
from graphragprov.domain import SourceUnit
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionOutcome,
    ReferenceGraphProgressSink,
    ReferenceGraphSource,
    construct_reference_source_extractions,
)
from graphragprov.experiments.prompts import build_twowiki_graph_source_prompt
from graphragprov.extraction.run import GenerateResponse, GroundedExtractionRun


def construct_twowiki_reference_extractions(
    *,
    case: TwoWikiCase,
    sources: tuple[TwoWikiSourceUnit, ...],
    generate_response: GenerateResponse,
    max_attempts: int,
    progress_sink: ReferenceGraphProgressSink | None = None,
) -> ReferenceGraphExtractionOutcome:
    """Construct supervised reference extractions for one 2Wiki case."""

    reference_sources = tuple(
        ReferenceGraphSource(paragraph_index=paragraph.index, source_unit_id=paragraph.unit_id)
        for paragraph in supporting_paragraphs(case)
    )

    def build_prompt(
        source: SourceUnit,
        paragraph_index: int,
        accepted_runs: tuple[GroundedExtractionRun, ...],
        validation_error: str | None,
    ) -> str:
        return build_twowiki_graph_source_prompt(
            case=case,
            source=source,
            paragraph_index=paragraph_index,
            accepted_runs=accepted_runs,
            validation_error=validation_error,
        )

    return construct_reference_source_extractions(
        support_sources=reference_sources,
        sources=sources,
        build_prompt=build_prompt,
        generate_response=generate_response,
        max_attempts=max_attempts,
        progress_sink=progress_sink,
    )
