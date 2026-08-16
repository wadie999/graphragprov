"""Tests for the one-case H0 command-line adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.run_one import (
    CheckpointedGenerateResponse,
    RunOneArguments,
    _run_configuration_payload,
    _write_or_validate_configuration,
    parse_arguments,
)


def test_checkpointed_generator_persists_exact_paid_call(tmp_path: Path) -> None:
    calls: list[str] = []

    def provider(prompt: str) -> str:
        calls.append(prompt)
        return '{"answer": "stored"}'

    generate = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    response = generate("Return JSON for this exact prompt.")

    assert response == ('{"answer": "stored"}')

    assert calls == ["Return JSON for this exact prompt."]

    assert generate.call_count == 1
    assert generate.executed_count == 1
    assert generate.reused_count == 0

    checkpoint_directories = sorted((tmp_path / "llm").iterdir())

    assert len(checkpoint_directories) == 1

    checkpoint = checkpoint_directories[0]

    assert checkpoint.name.startswith("0001-")

    assert (checkpoint / "prompt.txt").read_text(encoding="utf-8") == (
        "Return JSON for this exact prompt."
    )

    assert (checkpoint / "response.txt").read_text(encoding="utf-8") == ('{"answer": "stored"}')


def test_identical_prompts_are_distinct_calls_inside_one_execution(tmp_path: Path) -> None:
    responses = iter(('{"attempt": 1}', '{"attempt": 2}'))

    calls: list[str] = []

    def provider(prompt: str) -> str:
        calls.append(prompt)
        return next(responses)

    generate = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    first = generate("Retry this exact prompt.")

    second = generate("Retry this exact prompt.")

    assert first == ('{"attempt": 1}')

    assert second == ('{"attempt": 2}')

    assert calls == ["Retry this exact prompt.", "Retry this exact prompt."]

    assert generate.call_count == 2
    assert generate.executed_count == 2
    assert generate.reused_count == 0

    checkpoints = sorted(path.name for path in (tmp_path / "llm").iterdir())

    assert len(checkpoints) == 2

    assert checkpoints[0].startswith("0001-")

    assert checkpoints[1].startswith("0002-")

    # The prompt hashes are intentionally equal.
    assert checkpoints[0].split("-", maxsplit=1)[1] == checkpoints[1].split("-", maxsplit=1)[1]


def test_sequence_checkpoints_can_be_replayed_without_new_paid_calls(tmp_path: Path) -> None:
    calls: list[str] = []

    def provider(prompt: str) -> str:
        calls.append(prompt)

        return json.dumps({"provider_call": (len(calls))})

    original = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    first_original = original("Prompt A")

    second_original = original("Prompt A")

    third_original = original("Prompt B")

    assert len(calls) == 3

    resumed = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=True
    )

    assert resumed("Prompt A") == first_original

    assert resumed("Prompt A") == second_original

    assert resumed("Prompt B") == third_original

    # Replay used all three stored responses.
    assert len(calls) == 3

    assert resumed.call_count == 3
    assert resumed.executed_count == 0
    assert resumed.reused_count == 3


def test_checkpoint_reuse_is_never_silent(tmp_path: Path) -> None:
    def provider(prompt: str) -> str:
        return '{"ok": true}'

    original = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    original("Return JSON.")

    fresh_scientific_run = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    with pytest.raises(RuntimeError, match="--reuse-llm-checkpoints"):
        fresh_scientific_run("Return JSON.")


def test_resume_rejects_changed_prompt_sequence(tmp_path: Path) -> None:
    def provider(prompt: str) -> str:
        return '{"ok": true}'

    original = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    original("Original first prompt.")

    resumed = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=True
    )

    with pytest.raises(RuntimeError, match="sequence diverged"):
        resumed("Different first prompt.")


def test_prompt_only_checkpoint_is_safe_to_retry_after_provider_failure(tmp_path: Path) -> None:
    call_count = 0

    def provider(prompt: str) -> str:
        nonlocal call_count

        call_count += 1

        if call_count == 1:
            raise RuntimeError("provider unavailable")

        return '{"recovered": true}'

    first_execution = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=False
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        first_execution("Return JSON after recovery.")

    checkpoint_directories = list((tmp_path / "llm").iterdir())

    assert len(checkpoint_directories) == 1

    checkpoint = checkpoint_directories[0]

    assert (checkpoint / "prompt.txt").is_file()

    assert not (checkpoint / "response.txt").exists()

    resumed = CheckpointedGenerateResponse(
        root=tmp_path / "llm", generate_response=provider, reuse_existing=True
    )

    recovered = resumed("Return JSON after recovery.")

    assert recovered == ('{"recovered": true}')

    assert call_count == 2
    assert resumed.executed_count == 1
    assert resumed.reused_count == 0

    assert (checkpoint / "response.txt").is_file()


def test_run_configuration_prevents_cross_configuration_checkpoint_reuse(tmp_path: Path) -> None:
    path = tmp_path / "run-config.json"

    original: dict[str, object] = {
        "case_id": "case-a",
        "model": "model-a",
        "query_scope": "support",
    }

    _write_or_validate_configuration(path, original)

    # Exact resume is valid.
    _write_or_validate_configuration(path, original)

    changed: dict[str, object] = {"case_id": "case-a", "model": "model-b", "query_scope": "support"}

    with pytest.raises(RuntimeError, match="does not match"):
        _write_or_validate_configuration(path, changed)

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_parse_arguments_builds_explicit_h0_configuration() -> None:
    arguments = parse_arguments(
        (
            "--case-id",
            "2hop__example",
            "--query-scope",
            "repository",
            "--model",
            "deepseek-test",
            "--max-tokens",
            "4096",
            "--max-source-attempts",
            "4",
            "--max-query-attempts",
            "6",
            "--artifacts",
            "runs/test-h0",
            "--reuse-llm-checkpoints",
        )
    )

    assert arguments.case_id == ("2hop__example")

    assert arguments.query_scope is (QueryScope.REPOSITORY)

    assert arguments.model == ("deepseek-test")

    assert arguments.max_tokens == 4096
    assert arguments.max_source_attempts == 4
    assert arguments.max_query_attempts == 6

    assert arguments.artifacts == Path("runs/test-h0")

    assert arguments.reuse_llm_checkpoints is True


def test_run_configuration_records_reproducibility_inputs(tmp_path: Path) -> None:
    dataset = tmp_path / "musique.jsonl"

    arguments = RunOneArguments(
        case_id="2hop__example",
        query_scope=QueryScope.SUPPORT,
        dataset_path=dataset,
        artifacts=Path("runs/test"),
        model="deepseek-test",
        max_tokens=4096,
        max_source_attempts=3,
        max_query_attempts=5,
        reuse_llm_checkpoints=False,
    )

    payload = _run_configuration_payload(
        case_id=(arguments.case_id), dataset_path=dataset, arguments=arguments
    )

    assert payload["case_id"] == "2hop__example"

    assert payload["query_scope"] == "support"

    assert payload["graph_origin"] == "reference"

    assert payload["query_origin"] == "reference"

    assert payload["model"] == "deepseek-test"

    assert payload["max_tokens"] == 4096

    assert payload["max_source_attempts"] == 3

    assert payload["max_query_attempts"] == 5

    assert payload["dataset_path"] == str(dataset.resolve())
