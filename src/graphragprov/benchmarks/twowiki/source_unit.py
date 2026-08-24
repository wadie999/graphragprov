from dataclasses import dataclass

from graphragprov.benchmarks.twowiki.occurrence import TwoWikiUnitOccurrence
from graphragprov.domain.source_unit import SourceUnit


@dataclass(frozen=True, slots=True)
class TwoWikiSourceUnit(SourceUnit):
    occurrences: tuple[TwoWikiUnitOccurrence, ...]
