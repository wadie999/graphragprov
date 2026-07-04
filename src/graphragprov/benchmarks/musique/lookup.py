from pathlib import Path

from graphragprov.benchmarks.musique.occurrence import MusiqueUnitOccurrence
from graphragprov.benchmarks.musique.reader import iter_cases
from graphragprov.benchmarks.musique.source_unit import MusiqueSourceUnit


def find_unit(path: Path, unit_reference: str) -> MusiqueSourceUnit:
    """Find a source unit from its full ID or a unique ID prefix."""

    if not unit_reference.startswith("u_") or len(unit_reference) < 10:
        raise ValueError(
            "A source-unit reference must start with 'u_' and contain at least 8 hash characters."
        )

    matched_id: str | None = None
    text: str | None = None
    occurrences: list[MusiqueUnitOccurrence] = []

    for case in iter_cases(path):
        for paragraph in case.paragraphs:
            if not paragraph.unit_id.startswith(unit_reference):
                continue

            if matched_id is None:
                matched_id = paragraph.unit_id
                text = paragraph.text
            elif paragraph.unit_id != matched_id:
                raise ValueError(f"Ambiguous MuSiQue source-unit prefix: {unit_reference}")

            occurrences.append(
                MusiqueUnitOccurrence(
                    case_id=case.case_id,
                    paragraph_index=paragraph.index,
                    title=paragraph.title,
                    is_supporting=case.is_supporting(paragraph.index),
                )
            )

    if matched_id is None or text is None:
        raise KeyError(f"MuSiQue source unit not found: {unit_reference}")

    return MusiqueSourceUnit(
        unit_id=matched_id,
        text=text,
        occurrences=tuple(occurrences),
    )
