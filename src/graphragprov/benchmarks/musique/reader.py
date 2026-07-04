import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.hop import MusiqueHop
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph


def iter_cases(path: Path) -> Iterator[MusiqueCase]:
    """Yield MuSiQue cases in their original dataset order."""

    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            row: dict[str, Any] = json.loads(line)
            yield _parse_case(row)


def read_first_case(path: Path) -> MusiqueCase:
    """Read the first non-empty case from a MuSiQue JSONL file."""

    try:
        return next(iter_cases(path))
    except StopIteration as error:
        raise ValueError(f"MuSiQue dataset is empty: {path}") from error


def load_case(path: Path, case_id: str) -> MusiqueCase:
    """Read one MuSiQue case identified by its ID."""

    for case in iter_cases(path):
        if case.case_id == case_id:
            return case

    raise KeyError(f"MuSiQue case not found: {case_id}")


def _parse_case(row: dict[str, Any]) -> MusiqueCase:
    raw_paragraphs = sorted(
        row["paragraphs"],
        key=lambda paragraph: paragraph["idx"],
    )

    paragraphs = tuple(
        MusiqueParagraph(
            index=paragraph["idx"],
            title=paragraph["title"],
            text=paragraph["paragraph_text"],
        )
        for paragraph in raw_paragraphs
    )

    decomposition = tuple(
        MusiqueHop(
            hop_id=hop["id"],
            question=hop["question"],
            answer=hop["answer"],
            paragraph_support_index=hop["paragraph_support_idx"],
        )
        for hop in row["question_decomposition"]
    )

    gold_support_indices = tuple(
        paragraph["idx"] for paragraph in raw_paragraphs if paragraph["is_supporting"]
    )

    return MusiqueCase(
        case_id=row["id"],
        question=row["question"],
        answer=row["answer"],
        answer_aliases=tuple(row.get("answer_aliases", [])),
        answerable=row["answerable"],
        paragraphs=paragraphs,
        decomposition=decomposition,
        gold_support_indices=gold_support_indices,
    )
