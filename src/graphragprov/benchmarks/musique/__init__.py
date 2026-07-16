"""MuSiQue dataset reader and source-unit adapter."""

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.hop import MusiqueHop
from graphragprov.benchmarks.musique.lookup import find_unit
from graphragprov.benchmarks.musique.materialization import (
    collect_musique_source_units,
)
from graphragprov.benchmarks.musique.occurrence import (
    MusiqueUnitOccurrence,
)
from graphragprov.benchmarks.musique.paragraph import (
    MusiqueParagraph,
)
from graphragprov.benchmarks.musique.reader import (
    iter_cases,
    load_case,
    read_first_case,
)
from graphragprov.benchmarks.musique.result import (
    MusiqueCaseResult,
    MusiqueCaseResultStatus,
)
from graphragprov.benchmarks.musique.selection import (
    select_cases,
)
from graphragprov.benchmarks.musique.source_unit import (
    MusiqueSourceUnit,
)

__all__ = [
    "MusiqueCase",
    "MusiqueCaseResult",
    "MusiqueCaseResultStatus",
    "MusiqueHop",
    "MusiqueParagraph",
    "MusiqueSourceUnit",
    "MusiqueUnitOccurrence",
    "collect_musique_source_units",
    "find_unit",
    "iter_cases",
    "load_case",
    "read_first_case",
    "select_cases",
]
