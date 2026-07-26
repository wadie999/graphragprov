import json
from pathlib import Path

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction.artifacts import extraction_artifact_directory
from graphragprov.extraction.batch import (
    load_or_run_grounded_extraction_batch,
    load_or_run_grounded_extractions,
)
from graphragprov.hashing import source_unit_id


def make_source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


FIRST_SOURCE = make_source(title="Albert Einstein", text="He was born in Ulm.")

SECOND_SOURCE = make_source(title="Marie Curie", text="She was born in Warsaw.")

THIRD_SOURCE = make_source(title="Isaac Newton", text="He was born in Woolsthorpe.")

INVALID_RESPONSE = "{this is not valid JSON"


def empty_response() -> str:
    return json.dumps({"statements": []})


def test_extracts_unique_sources_in_first_seen_order(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)
        return empty_response()

    results = load_or_run_grounded_extractions(
        (FIRST_SOURCE, SECOND_SOURCE), cache_root=tmp_path, generate_response=fake_model
    )

    assert [result.run.source for result in results] == [FIRST_SOURCE, SECOND_SOURCE]

    assert len(received_prompts) == 2
    assert all(not result.reused for result in results)


def test_deduplicates_repeated_source_units(tmp_path: Path) -> None:
    calls = 0

    def fake_model(_: str) -> str:
        nonlocal calls
        calls += 1
        return empty_response()

    results = load_or_run_grounded_extractions(
        (FIRST_SOURCE, FIRST_SOURCE, FIRST_SOURCE),
        cache_root=tmp_path,
        generate_response=fake_model,
    )

    assert calls == 1
    assert len(results) == 1
    assert results[0].run.source == FIRST_SOURCE


def test_reuses_all_completed_extractions(tmp_path: Path) -> None:
    first_run = load_or_run_grounded_extractions(
        (FIRST_SOURCE, SECOND_SOURCE),
        cache_root=tmp_path,
        generate_response=lambda _: empty_response(),
    )

    def forbidden_model_call(_: str) -> str:
        raise AssertionError("model must not be called for cached sources")

    second_run = load_or_run_grounded_extractions(
        (FIRST_SOURCE, SECOND_SOURCE), cache_root=tmp_path, generate_response=forbidden_model_call
    )

    assert all(not result.reused for result in first_run)
    assert all(result.reused for result in second_run)

    assert [result.run for result in second_run] == [result.run for result in first_run]


def test_rejects_same_unit_id_with_different_content(tmp_path: Path) -> None:
    inconsistent = SourceUnit(
        unit_id=FIRST_SOURCE.unit_id, title=FIRST_SOURCE.title, text="Different text."
    )

    with pytest.raises(ValueError, match="identical source-unit IDs"):
        load_or_run_grounded_extractions(
            (FIRST_SOURCE, inconsistent),
            cache_root=tmp_path,
            generate_response=lambda _: empty_response(),
        )


def test_accepts_empty_source_collection(tmp_path: Path) -> None:
    results = load_or_run_grounded_extractions(
        (), cache_root=tmp_path, generate_response=lambda _: empty_response()
    )

    assert results == ()


def test_resilient_batch_continues_after_invalid_response(tmp_path: Path) -> None:
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)

        if SECOND_SOURCE.title in prompt:
            return INVALID_RESPONSE

        return empty_response()

    result = load_or_run_grounded_extraction_batch(
        (FIRST_SOURCE, SECOND_SOURCE, THIRD_SOURCE),
        cache_root=tmp_path,
        generate_response=fake_model,
    )

    assert len(received_prompts) == 3

    assert [item.outcome.source for item in result.items] == [
        FIRST_SOURCE,
        SECOND_SOURCE,
        THIRD_SOURCE,
    ]

    assert [run.source for run in result.runs] == [FIRST_SOURCE, THIRD_SOURCE]

    assert len(result.failures) == 1

    failure = result.failures[0]

    assert failure.source == SECOND_SOURCE
    assert failure.stage == "response_validation"
    assert failure.response == INVALID_RESPONSE
    assert result.executed_count == 3
    assert result.reused_count == 0

    failure_directory = extraction_artifact_directory(tmp_path, SECOND_SOURCE)

    assert (failure_directory / "response.txt").read_text(encoding="utf-8") == INVALID_RESPONSE

    assert (failure_directory / "error.json").is_file()


def test_resilient_batch_reuses_successes_and_failures(tmp_path: Path) -> None:
    def fake_model(prompt: str) -> str:
        if SECOND_SOURCE.title in prompt:
            return INVALID_RESPONSE

        return empty_response()

    first = load_or_run_grounded_extraction_batch(
        (FIRST_SOURCE, SECOND_SOURCE), cache_root=tmp_path, generate_response=fake_model
    )

    def forbidden_model_call(_: str) -> str:
        raise AssertionError("model must not be called for cached outcomes")

    second = load_or_run_grounded_extraction_batch(
        (FIRST_SOURCE, SECOND_SOURCE), cache_root=tmp_path, generate_response=forbidden_model_call
    )

    assert first.executed_count == 2
    assert first.reused_count == 0

    assert second.executed_count == 0
    assert second.reused_count == 2

    assert [item.outcome for item in second.items] == [item.outcome for item in first.items]

    assert len(second.runs) == 1
    assert second.runs[0].source == FIRST_SOURCE

    assert len(second.failures) == 1
    assert second.failures[0].source == SECOND_SOURCE
    assert second.failures[0].response == INVALID_RESPONSE
