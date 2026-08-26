import json
from pathlib import Path

import pytest

from graphragprov.experiments.multihop_fidelity.twowiki_subset import (
    build_twowiki_subset,
    read_case_ids,
    write_twowiki_subset,
)


def _dataset_rows() -> list[dict[str, object]]:
    return [
        {"_id": "case-a", "question": "A?", "context": [["A", ["Text A."]]]},
        {"_id": "case-b", "question": "B?", "context": [["B", ["Text B."]]]},
        {"_id": "case-c", "question": "C?", "context": [["C", ["Text C."]]]},
    ]


def test_read_case_ids_ignores_comments_and_preserves_order(tmp_path: Path) -> None:
    ids_file = tmp_path / "cohort.txt"

    ids_file.write_text("# frozen cohort\ncase-c\n\ncase-a\n", encoding="utf-8")

    assert read_case_ids(ids_file) == ("case-c", "case-a")


def test_build_subset_preserves_exact_rows_in_cohort_order(tmp_path: Path) -> None:
    dataset = tmp_path / "train.json"
    rows = _dataset_rows()

    dataset.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    subset = build_twowiki_subset(dataset=dataset, case_ids=("case-c", "case-a"))

    assert subset == [rows[2], rows[0]]


def test_write_subset_is_deterministic_runtime_cache(tmp_path: Path) -> None:
    dataset = tmp_path / "train.json"

    dataset.write_text(json.dumps(_dataset_rows(), ensure_ascii=False), encoding="utf-8")

    ids_file = tmp_path / "cohort.txt"

    ids_file.write_text("case-b\ncase-a\n", encoding="utf-8")

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_twowiki_subset(dataset=dataset, case_ids_file=ids_file, output=first)
    write_twowiki_subset(dataset=dataset, case_ids_file=ids_file, output=second)

    assert first.read_bytes() == second.read_bytes()

    assert [row["_id"] for row in json.loads(first.read_text(encoding="utf-8"))] == [
        "case-b",
        "case-a",
    ]


def test_subset_rejects_missing_case_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "train.json"

    dataset.write_text(json.dumps(_dataset_rows()), encoding="utf-8")

    with pytest.raises(KeyError, match="missing"):
        build_twowiki_subset(dataset=dataset, case_ids=("missing",))
