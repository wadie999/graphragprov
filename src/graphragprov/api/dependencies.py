"""Dependencies shared by GraphRAGProv API routes."""

from typing import Annotated, cast

from fastapi import Depends, Request

from graphragprov.experiments import MusiqueExperimentRepository


def get_experiment_repository(
    request: Request,
) -> MusiqueExperimentRepository:
    """Return the experiment repository configured for this application."""

    return cast(
        MusiqueExperimentRepository,
        request.app.state.experiment_repository,
    )


ExperimentRepositoryDependency = Annotated[
    MusiqueExperimentRepository,
    Depends(get_experiment_repository),
]