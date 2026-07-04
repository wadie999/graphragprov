"""MuSiQue dataset reader."""

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.hop import MusiqueHop
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph
from graphragprov.benchmarks.musique.reader import load_case, read_first_case

__all__ = [
    "MusiqueCase",
    "MusiqueHop",
    "MusiqueParagraph",
    "load_case",
    "read_first_case",
]
