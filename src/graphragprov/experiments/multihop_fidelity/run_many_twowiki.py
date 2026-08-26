"""Run many 2Wiki H0 cases through the shared batch scheduler."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from graphragprov.benchmarks.twowiki import iter_cases
from graphragprov.benchmarks.twowiki.selection import supporting_paragraphs
from graphragprov.config import twowiki_dataset_path
from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.run_many import Job, run_batch
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, DEFAULT_DEEPSEEK_TIMEOUT_SECONDS


def _load_jobs(dataset: Path, ids_file: Path) -> tuple[Job, ...]:
    ids = tuple(
        line.strip()
        for line in ids_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    if not ids or len(ids) != len(set(ids)):
        raise ValueError("case ID file must be non-empty and contain no duplicates")

    wanted = set(ids)
    supports: dict[str, frozenset[str]] = {}

    for case in iter_cases(dataset):
        if case.case_id in wanted:
            supports[case.case_id] = frozenset(
                paragraph.unit_id for paragraph in supporting_paragraphs(case)
            )

    missing = [case_id for case_id in ids if case_id not in supports]

    if missing:
        raise KeyError(f"2Wiki cases not found: {', '.join(missing)}")

    empty_support = [case_id for case_id in ids if not supports[case_id]]

    if empty_support:
        raise ValueError(
            "2Wiki cases contain no supporting source units: " + ", ".join(empty_support)
        )

    return tuple(
        Job(index, case_id, supports[case_id]) for index, case_id in enumerate(ids, start=1)
    )


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run many 2Wiki H0 cases through run_one_twowiki.")

    parser.add_argument("--case-ids-file", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)

    parser.add_argument(
        "--query-scope",
        choices=(QueryScope.SUPPORT.value, QueryScope.REPOSITORY.value),
        default=QueryScope.SUPPORT.value,
    )

    parser.add_argument("--dataset-path", type=Path)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=16_384)
    parser.add_argument("--max-source-attempts", type=int, default=3)
    parser.add_argument("--max-query-attempts", type=int, default=5)

    parser.add_argument(
        "--llm-timeout-seconds", type=float, default=DEFAULT_DEEPSEEK_TIMEOUT_SECONDS
    )

    parser.add_argument("--resume", action="store_true")

    args = parser.parse_args(argv)

    if args.workers < 1:
        parser.error("--workers must be >= 1")

    if args.query_scope == QueryScope.REPOSITORY.value and args.workers != 1:
        parser.error("repository scope requires --workers 1 with shared GraphDB")

    args.dataset_path = (args.dataset_path or twowiki_dataset_path()).expanduser().resolve()

    args.artifacts = args.artifacts.expanduser().resolve()
    args.case_ids_file = args.case_ids_file.expanduser().resolve()

    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)

    jobs = _load_jobs(args.dataset_path, args.case_ids_file)

    return run_batch(
        args=args,
        jobs=jobs,
        worker_module="graphragprov.experiments.multihop_fidelity.run_one_twowiki",
    )


if __name__ == "__main__":
    raise SystemExit(main())
