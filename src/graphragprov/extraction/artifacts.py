"""Persistence and reuse of grounded extraction outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from graphragprov.domain import SourceUnit
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.result import ExtractionResult
from graphragprov.extraction.run import (
    ExtractionFailureStage,
    GenerateResponse,
    GroundedExtractionFailure,
    GroundedExtractionOutcome,
    GroundedExtractionRun,
    run_grounded_extraction,
)

_SOURCE_FILENAME = "source.json"
_PROMPT_FILENAME = "prompt.txt"
_RESPONSE_FILENAME = "response.txt"
_EXTRACTION_FILENAME = "extraction.json"
_ERROR_FILENAME = "error.json"

_FAILURE_FORMAT = "grounded-extraction-failure-v1"


@dataclass(frozen=True, slots=True)
class CachedGroundedExtraction:
    """One successful extraction run together with its cache status."""

    run: GroundedExtractionRun
    reused: bool


def extraction_artifact_directory(cache_root: Path, source: SourceUnit) -> Path:
    """Return the deterministic artifact directory for one source unit."""

    return cache_root / source.unit_id


def load_or_run_grounded_extraction(
    source: SourceUnit, *, cache_root: Path, generate_response: GenerateResponse
) -> CachedGroundedExtraction:
    """Reuse one complete successful artifact or execute it once."""

    directory = extraction_artifact_directory(cache_root, source)

    if _success_artifact_is_complete(directory):
        return CachedGroundedExtraction(
            run=load_grounded_extraction_run(source, directory), reused=True
        )

    run = run_grounded_extraction(source, generate_response)
    save_grounded_extraction_run(run, directory)

    return CachedGroundedExtraction(run=run, reused=False)


def has_grounded_extraction_outcome(directory: Path) -> bool:
    """Return whether exactly one complete outcome is stored."""

    success = _success_artifact_is_complete(directory)
    failure = _failure_artifact_is_complete(directory)

    if success and failure:
        raise ValueError("artifact contains both a successful extraction and a failure")

    return success or failure


def save_grounded_extraction_outcome(outcome: GroundedExtractionOutcome, directory: Path) -> None:
    """Persist one successful or failed extraction outcome."""

    if isinstance(outcome, GroundedExtractionRun):
        save_grounded_extraction_run(outcome, directory)
    else:
        save_grounded_extraction_failure(outcome, directory)


def load_grounded_extraction_outcome(
    source: SourceUnit, directory: Path
) -> GroundedExtractionOutcome:
    """Load one complete successful or failed outcome."""

    success = _success_artifact_is_complete(directory)
    failure = _failure_artifact_is_complete(directory)

    if success and failure:
        raise ValueError("artifact contains both a successful extraction and a failure")

    if success:
        return load_grounded_extraction_run(source, directory)

    if failure:
        return load_grounded_extraction_failure(source, directory)

    raise ValueError("no complete grounded extraction outcome is stored")


def save_grounded_extraction_run(run: GroundedExtractionRun, directory: Path) -> None:
    """Save one complete validated extraction run."""

    run.extraction.validate_against(run.source)

    _save_common_artifacts(
        source=run.source, prompt=run.prompt, response=run.response, directory=directory
    )

    (directory / _EXTRACTION_FILENAME).write_text(run.extraction.to_json() + "\n", encoding="utf-8")

    (directory / _ERROR_FILENAME).unlink(missing_ok=True)


def save_grounded_extraction_failure(failure: GroundedExtractionFailure, directory: Path) -> None:
    """Save one complete inspectable extraction failure."""

    _save_common_artifacts(
        source=failure.source,
        prompt=failure.prompt,
        response=(failure.response if failure.response is not None else ""),
        directory=directory,
    )

    error_payload = {
        "format": _FAILURE_FORMAT,
        "stage": failure.stage,
        "error_type": failure.error_type,
        "error_message": (failure.error_message),
        "response_available": (failure.response is not None),
    }

    (directory / _ERROR_FILENAME).write_text(
        json.dumps(error_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (directory / _EXTRACTION_FILENAME).unlink(missing_ok=True)


def load_grounded_extraction_run(source: SourceUnit, directory: Path) -> GroundedExtractionRun:
    """Load and validate one successful extraction artifact."""

    _require_files(
        directory, _SOURCE_FILENAME, _PROMPT_FILENAME, _RESPONSE_FILENAME, _EXTRACTION_FILENAME
    )

    prompt, response = _load_common_artifacts(source, directory)

    try:
        extraction = ExtractionResult.from_json(
            (directory / _EXTRACTION_FILENAME).read_text(encoding="utf-8")
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("cached extraction is invalid") from error

    extraction.validate_against(source)

    return GroundedExtractionRun(
        source=source, prompt=prompt, response=response, extraction=extraction
    )


def load_grounded_extraction_failure(
    source: SourceUnit, directory: Path
) -> GroundedExtractionFailure:
    """Load and validate one failed extraction artifact."""

    _require_files(
        directory, _SOURCE_FILENAME, _PROMPT_FILENAME, _RESPONSE_FILENAME, _ERROR_FILENAME
    )

    prompt, response_text = _load_common_artifacts(source, directory)

    try:
        error_payload = json.loads((directory / _ERROR_FILENAME).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("cached extraction failure contains invalid JSON") from error

    if not isinstance(error_payload, dict) or error_payload.get("format") != _FAILURE_FORMAT:
        raise ValueError("cached extraction failure has an unsupported format")

    stage = error_payload.get("stage")
    error_type = error_payload.get("error_type")
    error_message = error_payload.get("error_message")
    response_available = error_payload.get("response_available")

    if stage not in ("provider", "response_validation"):
        raise ValueError("cached extraction failure has an invalid stage")

    if not isinstance(error_type, str):
        raise ValueError("cached extraction failure has an invalid error type")

    if not isinstance(error_message, str):
        raise ValueError("cached extraction failure has an invalid error message")

    if not isinstance(response_available, bool):
        raise ValueError("cached extraction failure has invalid response availability")

    return GroundedExtractionFailure(
        source=source,
        prompt=prompt,
        response=(response_text if response_available else None),
        stage=cast(ExtractionFailureStage, stage),
        error_type=error_type,
        error_message=error_message,
    )


def _save_common_artifacts(
    *, source: SourceUnit, prompt: str, response: str, directory: Path
) -> None:
    expected_prompt = build_extraction_prompt(source)

    if prompt != expected_prompt:
        raise ValueError("extraction prompt does not match the current source and prompt version")

    directory.mkdir(parents=True, exist_ok=True)

    source_payload = json.dumps(
        {"unit_id": source.unit_id, "title": source.title, "text": source.text},
        ensure_ascii=False,
        indent=2,
    )

    (directory / _SOURCE_FILENAME).write_text(source_payload + "\n", encoding="utf-8")
    (directory / _PROMPT_FILENAME).write_text(prompt, encoding="utf-8")
    (directory / _RESPONSE_FILENAME).write_text(response, encoding="utf-8")


def _load_common_artifacts(source: SourceUnit, directory: Path) -> tuple[str, str]:
    try:
        source_data = json.loads((directory / _SOURCE_FILENAME).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("cached source contains invalid JSON") from error

    expected_source_data = {"unit_id": source.unit_id, "title": source.title, "text": source.text}

    if source_data != expected_source_data:
        raise ValueError("cached source does not match the requested source unit")

    prompt = (directory / _PROMPT_FILENAME).read_text(encoding="utf-8")

    if prompt != build_extraction_prompt(source):
        raise ValueError("cached prompt does not match the current source and prompt version")

    response = (directory / _RESPONSE_FILENAME).read_text(encoding="utf-8")

    return prompt, response


def _success_artifact_is_complete(directory: Path) -> bool:
    return _files_exist(
        directory, _SOURCE_FILENAME, _PROMPT_FILENAME, _RESPONSE_FILENAME, _EXTRACTION_FILENAME
    )


def _failure_artifact_is_complete(directory: Path) -> bool:
    return _files_exist(
        directory, _SOURCE_FILENAME, _PROMPT_FILENAME, _RESPONSE_FILENAME, _ERROR_FILENAME
    )


def _files_exist(directory: Path, *filenames: str) -> bool:
    return all((directory / filename).is_file() for filename in filenames)


def _require_files(directory: Path, *filenames: str) -> None:
    missing = [filename for filename in filenames if not (directory / filename).is_file()]

    if missing:
        raise ValueError("incomplete extraction artifact; missing: " + ", ".join(missing))
