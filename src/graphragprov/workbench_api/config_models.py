"""Typed workbench configuration objects."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

BenchmarkName = Literal["musique", "twowiki", "custom"]


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    experiment_id: str
    label: str
    benchmark: BenchmarkName
    path: Path
    scope: str = "support"
    cohort_path: Path | None = None
    dataset_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    base_url: str
    timeout_seconds: float = 30.0
    repository: str | None = None


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    model: str
    max_tokens: int
    timeout_seconds: float
    api_key_env: str


@dataclass(frozen=True, slots=True)
class WorkbenchConfig:
    root: Path
    state_dir: Path
    frontend_dist: Path
    host: str
    port: int
    frontend_dev_port: int
    graphdb: ServiceConfig
    sparqlprov: ServiceConfig
    planner: PlannerConfig
    experiments: tuple[ExperimentConfig, ...]