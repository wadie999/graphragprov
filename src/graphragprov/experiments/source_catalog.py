"""Durable source snapshot for one MuSiQue experiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from graphragprov.benchmarks.musique import MusiqueSourceUnit, MusiqueUnitOccurrence
from graphragprov.hashing import source_unit_id, validate_source_unit_id

MUSIQUE_SOURCE_CATALOG_FORMAT = "musique-source-catalog-v1"
MUSIQUE_SOURCE_CATALOG_FILENAME = "source-units.json"


class SourceOccurrenceNotFoundError(LookupError):
    """Raised when an occurrence is absent from a source catalog."""


@dataclass(frozen=True, slots=True)
class MusiqueSourceCatalog:
    """Immutable source units selected for one MuSiQue experiment."""

    sources: tuple[MusiqueSourceUnit, ...]

    def __post_init__(self) -> None:
        seen_unit_ids: set[str] = set()
        seen_occurrences: set[tuple[str, int]] = set()

        for source in self.sources:
            _validate_source(source)

            if source.unit_id in seen_unit_ids:
                raise ValueError(f"duplicate source-unit ID in source catalog: {source.unit_id}")

            seen_unit_ids.add(source.unit_id)

            if not source.occurrences:
                raise ValueError(
                    f"source catalog entry has no MuSiQue occurrences: {source.unit_id}"
                )

            for occurrence in source.occurrences:
                _validate_occurrence(occurrence)

                occurrence_key = (occurrence.case_id, occurrence.paragraph_index)

                if occurrence_key in seen_occurrences:
                    raise ValueError(
                        "duplicate MuSiQue paragraph occurrence in "
                        "source catalog: "
                        f"{occurrence.case_id}:"
                        f"{occurrence.paragraph_index}"
                    )

                seen_occurrences.add(occurrence_key)

    @property
    def occurrence_count(self) -> int:
        """Return the number of paragraph occurrences."""

        return sum(len(source.occurrences) for source in self.sources)

    def get_source_for_occurrence(self, *, case_id: str, paragraph_index: int) -> MusiqueSourceUnit:
        """Resolve one benchmark paragraph to its source unit."""

        for source in self.sources:
            for occurrence in source.occurrences:
                if occurrence.case_id == case_id and occurrence.paragraph_index == paragraph_index:
                    return source

        raise SourceOccurrenceNotFoundError(
            f"source catalog has no occurrence {case_id}:{paragraph_index}"
        )

    def to_dict(self) -> dict[str, object]:
        """Return the durable catalog representation."""

        return {
            "format": MUSIQUE_SOURCE_CATALOG_FORMAT,
            "sources": [
                {
                    "unit_id": source.unit_id,
                    "title": source.title,
                    "text": source.text,
                    "occurrences": [
                        {
                            "case_id": occurrence.case_id,
                            "paragraph_index": (occurrence.paragraph_index),
                            "is_supporting": (occurrence.is_supporting),
                        }
                        for occurrence in source.occurrences
                    ],
                }
                for source in self.sources
            ],
        }

    def to_json(self) -> str:
        """Serialize the catalog deterministically."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MusiqueSourceCatalog:
        """Parse and validate one catalog representation."""

        _validate_fields(data, required={"format", "sources"}, location="source catalog")

        catalog_format = _require_string(data["format"], "source catalog.format")

        if catalog_format != MUSIQUE_SOURCE_CATALOG_FORMAT:
            raise ValueError(f"unsupported MuSiQue source catalog format: {catalog_format}")

        raw_sources = _require_list(data["sources"], "source catalog.sources")

        sources: list[MusiqueSourceUnit] = []

        for source_index, raw_source in enumerate(raw_sources):
            source_location = f"source catalog.sources[{source_index}]"
            source_data = _require_object(raw_source, source_location)

            _validate_fields(
                source_data,
                required={"unit_id", "title", "text", "occurrences"},
                location=source_location,
            )

            raw_occurrences = _require_list(
                source_data["occurrences"], f"{source_location}.occurrences"
            )

            occurrences: list[MusiqueUnitOccurrence] = []

            for occurrence_index, raw_occurrence in enumerate(raw_occurrences):
                occurrence_location = f"{source_location}.occurrences[{occurrence_index}]"
                occurrence_data = _require_object(raw_occurrence, occurrence_location)

                _validate_fields(
                    occurrence_data,
                    required={"case_id", "paragraph_index", "is_supporting"},
                    location=occurrence_location,
                )

                occurrences.append(
                    MusiqueUnitOccurrence(
                        case_id=_require_string(
                            occurrence_data["case_id"], f"{occurrence_location}.case_id"
                        ),
                        paragraph_index=_require_integer(
                            occurrence_data["paragraph_index"],
                            (f"{occurrence_location}.paragraph_index"),
                        ),
                        is_supporting=_require_boolean(
                            occurrence_data["is_supporting"],
                            (f"{occurrence_location}.is_supporting"),
                        ),
                    )
                )

            sources.append(
                MusiqueSourceUnit(
                    unit_id=_require_string(source_data["unit_id"], f"{source_location}.unit_id"),
                    title=_require_string(source_data["title"], f"{source_location}.title"),
                    text=_require_string(source_data["text"], f"{source_location}.text"),
                    occurrences=tuple(occurrences),
                )
            )

        return cls(sources=tuple(sources))

    @classmethod
    def from_json(cls, payload: str) -> MusiqueSourceCatalog:
        """Parse and validate a JSON catalog."""

        try:
            raw_data: object = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("MuSiQue source catalog contains invalid JSON") from error

        return cls.from_dict(_require_object(raw_data, "source catalog"))


def load_musique_source_catalog(path: Path) -> MusiqueSourceCatalog:
    """Load and validate a source catalog from disk."""

    return MusiqueSourceCatalog.from_json(path.read_text(encoding="utf-8"))


def write_musique_source_catalog(path: Path, catalog: MusiqueSourceCatalog) -> None:
    """Write one validated source catalog."""

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(catalog.to_json() + "\n", encoding="utf-8")


def _validate_source(source: MusiqueSourceUnit) -> None:
    if not isinstance(source.unit_id, str):
        raise ValueError("source-unit ID must be a string")

    if not isinstance(source.title, str):
        raise ValueError("source-unit title must be a string")

    if not isinstance(source.text, str):
        raise ValueError("source-unit text must be a string")

    validate_source_unit_id(source.unit_id)

    expected_unit_id = source_unit_id(title=source.title, text=source.text)

    if source.unit_id != expected_unit_id:
        raise ValueError(f"source-unit ID does not match source content: {source.unit_id}")


def _validate_occurrence(occurrence: MusiqueUnitOccurrence) -> None:
    if not isinstance(occurrence.case_id, str) or not occurrence.case_id.strip():
        raise ValueError("MuSiQue occurrence case ID must not be empty")

    if type(occurrence.paragraph_index) is not int or occurrence.paragraph_index < 0:
        raise ValueError("MuSiQue occurrence paragraph index must be a non-negative integer")

    if type(occurrence.is_supporting) is not bool:
        raise ValueError("MuSiQue occurrence support flag must be a boolean")


def _validate_fields(data: dict[str, object], *, required: set[str], location: str) -> None:
    fields = set(data)
    missing = required - fields
    unexpected = fields - required

    if missing:
        raise ValueError(f"{location} is missing field(s): {', '.join(sorted(missing))}")

    if unexpected:
        raise ValueError(
            f"{location} contains unexpected field(s): {', '.join(sorted(unexpected))}"
        )


def _require_object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{location} must be an object")

    return cast(dict[str, object], value)


def _require_list(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be a list")

    return value


def _require_string(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{location} must be a string")

    return value


def _require_integer(value: object, location: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{location} must be an integer")

    return value


def _require_boolean(value: object, location: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{location} must be a boolean")

    return value
