"""Tests for multi-hop experimental telemetry."""

from datetime import UTC, datetime

import pytest

from graphragprov.experiments.multihop_fidelity.telemetry import (
    ExperimentTelemetry,
    ExperimentTelemetryRecorder,
    LLMCallTelemetry,
    StageTelemetry,
    TokenUsage,
)
from graphragprov.providers.deepseek import DeepSeekCallObservation, DeepSeekTokenUsage


def _at(minute: int) -> datetime:
    return datetime(2026, 8, 16, 11, minute, tzinfo=UTC)


def test_case_telemetry_aggregates_realistic_h0_provider_calls() -> None:
    telemetry = ExperimentTelemetry(
        llm_calls=(
            LLMCallTelemetry(
                operation="graph.reference",
                provider="deepseek",
                model="deepseek-v4-flash",
                started_at=_at(0),
                elapsed_seconds=2.4,
                usage=TokenUsage(
                    input_tokens=4_800,
                    output_tokens=900,
                    total_tokens=5_700,
                    cached_input_tokens=3_200,
                    uncached_input_tokens=1_600,
                ),
                source_unit_id="u_source_a",
            ),
            LLMCallTelemetry(
                operation="graph.reference",
                provider="deepseek",
                model="deepseek-v4-flash",
                started_at=_at(1),
                elapsed_seconds=1.1,
                usage=TokenUsage(
                    input_tokens=1_700,
                    output_tokens=260,
                    total_tokens=1_960,
                    cached_input_tokens=1_000,
                    uncached_input_tokens=700,
                ),
                attempt_index=2,
                source_unit_id="u_source_a",
            ),
            LLMCallTelemetry(
                operation="query.reference",
                provider="deepseek",
                model="deepseek-v4-flash",
                started_at=_at(2),
                elapsed_seconds=3.0,
                usage=TokenUsage(
                    input_tokens=6_100,
                    output_tokens=1_100,
                    total_tokens=7_200,
                    cached_input_tokens=4_000,
                    uncached_input_tokens=2_100,
                ),
            ),
        ),
        stages=(
            StageTelemetry(stage="graph.materialization", started_at=_at(3), elapsed_seconds=0.18),
            StageTelemetry(stage="provenance.decode", started_at=_at(4), elapsed_seconds=0.03),
        ),
    )

    assert telemetry.usage_complete is True
    assert telemetry.input_tokens == 12_600
    assert telemetry.output_tokens == 2_260
    assert telemetry.total_tokens == 14_860
    assert telemetry.cached_input_tokens == 8_200
    assert telemetry.uncached_input_tokens == 4_400
    assert telemetry.cumulative_llm_seconds == pytest.approx(6.5)

    assert telemetry.llm_calls[0].source_unit_id == "u_source_a"
    assert telemetry.llm_calls[1].attempt_index == 2
    assert telemetry.stages[0].stage == "graph.materialization"


def test_failed_provider_call_preserves_latency_without_inventing_token_usage() -> None:
    telemetry = ExperimentTelemetry(
        llm_calls=(
            LLMCallTelemetry(
                operation="query.reference",
                provider="deepseek",
                model="deepseek-v4-flash",
                started_at=_at(0),
                elapsed_seconds=12.8,
                usage=None,
                succeeded=False,
                error_type="APITimeoutError",
                error_message="request timed out",
            ),
            LLMCallTelemetry(
                operation="query.reference",
                provider="deepseek",
                model="deepseek-v4-flash",
                started_at=_at(1),
                elapsed_seconds=2.0,
                usage=TokenUsage(
                    input_tokens=2_000,
                    output_tokens=400,
                    total_tokens=2_400,
                    cached_input_tokens=1_500,
                    uncached_input_tokens=500,
                ),
                attempt_index=2,
            ),
        )
    )

    assert telemetry.usage_complete is False
    assert telemetry.input_tokens == 2_000
    assert telemetry.output_tokens == 400
    assert telemetry.total_tokens == 2_400

    assert telemetry.cached_input_tokens is None
    assert telemetry.uncached_input_tokens is None

    assert telemetry.cumulative_llm_seconds == pytest.approx(14.8)


def test_token_usage_rejects_inconsistent_provider_accounting() -> None:
    with pytest.raises(ValueError, match="total tokens must equal"):
        TokenUsage(input_tokens=100, output_tokens=20, total_tokens=119)

    with pytest.raises(ValueError, match="must sum to input tokens"):
        TokenUsage(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cached_input_tokens=70,
            uncached_input_tokens=20,
        )


def test_llm_telemetry_rejects_incoherent_success_and_failure_state() -> None:
    usage = TokenUsage(input_tokens=10, output_tokens=2, total_tokens=12)

    with pytest.raises(ValueError, match="successful LLM calls"):
        LLMCallTelemetry(
            operation="graph.reference",
            provider="deepseek",
            model="deepseek-v4-flash",
            started_at=_at(0),
            elapsed_seconds=1.0,
            usage=usage,
            error_message="should not be present",
        )

    with pytest.raises(ValueError, match="failed LLM calls require"):
        LLMCallTelemetry(
            operation="graph.reference",
            provider="deepseek",
            model="deepseek-v4-flash",
            started_at=_at(0),
            elapsed_seconds=1.0,
            usage=None,
            succeeded=False,
        )


def test_measurements_require_timezone_aware_start_times() -> None:
    naive = datetime(2026, 8, 16, 11, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        LLMCallTelemetry(
            operation="query.reference",
            provider="deepseek",
            model="deepseek-v4-flash",
            started_at=naive,
            elapsed_seconds=1.0,
            usage=TokenUsage(input_tokens=10, output_tokens=2, total_tokens=12),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        StageTelemetry(stage="graphdb.semantic", started_at=naive, elapsed_seconds=0.1)


def test_telemetry_serialization_is_json_ready_and_preserves_exact_usage() -> None:
    call = LLMCallTelemetry(
        operation="graph.reference",
        provider="deepseek",
        model="deepseek-v4-flash",
        started_at=_at(0),
        elapsed_seconds=1.25,
        usage=TokenUsage(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cached_input_tokens=40,
            uncached_input_tokens=60,
        ),
        source_unit_id="u_a",
    )

    assert call.to_dict() == {
        "operation": "graph.reference",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "started_at": "2026-08-16T11:00:00+00:00",
        "elapsed_seconds": 1.25,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "cached_input_tokens": 40,
            "uncached_input_tokens": 60,
        },
        "attempt_index": 1,
        "source_unit_id": "u_a",
        "succeeded": True,
        "error_type": None,
        "error_message": None,
    }


def test_recorder_translates_exact_deepseek_observations() -> None:
    recorder = ExperimentTelemetryRecorder()

    observer = recorder.deepseek_observer(operation="graph.reference", source_unit_id="u_album")

    observer(
        DeepSeekCallObservation(
            requested_model="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            started_at=_at(0),
            elapsed_seconds=2.5,
            usage=DeepSeekTokenUsage(
                prompt_tokens=1_250,
                completion_tokens=310,
                total_tokens=1_560,
                prompt_cache_hit_tokens=900,
                prompt_cache_miss_tokens=350,
            ),
            succeeded=True,
        )
    )

    observer(
        DeepSeekCallObservation(
            requested_model="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            started_at=_at(1),
            elapsed_seconds=1.2,
            usage=DeepSeekTokenUsage(
                prompt_tokens=600,
                completion_tokens=100,
                total_tokens=700,
                prompt_cache_hit_tokens=400,
                prompt_cache_miss_tokens=200,
            ),
            succeeded=True,
        )
    )

    telemetry = recorder.snapshot()

    assert len(telemetry.llm_calls) == 2

    first = telemetry.llm_calls[0]
    second = telemetry.llm_calls[1]

    assert first.operation == "graph.reference"
    assert first.provider == "deepseek"
    assert first.source_unit_id == "u_album"
    assert first.attempt_index == 1

    assert first.usage is not None
    assert first.usage.input_tokens == 1_250
    assert first.usage.output_tokens == 310
    assert first.usage.cached_input_tokens == 900
    assert first.usage.uncached_input_tokens == 350

    assert second.attempt_index == 2

    assert telemetry.input_tokens == 1_850
    assert telemetry.output_tokens == 410
    assert telemetry.total_tokens == 2_260
    assert telemetry.cached_input_tokens == 1_300
    assert telemetry.uncached_input_tokens == 550


def test_recorder_preserves_failed_deepseek_call_without_usage() -> None:
    recorder = ExperimentTelemetryRecorder()

    observer = recorder.deepseek_observer(operation="query.reference")

    observer(
        DeepSeekCallObservation(
            requested_model="deepseek-v4-flash",
            response_model=None,
            started_at=_at(0),
            elapsed_seconds=8.0,
            usage=None,
            succeeded=False,
            error_type="RuntimeError",
            error_message="connection failed",
        )
    )

    telemetry = recorder.snapshot()

    assert len(telemetry.llm_calls) == 1

    call = telemetry.llm_calls[0]

    assert call.operation == "query.reference"
    assert call.model == "deepseek-v4-flash"
    assert call.succeeded is False
    assert call.usage is None
    assert call.error_type == "RuntimeError"
    assert call.error_message == "connection failed"

    assert telemetry.usage_complete is False
    assert telemetry.total_tokens == 0


def test_stage_recorder_measures_successful_operation() -> None:
    recorder = ExperimentTelemetryRecorder()

    with recorder.measure_stage("graph.materialization"):
        value = sum(range(100))

    assert value == 4_950

    telemetry = recorder.snapshot()

    assert len(telemetry.stages) == 1

    stage = telemetry.stages[0]

    assert stage.stage == "graph.materialization"
    assert stage.attempt_index == 1
    assert stage.elapsed_seconds >= 0
    assert stage.started_at.utcoffset() is not None


def test_stage_recorder_keeps_latency_when_operation_fails() -> None:
    recorder = ExperimentTelemetryRecorder()

    with pytest.raises(RuntimeError, match="GraphDB unavailable"):
        with recorder.measure_stage("graphdb.semantic"):
            raise RuntimeError("GraphDB unavailable")

    telemetry = recorder.snapshot()

    assert len(telemetry.stages) == 1

    stage = telemetry.stages[0]

    assert stage.stage == "graphdb.semantic"
    assert stage.elapsed_seconds >= 0


def test_snapshot_does_not_change_after_later_recordings() -> None:
    recorder = ExperimentTelemetryRecorder()

    observer = recorder.deepseek_observer(operation="graph.reference")

    before = recorder.snapshot()

    observer(
        DeepSeekCallObservation(
            requested_model="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            started_at=_at(0),
            elapsed_seconds=1.0,
            usage=DeepSeekTokenUsage(
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                prompt_cache_hit_tokens=60,
                prompt_cache_miss_tokens=40,
            ),
            succeeded=True,
        )
    )

    after = recorder.snapshot()

    assert before.llm_calls == ()
    assert len(after.llm_calls) == 1
