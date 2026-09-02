"""Catalog resources exposed by the workbench API."""

from typing import Literal

from pydantic import BaseModel

ExperimentOrigin = Literal["curated", "workspace"]
BenchmarkName = Literal["musique", "twowiki", "custom"]


class ExperimentSummary(BaseModel):
    experiment_id: str
    label: str
    benchmark: BenchmarkName
    origin: ExperimentOrigin = "curated"
    case_count: int
    available_case_count: int


class ExperimentList(BaseModel):
    items: tuple[ExperimentSummary, ...]
    total: int


class CaseSummary(BaseModel):
    experiment_id: str
    case_id: str
    label: str
    snapshot_id: str
    origin: ExperimentOrigin = "curated"
    question: str
    expected_answer: str
    hop_count: int | None
    artifact_status: str
    graph_available: bool
    provenance_available: bool


class CaseList(BaseModel):
    experiment_id: str
    items: tuple[CaseSummary, ...]
    total: int