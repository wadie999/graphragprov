import json
from pathlib import Path

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction.artifacts import (
    extraction_artifact_directory,
    load_grounded_extraction_run,
    load_or_run_grounded_extraction,
)
from graphragprov.hashing import source_unit_id

TITLE = "Albert Einstein"
TEXT = "He was born in Ulm."

SOURCE = SourceUnit(
    unit_id=source_unit_id(
        title=TITLE,
        text=TEXT,
    ),
    title=TITLE,
    text=TEXT,
)

MODEL_RESPONSE = json.dumps(
    {
        "statements": [
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {
                            "segment": "title",
                            "quote": "Albert Einstein",
                            "occurrence": 1,
                        },
                        {
                            "segment": "text",
                            "quote": "He",
                            "occurrence": 1,
                        },
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "born in",
                            "occurrence": 1,
                        }
                    ],
                },
                "object": {
                    "value": "Ulm",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "Ulm",
                            "occurrence": 1,
                        }
                    ],
                },
            }
        ]
    }
)


def test_runs_and_saves_missing_extraction(
    tmp_path: Path,
) -> None:
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)
        return MODEL_RESPONSE

    cached = load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=fake_model,
    )

    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )

    assert not cached.reused
    assert received_prompts == [cached.run.prompt]
    assert cached.run.source == SOURCE
    assert len(cached.run.extraction.statements) == 1

    assert (directory / "source.json").is_file()
    assert (directory / "prompt.txt").is_file()
    assert (directory / "response.txt").is_file()
    assert (directory / "extraction.json").is_file()


def test_reuses_complete_extraction_without_model_call(
    tmp_path: Path,
) -> None:
    first = load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=lambda _: MODEL_RESPONSE,
    )

    def forbidden_model_call(_: str) -> str:
        raise AssertionError("model must not be called for cached extraction")

    second = load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=forbidden_model_call,
    )

    assert not first.reused
    assert second.reused
    assert second.run == first.run


def test_incomplete_artifact_is_recomputed(
    tmp_path: Path,
) -> None:
    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )
    directory.mkdir(parents=True)
    (directory / "prompt.txt").write_text(
        "incomplete",
        encoding="utf-8",
    )

    calls = 0

    def fake_model(_: str) -> str:
        nonlocal calls
        calls += 1
        return MODEL_RESPONSE

    cached = load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=fake_model,
    )

    assert calls == 1
    assert not cached.reused

    restored = load_grounded_extraction_run(
        SOURCE,
        directory,
    )

    assert restored == cached.run


def test_rejects_cached_source_mismatch(
    tmp_path: Path,
) -> None:
    load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=lambda _: MODEL_RESPONSE,
    )

    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )
    source_path = directory / "source.json"
    source_data = json.loads(source_path.read_text(encoding="utf-8"))
    source_data["text"] = "Modified text."

    source_path.write_text(
        json.dumps(source_data),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="cached source does not match",
    ):
        load_grounded_extraction_run(
            SOURCE,
            directory,
        )


def test_rejects_stale_cached_prompt(
    tmp_path: Path,
) -> None:
    load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=lambda _: MODEL_RESPONSE,
    )

    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )
    (directory / "prompt.txt").write_text(
        "old prompt version",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="cached prompt does not match",
    ):
        load_grounded_extraction_run(
            SOURCE,
            directory,
        )


def test_rejects_cached_extraction_for_another_source(
    tmp_path: Path,
) -> None:
    load_or_run_grounded_extraction(
        SOURCE,
        cache_root=tmp_path,
        generate_response=lambda _: MODEL_RESPONSE,
    )

    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )
    extraction_path = directory / "extraction.json"
    extraction_data = json.loads(extraction_path.read_text(encoding="utf-8"))
    extraction_data["unit_id"] = "u_" + "0" * 64

    extraction_path.write_text(
        json.dumps(extraction_data),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not match source unit ID",
    ):
        load_grounded_extraction_run(
            SOURCE,
            directory,
        )


def test_direct_load_rejects_incomplete_artifact(
    tmp_path: Path,
) -> None:
    directory = extraction_artifact_directory(
        tmp_path,
        SOURCE,
    )
    directory.mkdir(parents=True)

    with pytest.raises(
        ValueError,
        match="incomplete extraction artifact",
    ):
        load_grounded_extraction_run(
            SOURCE,
            directory,
        )
