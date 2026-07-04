import json
from pathlib import Path
from typing import Any

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.paragraph import MusiqueParagraph


def read_first_case(path: Path) -> MusiqueCase:
    """Read the first non-empty case from a MuSiQue JSONL file."""

    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                return _parse_case(json.loads(line))

    raise ValueError(f"MuSiQue dataset is empty: {path}")


def load_case(path: Path, case_id: str) -> MusiqueCase:
    """Read one MuSiQue case identified by its ID."""

    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            row: dict[str, Any] = json.loads(line)

            if row["id"] == case_id:
                return _parse_case(row)

    raise KeyError(f"MuSiQue case not found: {case_id}")


def _parse_case(row: dict[str, Any]) -> MusiqueCase:
    raw_paragraphs = sorted(row["paragraphs"], key=lambda paragraph: paragraph["idx"])

    paragraphs = tuple(
        MusiqueParagraph(
            index=paragraph["idx"],
            title=paragraph["title"],
            text=paragraph["paragraph_text"],
        )
        for paragraph in raw_paragraphs
    )

    gold_support_indices = tuple(
        paragraph["idx"] for paragraph in raw_paragraphs if paragraph["is_supporting"]
    )

    return MusiqueCase(
        case_id=row["id"],
        question=row["question"],
        answer=row["answer"],
        answerable=row["answerable"],
        paragraphs=paragraphs,
        gold_support_indices=gold_support_indices,
    )
