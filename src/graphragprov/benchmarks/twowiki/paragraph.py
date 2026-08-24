from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TwoWikiParagraph:
    index: int
    title: str
    sentences: tuple[str, ...]
