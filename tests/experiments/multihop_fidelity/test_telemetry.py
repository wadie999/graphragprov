from datetime import UTC, datetime

import pytest

from graphragprov.experiments.multihop_fidelity.telemetry import (
    ExperimentTelemetry,
    LLMCallTelemetry,
    StageTelemetry,
    TokenUsage,
)


def _at(minute: int) -> datetime:
    return datetime(2026, 8, 16, 11, minute, tzinfo=UTC)


def test_case_telemetry_aggregates_realistic_h0_provider_calls() -> None:
    telemetry = ExperimentTelemetry(
        llm_calls=(
            LLMCallTelemetry(
                operation="graph.reference.extract",
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
                operation="graph.reference.correct",
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
                source_unit_id="u_source_a",
            ),
            LLMCallTelemetry(
                operation="query.reference.generate",
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
                attempt_index=2,
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
    assert telemetry.llm_calls[2].attempt_index == 2
    assert telemetry.stages[0].stage == "graph.materialization"


def test_failed_provider_call_preserves_latency_without_inventing_token_usage() -> None:
    telemetry = ExperimentTelemetry(
        llm_calls=(
            LLMCallTelemetry(
                operation="query.reference.generate",
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
                operation="query.reference.generate",
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

    # We must not fabricate cache totals when one call had no usage metadata.
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
            operation="graph.reference.extract",
            provider="deepseek",
            model="deepseek-v4-flash",
            started_at=_at(0),
            elapsed_seconds=1.0,
            usage=usage,
            error_message="should not be present",
        )

    with pytest.raises(ValueError, match="failed LLM calls require"):
        LLMCallTelemetry(
            operation="graph.reference.extract",
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
            operation="query.reference.generate",
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
        operation="graph.reference.extract",
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
        "operation": "graph.reference.extract",
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
