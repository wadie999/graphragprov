"""Filesystem catalog over configured experiment artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from graphragprov.workbench_api.artifacts import ArtifactCase, read_artifact
from graphragprov.workbench_api.config import ExperimentConfig, WorkbenchConfig


@dataclass(frozen=True, slots=True)
class CaseLocator:
    experiment: ExperimentConfig
    case_id: str
    result_path: Path
    snapshot_id: str


class ExperimentCatalog:
    def __init__(self, config: WorkbenchConfig) -> None:
        self._config = config
        self._experiments = {item.experiment_id: item for item in config.experiments}
        self._snapshots: dict[str, CaseLocator] = {}

    def experiments(self) -> tuple[ExperimentConfig, ...]:
        return self._config.experiments

    def experiment(self, experiment_id: str) -> ExperimentConfig:
        try:
            return self._experiments[experiment_id]
        except KeyError:
            raise KeyError(f"unknown experiment: {experiment_id}") from None

    def cases(self, experiment_id: str) -> tuple[CaseLocator, ...]:
        experiment = self.experiment(experiment_id)
        locators = tuple(
            self._locator(experiment, case_id) for case_id in self._case_ids(experiment)
        )
        self._snapshots.update({item.snapshot_id: item for item in locators})
        return locators

    def locate(self, experiment_id: str, case_id: str) -> CaseLocator:
        experiment = self.experiment(experiment_id)
        locator = self._locator(experiment, case_id)
        if not locator.result_path.exists():
            raise KeyError(f"case artifact not found: {experiment_id}/{case_id}")
        self._snapshots[locator.snapshot_id] = locator
        return locator

    def locate_snapshot(self, snapshot_id: str) -> CaseLocator:
        cached = self._snapshots.get(snapshot_id)
        if cached is not None:
            return cached
        for experiment in self._config.experiments:
            for locator in self.cases(experiment.experiment_id):
                if locator.snapshot_id == snapshot_id:
                    return locator
        raise KeyError(f"unknown snapshot: {snapshot_id}")

    def read(self, locator: CaseLocator) -> ArtifactCase:
        return read_artifact(locator.result_path)

    def _locator(self, experiment: ExperimentConfig, case_id: str) -> CaseLocator:
        digest = sha256(f"{experiment.experiment_id}\0{case_id}".encode()).hexdigest()[:24]
        return CaseLocator(
            experiment=experiment,
            case_id=case_id,
            result_path=experiment.path / case_id / experiment.scope / "result.json",
            snapshot_id=f"s_{digest}",
        )

    def _case_ids(self, experiment: ExperimentConfig) -> tuple[str, ...]:
        if experiment.cohort_path is not None and experiment.cohort_path.exists():
            lines = experiment.cohort_path.read_text(encoding="utf-8").splitlines()
            return tuple(line.strip() for line in lines if line.strip())
        if not experiment.path.exists():
            return ()
        return tuple(sorted(path.name for path in experiment.path.iterdir() if path.is_dir()))
