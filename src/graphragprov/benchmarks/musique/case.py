from dataclasses import dataclass

from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph


@dataclass(frozen=True, slots=True)
class MusiqueCase:
    case_id: str
    question: str
    answer: str
    answerable: bool
    paragraphs: tuple[MusiqueParagraph, ...]
    gold_support_indices: tuple[int, ...]
