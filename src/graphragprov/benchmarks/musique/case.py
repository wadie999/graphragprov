from dataclasses import dataclass

from graphragprov.benchmarks.musique.hop import MusiqueHop
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph


@dataclass(frozen=True, slots=True)
class MusiqueCase:
    case_id: str
    question: str
    answer: str
    answer_aliases: tuple[str, ...]
    answerable: bool
    paragraphs: tuple[MusiqueParagraph, ...]
    decomposition: tuple[MusiqueHop, ...]
    gold_support_indices: tuple[int, ...]

    @property
    def hop_count(self) -> int:
        return len(self.decomposition)

    def is_supporting(self, paragraph_index: int) -> bool:
        """Return whether a paragraph is a gold supporting paragraph."""

        return paragraph_index in self.gold_support_indices

    @property
    def supporting_paragraphs(self) -> tuple[MusiqueParagraph, ...]:
        """Return gold supporting paragraphs in dataset order."""

        return tuple(
            paragraph for paragraph in self.paragraphs if self.is_supporting(paragraph.index)
        )
