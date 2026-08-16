"""Tests for the DeepSeek provider adapter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import graphragprov.providers.deepseek as deepseek_module
from graphragprov.providers.deepseek import (
    DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
    DeepSeekCallObservation,
    deepseek_generator,
)


def _successful_response(
    *,
    content: str = '{"statements": []}',
    finish_reason: str = "stop",
    model: str = "deepseek-v4-flash",
    usage: object | None = None,
) -> SimpleNamespace:
    if usage is None:
        usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            prompt_cache_hit_tokens=70,
            prompt_cache_miss_tokens=30,
        )

    choice = SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=content))

    return SimpleNamespace(model=model, usage=usage, choices=[choice])


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: object | None = None,
    error: Exception | None = None,
) -> tuple[Mock, Mock]:
    create = Mock()

    if error is not None:
        create.side_effect = error
    else:
        create.return_value = response if response is not None else _successful_response()

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    constructor = Mock(return_value=client)
    monkeypatch.setattr(deepseek_module, "OpenAI", constructor)

    return constructor, create


def test_generator_preserves_stable_string_contract_and_exact_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructor, create = _install_client(monkeypatch)

    generate = deepseek_generator(api_key="secret", model="deepseek-v4-flash", max_tokens=4096)

    response = generate("Return JSON.")

    assert response == '{"statements": []}'

    constructor.assert_called_once_with(
        api_key="secret",
        base_url="https://api.deepseek.com",
        timeout=DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
        max_retries=0,
    )

    create.assert_called_once_with(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": "Return JSON."}],
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )


def test_generator_accepts_explicit_bounded_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    constructor, _ = _install_client(monkeypatch)

    deepseek_generator(api_key="secret", timeout_seconds=17.5)

    constructor.assert_called_once_with(
        api_key="secret", base_url="https://api.deepseek.com", timeout=17.5, max_retries=0
    )


def test_success_observation_preserves_exact_usage_and_cache_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_client(monkeypatch, response=_successful_response(model="deepseek-response-model"))

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(
        api_key="secret", model="deepseek-request-model", observe_call=observations.append
    )

    generate("Return JSON.")

    assert len(observations) == 1
    observation = observations[0]

    assert observation.requested_model == "deepseek-request-model"
    assert observation.response_model == "deepseek-response-model"
    assert observation.succeeded is True
    assert observation.error_type is None
    assert observation.error_message is None
    assert observation.elapsed_seconds >= 0
    assert observation.started_at.utcoffset() is not None

    assert observation.usage is not None
    assert observation.usage.prompt_tokens == 100
    assert observation.usage.completion_tokens == 20
    assert observation.usage.total_tokens == 120
    assert observation.usage.prompt_cache_hit_tokens == 70
    assert observation.usage.prompt_cache_miss_tokens == 30


def test_cache_fields_are_read_from_model_extra_when_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = SimpleNamespace(
        prompt_tokens=90,
        completion_tokens=10,
        total_tokens=100,
        model_extra={"prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 30},
    )

    _install_client(monkeypatch, response=_successful_response(usage=usage))

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(api_key="secret", observe_call=observations.append)

    generate("Return JSON.")

    assert observations[0].usage is not None
    assert observations[0].usage.prompt_cache_hit_tokens == 60
    assert observations[0].usage.prompt_cache_miss_tokens == 30


def test_network_failure_records_latency_without_inventing_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_client(monkeypatch, error=RuntimeError("network unavailable"))

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(api_key="secret", observe_call=observations.append)

    with pytest.raises(RuntimeError, match="network unavailable"):
        generate("Return JSON.")

    assert len(observations) == 1
    observation = observations[0]

    assert observation.succeeded is False
    assert observation.usage is None
    assert observation.error_type == "RuntimeError"
    assert observation.error_message == "network unavailable"
    assert observation.elapsed_seconds >= 0


def test_truncated_response_records_billable_usage_before_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_client(monkeypatch, response=_successful_response(finish_reason="length"))

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(api_key="secret", observe_call=observations.append)

    with pytest.raises(ValueError, match="truncated"):
        generate("Return JSON.")

    observation = observations[0]
    assert observation.succeeded is False
    assert observation.usage is not None
    assert observation.usage.total_tokens == 120
    assert observation.error_type == "ValueError"


def test_empty_response_is_rejected_and_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_client(monkeypatch, response=_successful_response(content="   "))

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(api_key="secret", observe_call=observations.append)

    with pytest.raises(ValueError, match="content is empty"):
        generate("Return JSON.")

    assert observations[0].succeeded is False
    assert observations[0].usage is not None


def test_response_without_choices_is_rejected_and_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(
        model="deepseek-v4-flash",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0, total_tokens=10),
        choices=[],
    )

    _install_client(monkeypatch, response=response)

    observations: list[DeepSeekCallObservation] = []

    generate = deepseek_generator(api_key="secret", observe_call=observations.append)

    with pytest.raises(ValueError, match="no choices"):
        generate("Return JSON.")

    assert observations[0].succeeded is False
    assert observations[0].usage is not None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"api_key": ""}, "API key"),
        ({"api_key": "secret", "model": ""}, "model"),
        ({"api_key": "secret", "max_tokens": 0}, "max_tokens"),
        ({"api_key": "secret", "timeout_seconds": 0.0}, "timeout_seconds"),
        ({"api_key": "secret", "timeout_seconds": float("inf")}, "timeout_seconds"),
    ),
)
def test_invalid_generator_configuration_is_rejected(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        deepseek_generator(**kwargs)  # type: ignore[arg-type]
