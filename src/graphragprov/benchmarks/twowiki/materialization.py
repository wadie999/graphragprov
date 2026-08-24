"""Construction of benchmark-independent source units from 2WikiMultiHopQA cases."""

from collections.abc import Iterable

from graphragprov.benchmarks.twowiki.case import TwoWikiCase
from graphragprov.benchmarks.twowiki.occurrence import TwoWikiUnitOccurrence
from graphragprov.benchmarks.twowiki.source_unit import TwoWikiSourceUnit


def collect_twowiki_source_units(cases: Iterable[TwoWikiCase]) -> tuple[TwoWikiSourceUnit, ...]:
    """Collect unique source units while preserving 2Wiki occurrences.

    All context paragraphs are included. Gold supporting facts are retained
    only as benchmark metadata and do not influence which source units are
    collected.
    """

    units_by_id: dict[str, TwoWikiSourceUnit] = {}
    unit_order: list[str] = []

    for case in cases:
        for paragraph in case.paragraphs:
            supporting_sentence_indices = tuple(
                fact.sentence_index
                for fact in case.supporting_facts
                if fact.title == paragraph.title
            )

            occurrence = TwoWikiUnitOccurrence(
                case_id=case.case_id,
                paragraph_index=paragraph.index,
                supporting_sentence_indices=supporting_sentence_indices,
            )

            existing = units_by_id.get(paragraph.unit_id)

            if existing is None:
                units_by_id[paragraph.unit_id] = TwoWikiSourceUnit(
                    unit_id=paragraph.unit_id,
                    title=paragraph.title,
                    text=paragraph.text,
                    occurrences=(occurrence,),
                )
                unit_order.append(paragraph.unit_id)
                continue

            if existing.title != paragraph.title or existing.text != paragraph.text:
                raise ValueError("identical 2Wiki source-unit IDs refer to different content")

            previous_occurrence = next(
                (
                    item
                    for item in existing.occurrences
                    if (
                        item.case_id == occurrence.case_id
                        and item.paragraph_index == occurrence.paragraph_index
                    )
                ),
                None,
            )

            if previous_occurrence is not None:
                if previous_occurrence != occurrence:
                    raise ValueError(
                        "conflicting metadata for 2Wiki paragraph "
                        f"{case.case_id!r}:{paragraph.index}"
                    )

                continue

            units_by_id[paragraph.unit_id] = TwoWikiSourceUnit(
                unit_id=existing.unit_id,
                title=existing.title,
                text=existing.text,
                occurrences=(*existing.occurrences, occurrence),
            )

    return tuple(units_by_id[unit_id] for unit_id in unit_order)
