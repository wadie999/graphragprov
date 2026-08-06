"""Deterministic operations over half-open character intervals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class CharacterInterval:
    """One half-open character interval: ``[start, end)``."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("interval start must not be negative")

        if self.end < self.start:
            raise ValueError("interval end must not precede start")

    @property
    def length(self) -> int:
        """Return the number of represented characters."""

        return self.end - self.start

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-serializable representation."""

        return {"start": self.start, "end": self.end, "length": self.length}


def merge_intervals(intervals: Iterable[CharacterInterval]) -> tuple[CharacterInterval, ...]:
    """Return the deterministic union of overlapping intervals.

    Duplicate, overlapping, and directly adjacent intervals are merged.
    Empty intervals do not contribute coverage.
    """

    ordered = sorted(interval for interval in intervals if interval.length > 0)

    if not ordered:
        return ()

    merged: list[CharacterInterval] = []
    current = ordered[0]

    for interval in ordered[1:]:
        if interval.start <= current.end:
            current = CharacterInterval(start=current.start, end=max(current.end, interval.end))
            continue

        merged.append(current)
        current = interval

    merged.append(current)

    return tuple(merged)


def covered_character_count(intervals: Iterable[CharacterInterval]) -> int:
    """Count covered characters after interval union."""

    return sum(interval.length for interval in merge_intervals(intervals))


def uncovered_intervals(
    *, total_length: int, covered: Iterable[CharacterInterval]
) -> tuple[CharacterInterval, ...]:
    """Return uncovered intervals inside ``[0, total_length)``."""

    if total_length < 0:
        raise ValueError("total length must not be negative")

    merged = merge_intervals(covered)

    for interval in merged:
        if interval.end > total_length:
            raise ValueError(
                "covered interval exceeds total length: "
                f"[{interval.start}, {interval.end}) > {total_length}"
            )

    if total_length == 0:
        return ()

    uncovered: list[CharacterInterval] = []
    cursor = 0

    for interval in merged:
        if cursor < interval.start:
            uncovered.append(CharacterInterval(start=cursor, end=interval.start))

        cursor = interval.end

    if cursor < total_length:
        uncovered.append(CharacterInterval(start=cursor, end=total_length))

    return tuple(uncovered)
