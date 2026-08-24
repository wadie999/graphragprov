from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TwoWikiEvidence:
    subject: str
    relation: str
    object: str
