"""Construction of benchmark-independent source units from MuSiQue cases."""

from collections.abc import Iterable

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.occurrence import (
    MusiqueUnitOccurrence,
)
from graphragprov.benchmarks.musique.source_unit import (
    MusiqueSourceUnit,
)


def collect_musique_source_units(
    cases: Iterable[MusiqueCase],
) -> tuple[MusiqueSourceUnit, ...]:
    """Collect unique source units while preserving MuSiQue occurrences.

    All paragraphs are included. Gold supporting labels are retained only as
    benchmark metadata and do not influence which source units are extracted.
    """

    units_by_id: dict[str, MusiqueSourceUnit] = {}
    unit_order: list[str] = []

    for case in cases:
        for paragraph in case.paragraphs:
            occurrence = MusiqueUnitOccurrence(
                case_id=case.case_id,
                paragraph_index=paragraph.index,
                is_supporting=case.is_supporting(paragraph.index),
            )

            existing = units_by_id.get(paragraph.unit_id)

            if existing is None:
                units_by_id[paragraph.unit_id] = MusiqueSourceUnit(
                    unit_id=paragraph.unit_id,
                    title=paragraph.title,
                    text=paragraph.text,
                    occurrences=(occurrence,),
                )
                unit_order.append(paragraph.unit_id)
                continue

            if existing.title != paragraph.title or existing.text != paragraph.text:
                raise ValueError("identical MuSiQue source-unit IDs refer to different content")

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
                        "conflicting metadata for MuSiQue "
                        f"paragraph {case.case_id!r}:"
                        f"{paragraph.index}"
                    )

                continue

            units_by_id[paragraph.unit_id] = MusiqueSourceUnit(
                unit_id=existing.unit_id,
                title=existing.title,
                text=existing.text,
                occurrences=(
                    *existing.occurrences,
                    occurrence,
                ),
            )

    return tuple(units_by_id[unit_id] for unit_id in unit_order)
