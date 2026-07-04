from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MusiqueUnitOccurrence:
    case_id: str
    paragraph_index: int
    title: str
    is_supporting: bool
