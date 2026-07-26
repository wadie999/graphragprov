"""Dependencies shared by GraphRAGProv API routes."""

from typing import Annotated, Protocol, cast

from fastapi import Depends, Request

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.experiments import MusiqueExperimentRepository
from graphragprov.qaagent import QAAgentRunResult


class MusiqueQARunner(Protocol):
    """Callable boundary for running one MuSiQue case."""

    def __call__(
        self,
        *,
        case: MusiqueCase,
        max_turns: int,
        model: str,
        max_tokens: int,
    ) -> QAAgentRunResult:
        """Execute one complete graph QA run."""
        ...


def get_experiment_repository(
    request: Request,
) -> MusiqueExperimentRepository:
    """Return the configured experiment repository."""

    return cast(
        MusiqueExperimentRepository,
        request.app.state.experiment_repository,
    )


def get_musique_qa_runner(
    request: Request,
) -> MusiqueQARunner:
    """Return the configured MuSiQue QA runner."""

    return cast(
        MusiqueQARunner,
        request.app.state.musique_qa_runner,
    )


ExperimentRepositoryDependency = Annotated[
    MusiqueExperimentRepository,
    Depends(get_experiment_repository),
]

MusiqueQARunnerDependency = Annotated[
    MusiqueQARunner,
    Depends(get_musique_qa_runner),
]