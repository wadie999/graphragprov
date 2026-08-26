"""Build a deterministic reduced 2Wiki dataset from a frozen case-ID cohort."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from graphragprov.config import twowiki_dataset_path


def read_case_ids(path: Path) -> tuple[str, ...]:
    """Read one non-empty, duplicate-free case ID per non-comment line."""

    ids = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    if not ids:
        raise ValueError("case ID file must not be empty")

    if len(ids) != len(set(ids)):
        raise ValueError("case ID file must not contain duplicates")

    return ids


def build_twowiki_subset(*, dataset: Path, case_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return exact source rows ordered by the frozen cohort ID file."""

    raw = cast(object, json.loads(dataset.read_text(encoding="utf-8")))

    if not isinstance(raw, list):
        raise ValueError("2Wiki dataset root must be a JSON array")

    rows_by_id: dict[str, dict[str, Any]] = {}

    for raw_row in raw:
        if not isinstance(raw_row, dict):
            raise ValueError("every 2Wiki dataset row must be a JSON object")

        row = cast(dict[str, Any], raw_row)
        case_id = row.get("_id")

        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("every 2Wiki dataset row must contain a non-empty _id")

        if case_id in rows_by_id:
            raise ValueError(f"duplicate 2Wiki case ID in dataset: {case_id}")

        rows_by_id[case_id] = row

    missing = [case_id for case_id in case_ids if case_id not in rows_by_id]

    if missing:
        raise KeyError(f"2Wiki cases not found: {', '.join(missing)}")

    return [rows_by_id[case_id] for case_id in case_ids]


def write_twowiki_subset(*, dataset: Path, case_ids_file: Path, output: Path) -> tuple[str, ...]:
    """Write a deterministic subset cache and return its ordered case IDs."""

    case_ids = read_case_ids(case_ids_file)
    rows = build_twowiki_subset(dataset=dataset, case_ids=case_ids)

    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    return case_ids


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reduced 2Wiki JSON cache from a frozen case-ID cohort."
    )

    parser.add_argument("--case-ids-file", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path)
    parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)

    args.dataset_path = (args.dataset_path or twowiki_dataset_path()).expanduser().resolve()

    args.case_ids_file = args.case_ids_file.expanduser().resolve()
    args.output = args.output.expanduser().resolve()

    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)

    case_ids = write_twowiki_subset(
        dataset=args.dataset_path, case_ids_file=args.case_ids_file, output=args.output
    )

    print(f"wrote {len(case_ids)} 2Wiki cases to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
