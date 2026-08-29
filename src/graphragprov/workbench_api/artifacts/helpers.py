"""Helpers for parsing persisted H0 artifacts."""

from __future__ import annotations

from typing import Any, cast

from graphragprov.domain import SourceUnit
from graphragprov.extraction import ExtractionResult
from graphragprov.extraction.run import GroundedExtractionRun


def extraction_run(data: dict[str, Any]) -> GroundedExtractionRun:
    source_data = _object(data.get("source"), "source")
    extraction_data = _object(
        data.get("extraction"),
        "extraction",
    )

    source = SourceUnit(
        unit_id=_string(
            source_data.get("unit_id"),
            "source.unit_id",
        ),
        title=_string(
            source_data.get("title"),
            "source.title",
        ),
        text=_string(
            source_data.get("text"),
            "source.text",
        ),
    )

    extraction = ExtractionResult.from_dict(extraction_data)
    extraction.validate_against(source)

    return GroundedExtractionRun(
        source=source,
        prompt=str(data.get("prompt", "")),
        response=str(data.get("response", "")),
        extraction=extraction,
    )


def _object(
    value: object,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"artifact field {name} must be an object"
        )

    return cast(dict[str, Any], value)


def _string(
    value: object,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"artifact field {name} must be a string"
        )

    return value