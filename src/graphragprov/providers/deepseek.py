"""DeepSeek adapter with exact call observations for experiment telemetry."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from openai import OpenAI

from graphragprov.extraction.run import GenerateResponse

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class DeepSeekTokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class DeepSeekCallObservation:
    requested_model: str
    response_model: str | None
    started_at: datetime
    elapsed_seconds: float
    usage: DeepSeekTokenUsage | None
    succeeded: bool
    error_type: str | None = None
    error_message: str | None = None


DeepSeekCallObserver = Callable[[DeepSeekCallObservation], None]


def deepseek_generator(
    *,
    api_key: str,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    max_tokens: int = 16_384,
    observe_call: DeepSeekCallObserver | None = None,
    timeout_seconds: float = DEFAULT_DEEPSEEK_TIMEOUT_SECONDS,
) -> GenerateResponse:
    """Create a deterministic DeepSeek JSON-response generator.

    Transport retries are disabled deliberately. Experiment-level code already owns
    retry policy, so one provider observation corresponds to one bounded API request.
    """

    if not api_key.strip():
        raise ValueError("DeepSeek API key must not be empty")

    if not model.strip():
        raise ValueError("DeepSeek model must not be empty")

    if max_tokens < 1:
        raise ValueError("max_tokens must be greater than zero")

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")

    client = OpenAI(
        api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=timeout_seconds, max_retries=0
    )

    def generate_response(prompt: str) -> str:
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        usage: DeepSeekTokenUsage | None = None
        response_model: str | None = None

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )

            usage = _extract_token_usage(getattr(response, "usage", None))
            response_model = _nonempty_string(getattr(response, "model", None))

            if not response.choices:
                raise ValueError("DeepSeek response contains no choices")

            choice = response.choices[0]

            if choice.finish_reason == "length":
                raise ValueError("DeepSeek response was truncated by the token limit")

            content = choice.message.content

            if content is None or not content.strip():
                raise ValueError("DeepSeek response content is empty")

        except Exception as error:
            _observe(
                observe_call,
                DeepSeekCallObservation(
                    requested_model=model,
                    response_model=response_model,
                    started_at=started_at,
                    elapsed_seconds=perf_counter() - started_clock,
                    usage=usage,
                    succeeded=False,
                    error_type=type(error).__name__,
                    error_message=str(error),
                ),
            )
            raise

        _observe(
            observe_call,
            DeepSeekCallObservation(
                requested_model=model,
                response_model=response_model,
                started_at=started_at,
                elapsed_seconds=perf_counter() - started_clock,
                usage=usage,
                succeeded=True,
            ),
        )

        return content

    return generate_response


def _extract_token_usage(value: object) -> DeepSeekTokenUsage | None:
    if value is None:
        return None

    prompt_tokens = _nonnegative_integer_field(value, "prompt_tokens")
    completion_tokens = _nonnegative_integer_field(value, "completion_tokens")
    total_tokens = _nonnegative_integer_field(value, "total_tokens")

    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        return None

    return DeepSeekTokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_cache_hit_tokens=_nonnegative_integer_field(value, "prompt_cache_hit_tokens"),
        prompt_cache_miss_tokens=_nonnegative_integer_field(value, "prompt_cache_miss_tokens"),
    )


def _nonnegative_integer_field(value: object, field: str) -> int | None:
    candidate = getattr(value, field, None)

    if candidate is None:
        model_extra = getattr(value, "model_extra", None)

        if isinstance(model_extra, dict):
            candidate = model_extra.get(field)

    if not _is_nonnegative_integer(candidate):
        return None

    return candidate


def _is_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


def _observe(observer: DeepSeekCallObserver | None, observation: DeepSeekCallObservation) -> None:
    if observer is not None:
        observer(observation)
