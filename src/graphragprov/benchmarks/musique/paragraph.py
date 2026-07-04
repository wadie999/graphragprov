from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MusiqueParagraph:
    index: int
    title: str
    text: str
