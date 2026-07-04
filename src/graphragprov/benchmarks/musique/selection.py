from pathlib import Path

from graphragprov.benchmarks.musique.case import MusiqueCase
from graphragprov.benchmarks.musique.reader import iter_cases


def select_cases(
    path: Path,
    hop_count: int,
    limit: int,
    *,
    answerable_only: bool = True,
) -> tuple[MusiqueCase, ...]:
    """Select MuSiQue cases in their original dataset order."""

    if limit < 0:
        raise ValueError("limit must be greater than or equal to zero")

    if limit == 0:
        return ()

    selected: list[MusiqueCase] = []

    for case in iter_cases(path):
        if case.hop_count != hop_count:
            continue

        if answerable_only and not case.answerable:
            continue

        selected.append(case)

        if len(selected) == limit:
            break

    return tuple(selected)
