"""Catalog resources exposed by the workbench API."""

from typing import Literal

from pydantic import BaseModel


class ExperimentSummary(BaseModel):
    experiment_id: str
    label: str
    benchmark: Literal["musique", "twowiki"]
    case_count: int
    available_case_count: int


class ExperimentList(BaseModel):
    items: tuple[ExperimentSummary, ...]
    total: int


class CaseSummary(BaseModel):
    experiment_id: str
    case_id: str
    snapshot_id: str
    question: str
    expected_answer: str
    hop_count: int
    artifact_status: str
    graph_available: bool
    provenance_available: bool


class CaseList(BaseModel):
    experiment_id: str
    items: tuple[CaseSummary, ...]
    total: int
