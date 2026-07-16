"""Tests for QA-agent configuration."""

import json
from typing import cast

import pytest

from graphragprov.qaagent import (
    QAAgentConfiguration,
    QAAnswerVisibility,
    QAContextMode,
    QADecompositionVisibility,
    QAGraphScope,
)


def test_default_configuration_is_primary_benchmark_setting() -> None:
    configuration = QAAgentConfiguration()

    assert configuration.to_dict() == {
        "context_mode": "tuples",
        "graph_scope": "case_all",
        "answer_visibility": "hidden",
        "decomposition_visibility": "hop_count",
        "max_turns": 1,
    }


def test_configuration_is_json_serializable() -> None:
    configuration = QAAgentConfiguration(
        context_mode="graph_agent",
        graph_scope="case_all",
        answer_visibility="hidden",
        decomposition_visibility="none",
        max_turns=5,
    )

    serialized = json.dumps(
        configuration.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
    )

    assert json.loads(serialized) == configuration.to_dict()


def test_max_turns_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="max_turns must be positive",
    ):
        QAAgentConfiguration(max_turns=0)


def test_invalid_context_mode_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="context_mode must be one of",
    ):
        QAAgentConfiguration(
            context_mode=cast(
                QAContextMode,
                "invalid",
            )
        )


def test_invalid_graph_scope_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="graph_scope must be one of",
    ):
        QAAgentConfiguration(
            graph_scope=cast(
                QAGraphScope,
                "invalid",
            )
        )


def test_invalid_answer_visibility_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="answer_visibility must be one of",
    ):
        QAAgentConfiguration(
            answer_visibility=cast(
                QAAnswerVisibility,
                "invalid",
            )
        )


def test_invalid_decomposition_visibility_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="decomposition_visibility must be one of",
    ):
        QAAgentConfiguration(
            decomposition_visibility=cast(
                QADecompositionVisibility,
                "invalid",
            )
        )
