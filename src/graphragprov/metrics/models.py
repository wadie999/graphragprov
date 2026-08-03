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
