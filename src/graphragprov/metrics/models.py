"""Immutable measurement result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterCoverage:
    """Covered characters relative to one character space."""

    covered_characters: int
    total_characters: int

    def __post_init__(self) -> None:
        if self.covered_characters < 0:
            raise ValueError("covered characters must not be negative")

        if self.total_characters < 0:
            raise ValueError("total characters must not be negative")

        if self.covered_characters > self.total_characters:
            raise ValueError("covered characters must not exceed total characters")

    @property
    def coverage_ratio(self) -> float | None:
        """Return coverage proportion or ``None`` for an empty segment."""

        if self.total_characters == 0:
            return None

        return self.covered_characters / self.total_characters

    def to_dict(self) -> dict[str, int | float | None]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "covered_characters": self.covered_characters,
            "total_characters": self.total_characters,
            "coverage_ratio": self.coverage_ratio,
        }


@dataclass(frozen=True, slots=True)
class SegmentedCharacterCoverage:
    """Coverage measured over title, text, and their combined space."""

    title: CharacterCoverage
    text: CharacterCoverage
    combined: CharacterCoverage

    def to_dict(self) -> dict[str, dict[str, int | float | None]]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "title": self.title.to_dict(),
            "text": self.text.to_dict(),
            "combined": self.combined.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CharacterCoverageMeasurements:
    """Role-specific character coverage for one source unit."""

    overall: SegmentedCharacterCoverage
    subject: SegmentedCharacterCoverage
    predicate: SegmentedCharacterCoverage
    object: SegmentedCharacterCoverage
    entity: SegmentedCharacterCoverage
    relation: SegmentedCharacterCoverage

    def to_dict(self) -> dict[str, dict[str, dict[str, int | float | None]]]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "overall": self.overall.to_dict(),
            "subject": self.subject.to_dict(),
            "predicate": self.predicate.to_dict(),
            "object": self.object.to_dict(),
            "entity": self.entity.to_dict(),
            "relation": self.relation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SentenceCoverage:
    """Covered sentences relative to all detected text sentences."""

    covered_sentences: int
    total_sentences: int

    def __post_init__(self) -> None:
        if self.covered_sentences < 0:
            raise ValueError("covered sentences must not be negative")

        if self.total_sentences < 0:
            raise ValueError("total sentences must not be negative")

        if self.covered_sentences > self.total_sentences:
            raise ValueError("covered sentences must not exceed total sentences")

    @property
    def coverage_ratio(self) -> float | None:
        """Return sentence coverage or ``None`` when text has no sentences."""

        if self.total_sentences == 0:
            return None

        return self.covered_sentences / self.total_sentences

    def to_dict(self) -> dict[str, int | float | None]:
        """Return a JSON-serializable representation."""

        return {
            "covered_sentences": self.covered_sentences,
            "total_sentences": self.total_sentences,
            "coverage_ratio": self.coverage_ratio,
        }


@dataclass(frozen=True, slots=True)
class SentenceCoverageMeasurements:
    """Role-specific sentence coverage for one source unit."""

    overall: SentenceCoverage
    subject: SentenceCoverage
    predicate: SentenceCoverage
    object: SentenceCoverage
    entity: SentenceCoverage
    relation: SentenceCoverage

    def to_dict(self) -> dict[str, dict[str, int | float | None]]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "overall": self.overall.to_dict(),
            "subject": self.subject.to_dict(),
            "predicate": self.predicate.to_dict(),
            "object": self.object.to_dict(),
            "entity": self.entity.to_dict(),
            "relation": self.relation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LongestUncoveredTextRegion:
    """Longest contiguous region of source text without grounded evidence."""

    start: int | None
    end: int | None
    length: int
    quote: str

    def __post_init__(self) -> None:
        if self.length < 0:
            raise ValueError("uncovered region length must not be negative")

        if self.start is None or self.end is None:
            if self.start is not None or self.end is not None:
                raise ValueError("uncovered region start and end must both be absent")

            if self.length != 0:
                raise ValueError("absent uncovered region must have zero length")

            if self.quote:
                raise ValueError("absent uncovered region must have an empty quote")

            return

        if self.start < 0:
            raise ValueError("uncovered region start must not be negative")

        if self.end < self.start:
            raise ValueError("uncovered region end must not precede start")

        if self.end - self.start != self.length:
            raise ValueError("uncovered region length must match its bounds")

        if len(self.quote) != self.length:
            raise ValueError("uncovered region quote length must match its bounds")

    @property
    def exists(self) -> bool:
        """Return whether an uncovered region exists."""

        return self.start is not None

    @classmethod
    def absent(cls) -> LongestUncoveredTextRegion:
        """Represent empty or completely covered source text."""

        return cls(start=None, end=None, length=0, quote="")

    def to_dict(self) -> dict[str, int | str | bool | None]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "exists": self.exists,
            "start": self.start,
            "end": self.end,
            "length": self.length,
            "quote": self.quote,
        }


@dataclass(frozen=True, slots=True)
class StatementDensity:
    """Accepted grounded statements relative to source length."""

    statement_count: int
    total_characters: int
    scale: int

    def __post_init__(self) -> None:
        if self.statement_count < 0:
            raise ValueError("statement count must not be negative")

        if self.total_characters < 0:
            raise ValueError("total characters must not be negative")

        if self.scale <= 0:
            raise ValueError("statement density scale must be greater than zero")

        if self.total_characters == 0 and self.statement_count > 0:
            raise ValueError("an empty source cannot contain grounded statements")

    @property
    def statements_per_scale(self) -> float | None:
        """Return density or ``None`` for an empty source."""

        if self.total_characters == 0:
            return None

        return self.statement_count * self.scale / self.total_characters

    def to_dict(self) -> dict[str, int | float | None]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "statement_count": self.statement_count,
            "total_characters": self.total_characters,
            "scale": self.scale,
            "statements_per_scale": self.statements_per_scale,
        }
