"""MuSiQue dataset reader."""

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph
from graphragprov.benchmarks.musique.reader import load_case

__all__ = ["MusiqueCase", "MusiqueParagraph", "load_case"]
