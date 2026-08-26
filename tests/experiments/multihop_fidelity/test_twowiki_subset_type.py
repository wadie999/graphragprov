"""Tests for 2Wiki cohort type validation."""

import json
from pathlib import Path

import pytest

from graphragprov.experiments.multihop_fidelity.twowiki_subset import (
    build_twowiki_subset,
    parse_arguments,
)


def _write_dataset(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "_id": "composition-a",
                    "type": "compositional",
                    "question": "Question A?",
                    "answer": "Answer A",
                },
                {
                    "_id": "comparison-a",
                    "type": "comparison",
                    "question": "Question B?",
                    "answer": "Answer B",
                },
                {
                    "_id": "composition-b",
                    "type": "compositional",
                    "question": "Question C?",
                    "answer": "Answer C",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_required_type_accepts_matching_cohort(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_dataset(dataset)

    rows = build_twowiki_subset(
        dataset=dataset, case_ids=("composition-b", "composition-a"), required_type="compositional"
    )

    assert [row["_id"] for row in rows] == ["composition-b", "composition-a"]


def test_required_type_rejects_mismatched_case(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_dataset(dataset)

    with pytest.raises(ValueError, match="comparison-a='comparison'"):
        build_twowiki_subset(
            dataset=dataset,
            case_ids=("composition-a", "comparison-a"),
            required_type="compositional",
        )


def test_type_validation_is_optional(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_dataset(dataset)

    rows = build_twowiki_subset(dataset=dataset, case_ids=("composition-a", "comparison-a"))

    assert [row["_id"] for row in rows] == ["composition-a", "comparison-a"]


def test_cli_accepts_compositional_type(tmp_path: Path) -> None:
    case_ids = tmp_path / "cases.txt"
    dataset = tmp_path / "dataset.json"
    output = tmp_path / "subset.json"

    case_ids.write_text("composition-a\n", encoding="utf-8")
    _write_dataset(dataset)

    args = parse_arguments(
        [
            "--case-ids-file",
            str(case_ids),
            "--dataset-path",
            str(dataset),
            "--output",
            str(output),
            "--required-type",
            "compositional",
        ]
    )

    assert args.required_type == "compositional"
