from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TwoWikiUnitOccurrence:
    case_id: str
    paragraph_index: int
    supporting_sentence_indices: tuple[int, ...]
