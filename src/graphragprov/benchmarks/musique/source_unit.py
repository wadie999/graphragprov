from dataclasses import dataclass

from graphragprov.benchmarks.musique.occurrence import MusiqueUnitOccurrence


@dataclass(frozen=True, slots=True)
class MusiqueSourceUnit:
    unit_id: str
    title: str
    text: str
    occurrences: tuple[MusiqueUnitOccurrence, ...]
