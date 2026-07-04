from dataclasses import dataclass

from graphragprov.benchmarks.musique.hop import MusiqueHop
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph


@dataclass(frozen=True, slots=True)
class MusiqueCase:
    case_id: str
    question: str
    answer: str
    answerable: bool
    paragraphs: tuple[MusiqueParagraph, ...]
    decomposition: tuple[MusiqueHop, ...]
    gold_support_indices: tuple[int, ...]

    @property
    def hop_count(self) -> int:
        return len(self.decomposition)
