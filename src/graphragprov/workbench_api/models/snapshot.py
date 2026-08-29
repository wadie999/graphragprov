"""Aggregate immutable case snapshot resource."""

from pydantic import BaseModel

from graphragprov.workbench_api.models.benchmark import BenchmarkRecord
from graphragprov.workbench_api.models.graph import GraphSnapshot
from graphragprov.workbench_api.models.metrics import MetricCollection
from graphragprov.workbench_api.models.run import QueryRun
from graphragprov.workbench_api.models.source import SourceUnitView


class CaseSnapshot(BaseModel):
    snapshot_id: str
    experiment_id: str
    case_id: str
    artifact_status: str
    failure_stage: str | None
    failure_message: str | None
    benchmark: BenchmarkRecord
    sources: tuple[SourceUnitView, ...]
    graph: GraphSnapshot | None
    metrics: MetricCollection
    reference_run: QueryRun | None
