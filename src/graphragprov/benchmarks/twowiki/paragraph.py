from dataclasses import dataclass

from graphragprov.hashing import source_unit_id


@dataclass(frozen=True, slots=True)
class TwoWikiParagraph:
    index: int
    title: str
    sentences: tuple[str, ...]

    @property
    def text(self) -> str:
        """Return the canonical paragraph text used by GraphRAGProv."""

        return " ".join(self.sentences)

    @property
    def unit_id(self) -> str:
        return source_unit_id(title=self.title, text=self.text)

    @property
    def short_unit_id(self) -> str:
        """Return a short source-unit identifier for human display."""

        return self.unit_id[:14]
