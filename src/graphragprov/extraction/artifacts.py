"""Persistence and reuse of grounded extraction runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from graphragprov.domain import SourceUnit
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.run import (
    GenerateResponse,
    GroundedExtractionRun,
    run_grounded_extraction,
)

_SOURCE_FILENAME = "source.json"
_PROMPT_FILENAME = "prompt.txt"
_RESPONSE_FILENAME = "response.txt"
_EXTRACTION_FILENAME = "extraction.json"


@dataclass(frozen=True, slots=True)
class CachedGroundedExtraction:
    """One extraction run together with its cache status."""

    run: GroundedExtractionRun
    reused: bool


def extraction_artifact_directory(
    cache_root: Path,
    source: SourceUnit,
) -> Path:
    """Return the deterministic artifact directory for one source unit."""

    return cache_root / source.unit_id


def load_or_run_grounded_extraction(
    source: SourceUnit,
    *,
    cache_root: Path,
    generate_response: GenerateResponse,
) -> CachedGroundedExtraction:
    """Reuse one complete extraction artifact or execute it once."""

    directory = extraction_artifact_directory(
        cache_root,
        source,
    )

    if _artifact_is_complete(directory):
        return CachedGroundedExtraction(
            run=load_grounded_extraction_run(
                source,
                directory,
            ),
            reused=True,
        )

    run = run_grounded_extraction(
        source,
        generate_response,
    )
    save_grounded_extraction_run(
        run,
        directory,
    )

    return CachedGroundedExtraction(
        run=run,
        reused=False,
    )


def save_grounded_extraction_run(
    run: GroundedExtractionRun,
    directory: Path,
) -> None:
    """Save one complete validated extraction run."""

    expected_prompt = build_extraction_prompt(run.source)

    if run.prompt != expected_prompt:
        raise ValueError("extraction prompt does not match the current source and prompt version")

    run.extraction.validate_against(run.source)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_payload = json.dumps(
        {
            "unit_id": run.source.unit_id,
            "title": run.source.title,
            "text": run.source.text,
        },
        ensure_ascii=False,
        indent=2,
    )

    (directory / _SOURCE_FILENAME).write_text(
        source_payload + "\n",
        encoding="utf-8",
    )
    (directory / _PROMPT_FILENAME).write_text(
        run.prompt,
        encoding="utf-8",
    )
    (directory / _RESPONSE_FILENAME).write_text(
        run.response,
        encoding="utf-8",
    )
    (directory / _EXTRACTION_FILENAME).write_text(
        run.extraction.to_json() + "\n",
        encoding="utf-8",
    )


def load_grounded_extraction_run(
    source: SourceUnit,
    directory: Path,
) -> GroundedExtractionRun:
    """Load and validate one complete extraction artifact."""

    _require_complete_artifact(directory)

    source_path = directory / _SOURCE_FILENAME
    prompt_path = directory / _PROMPT_FILENAME
    response_path = directory / _RESPONSE_FILENAME
    extraction_path = directory / _EXTRACTION_FILENAME

    try:
        source_data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("cached source contains invalid JSON") from error

    expected_source_data = {
        "unit_id": source.unit_id,
        "title": source.title,
        "text": source.text,
    }

    if source_data != expected_source_data:
        raise ValueError("cached source does not match the requested source unit")

    prompt = prompt_path.read_text(encoding="utf-8")
    expected_prompt = build_extraction_prompt(source)

    if prompt != expected_prompt:
        raise ValueError("cached prompt does not match the current source and prompt version")

    response = response_path.read_text(encoding="utf-8")

    try:
        extraction = ExtractionResult.from_json(extraction_path.read_text(encoding="utf-8"))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("cached extraction is invalid") from error

    extraction.validate_against(source)

    return GroundedExtractionRun(
        source=source,
        prompt=prompt,
        response=response,
        extraction=extraction,
    )


def _artifact_is_complete(
    directory: Path,
) -> bool:
    return all(
        (directory / filename).is_file()
        for filename in (
            _SOURCE_FILENAME,
            _PROMPT_FILENAME,
            _RESPONSE_FILENAME,
            _EXTRACTION_FILENAME,
        )
    )


def _require_complete_artifact(
    directory: Path,
) -> None:
    missing = [
        filename
        for filename in (
            _SOURCE_FILENAME,
            _PROMPT_FILENAME,
            _RESPONSE_FILENAME,
            _EXTRACTION_FILENAME,
        )
        if not (directory / filename).is_file()
    ]

    if missing:
        raise ValueError("incomplete extraction artifact; missing: " + ", ".join(missing))
