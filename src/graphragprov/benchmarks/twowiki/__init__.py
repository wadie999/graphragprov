"""2WikiMultiHopQA dataset reader."""

from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph
from graphragprov.benchmarks.twowiki.reader import iter_cases, load_case, read_first_case

__all__ = [
    "TwoWikiCase",
    "TwoWikiEvidence",
    "TwoWikiParagraph",
    "TwoWikiSupportingFact",
    "iter_cases",
    "load_case",
    "read_first_case",
]
