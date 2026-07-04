from pathlib import Path

from graphragprov.benchmarks.musique.occurrence import MusiqueUnitOccurrence
from graphragprov.benchmarks.musique.reader import iter_cases
from graphragprov.benchmarks.musique.source_unit import MusiqueSourceUnit


def find_unit(path: Path, unit_id: str) -> MusiqueSourceUnit:
    """Find one source unit and every occurrence of it in MuSiQue."""

    text: str | None = None
    occurrences: list[MusiqueUnitOccurrence] = []

    for case in iter_cases(path):
        supporting_indices = set(case.gold_support_indices)

        for paragraph in case.paragraphs:
            if paragraph.unit_id != unit_id:
                continue

            if text is None:
                text = paragraph.text

            occurrences.append(
                MusiqueUnitOccurrence(
                    case_id=case.case_id,
                    paragraph_index=paragraph.index,
                    title=paragraph.title,
                    is_supporting=paragraph.index in supporting_indices,
                )
            )

    if text is None:
        raise KeyError(f"MuSiQue source unit not found: {unit_id}")

    return MusiqueSourceUnit(
        unit_id=unit_id,
        text=text,
        occurrences=tuple(occurrences),
    )
