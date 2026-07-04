from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MusiqueHop:
    hop_id: int
    question: str
    answer: str
    paragraph_support_index: int | None
