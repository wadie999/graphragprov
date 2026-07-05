"""Deterministic localization of model-facing evidence references."""

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.span import TextSegment, TextSpan


def localize_evidence(
    source: SourceUnit,
    *,
    segment: TextSegment,
    quote: str,
    occurrence: int,
) -> TextSpan:
    """Resolve one exact evidence reference into character offsets."""

    if not quote:
        raise ValueError("evidence quote must not be empty")

    if occurrence < 1:
        raise ValueError("evidence occurrence must be greater than or equal to one")

    content = source.title if segment is TextSegment.TITLE else source.text

    search_start = 0
    current_occurrence = 0

    while True:
        start = content.find(quote, search_start)

        if start == -1:
            break

        current_occurrence += 1

        if current_occurrence == occurrence:
            span = TextSpan(
                segment=segment,
                start=start,
                end=start + len(quote),
                quote=quote,
            )
            span.validate_against(source)
            return span

        search_start = start + 1

    if current_occurrence == 0:
        raise ValueError(f"quote {quote!r} does not occur in source segment {segment.value!r}")

    raise ValueError(
        f"quote {quote!r} occurs {current_occurrence} time(s) in source "
        f"segment {segment.value!r}; occurrence {occurrence} does not exist"
    )
