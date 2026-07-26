"""Configuration of graph-based question-answering agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QAContextMode = Literal["tuples", "graph_agent", "hybrid"]

QAGraphScope = Literal["case_all", "gold_support_oracle", "repository_all"]

QAAnswerVisibility = Literal["hidden", "oracle"]

QADecompositionVisibility = Literal["none", "hop_count", "gold_decomposition"]

_CONTEXT_MODES: tuple[QAContextMode, ...] = ("tuples", "graph_agent", "hybrid")

_GRAPH_SCOPES: tuple[QAGraphScope, ...] = ("case_all", "gold_support_oracle", "repository_all")

_ANSWER_VISIBILITIES: tuple[QAAnswerVisibility, ...] = ("hidden", "oracle")

_DECOMPOSITION_VISIBILITIES: tuple[QADecompositionVisibility, ...] = (
    "none",
    "hop_count",
    "gold_decomposition",
)


@dataclass(frozen=True, slots=True)
class QAAgentConfiguration:
    """Independent experimental choices controlling one QA-agent run."""

    context_mode: QAContextMode = "tuples"
    graph_scope: QAGraphScope = "case_all"
    answer_visibility: QAAnswerVisibility = "hidden"
    decomposition_visibility: QADecompositionVisibility = "hop_count"
    max_turns: int = 1

    def __post_init__(self) -> None:
        _validate_choice(name="context_mode", value=self.context_mode, allowed=_CONTEXT_MODES)
        _validate_choice(name="graph_scope", value=self.graph_scope, allowed=_GRAPH_SCOPES)
        _validate_choice(
            name="answer_visibility", value=self.answer_visibility, allowed=_ANSWER_VISIBILITIES
        )
        _validate_choice(
            name="decomposition_visibility",
            value=self.decomposition_visibility,
            allowed=_DECOMPOSITION_VISIBILITIES,
        )

        if self.max_turns <= 0:
            raise ValueError("max_turns must be positive")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable configuration."""

        return {
            "context_mode": self.context_mode,
            "graph_scope": self.graph_scope,
            "answer_visibility": self.answer_visibility,
            "decomposition_visibility": self.decomposition_visibility,
            "max_turns": self.max_turns,
        }


def _validate_choice(*, name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
