from dataclasses import dataclass

from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph


@dataclass(frozen=True, slots=True)
class TwoWikiSupportingFact:
    title: str
    sentence_index: int


@dataclass(frozen=True, slots=True)
class TwoWikiCase:
    case_id: str
    question_type: str
    question: str

    paragraphs: tuple[TwoWikiParagraph, ...]
    supporting_facts: tuple[TwoWikiSupportingFact, ...]

    evidences: tuple[TwoWikiEvidence, ...]
    evidence_ids: tuple[TwoWikiEvidence, ...] | None

    answer: str | None
    answer_id: str | None

    entity_ids: tuple[str, ...]
