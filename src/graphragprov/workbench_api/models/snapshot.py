"""Aggregate immutable case snapshot resource."""

from typing import Literal

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
    case_label: str
    origin: Literal["curated", "workspace"] = "curated"

    artifact_status: str
    failure_stage: str | None
    failure_message: str | None

    build_id: str | None = None
    build_mode: Literal["source_only", "question_conditioned"] | None = None
    build_question: str | None = None

    benchmark: BenchmarkRecord | None
    sources: tuple[SourceUnitView, ...]
    graph: GraphSnapshot | None
    metrics: MetricCollection
    reference_run: QueryRun | None
