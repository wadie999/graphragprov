"""Runtime and provider-usage measurements for multi-hop fidelity experiments."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from graphragprov.providers.deepseek import DeepSeekCallObservation, DeepSeekCallObserver


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Exact token accounting reported for one provider call."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None
    uncached_input_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError("input tokens must not be negative")

        if self.output_tokens < 0:
            raise ValueError("output tokens must not be negative")

        if self.total_tokens < 0:
            raise ValueError("total tokens must not be negative")

        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total tokens must equal input tokens plus output tokens")

        if self.cached_input_tokens is not None:
            if self.cached_input_tokens < 0:
                raise ValueError("cached input tokens must not be negative")

            if self.cached_input_tokens > self.input_tokens:
                raise ValueError("cached input tokens must not exceed input tokens")

        if self.uncached_input_tokens is not None:
            if self.uncached_input_tokens < 0:
                raise ValueError("uncached input tokens must not be negative")

            if self.uncached_input_tokens > self.input_tokens:
                raise ValueError("uncached input tokens must not exceed input tokens")

        if self.cached_input_tokens is not None and self.uncached_input_tokens is not None:
            if self.cached_input_tokens + self.uncached_input_tokens != self.input_tokens:
                raise ValueError(
                    "cached and uncached input tokens must sum to input tokens "
                    "when both are reported"
                )

    def to_dict(self) -> dict[str, int | None]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "uncached_input_tokens": self.uncached_input_tokens,
        }


@dataclass(frozen=True, slots=True)
class LLMCallTelemetry:
    """One measured LLM provider call made during an experiment."""

    operation: str
    provider: str
    model: str
    started_at: datetime
    elapsed_seconds: float
    usage: TokenUsage | None
    attempt_index: int = 1
    source_unit_id: str | None = None
    succeeded: bool = True
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("LLM operation must not be empty")

        if not self.provider.strip():
            raise ValueError("LLM provider must not be empty")

        if not self.model.strip():
            raise ValueError("LLM model must not be empty")

        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("LLM call start time must be timezone-aware")

        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("LLM elapsed seconds must be finite and non-negative")

        if self.attempt_index < 1:
            raise ValueError("LLM attempt index must be positive")

        if self.source_unit_id is not None and not self.source_unit_id.strip():
            raise ValueError("source unit ID must not be empty when provided")

        if self.succeeded:
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("successful LLM calls must not contain error information")
        elif not self.error_message:
            raise ValueError("failed LLM calls require an error message")

        if self.error_type is not None and not self.error_message:
            raise ValueError("LLM error type requires an error message")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "operation": self.operation,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
            "usage": (self.usage.to_dict() if self.usage is not None else None),
            "attempt_index": self.attempt_index,
            "source_unit_id": self.source_unit_id,
            "succeeded": self.succeeded,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True, slots=True)
class StageTelemetry:
    """Wall-clock measurement for one non-provider experimental stage."""

    stage: str
    started_at: datetime
    elapsed_seconds: float
    attempt_index: int = 1

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage must not be empty")

        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("stage start time must be timezone-aware")

        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("stage elapsed seconds must be finite and non-negative")

        if self.attempt_index < 1:
            raise ValueError("stage attempt index must be positive")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "stage": self.stage,
            "started_at": self.started_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
            "attempt_index": self.attempt_index,
        }


@dataclass(frozen=True, slots=True)
class ExperimentTelemetry:
    """Ordered telemetry records for one experimental case."""

    llm_calls: tuple[LLMCallTelemetry, ...] = ()
    stages: tuple[StageTelemetry, ...] = ()

    @property
    def usage_complete(self) -> bool:
        """Return whether every LLM call carries provider-reported usage."""

        return all(call.usage is not None for call in self.llm_calls)

    @property
    def input_tokens(self) -> int:
        """Return input tokens from calls that reported usage."""

        return sum(call.usage.input_tokens for call in self.llm_calls if call.usage is not None)

    @property
    def output_tokens(self) -> int:
        """Return output tokens from calls that reported usage."""

        return sum(call.usage.output_tokens for call in self.llm_calls if call.usage is not None)

    @property
    def total_tokens(self) -> int:
        """Return total tokens from calls that reported usage."""

        return sum(call.usage.total_tokens for call in self.llm_calls if call.usage is not None)

    @property
    def cached_input_tokens(self) -> int | None:
        """Return cached input tokens when every call reports cache accounting."""

        if not self.usage_complete:
            return None

        values = [
            call.usage.cached_input_tokens for call in self.llm_calls if call.usage is not None
        ]

        if any(value is None for value in values):
            return None

        return sum(value for value in values if value is not None)

    @property
    def uncached_input_tokens(self) -> int | None:
        """Return uncached input tokens when every call reports cache accounting."""

        if not self.usage_complete:
            return None

        values = [
            call.usage.uncached_input_tokens for call in self.llm_calls if call.usage is not None
        ]

        if any(value is None for value in values):
            return None

        return sum(value for value in values if value is not None)

    @property
    def cumulative_llm_seconds(self) -> float:
        """Return cumulative provider-call latency without implying case wall time."""

        return sum(call.elapsed_seconds for call in self.llm_calls)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {
            "llm_calls": [call.to_dict() for call in self.llm_calls],
            "stages": [stage.to_dict() for stage in self.stages],
            "totals": {
                "usage_complete": self.usage_complete,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "cached_input_tokens": self.cached_input_tokens,
                "uncached_input_tokens": self.uncached_input_tokens,
                "cumulative_llm_seconds": self.cumulative_llm_seconds,
            },
        }


class ExperimentTelemetryRecorder:
    """Mutable recorder used while one experimental case is executing."""

    def __init__(self) -> None:
        self._llm_calls: list[LLMCallTelemetry] = []
        self._stages: list[StageTelemetry] = []

    def deepseek_observer(
        self, *, operation: str, source_unit_id: str | None = None
    ) -> DeepSeekCallObserver:
        """Create an observer that classifies DeepSeek calls for one operation."""

        if not operation.strip():
            raise ValueError("LLM operation must not be empty")

        if source_unit_id is not None and not source_unit_id.strip():
            raise ValueError("source unit ID must not be empty when provided")

        call_index = 0

        def observe(observation: DeepSeekCallObservation) -> None:
            nonlocal call_index

            call_index += 1

            usage = (
                None
                if observation.usage is None
                else TokenUsage(
                    input_tokens=(observation.usage.prompt_tokens),
                    output_tokens=(observation.usage.completion_tokens),
                    total_tokens=(observation.usage.total_tokens),
                    cached_input_tokens=(observation.usage.prompt_cache_hit_tokens),
                    uncached_input_tokens=(observation.usage.prompt_cache_miss_tokens),
                )
            )

            model = observation.response_model or observation.requested_model

            self._llm_calls.append(
                LLMCallTelemetry(
                    operation=operation,
                    provider="deepseek",
                    model=model,
                    started_at=observation.started_at,
                    elapsed_seconds=observation.elapsed_seconds,
                    usage=usage,
                    attempt_index=call_index,
                    source_unit_id=source_unit_id,
                    succeeded=observation.succeeded,
                    error_type=observation.error_type,
                    error_message=observation.error_message,
                )
            )

        return observe

    @contextmanager
    def measure_stage(self, stage: str, *, attempt_index: int = 1) -> Iterator[None]:
        """Measure one local or remote non-LLM stage with wall-clock time."""

        if not stage.strip():
            raise ValueError("stage must not be empty")

        if attempt_index < 1:
            raise ValueError("stage attempt index must be positive")

        started_at = datetime.now(UTC)
        started_clock = perf_counter()

        try:
            yield
        finally:
            self._stages.append(
                StageTelemetry(
                    stage=stage,
                    started_at=started_at,
                    elapsed_seconds=(perf_counter() - started_clock),
                    attempt_index=attempt_index,
                )
            )

    def snapshot(self) -> ExperimentTelemetry:
        """Return an immutable snapshot of all observations recorded so far."""

        return ExperimentTelemetry(llm_calls=tuple(self._llm_calls), stages=tuple(self._stages))
