"""Dependencies shared by GraphRAGProv API routes."""

from collections.abc import Callable
from typing import Annotated, Literal, Protocol, cast

from fastapi import Depends, Request

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.experiments import MusiqueExperimentRepository
from graphragprov.provenance import SourceRegistry
from graphragprov.qaagent import QAAgentRunResult

MusiqueQueryScope = Literal["case_graphs", "whole_repository"]

QARunEventSink = Callable[[dict[str, object]], None]


class MusiqueQARunner(Protocol):
    """Callable boundary for running one MuSiQue case."""

    def __call__(
        self,
        *,
        case: MusiqueCase,
        question: str | None = None,
        max_turns: int,
        query_scope: MusiqueQueryScope = "case_graphs",
        include_oracle_tuples: bool = False,
        model: str,
        max_tokens: int,
        provenance_registry: SourceRegistry | None = None,
        event_sink: QARunEventSink | None = None,
    ) -> QAAgentRunResult:
        """Execute one complete graph QA run."""
        ...


def get_experiment_repository(request: Request) -> MusiqueExperimentRepository:
    """Return the configured experiment repository."""

    return cast(MusiqueExperimentRepository, request.app.state.experiment_repository)


def get_musique_qa_runner(request: Request) -> MusiqueQARunner:
    """Return the configured MuSiQue QA runner."""

    return cast(MusiqueQARunner, request.app.state.musique_qa_runner)


ExperimentRepositoryDependency = Annotated[
    MusiqueExperimentRepository, Depends(get_experiment_repository)
]

MusiqueQARunnerDependency = Annotated[MusiqueQARunner, Depends(get_musique_qa_runner)]
