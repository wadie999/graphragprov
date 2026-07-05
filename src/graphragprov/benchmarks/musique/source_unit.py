from dataclasses import dataclass

from graphragprov.benchmarks.musique.occurrence import MusiqueUnitOccurrence
from graphragprov.domain.source_unit import SourceUnit


@dataclass(frozen=True, slots=True)
class MusiqueSourceUnit(SourceUnit):
    occurrences: tuple[MusiqueUnitOccurrence, ...]
