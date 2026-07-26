import pytest

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.localization import localize_evidence
from graphragprov.extraction.span import TextSegment, TextSpan

SOURCE = SourceUnit(
    unit_id="u_test",
    title="Albert Einstein",
    text="Einstein was born in Ulm. Einstein later lived in Bern.",
)


def test_localizes_title_evidence() -> None:
    span = localize_evidence(
        SOURCE, segment=TextSegment.TITLE, quote="Albert Einstein", occurrence=1
    )

    assert span == TextSpan(segment=TextSegment.TITLE, start=0, end=15, quote="Albert Einstein")


def test_localizes_first_text_occurrence() -> None:
    span = localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="Einstein", occurrence=1)

    assert span == TextSpan(segment=TextSegment.TEXT, start=0, end=8, quote="Einstein")


def test_localizes_second_text_occurrence() -> None:
    span = localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="Einstein", occurrence=2)

    assert span == TextSpan(segment=TextSegment.TEXT, start=26, end=34, quote="Einstein")


def test_occurrences_are_counted_inside_the_selected_segment() -> None:
    source = SourceUnit(
        unit_id="u_test", title="Publix", text="Publix is commonly known as Publix."
    )

    title_span = localize_evidence(source, segment=TextSegment.TITLE, quote="Publix", occurrence=1)
    text_span = localize_evidence(source, segment=TextSegment.TEXT, quote="Publix", occurrence=2)

    assert title_span.start == 0
    assert text_span.start == 28


def test_matching_is_case_sensitive() -> None:
    with pytest.raises(ValueError, match="does not occur"):
        localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="einstein", occurrence=1)


def test_rejects_empty_quote() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="", occurrence=1)


def test_rejects_non_positive_occurrence() -> None:
    with pytest.raises(ValueError, match="greater than or equal to one"):
        localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="Einstein", occurrence=0)


def test_rejects_missing_quote() -> None:
    with pytest.raises(ValueError, match="does not occur"):
        localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="Paris", occurrence=1)


def test_rejects_occurrence_out_of_range() -> None:
    with pytest.raises(ValueError, match=r"occurs 2 time\(s\).*occurrence 3 does not exist"):
        localize_evidence(SOURCE, segment=TextSegment.TEXT, quote="Einstein", occurrence=3)
