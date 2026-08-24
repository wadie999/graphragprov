import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph


def iter_cases(path: Path) -> Iterator[TwoWikiCase]:
    """Yield 2WikiMultiHopQA cases in their original dataset order."""

    with path.open(encoding="utf-8") as file:
        rows: list[dict[str, Any]] = json.load(file)

    for row in rows:
        yield _parse_case(row)


def read_first_case(path: Path) -> TwoWikiCase:
    """Read the first case from a 2WikiMultiHopQA JSON file."""

    try:
        return next(iter_cases(path))
    except StopIteration as error:
        raise ValueError(f"2WikiMultiHopQA dataset is empty: {path}") from error


def load_case(path: Path, case_id: str) -> TwoWikiCase:
    """Read one 2WikiMultiHopQA case identified by its ID."""

    for case in iter_cases(path):
        if case.case_id == case_id:
            return case

    raise KeyError(f"2WikiMultiHopQA case not found: {case_id}")


def _parse_case(row: dict[str, Any]) -> TwoWikiCase:
    paragraphs = tuple(
        TwoWikiParagraph(index=index, title=title, sentences=tuple(sentences))
        for index, (title, sentences) in enumerate(row["context"])
    )

    supporting_facts = tuple(
        TwoWikiSupportingFact(title=title, sentence_index=sentence_index)
        for title, sentence_index in row.get("supporting_facts", [])
    )

    evidences = tuple(
        TwoWikiEvidence(subject=subject, relation=relation, object=object_)
        for subject, relation, object_ in row.get("evidences", [])
    )

    raw_evidence_ids = row.get("evidences_id")

    evidence_ids = (
        tuple(
            TwoWikiEvidence(subject=subject, relation=relation, object=object_)
            for subject, relation, object_ in raw_evidence_ids
        )
        if raw_evidence_ids is not None
        else None
    )

    raw_entity_ids = row.get("entity_ids", "")

    return TwoWikiCase(
        case_id=row["_id"],
        question_type=row["type"],
        question=row["question"],
        paragraphs=paragraphs,
        supporting_facts=supporting_facts,
        evidences=evidences,
        evidence_ids=evidence_ids,
        answer=row.get("answer"),
        answer_id=row.get("answer_id"),
        entity_ids=tuple(raw_entity_ids.split("_")) if raw_entity_ids else (),
    )
